from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from app import deconstruction_routes, entry_routes, independent_routes
from app.core.account_store import AccountStore
from app.core.deconstruction_service import DeconstructionService
from app.core.deconstruction_store import DeconstructionStore
from app.core.entry_service import EntryService
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore
from app.core.ai_store import AIStore
from schemas.deconstruction import DeconstructionResponse


class Stage31DeconstructionApiTest(unittest.TestCase):
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

    @staticmethod
    def _encoded(text: str) -> str:
        return base64.b64encode(text.encode("utf-8")).decode("ascii")

    def _login(self, email: str = "拆解作者@example.com") -> str:
        response = self.client.post("/api/auth/email", json={"email": email})
        self.assertEqual(response.status_code, 200)
        return response.json()["account"]["account_id"]

    def _project(self, title: str = "雾港拆解") -> str:
        self._login()
        response = self.client.post(
            "/api/library/projects",
            json={"title": title, "mode": "independent", "brief": "一座靠潮汐记忆生活的城市。"},
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

    def _complete_and_process(self, project_id: str, chapter: dict) -> dict:
        completed = self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/complete",
            json={
                "content": chapter["content"],
                "expected_revision": chapter["server_revision"],
                "idempotency_key": f"stage31-{project_id}-{chapter['chapter_id']}",
            },
        )
        self.assertEqual(completed.status_code, 200)
        self.deconstruction.process_background_tasks()
        result = self.client.get(f"/api/independent/projects/{project_id}/deconstruction")
        self.assertEqual(result.status_code, 200)
        payload = result.json()
        DeconstructionResponse.model_validate(payload)
        return payload

    def test_import_confirm_queues_completed_deconstruction_with_real_evidence(self) -> None:
        project_id = self._project()
        source = (
            "导入说明\n"
            "# 第一章 雾起\n"
            "人物：林舟、顾遥\n"
            "剧情线：寻找旧港灯塔\n"
            "伏笔：门缝里的蓝纸\n"
            "海风从门缝里进来，林舟决定打开旧档案。\n\n"
            "# 第二章 回声\n"
            "林舟和顾遥在钟楼相遇，发现潮汐记录被人改过。"
        )
        preview = self.client.post(
            f"/api/independent/projects/{project_id}/imports/preview",
            json={"filename": "雾港.md", "content_base64": self._encoded(source)},
        )
        self.assertEqual(preview.status_code, 200)
        preview_id = preview.json()["preview"]["preview_id"]
        confirmed = self.client.post(
            f"/api/independent/projects/{project_id}/imports/{preview_id}/confirm"
        )
        self.assertEqual(confirmed.status_code, 200)

        queued = self.client.get(f"/api/independent/projects/{project_id}/deconstruction")
        self.assertEqual(queued.status_code, 200)
        self.assertIn(queued.json()["status"], {"queued", "running", "completed"})
        self.deconstruction.process_background_tasks()
        result = self.client.get(f"/api/independent/projects/{project_id}/deconstruction").json()
        DeconstructionResponse.model_validate(result)
        self.assertEqual(result["status"], "completed")
        document = result["document"]
        self.assertEqual(document["overview"]["chapter_count"], 2)
        self.assertEqual(len(document["chapter_breakdowns"]), 2)
        self.assertTrue(document["timeline"])
        self.assertTrue(all(0 <= node["normalized_start"] <= node["normalized_end"] <= 100 for node in document["timeline"]))
        self.assertTrue(document["evidence"])
        self.assertNotIn("account_id", document)
        self.assertNotIn("raw_text", result)

    def test_blank_empty_state_then_complete_chapter_generates_overview(self) -> None:
        project_id = self._project("空白拆解")
        started = self.client.post(
            f"/api/independent/projects/{project_id}/start",
            json={"source": "blank"},
        )
        self.assertEqual(started.status_code, 200)
        empty = self.client.get(f"/api/independent/projects/{project_id}/deconstruction")
        self.assertEqual(empty.status_code, 200)
        DeconstructionResponse.model_validate(empty.json())
        self.assertEqual(empty.json()["status"], "empty")
        self.assertIn("至少一章", empty.json()["empty_reason"])
        chapter = self._start_and_save(
            project_id,
            "人物：林舟。剧情线：寻找失踪的钟声。线索：旧信。林舟走进雾里。",
        )
        completed = self._complete_and_process(project_id, chapter)
        self.assertEqual(completed["status"], "completed")
        self.assertGreaterEqual(completed["document"]["overview"]["total_word_count"], 20)

    def test_deconstruction_retry_and_rebuild_required_keep_history(self) -> None:
        project_id = self._project("拆解失败重试")
        chapter = self._start_and_save(project_id, "[[deconstruction-fail]] 人物：林舟。")
        failed = self._complete_and_process(project_id, chapter)
        self.assertEqual(failed["status"], "failed_retryable")
        self.assertTrue(failed["actions"]["retry"])
        self.assertEqual(failed["document"]["overview"], None)

        failed_chapter = self.client.get(f"/api/independent/projects/{project_id}").json()["active_version"]["chapters"][0]
        fixed = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{failed_chapter['chapter_id']}/draft",
            json={
                "content": "人物：林舟。冲突：他必须在旧港关闭前找到失踪的钟声。",
                "expected_revision": failed_chapter["server_revision"],
            },
        )
        self.assertEqual(fixed.status_code, 200)
        ignored = self.client.post(
            f"/api/independent/projects/{project_id}/pending-changes/resolve",
            json={"decision": "ignore"},
        )
        self.assertEqual(ignored.status_code, 200)
        rebuild_required = self.client.get(f"/api/independent/projects/{project_id}/deconstruction").json()
        self.assertIn(rebuild_required["status"], {"stale", "rebuild_required"})
        self.assertTrue(rebuild_required["actions"]["rebuild"])
        queued = self.client.post(f"/api/independent/projects/{project_id}/deconstruction/retry")
        self.assertEqual(queued.status_code, 200)
        self.assertEqual(queued.json()["status"], "queued")
        self.deconstruction.process_background_tasks()
        done = self.client.get(f"/api/independent/projects/{project_id}/deconstruction").json()
        self.assertEqual(done["status"], "completed")
        self.assertGreaterEqual(len(done["history"]), 2)

    def test_idempotent_enqueue_and_run_do_not_duplicate_documents(self) -> None:
        project_id = self._project("拆解幂等")
        chapter = self._start_and_save(project_id, "人物：林舟。剧情线：寻找灯塔。")
        self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/complete",
            json={"content": chapter["content"], "expected_revision": chapter["server_revision"], "idempotency_key": "same"},
        )
        first = self.deconstruction.enqueue_for_project(project_id, self._account_id(), reason="重复触发")
        second = self.deconstruction.enqueue_for_project(project_id, self._account_id(), reason="重复触发")
        self.assertEqual(first.document_id, second.document_id)
        self.deconstruction.process_background_tasks()
        self.deconstruction.run_document(project_id, self._account_id(), first.document_id)
        persisted = self.deconstruction.store.load(project_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(len(persisted.documents), 1)
        self.assertEqual(persisted.documents[0].status, "completed")

    def _account_id(self) -> str:
        return self.client.get("/api/auth/session").json()["account"]["account_id"]

    def test_evidence_endpoint_is_chapter_backlink_and_accounts_are_isolated(self) -> None:
        project_id = self._project("证据回链")
        chapter = self._start_and_save(project_id, "人物：林舟。剧情线：寻找灯塔。林舟发现一封旧信。")
        result = self._complete_and_process(project_id, chapter)
        evidence_id = result["document"]["evidence"][0]["evidence_id"]
        evidence = self.client.get(
            f"/api/independent/projects/{project_id}/deconstruction/evidence/{evidence_id}"
        )
        self.assertEqual(evidence.status_code, 200)
        self.assertEqual(evidence.json()["chapter"]["chapter_number"], 1)
        self.assertTrue(evidence.json()["evidence"]["target_path"].startswith(f"/independent/{project_id}"))
        self.assertLessEqual(len(evidence.json()["evidence"]["excerpt"]), 180)

        other = TestClient(main.app)
        other.post("/api/auth/email", json={"email": "另一个作者@example.com"})
        hidden = other.get(f"/api/independent/projects/{project_id}/deconstruction")
        self.assertEqual(hidden.status_code, 404)
        hidden_evidence = other.get(
            f"/api/independent/projects/{project_id}/deconstruction/evidence/{evidence_id}"
        )
        self.assertEqual(hidden_evidence.status_code, 404)

    def test_route_requires_session_and_read_recovers_existing_mature_sidecar(self) -> None:
        project_id = self._project("旧数据恢复")
        account_id = self._account_id()
        original_deconstruction = self.independent.deconstruction_service
        self.independent.deconstruction_service = None
        chapter = self._start_and_save(project_id, "人物：林舟。冲突：旧港即将关闭。")
        completed = self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/complete",
            json={"content": chapter["content"], "expected_revision": chapter["server_revision"], "idempotency_key": "old-data"},
        )
        self.assertEqual(completed.status_code, 200)
        self.independent.deconstruction_service = original_deconstruction
        recovered = self.client.get(f"/api/independent/projects/{project_id}/deconstruction")
        self.assertEqual(recovered.status_code, 200)
        self.assertIn(recovered.json()["status"], {"queued", "running", "completed"})
        self.deconstruction.process_background_tasks()
        self.assertEqual(
            self.client.get(f"/api/independent/projects/{project_id}/deconstruction").json()["status"],
            "completed",
        )

        anonymous = TestClient(main.app)
        denied = anonymous.get(f"/api/independent/projects/{project_id}/deconstruction")
        self.assertEqual(denied.status_code, 401)


if __name__ == "__main__":
    unittest.main()
