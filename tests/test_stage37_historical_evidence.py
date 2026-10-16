"""Exact rule/model evidence survives chapter partitioning; all data synthetic."""
import base64
from dataclasses import replace
import unittest
from unittest.mock import patch

import test_stage31_deconstruction as fixtures
from app.agents.llm_runtime import LLMRuntime
from schemas.deconstruction import EvidenceRef


QUOTE = "阮青将书交给温禾。"
SOURCE = "  \r\n第一章 旧书\r\n😀" + QUOTE + "\r\n第二章 晨雾\r\n温禾走过石桥。\t　\r\n"


class HistoricalEvidenceTest(unittest.TestCase):
    setUp = fixtures.Stage31DeconstructionApiTest.setUp
    _cleanup = fixtures.Stage31DeconstructionApiTest._cleanup
    _login = fixtures.Stage31DeconstructionApiTest._login
    _project = fixtures.Stage31DeconstructionApiTest._project

    def request(self, method, path, status=200, **kwargs):
        response = getattr(self.client, method)(path, **kwargs)
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def seed(self, text=SOURCE):
        self.pid = self._project("历史证据合成稿")
        self.account = self._login()
        self.base = f"/api/independent/projects/{self.pid}"
        p = self.request("post", self.base + "/chapter-previews/import", json=dict(
            filename="历史.txt", content_base64=base64.b64encode(text.encode()).decode()))["preview"]
        result = self.request("post", self.base + f"/chapter-previews/{p['preview_id']}/confirm",
                              json=dict(expected_revision=p["revision"]))
        self.version = result["version_id"]
        return result["workspace"]

    def repartition(self):
        source = self.request("get", self.base)["chapter_source"]
        p = self.request("post", self.base + "/chapter-previews/resegment", json=dict(
            expected_version_id=source["version_id"], expected_source_hash=source["source_hash"]))["preview"]
        return self.request("post", self.base + f"/chapter-previews/{p['preview_id']}/confirm",
                            json=dict(expected_revision=p["revision"]))

    def rule_report(self):
        self.request("post", self.base + "/deconstruction/rebuild", json={})
        self.deconstruction.process_background_tasks()
        doc = self.request("get", self.base + "/deconstruction")["result"]
        self.assertEqual(doc["analysis_contract_version"], "2.0")
        return doc

    def snapshot(self):
        return self.request("get", self.base + f"/versions/{self.version}/source")["snapshot"]

    def evidence(self, doc, ref):
        return self.request("get", self.base + f"/deconstruction/evidence/{ref['evidence_id']}?document_id={doc['document_id']}")

    @staticmethod
    def exact(content, ref):
        return content.encode("utf-16-le")[ref["start_offset"]*2:ref["end_offset"]*2].decode("utf-16-le")

    def assert_historical(self, response, content):
        self.assertTrue(response["historical"])
        self.assertFalse(response["source_matches_current"])
        self.assertTrue(response["chapter"]["source_available"])
        self.assertEqual(response["chapter"]["content"], content)
        self.assertEqual(response["evidence"]["excerpt"], self.exact(content, response["evidence"]))

    def model_report(self):
        claim = dict(text="阮青交出旧书。", status="fact", evidence_ids=["Q1"])
        report = dict(producer="离线合成", title="交书", scope="第一章", chapter_numbers=[1],
            findings=[dict(id="F1", title="交书", **claim)],
            characters=[dict(id="C1", name="阮青", role="主要人物", identity=claim, motivation=claim, change=claim)],
            events=[dict(id="E1", title="交书", chapter_number=1, story_time="当下", actor_ids=["C1"],
                         action=claim, consequence=claim)], relations=[], story_order=["E1"], time_note="仅知当下",
            evidence=[dict(id="Q1", chapter_number=1, quote=QUOTE)], open_questions=[])
        source = self.request("get", self.base + "/deconstruction")["source"]
        return self.request("post", self.base + "/deconstruction/import", json=dict(
            expected_source_version_id=source["version_id"], expected_source_revision=source["revision"],
            expected_source_hash=source["hash"], report=report))["result"]

    def append_chapter(self):
        c = self.request("post", self.base + "/chapters")["chapter"]
        c = self.request("put", self.base + f"/chapters/{c['chapter_id']}/draft", json=dict(
            content="第二章追加。温禾已经到达古寺。", expected_revision=c["server_revision"]))["chapter"]
        self.request("post", self.base + f"/chapters/{c['chapter_id']}/complete", json=dict(
            content=c["content"], expected_revision=c["server_revision"], idempotency_key="append"))
        self.deconstruction.process_background_tasks()

    def legacy_stripped_document(self, doc):
        """Persist the former producer/serialization shape, never real data."""
        record = self.deconstruction.store.load(self.pid)
        stored = next(d for d in record.documents if d.document_id == doc["document_id"])
        canonical_ids = {e.evidence_id for e in stored.report.evidence}
        contents = {c["chapter_id"]: c["content"] for c in self.snapshot()["chapters"]}
        changed = []
        for item in stored.evidence:
            quote = self.exact(contents[item.chapter_id], item.model_dump())
            item.excerpt = quote.strip()
            if item.evidence_id not in canonical_ids:
                prefix = contents[item.chapter_id].encode("utf-16-le")[:item.start_offset*2].decode("utf-16-le")
                item.evidence_id = self.deconstruction._slug(
                    f"evidence:{stored.document_id}:{stored.source_version_id}:{item.chapter_id}:"
                    f"{item.label}:{len(prefix)}:{item.excerpt}")
            if quote != item.excerpt:
                changed.append(item.evidence_id)
        self.assertTrue(changed)
        self.deconstruction.store.save(record)
        return stored.model_dump(mode="json"), changed

    def test_evidence_ref_roundtrip_preserves_whitespace_only_in_quote(self):
        for quote in ["  😀原文\r\n\t　", "第一章 旧书\r", "\r\n原文\u3000"]:
            ref = EvidenceRef(evidence_id=" e1 ", source_version_id="v", chapter_id="c", chapter_number=1,
                              excerpt=quote, label=" 标签 ")
            self.assertEqual(ref.excerpt, quote)
            self.assertEqual(EvidenceRef.model_validate_json(ref.model_dump_json()).excerpt, quote)
            self.assertEqual((ref.evidence_id, ref.label), ("e1", "标签"))

    def test_generated_compatibility_and_canonical_offsets_all_exact(self):
        self.seed()
        doc = self.rule_report()
        contents = {c["chapter_id"]: c["content"] for c in self.snapshot()["chapters"]}
        self.assertTrue(any(e["excerpt"] != e["excerpt"].strip() for e in doc["evidence"]))
        for ref in doc["evidence"]:
            self.assertEqual(ref["excerpt"], self.exact(contents[ref["chapter_id"]], ref))
        canonical = {e["evidence_id"]: e for e in doc["report"]["evidence"] if e["granularity"] == "span"}
        for ref in doc["evidence"]:
            if ref["evidence_id"] in canonical:
                for key in ("excerpt", "start_offset", "end_offset"):
                    self.assertEqual(ref[key], canonical[ref["evidence_id"]][key])

    def test_all_new_rule_evidence_http_readable_after_partition(self):
        self.seed()
        with patch.object(LLMRuntime, "structured", side_effect=AssertionError("unexpected paid call")):
            doc = self.rule_report()
            contents = {c["chapter_id"]: c["content"] for c in self.snapshot()["chapters"]}
            self.repartition()
            for ref in doc["evidence"]:
                self.assert_historical(self.evidence(doc, ref), contents[ref["chapter_id"]])

    def test_persisted_legacy_strips_recover_exactly_without_rewriting_records(self):
        self.seed()
        doc, changed = self.legacy_stripped_document(self.rule_report())
        self.repartition()
        contents = {c["chapter_id"]: c["content"] for c in self.snapshot()["chapters"]}
        independent_before = self.independent.store._path(self.pid).read_bytes()
        reports_before = self.deconstruction.store._path(self.pid).read_bytes()
        recovered = []
        for ref in doc["evidence"]:
            linked = self.evidence(doc, ref)
            self.assert_historical(linked, contents[ref["chapter_id"]])
            if linked["evidence"]["excerpt"] != ref["excerpt"]:
                recovered.append(ref["evidence_id"])
        self.assertCountEqual(recovered, changed)
        self.assertEqual(self.independent.store._path(self.pid).read_bytes(), independent_before)
        self.assertEqual(self.deconstruction.store._path(self.pid).read_bytes(), reports_before)

    def test_legacy_strip_recovery_rejects_bad_excerpt_offsets_id_and_source(self):
        self.seed()
        doc, changed = self.legacy_stripped_document(self.rule_report())
        self.repartition()
        record = self.deconstruction.store.load(self.pid)
        stored = next(d for d in record.documents if d.document_id == doc["document_id"])
        old = self.deconstruction._historical_source(self.pid, self.account, self.version)
        for ref in [e for e in stored.evidence if e.evidence_id in changed]:
            self.assertIsNotNone(self.deconstruction._verified_evidence(old, stored, ref))
            mutations = [dict(excerpt=ref.excerpt + "假"), dict(end_offset=ref.end_offset+1),
                         dict(start_offset=ref.start_offset+1), dict(evidence_id="unknown"),
                         dict(source_hash="0"*64), dict(source_revision=ref.source_revision+1),
                         dict(document_id="other"), dict(chapter_id="other"), dict(chapter_number=999)]
            for update in mutations:
                with self.subTest(ref=ref.evidence_id, update=update):
                    self.assertIsNone(self.deconstruction._verified_evidence(old, stored, ref.model_copy(update=update)))
        bad_source = replace(old, source_hash="0"*64)
        self.assertIsNone(self.deconstruction._verified_evidence(bad_source, stored, stored.evidence[0]))

    def test_canonical_recovery_validates_report_against_frozen_source(self):
        self.seed()
        doc, changed = self.legacy_stripped_document(self.rule_report())
        self.repartition()
        record = self.deconstruction.store.load(self.pid)
        stored = next(d for d in record.documents if d.document_id == doc["document_id"])
        ref = next(e for e in stored.evidence if e.evidence_id in changed and e.evidence_id.startswith("d32_"))
        canonical = next(e for e in stored.report.evidence if e.evidence_id == ref.evidence_id)
        canonical.excerpt = canonical.excerpt.replace("章", "回")
        self.deconstruction.store.save(record)
        result = self.evidence(doc, ref.model_dump())
        self.assertFalse(result["chapter"]["source_available"])
        self.assertIsNone(result["chapter"]["content"])

    def test_scoped_model_append_then_partition_uses_old_scope_hash(self):
        self.seed("第一章 旧书\r\n😀" + QUOTE + "\r\n")
        doc = self.model_report()
        original = self.snapshot()["chapters"][0]
        self.append_chapter()
        self.assertTrue(self.evidence(doc, doc["evidence"][0])["source_matches_current"])
        self.assertNotEqual(self.snapshot()["source_hash"], doc["source_hash"])
        result = self.repartition()
        self.assertNotEqual(result["workspace"]["active_version"]["chapters"][0]["chapter_id"], original["chapter_id"])
        self.assert_historical(self.evidence(doc, doc["evidence"][0]), original["content"])

    def test_scope_hash_title_content_and_chapter_identity_tampering_rejected(self):
        self.seed("第一章 旧书\r\n😀" + QUOTE + "\r\n")
        doc = self.model_report()
        self.append_chapter()
        self.repartition()
        record = self.deconstruction.store.load(self.pid)
        stored = next(d for d in record.documents if d.document_id == doc["document_id"])
        ref = stored.evidence[0]
        old = self.deconstruction._historical_source(self.pid, self.account, self.version)
        for scope_hash in ("", "0"*64):
            self.assertIsNone(self.deconstruction._verified_evidence(old, stored.model_copy(update=dict(scope_hash=scope_hash)), ref))
        for field, value in [("content", old.chapters[0].content + "变更"), ("title", "新章名"),
                             ("chapter_id", "same-number-different-id"), ("chapter_number", 7)]:
            altered = replace(old, chapters=(replace(old.chapters[0], **{field: value}), *old.chapters[1:]))
            self.assertIsNone(self.deconstruction._verified_evidence(altered, stored, ref))
        for field, value in [("version_id", "other"), ("project_id", "other"), ("account_id", "other")]:
            self.assertIsNone(self.deconstruction._verified_evidence(replace(old, **{field: value}), stored, ref))

    def test_scoped_history_rejects_changed_old_text_even_if_quote_survives(self):
        self.seed("第一章 旧书\r\n😀" + QUOTE + "\r\n")
        doc = self.model_report()
        self.append_chapter()
        self.repartition()
        record = self.independent.store.load(self.pid)
        old = next(v for v in record.versions if v.version_id == self.version)
        old.chapters[0].formal_content += "引文之外的变更。"
        self.independent.store.save(record)
        result = self.evidence(doc, doc["evidence"][0])
        self.assertTrue(result["historical"])
        self.assertFalse(result["chapter"]["source_available"])
        self.assertIsNone(result["chapter"]["content"])

    def test_non_scoped_history_still_requires_full_source_hash(self):
        self.seed()
        doc = self.rule_report()
        self.repartition()
        record = self.independent.store.load(self.pid)
        old = next(v for v in record.versions if v.version_id == self.version)
        old.chapters[1].formal_content += "第二章变更。"
        self.independent.store.save(record)
        ref = next(e for e in doc["evidence"] if e["chapter_number"] == 1)
        result = self.evidence(doc, ref)
        self.assertFalse(result["chapter"]["source_available"])
        self.assertIsNone(result["chapter"]["content"])

    def test_model_history_requires_requested_document_and_account(self):
        self.seed("第一章 旧书\r\n😀" + QUOTE + "\r\n")
        doc = self.model_report()
        self.append_chapter()
        self.repartition()
        self.request("get", self.base + "/deconstruction/evidence/Q1?document_id=other", 404)
        self._login("unrelated-evidence@example.com")
        self.request("get", self.base + f"/deconstruction/evidence/Q1?document_id={doc['document_id']}", 404)
