"""Production factory -> preview -> durable cap -> synthetic HTTP wire only."""
from dataclasses import replace
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app import deconstruction_routes
from app.agents import deconstruction_model
from app.agents.llm_runtime import LLMResult, LLMUsage
from app.core.analysis_grounding import source_bank
from app.core.preview_analysis import PreviewFacts, PreviewCheckedReport
from app.core.model_call_budget import DurableModelBudget
import test_stage32_analysis_import as fixtures


MODEL = "mimo-v2.6-pro"
OFFICIAL = {"api.xiaomimimo.com", "token-plan-cn.xiaomimimo.com"}


class PreviewProviderBudgetTest(unittest.TestCase):
    setUp = fixtures.AnalysisImportTest.setUp
    _cleanup = fixtures.AnalysisImportTest._cleanup
    _login = fixtures.AnalysisImportTest._login
    _project = fixtures.AnalysisImportTest._project
    _start_and_save = fixtures.AnalysisImportTest._start_and_save
    _complete_and_process = fixtures.AnalysisImportTest._complete_and_process
    prepare = fixtures.AnalysisImportTest.prepare

    def assemble(self, host):
        project, _ = self.prepare()
        budget = DurableModelBudget(self.deconstruction.store.base_dir / "provider-budget", scope=project, budget_cny=2)
        self.deconstruction.model_budget = budget
        runtime = deconstruction_model.create_runtime(deconstruction_model.DeconstructionModelSettings(
            _env_file=None, api_key="synthetic-only", base_url=f"https://{host}/v1", model=MODEL))
        wire = fixtures.preview_selector_report(self.payload["report"])
        facts, checked = fixtures.preview_pair(wire)
        calls = []

        def transport(url, headers, body, timeout):
            calls.append(json.loads(body))
            material = json.loads(calls[-1]["messages"][1]["content"].split("\n", 1)[1])
            packet = checked if "facts" in material else facts
            return 200, json.dumps({"choices": [{"message": {"content": json.dumps(packet)}, "finish_reason": "stop"}],
                                    "usage": {"prompt_tokens": 100, "completion_tokens": 3000, "total_tokens": 3100,
                                              "completion_tokens_details": {"reasoning_tokens": 2500}}}).encode()

        runtime._transport = transport
        payload = {key: value for key, value in self.payload.items() if key != "report"}
        payload["chapter_numbers"] = [1]
        return project, runtime, budget, calls, payload, wire

    def send(self, runtime, payload):
        with patch.object(deconstruction_routes, "create_runtime", return_value=runtime):
            return self.client.post(self.url + "/analyze-preview", json=payload)

    def test_actual_configuration_selects_the_same_request_and_reservation_limit(self):
        for host in (*sorted(OFFICIAL), "offline.invalid", "api.xiaomimimo.com.evil.invalid"):
            for override in ("factory", None, "disabled", "enabled"):
                with self.subTest(host=host, thinking=override):
                    project, runtime, budget, calls, payload, _ = self.assemble(host)
                    if override != "factory":
                        runtime.settings = replace(runtime.settings, thinking=override)
                    thinking = runtime.settings.thinking
                    expected = 24576 if host in OFFICIAL and thinking == "enabled" else 12288
                    before = self.independent.store.load(project).model_dump(mode="json")
                    with patch.object(budget, "reserve", wraps=budget.reserve) as reserve:
                        response = self.send(runtime, payload)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(self.independent.store.load(project).model_dump(mode="json"), before)
                    self.assertEqual(len(calls), 2)
                    self.assertEqual(reserve.call_count, 2)
                    for call, reservation in zip(calls, reserve.call_args_list, strict=True):
                        self.assertEqual(call["max_completion_tokens" if host in OFFICIAL else "max_tokens"], expected)
                        self.assertEqual(reservation.args[2], expected)
                        self.assertEqual(reservation.kwargs["attempts"], 1)
                        if host in OFFICIAL and thinking == "enabled":
                            self.assertNotIn("temperature", call)
                        else:
                            self.assertEqual(call["temperature"], 0.3)
                    self.assertEqual(budget.public(MODEL)["calls"], 2)
                    self.assertAlmostEqual(budget.public(MODEL)["accounted_spent_cny"], 0.0366)

    def test_old_fit_is_still_permitted_while_official_thinking_is_refused_on_same_ledger(self):
        for host, disabled in (("offline.invalid", False), ("api.xiaomimimo.com", True)):
            with self.subTest(host=host):
                project, runtime, budget, calls, payload, wire = self.assemble(host)
                if disabled:
                    runtime.settings = replace(runtime.settings, thinking="disabled")
                account = self.independent.store.load(project).account_id
                source = self.deconstruction._source(project, account)
                chapters = [dict(chapter_number=c.chapter_number, title=c.title, content=c.content) for c in source.chapters]
                bank = source_bank({c["chapter_number"]: c["content"] for c in chapters})
                facts, _ = fixtures.preview_pair(wire)
                messages = deconstruction_model.preview_fact_messages(chapters, bank)
                messages.append({"role": "system", "content": json.dumps(PreviewFacts.model_json_schema(), ensure_ascii=False)})
                second = deconstruction_model.preview_checked_messages(chapters, bank, json.dumps(facts))
                second.append({"role": "system", "content": json.dumps(PreviewCheckedReport.model_json_schema(), ensure_ascii=False)})
                # Independent arithmetic reproduces the old-fit/new-refused boundary.
                input_bound = (sum(len(m["content"].encode("utf-8")) for m in messages) + 8192) * 3 / 1_000_000
                second_input = (sum(len(m["content"].encode("utf-8")) for m in second) + 8192) * 3 / 1_000_000
                old_bound = max(input_bound + 12288 * 6 / 1_000_000, 0.0183 + second_input + 12288 * 6 / 1_000_000)
                new_bound = max(input_bound + 24576 * 6 / 1_000_000, 0.0183 + second_input + 24576 * 6 / 1_000_000)
                remaining = (old_bound + new_bound) / 2
                self.assertLess(old_bound, remaining)
                self.assertGreater(new_bound, remaining)
                ledger = budget._load(MODEL)
                ledger.spent_cny = 2 - remaining
                budget._save(ledger, [])
                starting_spent = budget.public(MODEL)["accounted_spent_cny"]
                official = deconstruction_model.create_runtime(deconstruction_model.DeconstructionModelSettings(
                    _env_file=None, api_key="synthetic-only", base_url="https://api.xiaomimimo.com/v1", model=MODEL))
                official.settings = replace(official.settings, thinking="enabled")
                official._transport = runtime._transport
                refused = self.send(official, payload)
                self.assertEqual(refused.status_code, 409, refused.text)
                # With two stages an enabled fact request may fit even when
                # its report request cannot. That refused HTTP is never sent.
                refused_prefix = int(input_bound + 24576 * 6 / 1_000_000 <= remaining)
                self.assertEqual(len(calls), refused_prefix)
                self.assertEqual(budget.public(MODEL)["calls"], refused_prefix)
                self.assertEqual(budget.public(MODEL)["pending_attempts"], {})
                allowed = self.send(runtime, payload)
                self.assertEqual(allowed.status_code, 200, allowed.text)
                self.assertEqual(len(calls), refused_prefix + 2)
                for call in calls[refused_prefix:]:
                    self.assertEqual(call["max_completion_tokens" if host in OFFICIAL else "max_tokens"], 12288)
                self.assertAlmostEqual(budget.public(MODEL)["accounted_spent_cny"], starting_spent + (refused_prefix + 2) * 0.0183)
                restarted = DurableModelBudget(budget.directory, scope=budget.scope, budget_cny=10)
                self.assertEqual(restarted.public(MODEL), budget.public(MODEL))
                self.assertEqual(restarted.public(MODEL)["budget_cny"], 2)

    def test_runtime_without_settings_keeps_legacy_default_and_two_attempt_hold(self):
        _, _, budget, _, payload, wire = self.assemble("offline.invalid")
        requests = []
        replies = iter(fixtures.preview_pair(wire))

        async def respond(**kwargs):
            requests.append(kwargs)
            return LLMResult(call_id="synthetic", text="", data=next(replies), usage=LLMUsage(known=False))

        runtime = SimpleNamespace(model=MODEL, available=True, structured=respond)
        with patch.object(budget, "reserve", wraps=budget.reserve) as reserve:
            response = self.send(runtime, payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(requests), 2)
        self.assertEqual(reserve.call_count, 2)
        self.assertEqual(requests[0]["max_tokens"], 12288)
        self.assertEqual(reserve.call_args.args[2], 12288)
        self.assertEqual(reserve.call_args.kwargs["attempts"], 2)

    def test_nonofficial_format_repair_keeps_legacy_limit_in_both_reservations(self):
        _, runtime, budget, _, payload, wire = self.assemble("offline.invalid")
        calls = []
        facts, checked = fixtures.preview_pair(wire)
        replies = iter(({}, facts, checked))

        def transport(url, headers, body, timeout):
            calls.append(json.loads(body))
            return 200, json.dumps({"choices": [{"message": {"content": json.dumps(next(replies))},
                                                "finish_reason": "stop"}],
                                    "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}}).encode()

        runtime._transport = transport
        with patch.object(budget, "reserve", wraps=budget.reserve) as reserve:
            response = self.send(runtime, payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(calls), 3)
        self.assertEqual([call["max_tokens"] for call in calls], [12288, 12288, 12288])
        self.assertEqual([call.args[2] for call in reserve.call_args_list], [12288, 12288, 12288])
        self.assertEqual(budget.public(MODEL)["calls"], 3)
