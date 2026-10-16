"""Model-call budget accounting for long literary analysis jobs.

This module deliberately uses a conservative upper-bound estimate when a
provider does not expose cache-hit counters. It is a safety guard, not an
invoice calculator. The production ledger should still retain the provider's
reported usage for later reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
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
MIMO_FLASH_PRICING = TokenPricing(1.0, 2.0, 0.02, "mimo-v2.6-flash-cny-2026-10-05")
MIMO_PRO_PRICING = TokenPricing(3.0, 6.0, 0.025, "mimo-v2.6-pro-cny-2026-10-05")


def pricing_for_model(model: str) -> TokenPricing:
    """Select exact MiMo real-time CNY rates; retain legacy DeepSeek selection."""

    name = (model or "").lower().rsplit("/", 1)[-1]
    if name == "mimo-v2.6-flash":
        return MIMO_FLASH_PRICING
    if name == "mimo-v2.6-pro":
        return MIMO_PRO_PRICING
    if name.startswith("mimo-"):
        raise ValueError(f"未知 MiMo 模型价格：{name}")
    return FLASH_PRICING if "flash" in name else PRO_PRICING


def estimate_prompt_tokens(messages: Iterable[Mapping[str, object]]) -> int:
    """Estimate a request's uncached prompt size without exposing its text.

    Count every character as a token and include fixed structured-schema
    overhead. This is a deliberately high guard estimate, not billing usage.
    """

    characters = sum(len(str(message.get("content", "")).encode("utf-8")) for message in messages)
    return max(1, characters)


def _estimate_bound(messages: Iterable[Mapping[str, object]], max_tokens: int,
                    *, pricing: TokenPricing, attempts: int) -> float:
    if max_tokens < 0 or attempts < 1:
        raise ValueError("请求 token 上限无效")
    return pricing.cost(
        input_tokens=(estimate_prompt_tokens(messages) + 8192) * attempts,
        output_tokens=max_tokens * attempts,
    )


def estimate_structured_call_bound(messages: Iterable[Mapping[str, object]], max_tokens: int,
                                   *, model: str, attempts: int = 2) -> float:
    """CNY upper-bound guard for a structured call and its possible format repair.

    A preview route can use this before an untracked one-off call. A durable
    long-running job must additionally reserve and persist this amount.
    """
    return _estimate_bound(messages, max_tokens, pricing=pricing_for_model(model), attempts=attempts)


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
    # Durable upper bounds for requests that may have reached the provider.
    pending_attempts: dict[str, float] = field(default_factory=dict)
    _records: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        numbers = (self.budget_cny, self.reserve_cny, self.spent_cny, *self.pending_attempts.values())
        if any(not isfinite(value) or value < 0 for value in numbers):
            raise ValueError("预算账包含无效金额")

    @classmethod
    def from_public(cls, data: Mapping[str, object], *, pricing: TokenPricing) -> "BudgetLedger":
        version = data.get("pricing_version")
        if version and version != pricing.version:
            raise ValueError("模型价格与已保存的预算账不一致")
        pending = data.get("pending_attempts") or {}
        if not isinstance(pending, dict):
            raise ValueError("在途预算账格式无效")
        return cls(
            budget_cny=float(data.get("budget_cny", 10.0)),
            reserve_cny=float(data.get("reserve_cny", 1.0)), pricing=pricing,
            spent_cny=float(data.get("accounted_spent_cny", data.get("estimated_spent_cny", 0.0))),
            calls=int(data.get("calls", 0)),
            unknown_usage_calls=int(data.get("unknown_usage_calls", 0)),
            input_tokens=int(data.get("input_tokens", 0)),
            cache_read_tokens=int(data.get("cache_read_tokens", 0)),
            output_tokens=int(data.get("output_tokens", 0)),
            pending_attempts={str(key): float(value) for key, value in pending.items()},
        )

    def _bound(self, messages: Iterable[Mapping[str, object]], max_tokens: int, *, attempts: int = 1) -> float:
        return _estimate_bound(messages, max_tokens, pricing=self.pricing, attempts=attempts)

    def preflight(self, messages: Iterable[Mapping[str, object]], max_tokens: int, *, attempts: int = 2) -> None:
        """Reject a request whose conservative upper bound crosses the cap."""

        estimate = self._bound(messages, max_tokens, attempts=attempts)
        if self.spent_cny + sum(self.pending_attempts.values()) + estimate > max(0.0, self.budget_cny - self.reserve_cny):
            raise ModelBudgetExceeded("已达到本次拆解预算的安全上限，保留现有结果等待续费或调整预算。")

    def reserve_attempt(self, attempt_id: str, messages: Iterable[Mapping[str, object]], max_tokens: int, *, attempts: int = 2) -> None:
        """Persist public() before awaiting a structured call; repair may make a second request."""
        if attempt_id in self.pending_attempts:
            raise ValueError("请求预算已经预留")
        bound = self._bound(messages, max_tokens, attempts=attempts)
        if self.spent_cny + sum(self.pending_attempts.values()) + bound > max(0.0, self.budget_cny - self.reserve_cny):
            raise ModelBudgetExceeded("已达到本次拆解预算的安全上限，保留现有结果等待续费或调整预算。")
        self.pending_attempts[attempt_id] = bound

    def record(self, result: LLMResult, *, stage: str, attempt_id: str | None = None) -> float:
        """Record provider usage and return the conservative call estimate."""

        usage = getattr(result, "usage", None)
        call_id = getattr(result, "call_id", "unknown")
        reserved = self.pending_attempts.pop(attempt_id, None) if attempt_id is not None else None
        if attempt_id is not None and reserved is None:
            raise ValueError("没有对应的在途预算预留")
        # Adapters/fakes can construct LLMUsage directly, bypassing the provider
        # parser. Never release a durable hold based only on its `known` flag.
        if not isinstance(usage, LLMUsage) or not usage.is_valid:
            self.unknown_usage_calls += 1
            self.calls += max(1, getattr(result, "attempts", 1))
            self.spent_cny = round(self.spent_cny + (reserved or 0.0), 12)
            self._records.append({"call_id": call_id, "stage": stage, "usage_known": False,
                                  "estimated_cost_cny": reserved or 0.0})
            return reserved or 0.0
        cache_read = usage.cache_read_tokens
        uncached_input = usage.prompt_tokens - cache_read
        cost = self.pricing.cost(
            input_tokens=uncached_input,
            cache_read_tokens=cache_read,
            output_tokens=usage.completion_tokens,
        )
        # If provider counters exceed our preflight estimate, never understate the exposure.
        cost = max(cost, 0.0)
        # Cache tokens can cost fractions of a micro-yuan. Persist them rather
        # than rounding each request down and reopening the shared hard cap.
        self.spent_cny = round(self.spent_cny + cost, 12)
        self.calls += max(1, getattr(result, "attempts", 1))
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
            "estimated_cost_cny": round(cost, 12),
        })
        return cost

    def release_unsent(self, attempt_id: str) -> None:
        """Only the pre-dispatch coordinator may release a definitely unsent hold.

        Never use this for cancellation, timeout, restart or provider failure.
        Releasing a hold is not an HTTP request or an unknown-usage settlement.
        """
        if attempt_id not in self.pending_attempts:
            raise ValueError("没有对应的未发送预算预留")
        del self.pending_attempts[attempt_id]

    def public(self) -> dict[str, object]:
        return {
            "budget_cny": self.budget_cny,
            "reserve_cny": self.reserve_cny,
            "estimated_spent_cny": round(self.spent_cny, 4),
            "accounted_spent_cny": round(self.spent_cny, 12),
            "remaining_cny": round(max(0.0, self.budget_cny - self.spent_cny
                                       - sum(self.pending_attempts.values())), 4),
            "pricing_version": self.pricing.version,
            "calls": self.calls,
            "unknown_usage_calls": self.unknown_usage_calls,
            "input_tokens": self.input_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "output_tokens": self.output_tokens,
            "pending_attempts": dict(self.pending_attempts),
            "reserved_cny": round(sum(self.pending_attempts.values()), 6),
        }

    @property
    def records(self) -> list[dict[str, object]]:
        return list(self._records)
