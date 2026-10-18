"""Serial chapter preview through real structured parsing and synthetic HTTP only."""
import asyncio
from copy import deepcopy
import json
import threading
import unittest
from unittest.mock import patch

from app import deconstruction_routes
from app.agents import deconstruction_model
from app.core.model_call_budget import DurableModelBudget
from schemas.analysis_report import AnalysisRequest, AnalysisImport
import test_stage31_deconstruction as base
from chapter_preview_fixtures import chapter_case
from test_stage37_preview_capacity import wire_bound, MODEL


class ChapterPreviewApiTest(unittest.TestCase):
    setUp = base.Stage31DeconstructionApiTest.setUp
    _cleanup = base.Stage31DeconstructionApiTest._cleanup
    _login = base.Stage31DeconstructionApiTest._login
    _project = base.Stage31DeconstructionApiTest._project
    _encoded = staticmethod(base.Stage31DeconstructionApiTest._encoded)

    def prepare(self, count=2):
        self.project = self._project()
        _, _, _, texts = chapter_case(count)
        manuscript = "\n\n".join(f"# 第{n}章 渡口{n}\n{text}" for n, text in texts.items())
        preview = self.client.post(f"/api/independent/projects/{self.project}/imports/preview",
            json={"filename": "合成章包.md", "content_base64": self._encoded(manuscript)})
        self.assertEqual(preview.status_code, 200, preview.text)
        confirmed = self.client.post(f"/api/independent/projects/{self.project}/imports/{preview.json()['preview']['preview_id']}/confirm")
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.deconstruction.process_background_tasks()
        self.account = self.independent.store.load(self.project).account_id
        self.source = self.deconstruction._source(self.project, self.account)
        self.assertEqual(len(self.source.chapters), count)
        self.packets, self.outcome, self.bank, self.texts = chapter_case(
            texts={c.chapter_number: c.content for c in self.source.chapters})
        self.url = f"/api/independent/projects/{self.project}/deconstruction"
        state = self.client.get(self.url).json()
        self.body = {"expected_source_version_id": state["source"]["version_id"],
            "expected_source_revision": state["source"]["revision"], "expected_source_hash": state["source"]["hash"],
            "chapter_numbers": sorted(self.texts)}
        self.old_report = self.deconstruction.store.load(self.project).model_dump(mode="json")
        self.old_author = self.independent.store.load(self.project).model_dump(mode="json")
        self.budget = DurableModelBudget(self.deconstruction.store.base_dir / "chapter-budget" / self.project, budget_cny=5)
        self.deconstruction.model_budget = self.budget

    def scripted(self, replies, *, hook=None, unknown_at=()):
        self.calls, self.holds = [], []
        runtime = deconstruction_model.create_runtime(deconstruction_model.DeconstructionModelSettings(
            _env_file=None, api_key="synthetic-only", model=MODEL, base_url="https://api.xiaomimimo.com/v1"))
        def transport(*args):
            call = json.loads(args[2])
            self.calls.append(call)
            index = len(self.calls)
            self.holds.append(self.budget.public(MODEL))
            self.assertLessEqual(index, len(replies), "Unexpected automatic semantic retry or later chapter")
            if hook:
                hook(index)
            envelope = {"choices": [{"message": {"content": json.dumps(replies[index - 1], ensure_ascii=False)}, "finish_reason": "stop"}]}
            if index not in unknown_at:
                envelope["usage"] = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
            return 200, json.dumps(envelope).encode()
        runtime._transport = transport
        return runtime

    def run_preview(self, replies=None, **options):
        runtime = self.scripted(replies if replies is not None else [*self.packets, self.outcome], **options)
        with patch.object(deconstruction_routes, "create_runtime", return_value=runtime):
            return self.client.post(self.url + "/analyze-preview", json=self.body)

    def unchanged(self, *, author=True):
        self.assertEqual(self.deconstruction.store.load(self.project).model_dump(mode="json"), self.old_report)
        if author:
            self.assertEqual(self.independent.store.load(self.project).model_dump(mode="json"), self.old_author)

    def mutate_source(self, _):
        record = self.independent.store.load(self.project)
        version = next(v for v in record.versions if v.version_id == record.active_version_id)
        version.chapters[0].formal_content += "作者保存的合成变更。"
        version.chapters[0].server_revision += 1
        self.independent.store.save(record)

    def drain_budget(self, _):
        ledger = self.budget._load(MODEL)
        ledger.spent_cny = ledger.budget_cny - sum(ledger.pending_attempts.values())
        self.budget._save(ledger, self.budget._records())

    def test_two_and_six_chapter_success_exact_source_and_public_import(self):
        for count in (2, 6):
            with self.subTest(chapters=count):
                self.prepare(count)
                response = self.run_preview()
                self.assertEqual(response.status_code, 200, response.text)
                result = AnalysisImport.model_validate(response.json(), strict=True)
                self.assertEqual(result.report.chapter_numbers, list(range(1, count + 1)))
                self.assertEqual(len(self.calls), count + 1)
                self.assertEqual([c["max_completion_tokens"] for c in self.calls], [12288] * count + [24576])
                for n, call in enumerate(self.calls[:-1], 1):
                    material = json.loads(call["messages"][1]["content"].split("\n", 1)[1])
                    self.assertEqual([c["chapter_number"] for c in material["chapters"]], [n])
                    self.assertEqual("".join(s["text"] for s in material["chapters"][0]["segments"]), self.texts[n])
                    self.assertNotIn(self.texts[n], call["messages"][0]["content"])
                final = json.loads(self.calls[-1]["messages"][1]["content"].split("\n", 1)[1])
                self.assertEqual(["".join(s["text"] for s in c["segments"]) for c in final["chapters"]], list(self.texts.values()))
                self.assertEqual([p["atoms"][0]["id"] for p in final["chapter_facts"]], [f"H{n}_A" for n in self.texts])
                self.assertEqual(self.budget.public(MODEL)["calls"], count + 1)
                self.unchanged()
                imported = self.client.post(self.url + "/import", json=response.json())
                self.assertEqual(imported.status_code, 200, imported.text)
                self.assertEqual(self.independent.store.load(self.project).model_dump(mode="json"), self.old_author)

    def test_six_chapters_every_format_repair_obeys_fourteen_bound_and_actual_reservations(self):
        self.prepare(6)
        replies = []
        for packet in [*self.packets, self.outcome]:
            replies.extend([{**deepcopy(packet), "extra": "失败候选必须计入完整预留" * 400}, packet])
        response = self.run_preview(replies)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.calls), 14)
        self.assertEqual([c["max_completion_tokens"] for c in self.calls], [12288] * 12 + [24576] * 2)
        records = json.loads(self.budget.path.read_text())["records"]
        self.assertEqual(len(records), 14)
        for i, (call, record) in enumerate(zip(self.calls, records, strict=True)):
            self.assertEqual(call["thinking"], {"type": "disabled"})
            self.assertAlmostEqual(record["reserved_cny"], wire_bound(call), places=12)
            self.assertGreater(self.holds[i]["reserved_cny"], 0)
            if i % 2:
                self.assertGreater(record["reserved_cny"], records[i - 1]["reserved_cny"])
        self.assertEqual((self.budget.public(MODEL)["calls"], self.budget.public(MODEL)["reserved_cny"]), (14, 0))
        self.unchanged()

    def test_chapter_semantic_freeze_failure_stops_without_repair_or_later_steps(self):
        self.prepare(6)
        bad = deepcopy(self.packets[1])
        bad["atoms"][0]["subject_id"] = "null"
        response = self.run_preview([self.packets[0], bad])
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["detail"]["code"], "report_facts_invalid")
        self.assertEqual(len(self.calls), 2)
        self.unchanged()

    def test_chapter_structural_failure_gets_only_one_repair_then_stops(self):
        self.prepare(6)
        response = self.run_preview([self.packets[0], {}, {}])
        self.assertEqual(response.status_code, 502, response.text)
        self.assertEqual(len(self.calls), 3)
        self.unchanged()

    def blocker(self):
        return {"outcome": "blocked", "issues": [{"text": "第二章身份归属不足，不能据冻结事实生成确定人物。",
            "source_ids": self.packets[1]["atoms"][0]["source_ids"], "fact_ids": ["H2_A"]}]}

    def test_valid_blocked_is_final_sourced_failure_no_repair_and_retains_spent(self):
        self.prepare()
        blocked = self.blocker()
        response = self.run_preview([*self.packets, blocked])
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["detail"]["code"], "report_source_blocked")
        self.assertEqual(response.json()["detail"]["data"]["issues"], blocked["issues"])
        self.assertNotIn("report", response.json())
        self.assertEqual(len(self.calls), 3)
        state = self.budget.public(MODEL)
        self.assertEqual((state["calls"], state["reserved_cny"], state["unknown_usage_calls"]), (3, 0, 0))
        self.assertAlmostEqual(state["accounted_spent_cny"], 3 * 0.00042)
        self.unchanged()

    def test_real_structured_union_rejects_mixed_success_and_empty_issues(self):
        for mixed in ("empty", "blocked-with-report", "success-with-issues"):
            with self.subTest(mixed=mixed):
                self.prepare()
                bad = {"outcome": "blocked", "issues": []}
                if mixed == "blocked-with-report":
                    bad = {**self.blocker(), "report": self.outcome["report"]}
                elif mixed == "success-with-issues":
                    bad = {**self.outcome, "issues": self.blocker()["issues"]}
                response = self.run_preview([*self.packets, bad, bad])
                self.assertEqual(response.status_code, 502, response.text)
                self.assertEqual(len(self.calls), 4)
                self.unchanged()

    def test_invalid_blocker_source_is_rejected_without_semantic_retry(self):
        self.prepare()
        bad = self.blocker()
        bad["issues"][0]["source_ids"] = ["S99_" + "0" * 20]
        response = self.run_preview([*self.packets, bad])
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["detail"]["code"], "report_evidence_invalid")
        self.assertEqual(len(self.calls), 3)
        self.unchanged()

    def test_source_cas_between_chapters_before_global_and_before_repair_or_return(self):
        for at, repair in ((1, False), (2, False), (2, True), (3, True), (3, False)):
            with self.subTest(at=at, repair=repair):
                self.prepare()
                replies = [self.packets[0], {} if repair and at == 2 else self.packets[1],
                           {} if repair and at == 3 else self.outcome]
                response = self.run_preview(replies, hook=lambda n: self.mutate_source(n) if n == at else None)
                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(response.json()["detail"]["code"], "source_conflict")
                self.assertEqual(len(self.calls), at)
                self.unchanged(author=False)

    def test_budget_exhaustion_stops_next_chapter_global_or_growing_repair(self):
        for at, repair in ((1, False), (2, False), (2, True), (3, True)):
            with self.subTest(at=at, repair=repair):
                self.prepare()
                replies = [self.packets[0], {} if repair and at == 2 else self.packets[1],
                           {**self.outcome, "extra": "完整增长候选" * 600} if repair and at == 3 else self.outcome]
                response = self.run_preview(replies, hook=lambda n: self.drain_budget(n) if n == at else None)
                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(response.json()["detail"]["code"], "model_budget_exceeded")
                self.assertEqual(len(self.calls), at)
                state = self.budget.public(MODEL)
                self.assertEqual(state["reserved_cny"], 0)
                self.assertEqual(DurableModelBudget(self.budget.directory, budget_cny=10).public(MODEL), state)
                self.unchanged()

    def test_unknown_chapter_usage_persists_conservative_cost_and_stops_if_exhausted(self):
        self.prepare()
        def drain(n):
            if n == 2:
                self.drain_budget(n)
        response = self.run_preview(self.packets, hook=drain, unknown_at={2})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(len(self.calls), 2)
        state = self.budget.public(MODEL)
        self.assertEqual(state["unknown_usage_calls"], 1)
        record = json.loads(self.budget.path.read_text())["records"][-1]
        self.assertFalse(record["usage_known"])
        self.assertGreater(record["estimated_cost_cny"], 0)
        self.assertEqual(record["estimated_cost_cny"], record["reserved_cny"])
        self.assertEqual(DurableModelBudget(self.budget.directory, budget_cny=10).public(MODEL), state)
        self.unchanged()

    def test_cancelled_second_chapter_keeps_inflight_hold_and_never_calls_final(self):
        self.prepare()
        entered, release = threading.Event(), threading.Event()
        def block(n):
            if n == 2:
                entered.set()
                if not release.wait(timeout=3):
                    raise AssertionError("Synthetic transport not released")
        runtime = self.scripted(self.packets, hook=block)
        async def cancel():
            task = asyncio.create_task(self.deconstruction.analyze_preview(self.project, self.account,
                AnalysisRequest.model_validate(self.body, strict=True), runtime))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 1))
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            finally:
                release.set()
        asyncio.run(cancel())
        self.assertEqual(len(self.calls), 2)
        state = self.budget.public(MODEL)
        self.assertEqual(state["calls"], 1)
        self.assertGreater(state["reserved_cny"], 0)
        self.assertEqual(DurableModelBudget(self.budget.directory, budget_cny=10).public(MODEL), state)
        self.unchanged()
