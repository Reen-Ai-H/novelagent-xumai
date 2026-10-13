import unittest

from app.agents.llm_runtime import LLMResult, LLMUsage
from app.core.model_budget import (
    BudgetLedger, MIMO_FLASH_PRICING, MIMO_PRO_PRICING,
    ModelBudgetExceeded, estimate_structured_call_bound, pricing_for_model,
)


class Stage34BudgetTest(unittest.TestCase):
    def test_exact_mimo_realtime_prices_and_unknown_model(self):
        self.assertIs(pricing_for_model("mimo-v2.6-pro"), MIMO_PRO_PRICING)
        self.assertIs(pricing_for_model("xiaomi/mimo-v2.6-flash"), MIMO_FLASH_PRICING)
        self.assertEqual(MIMO_PRO_PRICING.cost(input_tokens=1_000_000,
                                               output_tokens=1_000_000,
                                               cache_read_tokens=1_000_000), 9.025)
        self.assertEqual(MIMO_FLASH_PRICING.cost(input_tokens=1_000_000,
                                                 output_tokens=1_000_000,
                                                 cache_read_tokens=1_000_000), 3.02)
        with self.assertRaises(ValueError):
            pricing_for_model("mimo-v2.6-pro-ultraspeed")

    def test_unknown_usage_consumes_persisted_two_attempt_reservation(self):
        ledger = BudgetLedger(budget_cny=1, reserve_cny=0.1, pricing=MIMO_PRO_PRICING)
        messages = [{"role": "user", "content": "中文正文" * 1000}]
        ledger.reserve_attempt("a", messages, 2000, attempts=2)
        before = ledger.public()
        self.assertAlmostEqual(before["reserved_cny"],
                               estimate_structured_call_bound(messages, 2000, model="mimo-v2.6-pro"),
                               places=6)
        self.assertGreater(before["reserved_cny"], 0)
        self.assertLess(before["remaining_cny"], 1.0)
        restored = BudgetLedger.from_public(before, pricing=MIMO_PRO_PRICING)
        self.assertEqual(restored.pending_attempts, ledger.pending_attempts)
        with self.assertRaises(ModelBudgetExceeded):
            restored.reserve_attempt("b", messages, 100_000, attempts=2)
        cost = restored.record(LLMResult(call_id="a", text="", usage=LLMUsage(known=False)),
                               stage="segment", attempt_id="a")
        self.assertAlmostEqual(cost, before["reserved_cny"], places=6)
        self.assertEqual(restored.public()["unknown_usage_calls"], 1)
        self.assertEqual(restored.public()["pending_attempts"], {})
        self.assertGreater(restored.public()["accounted_spent_cny"], 0)
        self.assertAlmostEqual(BudgetLedger.from_public(restored.public(), pricing=MIMO_PRO_PRICING).spent_cny,
                               restored.spent_cny, places=6)

    def test_known_usage_settles_reservation_and_cache_rate(self):
        ledger = BudgetLedger(pricing=MIMO_FLASH_PRICING)
        ledger.reserve_attempt("cached", [{"role": "user", "content": "文" * 100}], 1000)
        reserved = ledger.public()["reserved_cny"]
        actual = ledger.record(LLMResult(call_id="cached", text="{}",
                                         usage=LLMUsage(prompt_tokens=1000, cache_read_tokens=900,
                                                        completion_tokens=100, total_tokens=1100)),
                               stage="segment", attempt_id="cached")
        self.assertLess(actual, reserved)
        self.assertAlmostEqual(actual, (100 + 900 * 0.02 + 100 * 2) / 1_000_000)
        self.assertEqual(ledger.public()["input_tokens"], 100)
        self.assertEqual(ledger.public()["cache_read_tokens"], 900)
        self.assertEqual(ledger.public()["reserved_cny"], 0)
        with self.assertRaises(ValueError):
            BudgetLedger.from_public(ledger.public(), pricing=MIMO_PRO_PRICING)
