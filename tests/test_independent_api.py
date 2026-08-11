from __future__ import annotations

import base64
import io
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from app import entry_routes, independent_routes
from app.core.account_store import AccountStore
from app.core.entry_service import EntryService
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore


class IndependentApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        accounts = AccountStore(root / "accounts.json")
        projects = JsonProjectStore(root / "projects")
        service = EntryService(accounts=accounts, projects=projects)
        independent = IndependentWorkspaceService(
            store=IndependentStore(root / "independent"),
            projects=projects,
        )
        self.independent = independent
        self.patches = [
            patch.object(entry_routes, "account_store", accounts),
            patch.object(entry_routes, "entry_service", service),
            patch.object(independent_routes, "independent_service", independent),
        ]
        for patcher in self.patches:
            patcher.start()
        self.addCleanup(self._cleanup)
        self.client = TestClient(main.app)

    def _cleanup(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def _project(self, title: str = "雾港来信") -> str:
        self.client.post("/api/auth/email", json={"email": "independent@example.com"})
        response = self.client.post(
            "/api/library/projects",
            json={"title": title, "mode": "independent"},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["project"]["project_id"]

    @staticmethod
    def _encoded(text: str) -> str:
        return base64.b64encode(text.encode("utf-8")).decode("ascii")

    def test_import_preview_requires_confirmation_and_supports_txt_md_docx(self) -> None:
        project_id = self._project()
        invalid = self.client.post(
            f"/api/independent/projects/{project_id}/imports/preview",
            json={"filename": "旧稿.pdf", "content_base64": self._encoded("不能直接写入")},
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(invalid.json()["preview"]["status"], "failed")
        self.assertIn("TXT", invalid.json()["preview"]["error_message"])

        source = "导入说明\n# 第一章 雾起\n人物：林舟、顾遥\n剧情线：寻找旧港灯塔\n伏笔：门缝里的蓝纸\n\n海风从门缝里进来。\n# 第二章 回声\n线索在钟楼。"
        preview_response = self.client.post(
            f"/api/independent/projects/{project_id}/imports/preview",
            json={"filename": "雾港.md", "content_base64": self._encoded(source)},
        )
        self.assertEqual(preview_response.status_code, 200)
        preview = preview_response.json()["preview"]
        self.assertEqual(preview["format"], "md")
        self.assertEqual(preview["chapter_count"], 2)
        self.assertEqual(preview["total_word_count"], 42)
        self.assertTrue(preview["unrecognized_fragments"])

        before = self.client.get(f"/api/independent/projects/{project_id}").json()
        self.assertFalse(before["initialized"])
        confirmed = self.client.post(
            f"/api/independent/projects/{project_id}/imports/{preview['preview_id']}/confirm"
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(confirmed.json()["initialized"])
        self.assertEqual(len(confirmed.json()["active_version"]["chapters"]), 2)

        docx_project = self._project("DOCX 作品")
        document_xml = (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>第一章 文档</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>DOCX 正文保存。</w:t></w:r></w:p></w:body></w:document>"
        )
        docx_buffer = io.BytesIO()
        with zipfile.ZipFile(docx_buffer, "w") as archive:
            archive.writestr("word/document.xml", document_xml)
        docx_preview = self.client.post(
            f"/api/independent/projects/{docx_project}/imports/preview",
            json={
                "filename": "文档.docx",
                "content_base64": base64.b64encode(docx_buffer.getvalue()).decode("ascii"),
            },
        )
        self.assertEqual(docx_preview.status_code, 200)
        self.assertEqual(docx_preview.json()["preview"]["format"], "docx")
        self.assertEqual(docx_preview.json()["preview"]["chapter_count"], 1)

    def test_autosave_conflict_complete_is_idempotent_and_snapshot_recovers(self) -> None:
        project_id = self._project()
        start = self.client.post(f"/api/independent/projects/{project_id}/start", json={"source": "blank"})
        self.assertEqual(start.status_code, 200)
        chapter = start.json()["active_version"]["chapters"][0]
        chapter_id = chapter["chapter_id"]

        saved = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter_id}/draft",
            json={
                "content": "人物：林舟。剧情线：寻找灯塔。伏笔：蓝纸。林舟走进雾里。",
                "expected_revision": chapter["server_revision"],
            },
        )
        self.assertEqual(saved.status_code, 200)
        new_chapter = saved.json()["chapter"]
        conflict = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter_id}/draft",
            json={"content": "另一端的正文", "expected_revision": chapter["server_revision"]},
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["detail"]["code"], "save_conflict")
        self.assertIn("服务器", conflict.json()["detail"]["message"])

        complete_payload = {
            "content": new_chapter["content"],
            "expected_revision": new_chapter["server_revision"],
            "idempotency_key": "chapter-one",
        }
        completed = self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{chapter_id}/complete",
            json=complete_payload,
        )
        self.assertEqual(completed.status_code, 200)
        task = completed.json()["task"]
        self.assertEqual(task["status"], "queued")
        task = self.client.get(
            f"/api/independent/projects/{project_id}/tasks/{task['task_id']}"
        ).json()["task"]
        self.assertEqual(task["status"], "completed")
        duplicate = self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{chapter_id}/complete",
            json=complete_payload,
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json()["task"]["task_id"], task["task_id"])

        archive = self.client.get(f"/api/independent/projects/{project_id}/archive")
        self.assertEqual(archive.status_code, 200)
        self.assertEqual(archive.json()["archive"]["latest_chapter_number"], 1)
        self.assertEqual(archive.json()["archive"]["characters"][0]["source_chapter_number"], 1)
        self.assertTrue(archive.json()["available_snapshots"])

        fresh_client = TestClient(main.app)
        fresh_client.post("/api/auth/email", json={"email": "independent@example.com"})
        recovered = fresh_client.get(f"/api/independent/projects/{project_id}")
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(
            recovered.json()["active_version"]["chapters"][0]["content"],
            new_chapter["content"],
        )

    def test_analysis_failure_is_persistent_and_retryable_without_model_key(self) -> None:
        project_id = self._project("失败重试")
        started = self.client.post(f"/api/independent/projects/{project_id}/start", json={"source": "blank"}).json()
        chapter = started["active_version"]["chapters"][0]
        saved = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/draft",
            json={"content": "[[analysis-fail]] 先记录失败。", "expected_revision": chapter["server_revision"]},
        ).json()["chapter"]
        failed = self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/complete",
            json={"content": saved["content"], "expected_revision": saved["server_revision"]},
        )
        self.assertEqual(failed.status_code, 200)
        task_id = failed.json()["task"]["task_id"]
        failed_task = self.client.get(
            f"/api/independent/projects/{project_id}/tasks/{task_id}"
        ).json()["task"]
        self.assertEqual(failed_task["status"], "failed")
        corrected = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/draft",
            json={"content": "失败已修正。人物：林舟。", "expected_revision": saved["server_revision"]},
        ).json()["chapter"]
        retry = self.client.post(f"/api/independent/projects/{project_id}/tasks/{task_id}/retry")
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json()["task"]["status"], "completed")
        self.assertEqual(retry.json()["task"]["task_id"], task_id)
        self.assertGreater(corrected["server_revision"], saved["server_revision"])

    def test_queued_analysis_recovers_after_service_restart(self) -> None:
        project_id = self._project("后台恢复")
        account_id = self.client.get("/api/auth/session").json()["account"]["account_id"]
        record = self.independent.start_blank(project_id, account_id)
        chapter = record.versions[0].chapters[0]
        saved = self.independent.save_draft(
            project_id,
            account_id,
            chapter.chapter_id,
            content="服务重启后继续分析。人物：林舟。",
            title=chapter.title,
            expected_revision=chapter.server_revision,
        )
        queued = self.independent.complete_chapter(
            project_id,
            account_id,
            chapter.chapter_id,
            content=saved.content,
            expected_revision=saved.server_revision,
            idempotency_key="restart-recovery",
        )
        self.assertEqual(queued.status, "queued")

        restarted = IndependentWorkspaceService(
            store=self.independent.store,
            projects=self.independent.projects,
        )
        restarted.recover_pending_tasks(project_id, account_id)
        recovered = restarted.task(project_id, account_id, queued.task_id)
        self.assertEqual(recovered.status, "completed")
        self.assertEqual(
            restarted.workspace(project_id, account_id)["active_version"].archive.latest_chapter_number,
            1,
        )

    def test_pending_changes_ignore_rebuild_and_history_restore(self) -> None:
        project_id = self._project("版本回溯")
        started = self.client.post(f"/api/independent/projects/{project_id}/start", json={"source": "blank"}).json()
        chapter = started["active_version"]["chapters"][0]
        saved = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/draft",
            json={"content": "第一版正文。人物：林舟。", "expected_revision": chapter["server_revision"]},
        ).json()["chapter"]
        self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/complete",
            json={"content": saved["content"], "expected_revision": saved["server_revision"]},
        )
        original = self.client.get(f"/api/independent/projects/{project_id}").json()
        original_version_id = original["active_version_id"]
        original_revision = original["active_version"]["chapters"][0]["server_revision"]

        edited = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/draft",
            json={"content": "第一版正文，轻微措辞调整。人物：林舟。", "expected_revision": original_revision},
        )
        self.assertEqual(edited.status_code, 200)
        pending = edited.json()["workspace"]["pending_changes"]
        self.assertEqual(len(pending["changes"]), 1)
        blocked_complete = self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/complete",
            json={"content": edited.json()["chapter"]["content"], "expected_revision": edited.json()["chapter"]["server_revision"]},
        )
        self.assertEqual(blocked_complete.status_code, 409)
        ignored = self.client.post(
            f"/api/independent/projects/{project_id}/pending-changes/resolve",
            json={"decision": "ignore"},
        )
        self.assertEqual(ignored.status_code, 200)
        self.assertEqual(ignored.json()["workspace"]["active_version_id"], original_version_id)
        self.assertIsNone(ignored.json()["workspace"]["pending_changes"])

        current = ignored.json()["workspace"]["active_version"]["chapters"][0]
        edited_again = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/draft",
            json={"content": "重建版本正文。剧情线：旧港灯塔。", "expected_revision": current["server_revision"]},
        ).json()["chapter"]
        rebuilt = self.client.post(
            f"/api/independent/projects/{project_id}/pending-changes/resolve",
            json={"decision": "rebuild"},
        )
        self.assertEqual(rebuilt.status_code, 200)
        rebuilt_workspace = rebuilt.json()["workspace"]
        self.assertNotEqual(rebuilt_workspace["active_version_id"], original_version_id)
        self.assertEqual(sum(item["status"] == "active" for item in rebuilt_workspace["versions"]), 1)
        old_version = next(item for item in rebuilt_workspace["versions"] if item["version_id"] == original_version_id)
        self.assertEqual(old_version["status"], "recoverable")
        self.assertIsNotNone(old_version["recoverable_until"])
        rebuilt_version_id = rebuilt_workspace["active_version_id"]
        preview = self.client.get(f"/api/independent/projects/{project_id}/versions/{original_version_id}/preview")
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.json()["read_only"])
        restored = self.client.post(f"/api/independent/projects/{project_id}/versions/{original_version_id}/restore")
        self.assertEqual(restored.status_code, 200)
        restored_workspace = restored.json()["workspace"]
        self.assertNotEqual(restored_workspace["active_version_id"], rebuilt_version_id)
        self.assertEqual(sum(item["status"] == "active" for item in restored_workspace["versions"]), 1)
        persisted = self.independent.store.load(project_id)
        historical = next(item for item in persisted.versions if item.version_id == original_version_id)
        historical.recoverable_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.independent.store.save(persisted)
        expired = self.client.post(
            f"/api/independent/projects/{project_id}/versions/{original_version_id}/restore"
        )
        self.assertEqual(expired.status_code, 410)
        self.assertEqual(expired.json()["detail"]["code"], "version_expired")

    def test_archive_snapshot_is_read_only_and_trial_requires_explicit_confirmation(self) -> None:
        project_id = self._project("档案卡片")
        started = self.client.post(f"/api/independent/projects/{project_id}/start", json={"source": "blank"}).json()
        chapter = started["active_version"]["chapters"][0]
        saved = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/draft",
            json={"content": "人物：林舟。伏笔：蓝纸。", "expected_revision": 0},
        ).json()["chapter"]
        self.client.post(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/complete",
            json={"content": saved["content"], "expected_revision": saved["server_revision"]},
        )
        archive = self.client.get(f"/api/independent/projects/{project_id}/archive?chapter_number=1")
        self.assertEqual(archive.status_code, 200)
        self.assertTrue(archive.json()["read_only"])
        character_id = archive.json()["archive"]["characters"][0]["character_id"]
        estimate = self.client.post(
            f"/api/independent/projects/{project_id}/characters/{character_id}/trial-sketch",
            json={"style": "水墨线稿", "confirm": False},
        )
        self.assertEqual(estimate.status_code, 200)
        self.assertFalse(estimate.json()["credits_charged"])
        unconfigured = self.client.post(
            f"/api/independent/projects/{project_id}/characters/{character_id}/trial-sketch",
            json={"style": "水墨线稿", "confirm": True},
        )
        self.assertEqual(unconfigured.status_code, 503)
        self.assertEqual(unconfigured.json()["detail"]["code"], "image_service_unconfigured")


if __name__ == "__main__":
    unittest.main()
