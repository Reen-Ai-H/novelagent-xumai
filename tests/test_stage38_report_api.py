"""Production endpoints + actual structured parsing; all HTTP is synthetic."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
import threading
import time
import unittest
from unittest.mock import patch

from app import deconstruction_routes
from app.agents import deconstruction_model
from app.agents.llm_runtime import _collect_chat_stream
from app.core.book_analysis import BookAnalysis
from app.core.model_call_budget import DurableModelBudget
from app.core.report_pipeline import object_hash, target_hashes
from schemas.analysis_report import ReportTaskPublic
from stage38_report_fixtures import report_case, acceptance
import test_stage31_deconstruction as base
from test_stage37_preview_capacity import wire_bound


MODEL = "mimo-v2.6-pro"


class ReportApiTest(unittest.TestCase):
    setUp = base.Stage31DeconstructionApiTest.setUp
    _cleanup = base.Stage31DeconstructionApiTest._cleanup
    _login = base.Stage31DeconstructionApiTest._login
    _project = base.Stage31DeconstructionApiTest._project
    _encoded = staticmethod(base.Stage31DeconstructionApiTest._encoded)

    def prepare(self, count=2, *, bulk=False):
        self.project = self._project()
        _, _, texts = report_case(count, bulk=bulk)
        content = "\n\n".join(f"# 第{n}章 渡口验货\n{text}" for n, text in texts.items())
        preview = self.client.post(f"/api/independent/projects/{self.project}/imports/preview",
                                  json=dict(filename="synthetic.md", content_base64=self._encoded(content)))
        self.assertEqual(preview.status_code, 200, preview.text)
        confirmed = self.client.post(f"/api/independent/projects/{self.project}/imports/{preview.json()['preview']['preview_id']}/confirm")
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.deconstruction.process_background_tasks()
        self.account = self.independent.store.load(self.project).account_id
        source = self.deconstruction._source(self.project, self.account)
        self.draft, self.bank, self.texts = report_case(texts={c.chapter_number: c.content for c in source.chapters})
        self.body = dict(expected_source_version_id=source.version_id, expected_source_revision=source.source_revision,
                         expected_source_hash=source.source_hash)
        self.url = f"/api/independent/projects/{self.project}/deconstruction"
        self.old_author = self.independent.store.load(self.project).model_dump(mode="json")
        self.old_result = self.deconstruction.store.load(self.project).model_dump(mode="json")
        self.deconstruction.model_budget = DurableModelBudget(self.deconstruction.store.base_dir / "model-budgets",
                                                            scope="existing-five", budget_cny=5)
        self.calls = []
        self.holds = []
        self.factory_calls = 0
        self.runner = BookAnalysis(self.deconstruction, runtime_factory=self.factory)
        for p in (patch.object(deconstruction_routes, "book_analysis", self.runner),
                  patch.object(deconstruction_routes, "create_runtime", side_effect=self.factory)):
            p.start(); self.patches.append(p)
        self.scripted()
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def factory(self):
        self.factory_calls += 1
        return self.runtime

    def job(self):
        return self.runner.load(self.project, self.account)

    def scripted(self, replies=None, *, hook=None, unknown_at=()):
        self.replies = replies or [lambda: self.draft, lambda: acceptance(self.job()["draft"])]
        self.runtime = deconstruction_model.create_runtime(deconstruction_model.DeconstructionModelSettings(
            _env_file=None, api_key="synthetic-only", model=MODEL, base_url="https://api.xiaomimimo.com/v1"))
        def transport(url, headers, body, timeout):
            call = json.loads(body)
            self.calls.append(call)
            index = len(self.calls)
            self.assertLessEqual(index, len(self.replies), "Unexpected extra paid boundary")
            local = self.job()["budget"]
            shared = self.deconstruction.model_budget.public(MODEL)
            self.assertTrue(self.job()["inflight"])
            self.assertGreater(local["reserved_cny"], 0)
            self.assertGreater(shared["reserved_cny"], 0)
            self.holds.append((local, shared))
            if hook: hook(index)
            reply = self.replies[index - 1]
            value = reply() if callable(reply) else reply
            envelope = dict(choices=[dict(message=dict(content=json.dumps(value, ensure_ascii=False)), finish_reason="stop")])
            if index not in unknown_at:
                envelope["usage"] = dict(prompt_tokens=100, completion_tokens=20, total_tokens=120)
            return 200, json.dumps(envelope, ensure_ascii=False).encode()
        self.runtime._transport = transport

    def start(self, body=None):
        return self.client.post(self.url + "/book/start-report", json=body if body is not None else self.body)

    def wait(self):
        for _ in range(400):
            response = self.client.get(self.url + "/book")
            self.assertEqual(response.status_code, 200, response.text)
            job = response.json()["job"]
            if job["status"] != "running": return job
            time.sleep(0.005)
        self.fail("Synthetic task did not settle")

    def unchanged(self, *, author=True):
        self.assertEqual(self.deconstruction.store.load(self.project).model_dump(mode="json"), self.old_result)
        if author: self.assertEqual(self.independent.store.load(self.project).model_dump(mode="json"), self.old_author)

    def mutate(self, *, grow=False):
        record = self.independent.store.load(self.project)
        active = next(v for v in record.versions if v.version_id == record.active_version_id)
        active.chapters[0].formal_content += "作者修改。" + ("字" * 30001 if grow else "")
        active.chapters[0].server_revision += 1
        self.independent.store.save(record)

    def revised_reply(self):
        draft = self.job()["draft"]
        value = deepcopy(draft["characters"][0]); value["role"] = "渡口记账人"
        return dict(decision="revise", draft_hash=object_hash(draft), changes=[dict(target="characters/Lin",
            before_hash=target_hashes(draft)["characters/Lin"], replacement=value,
            text="按原文保留人物作用。", source_ids=[next(iter(self.bank))])])

    def test_six_chapter_normal_start_background_auto_adopt_and_exact_evidence(self):
        self.prepare(6, bulk=True)
        response = self.start()
        self.assertEqual(response.status_code, 200, response.text)
        public = ReportTaskPublic.model_validate(response.json()["job"])
        final = self.wait()
        self.assertEqual((final["kind"], final["status"], final["stage"], final["cursor"], final["total"]),
                         ("report-v2", "completed", "completed", 2, 2))
        state = self.client.get(self.url).json()
        self.assertEqual(state["result"]["document_id"], final["document_id"])
        self.assertEqual(state["result"]["report"]["producer"], MODEL)
        self.assertEqual(state["result"]["report"]["chapter_numbers"], list(range(1, 7)))
        self.assertEqual(self.independent.store.load(self.project).model_dump(mode="json"), self.old_author)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual([c["max_completion_tokens"] for c in self.calls], [24576, 8192])
        for call in self.calls:
            material = json.loads(call["messages"][1]["content"].split("\n", 1)[1])
            self.assertEqual(["".join(s["text"] for s in c["segments"]) for c in material["chapters"]], list(self.texts.values()))
        ref = state["result"]["evidence"][0]
        linked = self.client.get(self.url + "/evidence/" + ref["evidence_id"]).json()
        self.assertTrue(linked["source_matches_current"])
        self.assertEqual(linked["evidence"]["document_id"], final["document_id"])
        again = self.start().json()["job"]
        self.assertEqual(again["run_id"], public.run_id)
        self.assertEqual(again["document_id"], final["document_id"])
        self.assertEqual(len(self.calls), 2)

    def test_public_contract_and_safe_model_availability(self):
        self.prepare()
        budget = self.client.get(self.url + "/model-budget").json()
        self.assertIs(budget["model_available"], True)
        self.assertEqual(set(budget), {"budget", "model_available"})
        self.assertEqual(self.start().status_code, 200)
        public = self.wait()
        self.assertEqual(set(public), {"kind", "run_id", "status", "stage", "cursor", "total", "message", "budget", "document_id", "error_code"})
        self.assertNotIn("synthetic-only", json.dumps(public))
        for key in ("draft", "review_response", "draft_response", "revised", "participants"):
            self.assertNotIn(key, public)
        with patch.object(deconstruction_routes, "create_runtime", return_value=type("Disabled", (), dict(model=MODEL, available=False))()):
            self.assertIs(self.client.get(self.url + "/model-budget").json()["model_available"], False)

    def test_wrong_source_and_whole_over_limit_refuse_before_factory_or_payment(self):
        self.prepare()
        bad = {**self.body, "expected_source_hash": "0" * 64}
        self.assertEqual(self.start(bad).status_code, 409)
        self.assertEqual(self.factory_calls, 0)
        self.mutate(grow=True)
        source = self.deconstruction._source(self.project, self.account)
        body = dict(expected_source_version_id=source.version_id, expected_source_revision=source.source_revision,
                    expected_source_hash=source.source_hash)
        response = self.start(body)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["detail"]["code"], "report_scope_large")
        self.assertEqual(self.factory_calls, 0)
        self.assertEqual(self.calls, [])

    def test_start_body_requires_all_binding_fields_and_forbids_scope_subset(self):
        self.prepare()
        for bad in ({}, {**self.body, "chapter_numbers": [1]}, {k: v for k, v in self.body.items() if k != "expected_source_revision"}):
            with self.subTest(body=bad): self.assertEqual(self.start(bad).status_code, 422)
        self.assertEqual(self.calls, [])

    def test_one_sourced_revision_then_final_review_and_explicit_classification(self):
        self.prepare()
        self.scripted([lambda: self.draft, self.revised_reply, lambda: acceptance(self.job()["revised"])])
        self.assertEqual(self.start().status_code, 200)
        final = self.wait()
        self.assertEqual((final["status"], final["cursor"], final["total"]), ("completed", 3, 3))
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(self.job()["draft"]["characters"][0]["role"], "主要人物")
        report = self.client.get(self.url).json()["result"]["report"]
        self.assertEqual(report["characters"][0]["role"], "渡口记账人")
        self.assertEqual(report["characters"][0]["importance"], "main")
        self.assertIn("verification_response", self.job())

    def test_final_blocker_stops_no_semantic_retry_no_partial_adoption(self):
        self.prepare()
        def blocked(): return dict(decision="blocked", draft_hash=object_hash(self.job()["revised"]),
                                  issues=[dict(text="修订仍遗漏有效细节。", source_ids=[next(iter(self.bank))])])
        self.scripted([lambda: self.draft, self.revised_reply, blocked])
        self.start(); final = self.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "report_source_blocked"))
        self.assertEqual(len(self.calls), 3)
        self.unchanged()
        self.client.get(self.url + "/book")
        self.assertEqual(len(self.calls), 3)

    def test_invalid_draft_source_fails_without_review_or_format_repair(self):
        self.prepare()
        self.draft["evidence"][0]["source_id"] = "S9_" + "0" * 20
        self.start(); final = self.wait()
        self.assertEqual(final["error_code"], "report_evidence_invalid")
        self.assertEqual(len(self.calls), 1)
        self.unchanged()

    def test_all_six_http_reserve_actual_schema_and_growing_repair_input(self):
        self.prepare()
        self.scripted([{"extra": "完整失败候选" * 500}, lambda: self.draft,
                       {"extra": "批评失败候选" * 500}, self.revised_reply,
                       {"extra": "终审失败候选" * 500}, lambda: acceptance(self.job()["revised"])])
        self.start(); final = self.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(self.calls), 6)
        records = json.loads(self.deconstruction.model_budget.path.read_text())["records"]
        self.assertEqual(len(records), 6)
        for i, (call, record) in enumerate(zip(self.calls, records)):
            self.assertAlmostEqual(record["reserved_cny"], wire_bound(call), places=12)
            if i % 2: self.assertGreater(record["reserved_cny"], records[i - 1]["reserved_cny"])
        self.assertEqual(self.job()["budget"]["calls"], 6)

    def test_budget_exhaustion_and_persistence_failure_never_dispatch(self):
        self.prepare()
        self.deconstruction.model_budget.budget_cny = 0.0001
        self.start(); final = self.wait()
        self.assertEqual((final["status"], final["error_code"]), ("paused", "model_budget_exceeded"))
        self.assertEqual(self.calls, [])
        self.unchanged()

    def test_source_change_after_paid_draft_stops_review_and_keeps_old_result(self):
        self.prepare()
        self.scripted(hook=lambda index: self.mutate() if index == 1 else None)
        self.start(); final = self.wait()
        self.assertEqual(final["error_code"], "source_conflict")
        self.assertEqual(len(self.calls), 1)
        self.unchanged(author=False)

    def test_unknown_usage_is_conservatively_charged_in_same_two_ledgers(self):
        self.prepare()
        self.scripted(unknown_at=(1,))
        self.start(); self.assertEqual(self.wait()["status"], "completed")
        local = self.job()["budget"]; shared = self.deconstruction.model_budget.public(MODEL)
        self.assertEqual((local["calls"], shared["calls"]), (2, 2))
        self.assertEqual((local["unknown_usage_calls"], shared["unknown_usage_calls"]), (1, 1))
        self.assertGreater(shared["accounted_spent_cny"], self.holds[0][1]["reserved_cny"])
        self.assertEqual(shared["pending_attempts"], {})

    def assert_unknown_transport_guard(self, *, calls, stage):
        self.assertEqual(self.start().status_code, 200)
        final = self.wait()
        self.assertEqual((final["status"], final["error_code"], final["stage"]),
                         ("paused", "report_request_unknown", stage))
        self.assertTrue(self.job()["inflight"])
        self.assertEqual(len(self.calls), calls)
        local = self.job()["budget"]
        shared = self.deconstruction.model_budget.public(MODEL)
        for ledger in (local, shared):
            self.assertEqual(ledger["calls"], calls)
            self.assertEqual(ledger["unknown_usage_calls"], 1)
            self.assertEqual(ledger["pending_attempts"], {})
            self.assertGreaterEqual(ledger["accounted_spent_cny"], wire_bound(self.calls[-1]))
        records = json.loads(self.deconstruction.model_budget.path.read_text())["records"]
        self.assertEqual(len(records), calls)
        self.assertIs(records[-1]["usage_known"], False)
        self.assertAlmostEqual(records[-1]["estimated_cost_cny"], wire_bound(self.calls[-1]), places=12)
        before_job = deepcopy(self.job())
        before_scope = self.deconstruction.model_budget.path.read_bytes()
        recovered = BookAnalysis(self.deconstruction, runtime_factory=self.factory)
        with patch.object(deconstruction_routes, "book_analysis", recovered):
            self.assertEqual(self.client.portal.call(recovered.recover_pending), {"scheduled": 0, "invalid": 0})
            self.assertEqual(self.client.get(self.url + "/book").json()["job"], final)
            refused = self.start()
            self.assertEqual(refused.status_code, 409, refused.text)
            self.assertEqual(refused.json()["detail"]["code"], "report_request_unknown")
        self.assertEqual(self.job(), before_job)
        self.assertEqual(self.deconstruction.model_budget.path.read_bytes(), before_scope)
        self.assertEqual(len(self.calls), calls)
        self.unchanged()

    def assert_known_transport_failure(self, *, code, calls):
        self.assertEqual(self.start().status_code, 200)
        final = self.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", code))
        self.assertFalse(self.job()["inflight"])
        before_job = deepcopy(self.job())
        before_scope = self.deconstruction.model_budget.path.read_bytes()
        recovered = BookAnalysis(self.deconstruction, runtime_factory=self.factory)
        with patch.object(deconstruction_routes, "book_analysis", recovered):
            self.assertEqual(self.client.portal.call(recovered.recover_pending), {"scheduled": 0, "invalid": 0})
            self.assertEqual(self.client.get(self.url + "/book").json()["job"], final)
            self.assertEqual(self.job(), before_job)
            # Explicit retry is permitted for a complete response. Suppress
            # scheduling only to examine that pre-dispatch admission boundary.
            with patch.object(recovered, "ensure_task") as schedule:
                restarted = self.start()
                self.assertEqual(restarted.status_code, 200, restarted.text)
                schedule.assert_called_once()
            self.assertEqual(self.job()["budget"], before_job["budget"])
        self.assertEqual(self.deconstruction.model_budget.path.read_bytes(), before_scope)
        self.assertEqual(len(self.calls), calls)
        self.unchanged()

    @staticmethod
    def timeout_on(expected):
        def hook(index):
            if index == expected:
                raise TimeoutError("synthetic transport response unknown")
        return hook

    def test_actual_transport_timeout_pauses_draft_and_blocks_explicit_restart(self):
        self.prepare()
        self.scripted(hook=self.timeout_on(1))
        self.assert_unknown_transport_guard(calls=1, stage="draft")

    def test_actual_transport_timeout_pauses_review_and_retains_draft(self):
        self.prepare()
        self.scripted(hook=self.timeout_on(2))
        self.assert_unknown_transport_guard(calls=2, stage="review")
        self.assertIn("draft", self.job())

    def test_actual_transport_timeout_pauses_verification_and_retains_revision(self):
        self.prepare()
        self.scripted([lambda: self.draft, self.revised_reply, {}], hook=self.timeout_on(3))
        self.assert_unknown_transport_guard(calls=3, stage="verify")
        self.assertIn("revised", self.job())

    def test_actual_transport_timeout_in_draft_format_repair_is_not_bad_json(self):
        self.prepare()
        self.scripted([{}, {}], hook=self.timeout_on(2))
        self.assert_unknown_transport_guard(calls=2, stage="draft")

    def test_actual_transport_timeout_in_review_format_repair_is_not_bad_json(self):
        self.prepare()
        self.scripted([lambda: self.draft, {}, {}], hook=self.timeout_on(3))
        self.assert_unknown_transport_guard(calls=3, stage="review")

    def test_actual_transport_timeout_in_verification_format_repair_is_not_bad_json(self):
        self.prepare()
        self.scripted([lambda: self.draft, self.revised_reply, {}, {}], hook=self.timeout_on(4))
        self.assert_unknown_transport_guard(calls=4, stage="verify")

    def test_actual_transport_incomplete_stream_is_unknown_not_a_complete_bad_json(self):
        self.prepare()
        def incomplete(index):
            _collect_chat_stream([b'data: {"choices":[{"index":0,"delta":{"content":"{"}}]}\n'], 5)
        self.scripted(hook=incomplete)
        self.assert_unknown_transport_guard(calls=1, stage="draft")

    def test_actual_transport_complete_401_is_failed_not_unknown(self):
        self.prepare()
        transport = self.runtime._transport
        def unauthorized(*args, **kwargs):
            transport(*args, **kwargs)
            return 401, b""
        self.runtime._transport = unauthorized
        self.assert_known_transport_failure(code="provider_unauthorized", calls=1)

    def test_actual_transport_complete_429_is_failed_not_unknown(self):
        self.prepare()
        transport = self.runtime._transport
        def rate_limited(*args, **kwargs):
            transport(*args, **kwargs)
            return 429, b""
        self.runtime._transport = rate_limited
        self.assert_known_transport_failure(code="provider_rate_limited", calls=1)

    def test_actual_transport_complete_503_is_known_despite_unavailable_error_code(self):
        self.prepare()
        transport = self.runtime._transport
        def unavailable(*args, **kwargs):
            transport(*args, **kwargs)
            return 503, b""
        self.runtime._transport = unavailable
        self.assert_known_transport_failure(code="provider_unavailable", calls=1)

    def test_actual_transport_complete_repair_rejection_is_not_unknown(self):
        self.prepare()
        self.scripted([{}, {}])
        transport = self.runtime._transport
        def rejected_repair(*args, **kwargs):
            answer = transport(*args, **kwargs)
            return answer if len(self.calls) == 1 else (401, b"")
        self.runtime._transport = rejected_repair
        # The common runtime intentionally normalizes repair failures. That
        # code alone must not make an explicit rejection an unknown request.
        self.assert_known_transport_failure(code="provider_bad_json", calls=2)

    def test_actual_transport_complete_bad_json_twice_is_failed_not_unknown(self):
        self.prepare()
        self.scripted([{}, {}])
        transport = self.runtime._transport
        def malformed(*args, **kwargs):
            transport(*args, **kwargs)
            return 200, b'{"choices":[{"message":{"content":"{"},"finish_reason":"stop"}]}'
        self.runtime._transport = malformed
        self.assert_known_transport_failure(code="provider_bad_json", calls=2)

    def test_duplicate_running_start_and_reload_do_not_restart_http(self):
        self.prepare()
        entered = threading.Event(); release = threading.Event()
        self.addCleanup(release.set)
        self.scripted(hook=lambda i: (entered.set(), release.wait(5)) if i == 1 else None)
        first = self.start().json()["job"]
        self.assertTrue(entered.wait(5))
        second = self.start().json()["job"]
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(self.client.get(self.url + "/book").json()["job"]["run_id"], first["run_id"])
        self.assertEqual(len(self.calls), 1)
        release.set()
        self.assertEqual(self.wait()["status"], "completed")
        self.assertEqual(len(self.calls), 2)

    def test_cancelled_inflight_restart_and_explicit_start_never_resend(self):
        self.prepare()
        entered = threading.Event(); release = threading.Event()
        self.addCleanup(release.set)
        self.scripted(hook=lambda i: (entered.set(), release.wait(5)) if i == 1 else None)
        self.start(); self.assertTrue(entered.wait(5))
        self.client.portal.call(self.runner.tasks[self.project].cancel)
        final = self.wait(); release.set()
        self.assertEqual((final["status"], final["error_code"]), ("paused", "report_request_unknown"))
        shared = self.deconstruction.model_budget.public(MODEL)
        self.assertGreater(shared["reserved_cny"], 0)
        self.assertGreater(self.job()["budget"]["reserved_cny"], 0)
        self.assertEqual(self.client.portal.call(self.runner.recover_pending)["scheduled"], 0)
        before = sha256(self.deconstruction.model_budget.path.read_bytes()).hexdigest()
        self.assertEqual(self.start().status_code, 409)
        self.assertEqual(sha256(self.deconstruction.model_budget.path.read_bytes()).hexdigest(), before)
        self.assertEqual(len(self.calls), 1)
        self.unchanged()

    def test_pause_then_cancel_still_exposes_unknown_request_without_replay(self):
        self.prepare()
        entered = threading.Event(); release = threading.Event()
        self.addCleanup(release.set)
        self.scripted(hook=lambda i: (entered.set(), release.wait(5)) if i == 1 else None)
        self.start(); self.assertTrue(entered.wait(5))
        self.assertEqual(self.client.post(self.url + "/book/pause").status_code, 200)
        async def cancel():
            task = self.runner.tasks[self.project]
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self.client.portal.call(cancel)
        final = self.wait(); release.set()
        self.assertEqual((final["status"], final["error_code"]), ("paused", "report_request_unknown"))
        self.assertEqual(self.start().status_code, 409)
        self.assertEqual(len(self.calls), 1)

    def test_restart_after_draft_checkpoint_resumes_review_without_new_draft(self):
        self.prepare()
        original = self.runner._update_running
        stopped = False
        def checkpoint(*args, **kwargs):
            nonlocal stopped
            answer = original(*args, **kwargs)
            if not stopped and args[1].get("stage") == "review":
                stopped = True
                raise asyncio.CancelledError()
            return answer
        with patch.object(self.runner, "_update_running", side_effect=checkpoint):
            self.start(); self.assertEqual(self.wait()["status"], "paused")
        self.assertEqual(len(self.calls), 1)
        self.start(); final = self.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(self.calls), 2)

    def test_cross_account_cannot_start_or_read_private_job(self):
        self.prepare()
        self._login("other-report@example.test")
        self.assertEqual(self.start().status_code, 404)
        self.assertEqual(self.client.get(self.url + "/book").status_code, 404)
        self.assertEqual(self.calls, [])

    def test_shared_budget_save_failure_prevents_transport_and_preserves_old_report(self):
        self.prepare()
        with patch.object(self.deconstruction.model_budget, "_save", side_effect=OSError("synthetic disk failure")):
            self.start(); final = self.wait()
        self.assertEqual(final["status"], "paused")
        self.assertEqual(final["error_code"], "analysis_task_unavailable")
        self.assertEqual(self.calls, [])
        self.unchanged()

    def test_source_change_after_review_prevents_adoption(self):
        self.prepare()
        self.scripted(hook=lambda index: self.mutate() if index == 2 else None)
        self.start(); final = self.wait()
        self.assertEqual(final["error_code"], "source_conflict")
        self.assertEqual(len(self.calls), 2)
        self.unchanged(author=False)

    def test_checkpoint_recovery_without_browser_get_and_no_new_draft(self):
        self.prepare()
        original = self.runner._update_running
        stopped = False
        def checkpoint(*args, **kwargs):
            nonlocal stopped
            answer = original(*args, **kwargs)
            if not stopped and args[1].get("stage") == "review":
                stopped = True
                raise asyncio.CancelledError()
            return answer
        with patch.object(self.runner, "_update_running", side_effect=checkpoint):
            self.start(); self.assertEqual(self.wait()["status"], "paused")
        self.assertEqual(len(self.calls), 1)
        # Emulate a persisted running boundary at process shutdown. The new
        # runner schedules it through the same startup hook used by main.py.
        job = self.job(); job["status"] = "running"; self.runner.save(job)
        recovered = BookAnalysis(self.deconstruction, runtime_factory=self.factory)
        with patch.object(deconstruction_routes, "book_analysis", recovered):
            self.assertEqual(self.client.portal.call(recovered.recover_pending), {"scheduled": 1, "invalid": 0})
            self.assertEqual(self.wait()["status"], "completed")
        self.assertEqual(len(self.calls), 2)

    def test_crash_after_import_retries_only_idempotent_adoption_with_model_disabled(self):
        self.prepare()
        original = self.runner.save
        failed = False
        def save(job):
            nonlocal failed
            if not failed and job.get("status") == "completed":
                failed = True
                raise OSError("synthetic crash after successful import")
            return original(job)
        with patch.object(self.runner, "save", side_effect=save):
            self.start(); final = self.wait()
        self.assertEqual(final["status"], "paused")
        self.assertEqual(final["stage"], "adopt")
        adopted = self.client.get(self.url).json()["result"]["document_id"]
        documents = len(self.deconstruction.store.load(self.project).documents)
        self.assertEqual(len(self.calls), 2)
        # No credentials are needed to finish adopting an already reviewed
        # canonical candidate. This is not a fake inference branch.
        with patch.object(self.runner, "runtime_factory", side_effect=AssertionError("adoption must not request a model")):
            self.assertEqual(self.start().status_code, 200)
            final = self.wait()
        self.assertEqual((final["status"], final["document_id"]), ("completed", adopted))
        self.assertEqual(len(self.deconstruction.store.load(self.project).documents), documents)
        self.assertEqual(len(self.calls), 2)

    def test_same_scope_restart_cannot_raise_cap_or_clear_incurred_cost(self):
        self.prepare()
        ledger = self.deconstruction.model_budget._load(MODEL)
        ledger.spent_cny = 1.7906904
        self.deconstruction.model_budget._save(ledger, [])
        self.start(); self.assertEqual(self.wait()["status"], "completed")
        current = self.deconstruction.model_budget.public(MODEL)
        self.assertGreater(current["accounted_spent_cny"], 1.7906904)
        reopened = DurableModelBudget(self.deconstruction.model_budget.directory, scope="existing-five", budget_cny=100)
        self.assertEqual(reopened.public(MODEL), current)
        self.assertEqual(current["budget_cny"], 5)
        self.assertEqual(self.job()["budget"]["budget_cny"], 5)
        self.assertGreater(self.job()["budget"]["accounted_spent_cny"], 1.7906904)

    def test_invalid_review_source_or_hash_stops_no_silent_semantic_retry(self):
        self.prepare()
        def bad_review():
            return dict(decision="blocked", draft_hash=object_hash(self.job()["draft"]),
                        issues=[dict(text="有源问题。", source_ids=["S9_" + "0" * 20])])
        self.scripted([lambda: self.draft, bad_review])
        self.start(); final = self.wait()
        self.assertEqual(final["error_code"], "report_evidence_invalid")
        self.assertEqual(len(self.calls), 2)
        self.unchanged()
