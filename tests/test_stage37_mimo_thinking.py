"""Official analysis thinking parameters and full-usage accounting, offline only."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import deconstruction_routes
from app.agents import deconstruction_model
from app.agents.llm_runtime import LLMRuntime, LLMRuntimeSettings, _collect_chat_stream
from app.core.model_budget import MIMO_PRO_PRICING, estimate_structured_call_bound
from app.core.model_call_budget import DurableModelBudget, budgeted_structured
import test_stage32_analysis_import as import_fixtures
import test_stage37_targeted_repair as repair_fixtures


OFFICIAL = {"api.xiaomimimo.com", "token-plan-cn.xiaomimimo.com"}
REASONING = "SYNTHETIC_REASONING_MUST_NOT_LEAVE_COLLECTOR"
USAGE = {"prompt_tokens": 100, "completion_tokens": 3000, "total_tokens": 3100,
         "completion_tokens_details": {"reasoning_tokens": 2500}}


def config_for(host):
    return deconstruction_model.DeconstructionModelSettings(
        _env_file=None, api_key="synthetic-only", base_url=f"https://{host}/v1", model="mimo-v2.6-pro")


def stream(final):
    chunks = [
        {"choices": [{"delta": {"reasoning_content": REASONING}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": final}, "finish_reason": None}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        {"choices": [], "usage": USAGE},
    ]
    return [*(b"data: " + json.dumps(item).encode() + b"\n" for item in chunks), b"data: [DONE]\n"]


class ThinkingFactoryTest(unittest.TestCase):
    def test_default_and_injected_config_use_identical_production_factory(self):
        self.assertEqual(deconstruction_model.PREVIEW_MAX_TOKENS, 24576)
        for host in (*sorted(OFFICIAL), "offline.invalid", "api.xiaomimimo.com.evil.invalid"):
            with self.subTest(host=host):
                config = config_for(host)
                with patch.object(deconstruction_model, "DeconstructionModelSettings", return_value=config) as constructor:
                    default = deconstruction_model.create_runtime()
                constructor.assert_called_once_with()
                with patch.object(deconstruction_model, "DeconstructionModelSettings", side_effect=AssertionError("Unexpected config read")):
                    injected = deconstruction_model.create_runtime(config)
                self.assertEqual(default.settings, injected.settings)
                # Stage37 trial-4 decision restores the factory's disabled default.
                self.assertEqual(injected.settings.thinking, "disabled")
                self.assertEqual(deconstruction_model.preview_max_tokens(injected), 24576 if host in OFFICIAL else 12288)
                self.assertTrue(injected.settings.targeted_structured_repair)
                self.assertEqual(injected.settings.temperature, 0.3)
        self.assertIsNone(LLMRuntimeSettings().thinking)


class ThinkingWireTest(unittest.IsolatedAsyncioTestCase):
    async def test_only_official_enabled_mode_omits_sampling_controls(self):
        for host in (*sorted(OFFICIAL), "api.deepseek.com", "offline.invalid", "api.xiaomimimo.com.evil.invalid"):
            for thinking in (None, "disabled", "enabled"):
                with self.subTest(host=host, thinking=thinking):
                    calls = []

                    def transport(url, headers, body, timeout):
                        calls.append(json.loads(body))
                        return repair_fixtures.envelope("ok")

                    runtime = LLMRuntime(LLMRuntimeSettings(api_key="synthetic-only", base_url=f"https://{host}/v1",
                                                          model="mimo-v2.6-pro", thinking=thinking), transport=transport)
                    await runtime.complete(call_id="sampling", messages=[], max_tokens=8192, temperature=0.2)
                    body, = calls
                    if host in OFFICIAL and thinking == "enabled":
                        self.assertNotIn("temperature", body)
                    else:
                        self.assertEqual(body["temperature"], 0.2)
                    self.assertNotIn("top_p", body)
                    self.assertEqual(body.get("max_completion_tokens"), 8192 if host in OFFICIAL else None)
                    self.assertEqual(body.get("max_tokens"), None if host in OFFICIAL else 8192)
                    if thinking is not None and host in OFFICIAL | {"api.deepseek.com"}:
                        self.assertEqual(body["thinking"], {"type": thinking})
                    else:
                        self.assertNotIn("thinking", body)

    async def test_stream_keeps_only_final_content_and_bills_all_reasoning_usage(self):
        for first_final in ('{"answer":"ok"}', ""):
            with self.subTest(first_final=bool(first_final)), tempfile.TemporaryDirectory() as directory:
                budget = DurableModelBudget(Path(directory), budget_cny=2)
                progress, calls = [], []

                def transport(url, headers, body, timeout):
                    calls.append(json.loads(body))
                    final = first_final if len(calls) == 1 else '{"answer":"ok"}'
                    raw = _collect_chat_stream(iter(stream(final)), 10, progress=progress.append)
                    self.assertNotIn(REASONING, raw.decode())
                    return 200, raw

                configured = deconstruction_model.create_runtime(config_for("api.xiaomimimo.com"))
                runtime = LLMRuntime(replace(configured.settings, thinking="enabled"), transport=transport, max_retries=0)
                request = repair_fixtures.request()
                request["max_tokens"] = deconstruction_model.PREVIEW_MAX_TOKENS
                result = await budgeted_structured(runtime, budget, check_source=lambda: None, **request)
                count = 1 if first_final else 2
                self.assertEqual(len(calls), count)
                self.assertEqual(result.text, '{"answer":"ok"}')
                self.assertEqual(result.data, {"answer": "ok"})
                self.assertEqual(result.usage.completion_tokens, count * 3000)
                self.assertEqual(result.usage.total_tokens, count * 3100)
                self.assertAlmostEqual(budget.public(runtime.model)["accounted_spent_cny"],
                                       count * MIMO_PRO_PRICING.cost(input_tokens=100, output_tokens=3000), places=12)
                self.assertNotIn(REASONING, json.dumps(progress))
                self.assertNotIn(REASONING, budget.path.read_text())
                self.assertNotIn(REASONING, json.dumps(result.metadata(stage="thinking")))
                if count == 2:
                    self.assertEqual(repair_fixtures.candidate_messages(calls[1]), [])
                for call in calls:
                    self.assertEqual(call["max_completion_tokens"], 24576)
                    self.assertNotIn("temperature", call)


class PreviewThinkingBudgetTest(unittest.TestCase):
    setUp = import_fixtures.AnalysisImportTest.setUp
    _cleanup = import_fixtures.AnalysisImportTest._cleanup
    _login = import_fixtures.AnalysisImportTest._login
    _project = import_fixtures.AnalysisImportTest._project
    _start_and_save = import_fixtures.AnalysisImportTest._start_and_save
    _complete_and_process = import_fixtures.AnalysisImportTest._complete_and_process
    prepare = import_fixtures.AnalysisImportTest.prepare

    def test_product_preview_reserves_full_cap_for_initial_and_repair_calls(self):
        self.prepare()
        budget = DurableModelBudget(self.deconstruction.store.base_dir / "model-budgets", budget_cny=2)
        self.deconstruction.model_budget = budget
        wire = import_fixtures.preview_selector_report(self.payload["report"])
        facts, checked = import_fixtures.preview_pair(wire)
        runtime, calls = repair_fixtures.scripted([repair_fixtures.envelope("{}"), repair_fixtures.envelope(json.dumps(facts)),
                                                  repair_fixtures.envelope(json.dumps(checked))])
        runtime.settings = replace(deconstruction_model.create_runtime(config_for("api.xiaomimimo.com")).settings,
                                   thinking="enabled")
        body = {key: value for key, value in self.payload.items() if key != "report"}
        body["chapter_numbers"] = [1]
        with patch.object(deconstruction_routes, "create_runtime", return_value=runtime), \
                patch.object(budget, "reserve", wraps=budget.reserve) as reserve:
            response = self.client.post(self.url + "/analyze-preview", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(calls), 3)
        records = json.loads(budget.path.read_text())["records"]
        for index, (call, reservation, record) in enumerate(zip(calls, reserve.call_args_list, records, strict=True)):
            step_limit = 12288 if index < 2 else 24576
            self.assertEqual(call["max_completion_tokens"], step_limit)
            self.assertEqual(call["thinking"], {"type": "enabled"})
            self.assertNotIn("temperature", call)
            model, messages, max_tokens = reservation.args
            self.assertEqual(max_tokens, step_limit)
            expected = estimate_structured_call_bound(messages, max_tokens, model=model, attempts=1)
            self.assertAlmostEqual(record["reserved_cny"], expected, places=12)
            self.assertGreater(record["reserved_cny"], MIMO_PRO_PRICING.cost(output_tokens=step_limit))

    def test_cap_below_full_output_reservation_refuses_before_transport(self):
        self.prepare()
        self.deconstruction.model_budget = DurableModelBudget(
            self.deconstruction.store.base_dir / "model-budgets", budget_cny=0.1)
        configured = deconstruction_model.create_runtime(config_for("api.xiaomimimo.com"))

        def transport(*args):
            self.fail("Insufficient full-output budget must prevent transport")

        runtime = LLMRuntime(replace(configured.settings, thinking="enabled"), transport=transport, max_retries=0)
        body = {key: value for key, value in self.payload.items() if key != "report"}
        body["chapter_numbers"] = [1]
        with patch.object(deconstruction_routes, "create_runtime", return_value=runtime):
            response = self.client.post(self.url + "/analyze-preview", json=body)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.deconstruction.model_budget.public(runtime.model)["calls"], 0)
