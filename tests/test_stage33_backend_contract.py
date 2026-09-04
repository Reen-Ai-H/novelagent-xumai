from __future__ import annotations

import base64
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

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


class Stage33BackendContractTest(unittest.TestCase):
    """阶段 33 后端黑盒合同：只通过真实 API 和隔离持久化侧车验收。"""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="xumai33-backend-")
        root = Path(self.temporary.name)
        accounts = AccountStore(root / "accounts.json")
        projects = JsonProjectStore(root / "projects")
        independent = IndependentWorkspaceService(
            store=IndependentStore(root / "independent"),
            projects=projects,
        )
        deconstruction = DeconstructionService(
            independent=independent,
            store=DeconstructionStore(root / "deconstruction"),
        )
        independent.deconstruction_service = deconstruction
        entry = EntryService(
            accounts=accounts,
            projects=projects,
            independent=independent.store,
            ai=AIStore(root / "ai"),
        )
        self.independent = independent
        self.deconstruction = deconstruction
        self.patchers = [
            patch.object(entry_routes, "account_store", accounts),
            patch.object(entry_routes, "entry_service", entry),
            patch.object(independent_routes, "independent_service", independent),
            patch.object(deconstruction_routes, "deconstruction_service", deconstruction),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self.client.close()
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temporary.cleanup()

    @staticmethod
    def _encoded(text: str) -> str:
        return base64.b64encode(text.encode("utf-8")).decode("ascii")

    def _login(self, email: str = "stage33-owner@example.test") -> str:
        response = self.client.post("/api/auth/email", json={"email": email})
        self.assertEqual(response.status_code, 200)
        return response.json()["account"]["account_id"]

    def _project(self, title: str = "阶段33后端合同", *, mode: str = "independent") -> str:
        self._login()
        response = self.client.post(
            "/api/library/projects",
            json={"title": title, "mode": mode},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["project"]["project_id"]

    def _start(self, project_id: str) -> dict:
        response = self.client.post(
            f"/api/independent/projects/{project_id}/start",
            json={"source": "blank"},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _save(self, project_id: str, chapter: dict, content: str, *, title: str | None = None) -> dict:
        response = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/draft",
            json={
                "content": content,
                "title": title,
                "expected_revision": chapter["server_revision"],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["save_state"], "saved")
        return response.json()["chapter"]

    def _complete(self, project_id: str, chapter: dict, *, key: str) -> dict:
        response = self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/complete",
            json={
                "content": chapter["content"],
                "expected_revision": chapter["server_revision"],
                "idempotency_key": key,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.independent.recover_pending_tasks(
            project_id,
            self.client.get("/api/auth/session").json()["account"]["account_id"],
        )
        return response.json()["task"]

    def _process_deconstruction(self, project_id: str) -> dict:
        self.deconstruction.process_background_tasks()
        response = self.client.get(f"/api/independent/projects/{project_id}/deconstruction")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _two_chapter_version(self, project_id: str) -> tuple[dict, dict, str]:
        started = self._start(project_id)
        first = self._save(
            project_id,
            started["active_version"]["chapters"][0],
            "人物：林舟。剧情线：寻找灯塔。伏笔：门缝里的蓝纸。林舟在旧港打开档案。",
        )
        self._complete(project_id, first, key=f"stage33-first-{project_id}")

        added = self.client.post(f"/api/independent/projects/{project_id}/chapters", params={"title": "第二章 回声"})
        self.assertEqual(added.status_code, 200, added.text)
        second = self._save(
            project_id,
            added.json()["chapter"],
            "人物：顾遥。剧情线：寻找灯塔。线索：钟楼的旧信。顾遥带林舟走向河岸。",
        )
        self._complete(project_id, second, key=f"stage33-second-{project_id}")
        workspace = self.client.get(f"/api/independent/projects/{project_id}").json()
        return workspace["active_version"]["chapters"][0], workspace["active_version"]["chapters"][1], workspace["active_version_id"]

    def test_start_is_idempotent_and_new_chapter_return_preserves_existing_body(self) -> None:
        project_id = self._project()
        first_start = self._start(project_id)
        first = self._save(
            project_id,
            first_start["active_version"]["chapters"][0],
            "第一章作者正文，保存后仍应逐字保留。",
        )

        repeated_start = self._start(project_id)
        self.assertEqual(repeated_start["active_version_id"], first_start["active_version_id"])
        self.assertEqual(len(repeated_start["active_version"]["chapters"]), 1)
        self.assertEqual(repeated_start["active_version"]["chapters"][0]["content"], first["content"])

        added = self.client.post(
            f"/api/independent/projects/{project_id}/chapters",
            params={"title": "第二章 回声"},
        )
        self.assertEqual(added.status_code, 200, added.text)
        second = added.json()["chapter"]
        self.assertEqual(second["chapter_number"], 2)
        self.assertEqual(second["title"], "第二章 回声")
        self.assertNotEqual(second["chapter_id"], first["chapter_id"])
        current = self.client.get(f"/api/independent/projects/{project_id}").json()
        self.assertEqual(
            [chapter["content"] for chapter in current["active_version"]["chapters"]],
            [first["content"], ""],
        )

    def test_save_revision_cas_returns_server_body_and_does_not_accept_stale_write(self) -> None:
        project_id = self._project("revision CAS")
        chapter = self._start(project_id)["active_version"]["chapters"][0]
        saved = self._save(project_id, chapter, "服务端保存的正文，另一端不能静默覆盖。")
        conflict = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/draft",
            json={
                "content": "过期客户端试图覆盖的正文。",
                "expected_revision": chapter["server_revision"],
            },
        )
        self.assertEqual(conflict.status_code, 409)
        detail = conflict.json()["detail"]
        self.assertEqual(detail["code"], "save_conflict")
        self.assertEqual(detail["data"]["server_revision"], saved["server_revision"])
        self.assertEqual(detail["data"]["chapter"]["content"], saved["content"])
        persisted = self.client.get(f"/api/independent/projects/{project_id}").json()
        self.assertEqual(persisted["active_version"]["chapters"][0]["content"], saved["content"])

    def test_complete_is_idempotent_and_completed_body_cannot_create_second_task(self) -> None:
        project_id = self._project("完成幂等")
        chapter = self._start(project_id)["active_version"]["chapters"][0]
        chapter = self._save(project_id, chapter, "人物：林舟。剧情线：寻找灯塔。林舟完成第一章。")
        first_task = self._complete(project_id, chapter, key="stage33-complete-once")
        duplicate = self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/complete",
            json={
                "content": chapter["content"],
                "expected_revision": chapter["server_revision"],
                "idempotency_key": "stage33-complete-repeated",
            },
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertEqual(duplicate.json()["task"]["task_id"], first_task["task_id"])
        workspace = self.client.get(f"/api/independent/projects/{project_id}").json()
        chapter_tasks = [
            task
            for task in workspace["tasks"]
            if task["kind"] == "chapter_analysis" and task["chapter_id"] == chapter["chapter_id"]
        ]
        self.assertEqual(len(chapter_tasks), 1)
        self.assertEqual(chapter_tasks[0]["status"], "completed")
        self.assertEqual(workspace["active_version"]["chapters"][0]["formal_content"], chapter["content"])

    def test_old_chapter_ignore_keeps_archive_but_marks_deconstruction_stale_then_rebuild_publishes_new_source(self) -> None:
        project_id = self._project("旧章决策")
        chapter = self._start(project_id)["active_version"]["chapters"][0]
        chapter = self._save(
            project_id,
            chapter,
            "人物：林舟。剧情线：寻找灯塔。伏笔：蓝纸。第一版正文。",
        )
        self._complete(project_id, chapter, key="stage33-old-chapter")
        before = self.client.get(f"/api/independent/projects/{project_id}").json()
        old_version_id = before["active_version_id"]
        old_archive = deepcopy(before["archive"])
        old_deconstruction = self._process_deconstruction(project_id)
        self.assertEqual(old_deconstruction["effective_status"], "completed")

        edited = self._save(
            project_id,
            before["active_version"]["chapters"][0],
            "人物：林舟。剧情线：寻找灯塔。伏笔：蓝纸。第一版正文。作者补写轻微措辞。",
        )
        pending = self.client.get(f"/api/independent/projects/{project_id}").json()
        self.assertEqual(pending["active_version_id"], old_version_id)
        self.assertIsNotNone(pending["pending_changes"])
        self.assertEqual(pending["active_version"]["chapters"][0]["formal_content"], chapter["content"])
        blocked = self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{edited['chapter_id']}/complete",
            json={"content": edited["content"], "expected_revision": edited["server_revision"]},
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["detail"]["code"], "pending_changes_confirmation_required")

        ignored = self.client.post(
            f"/api/independent/projects/{project_id}/pending-changes/resolve",
            json={"decision": "ignore"},
        )
        self.assertEqual(ignored.status_code, 200, ignored.text)
        ignored_workspace = ignored.json()["workspace"]
        self.assertEqual(ignored_workspace["active_version_id"], old_version_id)
        self.assertIsNone(ignored_workspace["pending_changes"])
        self.assertEqual(ignored_workspace["archive"], old_archive)
        self.assertEqual(ignored_workspace["active_version"]["chapters"][0]["formal_content"], edited["content"])
        stale = self.client.get(f"/api/independent/projects/{project_id}/deconstruction")
        self.assertEqual(stale.status_code, 200)
        self.assertIn(stale.json()["effective_status"], {"stale", "rebuild_required"})
        self.assertIsNone(stale.json()["result"])

        historical_baseline = self.client.get(
            f"/api/independent/projects/{project_id}/versions/{old_version_id}/preview"
        ).json()["version"]
        current = ignored_workspace["active_version"]["chapters"][0]
        rebuilt_draft = self._save(
            project_id,
            current,
            "人物：林舟。剧情线：寻找灯塔。伏笔：蓝纸。全文重建后的正式正文。",
        )
        rebuilt = self.client.post(
            f"/api/independent/projects/{project_id}/pending-changes/resolve",
            json={"decision": "rebuild"},
        )
        self.assertEqual(rebuilt.status_code, 200, rebuilt.text)
        after_rebuild = self.client.get(f"/api/independent/projects/{project_id}").json()
        new_version_id = after_rebuild["active_version_id"]
        self.assertNotEqual(new_version_id, old_version_id)
        self.assertEqual(sum(item["status"] == "active" for item in after_rebuild["versions"]), 1)
        historical = next(item for item in after_rebuild["versions"] if item["version_id"] == old_version_id)
        historical_preview = self.client.get(
            f"/api/independent/projects/{project_id}/versions/{old_version_id}/preview"
        ).json()["version"]
        for field in (
            "content",
            "title",
            "formal_title",
            "formal_content",
            "word_count",
            "formal_word_count",
            "last_completed_hash",
        ):
            self.assertEqual(historical_preview["chapters"][0][field], historical_baseline["chapters"][0][field])
        self.assertEqual(historical_preview["archive"], historical_baseline["archive"])
        self.assertEqual(historical["status"], "recoverable")
        new_chapter = after_rebuild["active_version"]["chapters"][0]
        self.assertEqual(new_chapter["content"], rebuilt_draft["content"])
        self.assertEqual(new_chapter["formal_content"], rebuilt_draft["content"])
        self.assertEqual(after_rebuild["active_version"]["archive"]["latest_chapter_number"], 1)
        rebuilt_deconstruction = self._process_deconstruction(project_id)
        self.assertEqual(rebuilt_deconstruction["effective_status"], "completed")
        self.assertEqual(rebuilt_deconstruction["source"]["version_id"], new_version_id)
        self.assertIsNotNone(rebuilt_deconstruction["result"])

    def test_historical_version_preview_returns_every_chapter_read_only(self) -> None:
        project_id = self._project("逐章版本预览")
        first, second, old_version_id = self._two_chapter_version(project_id)
        edited_first = self._save(
            project_id,
            first,
            first["content"] + " 作者对第一章留下新的版本边界。",
        )
        rebuilt = self.client.post(
            f"/api/independent/projects/{project_id}/pending-changes/resolve",
            json={"decision": "rebuild"},
        )
        self.assertEqual(rebuilt.status_code, 200, rebuilt.text)

        preview = self.client.get(
            f"/api/independent/projects/{project_id}/versions/{old_version_id}/preview"
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        payload = preview.json()
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["version"]["version_id"], old_version_id)
        self.assertEqual(len(payload["version"]["chapters"]), 2)
        self.assertEqual(payload["version"]["chapters"][0]["content"], first["content"])
        self.assertEqual(payload["version"]["chapters"][1]["content"], second["content"])
        self.assertGreater(len(payload["version"]["chapters"][1]["content"]), 20)
        self.assertEqual(payload["archive"]["latest_chapter_number"], 2)
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn('"account_id":', serialized)
        self.assertNotIn('"raw_text":', serialized)
        self.assertNotEqual(edited_first["content"], payload["version"]["chapters"][0]["content"])

    def test_restore_only_appends_current_version_and_keeps_selected_history_byte_for_byte(self) -> None:
        project_id = self._project("历史恢复")
        first, second, historical_id = self._two_chapter_version(project_id)
        edited = self._save(
            project_id,
            first,
            first["content"] + " 当前稿本的作者修改。",
        )
        rebuilt = self.client.post(
            f"/api/independent/projects/{project_id}/pending-changes/resolve",
            json={"decision": "rebuild"},
        )
        self.assertEqual(rebuilt.status_code, 200, rebuilt.text)
        before_restore = self.client.get(f"/api/independent/projects/{project_id}").json()
        selected_before = deepcopy(
            self.client.get(
                f"/api/independent/projects/{project_id}/versions/{historical_id}/preview"
            ).json()["version"]
        )
        previous_active_id = before_restore["active_version_id"]
        version_count = len(before_restore["versions"])

        restored = self.client.post(
            f"/api/independent/projects/{project_id}/versions/{historical_id}/restore"
        )
        self.assertEqual(restored.status_code, 200, restored.text)
        after = self.client.get(f"/api/independent/projects/{project_id}").json()
        self.assertEqual(len(after["versions"]), version_count + 1)
        self.assertNotIn(after["active_version_id"], {historical_id, previous_active_id})
        self.assertEqual(sum(item["status"] == "active" for item in after["versions"]), 1)
        selected_after = self.client.get(
            f"/api/independent/projects/{project_id}/versions/{historical_id}/preview"
        ).json()["version"]
        self.assertEqual(selected_after["chapters"], selected_before["chapters"])
        self.assertEqual(selected_after["archive"], selected_before["archive"])
        restored_version = after["active_version"]
        self.assertEqual(restored_version["source_version_id"], historical_id)
        self.assertEqual(
            [chapter["content"] for chapter in restored_version["chapters"]],
            [first["content"], second["content"]],
        )
        self.assertTrue(
            all(
                restored_chapter["chapter_id"] != historical_chapter["chapter_id"]
                for restored_chapter, historical_chapter in zip(
                    restored_version["chapters"], selected_before["chapters"]
                )
            )
        )
        duplicate_restore = self.client.post(
            f"/api/independent/projects/{project_id}/versions/{historical_id}/restore"
        )
        self.assertEqual(duplicate_restore.status_code, 200, duplicate_restore.text)
        duplicate_workspace = self.client.get(f"/api/independent/projects/{project_id}").json()
        self.assertEqual(len(duplicate_workspace["versions"]), version_count + 1)
        self.assertEqual(duplicate_workspace["active_version_id"], after["active_version_id"])
        self.assertEqual(duplicate_restore.json()["version"]["version_id"], after["active_version_id"])
        changed_current = self._save(
            project_id,
            duplicate_workspace["active_version"]["chapters"][0],
            duplicate_workspace["active_version"]["chapters"][0]["content"] + " 作者后来又有真实修改。",
        )
        ignored_current = self.client.post(
            f"/api/independent/projects/{project_id}/pending-changes/resolve",
            json={"decision": "ignore"},
        )
        self.assertEqual(ignored_current.status_code, 200, ignored_current.text)
        repeated_after_change = self.client.post(
            f"/api/independent/projects/{project_id}/versions/{historical_id}/restore"
        )
        self.assertEqual(repeated_after_change.status_code, 200, repeated_after_change.text)
        after_real_change = self.client.get(f"/api/independent/projects/{project_id}").json()
        self.assertEqual(len(after_real_change["versions"]), version_count + 2)
        self.assertNotEqual(after_real_change["active_version_id"], after["active_version_id"])
        self.assertEqual(after_real_change["active_version"]["source_version_id"], historical_id)
        self.assertEqual(after_real_change["active_version"]["chapters"][0]["content"], first["content"])
        self.assertNotEqual(changed_current["content"], after_real_change["active_version"]["chapters"][0]["content"])
        current = self.client.get(f"/api/independent/projects/{project_id}").json()
        self.assertEqual(current["active_version_id"], after_real_change["active_version_id"])
        self.assertEqual(current["active_version"]["chapters"][0]["formal_content"], first["content"])
        self.assertNotEqual(edited["content"], current["active_version"]["chapters"][0]["content"])
        deconstruction = self._process_deconstruction(project_id)
        self.assertEqual(deconstruction["effective_status"], "completed")
        self.assertEqual(deconstruction["source"]["version_id"], after_real_change["active_version_id"])

    def test_restore_rejects_pending_old_chapter_changes_without_dropping_them(self) -> None:
        project_id = self._project("恢复待确认门禁")
        first, _, historical_id = self._two_chapter_version(project_id)
        edited = self._save(
            project_id,
            first,
            first["content"] + " 当前稿本已确认后的修改。",
        )
        rebuilt = self.client.post(
            f"/api/independent/projects/{project_id}/pending-changes/resolve",
            json={"decision": "rebuild"},
        )
        self.assertEqual(rebuilt.status_code, 200, rebuilt.text)
        before_restore = self.client.get(f"/api/independent/projects/{project_id}").json()
        active = before_restore["active_version"]["chapters"][0]
        pending_edit = self._save(
            project_id,
            active,
            active["content"] + " 这段修改尚未确认。",
        )
        before_count = len(self.client.get(f"/api/independent/projects/{project_id}").json()["versions"])

        blocked = self.client.post(
            f"/api/independent/projects/{project_id}/versions/{historical_id}/restore"
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["detail"]["code"], "pending_changes_confirmation_required")
        after_block = self.client.get(f"/api/independent/projects/{project_id}").json()
        self.assertEqual(len(after_block["versions"]), before_count)
        self.assertEqual(after_block["active_version_id"], before_restore["active_version_id"])
        self.assertEqual(after_block["active_version"]["chapters"][0]["content"], pending_edit["content"])
        self.assertIsNotNone(after_block["pending_changes"])

    def test_archive_snapshots_and_deconstruction_result_share_current_version_source(self) -> None:
        project_id = self._project("档案拆解一致")
        self._two_chapter_version(project_id)
        workspace = self.client.get(f"/api/independent/projects/{project_id}").json()
        archive = self.client.get(f"/api/independent/projects/{project_id}/archive")
        self.assertEqual(archive.status_code, 200, archive.text)
        archive_payload = archive.json()
        self.assertEqual(archive_payload["active_version_id"], workspace["active_version_id"])
        self.assertEqual(archive_payload["archive"], workspace["archive"])
        self.assertEqual(
            [snapshot["chapter_number"] for snapshot in archive_payload["available_snapshots"]],
            [1, 2],
        )
        historical_archive = self.client.get(
            f"/api/independent/projects/{project_id}/archive?chapter_number=1"
        )
        self.assertEqual(historical_archive.status_code, 200, historical_archive.text)
        self.assertTrue(historical_archive.json()["read_only"])
        self.assertEqual(historical_archive.json()["selected_chapter_number"], 1)
        selected_archive = historical_archive.json()["archive"]
        snapshot = archive_payload["available_snapshots"][0]
        self.assertEqual(selected_archive["latest_chapter_number"], snapshot["chapter_number"])
        self.assertEqual(selected_archive["characters"], snapshot["characters"])
        self.assertEqual(selected_archive["storylines"], snapshot["storylines"])
        self.assertEqual(selected_archive["foreshadowing"], snapshot["foreshadowing"])
        self.assertEqual(selected_archive["questions"], snapshot["questions"])
        self.assertEqual(selected_archive["snapshots"], [snapshot])

        deconstruction = self._process_deconstruction(project_id)
        self.assertEqual(deconstruction["effective_status"], "completed")
        self.assertEqual(deconstruction["source"]["version_id"], workspace["active_version_id"])
        self.assertTrue(deconstruction["source"]["match"])
        self.assertIsNotNone(deconstruction["result"])
        for evidence in deconstruction["result"]["evidence"]:
            self.assertEqual(evidence["source_version_id"], deconstruction["source"]["version_id"])
            self.assertEqual(evidence["source_revision"], deconstruction["source"]["revision"])
            self.assertEqual(evidence["source_hash"], deconstruction["source"]["hash"])

    def test_auth_owner_mode_and_resource_boundaries_return_safe_statuses(self) -> None:
        project_id = self._project("权限边界")
        anonymous = TestClient(main.app)
        try:
            response = anonymous.get(f"/api/independent/projects/{project_id}")
            self.assertEqual(response.status_code, 401)
        finally:
            anonymous.close()

        other = TestClient(main.app)
        try:
            self.assertEqual(
                other.post("/api/auth/email", json={"email": "stage33-other@example.test"}).status_code,
                200,
            )
            self.assertEqual(other.get(f"/api/independent/projects/{project_id}").status_code, 404)
            self.assertEqual(
                other.post(f"/api/independent/projects/{project_id}/start", json={"source": "blank"}).status_code,
                404,
            )
        finally:
            other.close()

        ai_project = self._project("模式门禁", mode="ai_assisted")
        mode_response = self.client.get(f"/api/independent/projects/{ai_project}/deconstruction")
        self.assertEqual(mode_response.status_code, 409)
        self.assertEqual(mode_response.json()["detail"]["code"], "mode_mismatch")

        started = self._start(project_id)
        chapter_id = started["active_version"]["chapters"][0]["chapter_id"]
        self.assertEqual(
            self.client.put(
                f"/api/independent/projects/{project_id}/chapters/missing/draft",
                json={"content": "不存在", "expected_revision": 0},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/api/independent/projects/{project_id}/tasks/missing").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/api/independent/projects/{project_id}/versions/missing/preview").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/api/independent/projects/{project_id}/archive?chapter_number=99").status_code,
            404,
        )
        self.assertNotEqual(chapter_id, "missing")
        self.assertEqual(
            self.client.get(f"/api/independent/projects/{project_id}/does-not-exist").status_code,
            404,
        )

    def test_public_workspace_and_import_preview_do_not_expose_account_or_raw_import_fields(self) -> None:
        project_id = self._project("公开响应边界")
        preview = self.client.post(
            f"/api/independent/projects/{project_id}/imports/preview",
            json={
                "filename": "正文.md",
                "content_base64": self._encoded("# 第一章\n作者正文不能通过 raw_text 旁路泄露。"),
            },
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        preview_payload = preview.json()
        self.assertNotIn("raw_text", preview_payload["preview"])
        self.assertNotIn("account_id", preview_payload["preview"])
        workspace = self.client.get(f"/api/independent/projects/{project_id}").json()
        serialized = json.dumps(workspace, ensure_ascii=False)
        self.assertNotIn('"account_id":', serialized)
        self.assertNotIn('"raw_text":', serialized)


if __name__ == "__main__":
    unittest.main()
