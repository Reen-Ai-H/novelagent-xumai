"""Per-HTTP job/shared caps; synthetic transports, isolated durable ledgers only."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.agents.llm_runtime import LLMResult, LLMRuntimeError, LLMUsage
from app.core.book_analysis import BookAnalysis, ReadingMemory, _BookCallBudget
from app.core.deconstruction_store import DeconstructionStore
from app.core.model_budget import BudgetLedger, MIMO_PRO_PRICING, ModelBudgetExceeded, estimate_structured_call_bound
from app.core.model_call_budget import DurableModelBudget
from test_stage37_targeted_repair import envelope, scripted


MODEL = "mimo-v2.6-pro"
PROJECT = "synthetic-book"
ACCOUNT = "offline"
MESSAGES = [{"role": "user", "content": "Synthetic source."}]
FIRST_USAGE = {"prompt_tokens": 1000, "completion_tokens": 2500, "total_tokens": 3500}
REPAIR_USAGE = {"prompt_tokens": 25000, "completion_tokens": 1000, "total_tokens": 26000}
CANDIDATE = json.dumps({"summary": 7, "candidate": "X" * 24000}, separators=(",", ":"))


class BookDualBudgetTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.service = SimpleNamespace(store=DeconstructionStore(self.root / "reports"))
        self.configure()

    def configure(self, local_cap=2, shared_cap=2):
        self.service.model_budget = DurableModelBudget(self.root / "shared", budget_cny=shared_cap)
        self.runner = BookAnalysis(self.service)
        self.runner._check_ready_source = lambda *args: None
        self.ledger = BudgetLedger(budget_cny=local_cap, reserve_cny=0, pricing=MIMO_PRO_PRICING)
        self.job = dict(project_id=PROJECT, account_id=ACCOUNT, run_id="same-run", model=MODEL,
                        source_version="v1", source_revision=1, source_hash="h1", cursor=0,
                        total=1, status="running", message="synthetic", budget=self.ledger.public())
        self.runner.save(self.job)

    async def call(self, runtime):
        return await self.runner._call(PROJECT, ACCOUNT, self.job, self.ledger, runtime,
                                       stage="memory", messages=deepcopy(MESSAGES),
                                       response_model=ReadingMemory, max_tokens=3000, timeout=2)

    def states(self):
        return (self.runner.load(PROJECT, ACCOUNT)["budget"], self.service.model_budget.public(MODEL))

    @staticmethod
    def replies():
        return [envelope(CANDIDATE, usage=FIRST_USAGE),
                envelope('{"summary":"synthetic memory"}', usage=REPAIR_USAGE)]

    async def test_local_cap_blocks_candidate_repair_despite_shared_headroom(self):
        # Old outer attempts=2 preflight allowed 0.018 + 0.081 = 0.099 > 0.09.
        self.configure(local_cap=0.09)
        runtime, calls = scripted(self.replies())
        with self.assertRaises(ModelBudgetExceeded):
            await self.call(runtime)
        self.assertEqual(len(calls), 1)
        for state in self.states():
            self.assertEqual(state["calls"], 1)
            self.assertEqual(state["unknown_usage_calls"], 0)
            self.assertEqual(state["pending_attempts"], {})
            self.assertAlmostEqual(state["accounted_spent_cny"], 0.018)

    async def test_shared_cap_blocks_candidate_repair_without_charging_unsent_local_hold(self):
        self.configure(shared_cap=0.09)
        runtime, calls = scripted(self.replies())
        with self.assertRaises(ModelBudgetExceeded):
            await self.call(runtime)
        self.assertEqual(len(calls), 1)
        for state in self.states():
            self.assertEqual(state["calls"], 1)
            self.assertEqual(state["unknown_usage_calls"], 0)
            self.assertEqual(state["pending_attempts"], {})
            self.assertAlmostEqual(state["accounted_spent_cny"], 0.018)

    async def test_first_shared_refusal_is_not_a_call_or_unknown_charge(self):
        self.configure(shared_cap=0.001)
        runtime, calls = scripted(self.replies())
        with self.assertRaises(ModelBudgetExceeded):
            await self.call(runtime)
        self.assertEqual(calls, [])
        for state in self.states():
            self.assertEqual(state["calls"], 0)
            self.assertEqual(state["unknown_usage_calls"], 0)
            self.assertEqual(state["pending_attempts"], {})
            self.assertEqual(state["accounted_spent_cny"], 0)

    async def test_first_local_refusal_never_reserves_shared_or_sends(self):
        self.configure(local_cap=0.001)
        runtime, calls = scripted(self.replies())
        with patch.object(self.service.model_budget, "reserve", wraps=self.service.model_budget.reserve) as reserve:
            with self.assertRaises(ModelBudgetExceeded):
                await self.call(runtime)
        reserve.assert_not_called()
        self.assertEqual(calls, [])
        self.assertEqual([state["calls"] for state in self.states()], [0, 0])

    async def test_each_http_reserves_full_repair_input_and_settles_both_ledgers(self):
        holds = []

        def inspect():
            local, shared = self.states()
            self.assertEqual(local["reserved_cny"], shared["reserved_cny"])
            self.assertEqual(len(local["pending_attempts"]), 1)
            self.assertEqual(len(shared["pending_attempts"]), 1)
            holds.append(local["reserved_cny"])

        runtime, calls = scripted(self.replies(), before_response=inspect)
        with patch.object(self.service.model_budget, "reserve", wraps=self.service.model_budget.reserve) as reserve:
            answer = await self.call(runtime)
        self.assertEqual(answer.data, {"summary": "synthetic memory"})
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(holds), 2)
        self.assertGreater(holds[1] - holds[0], len(CANDIDATE) * 3 / 1_000_000)
        for index, call in enumerate(reserve.call_args_list):
            model, messages, max_tokens = call.args
            self.assertEqual(call.kwargs["attempts"], 1)
            self.assertEqual(max_tokens, 3000)
            self.assertEqual(json.loads(messages[-1]["content"]), ReadingMemory.model_json_schema())
            self.assertAlmostEqual(holds[index], estimate_structured_call_bound(
                messages, max_tokens, model=model, attempts=1), places=6)
        for state in self.states():
            self.assertEqual(state["calls"], 2)
            self.assertEqual(state["unknown_usage_calls"], 0)
            self.assertEqual(state["pending_attempts"], {})
            self.assertAlmostEqual(state["accounted_spent_cny"], 0.099)

    async def test_first_valid_is_one_call_in_each_ledger(self):
        runtime, calls = scripted([envelope('{"summary":"ok"}', usage=FIRST_USAGE)])
        self.assertEqual((await self.call(runtime)).data, {"summary": "ok"})
        self.assertEqual(len(calls), 1)
        for state in self.states():
            self.assertEqual(state["calls"], 1)
            self.assertAlmostEqual(state["accounted_spent_cny"], 0.018)

    async def test_invalid_repair_is_not_adopted_but_both_calls_are_charged(self):
        runtime, calls = scripted([envelope(CANDIDATE, usage=FIRST_USAGE)] * 2)
        with self.assertRaises(LLMRuntimeError) as raised:
            await self.call(runtime)
        self.assertEqual(raised.exception.code, "provider_bad_json")
        self.assertEqual(len(calls), 2)
        self.assertNotIn("report", self.runner.load(PROJECT, ACCOUNT))
        for state in self.states():
            self.assertEqual(state["calls"], 2)
            self.assertAlmostEqual(state["accounted_spent_cny"], 0.036)

    async def test_incomplete_usage_retains_each_request_bound_in_both_ledgers(self):
        holds = []
        runtime, calls = scripted([envelope(CANDIDATE, usage={"total_tokens": 30000}),
                                   envelope('{"summary":"ok"}', usage={"prompt_tokens": 10})],
                                  before_response=lambda: holds.append(self.states()[0]["reserved_cny"]))
        await self.call(runtime)
        self.assertEqual(len(calls), 2)
        for state in self.states():
            self.assertEqual(state["calls"], 2)
            self.assertEqual(state["unknown_usage_calls"], 2)
            self.assertEqual(state["pending_attempts"], {})
            self.assertAlmostEqual(state["accounted_spent_cny"], sum(holds), places=6)

    async def test_provider_failure_charges_unknown_in_both_ledgers_once(self):
        runtime, calls = scripted([(500, b"synthetic failure")])
        with self.assertRaises(LLMRuntimeError):
            await self.call(runtime)
        self.assertEqual(len(calls), 1)
        local, shared = self.states()
        self.assertEqual(local["accounted_spent_cny"], shared["accounted_spent_cny"])
        for state in (local, shared):
            self.assertEqual((state["calls"], state["unknown_usage_calls"]), (1, 1))
            self.assertGreater(state["accounted_spent_cny"], 0)

    async def test_pause_after_first_response_prevents_repair_and_preserves_usage(self):
        runtime, calls = scripted(self.replies(), before_response=lambda: self.runner.pause(PROJECT, ACCOUNT))
        self.assertIsNone(await self.call(runtime))
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.runner.load(PROJECT, ACCOUNT)["status"], "paused")
        for state in self.states():
            self.assertEqual((state["calls"], state["unknown_usage_calls"]), (1, 0))
            self.assertAlmostEqual(state["accounted_spent_cny"], 0.018)

    async def test_source_guard_failure_between_holds_releases_only_unsent_requests(self):
        count = 0

        def check(*args):
            nonlocal count
            count += 1
            if count == 2:
                raise ValueError("synthetic source changed")

        self.runner._check_ready_source = check
        runtime, calls = scripted(self.replies())
        with self.assertRaisesRegex(ValueError, "synthetic source changed"):
            await self.call(runtime)
        self.assertEqual(calls, [])
        for state in self.states():
            self.assertEqual(state["pending_attempts"], {})
            self.assertEqual((state["calls"], state["unknown_usage_calls"]), (0, 0))

    async def test_either_reservation_write_failure_prevents_http(self):
        for target in (self.runner, self.service.model_budget):
            with self.subTest(target=type(target).__name__):
                runtime, calls = scripted(self.replies())
                with patch.object(target, "_save", side_effect=OSError("synthetic persistence failure")):
                    with self.assertRaises(OSError):
                        await self.call(runtime)
                self.assertEqual(calls, [])
                for state in self.states():
                    self.assertEqual(state["pending_attempts"], {})
                    self.assertEqual((state["calls"], state["unknown_usage_calls"]), (0, 0))

    async def test_file_fsync_failure_blocks_before_http(self):
        runtime, calls = scripted(self.replies())
        with patch("app.core.book_analysis.os.fsync", side_effect=OSError("synthetic sync failure")):
            with self.assertRaises(OSError):
                await self.call(runtime)
        self.assertEqual(calls, [])
        self.assertEqual(self.states()[0]["pending_attempts"], {})

    async def test_directory_sync_failure_after_replace_blocks_and_keeps_orphan_hold(self):
        runtime, calls = scripted(self.replies())
        actual_open = os.open

        def fail_directory(path, flags, *args, **kwargs):
            if Path(path) == self.runner.path(PROJECT).parent:
                raise OSError("synthetic directory sync failure")
            return actual_open(path, flags, *args, **kwargs)

        # Force the POSIX directory-sync branch on all offline CI platforms.
        with patch("app.core.book_analysis.os", SimpleNamespace(
                name="posix", open=fail_directory, fsync=os.fsync, close=os.close, O_RDONLY=os.O_RDONLY)):
            with self.assertRaises(OSError):
                await self.call(runtime)
        self.assertEqual(calls, [])
        local, shared = self.states()
        self.assertGreater(local["reserved_cny"], 0)
        self.assertEqual((local["calls"], local["unknown_usage_calls"]), (0, 0))
        self.assertEqual(shared["reserved_cny"], 0)

    async def test_unsent_release_write_failure_retains_hold_without_fake_call(self):
        self.configure(shared_cap=0.001)
        runtime, calls = scripted(self.replies())
        actual_save = self.runner.save

        def fail_release(job):
            if not job["budget"]["pending_attempts"]:
                raise OSError("synthetic release persistence failure")
            actual_save(job)

        with patch.object(self.runner, "save", side_effect=fail_release):
            with self.assertRaises(OSError):
                await self.call(runtime)
        self.assertEqual(calls, [])
        local, shared = self.states()
        self.assertGreater(local["reserved_cny"], 0)
        self.assertEqual((local["calls"], local["unknown_usage_calls"]), (0, 0))
        self.assertEqual(shared["calls"], 0)

    async def test_settlement_write_failure_settles_other_ledger_and_prevents_repair(self):
        for which in ("local", "shared"):
            with self.subTest(which=which):
                # Fresh independent fixture for each failed ledger.
                with tempfile.TemporaryDirectory() as directory:
                    self.root = Path(directory)
                    self.service.store = DeconstructionStore(self.root / "reports")
                    self.configure()
                    runtime, calls = scripted(self.replies())
                    target = self.runner if which == "local" else self.service.model_budget
                    method = "_settle_call" if which == "local" else "settle"
                    with patch.object(target, method, side_effect=OSError("synthetic settlement failure")):
                        with self.assertRaises(OSError):
                            await self.call(runtime)
                    self.assertEqual(len(calls), 1)
                    local, shared = self.states()
                    failed, settled = (local, shared) if which == "local" else (shared, local)
                    self.assertGreater(failed["reserved_cny"], 0)
                    self.assertEqual(failed["calls"], 0)
                    self.assertEqual(settled["pending_attempts"], {})
                    self.assertEqual(settled["calls"], 1)
                    self.assertAlmostEqual(settled["accounted_spent_cny"], 0.018)

    async def test_cancelled_http_keeps_both_holds_across_restart(self):
        entered, release = threading.Event(), threading.Event()

        def wait_in_transport():
            entered.set()
            if not release.wait(timeout=3):
                raise AssertionError("synthetic transport not released")

        runtime, calls = scripted([envelope('{"summary":"ok"}')], before_response=wait_in_transport)
        task = asyncio.create_task(self.call(runtime))
        try:
            self.assertTrue(await asyncio.to_thread(entered.wait, 1))
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        finally:
            release.set()
        self.assertEqual(len(calls), 1)
        before = self.states()
        self.runner = BookAnalysis(self.service)
        self.service.model_budget = DurableModelBudget(self.root / "shared", budget_cny=10)
        self.assertEqual(before, self.states())
        for state in before:
            self.assertGreater(state["reserved_cny"], 0)
            self.assertEqual((state["calls"], state["unknown_usage_calls"]), (0, 0))

    async def test_fake_runtime_still_reserves_two_attempts_in_both_ledgers(self):
        holds = []

        async def respond(**kwargs):
            holds.extend(state["reserved_cny"] for state in self.states())
            return LLMResult(call_id="fake", text="", data={"summary": "ok"}, usage=LLMUsage(known=False))

        runtime = SimpleNamespace(model=MODEL, structured=respond)
        with patch.object(self.service.model_budget, "reserve", wraps=self.service.model_budget.reserve) as reserve:
            await self.call(runtime)
        self.assertEqual(reserve.call_args.kwargs["attempts"], 2)
        self.assertEqual(holds[0], holds[1])
        for state in self.states():
            self.assertEqual((state["calls"], state["unknown_usage_calls"]), (1, 1))
            self.assertAlmostEqual(state["accounted_spent_cny"], holds[0], places=6)

    async def test_concurrent_runner_instances_cannot_overbook_job_cap(self):
        self.configure(local_cap=0.07)
        barrier = threading.Barrier(2)

        def reserve():
            runner = BookAnalysis(self.service)
            budget = _BookCallBudget(runner, self.job)
            barrier.wait(timeout=2)
            try:
                return budget.reserve(MODEL, MESSAGES, 3000, stage="concurrent")
            except ModelBudgetExceeded:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: reserve(), range(2)))
        self.assertEqual(sum(token is not None for token in results), 1)
        state = self.states()[0]
        self.assertEqual(len(state["pending_attempts"]), 1)
        self.assertLess(state["reserved_cny"], state["budget_cny"])

    async def test_stale_progress_write_cannot_erase_new_budget_and_pause_wins(self):
        stale = deepcopy(self.job)
        budget = _BookCallBudget(self.runner, self.job)
        token = budget.reserve(MODEL, MESSAGES, 3000, stage="synthetic")
        budget.settle(MODEL, token, LLMResult(call_id="synthetic", text="", usage=LLMUsage(known=False)), stage="synthetic")
        before = self.states()[0]
        self.runner._update_running(stale, {"memory": "synthetic progress"})
        self.assertEqual(self.states()[0], before)
        self.runner.pause(PROJECT, ACCOUNT)
        adopted = []
        self.assertIsNone(self.runner._update_running(stale, {"status": "completed"}, before_save=lambda: adopted.append(True)))
        self.assertEqual(adopted, [])
        self.assertEqual(self.runner.load(PROJECT, ACCOUNT)["status"], "paused")
        self.assertEqual(self.states()[0], before)
