"""Source binding and author-data safety for externally authored analysis."""
import copy
import unittest

from test_stage31_deconstruction import Stage31DeconstructionApiTest


class AnalysisImportTest(unittest.TestCase):
    setUp = Stage31DeconstructionApiTest.setUp
    _cleanup = Stage31DeconstructionApiTest._cleanup
    _login = Stage31DeconstructionApiTest._login
    _project = Stage31DeconstructionApiTest._project
    _start_and_save = Stage31DeconstructionApiTest._start_and_save
    _complete_and_process = Stage31DeconstructionApiTest._complete_and_process

    def prepare(self):
        project = self._project()
        chapter = self._start_and_save(project, "灯亮了。😀沈禾没有开门。他把钥匙交给陆川。")
        state = self._complete_and_process(project, chapter)
        self.url = f"/api/independent/projects/{project}/deconstruction"
        claim = {"text": "沈禾保留了不开门的选择。", "status": "inferred", "evidence_ids": ["Q1"]}
        report = {
            "producer": "合成测试", "title": "选择", "scope": "第一章合成片段", "chapter_numbers": [1],
            "findings": [{"id": "F1", "title": "行动中的否定", **claim}],
            "characters": [{"id": "C1", "name": "沈禾", "role": "行动者", "identity": claim, "motivation": claim, "change": claim}],
            "events": [{"id": "E1", "title": "没有开门", "chapter_number": 1, "story_time": "当下", "actor_ids": ["C1"], "action": claim, "consequence": claim}],
            "relations": [], "story_order": ["E1"], "time_note": "一个事件，无回忆。",
            "evidence": [{"id": "Q1", "chapter_number": 1, "quote": "沈禾没有开门。"}], "open_questions": [],
        }
        self.payload = {
            "expected_source_version_id": state["source"]["version_id"],
            "expected_source_revision": state["source"]["revision"],
            "expected_source_hash": state["source"]["hash"], "report": report,
        }
        return project, chapter

    def test_roundtrip_exact_utf16_and_idempotency(self):
        project, chapter = self.prepare()
        before = self.independent.store.load(project).model_dump(mode="json")
        response = self.client.post(self.url + "/import", json=self.payload)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]
        self.assertEqual(result["report"]["producer"], "合成测试")
        ref = result["evidence"][0]
        self.assertEqual(ref["start_offset"], 6)  # four BMP units plus the emoji surrogate pair
        linked = self.client.get(self.url + "/evidence/Q1")
        self.assertEqual(linked.status_code, 200, linked.text)
        again = self.client.post(self.url + "/import", json=self.payload).json()
        self.assertEqual(again["result"]["document_id"], result["document_id"])
        self.deconstruction.enqueue_for_project(project, before["account_id"])
        self.deconstruction.process_background_tasks()
        self.assertEqual(self.client.get(self.url).json()["result"]["document_id"], result["document_id"])
        self.assertEqual(self.independent.store.load(project).model_dump(mode="json"), before)

    def test_invalid_quote_and_dangling_edge_do_not_replace_result(self):
        self.prepare()
        before = self.client.get(self.url).json()["result"]["document_id"]
        bad = copy.deepcopy(self.payload)
        bad["report"]["evidence"][0]["quote"] = "沈禾打开了门。"
        self.assertEqual(self.client.post(self.url + "/import", json=bad).status_code, 422)
        bad = copy.deepcopy(self.payload)
        bad["report"]["relations"] = [{"from_id": "E1", "to_id": "missing", "kind": "causes", **bad["report"]["events"][0]["action"]}]
        self.assertEqual(self.client.post(self.url + "/import", json=bad).status_code, 422)
        self.assertEqual(self.client.get(self.url).json()["result"]["document_id"], before)

    def test_wrong_source_and_cross_account_are_rejected(self):
        self.prepare()
        bad = copy.deepcopy(self.payload)
        bad["expected_source_hash"] = "0" * 64
        self.assertEqual(self.client.post(self.url + "/import", json=bad).status_code, 409)
        self._login("another-analysis-author@example.com")
        self.assertEqual(self.client.post(self.url + "/import", json=self.payload).status_code, 404)

    def test_duplicate_identity_and_missing_time_event_rejected(self):
        self.prepare()
        bad = copy.deepcopy(self.payload)
        bad["report"]["characters"][0]["id"] = "E1"
        self.assertEqual(self.client.post(self.url + "/import", json=bad).status_code, 422)
        bad = copy.deepcopy(self.payload)
        bad["report"]["story_order"] = ["unknown"]
        self.assertEqual(self.client.post(self.url + "/import", json=bad).status_code, 422)

    def test_revised_report_evidence_resolves_active_document(self):
        self.prepare()
        first = self.client.post(self.url + "/import", json=self.payload).json()["result"]
        self.payload["report"]["findings"][0]["text"] = "新一版的解释。"
        revised = self.client.post(self.url + "/import", json=self.payload).json()["result"]
        self.assertNotEqual(first["document_id"], revised["document_id"])
        linked = self.client.get(self.url + "/evidence/Q1").json()
        self.assertEqual(linked["evidence"]["document_id"], revised["document_id"])
        self.assertTrue(linked["source_matches_current"])

    def test_portrait_evidence_and_episode_range_are_validated(self):
        self.prepare()
        report = self.payload["report"]
        report["characters"][0]["portrait"] = copy.deepcopy(report["events"][0]["action"])
        report["events"][0]["chapter_end"] = 1
        self.assertEqual(self.client.post(self.url + "/import", json=self.payload).status_code, 200)
        report["characters"][0]["portrait"]["evidence_ids"] = ["missing"]
        self.assertEqual(self.client.post(self.url + "/import", json=self.payload).status_code, 422)
        report["characters"][0]["portrait"]["evidence_ids"] = ["Q1"]
        report["events"][0]["chapter_end"] = 2
        self.assertEqual(self.client.post(self.url + "/import", json=self.payload).status_code, 422)


# Avoid rediscovering the imported fixture's tests in this module.
del Stage31DeconstructionApiTest
