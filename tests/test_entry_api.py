from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from app import entry_routes
from app.core.account_store import AccountStore
from app.core.entry_service import EntryService
from app.core.project_store import JsonProjectStore


class EntryApiTest(unittest.TestCase):
    def _client(self, tmp_dir: str) -> TestClient:
        accounts = AccountStore(Path(tmp_dir) / "accounts.json")
        projects = JsonProjectStore(Path(tmp_dir) / "projects")
        service = EntryService(accounts=accounts, projects=projects)
        self._patches = [
            patch.object(entry_routes, "account_store", accounts),
            patch.object(entry_routes, "entry_service", service),
        ]
        for patcher in self._patches:
            patcher.start()
        self.addCleanup(self._stop_patches)
        return TestClient(main.app)

    def _stop_patches(self) -> None:
        for patcher in reversed(getattr(self, "_patches", [])):
            patcher.stop()

    def test_email_login_rejects_invalid_input_and_persists_account(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            client = self._client(tmp_dir)

            invalid = client.post("/api/auth/email", json={"email": "not-an-email"})
            self.assertEqual(invalid.status_code, 422)
            self.assertEqual(invalid.json()["detail"]["code"], "invalid_email")

            login = client.post("/api/auth/email", json={"email": "Writer@Example.com"})
            self.assertEqual(login.status_code, 200)
            self.assertEqual(login.json()["account"]["email"], "writer@example.com")
            self.assertIn("xumai_session", client.cookies)

            session = client.get("/api/auth/session")
            self.assertEqual(session.status_code, 200)
            self.assertTrue(session.json()["authenticated"])

            client.post("/api/auth/logout")
            self.assertFalse(client.get("/api/auth/session").json()["authenticated"])

            relogin = client.post("/api/auth/email", json={"email": "writer@example.com"})
            self.assertEqual(relogin.status_code, 200)
            self.assertEqual(
                relogin.json()["account"]["account_id"],
                login.json()["account"]["account_id"],
            )

    def test_session_expiry_is_explicit_and_does_not_delete_projects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            client = self._client(tmp_dir)
            client.post("/api/auth/email", json={"email": "author@example.com"})
            created = client.post(
                "/api/library/projects",
                json={"title": "潮汐档案", "mode": "independent"},
            )
            self.assertEqual(created.status_code, 200)
            project_id = created.json()["project"]["project_id"]

            client.cookies.set("xumai_session", "expired-or-unknown")
            expired = client.get("/api/auth/session")
            self.assertEqual(expired.status_code, 401)
            self.assertEqual(expired.json()["detail"]["code"], "session_expired")

            fresh_client = TestClient(main.app)
            fresh_client.post("/api/auth/email", json={"email": "author@example.com"})
            library = fresh_client.get("/api/library")
            self.assertEqual(library.status_code, 200)
            self.assertEqual(library.json()["projects"][0]["project_id"], project_id)

    def test_projects_are_account_bound_searchable_and_mode_is_persistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            client = self._client(tmp_dir)
            client.post("/api/auth/email", json={"email": "first@example.com"})
            independent = client.post(
                "/api/library/projects",
                json={
                    "title": "雾港来信",
                    "mode": "independent",
                    "brief": "一位作者整理旧港口的来信。",
                },
            )
            ai_project = client.post(
                "/api/library/projects",
                json={"title": "第七码头", "mode": "ai_assisted"},
            )
            self.assertEqual(independent.json()["project"]["mode"], "independent")
            self.assertIn("独立创作编辑器", independent.json()["next_step_label"])
            self.assertEqual(ai_project.json()["project"]["mode_label"], "AI 辅助写作")
            self.assertIn("AI 创作室", ai_project.json()["next_step_label"])

            library = client.get("/api/library?q=雾港")
            self.assertEqual(library.status_code, 200)
            self.assertEqual([item["title"] for item in library.json()["projects"]], ["雾港来信"])

            client.post("/api/auth/logout")
            client.post("/api/auth/email", json={"email": "second@example.com"})
            other_library = client.get("/api/library")
            self.assertEqual(other_library.status_code, 200)
            self.assertEqual(other_library.json()["projects"], [])


if __name__ == "__main__":
    unittest.main()
