from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.deconstruction_routes as deconstruction_routes
import app.entry_routes as entry_routes
import app.independent_routes as independent_routes
import main
from app.core.ai_store import AIStore
from app.core.deconstruction_service import DeconstructionService
from app.core.deconstruction_store import DeconstructionStore
from app.core.entry_service import EntryService
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore
from app.core.account_store import AccountStore
from schemas.deconstruction import DeconstructionEvidenceResponse


class Stage31GDeconstructionContractTest(unittest.TestCase):
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

    def _login(self) -> str:
        response = self.client.post("/api/auth/email", json={"email": "stage31g@example.com"})
        self.assertEqual(response.status_code, 200)
        return response.json()["account"]["account_id"]

    def _project(self) -> str:
        self._login()
        response = self.client.post(
            "/api/library/projects",
            json={"title": "阶段31G合同测试", "mode": "independent", "brief": "验证拆解公开合同。"},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["project"]["project_id"]

    def _account_id(self) -> str:
        return self.client.get("/api/auth/session").json()["account"]["account_id"]

    def _start_save(self, project_id: str, content: str, title: str | None = None) -> dict:
        if title is None:
            started = self.client.post(
                f"/api/independent/projects/{project_id}/start",
                json={"source": "blank"},
            )
            self.assertEqual(started.status_code, 200)
            chapter = started.json()["active_version"]["chapters"][0]
        else:
            added = self.client.post(
                f"/api/independent/projects/{project_id}/chapters",
                params={"title": title},
            )
            self.assertEqual(added.status_code, 200)
            chapter = added.json()["chapter"]
        saved = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/draft",
            json={"content": content, "expected_revision": chapter["server_revision"]},
        )
        self.assertEqual(saved.status_code, 200)
        return saved.json()["chapter"]

    def _complete_without_dispatch(self, project_id: str, chapter: dict, key: str) -> None:
        account_id = self._account_id()
        self.independent.deconstruction_service = None
        self.independent.complete_chapter(
            project_id,
            account_id,
            chapter["chapter_id"],
            content=chapter["content"],
            expected_revision=chapter["server_revision"],
            idempotency_key=key,
        )
        self.independent.deconstruction_service = self.deconstruction

    def _complete_source(self) -> tuple[str, dict]:
        project_id = self._project()
        chapter = self._start_save(
            project_id,
            "\n\n  🧭人物：林舟。林舟在旧港打开门。\n\n\t雨声穿过走廊。",
        )
        self._complete_without_dispatch(project_id, chapter, "stage31g-complete-1")
        second = self._start_save(
            project_id,
            "\n  第二章 🌧️。林舟发现一封旧信。\n\n  他决定继续追查。",
            "第二章",
        )
        self._complete_without_dispatch(project_id, second, "stage31g-complete-2")
        third = self._start_save(
            project_id,
            " \n第三章。线索指向灯塔。\n\n  雾散开来。",
            "第三章",
        )
        self._complete_without_dispatch(project_id, third, "stage31g-complete-3")
        self.deconstruction.process_background_tasks()
        return project_id, chapter

    def test_timeline_normalizes_content_span_without_changing_absolute_evidence(self) -> None:
        project_id, first_chapter = self._complete_source()
        response = self.client.get(f"/api/independent/projects/{project_id}/deconstruction")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["effective_status"], "completed")
        timeline = payload["result"]["timeline"]
        self.assertGreater(len(timeline), 3)
        self.assertEqual(timeline[0]["normalized_start"], 0.0)
        self.assertEqual(timeline[-1]["normalized_end"], 100.0)

        previous_end = 0.0
        for node in timeline:
            self.assertGreaterEqual(node["normalized_start"], previous_end)
            self.assertLessEqual(node["normalized_start"], node["normalized_end"])
            self.assertLessEqual(node["normalized_end"], 100.0)
            previous_end = node["normalized_end"]

        first_node = timeline[0]
        first_ref = first_node["evidence_refs"][0]
        expected_position = first_chapter["content"].find("🧭")
        self.assertGreater(expected_position, 0)
        expected_utf16 = len(first_chapter["content"][:expected_position].encode("utf-16-le")) // 2
        self.assertEqual(first_ref["start_offset"], expected_utf16)
        self.assertEqual(first_ref["offset_unit"], "utf16_code_unit")
        self.assertEqual(first_ref["source_hash"], payload["source"]["hash"])

    def test_evidence_chapter_is_strict_public_model_and_openapi_schema(self) -> None:
        project_id, _ = self._complete_source()
        workspace = self.client.get(f"/api/independent/projects/{project_id}/deconstruction").json()
        evidence_id = workspace["result"]["evidence"][0]["evidence_id"]
        response = self.client.get(
            f"/api/independent/projects/{project_id}/deconstruction/evidence/{evidence_id}"
        )
        self.assertEqual(response.status_code, 200)
        evidence = DeconstructionEvidenceResponse.model_validate(response.json())
        self.assertEqual(type(evidence.chapter).__name__, "DeconstructionEvidenceChapter")
        self.assertEqual(
            set(evidence.chapter.model_dump()),
            {"chapter_id", "chapter_number", "title", "read_only", "source_available"},
        )

        invalid = response.json()
        invalid["chapter"]["unexpected_internal_field"] = "must be rejected"
        with self.assertRaises(ValidationError):
            DeconstructionEvidenceResponse.model_validate(invalid)

        schemas = main.app.openapi()["components"]["schemas"]
        response_schema = schemas["DeconstructionEvidenceResponse"]
        chapter_schema = response_schema["properties"]["chapter"]
        self.assertIn("$ref", chapter_schema)
        child_name = chapter_schema["$ref"].rsplit("/", 1)[-1]
        self.assertFalse(schemas[child_name].get("additionalProperties", True))


if __name__ == "__main__":
    unittest.main()
