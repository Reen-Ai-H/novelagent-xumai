"""Sparse, explicitly versioned reports; synthetic source and fake HTTP only."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from pydantic import TypeAdapter, ValidationError

from app import deconstruction_routes
from app.agents.deconstruction_model import source_report_messages
from app.core.analysis_grounding import GroundedReport, PreviewGroundedReport, bind_preview_selections
from app.core.book_analysis import BookAnalysis
from app.core.report_pipeline import ReportDraft, object_hash, validate_draft
from app.core.source_report import (
    SOURCE_REPORT_WIRE, SOURCE_REPORT_V2_WIRE, SOURCE_REPORT_V3_WIRE,
    SourceReportDraft, SourceReportDraftV2, SourceReportDraftV3, _legacy_projection,
    apply_source_revision, prepare_source_draft, report_wire, source_report_model,
    source_response_model, source_target_hashes, validate_source_candidate, validate_source_review,
)
from schemas.analysis_report import AnalysisImport, AnalysisReport, AnalysisReportV2, Character, PublicAnalysisReport
from schemas.deconstruction import DeconstructionDocument, DeconstructionProjectRecord, DeconstructionResponse
from stage38_report_fixtures import acceptance
from stage38_source_report_fixtures import source_case
import test_stage38_source_report_api as api
import test_stage37_historical_evidence as historical
from test_stage37_preview_capacity import wire_bound


def sparse_case(*, nulls=True):
    draft, bank, texts, binding = source_case()
    draft["schema_version"] = "2"
    if nulls:
        for person in draft["characters"]:
            person.update(motivation=None, change=None)
    return draft, bank, texts, binding["source_directory"]["entries"]


def with_background():
    _, _, texts, _ = source_case()
    texts = {**texts, 1: "程伯把旧信递给陈姨，" + texts[1]}
    draft, bank, texts, binding = source_case(texts=texts)
    draft["schema_version"] = "2"
    draft["participants"] = [dict(id="Cheng", name="程伯", name_source_ids=["C1P001"]),
                             dict(id="Chen", name="陈姨", name_source_ids=["C1P001"])]
    return draft, bank, texts, binding["source_directory"]["entries"]


class SourceV3ContractTest(unittest.TestCase):
    def setUp(self):
        self.draft, self.bank, self.texts, self.entries = sparse_case()

    def validate(self, value):
        return validate_source_candidate(value, self.entries, self.bank, self.texts,
                                         producer="synthetic", wire=SOURCE_REPORT_V3_WIRE)

    def test_only_explicit_v3_allows_required_nulls_for_both_importance_classes(self):
        before = deepcopy(self.draft)
        normalized, report = self.validate(self.draft)
        self.assertEqual(normalized, before)
        self.assertIs(type(report), AnalysisReportV2)
        self.assertEqual(report.schema_version, "2")
        self.assertEqual([p.importance for p in report.characters], ["main", "support"])
        for person in report.characters:
            self.assertIsNone(person.motivation)
            self.assertIsNone(person.change)
            self.assertTrue(person.identity.evidence_ids)
        self.assertEqual(self.draft, before)

    def test_missing_nullable_keys_and_empty_or_malformed_claims_are_rejected(self):
        for field in ("motivation", "change"):
            for invalid in ("missing", {}, "", "null", [], False, 0, {"text": "尚不明确"}):
                with self.subTest(field=field, invalid=invalid):
                    bad = deepcopy(self.draft)
                    if invalid == "missing":
                        del bad["characters"][0][field]
                    else:
                        bad["characters"][0][field] = invalid
                    with self.assertRaises(ValidationError):
                        self.validate(bad)

    def test_identity_still_requires_complete_nonempty_sourced_claim(self):
        for invalid in (None, {}, "", {"text": "姓名有据"}):
            with self.subTest(identity=invalid):
                bad = deepcopy(self.draft)
                bad["characters"][0]["identity"] = invalid
                with self.assertRaises(ValidationError):
                    self.validate(bad)
        for field, value in (("source_ids", []), ("source_ids", ["C9P001"]),
                             ("subject_id", "Missing"), ("subject_id", "null"), ("text", "")):
            with self.subTest(field=field, value=value):
                bad = deepcopy(self.draft)
                bad["characters"][0]["identity"][field] = value
                with self.assertRaises(ValueError):
                    self.validate(bad)

    def test_nonnull_analysis_retains_all_source_holder_status_and_phase_gates(self):
        for field in ("motivation", "change"):
            for key, value in (("source_ids", ["C9P001"]), ("source_ids", []),
                               ("subject_id", "Missing"), ("status", "planned"), ("phase", "fact")):
                with self.subTest(field=field, defect=key):
                    bad = deepcopy(self.draft)
                    bad["characters"][0][field] = deepcopy(bad["characters"][0]["identity"])
                    bad["characters"][0][field][key] = value
                    with self.assertRaises(ValueError):
                        self.validate(bad)

    def test_public_version_is_discriminated_and_never_inferred_from_nulls(self):
        report = self.validate(self.draft)[1].model_dump(mode="json")
        self.assertIs(type(AnalysisImport.model_validate(dict(report=report), strict=True).report), AnalysisReportV2)
        for version in ("1", "3", "", None, 2, False):
            with self.subTest(version=version):
                bad = {**report, "schema_version": version}
                with self.assertRaises(ValidationError):
                    TypeAdapter(PublicAnalysisReport).validate_python(bad, strict=True)
        del report["schema_version"]
        with self.assertRaises(ValidationError):
            AnalysisImport.model_validate(dict(report=report), strict=True)
        legacy = self.validate(sparse_case(nulls=False)[0])[1].model_dump(mode="json")
        legacy.pop("schema_version")
        self.assertIs(type(AnalysisImport.model_validate(dict(report=legacy), strict=True).report), AnalysisReport)

    def test_old_source_legacy_generation_and_preview_remain_strict(self):
        old = {**self.draft, "schema_version": "1"}
        for wire in (SOURCE_REPORT_WIRE, SOURCE_REPORT_V2_WIRE):
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                source_report_model(wire).model_validate(old, strict=True)
        projected = _legacy_projection(old, self.entries)
        with self.assertRaises(ValidationError):
            validate_draft(projected, self.bank, self.texts, producer="synthetic")
        public = self.validate(self.draft)[1].model_dump(mode="json")
        public["schema_version"] = "1"
        grounded = deepcopy(public)
        grounded.pop("producer")
        grounded["evidence"] = [dict(id=e["id"], source_id=e["id"]) for e in public["evidence"]]
        preview = deepcopy(grounded)
        for event in preview["events"]:
            event.pop("chapter_number")
            event.pop("chapter_end")
        for model, payload in ((AnalysisReport, public), (GroundedReport, grounded), (PreviewGroundedReport, preview)):
            with self.subTest(model=model.__name__), self.assertRaises(ValidationError) as caught:
                model.model_validate(payload, strict=True)
            paths = {tuple(e["loc"]) for e in caught.exception.errors(include_input=False)}
            self.assertIn(("characters", 0, "motivation"), paths)
            self.assertIn(("characters", 0, "change"), paths)
        with self.assertRaises(ValidationError):
            Character.model_validate(public["characters"][0], strict=True)
        with self.assertRaises(ValidationError):
            bind_preview_selections(preview, self.bank, self.texts, producer="synthetic")

    def test_old_schema_snapshots_are_identical_including_defaults_and_descriptions(self):
        # Snapshots measured in the untouched initial source-only copy.
        hashes = {
            Character: "e647b9a1b7ffc89b1e0482d1cfe7ed16364acdbb03faaa8503f3a1b46d3736a5",
            AnalysisReport: "b1b877a935ce4ae51951543092a489900b9e957cdec6f2afb447ae9a9c4ef1ce",
            GroundedReport: "cce521ec2c85d955a0d86e057f17fc887aab7ddffe49a8c74f1cdb50213171fc",
            PreviewGroundedReport: "e21ab1d5cb01fef9171da16a7581fbac3fed7a4a44aa7fd2870c0341654bcda4",
            ReportDraft: "dba4bd612ddbf72624bd09ecf7759965df36f73e072c57ddd6e372409e7328ce",
            SourceReportDraft: "bf4f806e8cca76c484c0b5c99c87680258d2c18b21ce325101cf473e2c9fe775",
            SourceReportDraftV2: "149cf1311e88ca98c26956ffbb8dac00205e3084eabde0ec2312d880f21e87c5",
        }
        for model, expected in hashes.items():
            with self.subTest(model=model.__name__):
                self.assertEqual(object_hash(model.model_json_schema()), expected)

    def test_unknown_private_wire_and_public_projection_versions_reject(self):
        self.assertIs(source_report_model(SOURCE_REPORT_V3_WIRE), SourceReportDraftV3)
        for version in ("source-report-v4", "source-report-v0", "", 3):
            with self.subTest(version=version):
                with self.assertRaises(ValueError):
                    source_report_model(version)
                with self.assertRaises(ValueError):
                    report_wire(dict(report_wire_version=version))
        with self.assertRaises(ValueError):
            validate_draft({}, self.bank, self.texts, producer="synthetic", schema_version="3")
        with self.assertRaises(ValueError):
            bind_preview_selections({}, self.bank, self.texts, producer="synthetic", schema_version="3")

    def test_repair_guard_is_per_call_and_uses_the_same_v3_schema(self):
        first = source_response_model(SOURCE_REPORT_V3_WIRE)
        second = source_response_model(SOURCE_REPORT_V3_WIRE)
        self.assertIsNot(first, second)
        self.assertEqual(first.model_json_schema(), SourceReportDraftV3.model_json_schema())
        invalid = {**sparse_case(nulls=False)[0], "unexpected": True}
        with self.assertRaises(ValidationError):
            first.model_validate(invalid, strict=True)
        with self.assertRaises(ValidationError):
            first.model_validate(self.draft, strict=True)
        second.model_validate(self.draft, strict=True)
        for wire in (SOURCE_REPORT_WIRE, SOURCE_REPORT_V2_WIRE):
            self.assertIs(source_response_model(wire), source_report_model(wire))

    def test_participants_name_declaration_or_text_mention_is_not_claim_use(self):
        draft, bank, texts, entries = with_background()
        draft["characters"][0]["identity"]["text"] += "程伯与陈姨也出现在原文。"
        before = deepcopy(draft)
        frozen, diagnostics = prepare_source_draft(draft, entries, bank, texts,
            producer="synthetic", wire=SOURCE_REPORT_V3_WIRE)
        self.assertEqual(frozen, before)
        self.assertEqual([(d["code"], d["targets"]) for d in diagnostics],
                         [("unused_participant", ["participants/Cheng"]), ("unused_participant", ["participants/Chen"])])
        with self.assertRaisesRegex(ValueError, "实际引用"):
            validate_source_candidate(frozen, entries, bank, texts, producer="synthetic", wire=SOURCE_REPORT_V3_WIRE)
        self.assertEqual(draft, before)

    def test_real_claim_subject_and_object_use_both_background_individuals(self):
        draft, bank, texts, entries = with_background()
        draft["events"][0]["sub_events"].append(dict(title="递信", text="程伯把旧信递给陈姨。",
            status="fact", source_ids=["C1P001"], subject_id="Cheng", object_id="Chen", kind="action", phase="actual"))
        frozen, diagnostics = prepare_source_draft(draft, entries, bank, texts,
            producer="synthetic", wire=SOURCE_REPORT_V3_WIRE)
        self.assertEqual(diagnostics, [])
        self.assertEqual(frozen["participants"], draft["participants"])
        validate_source_candidate(frozen, entries, bank, texts, producer="synthetic", wire=SOURCE_REPORT_V3_WIRE)

    def test_same_name_participants_keep_distinct_ids_and_each_requires_use(self):
        draft, bank, texts, entries = with_background()
        draft["participants"][1]["name"] = "程伯"
        draft["events"][0]["action"].update(object_id="Cheng")
        _, diagnostics = prepare_source_draft(draft, entries, bank, texts,
            producer="synthetic", wire=SOURCE_REPORT_V3_WIRE)
        self.assertEqual([d["targets"] for d in diagnostics], [["participants/Chen"]])
        draft["events"][0]["consequence"].update(object_id="Chen")
        frozen, _ = validate_source_candidate(draft, entries, bank, texts,
            producer="synthetic", wire=SOURCE_REPORT_V3_WIRE)
        self.assertEqual([p["id"] for p in frozen["participants"]], ["Cheng", "Chen"])
        self.assertEqual([p["name"] for p in frozen["participants"]], ["程伯", "程伯"])

    def test_unused_diagnostics_are_bounded_and_never_silently_pruned(self):
        draft, bank, texts, entries = with_background()
        draft["participants"] = [dict(id=f"P{i}", name="程伯", name_source_ids=["C1P001"]) for i in range(13)]
        before = deepcopy(draft)
        with self.assertRaisesRegex(ValueError, "诊断边界"):
            prepare_source_draft(draft, entries, bank, texts, producer="synthetic", wire=SOURCE_REPORT_V3_WIRE)
        self.assertEqual(draft, before)
        old = {**draft, "schema_version": "1"}
        # Historical v1/v2 intentionally retain their original acceptance set.
        for wire in (SOURCE_REPORT_WIRE, SOURCE_REPORT_V2_WIRE):
            validate_source_candidate(old, entries, bank, texts, producer="synthetic", wire=wire)

    def test_null_analysis_action_refs_and_literal_null_ref_still_reject(self):
        for ref in ("Lin.motivation", "Lin.change", None):
            with self.subTest(ref=ref):
                bad = deepcopy(self.draft)
                bad["character_relations"] = [dict(from_id="Lin", to_id="Xu", label="核对",
                    text="共同核对。", status="fact", source_ids=["C1P001"], action_ref=ref)]
                with self.assertRaises(ValueError):
                    self.validate(bad)
                if ref is not None:
                    _, diagnostics = prepare_source_draft(bad, self.entries, self.bank, self.texts,
                        producer="synthetic", wire=SOURCE_REPORT_V3_WIRE)
                    self.assertIn("character_action", [d["code"] for d in diagnostics])

    def test_sourced_claim_to_null_revision_binds_old_value_and_retains_raw(self):
        draft = sparse_case(nulls=False)[0]
        person = deepcopy(draft["characters"][0])
        person["motivation"] = None
        raw = dict(decision="revise", draft_hash=object_hash(draft), changes=[dict(
            target="characters/Lin", before_hash=source_target_hashes(draft)["characters/Lin"],
            replacement=person, text="当前材料仅记行动，未交代动机。", source_ids=["C1P001"])])
        before = deepcopy(raw)
        review = validate_source_review(raw, draft, self.entries, self.bank, self.texts, wire=SOURCE_REPORT_V3_WIRE)
        revised = apply_source_revision(review, draft, self.entries, self.bank, self.texts,
            producer="synthetic", wire=SOURCE_REPORT_V3_WIRE)
        self.assertIsNone(revised["characters"][0]["motivation"])
        self.assertIsNotNone(draft["characters"][0]["motivation"])
        self.assertEqual(raw, before)
        for field, value in (("before_hash", object_hash(person)), ("source_ids", ["C9P001"])):
            bad = deepcopy(raw)
            bad["changes"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                r = validate_source_review(bad, draft, self.entries, self.bank, self.texts, wire=SOURCE_REPORT_V3_WIRE)
                apply_source_revision(r, draft, self.entries, self.bank, self.texts,
                    producer="synthetic", wire=SOURCE_REPORT_V3_WIRE)

    def test_sparse_revision_keeps_eight_target_and_twelve_kib_limits(self):
        changes = [dict(target=f"open_questions/{i}", before_hash=None, replacement={"value": "需核对的事项"},
                        text="按同一原文核对。", source_ids=["C1P001"]) for i in range(8)]
        raw = dict(decision="revise", draft_hash=object_hash(self.draft), changes=changes)
        review = validate_source_review(raw, self.draft, self.entries, self.bank, self.texts, wire=SOURCE_REPORT_V3_WIRE)
        self.assertEqual(len(review.changes), 8)
        with self.assertRaises(ValidationError):
            validate_source_review({**raw, "changes": changes + [{**changes[-1], "target": "open_questions/8"}]},
                self.draft, self.entries, self.bank, self.texts, wire=SOURCE_REPORT_V3_WIRE)
        large = deepcopy(raw)
        large["changes"][0]["replacement"]["value"] = "字" * 4096
        with self.assertRaisesRegex(ValueError, "12KiB"):
            validate_source_review(large, self.draft, self.entries, self.bank, self.texts, wire=SOURCE_REPORT_V3_WIRE)

    def test_v3_prompts_are_independent_compact_and_preserve_complete_untrusted_source(self):
        chapters = [dict(chapter_number=n, title="合成章节", content=text) for n, text in self.texts.items()]
        old = source_report_messages(chapters, self.bank, self.entries, stage="draft", wire=SOURCE_REPORT_V2_WIRE)
        for stage in ("draft", "review", "verify"):
            context = {} if stage == "draft" else dict(draft=self.draft, diagnostics=[])
            if stage == "verify":
                context.update(original=self.draft, revision=dict(changes=[]))
            messages = source_report_messages(chapters, self.bank, self.entries, stage=stage,
                wire=SOURCE_REPORT_V3_WIRE, **context)
            system = messages[0]["content"]
            for rule in ("source-report-v3", "motivation/change", "identity", "未交代", "subject_id/object_id",
                         "不凑数组上限", "同名", "不可信材料", "有源修订", "终审"):
                self.assertIn(rule, system)
            self.assertNotIn("source-report-v1", system)
            self.assertNotIn("source-report-v2", system)
            for person in self.draft["characters"]:
                self.assertNotIn(person["name"], system)
            material = json.loads(messages[1]["content"].split("\n", 1)[1])
            self.assertEqual(["".join(s["text"] for s in c["segments"]) for c in material["chapters"]], list(self.texts.values()))
            if stage != "draft":
                self.assertIn("借null删仍成立的事实", system)
                self.assertEqual(material["draft_hash"], object_hash(self.draft))
            else:
                self.assertLess(len(system), len(old[0]["content"]))


class SourceV3ApiTest(unittest.TestCase):
    def case(self, *, nulls=True, bulk=False):
        case = api.SourceReportApiTest("runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.prepare(6 if bulk else 2, bulk=bulk)
        if nulls:
            for person in case.draft["characters"]:
                person.update(motivation=None, change=None)
        return case

    def packet(self, call):
        return json.loads(call["messages"][1]["content"].split("\n", 1)[1])

    def null_revision(self, case):
        draft = case.job()["draft"]
        person = deepcopy(draft["characters"][0])
        person.update(motivation=None, change=None)
        return dict(decision="revise", draft_hash=object_hash(draft), changes=[dict(
            target="characters/Lin", before_hash=source_target_hashes(draft)["characters/Lin"],
            replacement=person, text="仅有行动记载，未交代动机及变化。", source_ids=["C1P001"])])

    def test_nulls_and_insights_survive_start_import_disk_reread_guide_and_export_reimport(self):
        case = self.case(bulk=True)
        insight = deepcopy(case.draft["characters"][0]["identity"])
        case.draft["characters"][0]["insights"] = [insight]  # real raw omits optional title
        before = deepcopy(case.draft)
        case.start(); final = case.wait()
        self.assertEqual((final["status"], final["total"]), ("completed", 2), final)
        job = case.job()
        self.assertEqual(job["report_wire_version"], SOURCE_REPORT_V3_WIRE)
        self.assertEqual(job["draft_response"], before)
        self.assertNotIn("title", job["draft_response"]["characters"][0]["insights"][0])
        for key in ("draft_response", "review_response"):
            self.assertEqual(json.loads(job[key + "_text"]), job[key])
        state = case.client.get(case.url).json()
        DeconstructionResponse.model_validate(state)
        self.assertEqual(state["required_engine_revision"], None)
        for envelope in (state["result"], state["document"], state["active_run"], state["history"][-1]):
            self.assertEqual(envelope["analysis_contract_version"], "model.2")
        report = state["result"]["report"]
        self.assertEqual(report["schema_version"], "2")
        self.assertIsNone(report["characters"][0]["motivation"])
        self.assertIsNone(report["characters"][0]["change"])
        self.assertEqual(report["characters"][0]["insights"][0]["title"], "补充信息")
        self.assertEqual(report["characters"][0]["insights"][0]["text"], insight["text"])
        record = case.deconstruction.store.load(case.project)
        reread = DeconstructionProjectRecord.model_validate_json(record.model_dump_json())
        stored = next(d for d in reread.documents if d.document_id == final["document_id"])
        self.assertIs(type(stored.report), AnalysisReportV2)
        self.assertEqual(stored.report.model_dump(mode="json"), report)
        guide = case.client.get(case.url + "/guide").json()
        self.assertTrue(guide["complete"])
        stage = guide["characters"][0]["stages"][0]
        self.assertIsNone(stage["motivation"])
        self.assertIsNone(stage["change"])
        self.assertTrue(stage["insights"])
        exported = json.loads(AnalysisImport(**case.body, report=stored.report).model_dump_json())
        imported = case.client.post(case.url + "/import", json=exported)
        self.assertEqual(imported.status_code, 200, imported.text)
        self.assertEqual(imported.json()["result"]["document_id"], final["document_id"])
        self.assertEqual(imported.json()["result"]["report"], report)
        self.assertEqual(len(case.calls), 2)
        for ref in state["result"]["evidence"]:
            linked = case.client.get(case.url + "/evidence/" + ref["evidence_id"],
                params=dict(document_id=final["document_id"]))
            self.assertEqual(linked.status_code, 200, linked.text)
            self.assertTrue(linked.json()["source_matches_current"])
        self.assertEqual(case.independent.store.load(case.project).model_dump(mode="json"), case.old_author)

    def test_mixed_schema_guide_preserves_old_claims_and_new_null_stages(self):
        case = self.case()
        for n in (1, 2):
            draft, bank, texts, binding = source_case(texts={n: case.texts[n]})
            wire = SOURCE_REPORT_WIRE if n == 1 else SOURCE_REPORT_V3_WIRE
            if n == 2:
                draft["schema_version"] = "2"
                for person in draft["characters"]:
                    person.update(motivation=None, change=None)
            report = validate_source_candidate(draft, binding["source_directory"]["entries"], bank, texts,
                producer="synthetic", wire=wire)[1]
            response = case.client.post(case.url + "/import", json=AnalysisImport(**case.body, report=report).model_dump(mode="json"))
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["result"]["analysis_contract_version"], f"model.{n}")
        guide = case.client.get(case.url + "/guide").json()
        self.assertTrue(guide["complete"])
        self.assertEqual(len(guide["characters"]), 2)
        for character in guide["characters"]:
            self.assertEqual([s["scope_start"] for s in character["stages"]], [1, 2])
            self.assertIsNotNone(character["stages"][0]["motivation"])
            self.assertIsNone(character["stages"][1]["motivation"])
        self.assertEqual(case.calls, [])

    def test_public_schema1_or_unknown_tags_reject_null_import_and_preserve_old_report(self):
        case = self.case()
        draft, bank, texts, binding = source_case(texts=case.texts)
        draft["schema_version"] = "2"
        draft["characters"][0].update(motivation=None, change=None)
        report = validate_source_candidate(draft, binding["source_directory"]["entries"], bank, texts,
            producer="synthetic", wire=SOURCE_REPORT_V3_WIRE)[1].model_dump(mode="json")
        for version in ("1", "3", "model.2", 2, None):
            with self.subTest(version=version):
                response = case.client.post(case.url + "/import", json=dict(**case.body, report={**report, "schema_version": version}))
                self.assertEqual(response.status_code, 422, response.text)
                case.unchanged()

    def test_envelopes_cannot_relabel_schema2_as_model1_or_missing_version(self):
        case = self.case()
        case.start(); self.assertEqual(case.wait()["status"], "completed")
        record = case.deconstruction.store.load(case.project).model_dump(mode="json")
        document = next(d for d in record["documents"] if d["document_id"] == case.job()["document_id"])
        for version in ("model.1", "model.3", "1.0", None):
            with self.subTest(version=version):
                bad = deepcopy(document)
                if version is None:
                    del bad["analysis_contract_version"]
                else:
                    bad["analysis_contract_version"] = version
                with self.assertRaises(ValidationError):
                    DeconstructionDocument.model_validate(bad)
        bad = {**document, "report": None}
        with self.assertRaises(ValidationError):
            DeconstructionDocument.model_validate(bad)
        state = case.client.get(case.url).json()
        for field in ("active_run", "result", "document"):
            bad = deepcopy(state)
            bad[field]["analysis_contract_version"] = "model.1"
            with self.subTest(field=field), self.assertRaises(ValidationError):
                DeconstructionResponse.model_validate(bad)

    def test_unused_background_reaches_review_but_accept_cannot_adopt_or_delete_it(self):
        case = self.case()
        case.draft["participants"] = [dict(id="Background", name="林客", name_source_ids=["C1P001"])]
        before = deepcopy(case.draft)
        case.start(); final = case.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "report_evidence_invalid"), final)
        self.assertEqual(len(case.calls), 2)
        self.assertEqual(case.job()["draft"], before)
        self.assertEqual(self.packet(case.calls[1])["diagnostics"][0]["code"], "unused_participant")
        self.assertNotIn("approved_hash", case.job())
        case.unchanged()

    def test_unused_background_requires_explicit_sourced_retraction_and_verify(self):
        case = self.case()
        case.draft["participants"] = [dict(id="Background", name="林客", name_source_ids=["C1P001"])]
        def revision():
            draft = case.job()["draft"]
            return dict(decision="revise", draft_hash=object_hash(draft), changes=[dict(
                target="participants/Background", before_hash=source_target_hashes(draft)["participants/Background"],
                replacement=None, text="该条是同一人物的重复声明，且未被主张引用。", source_ids=["C1P001"])])
        case.scripted([lambda: case.draft, revision, lambda: acceptance(case.job()["revised"])])
        case.start(); final = case.wait()
        self.assertEqual((final["status"], final["total"]), ("completed", 3), final)
        self.assertEqual(case.job()["draft"]["participants"], case.draft["participants"])
        self.assertEqual(case.job()["revised"]["participants"], [])
        self.assertEqual(self.packet(case.calls[2])["previous_objects"]["participants/Background"], case.draft["participants"][0])
        self.assertEqual(len(case.calls), 3)

    def test_real_claim_to_null_revision_retains_old_values_reasons_raw_and_hashes(self):
        case = self.case(nulls=False)
        case.scripted([lambda: case.draft, lambda: self.null_revision(case), lambda: acceptance(case.job()["revised"])])
        case.start(); final = case.wait()
        self.assertEqual((final["status"], final["total"]), ("completed", 3), final)
        job = case.job()
        self.assertIsNotNone(job["draft"]["characters"][0]["motivation"])
        self.assertIsNone(job["revised"]["characters"][0]["motivation"])
        packet = self.packet(case.calls[2])
        self.assertEqual(packet["previous_objects"]["characters/Lin"], job["draft"]["characters"][0])
        self.assertEqual(packet["revision"], job["review_response"])
        self.assertEqual(job["review_response"]["changes"][0]["before_hash"], object_hash(job["draft"]["characters"][0]))
        self.assertEqual(job["approved_hash"], object_hash(job["revised"]))
        for key in ("draft_response", "review_response", "verification_response"):
            self.assertEqual(json.loads(job[key + "_text"]), job[key])
        self.assertEqual(len(case.calls), 3)

    def test_verify_blocks_null_used_to_hide_real_facts_and_keeps_old_report(self):
        case = self.case(nulls=False)
        def blocked():
            return dict(decision="blocked", draft_hash=object_hash(case.job()["revised"]),
                issues=[dict(text="原文交代了该动机，不能借null撤回。", source_ids=["C1P001"])])
        case.scripted([lambda: case.draft, lambda: self.null_revision(case), blocked])
        case.start(); final = case.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "report_source_blocked"), final)
        self.assertEqual(len(case.calls), 3)
        self.assertIsNotNone(case.job()["draft"]["characters"][0]["motivation"])
        case.unchanged()

    def test_format_repair_cannot_clear_complete_claim_to_null(self):
        case = self.case(nulls=False)
        first = {**deepcopy(case.draft), "unexpected": "结构错误"}
        cleared = deepcopy(case.draft)
        cleared["characters"][0].update(motivation=None, change=None)
        case.scripted([first, cleared])
        case.start(); final = case.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "provider_bad_json"), final)
        self.assertEqual(len(case.calls), 2)
        self.assertNotIn("draft", case.job())
        self.assertNotIn("review_response", case.job())
        self.assertEqual(case.job()["budget"]["calls"], 2)
        records = json.loads(case.deconstruction.model_budget.path.read_text())["records"]
        self.assertEqual(len(records), 2)
        self.assertTrue(all(r["status"] == "settled" for r in records))
        case.unchanged()

    def test_format_repair_cannot_clear_sourced_claim_with_missing_action_annotation(self):
        case = self.case(nulls=False)
        first = deepcopy(case.draft)
        del first["characters"][0]["motivation"]["phase"]
        cleared = deepcopy(case.draft)
        cleared["characters"][0]["motivation"] = None
        case.scripted([first, cleared])
        case.start(); final = case.wait()
        self.assertEqual(final["error_code"], "provider_bad_json", final)
        self.assertEqual(len(case.calls), 2)
        self.assertNotIn("draft", case.job())
        case.unchanged()

    def test_format_repair_cannot_move_null_between_distinct_same_name_people(self):
        case = self.case(nulls=False)
        case.draft["characters"][1]["name"] = case.draft["characters"][0]["name"]
        case.draft["characters"][1]["motivation"] = None
        first = {**deepcopy(case.draft), "unexpected": True}
        cleared = deepcopy(case.draft)
        cleared["characters"][0]["motivation"] = None
        cleared["characters"][1]["motivation"] = deepcopy(cleared["characters"][1]["identity"])
        case.scripted([first, cleared])
        case.start(); final = case.wait()
        self.assertEqual(final["error_code"], "provider_bad_json", final)
        self.assertEqual(len(case.calls), 2)
        self.assertNotIn("draft", case.job())
        case.unchanged()

    def test_schema2_scope_evidence_survives_append_and_partition_without_rebinding(self):
        case = historical.HistoricalEvidenceTest("runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.seed("第一章 旧书\r\n😀" + historical.QUOTE + "\r\n")
        original_report = case.model_report()["report"]
        report = deepcopy(original_report)
        report["schema_version"] = "2"
        report["characters"][0].update(motivation=None, change=None)
        source = case.request("get", case.base + "/deconstruction")["source"]
        document = case.request("post", case.base + "/deconstruction/import", json=dict(
            expected_source_version_id=source["version_id"], expected_source_revision=source["revision"],
            expected_source_hash=source["hash"], report=report))["result"]
        self.assertEqual(document["analysis_contract_version"], "model.2")
        original = case.snapshot()["chapters"][0]
        case.append_chapter()
        self.assertTrue(case.evidence(document, document["evidence"][0])["source_matches_current"])
        case.repartition()
        case.assert_historical(case.evidence(document, document["evidence"][0]), original["content"])
        stored = next(d for d in case.deconstruction.store.load(case.pid).documents if d.document_id == document["document_id"])
        old_source = case.deconstruction._historical_source(case.pid, case.account, case.version)
        self.assertIsNone(case.deconstruction._verified_evidence(old_source, stored.model_copy(update=dict(scope_hash="0" * 64)), stored.evidence[0]))
        self.assertIsNone(case.deconstruction._verified_evidence(replace(old_source, account_id="another-account"), stored, stored.evidence[0]))
        self.assertEqual(stored.report.model_dump(mode="json"), report)
        self.assertEqual(original_report["schema_version"], "1")

    def test_null_draft_can_use_one_structural_repair_without_fabricating_claims(self):
        case = self.case()
        invalid = {**deepcopy(case.draft), "unexpected": True}
        case.scripted([invalid, lambda: case.draft, lambda: acceptance(case.job()["draft"])])
        case.start(); final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(case.calls), 3)
        self.assertEqual(json.loads(json.loads(case.calls[1]["messages"][-1]["content"])["untrusted_previous_output"]), invalid)
        self.assertIsNone(case.job()["draft"]["characters"][0]["motivation"])

    def test_six_actual_http_keep_caps_full_candidate_and_two_budget_reservations(self):
        case = self.case(bulk=True)
        case.scripted([{"unexpected": "草稿" * 300}, lambda: case.draft,
                       {"unexpected": "审查" * 300}, case.revised_reply,
                       {"unexpected": "终审" * 300}, lambda: acceptance(case.job()["revised"])])
        case.start(); final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual([c["max_completion_tokens"] for c in case.calls], [24576, 24576, 8192, 8192, 4096, 4096])
        records = json.loads(case.deconstruction.model_budget.path.read_text())["records"]
        for i, (call, holds, record) in enumerate(zip(case.calls, case.holds, records, strict=True)):
            for ledger in holds:
                self.assertAlmostEqual(ledger["reserved_cny"], wire_bound(call), places=12)
            self.assertAlmostEqual(record["reserved_cny"], wire_bound(call), places=12)
            if i % 2:
                self.assertGreater(record["reserved_cny"], records[i - 1]["reserved_cny"])
        self.assertEqual(case.job()["budget"]["calls"], 6)

    def test_null_draft_cached_raw_resume_does_not_repeat_http(self):
        case = self.case()
        original = case.runner._update_running
        def stop(job, values, **kwargs):
            if "draft" in values:
                import asyncio
                raise asyncio.CancelledError()
            return original(job, values, **kwargs)
        with patch.object(case.runner, "_update_running", side_effect=stop):
            case.start(); self.assertEqual(case.wait()["status"], "paused")
        before = deepcopy(case.job())
        recovered = BookAnalysis(case.deconstruction, runtime_factory=case.factory)
        with patch.object(deconstruction_routes, "book_analysis", recovered):
            case.start(); final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(case.calls), 2)
        self.assertEqual(case.job()["draft_response_text"], before["draft_response_text"])
        self.assertEqual(case.job()["source_directory"], before["source_directory"])

    def reject_cache(self, change, *, stage="review"):
        case = self.case(nulls=False)
        if stage == "verify":
            case.scripted([lambda: case.draft, lambda: self.null_revision(case), lambda: acceptance(case.job()["revised"])])
        with case.checkpoint(stage):
            case.start(); self.assertEqual(case.wait()["status"], "paused")
        job = case.job()
        count = len(case.calls)
        change(job)
        case.runner.save(job)
        case.start(); final = case.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "report_evidence_invalid"), final)
        self.assertEqual(len(case.calls), count)
        case.unchanged()

    def test_v3_missing_raw_provenance_is_not_reconstructed_or_resent(self):
        self.reject_cache(lambda j: j.pop("draft_response_text"))

    def test_v3_cache_chapter_bool_and_float_are_type_sensitive(self):
        for value in (True, 1.0):
            with self.subTest(value=value):
                self.reject_cache(lambda j: j["draft_response"]["chapter_numbers"].__setitem__(0, value))

    def test_v3_frozen_claim_cannot_be_silently_cleared_on_resume(self):
        self.reject_cache(lambda j: j["draft"]["characters"][0].__setitem__("motivation", None))

    def test_v3_revision_and_review_raw_remain_bound_before_verify(self):
        for defect in ("raw", "value"):
            def change(job):
                if defect == "raw":
                    job.pop("review_response_text")
                else:
                    job["revised"]["characters"][0]["identity"]["text"] = "另一身份"
            with self.subTest(defect=defect):
                self.reject_cache(change, stage="verify")

    def test_v3_review_and_verify_cached_chapter_types_remain_strict(self):
        self.reject_cache(lambda j: j["review_response"]["checked_chapters"].__setitem__(0, True), stage="adopt")
        def corrupt_verification(job):
            value = acceptance(job["revised"])
            job["verification_response_text"] = json.dumps(value, ensure_ascii=False)
            job["verification_response"] = deepcopy(value)
            job["verification_response"]["checked_chapters"][0] = True
        self.reject_cache(corrupt_verification, stage="verify")

    def test_v3_actual_structured_data_mismatch_is_rejected_before_freeze(self):
        case = self.case()
        original = case.runner._call
        async def corrupt(*args, **kwargs):
            answer = await original(*args, **kwargs)
            data = deepcopy(answer.data)
            data["chapter_numbers"][0] = True
            return replace(answer, data=data)
        with patch.object(case.runner, "_call", side_effect=corrupt):
            case.start(); final = case.wait()
        self.assertEqual(final["error_code"], "report_evidence_invalid", final)
        self.assertEqual(len(case.calls), 1)
        self.assertNotIn("draft", case.job())
        case.unchanged()

    def test_v3_unknown_http_result_stays_paused_and_never_resends(self):
        case = self.case()
        case.scripted(hook=case.timeout_on(2))
        case.assert_unknown_transport_guard(calls=2, stage="review")
        self.assertIsNone(case.job()["draft"]["characters"][0]["motivation"])

    def test_v3_source_directory_or_wire_tamper_rejects_before_next_http(self):
        for defect in ("directory", "wire"):
            def change(job):
                if defect == "directory":
                    job["source_directory"]["entries"]["C1P001"] = job["source_directory"]["entries"]["C2P001"]
                else:
                    job["report_wire_version"] = "source-report-next"
            with self.subTest(defect=defect):
                self.reject_cache(change)

    def test_v3_cached_report_cannot_be_reinterpreted_as_old_wire(self):
        self.reject_cache(lambda j: j.__setitem__("report_wire_version", SOURCE_REPORT_V2_WIRE))
