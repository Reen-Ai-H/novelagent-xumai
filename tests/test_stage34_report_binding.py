"""Merged deterministic/model contracts and exact historical evidence lookup."""
import copy
import unittest

from test_stage32_analysis_import import AnalysisImportTest
from schemas.deconstruction import DeconstructionDocument, DeconstructionResponse


class ReportBindingTest(unittest.TestCase):
    setUp = AnalysisImportTest.setUp
    _cleanup = AnalysisImportTest._cleanup
    _login = AnalysisImportTest._login
    _project = AnalysisImportTest._project
    _start_and_save = AnalysisImportTest._start_and_save
    _complete_and_process = AnalysisImportTest._complete_and_process
    prepare = AnalysisImportTest.prepare

    def test_legacy_preview_record_upgrades_in_memory(self):
        project, _ = self.prepare()
        response = self.client.post(self.url + "/import", json=self.payload)
        self.assertEqual(response.status_code, 200, response.text)
        record = self.deconstruction.store.load(project)
        document = next(x for x in record.documents if x.report and hasattr(x.report, "producer"))
        legacy = document.model_dump(mode="json")
        legacy["analysis_contract_version"] = "1.0"
        parsed = DeconstructionDocument.model_validate(legacy)
        self.assertEqual(parsed.analysis_contract_version, "model.1")
        self.assertEqual(legacy["analysis_contract_version"], "1.0")
        DeconstructionResponse.model_validate(response.json())

    def test_document_disambiguates_repeated_evidence_ids(self):
        self.prepare()
        first = self.client.post(self.url + "/import", json=self.payload).json()["result"]
        revised = copy.deepcopy(self.payload)
        revised["report"]["findings"][0]["text"] = "第二次解读，仍指向同一引文。"
        second = self.client.post(self.url + "/import", json=revised).json()["result"]
        historical = self.client.get(self.url + "/evidence/Q1", params={"document_id": first["document_id"]})
        self.assertEqual(historical.status_code, 200, historical.text)
        self.assertEqual(historical.json()["evidence"]["document_id"], first["document_id"])
        self.assertTrue(historical.json()["historical"])
        current = self.client.get(self.url + "/evidence/Q1", params={"document_id": second["document_id"]})
        self.assertTrue(current.json()["source_matches_current"])
        self.assertEqual(self.client.get(self.url + "/evidence/Q1", params={"document_id": "unrelated"}).status_code, 404)

    def test_valid_previous_volume_keeps_exact_locate_after_append(self):
        project, _ = self.prepare()
        first = self.client.post(self.url + "/import", json=self.payload).json()["result"]
        added = self.client.post(f"/api/independent/projects/{project}/chapters").json()["chapter"]
        saved = self.client.put(f"/api/independent/projects/{project}/chapters/{added['chapter_id']}/draft",
                               json={"content": "沈禾终于开门。", "expected_revision": added["server_revision"]}).json()["chapter"]
        self.client.post(f"/api/independent/projects/{project}/chapters/{added['chapter_id']}/complete",
                         json={"content": saved["content"], "expected_revision": saved["server_revision"], "idempotency_key": "second-volume"})
        report = copy.deepcopy(self.payload["report"])
        report["chapter_numbers"] = [2]
        report["events"][0]["chapter_number"] = 2
        report["evidence"][0].update(chapter_number=2, quote="沈禾终于开门。")
        second_response = self.client.post(self.url + "/import", json={"report": report})
        self.assertEqual(second_response.status_code, 200, second_response.text)
        second = second_response.json()["result"]
        self.assertNotEqual(first["document_id"], second["document_id"])
        for document, number in ((first, 1), (second, 2)):
            response = self.client.get(self.url + "/evidence/Q1", params={"document_id": document["document_id"]})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()["source_matches_current"])
            self.assertEqual(response.json()["evidence"]["chapter_number"], number)

    def test_model_evidence_rejects_other_document_or_source(self):
        project, _ = self.prepare()
        self.client.post(self.url + "/import", json=self.payload)
        document = next(x for x in self.deconstruction.store.load(project).documents if x.analysis_contract_version == "model.1")
        for field, value in (("document_id", "other-document"), ("source_hash", "a" * 64),
                             ("source_version_id", "other-version"), ("source_revision", 999)):
            payload = document.model_dump(mode="json")
            payload["evidence"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                DeconstructionDocument.model_validate(payload)

    def test_public_model_document_rejects_other_identity(self):
        self.prepare()
        payload = self.client.post(self.url + "/import", json=self.payload).json()
        original = payload["document"]["document_id"]
        payload["document"]["document_id"] = "other-document"
        for ref in payload["document"]["evidence"]:
            self.assertEqual(ref["document_id"], original)
            ref["document_id"] = "other-document"
        with self.assertRaises(ValueError):
            DeconstructionResponse.model_validate(payload)

    def test_evidence_end_outside_chapter_is_not_current(self):
        project, _ = self.prepare()
        result = self.client.post(self.url + "/import", json=self.payload).json()["result"]
        record = self.deconstruction.store.load(project)
        document = next(x for x in record.documents if x.document_id == result["document_id"])
        document.evidence[0].end_offset = 999999
        self.deconstruction.store.save(record)
        response = self.client.get(self.url + "/evidence/Q1", params={"document_id": result["document_id"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["source_matches_current"])
        self.assertFalse(response.json()["chapter"]["source_available"])

    def test_history_keeps_model_contract_version(self):
        self.prepare()
        response = self.client.post(self.url + "/import", json=self.payload).json()
        result = response["result"]
        summary = next(x for x in response["history"] if x["document_id"] == result["document_id"])
        self.assertEqual(summary["analysis_contract_version"], "model.1")
