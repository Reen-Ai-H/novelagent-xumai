"""Manager-owned black-box acceptance: real pipeline, synthetic unlabelled prose.

Fixtures describe story facts, not precomputed model answers. Services and the
analysis core are never mocked. HTTP dependency wiring uses isolated real stores.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import json
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
from schemas.deconstruction import DeconstructionResponse


NATURAL = [
    "林舟想找到失踪的姐姐，却害怕再次走进旧站。顾遥把一把缺角的铜钥匙交给林舟，说："
    "“我替你守住门，你去找她。”林舟答应与顾遥合作。钥匙为什么缺了一角？他把疑问记在心里。",
    "三年前，姐姐曾对林舟说：“缺角的铜钥匙能打开钟楼的门。”与此同时，顾遥在河岸寻找脚印。"
    "因为雨水即将冲掉脚印，顾遥决定立刻沿河追赶。",
    "林舟用那把缺角的铜钥匙打开钟楼，终于找到姐姐的信。信解释了钥匙上的缺口，先前的疑问有了答案。"
    "顾遥赶来帮助林舟，两人决定一起公开真相。林舟不再害怕旧站。钟声像一条长线，穿过雨后的街巷。",
]


class Stage32AcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="xumai32-acceptance-")
        root = Path(self.temporary.name)
        accounts = AccountStore(root / "accounts.json")
        projects = JsonProjectStore(root / "projects")
        self.independent = IndependentWorkspaceService(store=IndependentStore(root / "independent"), projects=projects)
        self.service = DeconstructionService(independent=self.independent, store=DeconstructionStore(root / "deconstruction"))
        self.independent.deconstruction_service = self.service
        entry = EntryService(accounts=accounts, projects=projects, independent=self.independent.store, ai=AIStore(root / "ai"))
        self.patchers = [patch.object(entry_routes, "account_store", accounts),
                         patch.object(entry_routes, "entry_service", entry),
                         patch.object(independent_routes, "independent_service", self.independent),
                         patch.object(deconstruction_routes, "deconstruction_service", self.service)]
        for item in self.patchers:
            item.start()
        self.client = TestClient(main.app)
        self.account_id = self.client.post("/api/auth/email", json={"email": "acceptance32@example.test"}).json()["account"]["account_id"]

    def tearDown(self):
        self.client.close()
        for item in reversed(self.patchers):
            item.stop()
        self.temporary.cleanup()

    def import_story(self, chapters):
        created = self.client.post("/api/library/projects", json={"title": "管理验收合成作品", "mode": "independent"})
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["project"]["project_id"]
        text = "\n\n".join(f"# 第{number}章\n{content}" for number, content in enumerate(chapters, 1))
        preview = self.client.post(f"/api/independent/projects/{project_id}/imports/preview",
                                   json={"filename": "synthetic.md", "content_base64": base64.b64encode(text.encode()).decode()})
        self.assertEqual(preview.status_code, 200)
        confirmed = self.client.post(f"/api/independent/projects/{project_id}/imports/{preview.json()['preview']['preview_id']}/confirm")
        self.assertEqual(confirmed.status_code, 200)
        return self.analyze_project(project_id)

    def write_story(self, chapters):
        created = self.client.post("/api/library/projects", json={"title": "逐字正文验收", "mode": "independent"})
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["project"]["project_id"]
        base = f"/api/independent/projects/{project_id}"
        started = self.client.post(base + "/start", json={"source": "blank"})
        self.assertEqual(started.status_code, 200)
        chapter = started.json()["active_version"]["chapters"][0]
        for number, content in enumerate(chapters, 1):
            if number > 1:
                added = self.client.post(base + "/chapters")
                self.assertEqual(added.status_code, 200)
                chapter = added.json()["chapter"]
            saved = self.client.put(base + f"/chapters/{chapter['chapter_id']}/draft",
                                   json={"content": content, "expected_revision": chapter["server_revision"]})
            self.assertEqual(saved.status_code, 200)
            chapter = saved.json()["chapter"]
            self.assertEqual(chapter["content"], content)
            if content.strip():
                completed = self.client.post(base + f"/chapters/{chapter['chapter_id']}/complete",
                                             json={"content": content, "expected_revision": chapter["server_revision"],
                                                   "idempotency_key": f"raw-chapter-{number}"})
                self.assertEqual(completed.status_code, 200)
        current = self.independent.workspace(project_id, self.account_id)["active_version"]
        self.assertEqual([item.content for item in current.chapters], chapters)
        self.assertEqual([item.formal_content for item in current.chapters if item.formal_content.strip()],
                         [content for content in chapters if content.strip()])
        return self.analyze_project(project_id)

    def analyze_project(self, project_id):
        before = self.independent.workspace(project_id, self.account_id)["active_version"].model_dump(mode="json")
        self.service.process_background_tasks()
        payload = self.client.get(f"/api/independent/projects/{project_id}/deconstruction").json()
        DeconstructionResponse.model_validate(payload)
        self.assertEqual(payload["effective_status"], "completed", payload.get("error"))
        self.assertEqual(self.independent.workspace(project_id, self.account_id)["active_version"].model_dump(mode="json"), before,
                         "Deconstruction must not rewrite manuscript, archive or revision")
        self.assertIsNotNone(payload["result"].get("report"), "Stage32 requires a real six-view report, not the stage31 overview")
        self.assert_report(payload, before)
        return project_id, payload, before

    def assert_report(self, payload, manuscript):
        report = payload["result"]["report"]
        self.assertEqual(report["report_version"], "2.0")
        for field in ("characters", "plot", "foreshadowing", "rhythm", "reader_experience", "technique"):
            self.assertIn(field, report)
        content = {c["chapter_id"]: c["formal_content"] for c in manuscript["chapters"] if c["formal_content"].strip()}
        evidence = {e["evidence_id"]: e for e in report["evidence"]}
        self.assertTrue(evidence)
        for ref in evidence.values():
            self.assertEqual(ref["source_hash"], payload["source"]["hash"])
            self.assertEqual(ref["source_version_id"], payload["source"]["version_id"])
            self.assertEqual(ref["source_revision"], payload["source"]["revision"])
            self.assertEqual(ref["document_id"], payload["result"]["document_id"])
            self.assertIn(ref["chapter_id"], content)
            if ref["granularity"] == "span":
                raw = content[ref["chapter_id"]].encode("utf-16-le")
                start, end = ref["start_offset"] * 2, ref["end_offset"] * 2
                self.assertTrue(0 <= start < end <= len(raw))
                self.assertEqual(raw[start:end].decode("utf-16-le"), ref["excerpt"])
                raw[:start].decode("utf-16-le")
                raw[end:].decode("utf-16-le")
        for key in ("rhythm", "reader_experience"):
            points = report[key]["items"]
            self.assertEqual(points[0]["normalized_start"], 0)
            self.assertEqual(points[-1]["normalized_end"], 100)
            self.assertTrue(all(a["normalized_end"] <= b["normalized_start"] for a, b in zip(points, points[1:])))
            self.assertTrue(any(p["epistemic_status"] != "unknown" for p in points))
        for item in report["technique"]["items"]:
            self.assertTrue(item["observation"].strip())
            self.assertTrue(item["learning_note"].strip())
            self.assertTrue(item["evidence_ids"] or item["epistemic_status"] == "unknown")
        serialized = json.dumps(payload)
        for forbidden_key in ("account_id", "private_memory", "raw_completion", "prompt", "content", "formal_content"):
            self.assertNotIn(f'"{forbidden_key}":', serialized)

    def test_natural_multiline_story_yields_supported_connected_analysis(self):
        _, payload, _ = self.import_story(NATURAL)
        report = payload["result"]["report"]
        people = {p["name"]: p for p in report["characters"]["characters"]}
        self.assertTrue({"林舟", "顾遥"} <= people.keys(), "Unlabelled natural prose must identify explicit named participants")
        for name in ("林舟", "顾遥"):
            states = [s for s in report["characters"]["states"] if s["character_id"] == people[name]["item_id"]]
            self.assertGreaterEqual(len(states), 2)
            self.assertTrue(all(s["evidence_ids"] for s in states))
        self.assertTrue(report["characters"]["relations"], "Explicit cooperation should connect the named participants")
        self.assertTrue(any(e["temporal_mode"] == "flashback" for e in report["plot"]["events"]))
        self.assertTrue(any(e["temporal_mode"] == "parallel" for e in report["plot"]["events"]))
        self.assertTrue(any(r["relation_type"] in {"causes", "enables"} for r in report["plot"]["relations"]),
                        "Explicit reason and enabled action must not collapse to mere ordering")
        self.assertTrue(any(s["status"] == "paid_off" for s in report["foreshadowing"]["states"]),
                        "The planted key's explicit later use and explanation should be traceable")

    def test_single_chapter_is_supported(self):
        self.import_story(["小雨推开门，听见屋里有人唱歌。“你还在吗？”她问。歌声停了。"])

    def test_ordinary_multichapter_without_character_markers(self):
        self.import_story(["周砚沿河走到码头，拿出一张船票。", "阿岚把绳索抛给周砚，两人一起把船拖到岸边。"])

    def test_hundred_chapter_synthetic_long_form(self):
        chapters = [f"林舟来到第{i}处驿站，记录新的路标。顾遥递给林舟一张地图。两人继续沿河寻找姐姐。" for i in range(1, 101)]
        _, payload, _ = self.import_story(chapters)
        self.assertEqual(len(payload["result"]["report"]["chapters"]), 100)

    def test_leading_and_internal_whitespace_does_not_shift_evidence(self):
        self.write_story(["  \n\n\t  林舟推开门。\n\n顾遥在屋内点灯。  ", "\n\t顾遥带着林舟走向河岸。\n"])

    def test_emoji_utf16_evidence_keeps_real_source_boundaries(self):
        self.write_story(["  🧭林舟拿起钥匙。顾遥问：“这把🔑能开哪扇门？”", "顾遥用钥匙开门，门后挂着一面🏳️‍🌈旗帜。"])

    def test_blank_chapters_do_not_create_invented_events_or_progress(self):
        _, payload, before = self.write_story(["  ", "林舟推开门。", "\n\t", "顾遥点亮灯。", ""])
        blank_ids = {item["chapter_id"] for item in before["chapters"] if not item["formal_content"].strip()}
        report = payload["result"]["report"]
        self.assertFalse(blank_ids.intersection(ref["chapter_id"] for ref in report["evidence"]))
        self.assertFalse(blank_ids.intersection(key for event in report["plot"]["events"] for key in event["chapter_ids"]))

    def test_repetition_alone_is_not_confirmed_foreshadowing_payoff(self):
        _, payload, _ = self.import_story(["林舟看见墙是蓝色的，然后离开。", "顾遥看见海是蓝色的，然后回家。"])
        paid = [s for s in payload["result"]["report"]["foreshadowing"]["states"] if s["status"] == "paid_off"]
        self.assertFalse(paid, "A shared color alone does not establish setup and payoff")

    def test_adjacent_events_are_not_asserted_as_causation(self):
        _, payload, _ = self.import_story(["林舟在院子里给花浇水。", "远处的顾遥在书店读书。"])
        causes = [r for r in payload["result"]["report"]["plot"]["relations"] if r["relation_type"] in {"causes", "enables", "prevents"}]
        self.assertFalse(causes, "Narrative adjacency alone does not establish causal edges")

    def test_retry_recreation_and_historical_evidence_preserve_source(self):
        project_id, payload, before = self.import_story(NATURAL)
        endpoint = f"/api/independent/projects/{project_id}/deconstruction"
        report_before = deepcopy(payload["result"]["report"])
        second = DeconstructionService(independent=self.independent, store=self.service.store)
        second.process_background_tasks()
        self.assertEqual(second.read(project_id, self.account_id)["result"]["report"], report_before)
        for _ in range(2):
            response = self.client.post(endpoint + "/rebuild")
            self.assertEqual(response.status_code, 200)
        self.service.process_background_tasks()
        self.assertEqual(len(self.service.store.load(project_id).documents), 1)
        chapter = before["chapters"][0]
        saved = self.client.put(f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/draft",
                               json={"content": chapter["content"] + " 作者保留的新句。", "expected_revision": chapter["server_revision"]})
        self.assertEqual(saved.status_code, 200)
        pending = self.client.get(endpoint).json()
        self.assertEqual(pending["effective_status"], "rebuild_required")
        self.assertIsNone(pending["result"])
        self.assertEqual(self.client.post(f"/api/independent/projects/{project_id}/pending-changes/resolve", json={"decision": "rebuild"}).status_code, 200)
        self.service.process_background_tasks()
        rebuilt = self.client.get(endpoint).json()
        self.assertEqual(rebuilt["effective_status"], "completed")
        self.assertNotEqual(rebuilt["source"]["hash"], payload["source"]["hash"])
        ref = report_before["evidence"][0]
        historical = self.client.get(endpoint + "/evidence/" + ref["evidence_id"])
        self.assertEqual(historical.status_code, 200)
        self.assertTrue(historical.json()["historical"])
        self.assertTrue(historical.json()["chapter"]["read_only"])
        self.assertEqual(historical.json()["evidence"]["source_hash"], payload["source"]["hash"])
        other = TestClient(main.app)
        try:
            self.assertEqual(other.get(endpoint).status_code, 401)
            self.assertEqual(other.post("/api/auth/email", json={"email": "other32@example.test"}).status_code, 200)
            self.assertEqual(other.get(endpoint).status_code, 404)
            self.assertEqual(other.get(endpoint + "/evidence/" + ref["evidence_id"]).status_code, 404)
        finally:
            other.close()


if __name__ == "__main__":
    unittest.main()
