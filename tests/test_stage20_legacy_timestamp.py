from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from app import entry_routes, novel_routes
from app.core.account_store import AccountStore
from app.core.project_store import JsonProjectStore
from app.models import NovelProject


class Stage20LegacyTimestampTest(unittest.TestCase):
    """旧接口读取历史混合时间时只做内存兼容，不改变归属或原始文件。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.accounts = AccountStore(root / "accounts.json")
        self.projects = JsonProjectStore(root / "projects")
        self.workflow = novel_routes.novel_workflow_service.__class__(store=self.projects)
        self.patches = [
            patch.object(entry_routes, "account_store", self.accounts),
            patch.object(novel_routes, "novel_workflow_service", self.workflow),
        ]
        for patcher in self.patches:
            patcher.start()
        self.addCleanup(self._cleanup)
        self.client_a = TestClient(main.app)
        self.client_b = TestClient(main.app)
        self.assertEqual(
            self.client_a.post(
                "/api/auth/email",
                json={"email": "stage20-a@example.test"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client_b.post(
                "/api/auth/email",
                json={"email": "stage20-b@example.test"},
            ).status_code,
            200,
        )

    def _cleanup(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def _create(self, client: TestClient, project_id: str) -> None:
        response = client.post(
            "/novel/projects",
            json={
                "project_id": project_id,
                "title": project_id,
                "project_brief": "阶段 20 混合时间兼容",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)

    def _rewrite_raw_time(
        self,
        project_id: str,
        *,
        updated_at: object = ...,
        created_at: str = "2024-01-01T00:00:00Z",
    ) -> None:
        path = self.projects._project_path(project_id)
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["created_at"] = created_at
        if updated_at is ...:
            raw.pop("updated_at", None)
        else:
            raw["updated_at"] = updated_at
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_authenticated_legacy_list_handles_mixed_times_and_owner_boundary(self) -> None:
        account_a_ids = [
            "stage20-legacy-aware",
            "stage20-legacy-naive",
            "stage20-legacy-offset",
            "stage20-legacy-missing",
            "stage20-legacy-null",
            "stage20-legacy-invalid",
        ]
        for project_id in account_a_ids:
            self._create(self.client_a, project_id)
        self._create(self.client_b, "stage20-legacy-other")

        self._rewrite_raw_time(
            "stage20-legacy-aware",
            updated_at="2024-01-03T08:00:00+08:00",
        )
        self._rewrite_raw_time(
            "stage20-legacy-naive",
            updated_at="2024-01-03T00:00:00",
        )
        self._rewrite_raw_time(
            "stage20-legacy-offset",
            updated_at="2024-01-02T23:00:00-01:00",
        )
        self._rewrite_raw_time("stage20-legacy-missing")
        self._rewrite_raw_time("stage20-legacy-null", updated_at=None)
        self._rewrite_raw_time("stage20-legacy-invalid", updated_at="not-a-time")

        paths = [self.projects._project_path(project_id) for project_id in account_a_ids]
        raw_before = {path.name: path.read_bytes() for path in paths}

        first = self.client_a.get("/novel/projects")
        self.assertEqual(first.status_code, 200, first.text)
        first_ids = [item["project_id"] for item in first.json()["projects"]]
        self.assertEqual(first_ids[:3], [
            "stage20-legacy-offset",
            "stage20-legacy-naive",
            "stage20-legacy-aware",
        ])
        self.assertEqual(set(first_ids), set(account_a_ids))

        second = self.client_a.get("/novel/projects")
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(
            [item["project_id"] for item in second.json()["projects"]],
            first_ids,
        )
        self.assertEqual(
            {path.name: path.read_bytes() for path in paths},
            raw_before,
        )

        other_list = self.client_b.get("/novel/projects")
        self.assertEqual(other_list.status_code, 200, other_list.text)
        self.assertEqual(
            [item["project_id"] for item in other_list.json()["projects"]],
            ["stage20-legacy-other"],
        )
        self.assertEqual(
            self.client_b.get("/novel/projects/stage20-legacy-aware").status_code,
            404,
        )

    def test_datetime_objects_and_new_project_timestamps_are_aware(self) -> None:
        generated = NovelProject(project_id="stage20-generated", title="新写入")
        self.assertIsNotNone(generated.created_at.tzinfo)
        self.assertIsNotNone(generated.updated_at.tzinfo)

        project = NovelProject(
            project_id="stage20-object-time",
            title="对象时间",
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 2, 0, 0, 0),
        )
        self.projects.save_project(project)
        raw = json.loads(
            self.projects._project_path("stage20-object-time").read_text(encoding="utf-8")
        )
        self.assertTrue(raw["created_at"].endswith("+00:00"))
        self.assertTrue(raw["updated_at"].endswith("+00:00"))
        loaded = self.projects.load_project("stage20-object-time")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.updated_at.tzinfo, timezone.utc)


if __name__ == "__main__":
    unittest.main()
