"""Exact disabled-pro preview capacity and unchanged paid-call guards, synthetic only."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app import deconstruction_routes
from app.agents import deconstruction_model
from app.agents.llm_runtime import LLMRuntime, LLMRuntimeSettings
from app.core.analysis_grounding import source_bank
from app.core.model_budget import estimate_structured_call_bound
from app.core.model_call_budget import DurableModelBudget
from app.core.preview_analysis import PreviewFacts, freeze_preview_facts
import test_stage37_fact_prompt_revision as fact_fixtures
import test_stage37_two_pass_preview as two_pass


OFFICIAL = {"api.xiaomimimo.com", "token-plan-cn.xiaomimimo.com"}
MODEL = "mimo-v2.6-pro"


def wire_bound(call):
    messages = deepcopy(call["messages"])
    prefix, schema_text = messages[0]["content"].rsplit(
        "\n\n只返回一个 JSON 对象，严格符合以下 schema，不要 Markdown 或解释：", 1)
    messages[0]["content"] = prefix
    messages.append({"role": "system", "content": json.dumps(json.loads(schema_text), ensure_ascii=False)})
    return estimate_structured_call_bound(messages, call["max_completion_tokens"], model=MODEL, attempts=1)


class PreviewCapacitySelectionTest(unittest.TestCase):
    def test_host_model_thinking_cross_product_with_exact_disabled_match(self):
        for host in (*sorted(OFFICIAL), "offline.invalid", "api.xiaomimimo.com.evil.invalid", "", "api.deepseek.com"):
            for model in (MODEL, "mimo-v2.6-flash", "mimo-v2.6-pro-preview", "MIMO-v2.6-pro", "unknown", " " + MODEL, MODEL + " ", ""):
                for thinking in ("disabled", "enabled", None, "unknown", "DISABLED"):
                    with self.subTest(host=host, model=model, thinking=thinking):
                        runtime = LLMRuntime(LLMRuntimeSettings(api_key="synthetic-only", model=model, thinking=thinking,
                            base_url=f"https://{host}/v1" if host else None), max_retries=0)
                        # Preserve the existing official enabled branch. The
                        # newly raised disabled branch is exact-model only.
                        expected = 24576 if host in OFFICIAL and (
                            thinking == "enabled" or (thinking == "disabled" and model == MODEL)) else 12288
                        self.assertEqual(deconstruction_model.preview_max_tokens(runtime), expected)

    def test_fake_runtime_with_matching_attributes_still_uses_12288(self):
        settings = SimpleNamespace(base_host="api.xiaomimimo.com", thinking="disabled", model=MODEL)
        for runtime in (SimpleNamespace(model=MODEL), SimpleNamespace(model=MODEL, settings=settings)):
            with self.subTest(runtime=runtime):
                self.assertEqual(deconstruction_model.preview_max_tokens(runtime), 12288)

    def test_unchanged_freeze_rejects_invalid_noncharacter_endpoint_even_if_unknown(self):
        for kind in ("cause", "purpose", "before", "reveal", "echo"):
            for status in ("fact", "unknown"):
                for target in (None, "", "A0", "Missing"):
                    with self.subTest(kind=kind, status=status, target=target):
                        facts, bank, texts = fact_fixtures.institution_facts()
                        facts["cues"] = [{"id": "Cue", "kind": kind, "from_atom_id": "A0", "to_atom_id": target,
                            "status": status, "text": "仅用于检查端点的合成线索。", "source_ids": facts["atoms"][0]["source_ids"]}]
                        before = deepcopy(facts)
                        with self.assertRaises(ValueError):
                            freeze_preview_facts(facts, bank, texts)
                        self.assertEqual(facts, before)


class OfficialDisabledPreviewCapacityTest(unittest.TestCase):
    setUp = two_pass.TwoPassApiTest.setUp
    _cleanup = two_pass.TwoPassApiTest._cleanup
    _login = two_pass.TwoPassApiTest._login
    _project = two_pass.TwoPassApiTest._project
    _start_and_save = two_pass.TwoPassApiTest._start_and_save
    _complete_and_process = two_pass.TwoPassApiTest._complete_and_process
    prepare = two_pass.TwoPassApiTest.prepare
    run_preview = two_pass.TwoPassApiTest.run_preview

    def test_both_stages_and_both_repairs_use_disabled24576_and_complete_reservations(self):
        def packets(facts, checked):
            return [{}, facts, {**deepcopy(checked), "extra": "不可信但完整的合成候选" * 400}, checked]
        for host in sorted(OFFICIAL):
            with self.subTest(host=host):
                response, calls, holds, budget = self.run_preview(packets, host=host)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(len(calls), 4)
                records = json.loads(budget.path.read_text())["records"][-4:]
                self.assertEqual([r["stage"].split(":")[-1] for r in records],
                                 ["facts", "format-repair", "checked", "format-repair"])
                self.assertGreater(holds[3]["reserved_cny"], holds[2]["reserved_cny"])
                for call, record in zip(calls, records, strict=True):
                    self.assertEqual(call["max_completion_tokens"], 24576)
                    self.assertNotIn("max_tokens", call)
                    self.assertEqual(call["thinking"], {"type": "disabled"})
                    self.assertEqual(call["temperature"], 0.3)
                    self.assertAlmostEqual(record["reserved_cny"], wire_bound(call), places=12)

    def test_old12288_fit_is_refused_before_first_new24576_http(self):
        project, _ = self.prepare()
        account = self.independent.store.load(project).account_id
        source = self.deconstruction._source(project, account)
        chapters = [dict(chapter_number=c.chapter_number, title=c.title, content=c.content) for c in source.chapters]
        bank = source_bank({c.chapter_number: c.content for c in source.chapters})
        messages = [*deconstruction_model.preview_fact_messages(chapters, bank),
                    {"role": "system", "content": json.dumps(PreviewFacts.model_json_schema(), ensure_ascii=False)}]
        old = estimate_structured_call_bound(messages, 12288, model=MODEL, attempts=1)
        new = estimate_structured_call_bound(messages, 24576, model=MODEL, attempts=1)
        cap = (old + new) / 2
        self.assertLess(old, cap)
        self.assertGreater(new, cap)
        budget = DurableModelBudget(self.deconstruction.store.base_dir / "strict-cap", budget_cny=cap)
        self.deconstruction.model_budget = budget
        runtime = deconstruction_model.create_runtime(deconstruction_model.DeconstructionModelSettings(
            _env_file=None, api_key="synthetic-only", model=MODEL, base_url="https://api.xiaomimimo.com/v1"))
        runtime._transport = lambda *args: self.fail("New output bound cannot fit; no HTTP is permitted")
        body = {key: value for key, value in self.payload.items() if key != "report"}
        body["chapter_numbers"] = [1]
        before = self.deconstruction.store.load(project).model_dump(mode="json")
        with patch.object(deconstruction_routes, "create_runtime", return_value=runtime):
            response = self.client.post(self.url + "/analyze-preview", json=body)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["detail"]["code"], "model_budget_exceeded")
        state = budget.public(MODEL)
        self.assertEqual((state["calls"], state["reserved_cny"], state["accounted_spent_cny"]), (0, 0, 0))
        self.assertEqual(self.deconstruction.store.load(project).model_dump(mode="json"), before)

    def test_second_stage_exhaustion_does_not_send_or_lower_output_cap(self):
        def drain(n, budget, runtime):
            if n == 1:
                ledger = budget._load(MODEL)
                ledger.spent_cny = ledger.budget_cny - sum(ledger.pending_attempts.values()) - 0.001
                budget._save(ledger, budget._records())
        response, calls, _, budget = self.run_preview(lambda f, c: [f, c], host="api.xiaomimimo.com", hook=drain)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["max_completion_tokens"], 24576)
        state = budget.public(MODEL)
        self.assertEqual((state["calls"], state["reserved_cny"]), (1, 0))
        self.assertEqual(DurableModelBudget(budget.directory, budget_cny=10).public(MODEL), state)

    def test_growing_second_repair_budget_is_refused_before_third_http(self):
        def packets(facts, checked):
            return [facts, {**deepcopy(checked), "extra": "需要完整计入预留的失败候选" * 400}]
        def drain(n, budget, runtime):
            if n == 2:
                ledger = budget._load(MODEL)
                ledger.spent_cny = ledger.budget_cny - sum(ledger.pending_attempts.values())
                budget._save(ledger, budget._records())
        response, calls, _, budget = self.run_preview(packets, host="api.xiaomimimo.com", hook=drain)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(call["max_completion_tokens"] == 24576 for call in calls))
        self.assertEqual((budget.public(MODEL)["calls"], budget.public(MODEL)["reserved_cny"]), (2, 0))

    def test_source_change_before_report_or_report_repair_still_stops_http(self):
        for change_at in (1, 2):
            with self.subTest(change_at=change_at):
                def change(n, budget, runtime):
                    if n == change_at:
                        record = self.independent.store.load(self.project)
                        version = next(v for v in record.versions if v.version_id == record.active_version_id)
                        version.chapters[0].formal_content += "保存的合成变更。"
                        version.chapters[0].server_revision += 1
                        self.independent.store.save(record)
                response, calls, _, _ = self.run_preview(lambda f, c: [f, {}], host="api.xiaomimimo.com", hook=change)
                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(len(calls), change_at)
                self.assertTrue(all(call["max_completion_tokens"] == 24576 for call in calls))
