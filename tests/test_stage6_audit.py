from __future__ import annotations

import base64
import io
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from app import ai_routes, entry_routes, independent_routes, novel_routes
from app.agents.llm_runtime import LLMRuntime, LLMRuntimeSettings
from app.core.account_store import AccountStore
from app.core.ai_service import AIStudioService
from app.core.ai_store import AIStore
from app.core.entry_service import EntryService
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore


class Stage6P0LegacyAuthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.accounts = AccountStore(root / "accounts.json")
        self.projects = JsonProjectStore(root / "projects")
        self.novel_service = novel_routes.novel_workflow_service.__class__(
            store=self.projects
        )
        self.patches = [
            patch.object(entry_routes, "account_store", self.accounts),
            patch.object(novel_routes, "novel_workflow_service", self.novel_service),
        ]
        for patcher in self.patches:
            patcher.start()
        self.addCleanup(self._cleanup)
        self.client_a = TestClient(main.app)
        self.client_b = TestClient(main.app)
        self.assertEqual(
            self.client_a.post("/api/auth/email", json={"email": "stage6-a@example.com"}).status_code,
            200,
        )
        self.assertEqual(
            self.client_b.post("/api/auth/email", json={"email": "stage6-b@example.com"}).status_code,
            200,
        )

    def _cleanup(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def _create_project(self) -> tuple[str, str]:
        response = self.client_a.post(
            "/novel/projects",
            json={
                "project_id": "stage6-legacy-a",
                "title": "阶段 6 旧路由作品",
                "global_worldview": "旧城的档案会记录所有公开事件。",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        planned = self.client_a.post(
            "/novel/chapters/plan",
            json={
                "project_id": "stage6-legacy-a",
                "global_worldview": "旧城的档案会记录所有公开事件。",
                "chapter_number": 1,
                "characters": [],
            },
        )
        self.assertEqual(planned.status_code, 200, planned.text)
        return "stage6-legacy-a", planned.json()["session_id"]

    @staticmethod
    def _legacy_calls(project_id: str, session_id: str) -> list[tuple[str, callable]]:
        return [
            ("create", lambda client: client.post("/novel/projects", json={"title": "未登录作品"})),
            ("list", lambda client: client.get("/novel/projects")),
            ("plan", lambda client: client.post("/novel/chapters/plan", json={"project_id": project_id, "global_worldview": "世界", "chapter_number": 1, "characters": []})),
            ("current", lambda client: client.get("/novel/projects/current")),
            ("project", lambda client: client.get(f"/novel/projects/{project_id}")),
            ("codex", lambda client: client.get(f"/novel/projects/{project_id}/codex")),
            ("prepare-get", lambda client: client.get(f"/novel/projects/{project_id}/prepare-next")),
            ("prepare-post", lambda client: client.post(f"/novel/projects/{project_id}/prepare-next", json={})),
            ("full-plan-post", lambda client: client.post(f"/novel/projects/{project_id}/full-plan", json={"target_chapter_count": 1})),
            ("full-plan-put", lambda client: client.put(f"/novel/projects/{project_id}/full-plan", json={"full_plan": {"premise": "阶段 6", "core_conflict": "归属校验"}})),
            ("batch-plan", lambda client: client.post(f"/novel/projects/{project_id}/batch/plan", json={"start_chapter": 1, "end_chapter": 1})),
            ("batch-generate", lambda client: client.post(f"/novel/projects/{project_id}/batch/generate", json={"start_chapter": 1, "end_chapter": 1})),
            ("chapter", lambda client: client.get(f"/novel/projects/{project_id}/chapters/1")),
            ("next", lambda client: client.post(f"/novel/projects/{project_id}/chapters/next", json={})),
            ("approve", lambda client: client.post(f"/novel/chapters/{session_id}/approve", json={"plot_beats": [{"order": 1, "summary": "继续"}], "human_feedback": "继续"})),
            ("review", lambda client: client.post(f"/novel/chapters/{session_id}/review")),
            ("revise", lambda client: client.post(f"/novel/chapters/{session_id}/revise", json={"human_feedback": "继续"})),
            ("accept", lambda client: client.post(f"/novel/chapters/{session_id}/accept", json={"human_feedback": "接受"})),
            ("session", lambda client: client.get(f"/novel/sessions/{session_id}")),
        ]

    def test_all_legacy_operations_require_session_and_owner(self) -> None:
        project_id, session_id = self._create_project()
        anonymous = TestClient(main.app)
        for name, call in self._legacy_calls(project_id, session_id):
            response = call(anonymous)
            self.assertEqual(response.status_code, 401, name)

        for name, call in self._legacy_calls(project_id, session_id):
            if name == "create":
                continue
            response = call(self.client_b)
            if name == "list":
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["projects"], [])
            else:
                self.assertIn(response.status_code, {403, 404}, name)

        self.assertEqual(self.client_b.get("/novel/projects").json()["projects"], [])
        self.novel_service.create_project(
            project_id="stage6-orphan",
            title="无 owner 历史作品",
            global_worldview="保留但不可认领。",
        )
        self.assertEqual(self.client_a.get("/novel/projects/stage6-orphan").status_code, 404)


class Stage6P0PrivateResponseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        accounts = AccountStore(root / "accounts.json")
        projects = JsonProjectStore(root / "projects")
        independent = IndependentWorkspaceService(
            store=IndependentStore(root / "independent"),
            projects=projects,
        )
        service = EntryService(
            accounts=accounts,
            projects=projects,
            independent=independent.store,
            ai=AIStore(root / "ai"),
        )
        ai = AIStudioService(
            store=AIStore(root / "ai"),
            projects=projects,
            manuscript=independent,
            runtime=LLMRuntime(LLMRuntimeSettings()),
        )
        self.ai = ai
        self.patches = [
            patch.object(entry_routes, "account_store", accounts),
            patch.object(entry_routes, "entry_service", service),
            patch.object(independent_routes, "independent_service", independent),
            patch.object(ai_routes, "ai_service", ai),
        ]
        for patcher in self.patches:
            patcher.start()
        self.addCleanup(self._cleanup)
        self.client = TestClient(main.app)
        self.assertEqual(
            self.client.post("/api/auth/email", json={"email": "stage6-private@example.com"}).status_code,
            200,
        )

    def _cleanup(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def test_private_memory_never_enters_browser_response(self) -> None:
        created = self.client.post(
            "/api/library/projects",
            json={"title": "双哨兵", "mode": "ai_assisted", "brief": "共享事实"},
        )
        project_id = created.json()["project"]["project_id"]
        blueprint = self.client.post(
            f"/api/ai/projects/{project_id}/messages",
            json={"content": "主角是林舟，顾遥守住回信。"},
        ).json()
        confirmed = self.client.post(
            f"/api/ai/projects/{project_id}/blueprint/confirm",
            json={"expected_revision": blueprint["blueprint_revision"], "idempotency_key": "stage6-confirm"},
        )
        run = self.client.post(
            f"/api/ai/projects/{project_id}/director/start",
            json={"strategy": "pause_at_key_nodes", "idempotency_key": "stage6-run"},
        ).json()["active_run"]
        record = self.ai.store.load(project_id)
        self.assertIsNotNone(record)
        by_name = {item.name: item for item in record.story_characters}
        by_name["林舟"].private_memory = ["林舟私有审计哨兵 A"]
        by_name["顾遥"].private_memory = ["顾遥私有审计哨兵 B"]
        by_name["林舟"].experiences = ["林舟内部经历哨兵 A"]
        by_name["顾遥"].experiences = ["顾遥内部经历哨兵 B"]
        self.ai.store.save(record)

        browser_response = self.client.get(
            f"/api/ai/projects/{project_id}/director/runs/{run['run_id']}/character-contexts"
        )
        self.assertEqual(browser_response.status_code, 200)
        serialized = browser_response.json()
        rendered = str(serialized)
        self.assertNotIn("private_memory", rendered)
        self.assertNotIn("审计哨兵 A", rendered)
        self.assertNotIn("审计哨兵 B", rendered)
        self.assertNotIn("内部经历哨兵 A", rendered)
        self.assertNotIn("内部经历哨兵 B", rendered)
        self.assertIn("共享", rendered)

        internal = self.ai.story_character_contexts(project_id, record.account_id, run["run_id"])
        internal_by_name = {item.name: item for item in internal}
        self.assertIn("林舟私有审计哨兵 A", internal_by_name["林舟"].private_memory)
        self.assertNotIn("顾遥私有审计哨兵 B", internal_by_name["林舟"].private_memory)
        self.assertIn("顾遥私有审计哨兵 B", internal_by_name["顾遥"].private_memory)
        self.assertNotIn("林舟私有审计哨兵 A", internal_by_name["顾遥"].private_memory)


class Stage6P1ReliabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        accounts = AccountStore(self.root / "accounts.json")
        projects = JsonProjectStore(self.root / "projects")
        independent = IndependentWorkspaceService(
            store=IndependentStore(self.root / "independent"),
            projects=projects,
        )
        service = EntryService(
            accounts=accounts,
            projects=projects,
            independent=independent.store,
            ai=AIStore(self.root / "ai"),
        )
        ai = AIStudioService(
            store=AIStore(self.root / "ai"),
            projects=projects,
            manuscript=independent,
            runtime=LLMRuntime(LLMRuntimeSettings()),
        )
        self.accounts = accounts
        self.projects = projects
        self.independent = independent
        self.ai = ai
        self.patches = [
            patch.object(entry_routes, "account_store", accounts),
            patch.object(entry_routes, "entry_service", service),
            patch.object(independent_routes, "independent_service", independent),
            patch.object(ai_routes, "ai_service", ai),
        ]
        for patcher in self.patches:
            patcher.start()
        self.addCleanup(self._cleanup)
        self.client = TestClient(main.app)
        login = self.client.post(
            "/api/auth/email",
            json={"email": "stage6-p1@example.com"},
        )
        self.assertEqual(login.status_code, 200, login.text)

    def _cleanup(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def _independent_project(self) -> str:
        response = self.client.post(
            "/api/library/projects",
            json={"title": "阶段 6 导入校验", "mode": "independent"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["project"]["project_id"]

    def _ai_project(self, title: str) -> str:
        response = self.client.post(
            "/api/library/projects",
            json={"title": title, "mode": "ai_assisted", "brief": "一座被雾封存的城市。"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        project_id = response.json()["project"]["project_id"]
        message = self.client.post(
            f"/api/ai/projects/{project_id}/messages",
            json={"content": "主角是林舟，顾遥守住回信。"},
        )
        self.assertEqual(message.status_code, 200, message.text)
        confirmed = self.client.post(
            f"/api/ai/projects/{project_id}/blueprint/confirm",
            json={
                "expected_revision": message.json()["blueprint_revision"],
                "idempotency_key": f"stage6-confirm-{project_id}",
            },
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        return project_id

    def test_blank_txt_md_docx_preview_fails_and_confirm_cannot_create_version(self) -> None:
        project_id = self._independent_project()
        docx_buffer = io.BytesIO()
        with zipfile.ZipFile(docx_buffer, "w") as archive:
            archive.writestr(
                "word/document.xml",
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>   </w:t></w:r></w:p></w:body></w:document>',
            )
        inputs = {
            "empty.txt": b" \n\t ",
            "empty.md": b"\n  \n",
            "empty.docx": docx_buffer.getvalue(),
        }
        for filename, content in inputs.items():
            preview_response = self.client.post(
                f"/api/independent/projects/{project_id}/imports/preview",
                json={
                    "filename": filename,
                    "content_base64": base64.b64encode(content).decode("ascii"),
                },
            )
            self.assertEqual(preview_response.status_code, 200, preview_response.text)
            preview = preview_response.json()["preview"]
            self.assertEqual(preview["status"], "failed", filename)
            self.assertIn("正文", preview["error_message"], filename)
            confirm = self.client.post(
                f"/api/independent/projects/{project_id}/imports/{preview['preview_id']}/confirm",
            )
            self.assertEqual(confirm.status_code, 422, filename)
        workspace = self.client.get(f"/api/independent/projects/{project_id}")
        self.assertIsNone(workspace.json()["active_version_id"])

    def test_server_worker_advances_after_page_exit_and_zero_credit_demo_is_idempotent(self) -> None:
        project_id = self._ai_project("阶段 6 服务端导演台")
        started = self.client.post(
            f"/api/ai/projects/{project_id}/director/start",
            json={"strategy": "pause_at_key_nodes", "defer": True, "idempotency_key": "stage6-worker"},
        )
        self.assertEqual(started.status_code, 200, started.text)
        run_id = started.json()["active_run"]["run_id"]
        self.assertEqual(started.json()["active_run"]["status"], "character_simulation")

        fresh_service = AIStudioService(
            store=AIStore(self.root / "ai"),
            projects=self.projects,
            manuscript=self.independent,
            runtime=LLMRuntime(LLMRuntimeSettings()),
        )
        with patch.object(ai_routes, "ai_service", fresh_service):
            with TestClient(main.app) as page_closed_client:
                logged_in = page_closed_client.post(
                    "/api/auth/email",
                    json={"email": "stage6-p1@example.com"},
                )
                self.assertEqual(logged_in.status_code, 200, logged_in.text)
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    recovered = page_closed_client.get(
                        f"/api/ai/projects/{project_id}/director/runs/{run_id}"
                    )
                    if recovered.json()["run"]["status"] == "waiting_for_choice":
                        break
                    time.sleep(0.05)
                self.assertEqual(recovered.json()["run"]["status"], "waiting_for_choice")
                self.assertEqual(len(recovered.json()["run"]["choices"]), 3)

                chosen = page_closed_client.post(
                    f"/api/ai/projects/{project_id}/director/runs/{run_id}/choice",
                    json={"choice_id": "hand-to-role"},
                )
                self.assertEqual(chosen.status_code, 200, chosen.text)
                self.assertEqual(chosen.json()["active_run"]["used_credits"], 0)
                self.assertEqual(chosen.json()["credits_used"], 0)
                self.assertIn("不消耗创作积分", chosen.json()["analysis_label"])
                repeated = page_closed_client.post(
                    f"/api/ai/projects/{project_id}/director/runs/{run_id}/choice",
                    json={"choice_id": "hand-to-role"},
                )
                self.assertEqual(repeated.status_code, 200, repeated.text)
                self.assertEqual(len(fresh_service.store.load(project_id).credit_ledger), 1)
                self.assertEqual(fresh_service.store.load(project_id).credit_ledger[0].credits, 0)

        resumed = AIStudioService(
            store=AIStore(self.root / "ai"),
            projects=self.projects,
            manuscript=self.independent,
            runtime=LLMRuntime(LLMRuntimeSettings()),
        )
        self.assertEqual(resumed.store.load(project_id).runs[-1].status, "completed")

    def test_notifications_are_persistent_readable_and_account_bound(self) -> None:
        project_id = self._ai_project("阶段 6 通知隔离")
        notifications = self.client.get("/api/notifications")
        self.assertEqual(notifications.status_code, 200, notifications.text)
        payload = notifications.json()
        self.assertEqual(payload["unread_count"], 1)
        item = next(item for item in payload["notifications"] if item["project_id"] == project_id)
        self.assertEqual(item["project_title"], "阶段 6 通知隔离")
        self.assertEqual(item["target_path"], f"/ai/{project_id}")
        marked = self.client.post(
            f"/api/notifications/{project_id}/{item['notification_id']}/read",
        )
        self.assertEqual(marked.status_code, 200, marked.text)
        self.assertEqual(marked.json()["unread_count"], 0)

        fresh = TestClient(main.app)
        self.assertEqual(
            fresh.post("/api/auth/email", json={"email": "stage6-p1@example.com"}).status_code,
            200,
        )
        recovered = fresh.get("/api/notifications")
        self.assertEqual(recovered.status_code, 200, recovered.text)
        recovered_item = next(item for item in recovered.json()["notifications"] if item["project_id"] == project_id)
        self.assertTrue(recovered_item["read"])

        other = TestClient(main.app)
        self.assertEqual(
            other.post("/api/auth/email", json={"email": "stage6-other@example.com"}).status_code,
            200,
        )
        self.assertEqual(other.get("/api/notifications").json()["notifications"], [])
        self.assertEqual(
            other.post(
                f"/api/notifications/{project_id}/{item['notification_id']}/read",
            ).status_code,
            404,
        )
