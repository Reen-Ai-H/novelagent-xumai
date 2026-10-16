"""Version-scoped import identity; HTTP regressions using only synthetic data."""
import copy
import hashlib
import unittest
from unittest.mock import patch

import test_stage37_historical_evidence as fixtures
from app import deconstruction_routes
from app.agents.llm_runtime import LLMRuntime
from app.core.deconstruction_service import DeconstructionService


class ReportIdentityTest(unittest.TestCase):
    setUp = fixtures.HistoricalEvidenceTest.setUp
    _cleanup = fixtures.HistoricalEvidenceTest._cleanup
    _login = fixtures.HistoricalEvidenceTest._login
    _project = fixtures.HistoricalEvidenceTest._project
    request = fixtures.HistoricalEvidenceTest.request
    seed = fixtures.HistoricalEvidenceTest.seed
    repartition = fixtures.HistoricalEvidenceTest.repartition
    snapshot = fixtures.HistoricalEvidenceTest.snapshot
    model_report = fixtures.HistoricalEvidenceTest.model_report
    append_chapter = fixtures.HistoricalEvidenceTest.append_chapter
    evidence = fixtures.HistoricalEvidenceTest.evidence
    exact = staticmethod(fixtures.HistoricalEvidenceTest.exact)
    assert_historical = fixtures.HistoricalEvidenceTest.assert_historical

    def import_payload(self, report):
        source = self.request("get", self.base + "/deconstruction")["source"]
        return dict(expected_source_version_id=source["version_id"],
                    expected_source_revision=source["revision"],
                    expected_source_hash=source["hash"], report=report)

    def reimport(self, doc):
        response = self.request("post", self.base + "/deconstruction/import",
                                json=self.import_payload(doc["report"]))
        self.assertEqual(response["status"], "completed")
        self.assertIsNotNone(response["result"])
        self.assertTrue(response["source"]["match"])
        return response["result"]

    def documents(self):
        return {d.document_id: d.model_dump(mode="json")
                for d in self.deconstruction.store.load(self.pid).documents}

    def legacy_identity(self, doc):
        """Reproduce the pre-fix ID formula in this test's disposable store."""
        record = self.deconstruction.store.load(self.pid)
        stored = next(d for d in record.documents if d.document_id == doc["document_id"])
        digest = hashlib.sha256(stored.report.model_dump_json().encode("utf-8")).hexdigest()
        legacy_id = hashlib.sha1(
            f"analysis-scope:{self.pid}:{stored.scope_start}-{stored.scope_end}:"
            f"{stored.scope_hash}:{digest}".encode("utf-8")
        ).hexdigest()[:20]
        stored.document_id = legacy_id
        for ref in stored.evidence:
            ref.document_id = legacy_id
        record.active_document_id = legacy_id
        self.deconstruction.store.save(record)
        return self.request("get", self.base + "/deconstruction")["result"]

    def assert_version_isolation(self, old):
        before = self.documents()
        old_chapters = {c["chapter_id"]: c for c in self.snapshot()["chapters"]}
        new_version = self.repartition()["version_id"]
        new_chapters = {c["chapter_id"]: c for c in self.request(
            "get", self.base + f"/versions/{new_version}/source")["snapshot"]["chapters"]}
        manuscript_before = self.independent.store._path(self.pid).read_bytes()
        with patch.object(LLMRuntime, "structured", side_effect=AssertionError("no model call")):
            current = self.reimport(old)
            self.assertNotEqual(current["document_id"], old["document_id"])
            self.assertEqual(current["source_version_id"], new_version)
            self.assertEqual(current["scope_hash"], old["scope_hash"])
            self.assertEqual(current["report"], old["report"])
            self.assertNotEqual(current["evidence"][0]["chapter_id"], old["evidence"][0]["chapter_id"])
            # Repeat after reconstructing the service to exercise persisted identity.
            self.deconstruction = DeconstructionService(independent=self.independent, store=self.deconstruction.store)
            with patch.object(deconstruction_routes, "deconstruction_service", self.deconstruction):
                for _ in range(2):
                    self.assertEqual(self.reimport(old), current)
                for ref in old["evidence"]:
                    linked = self.evidence(old, ref)
                    self.assert_historical(linked, old_chapters[ref["chapter_id"]]["content"])
                    self.assertEqual(linked["evidence"], ref)
                linked = self.evidence(current, current["evidence"][0])
                self.assertTrue(linked["source_matches_current"])
                self.assertFalse(linked["historical"])
                self.assertEqual(linked["evidence"]["document_id"], current["document_id"])
                content = new_chapters[linked["chapter"]["chapter_id"]]["content"]
                self.assertEqual(linked["evidence"]["excerpt"], self.exact(content, linked["evidence"]))
        after = self.documents()
        self.assertEqual(set(after) - set(before), {current["document_id"]})
        for document_id, saved in before.items():
            self.assertEqual(after[document_id], saved)
        self.assertEqual(self.independent.store._path(self.pid).read_bytes(), manuscript_before)

    def test_same_report_new_version_gets_new_document_without_rebinding_old_q1(self):
        self.seed()
        self.assert_version_isolation(self.model_report())

    def test_legacy_id_remains_readable_and_never_reused_by_new_version(self):
        self.seed()
        self.assert_version_isolation(self.legacy_identity(self.model_report()))

    def test_legacy_same_version_duplicate_keeps_persisted_ids_and_document(self):
        self.seed()
        old = self.legacy_identity(self.model_report())
        before = self.documents()
        for _ in range(2):
            self.assertEqual(self.reimport(old), old)
        self.assertEqual(self.documents(), before)
        self.assertEqual(self.evidence(old, old["evidence"][0])["evidence"], old["evidence"][0])

    def test_same_version_scope_idempotency_survives_append_and_other_report(self):
        self.seed("第一章 旧书\r\n😀" + fixtures.QUOTE + "\r\n")
        old = self.model_report()
        saved = self.documents()[old["document_id"]]
        self.append_chapter()
        self.assertNotEqual(self.snapshot()["source_hash"], old["source_hash"])
        self.assertEqual(self.reimport(old), old)
        self.assertTrue(self.evidence(old, old["evidence"][0])["source_matches_current"])
        changed = copy.deepcopy(old)
        changed["report"]["title"] = "同范围的另一份分析"
        other = self.reimport(changed)
        self.assertNotEqual(other["document_id"], old["document_id"])
        before = self.documents()
        self.assertEqual(self.reimport(old), old)
        self.assertEqual(self.documents(), before)
        self.assertEqual(self.documents()[old["document_id"]], saved)
        linked = self.evidence(old, old["evidence"][0])
        self.assertTrue(linked["chapter"]["source_available"])
        self.assertEqual(linked["evidence"], old["evidence"][0])

    def test_new_identity_still_rejects_stale_cas_and_nonexact_quotes_without_writes(self):
        self.seed()
        old = self.model_report()
        stale = self.import_payload(old["report"])
        self.repartition()
        current = self.import_payload(old["report"])
        wrong_version = dict(current, expected_source_version_id=old["source_version_id"])
        wrong_hash = dict(current, expected_source_hash="0" * 64)
        wrong_quote = copy.deepcopy(current)
        wrong_quote["report"]["evidence"][0]["quote"] += "不存在的引文"
        manuscript_before = self.independent.store._path(self.pid).read_bytes()
        reports_before = self.deconstruction.store._path(self.pid).read_bytes()
        for payload, status in [(stale, 409), (wrong_version, 409), (wrong_hash, 409), (wrong_quote, 422)]:
            self.request("post", self.base + "/deconstruction/import", status, json=payload)
            self.assertEqual(self.independent.store._path(self.pid).read_bytes(), manuscript_before)
            self.assertEqual(self.deconstruction.store._path(self.pid).read_bytes(), reports_before)
