"""Stage 34 author-body safety checks through the real independent API."""

from __future__ import annotations

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


class Stage34IndependentSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="xumai34-independent-")
        root = Path(self.temporary.name)
        accounts = AccountStore(root / "accounts.json")
        projects = JsonProjectStore(root / "projects")
        independent = IndependentWorkspaceService(
            store=IndependentStore(root / "independent"), projects=projects,
        )
        deconstruction = DeconstructionService(
            independent=independent, store=DeconstructionStore(root / "deconstruction"),
        )
        independent.deconstruction_service = deconstruction
        self.deconstruction = deconstruction
        entry = EntryService(
            accounts=accounts, projects=projects, independent=independent.store,
            ai=AIStore(root / "ai"),
        )
        self.patchers = [
            patch.object(entry_routes, "account_store", accounts),
            patch.object(entry_routes, "entry_service", entry),
            patch.object(independent_routes, "independent_service", independent),
            patch.object(deconstruction_routes, "deconstruction_service", deconstruction),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.client = TestClient(main.app)
        login = self.client.post("/api/auth/email", json={"email": "stage34-author@example.test"})
        self.assertEqual(login.status_code, 200, login.text)
        created = self.client.post(
            "/api/library/projects", json={"title": "恢复与保存安全", "mode": "independent"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        self.project_id = created.json()["project"]["project_id"]
        self.base = f"/api/independent/projects/{self.project_id}"

    def tearDown(self) -> None:
        self.client.close()
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temporary.cleanup()

    def workspace(self) -> dict:
        response = self.client.get(self.base)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def start(self) -> dict:
        response = self.client.post(f"{self.base}/start", json={"source": "blank"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["active_version"]["chapters"][0]

    def save(self, chapter: dict, content: str, *, title: str | None = None) -> dict:
        response = self.client.put(
            f"{self.base}/chapters/{chapter['chapter_id']}/draft",
            json={"content": content, "title": title, "expected_revision": chapter["server_revision"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["chapter"]

    def complete(self, chapter: dict) -> dict:
        response = self.client.post(
            f"{self.base}/chapters/{chapter['chapter_id']}/complete",
            json={"content": chapter["content"], "expected_revision": chapter["server_revision"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["task"]

    def rebuild(self) -> dict:
        response = self.client.post(f"{self.base}/pending-changes/resolve", json={"decision": "rebuild"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["workspace"]

    def preview(self, version_id: str) -> dict:
        response = self.client.get(f"{self.base}/versions/{version_id}/preview")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["read_only"])
        return response.json()["version"]

    def test_save_revision_completion_and_source_invalidation(self) -> None:
        first = self.start()
        saved = self.save(first, "人物：林舟。剧情线：寻灯。第一章作者正式正文。")
        stale = self.client.put(
            f"{self.base}/chapters/{first['chapter_id']}/draft",
            json={"content": "过期请求不能覆盖", "expected_revision": first["server_revision"]},
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["detail"]["code"], "save_conflict")
        self.assertEqual(stale.json()["detail"]["data"]["chapter"]["content"], saved["content"])
        unsaved_complete = self.client.post(
            f"{self.base}/chapters/{saved['chapter_id']}/complete",
            json={"content": "没有保存的正文", "expected_revision": saved["server_revision"]},
        )
        self.assertEqual(unsaved_complete.status_code, 409)
        self.assertEqual(unsaved_complete.json()["detail"]["code"], "save_required")
        task = self.complete(saved)
        repeated = self.complete(saved)
        self.assertEqual(repeated["task_id"], task["task_id"])
        self.assertEqual(
            len([item for item in self.workspace()["tasks"] if item["kind"] == "chapter_analysis"]), 1,
        )
        self.deconstruction.process_background_tasks()
        report_before = self.client.get(f"{self.base}/deconstruction").json()
        self.assertEqual(report_before["effective_status"], "completed")
        source_before = report_before["source"]
        edited = self.save(self.workspace()["active_version"]["chapters"][0], saved["content"] + "作者新增一段。")
        pending = self.workspace()
        self.assertEqual(pending["active_version"]["chapters"][0]["formal_content"], saved["content"])
        self.assertIsNotNone(pending["pending_changes"])
        blocked = self.client.post(
            f"{self.base}/chapters/{edited['chapter_id']}/complete",
            json={"content": edited["content"], "expected_revision": edited["server_revision"]},
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["detail"]["code"], "pending_changes_confirmation_required")
        source_after = self.client.get(f"{self.base}/deconstruction").json()
        self.assertEqual(source_after["effective_status"], "rebuild_required")
        self.assertEqual(source_after["source"]["hash"], source_before["hash"])
        self.assertIsNone(source_after["result"])
        ignored = self.client.post(f"{self.base}/pending-changes/resolve", json={"decision": "ignore"})
        self.assertEqual(ignored.status_code, 200, ignored.text)
        invalidated = self.client.get(f"{self.base}/deconstruction").json()
        self.assertEqual(invalidated["effective_status"], "stale")
        self.assertNotEqual(invalidated["source"]["hash"], source_before["hash"])
        self.assertIsNone(invalidated["result"])

    def test_rebuild_freezes_history_and_restore_only_copies_confirmed_body(self) -> None:
        first = self.start()
        formal = self.save(first, "第一章旧正式正文。", title="第一章 旧标题")
        self.complete(formal)
        historical_id = self.workspace()["active_version_id"]
        draft = self.save(formal, "第一章尚未确认的新正文。", title="第一章 草稿标题")
        after_rebuild = self.rebuild()
        self.assertNotEqual(after_rebuild["active_version_id"], historical_id)
        self.assertEqual(after_rebuild["active_version"]["chapters"][0]["content"], draft["content"])
        frozen = deepcopy(self.preview(historical_id))
        self.assertEqual(frozen["chapters"][0]["content"], formal["content"])
        self.assertEqual(frozen["chapters"][0]["title"], formal["title"])
        self.assertEqual(frozen["chapters"][0]["formal_content"], formal["content"])
        self.assertEqual(frozen["chapters"][0]["word_count"], formal["word_count"])
        restored = self.client.post(f"{self.base}/versions/{historical_id}/restore")
        self.assertEqual(restored.status_code, 200, restored.text)
        current = self.workspace()["active_version"]
        self.assertEqual(current["chapters"][0]["content"], formal["content"])
        self.assertEqual(current["chapters"][0]["title"], formal["title"])
        self.assertNotEqual(current["chapters"][0]["chapter_id"], frozen["chapters"][0]["chapter_id"])
        self.assertEqual(self.preview(historical_id), frozen)

    def test_restore_blocks_pending_changes_and_repeated_request_is_idempotent(self) -> None:
        first = self.start()
        formal = self.save(first, "第一章正式正文。")
        self.complete(formal)
        historical_id = self.workspace()["active_version_id"]
        self.save(formal, "第二版正式正文。")
        current = self.rebuild()
        active_id = current["active_version_id"]
        chapter = current["active_version"]["chapters"][0]
        pending_draft = self.save(chapter, "尚未确认的第三版正文。")
        before_block = self.workspace()
        blocked = self.client.post(f"{self.base}/versions/{historical_id}/restore")
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["detail"]["code"], "pending_changes_confirmation_required")
        after_block = self.workspace()
        self.assertEqual(after_block["active_version_id"], active_id)
        self.assertEqual(len(after_block["versions"]), len(before_block["versions"]))
        self.assertEqual(after_block["active_version"]["chapters"][0]["content"], pending_draft["content"])
        self.assertEqual(after_block["pending_changes"], before_block["pending_changes"])
        ignored = self.client.post(f"{self.base}/pending-changes/resolve", json={"decision": "ignore"})
        self.assertEqual(ignored.status_code, 200, ignored.text)
        selected = deepcopy(self.preview(historical_id))
        restored = self.client.post(f"{self.base}/versions/{historical_id}/restore")
        self.assertEqual(restored.status_code, 200, restored.text)
        first_restore = self.workspace()
        second = self.client.post(f"{self.base}/versions/{historical_id}/restore")
        self.assertEqual(second.status_code, 200, second.text)
        repeated = self.workspace()
        self.assertEqual(repeated["active_version_id"], first_restore["active_version_id"])
        self.assertEqual(len(repeated["versions"]), len(first_restore["versions"]))
        self.assertEqual(second.json()["task"]["task_id"], restored.json()["task"]["task_id"])
        self.assertEqual(self.preview(historical_id), selected)
        changed = self.save(repeated["active_version"]["chapters"][0], "恢复副本后来另有作者修改。")
        self.assertEqual(changed["content"], "恢复副本后来另有作者修改。")
        self.assertEqual(self.preview(historical_id), selected)
        still_blocked = self.client.post(f"{self.base}/versions/{historical_id}/restore")
        self.assertEqual(still_blocked.status_code, 409)
        self.assertEqual(self.workspace()["active_version_id"], first_restore["active_version_id"])
        self.assertEqual(self.preview(historical_id), selected)
