"""One durable hard cap for preview and book calls across projects and revisions."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from uuid import uuid4

from app.agents.llm_runtime import LLMResult, LLMRuntime, LLMUsage
from app.core.model_budget import BudgetLedger, pricing_for_model
from app.core.project_lock import ProjectLockStore


class DurableModelBudget:
    def __init__(self, directory: Path, *, scope="default", budget_cny=10.0):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", scope):
            raise ValueError("模型预算scope无效")
        # Validate injected caps before any request or filesystem mutation.
        BudgetLedger(budget_cny=budget_cny, reserve_cny=0)
        self.directory = directory
        self.scope = scope
        self.budget_cny = budget_cny
        self.locks = ProjectLockStore(directory / "locks")

    @property
    def path(self):
        return self.directory / f"{self.scope}.json"

    def _load(self, model):
        pricing = pricing_for_model(model)
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            ledger = BudgetLedger.from_public(data["budget"], pricing=pricing)
            # Restarting with a larger constructor value cannot reopen a cap.
            ledger.budget_cny = min(ledger.budget_cny, self.budget_cny)
            return ledger
        return BudgetLedger(budget_cny=self.budget_cny, reserve_cny=0, pricing=pricing)

    def _save(self, ledger, records):
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.directory, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({"budget": ledger.public(), "records": records}, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
            try:
                descriptor = os.open(self.directory, os.O_RDONLY)
            except OSError:
                descriptor = None
            if descriptor is not None:
                try:
                    if os.name != "nt":
                        os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def _records(self):
        return json.loads(self.path.read_text(encoding="utf-8"))["records"] if self.path.exists() else []

    def public(self, model):
        with self.locks.project_lock(self.scope):
            return self._load(model).public()

    def reserve(self, model, messages, max_tokens, *, attempts=1, stage):
        token = uuid4().hex
        with self.locks.project_lock(self.scope):
            ledger = self._load(model)
            ledger.reserve_attempt(token, messages, max_tokens, attempts=attempts)
            records = self._records()
            records.append({"attempt_id": token, "stage": stage, "status": "pending",
                            "reserved_cny": ledger.pending_attempts[token]})
            self._save(ledger, records)
        return token

    def settle(self, model, token, result, *, stage):
        with self.locks.project_lock(self.scope):
            ledger = self._load(model)
            ledger.record(result, stage=stage, attempt_id=token)
            records = self._records()
            for record in records:
                if record["attempt_id"] == token:
                    record.update(ledger.records[-1], status="settled")
                    break
            self._save(ledger, records)


async def budgeted_structured(runtime, budget, *, check_source, timeout=1220, **kwargs):
    """Track real HTTP attempts separately, including structured format repair.

    Runtime retries are disabled for this adapter: format repair remains one
    bounded additional request. Cancellation leaves the durable hold intact.
    Deterministic runtimes without an HTTP boundary reserve both attempts.
    """
    if isinstance(runtime, LLMRuntime):
        class TrackedRuntime(LLMRuntime):
            guard_error = None

            async def _request(self, **request):
                if self.guard_error is not None:
                    raise self.guard_error
                # Include the exact schema in the preflight, including the
                # duplicate schema embedded in runtime's repair instructions.
                messages = [*request["messages"], {"role": "system", "content":
                            json.dumps(request.get("json_schema"), ensure_ascii=False)}]
                try:
                    check_source()
                    token = budget.reserve(self.model, messages, request["max_tokens"], stage=request["call_id"])
                except Exception as exc:
                    self.guard_error = exc
                    raise
                try:
                    result = await super()._request(**request)
                except Exception as exc:
                    budget.settle(self.model, token,
                                  LLMResult(call_id=request["call_id"], text="",
                                            usage=getattr(exc, "usage", LLMUsage(known=False))),
                                  stage=request["call_id"] + ":failed")
                    raise
                budget.settle(self.model, token, result, stage=request["call_id"])
                return result
        tracked = TrackedRuntime(runtime.settings, transport=runtime._transport, max_retries=0)
        try:
            return await asyncio.wait_for(tracked.structured(**kwargs), timeout=timeout)
        except Exception:
            # structured() intentionally normalizes format-repair failures;
            # preserve our local budget/source refusal as the actionable error.
            if tracked.guard_error is not None:
                raise tracked.guard_error from None
            raise
    check_source()
    token = budget.reserve(runtime.model, kwargs["messages"], kwargs["max_tokens"], attempts=2,
                           stage=kwargs["call_id"])
    try:
        answer = await asyncio.wait_for(runtime.structured(**kwargs), timeout=timeout)
    except Exception as exc:
        budget.settle(runtime.model, token,
                      LLMResult(call_id=kwargs["call_id"], text="",
                                usage=getattr(exc, "usage", LLMUsage(known=False)),
                                attempts=getattr(exc, "attempts", 1)), stage=kwargs["call_id"] + ":failed")
        raise
    budget.settle(runtime.model, token, answer, stage=kwargs["call_id"])
    return answer
