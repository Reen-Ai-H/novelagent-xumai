"""Source-only ID validation through real structured parsing, synthetic HTTP.

No private failed candidate is loaded or repaired. Distinct background objects
have actual names in this test's uploaded source, not identical object copies.
"""
from copy import deepcopy
from itertools import combinations
import json
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.agents.llm_runtime import LLMRuntime
from app.core.report_pipeline import ReportDraft, validate_draft
from app.core.source_report import (
    SOURCE_ID_GROUPS, SOURCE_REPORT_V2_WIRE, SourceReportDraft, prepare_source_draft,
    validate_source_candidate,
)
from stage38_report_fixtures import acceptance
from stage38_source_report_fixtures import source_case
import test_stage38_source_report_api as api
from test_stage37_preview_capacity import wire_bound


COLLISION_ID = "OnlyInUntrustedCandidate"
DRAFT_GUIDANCE = (
    "findings保留少量跨人物、跨事件的综合发现，不作人物卡或事件摘要合集。"
    "人物字段写本人的身份、动机和变化，事件字段写经过、结果及关键细节。"
    "必要重复只保留各自职责所需的概括，主体、时层和阶段保持一致；"
    "重要事实及限定留在正确归属处，不为适配8目标删事实或降低确定性。"
)
REVIEW_GUIDANCE = (
    "将标题、正文、主体/对象ID所指人物、阶段和故事顺序合成完整主张，再对照原文；"
    "同一事实的跨字段副本一并核对，不能只检查正文或引用是否存在。"
)


class SourceReportIDTest(unittest.TestCase):
    def case(self, *, legacy=False):
        case = api.old.ReportApiTest("runTest") if legacy else api.SourceReportApiTest("runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        original = api.old.report_case

        def with_background_people(*args, **kwargs):
            draft, bank, texts = original(*args, **kwargs)
            if kwargs.get("texts") is None:
                texts = dict(texts)
                texts[1] = "程伯把旧信递给陈姨，林客与许守在旁核对来船记录；" + texts[1]
                return original(texts=texts)
            return draft, bank, texts

        with patch.object(api.old, "report_case", side_effect=with_background_people):
            if legacy:
                case.prepare()
            else:
                case.prepare(wire=SOURCE_REPORT_V2_WIRE)
        return case

    def pair(self, case):
        legal = deepcopy(case.draft)
        legal["participants"] = [
            dict(id=COLLISION_ID, name="程伯", name_source_ids=["C1P001"]),
            dict(id="LetterRecipient", name="陈姨", name_source_ids=["C1P001"]),
        ]
        legal["events"][0]["sub_events"].append(dict(
            title="递交旧信", text="程伯把旧信递给陈姨。", status="fact", source_ids=["C1P001"],
            subject_id=COLLISION_ID, object_id="LetterRecipient", kind="action", phase="actual"))
        bad = deepcopy(legal)
        bad["participants"][1]["id"] = COLLISION_ID
        bad["events"][0]["sub_events"][-1]["object_id"] = COLLISION_ID
        return bad, legal

    def assert_dual_accounting(self, case, caps):
        records = json.loads(case.deconstruction.model_budget.path.read_text())["records"]
        self.assertEqual(len(records), len(caps))
        self.assertEqual([call["max_completion_tokens"] for call in case.calls], caps)
        for call, hold, record in zip(case.calls, case.holds, records, strict=True):
            bound = wire_bound(call)
            self.assertAlmostEqual(record["reserved_cny"], bound, places=12)
            for ledger in hold:
                self.assertAlmostEqual(ledger["reserved_cny"], bound, places=12)
        for ledger in (case.job()["budget"], case.deconstruction.model_budget.public(api.old.MODEL)):
            self.assertEqual(ledger["calls"], len(caps))
            self.assertEqual(ledger["unknown_usage_calls"], 0)
            self.assertEqual(ledger["pending_attempts"], {})

    def test_duplicate_then_one_format_repair_review_and_import_preserves_objects_and_refs(self):
        case = self.case()
        bad, legal = self.pair(case)
        before = deepcopy(bad)
        case.scripted([bad, legal, lambda: acceptance(case.job()["draft"])])
        self.assertEqual(case.start().status_code, 200)
        final = case.wait()
        self.assertEqual((final["status"], final["stage"]), ("completed", "completed"), final)
        self.assertEqual(case.job()["draft"], legal)
        self.assertEqual(case.job()["draft_response"], legal)
        self.assertEqual(bad, before)
        self.assertEqual(len(case.job()["draft"]["participants"]), 2)
        # The *model's* synthetic reply changes only one ID and its matching
        # reference. Production code never deduplicates or rewrites either.
        expected = deepcopy(bad)
        expected["participants"][1]["id"] = "LetterRecipient"
        expected["events"][0]["sub_events"][-1]["object_id"] = "LetterRecipient"
        self.assertEqual(legal, expected)
        review = json.loads(case.calls[2]["messages"][1]["content"].split("\n", 1)[1])
        self.assertEqual(review["draft"], legal)
        self.assertEqual(review["diagnostics"], [])
        self.assertEqual(case.client.get(case.url).json()["result"]["document_id"], final["document_id"])
        self.assertEqual(case.independent.store.load(case.project).model_dump(mode="json"), case.old_author)
        self.assert_dual_accounting(case, [24576, 24576, 8192])

        repair_messages = case.calls[1]["messages"]
        trusted = "\n".join(m["content"] for m in repair_messages if m["role"] == "system")
        self.assertIn("全局唯一", trusted)
        self.assertIn("不得合并、去重、删对象", trusted)
        self.assertIn("from_action/to_action/action_ref", trusted)
        self.assertNotIn(COLLISION_ID, trusted)
        for person in legal["participants"]:
            self.assertNotIn(person["name"], trusted)
        previous = json.loads(repair_messages[-1]["content"])
        self.assertEqual(json.loads(previous["untrusted_previous_output"]), bad)
        self.assertIn("报告对象（不符合合同）", trusted)
        for call in case.calls:
            self.assertIn(DRAFT_GUIDANCE, call["messages"][0]["content"])
        self.assertIn(REVIEW_GUIDANCE, case.calls[2]["messages"][0]["content"])

    def test_second_duplicate_is_rejected_without_review_or_program_deduplication(self):
        case = self.case()
        bad, _ = self.pair(case)
        before = deepcopy(bad)
        case.scripted([bad, bad])
        case.start()
        final = case.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "provider_bad_json"))
        self.assertEqual(bad, before)
        self.assertNotIn("draft", case.job())
        self.assertNotIn("review_response", case.job())
        self.assertNotIn("approved_hash", case.job())
        self.assert_dual_accounting(case, [24576, 24576])
        case.unchanged()

    def test_all_groups_and_cross_group_id_collisions_are_strict_input_immutable(self):
        draft, _, _, _ = source_case()
        draft["participants"] = [dict(id="Background", name="程伯", name_source_ids=["C1P001"])]
        # Shape-only: no literal-source rejection is involved in these cases.
        for left, right in combinations(SOURCE_ID_GROUPS, 2):
            with self.subTest(groups=(left, right)):
                bad = deepcopy(draft)
                bad[right][0]["id"] = bad[left][0]["id"]
                before = deepcopy(bad)
                with self.assertRaises(ValidationError):
                    SourceReportDraft.model_validate(bad, strict=True)
                self.assertEqual(bad, before)
        for group in SOURCE_ID_GROUPS:
            with self.subTest(group=group):
                bad = deepcopy(draft)
                bad[group].append(deepcopy(bad[group][0]))
                before = deepcopy(bad)
                with self.assertRaises(ValidationError):
                    SourceReportDraft.model_validate(bad, strict=True)
                self.assertEqual(bad, before)

    def test_cross_group_collision_uses_only_existing_single_format_repair(self):
        case = self.case()
        case.draft["events"][0]["id"] = case.draft["characters"][0]["id"]
        case.scripted([case.draft, case.draft])
        case.start()
        final = case.wait()
        self.assertEqual(final["error_code"], "provider_bad_json")
        self.assertEqual(len(case.calls), 2)
        self.assertNotIn("review_response", case.job())
        case.unchanged()

    def test_repair_does_not_hide_deletion_with_remaining_dangling_endpoint(self):
        case = self.case()
        bad, deleted = self.pair(case)
        deleted["participants"].pop()
        case.scripted([bad, deleted, lambda: acceptance(case.job()["draft"])])
        case.start()
        final = case.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "report_evidence_invalid"))
        self.assertEqual(len(case.calls), 3)
        self.assertIn("review_response", case.job())
        self.assertNotIn("approved_hash", case.job())
        case.unchanged()

    def test_actual_transport_timeout_during_uniqueness_repair_stays_unknown_no_resend(self):
        case = self.case()
        bad, legal = self.pair(case)
        case.scripted([bad, legal], hook=case.timeout_on(2))
        case.assert_unknown_transport_guard(calls=2, stage="draft")
        self.assertNotIn("draft", case.job())

    def test_legacy_model_and_early_rejection_do_not_gain_source_only_repair(self):
        case = self.case(legacy=True)
        case.draft["events"][0]["id"] = case.draft["characters"][0]["id"]
        ReportDraft.model_validate(case.draft, strict=True)
        with self.assertRaises(ValueError):
            validate_draft(case.draft, case.bank, case.texts, producer="synthetic")
        case.start()
        final = case.wait()
        self.assertEqual(final["error_code"], "report_evidence_invalid")
        self.assertEqual(len(case.calls), 1)
        self.assertNotIn("review_response", case.job())
        case.unchanged()

    def test_source_schema_guidance_is_static_and_legacy_schema_unchanged(self):
        schema = SourceReportDraft.model_json_schema()
        self.assertIn("全局唯一", schema["description"])
        self.assertIn("事实文字、判断状态与来源编号选择", schema["description"])
        self.assertIn("同步对应的", schema["description"])
        for name in ("SourceCharacter", "SourceEvent", "SourceFinding", "SourceParticipant"):
            self.assertIn("全局唯一", schema["$defs"][name]["properties"]["id"]["description"])
        self.assertNotIn("全局唯一", json.dumps(ReportDraft.model_json_schema(), ensure_ascii=False))
        draft, _, _, _ = source_case()
        draft["events"][0]["id"] = COLLISION_ID
        draft["participants"] = [dict(id=COLLISION_ID, name="程伯", name_source_ids=["C1P001"])]
        with self.assertRaises(ValidationError) as caught:
            SourceReportDraft.model_validate(draft, strict=True)
        summary = LLMRuntime._schema_error_summary(caught.exception, schema)
        self.assertIn("报告对象（不符合合同）", summary)
        self.assertNotIn(COLLISION_ID, summary)
        self.assertNotIn("程伯", summary)

    def test_source_membership_and_full_final_gate_still_reject_after_shape(self):
        draft, bank, texts, binding = source_case()
        entries = binding["source_directory"]["entries"]
        unknown = deepcopy(draft)
        unknown["time_source_ids"] = ["C9P001"]
        SourceReportDraft.model_validate(unknown, strict=True)
        with self.assertRaises(ValueError):
            validate_source_candidate(unknown, entries, bank, texts, producer="synthetic")
        reserved = deepcopy(draft)
        reserved["findings"][0]["id"] = next(iter(bank))
        SourceReportDraft.model_validate(reserved, strict=True)
        with self.assertRaisesRegex(ValueError, "占用服务器证据ID"):
            prepare_source_draft(reserved, entries, bank, texts, producer="synthetic")

    def test_semantic_prompt_additions_reach_actual_review_and_final_verification(self):
        case = self.case()
        case.scripted([lambda: case.draft, case.revised_reply, lambda: acceptance(case.job()["revised"])])
        case.start()
        final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(case.calls), 3)
        for index, call in enumerate(case.calls):
            trusted = call["messages"][0]["content"]
            self.assertIn(DRAFT_GUIDANCE, trusted)
            if index:
                self.assertIn(REVIEW_GUIDANCE, trusted)
            for person in case.draft["characters"]:
                self.assertNotIn(person["name"], trusted)
        self.assertEqual([call["max_completion_tokens"] for call in case.calls], [24576, 8192, 4096])
