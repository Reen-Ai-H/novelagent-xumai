import unittest

from app.agents.llm_runtime import LLMResult, LLMUsage
from app.core.model_budget import BudgetLedger, FLASH_PRICING, ModelBudgetExceeded, estimate_prompt_tokens


class ModelBudgetTest(unittest.TestCase):
    def test_preflight_keeps_reserved_closeout_budget(self):
        ledger = BudgetLedger(budget_cny=1.0, reserve_cny=0.25, pricing=FLASH_PRICING)
        messages = [{"role": "user", "content": "正文" * 1000}]
        ledger.preflight(messages, 1000)
        ledger.record(
            LLMResult(
                call_id="one",
                text="{}",
                usage=LLMUsage(prompt_tokens=100, completion_tokens=100, total_tokens=200),
            ),
            stage="segment",
        )
        self.assertEqual(ledger.public()["calls"], 1)
        self.assertGreaterEqual(ledger.public()["remaining_cny"], 0)

    def test_preflight_rejects_request_that_cannot_leave_reserve(self):
        ledger = BudgetLedger(budget_cny=0.1, reserve_cny=0.05, pricing=FLASH_PRICING)
        with self.assertRaises(ModelBudgetExceeded):
            ledger.preflight([{"role": "user", "content": "x" * 20000}], 10000)

    def test_unknown_usage_is_visible(self):
        ledger = BudgetLedger()
        ledger.record(LLMResult(call_id="unknown", text="{}", usage=LLMUsage(known=False)), stage="segment")
        self.assertEqual(ledger.public()["unknown_usage_calls"], 1)
        self.assertEqual(ledger.public()["estimated_spent_cny"], 0.0)

    def test_cache_reads_are_accounted_separately(self):
        ledger = BudgetLedger()
        ledger.record(
            LLMResult(
                call_id="cached",
                text="{}",
                usage=LLMUsage(prompt_tokens=1000, cache_read_tokens=900, completion_tokens=100, total_tokens=1100),
            ),
            stage="segment",
        )
        self.assertEqual(ledger.public()["input_tokens"], 100)
        self.assertEqual(ledger.public()["cache_read_tokens"], 900)

    def test_prompt_estimate_is_positive(self):
        self.assertGreater(estimate_prompt_tokens([{"role": "system", "content": ""}]), 0)


if __name__ == "__main__":
    unittest.main()
