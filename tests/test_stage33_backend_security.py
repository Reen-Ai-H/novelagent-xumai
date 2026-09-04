"""阶段 33 后端黑盒合同：正文、版本、派生结果与账户边界。

这些用例只通过 HTTP 观察作者可见的合同；服务对象仅用于把真实实现接到
隔离临时目录，并用真实确定性 worker 推进后台任务。被测服务与分析引擎不做
mock，也不读取真实模型或项目数据。
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
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


class Stage33BackendSecurityTest(unittest.TestCase):
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

    def _login(self, email: str = "stage33@example.test") -> str:
        response = self.client.post("/api/auth/email", json={"email": email})
        self.assertEqual(response.status_code, 200)
        return response.json()["account"]["account_id"]

    def _project(self, title: str = "阶段 33 黑盒作品") -> str:
        self._login()
        response = self.client.post(
            "/api/library/projects",
            json={"title": title, "mode": "independent"},
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

    def _save(self, project_id: str, chapter: dict, content: str, title: str | None = None) -> dict:
        payload = {
            "content": content,
            "expected_revision": chapter["server_revision"],
        }
        if title is not None:
            payload["title"] = title
        response = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/draft",
            json=payload,
        )
        self.assertEqual(response.status_code, 200)
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
        self.assertEqual(response.status_code, 200)
        task_id = response.json()["task"]["task_id"]
        observed = self.client.get(f"/api/independent/projects/{project_id}/tasks/{task_id}")
        self.assertEqual(observed.status_code, 200)
        self.assertEqual(observed.json()["task"]["status"], "completed")
        return observed.json()["task"]

    def _two_chapter_story(self) -> tuple[str, dict, list[str]]:
        project_id = self._project("阶段 33 双章版本")
        started = self._start(project_id)
        first_content = "人物：林舟。剧情线：寻找灯塔。林舟在雾里打开旧门。"
        first = self._save(project_id, started["active_version"]["chapters"][0], first_content, "雾起")
        self._complete(project_id, first, key="stage33-story-1")

        added = self.client.post(
            f"/api/independent/projects/{project_id}/chapters",
            params={"title": "回声"},
        )
        self.assertEqual(added.status_code, 200)
        second_content = "人物：顾遥。剧情线：寻找灯塔。顾遥在钟楼留下新线索。"
        second = self._save(project_id, added.json()["chapter"], second_content)
        self._complete(project_id, second, key="stage33-story-2")
        self.deconstruction.process_background_tasks()
        workspace = self.client.get(f"/api/independent/projects/{project_id}")
        self.assertEqual(workspace.status_code, 200)
        return project_id, workspace.json(), [first_content, second_content]

    def test_new_chapter_returns_unique_document_without_mutating_existing_body(self) -> None:
        project_id = self._project()
        started = self._start(project_id)
        first = self._save(
            project_id,
            started["active_version"]["chapters"][0],
            "作者已经写好的第一章正文。",
            "雾起",
        )
        self._complete(project_id, first, key="stage33-new-chapter-base")

        second_response = self.client.post(
            f"/api/independent/projects/{project_id}/chapters",
            params={"title": "第二章 回声"},
        )
        third_response = self.client.post(f"/api/independent/projects/{project_id}/chapters")
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(third_response.status_code, 200)
        second = second_response.json()["chapter"]
        third = third_response.json()["chapter"]
        self.assertNotEqual(second["chapter_id"], third["chapter_id"])
        self.assertEqual((second["chapter_number"], third["chapter_number"]), (2, 3))
        self.assertEqual(second["title"], "第二章 回声")
        self.assertEqual(second["content"], "")
        self.assertEqual(third["content"], "")

        workspace = self.client.get(f"/api/independent/projects/{project_id}").json()
        chapters = workspace["active_version"]["chapters"]
        self.assertEqual(chapters[0]["content"], "作者已经写好的第一章正文。")
        self.assertEqual(chapters[0]["formal_content"], "作者已经写好的第一章正文。")
        self.assertEqual([chapter["chapter_number"] for chapter in chapters], [1, 2, 3])

    def test_save_uses_revision_cas_and_stale_writer_cannot_overwrite_body_or_title(self) -> None:
        project_id = self._project()
        started = self._start(project_id)
        chapter = started["active_version"]["chapters"][0]
        saved = self._save(project_id, chapter, "第一端保存的正文。", "第一端标题")

        stale = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/draft",
            json={
                "content": "第二端不应覆盖的正文。",
                "title": "第二端不应覆盖的标题",
                "expected_revision": chapter["server_revision"],
            },
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["detail"]["code"], "save_conflict")
        self.assertEqual(stale.json()["detail"]["data"]["server_revision"], saved["server_revision"])
        self.assertEqual(stale.json()["detail"]["data"]["chapter"]["content"], saved["content"])

        current = self.client.get(f"/api/independent/projects/{project_id}").json()
        persisted = current["active_version"]["chapters"][0]
        self.assertEqual(persisted["content"], "第一端保存的正文。")
        self.assertEqual(persisted["title"], "第一端标题")
        self.assertEqual(persisted["server_revision"], saved["server_revision"])

    def test_complete_repeat_returns_same_task_without_duplicate_snapshot_or_notification(self) -> None:
        project_id = self._project()
        started = self._start(project_id)
        content = "人物：林舟。剧情线：寻找灯塔。林舟决定沿着潮声前进。"
        saved = self._save(project_id, started["active_version"]["chapters"][0], content)
        payload = {
            "content": saved["content"],
            "expected_revision": saved["server_revision"],
            "idempotency_key": "stage33-complete-once",
        }

        first = self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{saved['chapter_id']}/complete",
            json=payload,
        )
        self.assertEqual(first.status_code, 200)
        task_id = first.json()["task"]["task_id"]
        completed = self.client.get(f"/api/independent/projects/{project_id}/tasks/{task_id}")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["task"]["status"], "completed")

        duplicate = self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{saved['chapter_id']}/complete",
            json=payload,
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json()["task"]["task_id"], task_id)

        workspace = self.client.get(f"/api/independent/projects/{project_id}").json()
        self.assertEqual([task["task_id"] for task in workspace["tasks"]], [task_id])
        self.assertEqual(
            sum(item["kind"] == "analysis_completed" for item in workspace["notifications"]),
            1,
        )
        self.assertEqual(len(workspace["archive"]["snapshots"]), 1)
        self.assertEqual(workspace["active_version"]["chapters"][0]["status"], "ready")

    def test_old_chapter_ignore_and_rebuild_keep_both_derivations_bound_to_the_right_source(self) -> None:
        project_id, before, contents = self._two_chapter_story()
        original_version_id = before["active_version_id"]
        before_archive = deepcopy(before["archive"])
        before_deconstruction = self.client.get(
            f"/api/independent/projects/{project_id}/deconstruction"
        ).json()
        self.assertEqual(before_deconstruction["effective_status"], "completed")

        first = before["active_version"]["chapters"][0]
        edited = self._save(
            project_id,
            first,
            "人物：林舟。剧情线：寻找灯塔。作者只调整了第一章措辞。",
            "雾起·修订",
        )
        blocked = self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{edited['chapter_id']}/complete",
            json={
                "content": edited["content"],
                "expected_revision": edited["server_revision"],
                "idempotency_key": "stage33-old-chapter-blocked",
            },
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["detail"]["code"], "pending_changes_confirmation_required")
        self.assertEqual(
            self.client.get(f"/api/independent/projects/{project_id}/archive").json()["archive"],
            before_archive,
        )

        ignored = self.client.post(
            f"/api/independent/projects/{project_id}/pending-changes/resolve",
            json={"decision": "ignore"},
        )
        self.assertEqual(ignored.status_code, 200)
        ignored_workspace = ignored.json()["workspace"]
        self.assertEqual(ignored_workspace["active_version_id"], original_version_id)
        self.assertIsNone(ignored_workspace["pending_changes"])
        self.assertEqual(
            self.client.get(f"/api/independent/projects/{project_id}/archive").json()["archive"],
            before_archive,
        )
        ignored_deconstruction = self.client.get(
            f"/api/independent/projects/{project_id}/deconstruction"
        ).json()
        self.assertEqual(ignored_deconstruction["effective_status"], "stale")
        self.assertFalse(ignored_deconstruction["source_match"])
        self.assertIsNone(ignored_deconstruction["result"])

        current = ignored_workspace["active_version"]["chapters"][0]
        rebuilt_draft = self._save(
            project_id,
            current,
            "人物：林舟。剧情线：寻找灯塔。全文重建后加入一枚新钥匙。",
            "雾起·全文重建",
        )
        rebuilt = self.client.post(
            f"/api/independent/projects/{project_id}/pending-changes/resolve",
            json={"decision": "rebuild"},
        )
        self.assertEqual(rebuilt.status_code, 200)
        rebuilt_workspace = rebuilt.json()["workspace"]
        self.assertNotEqual(rebuilt_workspace["active_version_id"], original_version_id)
        self.assertEqual(
            sum(item["status"] == "active" for item in rebuilt_workspace["versions"]),
            1,
        )
        self.assertEqual(rebuilt_workspace["active_version"]["chapters"][0]["content"], rebuilt_draft["content"])
        self.assertEqual(rebuilt_workspace["active_version"]["chapters"][0]["formal_content"], rebuilt_draft["content"])

        self.deconstruction.process_background_tasks()
        active = rebuilt_workspace["active_version"]
        deconstruction = self.client.get(
            f"/api/independent/projects/{project_id}/deconstruction"
        ).json()
        self.assertEqual(deconstruction["effective_status"], "completed")
        self.assertTrue(deconstruction["source_match"])
        self.assertEqual(deconstruction["source"]["version_id"], active["version_id"])
        formal_chapters = [chapter for chapter in active["chapters"] if chapter["formal_content"].strip()]
        self.assertEqual(deconstruction["source"]["chapter_count"], len(active["chapters"]))
        self.assertEqual(
            deconstruction["source"]["revision"],
            max(chapter["server_revision"] for chapter in formal_chapters),
        )
        self.assertEqual(
            deconstruction["source"]["total_word_count"],
            sum(chapter["word_count"] for chapter in active["chapters"]),
        )
        self.assertEqual(
            deconstruction["result"]["source_version_id"],
            deconstruction["source"]["version_id"],
        )
        self.assertEqual(
            deconstruction["result"]["source_revision"],
            deconstruction["source"]["revision"],
        )
        self.assertEqual(
            deconstruction["result"]["source_hash"],
            deconstruction["source"]["hash"],
        )
        archive = self.client.get(f"/api/independent/projects/{project_id}/archive").json()
        self.assertEqual(archive["active_version_id"], active["version_id"])
        self.assertEqual(archive["archive"]["latest_chapter_number"], 2)
        self.assertTrue(any(item["title"] == "寻找灯塔" for item in archive["archive"]["storylines"]))

    def test_version_preview_is_complete_and_repeated_restore_does_not_create_extra_version(self) -> None:
        project_id, before, contents = self._two_chapter_story()
        original_version_id = before["active_version_id"]
        first_chapter = before["active_version"]["chapters"][0]
        self._save(
            project_id,
            first_chapter,
            "人物：林舟。剧情线：寻找灯塔。修订后准备建立历史稿本。",
            "修订后的雾起",
        )
        rebuilt = self.client.post(
            f"/api/independent/projects/{project_id}/pending-changes/resolve",
            json={"decision": "rebuild"},
        )
        self.assertEqual(rebuilt.status_code, 200)
        after_rebuild = rebuilt.json()["workspace"]

        preview = self.client.get(
            f"/api/independent/projects/{project_id}/versions/{original_version_id}/preview"
        )
        self.assertEqual(preview.status_code, 200)
        preview_payload = preview.json()
        self.assertTrue(preview_payload["read_only"])
        self.assertEqual(
            [chapter["content"] for chapter in preview_payload["version"]["chapters"]],
            contents,
        )
        self.assertEqual(preview_payload["archive"], before["archive"])

        restored = self.client.post(
            f"/api/independent/projects/{project_id}/versions/{original_version_id}/restore"
        )
        self.assertEqual(restored.status_code, 200)
        restored_workspace = restored.json()["workspace"]
        self.assertEqual(len(restored_workspace["versions"]), len(after_rebuild["versions"]) + 1)
        restored_active_id = restored_workspace["active_version_id"]
        self.assertNotEqual(restored_active_id, original_version_id)
        self.assertEqual(
            [chapter["content"] for chapter in restored_workspace["active_version"]["chapters"]],
            contents,
        )

        historical_after_restore = self.client.get(
            f"/api/independent/projects/{project_id}/versions/{original_version_id}/preview"
        )
        self.assertEqual(historical_after_restore.status_code, 200)
        self.assertEqual(historical_after_restore.json(), preview_payload)

        duplicate = self.client.post(
            f"/api/independent/projects/{project_id}/versions/{original_version_id}/restore"
        )
        self.assertEqual(duplicate.status_code, 200)
        duplicate_workspace = duplicate.json()["workspace"]
        self.assertEqual(duplicate_workspace["active_version_id"], restored_active_id)
        self.assertEqual(len(duplicate_workspace["versions"]), len(restored_workspace["versions"]))
        self.assertEqual(duplicate.json()["restored_from"]["version_id"], original_version_id)

    def test_anonymous_and_cross_account_requests_return_401_or_404_without_project_data(self) -> None:
        project_id, workspace, _ = self._two_chapter_story()
        endpoint = f"/api/independent/projects/{project_id}"
        deconstruction_endpoint = endpoint + "/deconstruction"
        version_id = workspace["active_version_id"]
        chapter_id = workspace["active_version"]["chapters"][0]["chapter_id"]

        anonymous = TestClient(main.app)
        self.assertEqual(anonymous.get(endpoint).status_code, 401)
        self.assertEqual(anonymous.get(deconstruction_endpoint).status_code, 401)
        anonymous.close()

        other = TestClient(main.app)
        try:
            login = other.post("/api/auth/email", json={"email": "stage33-other@example.test"})
            self.assertEqual(login.status_code, 200)
            self.assertEqual(other.get(endpoint).status_code, 404)
            self.assertEqual(other.get(deconstruction_endpoint).status_code, 404)
            self.assertEqual(
                other.get(f"{endpoint}/versions/{version_id}/preview").status_code,
                404,
            )
            self.assertEqual(
                other.put(
                    f"{endpoint}/chapters/{chapter_id}/draft",
                    json={"content": "跨账户正文", "expected_revision": 0},
                ).status_code,
                404,
            )
        finally:
            other.close()


if __name__ == "__main__":
    unittest.main()
