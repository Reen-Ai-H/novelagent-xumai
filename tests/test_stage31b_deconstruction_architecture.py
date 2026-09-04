from __future__ import annotations

import base64
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import RLock
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

import main
from app import deconstruction_routes, entry_routes, independent_routes
from app.core.account_store import AccountStore
from app.core.ai_store import AIStore
from app.core.deconstruction_service import DeconstructionService
from app.core.deconstruction_store import DeconstructionStore
from app.core.entry_service import EntryService
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore
from schemas.deconstruction import DeconstructionResponse


class _FailingDispatch:
    def __init__(self) -> None:
        self.calls = 0

    def reconcile_outbox(self, project_id: str, account_id: str, **kwargs: object) -> int:
        del project_id, account_id, kwargs
        self.calls += 1
        raise OSError("dispatch unavailable")


class _TrackingLock:
    """A test-only RLock that exposes whether the deconstruction lock is held."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._depth = 0

    @property
    def held(self) -> bool:
        return self._depth > 0

    def __enter__(self):
        self._lock.acquire()
        self._depth += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._depth -= 1
        self._lock.release()
        return False


class Stage31BDeconstructionArchitectureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        accounts = AccountStore(root / "accounts.json")
        projects = JsonProjectStore(root / "projects")
        independent = IndependentWorkspaceService(
            store=IndependentStore(root / "independent"),
            projects=projects,
        )
        entry = EntryService(
            accounts=accounts,
            projects=projects,
            independent=independent.store,
            ai=AIStore(root / "ai"),
        )
        deconstruction = DeconstructionService(
            independent=independent,
            store=DeconstructionStore(root / "deconstruction"),
        )
        independent.deconstruction_service = deconstruction
        self.independent = independent
        self.deconstruction = deconstruction
        self.patches = [
            patch.object(entry_routes, "account_store", accounts),
            patch.object(entry_routes, "entry_service", entry),
            patch.object(independent_routes, "independent_service", independent),
            patch.object(deconstruction_routes, "deconstruction_service", deconstruction),
        ]
        for patcher in self.patches:
            patcher.start()
        self.addCleanup(self._cleanup)
        self.client = TestClient(main.app)

    def _cleanup(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def _login(self, email: str = "stage31b@example.com") -> str:
        response = self.client.post("/api/auth/email", json={"email": email})
        self.assertEqual(response.status_code, 200)
        return response.json()["account"]["account_id"]

    def _account_id(self) -> str:
        return self.client.get("/api/auth/session").json()["account"]["account_id"]

    def _project(self, title: str = "拆解架构测试") -> str:
        self._login()
        response = self.client.post(
            "/api/library/projects",
            json={"title": title, "mode": "independent", "brief": "用于验证后端拆解合同。"},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["project"]["project_id"]

    def _start_and_save(self, project_id: str, content: str) -> dict:
        started = self.client.post(
            f"/api/independent/projects/{project_id}/start",
            json={"source": "blank"},
        )
        self.assertEqual(started.status_code, 200)
        chapter = started.json()["active_version"]["chapters"][0]
        saved = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/draft",
            json={"content": content, "expected_revision": chapter["server_revision"]},
        )
        self.assertEqual(saved.status_code, 200)
        return saved.json()["chapter"]

    def _complete_direct(self, project_id: str, chapter: dict) -> None:
        task = self.independent.complete_chapter(
            project_id,
            self._account_id(),
            chapter["chapter_id"],
            content=chapter["content"],
            expected_revision=chapter["server_revision"],
            idempotency_key=f"stage31b-{project_id}-{chapter['chapter_id']}",
        )
        self.assertEqual(task.status, "queued")

    def _complete_deconstruction(self, project_id: str, chapter: dict):
        self.independent.deconstruction_service = None
        self._complete_direct(project_id, chapter)
        self.independent.deconstruction_service = self.deconstruction
        self.deconstruction.process_background_tasks()
        return self.client.get(f"/api/independent/projects/{project_id}/deconstruction").json()

    def test_saved_body_survives_dispatch_failure_and_outbox_retries(self) -> None:
        project_id = self._project("派发失败不回滚正文")
        chapter = self._start_and_save(project_id, "人物：林舟。线索：旧信。林舟在雾里打开了门。")
        failing = _FailingDispatch()
        self.independent.deconstruction_service = failing

        response = self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/complete",
            json={
                "content": chapter["content"],
                "expected_revision": chapter["server_revision"],
                "idempotency_key": "dispatch-failure-once",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(failing.calls, 1)
        record = self.independent.store.load(project_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertTrue(record.deconstruction_outbox)
        self.assertGreaterEqual(record.deconstruction_outbox[0].attempts, 1)
        self.assertEqual(record.versions[0].chapters[0].formal_content, chapter["content"])
        self.assertIsNone(self.deconstruction.store.load(project_id))

        self.independent.deconstruction_service = self.deconstruction
        self.deconstruction.process_background_tasks()
        persisted = self.deconstruction.store.load(project_id)
        self.assertIsNotNone(persisted)
        assert persisted is not None
        self.assertEqual(persisted.documents[0].status, "completed")
        self.assertEqual(self.independent.store.load(project_id).deconstruction_outbox, [])

    def test_outbox_recovers_after_service_recreation_without_browser_request(self) -> None:
        project_id = self._project("重启后恢复拆解")
        chapter = self._start_and_save(project_id, "人物：顾遥。剧情线：寻找灯塔。顾遥收好一枚旧钥匙。")
        self.independent.deconstruction_service = None
        self._complete_direct(project_id, chapter)
        original = self.independent.store.load(project_id)
        self.assertIsNotNone(original)
        assert original is not None
        self.assertEqual(len(original.deconstruction_outbox), 1)

        restarted_independent = IndependentWorkspaceService(
            store=self.independent.store,
            projects=self.independent.projects,
        )
        restarted_deconstruction = DeconstructionService(
            independent=restarted_independent,
            store=self.deconstruction.store,
        )
        restarted_independent.deconstruction_service = restarted_deconstruction
        self.assertGreaterEqual(restarted_deconstruction.reconcile_all_outboxes(), 1)
        restarted_deconstruction.process_background_tasks()
        persisted = restarted_deconstruction.store.load(project_id)
        self.assertIsNotNone(persisted)
        assert persisted is not None
        self.assertEqual(len(persisted.documents), 1)
        self.assertEqual(persisted.documents[0].status, "completed")
        self.assertEqual(restarted_independent.store.load(project_id).deconstruction_outbox, [])

    def test_unexpected_analysis_exception_becomes_safe_retryable_failure(self) -> None:
        project_id = self._project("拆解异常可重试")
        chapter = self._start_and_save(project_id, "人物：林舟。冲突：旧港关闭。")
        self.independent.deconstruction_service = None
        self._complete_direct(project_id, chapter)
        self.independent.deconstruction_service = self.deconstruction
        self.assertEqual(self.deconstruction.reconcile_outbox(project_id, self._account_id()), 1)
        queued = self.deconstruction.store.load(project_id)
        self.assertIsNotNone(queued)
        assert queued is not None
        document_id = queued.active_document_id
        self.assertIsNotNone(document_id)
        assert document_id is not None

        with patch.object(self.deconstruction, "_build_document", side_effect=RuntimeError("private-sentinel")):
            result = self.deconstruction.run_document(project_id, self._account_id(), document_id)
        self.assertEqual(result.status, "failed_retryable")
        self.assertNotIn("private-sentinel", result.error_message or "")
        public = self.client.get(f"/api/independent/projects/{project_id}/deconstruction").json()
        self.assertEqual(public["status"], "failed_retryable")
        self.assertEqual(public["document"]["overview"], None)

        self.deconstruction.retry(project_id, self._account_id(), document_id)
        self.deconstruction.process_background_tasks()
        recovered = self.client.get(f"/api/independent/projects/{project_id}/deconstruction").json()
        self.assertEqual(recovered["effective_status"], "completed")
        self.assertIsNotNone(recovered["result"])

    def test_corrupt_sidecar_does_not_stop_other_project_recovery(self) -> None:
        project_id = self._project("有效侧车")
        chapter = self._start_and_save(project_id, "人物：林舟。剧情线：寻找灯塔。")
        self._complete_deconstruction(project_id, chapter)
        self.deconstruction.store.base_dir.mkdir(parents=True, exist_ok=True)
        (self.deconstruction.store.base_dir / "corrupt-sidecar.json").write_text("{bad", encoding="utf-8")

        records = self.deconstruction.store.list_records()
        self.assertTrue(any(item.project_id == project_id for item in records))
        self.deconstruction.process_background_tasks()
        self.assertEqual(self.deconstruction.store.load(project_id).documents[0].status, "completed")

    def test_source_reads_are_outside_deconstruction_lock_and_concurrent_calls_finish(self) -> None:
        project_id = self._project("锁顺序")
        chapter = self._start_and_save(project_id, "人物：林舟。线索：旧信。")
        self.independent.deconstruction_service = None
        self._complete_direct(project_id, chapter)
        self.independent.deconstruction_service = self.deconstruction
        document = self.deconstruction.enqueue_for_project(project_id, self._account_id())
        tracking_lock = _TrackingLock()
        original_source = self.deconstruction._source

        def source_outside_lock(current_project_id: str, current_account_id: str):
            self.assertFalse(tracking_lock.held)
            return original_source(current_project_id, current_account_id)

        with patch.object(self.deconstruction, "_lock", tracking_lock), patch.object(
            self.deconstruction, "_source", side_effect=source_outside_lock
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                enqueue_future = pool.submit(
                    self.deconstruction.enqueue_for_project,
                    project_id,
                    self._account_id(),
                )
                run_future = pool.submit(
                    self.deconstruction.run_document,
                    project_id,
                    self._account_id(),
                    document.document_id,
                )
                self.assertEqual(enqueue_future.result(timeout=3).document_id, document.document_id)
                self.assertIn(run_future.result(timeout=3).status, {"queued", "running", "completed"})

        self.deconstruction.process_background_tasks()
        self.assertEqual(self.deconstruction.store.load(project_id).documents[0].status, "completed")

    def test_evidence_has_utf16_source_contract_and_old_version_does_not_jump(self) -> None:
        project_id = self._project("证据来源合同")
        content = "  🧭人物：林舟。剧情线：寻找旧港。线索：门缝里的蓝纸。林舟决定开门。"
        chapter = self._start_and_save(project_id, content)
        done = self._complete_deconstruction(project_id, chapter)
        item = next(item for item in done["document"]["evidence"] if "人物" in item["excerpt"])
        position = content.find(item["excerpt"].strip())
        self.assertGreaterEqual(position, 0)
        expected_start = len(content[:position].encode("utf-16-le")) // 2
        self.assertEqual(item["start_offset"], expected_start)
        self.assertEqual(item["offset_unit"], "utf16_code_unit")
        self.assertEqual(item["document_id"], done["document"]["document_id"])
        self.assertEqual(item["source_version_id"], done["source"]["version_id"])
        self.assertEqual(item["source_hash"], done["source"]["hash"])

        old_evidence_id = item["evidence_id"]
        self.independent.save_draft(
            project_id,
            self._account_id(),
            chapter["chapter_id"],
            content=content + " 新的回声出现。",
            title=None,
            expected_revision=chapter["server_revision"],
        )
        self.independent.resolve_changes(project_id, self._account_id(), "rebuild")
        historical = self.deconstruction.evidence(project_id, self._account_id(), old_evidence_id)
        self.assertFalse(historical["source_matches_current"])
        self.assertTrue(historical["historical"])
        self.assertFalse(historical["chapter"]["source_available"])

    def test_canonical_status_hides_completed_result_while_author_changes_are_pending(self) -> None:
        project_id = self._project("统一状态")
        chapter = self._start_and_save(project_id, "人物：林舟。剧情线：寻找灯塔。")
        done = self._complete_deconstruction(project_id, chapter)
        self.assertEqual(done["effective_status"], "completed")
        self.assertEqual(done["run_status"], "completed")
        self.assertTrue(done["source_match"])
        self.assertIsNotNone(done["result"])
        self.assertIsNotNone(done["deconstruction"]["result"])
        DeconstructionResponse.model_validate(done)

        self.independent.save_draft(
            project_id,
            self._account_id(),
            chapter["chapter_id"],
            content=chapter["content"] + " 作者补写。",
            title=None,
            expected_revision=chapter["server_revision"],
        )
        pending = self.client.get(f"/api/independent/projects/{project_id}/deconstruction").json()
        self.assertEqual(pending["effective_status"], "rebuild_required")
        self.assertEqual(pending["run_status"], "completed")
        self.assertIsNone(pending["result"])
        self.assertIsNone(pending["deconstruction"]["result"])
        self.assertIsNone(pending["document"])
        DeconstructionResponse.model_validate(pending)

    def test_routes_have_strict_public_response_models_and_source_precondition(self) -> None:
        paths = main.app.openapi()["paths"]
        for route in (
            "/api/independent/projects/{project_id}/deconstruction",
            "/api/independent/projects/{project_id}/deconstruction/rebuild",
            "/api/independent/projects/{project_id}/deconstruction/retry",
            "/api/independent/projects/{project_id}/deconstruction/evidence/{evidence_id}",
        ):
            operations = paths[route]
            for operation in operations.values():
                if not isinstance(operation, dict) or "responses" not in operation:
                    continue
                schemas = [
                    response.get("content", {}).get("application/json", {}).get("schema", {})
                    for response in operation["responses"].values()
                    if isinstance(response, dict)
                ]
                self.assertTrue(any("$ref" in schema for schema in schemas))

        project_id = self._project("来源前置条件")
        chapter = self._start_and_save(project_id, "人物：林舟。")
        done = self._complete_deconstruction(project_id, chapter)
        response = self.client.post(
            f"/api/independent/projects/{project_id}/deconstruction/rebuild",
            json={"expected_source_hash": "0" * 64},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "source_conflict")
        self.assertEqual(
            response.json()["detail"]["data"]["source"]["hash"],
            done["source"]["hash"],
        )

    def test_public_model_rejects_conflicting_legacy_status_projection(self) -> None:
        project_id = self._project("状态合同拒绝矛盾")
        chapter = self._start_and_save(project_id, "人物：林舟。剧情线：寻找灯塔。")
        payload = self._complete_deconstruction(project_id, chapter)
        payload["status"] = "rebuild_required"
        with self.assertRaises(ValidationError):
            DeconstructionResponse.model_validate(payload)

    def test_repeated_outbox_reconcile_is_idempotent(self) -> None:
        project_id = self._project("outbox幂等")
        chapter = self._start_and_save(project_id, "人物：顾遥。线索：旧信。")
        self.independent.deconstruction_service = None
        self._complete_direct(project_id, chapter)
        self.independent.deconstruction_service = self.deconstruction
        self.assertEqual(self.deconstruction.reconcile_outbox(project_id, self._account_id()), 1)
        self.assertEqual(self.deconstruction.reconcile_outbox(project_id, self._account_id()), 0)
        self.deconstruction.process_background_tasks()
        self.deconstruction.process_background_tasks()
        record = self.deconstruction.store.load(project_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(len(record.documents), 1)
        self.assertEqual(record.documents[0].status, "completed")

    def test_ack_failure_keeps_outbox_for_a_safe_idempotent_retry(self) -> None:
        project_id = self._project("确认失败可恢复")
        chapter = self._start_and_save(project_id, "人物：顾遥。线索：一封旧信。")
        self.independent.deconstruction_service = None
        self._complete_direct(project_id, chapter)
        self.independent.deconstruction_service = self.deconstruction

        with patch.object(self.independent, "ack_deconstruction_event", side_effect=OSError("ack unavailable")):
            self.assertEqual(self.deconstruction.reconcile_outbox(project_id, self._account_id()), 0)
        first = self.deconstruction.store.load(project_id)
        self.assertIsNotNone(first)
        assert first is not None
        self.assertEqual(len(first.documents), 1)
        self.assertEqual(first.documents[0].status, "queued")
        self.assertEqual(len(self.independent.store.load(project_id).deconstruction_outbox), 1)

        self.assertEqual(self.deconstruction.reconcile_outbox(project_id, self._account_id()), 1)
        self.deconstruction.process_background_tasks()
        second = self.deconstruction.store.load(project_id)
        self.assertIsNotNone(second)
        assert second is not None
        self.assertEqual(len(second.documents), 1)
        self.assertEqual(second.documents[0].status, "completed")
        self.assertEqual(self.independent.store.load(project_id).deconstruction_outbox, [])


if __name__ == "__main__":
    unittest.main()
