"""Model-call budget accounting for long literary analysis jobs.

This module deliberately uses a conservative upper-bound estimate when a
provider does not expose cache-hit counters. It is a safety guard, not an
invoice calculator. The production ledger should still retain the provider's
reported usage for later reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from app.agents.llm_runtime import LLMResult, LLMUsage


class ModelBudgetExceeded(RuntimeError):
    """Raised before a request which could exceed the configured hard cap."""


@dataclass(frozen=True)
class TokenPricing:
    """Peak-hour CNY prices per million tokens.

    These defaults match the DeepSeek prices recorded on 2026-09-11. The
    values are versioned by the caller and must not be used to reconstruct an
    older invoice.
    """

    input_per_million: float
    output_per_million: float
    cache_read_per_million: float = 0.0
    version: str = "deepseek-2026-09-11-peak"

    def cost(self, *, input_tokens: int = 0, output_tokens: int = 0, cache_read_tokens: int = 0) -> float:
        return (
            max(0, input_tokens) * self.input_per_million
            + max(0, output_tokens) * self.output_per_million
            + max(0, cache_read_tokens) * self.cache_read_per_million
        ) / 1_000_000


FLASH_PRICING = TokenPricing(input_per_million=2.0, output_per_million=8.0, cache_read_per_million=0.04)
PRO_PRICING = TokenPricing(input_per_million=9.0, output_per_million=27.0, cache_read_per_million=0.30)


def pricing_for_model(model: str) -> TokenPricing:
    """Select a conservative current DeepSeek plan by model name."""

    return FLASH_PRICING if "flash" in (model or "").lower() else PRO_PRICING


def estimate_prompt_tokens(messages: Iterable[Mapping[str, object]]) -> int:
    """Estimate a request's uncached prompt size without exposing its text.

    Chinese literary text is intentionally estimated at two characters/token;
    this overestimates ordinary mixed text enough to make the preflight guard
    safer while remaining cheap and deterministic.
    """

    characters = sum(len(str(message.get("content", ""))) for message in messages)
    return max(1, (characters + 1) // 2)


@dataclass
class BudgetLedger:
    budget_cny: float = 10.0
    reserve_cny: float = 1.0
    pricing: TokenPricing = FLASH_PRICING
    spent_cny: float = 0.0
    calls: int = 0
    unknown_usage_calls: int = 0
    input_tokens: int = 0
    cache_read_tokens: int = 0
    output_tokens: int = 0
    _records: list[dict[str, object]] = field(default_factory=list)

    def preflight(self, messages: Iterable[Mapping[str, object]], max_tokens: int) -> None:
        """Reject a request whose conservative upper bound crosses the cap."""

        estimate = self.pricing.cost(
            input_tokens=estimate_prompt_tokens(messages),
            output_tokens=max(0, max_tokens),
        )
        if self.spent_cny + estimate > max(0.0, self.budget_cny - self.reserve_cny):
            raise ModelBudgetExceeded("已达到本次拆解预算的安全上限，保留现有结果等待续费或调整预算。")

    def record(self, result: LLMResult, *, stage: str) -> float:
        """Record provider usage and return the conservative call estimate."""

        usage = getattr(result, "usage", None)
        call_id = getattr(result, "call_id", "unknown")
        if not isinstance(usage, LLMUsage) or not usage.known:
            self.unknown_usage_calls += 1
            self._records.append({"call_id": call_id, "stage": stage, "usage_known": False})
            return 0.0
        cache_read = min(max(0, usage.prompt_tokens), max(0, usage.cache_read_tokens))
        uncached_input = max(0, usage.prompt_tokens - cache_read)
        cost = self.pricing.cost(
            input_tokens=uncached_input,
            cache_read_tokens=cache_read,
            output_tokens=usage.completion_tokens,
        )
        self.spent_cny = round(self.spent_cny + cost, 6)
        self.calls += 1
        self.input_tokens += uncached_input
        self.cache_read_tokens += cache_read
        self.output_tokens += usage.completion_tokens
        self._records.append({
            "call_id": call_id,
            "stage": stage,
            "usage_known": True,
            "prompt_tokens": usage.prompt_tokens,
            "uncached_input_tokens": uncached_input,
            "cache_read_tokens": cache_read,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "estimated_cost_cny": round(cost, 6),
        })
        return cost

    def public(self) -> dict[str, object]:
        return {
            "budget_cny": self.budget_cny,
            "reserve_cny": self.reserve_cny,
            "estimated_spent_cny": round(self.spent_cny, 4),
            "remaining_cny": round(max(0.0, self.budget_cny - self.spent_cny), 4),
            "pricing_version": self.pricing.version,
            "calls": self.calls,
            "unknown_usage_calls": self.unknown_usage_calls,
            "input_tokens": self.input_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "output_tokens": self.output_tokens,
        }

    @property
    def records(self) -> list[dict[str, object]]:
        return list(self._records)
