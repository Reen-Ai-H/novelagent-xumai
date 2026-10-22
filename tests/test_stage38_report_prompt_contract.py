"""Prompt/schema agreement and real binding, not a model semantic-quality test.

All generated reports here are synthetic. No private manuscript or failed
candidate is repaired, embedded, or used as an accepted report fixture.
"""
from copy import deepcopy
import json
import re
from typing import get_args
import unittest

from pydantic import BaseModel, ValidationError

from app.agents.deconstruction_model import report_messages
from app.core.model_budget import estimate_structured_call_bound
from app.core.report_pipeline import (
    DraftCharacter, DraftCharacterRelation, DraftClaim, DraftRelation,
    ReportDraft, ReportReview, ReportVerification, REVIEW_MAX_TOKENS,
    VERIFY_MAX_TOKENS, apply_revision, object_hash, target_hashes,
    validate_draft, validate_review,
)
from schemas.analysis_report import Claim
from stage38_report_fixtures import acceptance, report_case
import test_stage38_report_api as api
from test_stage37_preview_capacity import wire_bound


REF_FIELDS = {"evidence_ids", "name_evidence_ids", "time_evidence_ids"}
MODEL = "mimo-v2.6-pro"


def reference_ids(value):
    if isinstance(value, dict):
        return [ref for key, item in value.items()
                for ref in (item if key in REF_FIELDS else reference_ids(item))]
    if isinstance(value, list):
        return [ref for item in value for ref in reference_ids(item)]
    return []


def remap_synthetic_evidence(draft, mapping):
    """Only the synthetic fixture's explicit, complete alias map is used."""
    result = deepcopy(draft)
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in REF_FIELDS:
                    value[key] = [mapping[ref] for ref in item]
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(result)
    for item in result["evidence"]:
        item["id"] = mapping[item["id"]]
    return result


def identity_case(count=2, *, bulk=False):
    draft, bank, texts = report_case(count, bulk=bulk)
    mapping = {item["id"]: item["source_id"] for item in draft["evidence"]}
    return remap_synthetic_evidence(draft, mapping), bank, texts


def capacity_sources(draft, bank, count=123):
    """Increase citation volume, not narrative complexity or quality claims."""
    result = deepcopy(draft)
    used = set(reference_ids(result))
    first = min(result["chapter_numbers"])
    extra = [p.id for p in bank.values() if p.chapter_number == first and p.id not in used][:count-len(used)]
    if len(used) + len(extra) != count:
        raise AssertionError("Synthetic capacity source is insufficient")
    result["evidence"].extend(dict(id=key, source_id=key) for key in extra)
    for offset in range(0, len(extra), 12):
        claim = deepcopy(result["characters"][0]["identity"])
        claim["evidence_ids"] = extra[offset:offset+12]
        result["characters"][0]["insights"].append(dict(title="汇总核对", **claim))
    return result


def messages_for(stage, draft, bank, texts):
    context = {} if stage == "draft" else dict(draft=draft)
    if stage == "verify":
        target = "findings/" + draft["findings"][0]["id"]
        context.update(original=draft, revision=dict(decision="revise", draft_hash=object_hash(draft),
            changes=[dict(target=target, before_hash=target_hashes(draft)[target],
                          replacement=deepcopy(draft["findings"][0]), text="按来源核对该项。",
                          source_ids=[draft["evidence"][0]["source_id"]])]))
    return report_messages([dict(chapter_number=n, title="合成章节", content=text) for n, text in texts.items()],
                           bank, stage=stage, **context)


def draft_claim_paths(model, prefix=""):
    def models(annotation):
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return {annotation}
        return {model for arg in get_args(annotation) for model in models(arg)}
    paths = set()
    for name, field in model.model_fields.items():
        path = prefix + name
        for nested in models(field.annotation):
            if issubclass(nested, DraftClaim):
                paths.add(path)
            else:
                paths.update(draft_claim_paths(nested, path + "."))
    return paths


class ReportPromptContractTest(unittest.TestCase):
    def setUp(self):
        self.draft, self.bank, self.texts = identity_case()

    def test_draft_claim_scope_is_exactly_the_current_schema_not_all_claims(self):
        prompt = messages_for("draft", self.draft, self.bank, self.texts)[0]["content"]
        declaration = re.search(r"DraftClaim适用字段：([^。]+)。", prompt)
        self.assertIsNotNone(declaration)
        self.assertEqual(set(declaration.group(1).split("、")), draft_claim_paths(ReportDraft))
        self.assertNotIn("所有Claim都用", prompt)
        basis = re.search(r"importance_basis只用([a-z_/]+)", prompt)
        self.assertIsNotNone(basis)
        self.assertEqual(set(basis.group(1).split("/")), set(Claim.model_fields))
        self.assertIs(DraftCharacter.model_fields["importance_basis"].annotation, Claim)

    def test_basic_importance_claim_still_rejects_all_four_action_fields(self):
        draft = deepcopy(self.draft)
        fields = ("subject_id", "object_id", "kind", "phase")
        draft["characters"][0]["importance_basis"].update({key: draft["characters"][0]["identity"][key] for key in fields})
        with self.assertRaises(ValidationError) as caught:
            ReportDraft.model_validate(draft, strict=True)
        errors = caught.exception.errors(include_input=False)
        self.assertEqual({tuple(e["loc"]) for e in errors},
                         {("characters", 0, "importance_basis", key) for key in fields})
        self.assertTrue(all(e["type"] == "extra_forbidden" for e in errors))

    def test_both_relation_types_still_reject_an_independent_id(self):
        prompt = messages_for("draft", self.draft, self.bank, self.texts)[0]["content"]
        self.assertIn("relations和character_relations不带独立id", prompt)
        for model in (DraftRelation, DraftCharacterRelation):
            self.assertNotIn("id", model.model_fields)
        for group in ("relations", "character_relations"):
            with self.subTest(group=group):
                draft = deepcopy(self.draft)
                if group == "character_relations":
                    action = draft["events"][0]["action"]
                    draft[group] = [dict(from_id=action["subject_id"], to_id=action["object_id"],
                        label="协作", text="共同核对记录。", status="fact", evidence_ids=action["evidence_ids"],
                        action_ref=draft["events"][0]["id"] + ".action")]
                validate_draft(draft, self.bank, self.texts, producer="synthetic")
                draft[group][0]["id"] = "UnexpectedRelationId"
                with self.assertRaises(ValidationError) as caught:
                    ReportDraft.model_validate(draft, strict=True)
                self.assertEqual([tuple(e["loc"]) for e in caught.exception.errors(include_input=False)], [(group, 0, "id")])

    def test_identity_id_and_complete_declaration_rules_reach_all_three_requests(self):
        for stage in ("draft", "review", "verify"):
            with self.subTest(stage=stage):
                messages = messages_for(stage, self.draft, self.bank, self.texts)
                system = messages[0]["content"]
                for rule in ("evidence.id == source_id", "每个所用来源恰好声明一次", "命中已声明的evidence.id", "已有旧EV别名"):
                    self.assertIn(rule, system)
                self.assertIn("ReportDraft内所有evidence_ids", system)
                material = json.loads(messages[1]["content"].split("\n", 1)[1])
                self.assertEqual(["".join(s["text"] for s in c["segments"]) for c in material["chapters"]], list(self.texts.values()))
                if stage != "draft":
                    review = system.split("# 独立批评与有界修订", 1)[1]
                    self.assertIn("新增evidence的id == source_id", review)
                    self.assertIn("旧EV明确映射仍兼容", review)
                    self.assertIn("issues/changes的source_ids直接选择材料中的实际source_id", review)

    def test_semantic_boundaries_reach_requests_but_do_not_prove_model_quality(self):
        rules = ("叙述顺序≠故事时间", "回忆锚", "尚未返回", "近似姓名", "跨世代同名", "同一次经历",
                 "后来", "单方领会", "情感回应", "制度利益", "报复机制", "单纯恩怨")
        for stage in ("draft", "review", "verify"):
            with self.subTest(stage=stage):
                system = messages_for(stage, self.draft, self.bank, self.texts)[0]["content"]
                for rule in rules:
                    self.assertIn(rule, system)
                if stage != "draft":
                    review = system.split("# 独立批评与有界修订", 1)[1]
                    for rule in rules[1:]:
                        self.assertIn(rule, review)
                for person in self.draft["characters"]:
                    self.assertNotIn(person["name"], system)


class ReportEvidenceIdentityTest(unittest.TestCase):
    def setUp(self):
        self.draft, self.bank, self.texts = identity_case()

    def test_complete_six_chapter_identity_ids_bind_exact_original_source(self):
        draft, bank, texts = identity_case(6, bulk=True)
        before = deepcopy(draft)
        normalized, report = validate_draft(draft, bank, texts, producer="synthetic")
        self.assertGreaterEqual(sum(map(len, texts.values())), 21224)
        self.assertGreaterEqual(len(bank), 668)
        self.assertEqual({e["id"] for e in draft["evidence"]}, set(reference_ids(draft)))
        self.assertTrue(all(e["id"] == e["source_id"] for e in draft["evidence"]))
        self.assertEqual(normalized, before)
        self.assertEqual(draft, before)
        self.assertEqual(report.chapter_numbers, list(range(1, 7)))
        for evidence in report.evidence:
            passage = bank[evidence.id]
            self.assertEqual(evidence.quote, texts[passage.chapter_number][passage.start:passage.end])
            self.assertEqual(evidence.chapter_number, passage.chapter_number)

    def test_valid_source_without_its_declaration_still_fails_no_automatic_fill(self):
        omitted = self.draft["evidence"].pop(0)["id"]
        self.assertIn(omitted, self.bank)
        self.assertIn(omitted, reference_ids(self.draft))
        ReportDraft.model_validate(self.draft, strict=True)
        before = deepcopy(self.draft)
        with self.assertRaisesRegex(ValueError, "判断引用了不存在的证据"):
            validate_draft(self.draft, self.bank, self.texts, producer="synthetic")
        self.assertEqual(self.draft, before)

    def test_declared_unknown_identity_source_still_fails_before_binding(self):
        key = "S9_" + "0" * 20
        self.assertNotIn(key, self.bank)
        self.draft["evidence"].append(dict(id=key, source_id=key))
        self.draft["findings"][0]["evidence_ids"] = [key]
        ReportDraft.model_validate(self.draft, strict=True)
        before = deepcopy(self.draft)
        with self.assertRaisesRegex(ValueError, "未提供的原文来源编号"):
            validate_draft(self.draft, self.bank, self.texts, producer="synthetic")
        self.assertEqual(self.draft, before)

    def test_legacy_ev_aliases_roundtrip_without_implicit_renaming(self):
        draft = remap_synthetic_evidence(self.draft, {e["id"]: f"EV{i}" for i, e in enumerate(self.draft["evidence"])})
        before = deepcopy(draft)
        normalized, report = validate_draft(draft, self.bank, self.texts, producer="synthetic")
        self.assertEqual(normalized, before)
        self.assertEqual([e.id for e in report.evidence], [e["id"] for e in before["evidence"]])
        self.assertTrue(all(e.id.startswith("EV") for e in report.evidence))
        self.assertEqual(draft, before)

    def test_mixing_ev_declarations_with_undeclared_s_refs_is_not_auto_guessed(self):
        original = remap_synthetic_evidence(self.draft, {e["id"]: f"EV{i}" for i, e in enumerate(self.draft["evidence"])})
        # Synthetic reproduction of the namespace error, never a repair of a
        # real failed candidate: keep EV declarations but replace all refs.
        invalid = deepcopy(self.draft)
        invalid["evidence"] = original["evidence"]
        self.assertTrue(set(reference_ids(invalid)) <= set(self.bank))
        self.assertFalse(set(reference_ids(invalid)) & {e["id"] for e in invalid["evidence"]})
        ReportDraft.model_validate(invalid, strict=True)
        before = deepcopy(invalid)
        with self.assertRaisesRegex(ValueError, "判断引用了不存在的证据"):
            validate_draft(invalid, self.bank, self.texts, producer="synthetic")
        self.assertEqual(invalid, before)

    def test_private_support_fields_also_require_a_declared_not_merely_known_source(self):
        draft, bank, texts = identity_case(bulk=True)
        missing = next(key for key in bank if key not in {e["id"] for e in draft["evidence"]})
        for field in ("name", "importance", "alias", "order", "question", "time"):
            with self.subTest(field=field):
                invalid = deepcopy(draft)
                if field == "name": invalid["characters"][0]["name_evidence_ids"] = [missing]
                if field == "importance": invalid["characters"][0]["importance_basis"]["evidence_ids"] = [missing]
                if field == "alias":
                    person = invalid["characters"][0]
                    person.update(aliases=[person["name"]], alias_basis=[dict(name=person["name"], evidence_ids=[missing])])
                if field == "order": invalid["order_constraints"] = [dict(from_action="E1a.action", to_action="E1b.action", evidence_ids=[missing])]
                if field == "question": invalid.update(open_questions=["尚有哪些记录待核？"], question_sources=[dict(index=0, evidence_ids=[missing])])
                if field == "time": invalid["time_evidence_ids"] = [missing]
                ReportDraft.model_validate(invalid, strict=True)
                before = deepcopy(invalid)
                with self.assertRaisesRegex(ValueError, "私有支持引用不存在"):
                    validate_draft(invalid, bank, texts, producer="synthetic")
                self.assertEqual(invalid, before)

    def test_revision_adds_canonical_evidence_while_preserving_legacy_ev_ids(self):
        draft, bank, texts = identity_case(bulk=True)
        draft = remap_synthetic_evidence(draft, {e["id"]: f"EV{i}" for i, e in enumerate(draft["evidence"])})
        before = deepcopy(draft)
        key = next(key for key in bank if key not in {e["source_id"] for e in draft["evidence"]})
        finding = deepcopy(draft["findings"][0]); finding["evidence_ids"] = [key]
        target = "findings/" + finding["id"]
        revision = dict(decision="revise", draft_hash=object_hash(draft), changes=[
            dict(target="evidence/" + key, before_hash=None, replacement=dict(id=key, source_id=key), text="补充该项的实际来源。", source_ids=[key]),
            dict(target=target, before_hash=target_hashes(draft)[target], replacement=finding, text="依明确声明引用来源。", source_ids=[key])])
        review = validate_review(revision, draft, bank, texts)
        revised = apply_revision(review, draft, bank, texts, producer="synthetic")
        self.assertEqual(draft, before)
        self.assertEqual(revised["evidence"][:-1], before["evidence"])
        self.assertEqual(revised["evidence"][-1], dict(id=key, source_id=key))
        validate_review(acceptance(revised), revised, bank, texts, final=True)

    def test_review_issue_uses_direct_source_even_when_draft_has_not_declared_it(self):
        draft, bank, texts = identity_case(bulk=True)
        key = next(key for key in bank if key not in {e["source_id"] for e in draft["evidence"]})
        before = deepcopy(draft)
        blocked = dict(decision="blocked", draft_hash=object_hash(draft),
                       issues=[dict(text="该处来源仍需进一步核对。", source_ids=[key])])
        review = validate_review(blocked, draft, bank, texts)
        self.assertEqual(review.issues[0].source_ids, [key])
        self.assertEqual(draft, before)


class ReportPromptCapacityTest(unittest.TestCase):
    def test_full_source_123_declarations_use_full_schema_and_unchanged_caps(self):
        draft, bank, texts = identity_case(6, bulk=True)
        draft = capacity_sources(draft, bank)
        validate_draft(draft, bank, texts, producer="synthetic")
        self.assertEqual(len(set(reference_ids(draft))), 123)
        self.assertEqual(len(draft["evidence"]), 123)
        self.assertGreater(len(json.dumps(draft["evidence"], separators=(",", ":"))), 8000)
        self.assertEqual((REVIEW_MAX_TOKENS, VERIFY_MAX_TOKENS), (8192, 4096))
        for stage, schema, cap in (("draft", ReportDraft, 24576), ("review", ReportReview, REVIEW_MAX_TOKENS),
                                   ("verify", ReportVerification, VERIFY_MAX_TOKENS)):
            with self.subTest(stage=stage):
                messages = messages_for(stage, draft, bank, texts)
                material = json.loads(messages[1]["content"].split("\n", 1)[1])
                if stage == "review":
                    self.assertEqual(sum(key.startswith("evidence/") for key in material["target_hashes"]), 123)
                tracked = [*messages, dict(role="system", content=json.dumps(schema.model_json_schema(), ensure_ascii=False))]
                bound = estimate_structured_call_bound(tracked, cap, model=MODEL, attempts=1)
                exact_bytes = sum(len(m["content"].encode()) for m in tracked)
                self.assertAlmostEqual(bound, (exact_bytes + 8192) * 3 / 1_000_000 + cap * 6 / 1_000_000, places=12)
                self.assertGreater(bound, estimate_structured_call_bound(messages, cap, model=MODEL, attempts=1))

    def synthetic_api(self):
        case = api.ReportApiTest("runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.prepare(6, bulk=True)
        mapping = {item["id"]: item["source_id"] for item in case.draft["evidence"]}
        case.draft = capacity_sources(remap_synthetic_evidence(case.draft, mapping), case.bank)
        return case

    def test_actual_transport_sends_new_rules_full_source_and_auto_imports_identity_ids(self):
        case = self.synthetic_api()
        self.assertEqual(case.start().status_code, 200)
        final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(case.calls), 2)
        self.assertEqual([c["max_completion_tokens"] for c in case.calls], [24576, 8192])
        report = case.client.get(case.url).json()["result"]["report"]
        self.assertEqual(len(report["evidence"]), 123)
        self.assertEqual({e["id"] for e in report["evidence"]}, set(reference_ids(case.draft)))
        records = json.loads(case.deconstruction.model_budget.path.read_text())["records"]
        for call, record in zip(case.calls, records, strict=True):
            self.assertIn("evidence.id == source_id", call["messages"][0]["content"])
            self.assertIn("importance_basis只用text/status/evidence_ids", call["messages"][0]["content"])
            material = json.loads(call["messages"][1]["content"].split("\n", 1)[1])
            self.assertEqual(["".join(s["text"] for s in c["segments"]) for c in material["chapters"]], list(case.texts.values()))
            self.assertAlmostEqual(record["reserved_cny"], wire_bound(call), places=12)
        self.assertEqual(case.independent.store.load(case.project).model_dump(mode="json"), case.old_author)

    def test_actual_format_repair_reserves_full_123_citation_candidate_and_schema(self):
        case = self.synthetic_api()
        invalid = {**deepcopy(case.draft), "unexpected": True}
        case.scripted([invalid, lambda: case.draft, lambda: acceptance(case.job()["draft"])])
        self.assertEqual(case.start().status_code, 200)
        self.assertEqual(case.wait()["status"], "completed")
        self.assertEqual(len(case.calls), 3)
        self.assertEqual([call["max_completion_tokens"] for call in case.calls], [24576, 24576, 8192])
        repaired = case.calls[1]
        previous = json.loads(repaired["messages"][-1]["content"])["untrusted_previous_output"]
        self.assertEqual(json.loads(previous), invalid)
        self.assertEqual(len(json.loads(previous)["evidence"]), 123)
        records = json.loads(case.deconstruction.model_budget.path.read_text())["records"]
        self.assertEqual(len(records), 3)
        self.assertGreater(records[1]["reserved_cny"], records[0]["reserved_cny"])
        for call, record in zip(case.calls, records, strict=True):
            self.assertAlmostEqual(record["reserved_cny"], wire_bound(call), places=12)
        self.assertEqual(case.independent.store.load(case.project).model_dump(mode="json"), case.old_author)
