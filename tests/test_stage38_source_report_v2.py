"""Explicit v2 display defaults; real structured requests with synthetic HTTP.

No historical manuscript/diagnostic is loaded. Older source/legacy contracts
stay strict, and actual raw content remains distinct from normalized drafts.
"""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app import deconstruction_routes
from app.core.book_analysis import BookAnalysis
from app.core.report_pipeline import ReportDraft, object_hash, validate_draft
from app.core.source_report import (
    SOURCE_REPORT_WIRE, SOURCE_REPORT_V2_WIRE, SourceReportDraft,
    SourceReportDraftV2, _legacy_projection, apply_source_revision,
    report_wire, source_report_model, source_target_hashes,
    validate_source_candidate, validate_source_review,
)
from stage38_report_fixtures import acceptance
from stage38_source_report_fixtures import source_case
import test_stage38_source_report_api as api
from test_stage37_preview_capacity import wire_bound


def add_insight(draft):
    claim = deepcopy(draft["characters"][0]["identity"])
    draft["characters"][0]["insights"] = [claim]
    return claim


class SourceV2ContractTest(unittest.TestCase):
    def setUp(self):
        self.draft, self.bank, self.texts, binding = source_case()
        self.entries = binding["source_directory"]["entries"]
        add_insight(self.draft)

    def normalized(self):
        return SourceReportDraftV2.model_validate(self.draft, strict=True).model_dump(mode="json")

    def revision(self, draft, replacement):
        return dict(decision="revise", draft_hash=object_hash(draft), changes=[dict(
            target="characters/Lin", before_hash=source_target_hashes(draft)["characters/Lin"],
            replacement=replacement, text="按原文保留参与验货的经历。", source_ids=["C1P001"])])

    def test_only_v2_missing_insight_title_defaults_without_mutating_facts_or_input(self):
        before = deepcopy(self.draft)
        normalized = self.normalized()
        expected = deepcopy(before)
        expected["characters"][0]["insights"][0]["title"] = "补充信息"
        self.assertEqual(normalized, expected)
        self.assertEqual(self.draft, before)
        with self.assertRaises(ValidationError):
            SourceReportDraft.model_validate(self.draft, strict=True)
        legacy = _legacy_projection(self.draft, self.entries)
        with self.assertRaises(ValidationError):
            ReportDraft.model_validate(legacy, strict=True)
        with self.assertRaises(ValidationError):
            validate_draft(legacy, self.bank, self.texts, producer="synthetic")
        actual, public = validate_source_candidate(self.draft, self.entries, self.bank, self.texts,
                                                   producer="synthetic", wire=SOURCE_REPORT_V2_WIRE)
        self.assertEqual(actual, expected)
        self.assertEqual(public.characters[0].insights[0].title, "补充信息")

    def test_provided_title_is_preserved_exactly_with_original_limits(self):
        for title in ("核对经历", "保留 内部空格", "字" * 80):
            with self.subTest(title_length=len(title)):
                self.draft["characters"][0]["insights"][0]["title"] = title
                self.assertEqual(self.normalized(), self.draft)

    def test_null_empty_long_and_nonstring_titles_do_not_trigger_default(self):
        for title in (None, "", "  ", "字" * 81, 0, False, [], {}):
            with self.subTest(title=title):
                self.draft["characters"][0]["insights"][0]["title"] = title
                before = deepcopy(self.draft)
                with self.assertRaises(ValidationError):
                    self.normalized()
                self.assertEqual(self.draft, before)

    def test_existing_shared_whitespace_normalization_is_not_redefined_by_v2(self):
        self.draft["characters"][0]["insights"][0]["title"] = " 保留原内容 "
        before = deepcopy(self.draft)
        self.assertEqual(self.normalized(), SourceReportDraft.model_validate(self.draft, strict=True).model_dump(mode="json"))
        self.assertEqual(self.normalized()["characters"][0]["insights"][0]["title"], "保留原内容")
        self.assertEqual(self.draft, before)

    def test_all_other_titles_and_every_factual_field_remain_required(self):
        base = self.normalized()
        for group in ("events", "findings"):
            with self.subTest(title_group=group):
                bad = deepcopy(base)
                del bad[group][0]["title"]
                with self.assertRaises(ValidationError):
                    SourceReportDraftV2.model_validate(bad, strict=True)
        for group in ("sub_events", "contradictions"):
            with self.subTest(detail_group=group):
                bad = deepcopy(base)
                if group == "sub_events":
                    del bad["events"][0][group][0]["title"]
                else:
                    bad[group] = [deepcopy(self.draft["characters"][0]["insights"][0])]
                with self.assertRaises(ValidationError):
                    SourceReportDraftV2.model_validate(bad, strict=True)
        for field in self.draft["characters"][0]["insights"][0]:
            with self.subTest(claim_field=field):
                bad = deepcopy(self.draft)
                del bad["characters"][0]["insights"][0][field]
                with self.assertRaises(ValidationError):
                    SourceReportDraftV2.model_validate(bad, strict=True)

    def test_v2_inherits_unique_ids_and_full_source_endpoint_time_gates(self):
        for defect in ("id", "source", "endpoint", "time"):
            with self.subTest(defect=defect):
                bad = deepcopy(self.draft)
                if defect == "id": bad["events"][0]["id"] = bad["characters"][0]["id"]
                if defect == "source": bad["characters"][0]["insights"][0]["source_ids"] = ["C9P001"]
                if defect == "endpoint": bad["characters"][0]["insights"][0]["subject_id"] = "MissingPerson"
                if defect == "time": bad["story_order"].reverse()
                with self.assertRaises(ValueError):
                    validate_source_candidate(bad, self.entries, self.bank, self.texts,
                                              producer="synthetic", wire=SOURCE_REPORT_V2_WIRE)

    def test_revision_defaults_only_under_same_v2_and_preserves_original_review(self):
        draft = self.normalized()
        replacement = deepcopy(draft["characters"][0])
        del replacement["insights"][0]["title"]
        raw = self.revision(draft, replacement)
        before = deepcopy(raw)
        review = validate_source_review(raw, draft, self.entries, self.bank, self.texts)
        revised = apply_source_revision(review, draft, self.entries, self.bank, self.texts,
                                        producer="synthetic", wire=SOURCE_REPORT_V2_WIRE)
        self.assertEqual(revised, draft)
        self.assertEqual(raw, before)
        self.assertNotIn("title", review.changes[0].replacement["insights"][0])
        with self.assertRaises(ValidationError):
            apply_source_revision(review, draft, self.entries, self.bank, self.texts,
                                  producer="synthetic", wire=SOURCE_REPORT_WIRE)

    def test_review_hash_and_before_hash_use_normalized_objects_not_raw(self):
        draft = self.normalized()
        self.assertNotEqual(object_hash(draft), object_hash(self.draft))
        with self.assertRaisesRegex(ValueError, "其他草稿"):
            validate_source_review(acceptance(self.draft), draft, self.entries, self.bank, self.texts)
        with self.assertRaisesRegex(ValueError, "规范化草稿"):
            validate_source_review(acceptance(self.draft), self.draft, self.entries, self.bank, self.texts,
                                   wire=SOURCE_REPORT_V2_WIRE)
        raw = self.revision(draft, deepcopy(draft["characters"][0]))
        raw["changes"][0]["before_hash"] = object_hash(self.draft["characters"][0])
        review = validate_source_review(raw, draft, self.entries, self.bank, self.texts)
        with self.assertRaisesRegex(ValueError, "原值哈希"):
            apply_source_revision(review, draft, self.entries, self.bank, self.texts,
                                  producer="synthetic", wire=SOURCE_REPORT_V2_WIRE)

    def test_schema_versions_only_relax_insight_display_title(self):
        self.assertIs(source_report_model(SOURCE_REPORT_WIRE), SourceReportDraft)
        self.assertIs(source_report_model(SOURCE_REPORT_V2_WIRE), SourceReportDraftV2)
        self.assertEqual(report_wire({"report_wire_version": SOURCE_REPORT_V2_WIRE}), SOURCE_REPORT_V2_WIRE)
        with self.assertRaises(ValueError): source_report_model("source-report-next")
        v1, v2 = SourceReportDraft.model_json_schema(), SourceReportDraftV2.model_json_schema()
        self.assertIn("title", v1["$defs"]["SourceDetail"]["required"])
        self.assertIn("title", v2["$defs"]["SourceDetail"]["required"])
        self.assertNotIn("title", v2["$defs"]["SourceInsight"]["required"])
        self.assertEqual(v2["$defs"]["SourceInsight"]["properties"]["title"]["default"], "补充信息")
        for name, node in v1["$defs"].items():
            if name != "SourceCharacter": self.assertEqual(node, v2["$defs"][name])
        self.assertEqual(v1["properties"].keys(), v2["properties"].keys())


class SourceV2ApiTest(unittest.TestCase):
    def case(self, *, v1=False):
        case = api.SourceReportApiTest("runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.prepare()
        if v1:
            with patch.object(case.runner, "ensure_task"):
                case.start()
            job = case.job()
            job.update(report_wire_version=SOURCE_REPORT_WIRE, status="paused", stage="queued")
            case.runner.save(job)
        return case

    def packet(self, call):
        return json.loads(call["messages"][1]["content"].split("\n", 1)[1])

    def assert_raw(self, case, key):
        self.assertEqual(json.loads(case.job()[key + "_text"]), case.job()[key])

    def test_new_job_defaults_then_reviews_normalized_draft_keeps_actual_raw_and_imports(self):
        case = self.case()
        add_insight(case.draft)
        before = deepcopy(case.draft)
        case.start()
        final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        job = case.job()
        self.assertEqual(job["report_wire_version"], SOURCE_REPORT_V2_WIRE)
        self.assertEqual(job["draft_response"], before)
        self.assertNotIn("title", job["draft_response"]["characters"][0]["insights"][0])
        self.assert_raw(case, "draft_response")
        expected = deepcopy(before)
        expected["characters"][0]["insights"][0]["title"] = "补充信息"
        self.assertEqual(job["draft"], expected)
        self.assertEqual(self.packet(case.calls[1])["draft"], expected)
        self.assertEqual(self.packet(case.calls[1])["draft_hash"], object_hash(expected))
        self.assertEqual(self.packet(case.calls[1])["target_hashes"], source_target_hashes(expected))
        self.assertEqual(job["approved_hash"], object_hash(expected))
        report = case.client.get(case.url).json()["result"]["report"]
        self.assertEqual(report["characters"][0]["insights"][0]["title"], "补充信息")
        self.assertEqual(len(case.calls), 2)
        for call in case.calls:
            system = call["messages"][0]["content"]
            for rule in ("source-report-v2", "报告实例JSON", "不返回schema定义本身", "SourceDetail", "title", "SourceInsight", "补充信息"):
                self.assertIn(rule, system)
        records = json.loads(case.deconstruction.model_budget.path.read_text())["records"]
        for call, hold, record in zip(case.calls, case.holds, records, strict=True):
            for ledger in hold: self.assertAlmostEqual(ledger["reserved_cny"], wire_bound(call), places=12)
            self.assertAlmostEqual(record["reserved_cny"], wire_bound(call), places=12)
        public = case.client.get(case.url + "/book").json()["job"]
        self.assertFalse(set(public).intersection(job_key for job_key in job if "response" in job_key))
        self.assertEqual(case.independent.store.load(case.project).model_dump(mode="json"), case.old_author)
        self.assertEqual(case.draft, before)

    def test_provided_title_and_facts_are_identical_in_raw_draft_review_and_public(self):
        case = self.case()
        add_insight(case.draft)["title"] = "原样 展示"
        before = deepcopy(case.draft)
        case.start(); final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(case.job()["draft_response"], before)
        self.assertEqual(case.job()["draft"], before)
        self.assertEqual(self.packet(case.calls[1])["draft"], before)
        self.assertEqual(case.client.get(case.url).json()["result"]["report"]["characters"][0]["insights"][0]["title"], "原样 展示")
        self.assert_raw(case, "draft_response")

    def test_unique_revision_defaults_before_verify_hash_without_mutating_review(self):
        case = self.case()
        add_insight(case.draft)
        saved = {}
        def correction():
            draft = case.job()["draft"]
            person = deepcopy(draft["characters"][0])
            person["role"] = "渡口记账人"
            del person["insights"][0]["title"]
            raw = dict(decision="revise", draft_hash=object_hash(draft), changes=[dict(
                target="characters/Lin", before_hash=source_target_hashes(draft)["characters/Lin"],
                replacement=person, text="按原文保留人物作用及经历。", source_ids=["C1P001"])])
            saved["review"] = deepcopy(raw)
            return raw
        case.scripted([lambda: case.draft, correction, lambda: acceptance(case.job()["revised"])])
        case.start(); final = case.wait()
        self.assertEqual((final["status"], final["total"]), ("completed", 3), final)
        job = case.job()
        self.assertEqual(job["review_response"], saved["review"])
        self.assertNotIn("title", job["review_response"]["changes"][0]["replacement"]["insights"][0])
        expected = deepcopy(saved["review"]["changes"][0]["replacement"])
        expected["insights"][0]["title"] = "补充信息"
        self.assertEqual(job["revised"]["characters"][0], expected)
        packet = self.packet(case.calls[2])
        self.assertEqual(packet["draft"], job["revised"])
        self.assertEqual(packet["draft_hash"], object_hash(job["revised"]))
        self.assertEqual(packet["revision"], saved["review"])
        self.assertEqual(job["approved_hash"], object_hash(job["revised"]))
        for key in ("draft_response", "review_response", "verification_response"): self.assert_raw(case, key)
        self.assertEqual(len(case.calls), 3)

    def test_same_version_cached_raw_resumes_without_a_second_draft_http(self):
        case = self.case()
        add_insight(case.draft)
        original = case.runner._update_running
        def stop_before_freeze(job, values, **kwargs):
            if "draft" in values:
                import asyncio
                raise asyncio.CancelledError()
            return original(job, values, **kwargs)
        with patch.object(case.runner, "_update_running", side_effect=stop_before_freeze):
            case.start(); self.assertEqual(case.wait()["status"], "paused")
        self.assertNotIn("draft", case.job())
        self.assert_raw(case, "draft_response")
        before = deepcopy(case.job()["draft_response"])
        recovered = BookAnalysis(case.deconstruction, runtime_factory=case.factory)
        with patch.object(deconstruction_routes, "book_analysis", recovered):
            case.start(); final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(case.calls), 2)
        self.assertEqual(case.job()["draft_response"], before)
        self.assertNotIn("title", before["characters"][0]["insights"][0])

    def reject_corrupt_cache(self, change, *, stage="review"):
        case = self.case()
        add_insight(case.draft)
        if stage == "verify":
            case.scripted([lambda: case.draft, case.revised_reply, lambda: acceptance(case.job()["revised"])])
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

    def test_v2_cached_data_without_safe_raw_text_is_not_upgraded_or_resent(self):
        self.reject_corrupt_cache(lambda job: job.pop("draft_response_text"))

    def test_v2_raw_and_cached_json_mismatch_is_rejected_before_review(self):
        def corrupt(job): job["draft_response"]["characters"][0]["insights"][0]["title"] = "补充信息"
        self.reject_corrupt_cache(corrupt)

    def test_cached_chapter_integer_cannot_be_substituted_with_boolean(self):
        def corrupt(job):
            raw = json.loads(job["draft_response_text"])
            self.assertIs(type(raw["chapter_numbers"][0]), int)
            job["draft_response"]["chapter_numbers"][0] = True
            self.assertEqual(raw, job["draft_response"])  # Python's unsafe equality.
            self.assertNotEqual(object_hash(raw), object_hash(job["draft_response"]))
        self.reject_corrupt_cache(corrupt)

    def test_cached_chapter_integer_cannot_be_substituted_with_float(self):
        def corrupt(job):
            raw = json.loads(job["draft_response_text"])
            job["draft_response"]["chapter_numbers"][0] = 1.0
            self.assertEqual(raw, job["draft_response"])
            self.assertNotEqual(object_hash(raw), object_hash(job["draft_response"]))
        self.reject_corrupt_cache(corrupt)

    def test_cached_review_checked_chapter_integer_cannot_be_boolean(self):
        def corrupt(job):
            raw = json.loads(job["review_response_text"])
            job["review_response"]["checked_chapters"][0] = True
            self.assertEqual(raw, job["review_response"])
            self.assertNotEqual(object_hash(raw), object_hash(job["review_response"]))
        self.reject_corrupt_cache(corrupt, stage="adopt")

    def test_cached_verification_integer_cannot_be_boolean(self):
        def corrupt(job):
            raw = acceptance(job["revised"])
            job["verification_response_text"] = json.dumps(raw, ensure_ascii=False)
            job["verification_response"] = deepcopy(raw)
            job["verification_response"]["checked_chapters"][0] = True
            self.assertEqual(raw, job["verification_response"])
        self.reject_corrupt_cache(corrupt, stage="verify")

    def test_actual_structured_data_boolean_mismatch_with_text_is_rejected(self):
        case = self.case()
        add_insight(case.draft)
        original = case.runner._call
        async def corrupt_data(*args, **kwargs):
            answer = await original(*args, **kwargs)
            data = deepcopy(answer.data)
            data["chapter_numbers"][0] = True
            self.assertEqual(data, answer.data)
            return replace(answer, data=data)
        with patch.object(case.runner, "_call", side_effect=corrupt_data):
            case.start(); final = case.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "report_evidence_invalid"), final)
        self.assertEqual(len(case.calls), 1)
        self.assertNotIn("draft", case.job())
        case.unchanged()

    def test_raw_cache_object_key_reordering_is_safe_but_array_order_is_not(self):
        case = self.case()
        add_insight(case.draft)
        with case.checkpoint("review"):
            case.start(); self.assertEqual(case.wait()["status"], "paused")
        job = case.job()
        raw = deepcopy(job["draft_response"])
        job["draft_response"] = dict(reversed(list(raw.items())))
        self.assertEqual(object_hash(raw), object_hash(job["draft_response"]))
        changed_order = deepcopy(raw)
        changed_order["chapter_numbers"].reverse()
        self.assertNotEqual(object_hash(raw), object_hash(changed_order))
        case.runner.save(job)
        case.start(); final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(case.calls), 2)
        self.assertEqual(case.independent.store.load(case.project).model_dump(mode="json"), case.old_author)

    def test_frozen_normalized_facts_cannot_diverge_from_actual_raw(self):
        def corrupt(job): job["draft"]["characters"][0]["role"] = "另一种身份"
        self.reject_corrupt_cache(corrupt)

    def test_v2_raw_review_missing_before_verify_is_not_reconstructed(self):
        self.reject_corrupt_cache(lambda job: job.pop("review_response_text"), stage="verify")

    def test_v2_revised_facts_cannot_diverge_before_paid_verification(self):
        def corrupt(job): job["revised"]["characters"][0]["role"] = "另一种身份"
        self.reject_corrupt_cache(corrupt, stage="verify")

    def test_v1_cached_missing_title_still_rejects_without_new_http_or_default(self):
        case = self.case(v1=True)
        add_insight(case.draft)
        job = case.job()
        job.update(stage="draft", draft_response=deepcopy(case.draft))
        case.runner.save(job)
        before = deepcopy(job["draft_response"])
        case.start(); final = case.wait()
        self.assertEqual(final["error_code"], "report_evidence_invalid")
        self.assertEqual(case.calls, [])
        self.assertEqual(case.job()["report_wire_version"], SOURCE_REPORT_WIRE)
        self.assertEqual(case.job()["draft_response"], before)
        self.assertNotIn("draft_response_text", case.job())
        case.unchanged()

    def test_v1_live_structured_remains_strict_and_does_not_get_v2_exception(self):
        case = self.case(v1=True)
        add_insight(case.draft)
        case.scripted([lambda: case.draft, lambda: case.draft])
        case.start(); final = case.wait()
        self.assertEqual(final["error_code"], "provider_bad_json")
        self.assertEqual(len(case.calls), 2)
        self.assertEqual(case.job()["report_wire_version"], SOURCE_REPORT_WIRE)
        self.assertIn("source-report-v1：人物insights", case.calls[0]["messages"][0]["content"])
        self.assertNotIn("draft", case.job())
        case.unchanged()

    def test_valid_v1_cached_response_still_resumes_without_new_raw_requirement(self):
        case = self.case(v1=True)
        add_insight(case.draft)["title"] = "核对经历"
        job = case.job()
        job.update(stage="draft", draft_response=deepcopy(case.draft))
        case.runner.save(job)
        case.scripted([lambda: acceptance(case.job()["draft"])])
        case.start(); final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(case.job()["report_wire_version"], SOURCE_REPORT_WIRE)
        self.assertEqual(len(case.calls), 1)
        self.assertEqual(case.calls[0]["max_completion_tokens"], 8192)
        self.assertFalse(any(key.endswith("_response_text") for key in case.job()))

    def test_revision_with_omitted_title_recovers_before_verify_without_repeating_http(self):
        case = self.case()
        add_insight(case.draft)
        def correction():
            reply = case.revised_reply()
            del reply["changes"][0]["replacement"]["insights"][0]["title"]
            return reply
        case.scripted([lambda: case.draft, correction, lambda: acceptance(case.job()["revised"])])
        with case.checkpoint("verify"):
            case.start(); self.assertEqual(case.wait()["status"], "paused")
        before = deepcopy(case.job())
        self.assertEqual(len(case.calls), 2)
        self.assertNotIn("title", before["review_response"]["changes"][0]["replacement"]["insights"][0])
        recovered = BookAnalysis(case.deconstruction, runtime_factory=case.factory)
        with patch.object(deconstruction_routes, "book_analysis", recovered):
            case.start(); final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(case.calls), 3)
        for key in ("draft_response", "draft_response_text", "review_response", "review_response_text", "revised"):
            self.assertEqual(case.job()[key], before[key])
        self.assertEqual(self.packet(case.calls[2])["draft_hash"], object_hash(before["revised"]))

    def test_defaulted_draft_transport_unknown_keeps_both_ledgers_and_no_resend(self):
        case = self.case()
        add_insight(case.draft)
        case.scripted(hook=case.timeout_on(2))
        case.assert_unknown_transport_guard(calls=2, stage="review")
        self.assert_raw(case, "draft_response")
        self.assertNotIn("title", case.job()["draft_response"]["characters"][0]["insights"][0])
        self.assertEqual(case.job()["draft"]["characters"][0]["insights"][0]["title"], "补充信息")

    def test_failed_v1_history_is_preserved_while_explicit_new_job_uses_v2(self):
        case = self.case(v1=True)
        old = case.job()
        add_insight(case.draft)
        old.update(status="failed", stage="draft", error_code="report_evidence_invalid", draft_response=deepcopy(case.draft))
        case.runner.save(old)
        before = deepcopy(old)
        case.start(); final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        job = case.job()
        self.assertEqual(job["report_wire_version"], SOURCE_REPORT_V2_WIRE)
        self.assertEqual(job["report_history"][-1], {key:value for key,value in before.items() if key != "report_history"})
        self.assertEqual(len(case.calls), 2)
        self.assertNotIn("title", job["report_history"][-1]["draft_response"]["characters"][0]["insights"][0])

    def test_invalid_provided_title_uses_one_existing_repair_then_rejects(self):
        case = self.case()
        add_insight(case.draft)["title"] = None
        case.scripted([lambda: case.draft, lambda: case.draft])
        case.start(); final = case.wait()
        self.assertEqual(final["error_code"], "provider_bad_json")
        self.assertEqual(len(case.calls), 2)
        self.assertNotIn("draft", case.job())
        case.unchanged()

    def test_review_cannot_accept_defaulted_title_with_invalid_source(self):
        case = self.case()
        add_insight(case.draft)["source_ids"] = ["C9P001"]
        case.start(); final = case.wait()
        self.assertEqual(final["error_code"], "report_evidence_invalid")
        self.assertEqual(len(case.calls), 2)
        self.assertIn("review_response", case.job())
        self.assertNotIn("approved_hash", case.job())
        case.unchanged()

    def test_schema_echo_then_single_legal_repair_is_instance_not_schema(self):
        case = self.case()
        add_insight(case.draft)
        case.scripted([SourceReportDraftV2.model_json_schema(), lambda: case.draft,
                       lambda: acceptance(case.job()["draft"])])
        case.start(); final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(case.calls), 3)
        self.assertNotIn("title", case.job()["draft_response"]["characters"][0]["insights"][0])
        self.assertEqual(case.job()["draft"]["characters"][0]["insights"][0]["title"], "补充信息")
