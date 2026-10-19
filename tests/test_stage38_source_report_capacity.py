"""Measured full wire/schema bounds; synthetic citation load != literary proof."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from app.agents.deconstruction_model import report_messages, source_report_messages
from app.core.model_budget import estimate_structured_call_bound
from app.core.report_pipeline import ReportReview, ReportVerification, object_hash, validate_draft
from app.core.source_report import (SourceReportDraft, _legacy_projection, source_target_hashes,
                                    validate_source_candidate)
from stage38_report_fixtures import acceptance
from stage38_source_report_fixtures import capacity_draft, source_case
import test_stage38_source_report_api as api
from test_stage37_preview_capacity import wire_bound


class SourceReportCapacityTest(unittest.TestCase):
    def fixture(self):
        draft, bank, texts, job = source_case(6, bulk=True)
        entries = job["source_directory"]["entries"]
        draft = capacity_draft(draft, entries)
        return draft, bank, texts, entries

    def test_full_schema_and_all_stage_inputs_are_counted_without_increasing_caps(self):
        draft, bank, texts, entries = self.fixture()
        before = deepcopy(draft)
        with patch("app.core.source_report.validate_draft", wraps=validate_draft) as gate:
            validate_source_candidate(draft, entries, bank, texts, producer="synthetic")
        legacy = gate.call_args.args[0]
        self.assertEqual(len(legacy["evidence"]), 137)
        self.assertGreaterEqual(sum(map(len, texts.values())), 21224)
        self.assertGreaterEqual(len(bank), 668)
        chapters = [dict(chapter_number=n, title="合成章节", content=text) for n, text in texts.items()]
        target = "characters/Lin"
        revision = dict(decision="revise", draft_hash=object_hash(draft), changes=[dict(target=target,
            before_hash=source_target_hashes(draft)[target], replacement=draft["characters"][0],
            text="依原文核对。", source_ids=["C1P001"])])
        for stage, schema, cap in (("draft", SourceReportDraft, 24576), ("review", ReportReview, 8192), ("verify", ReportVerification, 4096)):
            with self.subTest(stage=stage):
                context = {} if stage == "draft" else dict(draft=draft, diagnostics=[])
                if stage == "verify": context.update(original=draft, revision=revision)
                messages = source_report_messages(chapters, bank, entries, stage=stage, **context)
                packet = json.loads(messages[1]["content"].split("\n", 1)[1])
                self.assertEqual(["".join(s["text"] for s in c["segments"]) for c in packet["chapters"]], list(texts.values()))
                if stage == "review":
                    self.assertFalse(any(target.startswith("evidence/") for target in packet["target_hashes"]))
                    self.assertNotIn("evidence", packet["draft"])
                counted = [*messages, dict(role="system", content=json.dumps(schema.model_json_schema(), ensure_ascii=False))]
                actual_bytes = sum(len(message["content"].encode("utf-8")) for message in counted)
                bound = estimate_structured_call_bound(counted, cap, model=api.old.MODEL, attempts=1)
                self.assertAlmostEqual(bound, (actual_bytes + 8192) * 3 / 1_000_000 + cap * 6 / 1_000_000, places=12)
                self.assertGreater(bound, estimate_structured_call_bound(messages, cap, model=api.old.MODEL, attempts=1))
        self.assertEqual(draft, before)

    def test_short_selector_and_no_table_have_exact_json_byte_savings(self):
        draft, bank, texts, entries = self.fixture()
        legacy = _legacy_projection(draft, entries)
        compact = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        chapters = [dict(chapter_number=n, title="合成章节", content=text) for n, text in texts.items()]
        old_packet = json.loads(report_messages(chapters, bank, stage="draft")[1]["content"].split("\n", 1)[1])
        new_packet = json.loads(source_report_messages(chapters, bank, entries, stage="draft")[1]["content"].split("\n", 1)[1])
        input_saving = sum(len(key) - len(short) for short, key in entries.items())
        self.assertEqual(len(compact(old_packet)) - len(compact(new_packet)), input_saving)
        self.assertEqual(input_saving, len(bank) * 17)  # S hash IDs=23; this fixture's short IDs=6.
        self.assertLess(len(compact(draft)), len(compact(legacy)))
        self.assertNotIn("evidence", draft)
        self.assertGreater(len(compact(legacy["evidence"])), 9000)

    def test_actual_large_candidate_format_repair_reserves_complete_wire_not_empty_shell(self):
        case = api.SourceReportApiTest("runTest")
        case.setUp(); self.addCleanup(case.doCleanups)
        case.prepare(6, bulk=True)
        _, _, _, entries = self.fixture()
        case.draft = capacity_draft(case.draft, entries)
        invalid = {**deepcopy(case.draft), "unexpected": True}
        case.scripted([invalid, lambda: case.draft, lambda: acceptance(case.job()["draft"])])
        self.assertEqual(case.start().status_code, 200)
        final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(case.calls), 3)
        self.assertEqual([c["max_completion_tokens"] for c in case.calls], [24576, 24576, 8192])
        previous = json.loads(case.calls[1]["messages"][-1]["content"])["untrusted_previous_output"]
        self.assertEqual(json.loads(previous), invalid)
        report = case.client.get(case.url).json()["result"]["report"]
        self.assertEqual(len(report["evidence"]), 137)
        records = json.loads(case.deconstruction.model_budget.path.read_text())["records"]
        self.assertGreater(records[1]["reserved_cny"], records[0]["reserved_cny"])
        for call, record in zip(case.calls, records, strict=True):
            self.assertAlmostEqual(record["reserved_cny"], wire_bound(call), places=12)
        self.assertEqual(case.independent.store.load(case.project).model_dump(mode="json"), case.old_author)
