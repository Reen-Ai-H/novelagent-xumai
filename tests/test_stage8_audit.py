from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from app import entry_routes, independent_routes
from app.core.account_store import AccountStore
from app.core.ai_store import AIStore
from app.core.entry_service import EntryService
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore


class Stage8RegressionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
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
        self.patches = [
            patch.object(entry_routes, "account_store", accounts),
            patch.object(entry_routes, "entry_service", service),
            patch.object(independent_routes, "independent_service", independent),
        ]
        for patcher in self.patches:
            patcher.start()
        self.addCleanup(self._cleanup)
        self.client = TestClient(main.app)
        login = self.client.post(
            "/api/auth/email",
            json={"email": "stage8-regression@example.com"},
        )
        self.assertEqual(login.status_code, 200, login.text)

    def _cleanup(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def test_library_mixed_initialized_and_uninitialized_projects_stays_200(self) -> None:
        initialized = self.client.post(
            "/api/library/projects",
            json={"title": "已有正文", "mode": "independent"},
        )
        self.assertEqual(initialized.status_code, 200, initialized.text)
        initialized_id = initialized.json()["project"]["project_id"]
        started = self.client.post(
            f"/api/independent/projects/{initialized_id}/start",
            json={},
        )
        self.assertEqual(started.status_code, 200, started.text)

        uninitialized = self.client.post(
            "/api/library/projects",
            json={"title": "尚未开始", "mode": "independent"},
        )
        self.assertEqual(uninitialized.status_code, 200, uninitialized.text)

        library = self.client.get("/api/library")
        self.assertEqual(library.status_code, 200, library.text)
        self.assertEqual(
            {item["title"] for item in library.json()["projects"]},
            {"已有正文", "尚未开始"},
        )

    def test_legacy_naive_and_malformed_project_times_are_read_without_rewriting(self) -> None:
        created = self.client.post(
            "/api/library/projects",
            json={"title": "历史时间", "mode": "independent"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        project_id = created.json()["project"]["project_id"]
        path = self.root / "projects" / f"{project_id}.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        original["created_at"] = "2026-08-10T00:00:00"
        original["updated_at"] = "not-a-timestamp"
        path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")

        library = self.client.get("/api/library")
        self.assertEqual(library.status_code, 200, library.text)
        item = next(item for item in library.json()["projects"] if item["project_id"] == project_id)
        self.assertEqual(item["title"], "历史时间")
        self.assertIsNotNone(datetime.fromisoformat(item["latest_edited_at"]).tzinfo)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["updated_at"], "not-a-timestamp")

    def test_new_entry_project_timestamps_are_aware_utc(self) -> None:
        created = self.client.post(
            "/api/library/projects",
            json={"title": "新时间", "mode": "independent"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        project_id = created.json()["project"]["project_id"]
        raw = json.loads((self.root / "projects" / f"{project_id}.json").read_text(encoding="utf-8"))
        self.assertEqual(datetime.fromisoformat(raw["created_at"]).tzinfo, timezone.utc)
        self.assertEqual(datetime.fromisoformat(raw["updated_at"]).tzinfo, timezone.utc)

    def test_invalid_independent_sidecar_time_keeps_project_on_library(self) -> None:
        created = self.client.post(
            "/api/library/projects",
            json={"title": "侧车时间", "mode": "independent"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        project_id = created.json()["project"]["project_id"]
        started = self.client.post(
            f"/api/independent/projects/{project_id}/start",
            json={},
        )
        self.assertEqual(started.status_code, 200, started.text)
        path = self.root / "independent" / f"{project_id}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["updated_at"] = None
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

        library = self.client.get("/api/library")
        self.assertEqual(library.status_code, 200, library.text)
        self.assertEqual(library.json()["projects"][0]["title"], "侧车时间")

    def test_equal_project_times_have_stable_order(self) -> None:
        project_ids: list[str] = []
        for title in ("同一时刻甲", "同一时刻乙"):
            created = self.client.post(
                "/api/library/projects",
                json={"title": title, "mode": "independent"},
            )
            self.assertEqual(created.status_code, 200, created.text)
            project_ids.append(created.json()["project"]["project_id"])
        timestamp = "2026-08-10T00:00:00+00:00"
        for project_id in project_ids:
            path = self.root / "projects" / f"{project_id}.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["updated_at"] = timestamp
            path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

        first = self.client.get("/api/library")
        second = self.client.get("/api/library")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        first_ids = [item["project_id"] for item in first.json()["projects"]]
        second_ids = [item["project_id"] for item in second.json()["projects"]]
        self.assertEqual(first_ids, second_ids)
        self.assertEqual(first_ids[:2], sorted(project_ids, reverse=True))

    def test_archive_scrollspy_contract_includes_manual_scroll_and_bottom_boundary(self) -> None:
        source = Path(__file__).parents[1].joinpath("frontend/app.js").read_text(encoding="utf-8")
        self.assertIn('window.addEventListener("scroll"', source)
        self.assertIn("document.documentElement.scrollHeight - window.innerHeight", source)
        self.assertIn("getBoundingClientRect()", source)
        self.assertIn('block: "center"', source)

    def test_notification_list_has_delegated_click_contract(self) -> None:
        source = Path(__file__).parents[1].joinpath("frontend/app.js").read_text(encoding="utf-8")
        self.assertIn('elements.notificationsList.addEventListener("click", handleAction)', source)
        self.assertIn('#libraryScreen [data-action="open-notifications"]', source)
        self.assertIn("notificationTargetPath", source)
        self.assertEqual(entry_routes._notification_target("../escape", "independent", "analysis_completed"), "")
        self.assertEqual(entry_routes._notification_target("safe_project", "independent", "analysis_completed"), "/archive/safe_project")
