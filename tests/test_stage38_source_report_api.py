"""Fresh production start-report jobs, with real runtime parsing/fake HTTP only."""
import asyncio
from copy import deepcopy
import json
import threading
import unittest
from unittest.mock import patch

from app import deconstruction_routes
from app.core.book_analysis import BookAnalysis
from app.core.report_pipeline import object_hash
from app.core.source_report import SOURCE_REPORT_V2_WIRE, check_source_directory, source_target_hashes
from stage38_report_fixtures import acceptance
from stage38_source_report_fixtures import source_case
import test_stage38_report_api as old
from test_stage37_preview_capacity import wire_bound


class SourceReportApiTest(unittest.TestCase):
    setUp = old.ReportApiTest.setUp
    _cleanup = old.ReportApiTest._cleanup
    _login = old.ReportApiTest._login
    _project = old.ReportApiTest._project
    _encoded = staticmethod(old.ReportApiTest._encoded)
    factory = old.ReportApiTest.factory
    scripted = old.ReportApiTest.scripted
    job = old.ReportApiTest.job
    start = old.ReportApiTest.start
    wait = old.ReportApiTest.wait
    unchanged = old.ReportApiTest.unchanged
    mutate = old.ReportApiTest.mutate
    assert_unknown_transport_guard = old.ReportApiTest.assert_unknown_transport_guard
    assert_known_transport_failure = old.ReportApiTest.assert_known_transport_failure
    timeout_on = staticmethod(old.ReportApiTest.timeout_on)

    def prepare(self, count=2, *, bulk=False):
        old.ReportApiTest.prepare(self, count, bulk=bulk, legacy=False)
        self.draft, _, _, _ = source_case(texts=self.texts)

    def revised_reply(self):
        draft = self.job()["draft"]
        value = deepcopy(draft["characters"][0]); value["role"] = "渡口记账人"
        return dict(decision="revise", draft_hash=object_hash(draft), changes=[dict(target="characters/Lin",
            before_hash=source_target_hashes(draft)["characters/Lin"], replacement=value,
            text="按原文保留人物作用。", source_ids=["C1P001"])])

    def checkpoint(self, stage):
        original = self.runner._update_running
        stopped = False
        def update(*args, **kwargs):
            nonlocal stopped
            answer = original(*args, **kwargs)
            if not stopped and args[1].get("stage") == stage:
                stopped = True
                raise asyncio.CancelledError()
            return answer
        return patch.object(self.runner, "_update_running", side_effect=update)

    def test_fresh_six_chapter_job_freezes_private_wire_and_auto_imports_stable_sources(self):
        self.prepare(6, bulk=True)
        self.assertIsNone(self.job())
        self.assertGreaterEqual(sum(map(len, self.texts.values())), 21224)
        self.assertGreaterEqual(len(self.bank), 668)
        self.assertEqual(self.start().status_code, 200)
        final = self.wait()
        self.assertEqual((final["status"], final["stage"], final["cursor"], final["total"]), ("completed", "completed", 2, 2))
        job = self.job()
        self.assertEqual(job["report_wire_version"], SOURCE_REPORT_V2_WIRE)
        entries = check_source_directory(job, self.bank, self.texts)
        self.assertEqual(len(entries), len(self.bank))
        self.assertEqual(job["draft_diagnostics"], [])
        self.assertNotIn("evidence", job["draft"])
        result = self.client.get(self.url).json()["result"]
        self.assertEqual(result["document_id"], final["document_id"])
        self.assertEqual(result["report"]["producer"], old.MODEL)
        self.assertEqual(result["report"]["chapter_numbers"], list(range(1, 7)))
        for row in result["report"]["evidence"]:
            passage = self.bank[row["id"]]
            self.assertEqual((row["chapter_number"], row["quote"]), (passage.chapter_number, passage.quote))
        self.assertEqual(len(self.calls), 2)
        self.assertEqual([call["max_completion_tokens"] for call in self.calls], [24576, 8192])
        for call in self.calls:
            packet = json.loads(call["messages"][1]["content"].split("\n", 1)[1])
            self.assertEqual(["".join(s["text"] for s in c["segments"]) for c in packet["chapters"]], list(self.texts.values()))
            sent = {s["source_id"] for c in packet["chapters"] for s in c["segments"] if "source_id" in s}
            self.assertEqual(sent, set(entries))
            self.assertNotIn("evidence/", json.dumps(packet))
            self.assertFalse(set(self.bank).intersection(sent))
        self.assertEqual(self.independent.store.load(self.project).model_dump(mode="json"), self.old_author)
        public = self.client.get(self.url + "/book").json()["job"]
        for key in ("source_directory", "report_wire_version", "draft_diagnostics", "draft_response", "draft", "review_response"):
            self.assertNotIn(key, public)

    def test_unknown_citation_can_be_explicitly_sourced_once_then_verified(self):
        self.prepare()
        self.draft["characters"][0]["name_source_ids"] = ["C9P001"]
        original = deepcopy(self.draft)
        def correction():
            draft = self.job()["draft"]
            self.assertIn("unknown_source", [d["code"] for d in self.job()["draft_diagnostics"]])
            person = deepcopy(draft["characters"][0]); person["name_source_ids"] = ["C1P001"]
            return dict(decision="revise", draft_hash=object_hash(draft), changes=[dict(target="characters/Lin",
                before_hash=source_target_hashes(draft)["characters/Lin"], replacement=person,
                text="姓名出现在本章此处，选择该实际来源。", source_ids=["C1P001"])])
        self.scripted([lambda: self.draft, correction, lambda: acceptance(self.job()["revised"])])
        self.start(); final = self.wait()
        self.assertEqual((final["status"], final["cursor"], final["total"]), ("completed", 3, 3))
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(self.job()["draft_response"], original)
        self.assertEqual(self.job()["draft"], original)
        self.assertEqual(self.job()["revised"]["characters"][0]["name_source_ids"], ["C1P001"])
        review_packet = json.loads(self.calls[1]["messages"][1]["content"].split("\n", 1)[1])
        self.assertEqual(review_packet["diagnostics"], self.job()["draft_diagnostics"])
        self.assertNotIn("evidence", self.job()["revised"])

    def test_located_time_cycle_reaches_review_and_requires_explicit_single_revision(self):
        self.prepare()
        self.draft["order_constraints"] = [dict(from_action="E1b.action", to_action="E1a.action", source_ids=["C1P001"])]
        original = deepcopy(self.draft)
        def correction():
            draft = self.job()["draft"]
            self.assertIn("event_cycle", [d["code"] for d in self.job()["draft_diagnostics"]])
            return dict(decision="revise", draft_hash=object_hash(draft), changes=[dict(target="order_constraints/0",
                before_hash=source_target_hashes(draft)["order_constraints/0"],
                replacement=dict(from_action="E1b.action", to_action="E1b.consequence", source_ids=["C1P005"]),
                text="以同一次核对的动作与后果为边界纠正先后。", source_ids=["C1P005"])])
        self.scripted([lambda: self.draft, correction, lambda: acceptance(self.job()["revised"])])
        self.start(); final = self.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(self.job()["draft"], original)
        self.assertEqual(self.job()["revised"]["events"], original["events"])
        self.assertEqual(self.job()["revised"]["relations"], original["relations"])

    def test_review_accept_does_not_bypass_unknown_reference(self):
        self.prepare()
        self.draft["time_source_ids"] = ["C9P001"]
        self.start(); final = self.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "report_evidence_invalid"))
        self.assertEqual(len(self.calls), 2)
        self.assertIn("review_response", self.job())
        self.assertNotIn("approved_hash", self.job())
        self.unchanged()

    def test_review_accept_does_not_bypass_time_cycle(self):
        self.prepare()
        self.draft["order_constraints"] = [dict(from_action="E1b.action", to_action="E1a.action", source_ids=["C1P001"])]
        self.start(); final = self.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "report_evidence_invalid"))
        self.assertEqual(len(self.calls), 2)
        self.unchanged()

    def test_unresolved_revision_stops_before_verify_without_new_loop(self):
        self.prepare()
        self.draft["time_source_ids"] = ["C9P001"]
        self.scripted([lambda: self.draft, self.revised_reply])
        self.start(); final = self.wait()
        self.assertEqual((final["status"], final["stage"], final["error_code"]), ("failed", "revise", "report_evidence_invalid"))
        self.assertEqual(len(self.calls), 2)
        self.assertNotIn("revised", self.job())
        self.unchanged()

    def test_final_sourced_blocker_rejects_loss_of_valid_fact_and_preserves_original(self):
        self.prepare()
        def retraction():
            draft = self.job()["draft"]
            return dict(decision="revise", draft_hash=object_hash(draft), changes=[dict(target="relations/0",
                before_hash=source_target_hashes(draft)["relations/0"], replacement=None,
                text="审查误认为该先后连接无据。", source_ids=["C1P001"])])
        def blocked():
            return dict(decision="blocked", draft_hash=object_hash(self.job()["revised"]),
                        issues=[dict(text="原文先后仍成立，撤回会漏掉有效事实。", source_ids=["C1P001"])])
        self.scripted([lambda: self.draft, retraction, blocked])
        self.start(); final = self.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "report_source_blocked"))
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(len(self.job()["draft"]["relations"]), len(self.draft["relations"]))
        self.unchanged()

    def test_object_id_ambiguity_still_fails_before_review_after_one_format_repair(self):
        self.prepare()
        self.draft["events"][0]["id"] = "Lin"
        self.scripted([lambda: self.draft, lambda: self.draft])
        self.start(); final = self.wait()
        self.assertEqual(final["error_code"], "provider_bad_json")
        self.assertEqual(len(self.calls), 2)
        self.assertNotIn("draft", self.job())
        self.assertNotIn("review_response", self.job())
        self.unchanged()

    def test_unexpected_draft_error_is_fatal_not_an_ignorable_review_issue(self):
        self.prepare()
        with patch("app.core.report_job.prepare_source_draft", side_effect=RuntimeError("private synthetic detail")):
            self.start(); final = self.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "report_internal_error"))
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn("private synthetic detail", json.dumps(final))
        self.assertNotIn("review_response", self.job())
        self.assertNotIn("draft_diagnostics", self.job())
        self.assertEqual(self.client.get(self.url + "/book").json()["job"], final)
        self.assertEqual(len(self.calls), 1)
        self.unchanged()

    def test_all_six_http_use_full_actual_schema_candidate_and_unchanged_caps(self):
        self.prepare()
        self.scripted([{"unexpected": "草稿失败" * 300}, lambda: self.draft,
                       {"unexpected": "审查失败" * 300}, self.revised_reply,
                       {"unexpected": "终审失败" * 300}, lambda: acceptance(self.job()["revised"])])
        self.start(); final = self.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(self.calls), 6)
        self.assertEqual([call["max_completion_tokens"] for call in self.calls], [24576, 24576, 8192, 8192, 4096, 4096])
        records = json.loads(self.deconstruction.model_budget.path.read_text())["records"]
        for i, (call, record) in enumerate(zip(self.calls, records, strict=True)):
            self.assertAlmostEqual(record["reserved_cny"], wire_bound(call), places=12)
            if i % 2:
                self.assertGreater(record["reserved_cny"], records[i - 1]["reserved_cny"])
        self.assertEqual(self.job()["budget"]["calls"], 6)

    def test_cached_response_recovers_with_identical_map_and_no_repeated_draft_request(self):
        self.prepare()
        original = self.runner._update_running
        def checkpoint(job, values, **kwargs):
            if "draft" in values:
                raise asyncio.CancelledError()
            return original(job, values, **kwargs)
        with patch.object(self.runner, "_update_running", side_effect=checkpoint):
            self.start(); self.assertEqual(self.wait()["status"], "paused")
        self.assertEqual(len(self.calls), 1)
        directory = deepcopy(self.job()["source_directory"])
        self.assertNotIn("draft", self.job())
        recovered = BookAnalysis(self.deconstruction, runtime_factory=self.factory)
        with patch.object(deconstruction_routes, "book_analysis", recovered):
            self.start(); self.assertEqual(self.wait()["status"], "completed")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.job()["source_directory"], directory)

    def test_recovery_retains_invalid_draft_diagnostics_and_does_not_charge_again(self):
        self.prepare()
        self.draft["time_source_ids"] = ["C9P001"]
        with self.checkpoint("review"):
            self.start(); self.assertEqual(self.wait()["status"], "paused")
        self.assertEqual(len(self.calls), 1)
        before = deepcopy(self.job())
        recovered = BookAnalysis(self.deconstruction, runtime_factory=self.factory)
        with patch.object(deconstruction_routes, "book_analysis", recovered):
            self.start(); final = self.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "report_evidence_invalid"))
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.job()["draft"], before["draft"])
        self.assertEqual(self.job()["draft_diagnostics"], before["draft_diagnostics"])
        self.assertEqual(self.job()["source_directory"], before["source_directory"])
        self.unchanged()

    def test_tampered_persisted_map_is_rejected_before_another_request(self):
        self.prepare()
        with self.checkpoint("review"):
            self.start(); self.assertEqual(self.wait()["status"], "paused")
        job = self.job()
        job["source_directory"]["entries"]["C1P001"] = job["source_directory"]["entries"]["C2P001"]
        self.runner.save(job)
        self.start(); final = self.wait()
        self.assertEqual(final["error_code"], "report_evidence_invalid")
        self.assertEqual(len(self.calls), 1)
        self.unchanged()

    def test_explicit_wire_not_guessed_from_old_candidate_shape(self):
        self.prepare()
        old_draft, _, _ = old.report_case(texts=self.texts)
        self.scripted([old_draft, old_draft])
        self.start(); final = self.wait()
        self.assertEqual(final["error_code"], "provider_bad_json")
        self.assertEqual(len(self.calls), 2)
        self.assertNotIn("draft", self.job())
        self.assertEqual(self.job()["report_wire_version"], SOURCE_REPORT_V2_WIRE)
        self.unchanged()

    def test_failed_legacy_json_is_preserved_in_history_not_converted_or_adopted(self):
        self.prepare()
        old_draft, _, _ = old.report_case(texts=self.texts)
        old_draft["evidence"][0]["source_id"] = "S9_" + "0" * 20
        with patch.object(self.runner, "ensure_task"):
            self.start()
        legacy = self.job()
        legacy.pop("report_wire_version"); legacy.pop("source_directory")
        legacy.update(run_id="failed-legacy", status="failed", stage="draft",
                      error_code="report_evidence_invalid", draft_response=old_draft)
        self.runner.save(legacy)
        before = deepcopy(legacy)
        self.start(); final = self.wait()
        self.assertEqual(final["status"], "completed", final)
        current = self.job()
        self.assertEqual(current["report_history"][-1], {k: v for k, v in before.items() if k != "report_history"})
        self.assertEqual(current["report_history"][-1]["draft_response"], old_draft)
        self.assertNotEqual(current["run_id"], "failed-legacy")
        self.assertEqual(current["report_wire_version"], SOURCE_REPORT_V2_WIRE)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(current["draft_response"], self.draft)

    def test_unversioned_legacy_job_keeps_ev_ids_and_original_validation_path(self):
        from test_stage38_report_prompt_contract import remap_synthetic_evidence
        case = old.ReportApiTest("runTest")
        case.setUp(); self.addCleanup(case.doCleanups)
        case.prepare()
        case._legacy_fixture.pop("report_wire_version")
        mapping = {row["id"]: f"EV{i}" for i, row in enumerate(case.draft["evidence"])}
        case.draft = remap_synthetic_evidence(case.draft, mapping)
        case.start(); final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertNotIn("report_wire_version", case.job())
        self.assertNotIn("source_directory", case.job())
        self.assertEqual(len(case.calls), 2)
        report = case.client.get(case.url).json()["result"]["report"]
        self.assertEqual([e["id"] for e in report["evidence"]], list(mapping.values()))
        self.assertIn("evidence.id == source_id", case.calls[0]["messages"][0]["content"])
        self.assertNotIn("SourceReportDraft", case.calls[0]["messages"][0]["content"])

    # Re-run safety assertions with FRESH new-wire production jobs. Original
    # legacy-wire tests retain their old expectations in their own test class.
    def test_new_wire_transport_timeout_draft_unknown_gate(self):
        old.ReportApiTest.test_actual_transport_timeout_pauses_draft_and_blocks_explicit_restart(self)

    def test_new_wire_transport_timeout_review_unknown_gate(self):
        old.ReportApiTest.test_actual_transport_timeout_pauses_review_and_retains_draft(self)

    def test_new_wire_transport_timeout_verification_unknown_gate(self):
        old.ReportApiTest.test_actual_transport_timeout_pauses_verification_and_retains_revision(self)

    def test_new_wire_repair_transport_timeout_unknown_gate(self):
        old.ReportApiTest.test_actual_transport_timeout_in_draft_format_repair_is_not_bad_json(self)

    def test_new_wire_complete_401_is_not_unknown(self):
        old.ReportApiTest.test_actual_transport_complete_401_is_failed_not_unknown(self)

    def test_new_wire_complete_429_is_not_unknown(self):
        old.ReportApiTest.test_actual_transport_complete_429_is_failed_not_unknown(self)

    def test_new_wire_complete_bad_json_is_not_unknown(self):
        old.ReportApiTest.test_actual_transport_complete_bad_json_twice_is_failed_not_unknown(self)

    def test_new_wire_concurrent_clicks_reuse_job_and_request(self):
        old.ReportApiTest.test_duplicate_running_start_and_reload_do_not_restart_http(self)

    def test_new_wire_source_precheck_before_factory_or_payment(self):
        old.ReportApiTest.test_wrong_source_and_whole_over_limit_refuse_before_factory_or_payment(self)

    def test_new_wire_source_cas_after_draft_blocks_review(self):
        old.ReportApiTest.test_source_change_after_paid_draft_stops_review_and_keeps_old_result(self)

    def test_new_wire_source_cas_after_review_blocks_adoption(self):
        old.ReportApiTest.test_source_change_after_review_prevents_adoption(self)

    def test_new_wire_shared_budget_cannot_reset_or_expand(self):
        old.ReportApiTest.test_same_scope_restart_cannot_raise_cap_or_clear_incurred_cost(self)

    def test_new_wire_insufficient_budget_sends_nothing(self):
        old.ReportApiTest.test_budget_exhaustion_and_persistence_failure_never_dispatch(self)

    def test_new_wire_cross_account_access_is_rejected(self):
        old.ReportApiTest.test_cross_account_cannot_start_or_read_private_job(self)

    def test_new_wire_recovery_after_import_only_repeats_idempotent_import(self):
        old.ReportApiTest.test_crash_after_import_retries_only_idempotent_adoption_with_model_disabled(self)
