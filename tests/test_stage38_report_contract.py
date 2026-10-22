from copy import deepcopy
import json
import unittest

from app.agents.deconstruction_model import report_messages
from app.core.report_pipeline import (ReportDraft, ReportReview, ReportVerification, ReviewRevise,
    MAX_REVISION_BYTES, apply_revision, canonical, object_hash, public_wire, target_hashes,
    validate_draft, validate_review)
from schemas.analysis_report import AnalysisReport
from stage38_report_fixtures import report_case, acceptance


class ReportContractTest(unittest.TestCase):
    def setUp(self):
        self.draft, self.bank, self.texts = report_case()

    def bind(self):
        return validate_draft(self.draft, self.bank, self.texts, producer="synthetic")

    def revision(self, *, target="characters/Lin", replacement=None):
        replacement = deepcopy(self.draft["characters"][0]) if replacement is None else replacement
        return dict(decision="revise", draft_hash=object_hash(self.draft), changes=[dict(
            target=target, before_hash=target_hashes(self.draft)[target], replacement=replacement,
            text="按原文纠正该项。", source_ids=[next(iter(self.bank))])])

    def apply(self, revision):
        review = validate_review(revision, self.draft, self.bank, self.texts)
        return apply_revision(review, self.draft, self.bank, self.texts, producer="synthetic")

    def test_full_scale_six_chapters_and_explicit_public_projection(self):
        self.draft, self.bank, self.texts = report_case(6, bulk=True)
        data, report = self.bind()
        self.assertGreaterEqual(sum(map(len, self.texts.values())), 21224)
        self.assertGreaterEqual(len(self.bank), 668)
        self.assertEqual(report.chapter_numbers, list(range(1, 7)))
        self.assertEqual(len(report.events), 12)
        self.assertEqual(sum(2 + len(e.sub_events) for e in report.events), 72)
        self.assertNotIn("subject_id", report.model_dump_json())
        self.assertNotIn("importance_basis", report.model_dump_json())
        for evidence in report.evidence:
            self.assertIn(evidence.quote, self.texts[evidence.chapter_number])
        self.assertEqual(data, self.draft)

    def test_source_and_each_claim_reference_stay_strict(self):
        for field in ("selector", "claim", "name", "importance", "question", "time"):
            with self.subTest(field=field):
                old = deepcopy(self.draft)
                if field == "selector": self.draft["evidence"][0]["source_id"] = "S9_" + "0" * 20
                if field == "claim": self.draft["events"][0]["action"]["evidence_ids"] = ["absent"]
                if field == "name": self.draft["characters"][0]["name_evidence_ids"] = ["absent"]
                if field == "importance": self.draft["characters"][0]["importance_basis"]["evidence_ids"] = ["absent"]
                if field == "question": self.draft["open_questions"] = ["具体未解事项。"]
                if field == "time": self.draft["time_evidence_ids"] = ["absent"]
                with self.assertRaises(ValueError): self.bind()
                self.draft = old

    def test_pronoun_concept_group_and_unprovided_alias_are_rejected(self):
        for name in ("他", "大道", "群众", "无据新名"):
            with self.subTest(name=name):
                self.draft["characters"][0]["name"] = name
                with self.assertRaises(ValueError): self.bind()
        self.draft["characters"][0]["name"] = "林客"
        self.draft["characters"][0]["aliases"] = ["虚构别名"]
        with self.assertRaises(ValueError): self.bind()

    def test_importance_is_explicit_and_role_and_identity_are_preserved(self):
        self.draft["characters"][0]["role"] = "渡口记账人"
        self.draft["characters"][1]["role"] = "验货见证者"
        _, report = self.bind()
        self.assertEqual(report.characters[0].role, "渡口记账人")
        self.assertEqual(report.characters[1].role, "验货见证者")
        self.assertEqual([p.importance for p in report.characters], ["main", "support"])
        self.assertEqual(report.characters[0].identity.text, self.draft["characters"][0]["identity"]["text"])

    def test_legacy_missing_or_null_importance_roundtrips_without_role_changes(self):
        _, report = self.bind()
        legacy = report.model_dump(mode="json")
        for person in legacy["characters"]:
            person.pop("importance")
        parsed = AnalysisReport.model_validate(legacy, strict=True)
        self.assertEqual([p.importance for p in parsed.characters], [None, None])
        self.assertEqual([p.role for p in parsed.characters], [p["role"] for p in legacy["characters"]])
        reread = AnalysisReport.model_validate_json(parsed.model_dump_json(), strict=True)
        self.assertEqual(reread, parsed)

    def test_eighty_character_role_is_not_prefixed_or_truncated(self):
        role = "原身份说明" * 16
        self.assertEqual(len(role), 80)
        self.draft["characters"][0]["role"] = role
        _, report = self.bind()
        self.assertEqual(report.characters[0].role, role)
        self.assertEqual(report.characters[0].importance, "main")
        self.draft["characters"][0]["role"] = role + "字"
        with self.assertRaises(ValueError): self.bind()

    def test_identity_prefix_is_not_a_classification_or_validation_rule(self):
        self.draft["characters"][1]["role"] = "主要人物的导师"
        _, report = self.bind()
        self.assertEqual(report.characters[1].role, "主要人物的导师")
        self.assertEqual(report.characters[1].importance, "support")
        self.draft["characters"][0]["role"] = "配角的保护者"
        _, report = self.bind()
        self.assertEqual(report.characters[0].role, "配角的保护者")
        self.assertEqual(report.characters[0].importance, "main")

    def test_new_draft_still_requires_explicit_grounded_importance(self):
        for bad in (None, "incidental", "主要人物", True):
            with self.subTest(value=bad):
                self.draft["characters"][0]["importance"] = bad
                with self.assertRaises(ValueError): self.bind()
        self.draft["characters"][0].pop("importance")
        with self.assertRaises(ValueError): self.bind()
        _, report = validate_draft(report_case()[0], self.bank, self.texts, producer="synthetic")
        public = report.model_dump(mode="json")
        public["characters"][0]["importance"] = "unrecognised"
        with self.assertRaises(ValueError): AnalysisReport.model_validate(public, strict=True)

    def test_first_second_person_cards_reject_even_when_name_occurs_in_real_source(self):
        _, _, base = report_case(1)
        for pronoun in ("我", "我们", "咱", "咱们", "俺", "俺们", "你", "你们", "您", "您们"):
            with self.subTest(pronoun=pronoun):
                texts = {1: f"林客说，{pronoun}和许守一起核对来船记录。" + base[1]}
                draft, bank, texts = report_case(texts=texts)
                person = draft["characters"][0]
                person["name"] = pronoun
                selected = {e["id"]: bank[e["source_id"]].quote for e in draft["evidence"]}
                self.assertTrue(any(pronoun in selected[q] for q in person["name_evidence_ids"]))
                with self.assertRaisesRegex(ValueError, "代词"):
                    validate_draft(draft, bank, texts, producer="synthetic")

    def test_named_first_person_narrator_and_contextual_alias_remain_valid(self):
        _, _, base = report_case(1)
        texts = {1: "我叫林客，许守叫我阿林，今天我和许守一同核对来船记录。" + base[1]}
        draft, bank, texts = report_case(texts=texts)
        draft["characters"][0].update(aliases=["阿林"], alias_basis=[dict(name="阿林", evidence_ids=["Q1_0"])])
        draft["characters"][0]["identity"]["text"] = "第一人称叙述者名为林客，也被称为阿林。"
        _, report = validate_draft(draft, bank, texts, producer="synthetic")
        self.assertEqual(report.characters[0].name, "林客")
        self.assertEqual(report.characters[0].aliases, ["阿林"])
        self.assertEqual(report.characters[0].importance, "main")
        self.assertTrue(any("我" in e.quote for e in report.evidence))

    def test_null_and_wrong_identity_cannot_be_borrowed(self):
        for subject, obj in ((None, None), ("null", "Xu"), ("Xu", None)):
            with self.subTest(subject=subject):
                self.draft["characters"][0]["identity"].update(subject_id=subject, object_id=obj)
                with self.assertRaises(ValueError): self.bind()

    def test_feeling_holder_and_directed_character_edge(self):
        self.draft["characters"][0]["motivation"].update(kind="feeling", subject_id="Lin", object_id="Xu")
        self.draft["character_relations"] = [dict(from_id="Lin", to_id="Xu", label="关注",
            text="林客关注许守。", status="fact", evidence_ids=["Q1_0"], action_ref="Lin.motivation")]
        self.bind()
        self.draft["character_relations"][0].update(from_id="Xu", to_id="Lin")
        with self.assertRaises(ValueError): self.bind()
        self.draft["characters"][0]["motivation"].update(subject_id="Xu", object_id="Lin")
        with self.assertRaises(ValueError): self.bind()

    def test_unknown_actor_and_omitted_real_actor_are_rejected(self):
        for actors in ([], ["Xu"], ["absent"]):
            with self.subTest(actors=actors):
                self.draft["events"][0]["actor_ids"] = actors
                with self.assertRaises(ValueError): self.bind()

    def test_phase_and_connection_cannot_be_hidden_by_lower_status(self):
        edge = self.draft["relations"][0]
        edge.update(kind="causes", basis="cause")
        self.bind()
        for phase in ("planned", "requested", "negated", "unknown"):
            with self.subTest(phase=phase):
                self.draft["events"][0]["action"].update(phase=phase, status="unknown")
                edge["status"] = "unknown"
                with self.assertRaises(ValueError): self.bind()

    def test_real_action_endpoint_and_known_time_order(self):
        self.draft["relations"][0]["from_action"] = self.draft["events"][1]["id"] + ".action"
        with self.assertRaises(ValueError): self.bind()
        self.draft, _, _ = report_case()
        self.draft["story_order"].reverse()
        with self.assertRaises(ValueError): self.bind()

    def test_time_cycle_rejected_without_inventing_total_chronology(self):
        self.draft["relations"] = []
        self.draft["order_constraints"] = [dict(from_action="E1a.action", to_action="E1b.action", evidence_ids=["Q1_0"]),
            dict(from_action="E1b.action", to_action="E1a.action", evidence_ids=["Q1_1"])]
        with self.assertRaises(ValueError): self.bind()
        self.draft["order_constraints"].pop()
        self.bind()

    def test_sourced_replacement_keeps_original_immutable_and_no_code_semantics(self):
        original = deepcopy(self.draft)
        revision = self.revision()
        revision["changes"][0]["replacement"]["identity"]["text"] = "按来源修正后的身份说明。"
        revised = self.apply(revision)
        self.assertEqual(self.draft, original)
        self.assertEqual(revised["characters"][0]["identity"]["text"], "按来源修正后的身份说明。")
        self.assertEqual(revised["events"], original["events"])

    def test_hash_source_total_bytes_target_and_extra_fields_reject(self):
        for defect in ("draft-hash", "object-hash", "source", "bytes", "target", "extra", "empty"):
            with self.subTest(defect=defect):
                revision = self.revision()
                change = revision["changes"][0]
                if defect == "draft-hash": revision["draft_hash"] = "0" * 64
                if defect == "object-hash": change["before_hash"] = "0" * 64
                if defect == "source": change["source_ids"] = ["S9_" + "0" * 20]
                if defect == "bytes": change["text"] = "大" * 500; change["replacement"]["unexpected"] = "X" * MAX_REVISION_BYTES
                if defect == "target": change.update(target="characters/Lin/identity", before_hash=None)
                if defect == "extra": change["replacement"]["unexpected"] = True
                if defect == "empty": revision["changes"] = []
                with self.assertRaises(ValueError): self.apply(revision)

    def test_ninth_target_and_implicit_delete_dangling_dependencies_reject(self):
        revision = self.revision()
        revision["changes"] *= 9
        with self.assertRaises(ValueError): self.apply(revision)
        revision = self.revision()
        revision["changes"][0]["replacement"] = None
        with self.assertRaises(ValueError): self.apply(revision)

    def test_final_is_bound_to_actual_revised_candidate_and_cannot_revise_again(self):
        review = self.revision()
        revised = self.apply(review)
        validate_review(acceptance(revised), revised, self.bank, self.texts, final=True)
        review["draft_hash"] = object_hash(revised)
        with self.assertRaises(ValueError): validate_review(review, revised, self.bank, self.texts, final=True)
        bad = acceptance(revised); bad["checked_chapters"] = [1]
        with self.assertRaises(ValueError): validate_review(bad, revised, self.bank, self.texts, final=True)

    def test_full_source_and_injection_remain_only_user_material(self):
        for stage in ("draft", "review", "verify"):
            context = {} if stage == "draft" else dict(draft=self.draft)
            if stage == "verify": context.update(original=self.draft, revision=self.revision())
            messages = report_messages([dict(chapter_number=n, title="合成", content=t) for n, t in self.texts.items()],
                                      self.bank, stage=stage, **context)
            material = json.loads(messages[1]["content"].split("\n", 1)[1])
            self.assertEqual(["".join(s["text"] for s in c["segments"]) for c in material["chapters"]], list(self.texts.values()))
            self.assertNotIn(self.texts[1], messages[0]["content"])
        for schema in (ReportDraft, ReportReview, ReportVerification):
            self.assertIsInstance(schema.model_json_schema(), dict)
