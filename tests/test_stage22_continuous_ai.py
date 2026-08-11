from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from app.agents.llm_runtime import LLMResult, LLMUsage
from app.core.ai_service import AIServiceError, AIStudioService
from app.core.ai_store import AIStore
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore

from tests.test_stage18_ai_text_pipeline import Stage18PipelineRuntime
from schemas.ai import DirectorReviewResponse


class Stage22Fixture:
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        projects = JsonProjectStore(root / "projects")
        independent = IndependentWorkspaceService(store=IndependentStore(root / "independent"), projects=projects)
        self.runtime = Stage18PipelineRuntime()
        self.ai = AIStudioService(
            store=AIStore(root / "ai"),
            projects=projects,
            manuscript=independent,
            runtime=self.runtime,
        )
        self.project_id = "stage22-continuous-project"
        self.account_id = "stage22-continuous-account"
        asyncio.run(self.ai.send_message(self.project_id, self.account_id, "主角是林舟，顾遥守住一封回信。"))
        workspace = self.ai.workspace(self.project_id, self.account_id)
        self.ai.confirm_blueprint(
            self.project_id,
            self.account_id,
            workspace["blueprint_revision"],
            "stage22-confirm",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run_and_choose(self, key: str) -> dict:
        waiting = asyncio.run(
            self.ai.start_director(
                self.project_id,
                self.account_id,
                strategy="pause_at_key_nodes",
                idempotency_key=key,
                defer=False,
            )
        )
        run = waiting["active_run"]
        self.assertEqual(run["status"], "waiting_for_choice")
        self.assertEqual(len(run["choices"]), 3)
        return asyncio.run(self.ai.choose(self.project_id, self.account_id, run["run_id"], "role"))

    def _assert_system_chapters_are_not_author_pending_changes_and_three_runs_are_sequential(self) -> None:
        for index in range(1, 4):
            completed = self._run_and_choose(f"stage22-run-{index}")
            self.assertEqual(completed["active_run"]["status"], "completed")
            self.assertEqual(completed["active_run"]["chapter_number"], index)
            self.assertEqual(completed["active_run"]["selected_choice_id"], "role")

        manuscript = self.ai.manuscript.workspace(self.project_id, self.account_id)
        active = manuscript["active_version"]
        self.assertEqual(len(active.chapters), 3)
        self.assertIsNone(manuscript["pending_changes"])
        self.assertEqual(
            [snapshot.chapter_number for snapshot in active.archive.snapshots],
            [1, 2, 3],
        )
        workspace = self.ai.workspace(self.project_id, self.account_id)
        self.assertEqual(len({run["run_id"] for run in workspace["runs"]}), 3)
        self.assertTrue(all(run["selected_choice_id"] for run in workspace["runs"]))
        self.assertEqual(
            sum(item.kind == "director_completed" for item in self.ai.store.load(self.project_id).notifications),
            3,
        )
        self.assertEqual(len(active.archive.snapshots), 3)
        self.assertEqual(len(manuscript["versions"]), 1)
        self.assertTrue(all(not item.result for item in self.ai.store.load(self.project_id).model_calls))

    def _assert_author_edit_still_creates_pending_changes(self) -> None:
        completed = self._run_and_choose("stage22-author-edit")
        self.assertEqual(completed["active_run"]["status"], "completed")
        manuscript = self.ai.manuscript.workspace(self.project_id, self.account_id)
        chapter = manuscript["active_version"].chapters[0]
        self.ai.manuscript.save_draft(
            self.project_id,
            self.account_id,
            chapter.chapter_id,
            content=chapter.content + "作者手工修改。",
            title=chapter.title,
            expected_revision=chapter.server_revision,
        )
        after = self.ai.manuscript.workspace(self.project_id, self.account_id)
        self.assertIsNotNone(after["pending_changes"])
        self.assertEqual(len(after["pending_changes"].changes), 1)

    def _assert_review_retry_reuses_successful_body(self) -> None:
        self.runtime.fail_review_once = True
        failed = self._run_and_choose("stage22-retry-cache")
        self.assertEqual(failed["active_run"]["status"], "failed")
        first_text_calls = len(self.runtime.text_calls)
        retry_waiting = asyncio.run(self.ai.retry(self.project_id, self.account_id, failed["active_run"]["run_id"]))
        self.assertEqual(retry_waiting["active_run"]["status"], "waiting_for_choice")
        completed = asyncio.run(
            self.ai.choose(self.project_id, self.account_id, failed["active_run"]["run_id"], "role")
        )
        self.assertEqual(completed["active_run"]["status"], "completed")
        self.assertEqual(len(self.runtime.text_calls), first_text_calls)
        self.assertEqual(len(self.ai.manuscript.workspace(self.project_id, self.account_id)["active_version"].chapters), 1)

    def _assert_service_recreation_recovers_completed_work(self) -> None:
        first = self._run_and_choose("stage22-restart-1")
        self.assertEqual(first["active_run"]["chapter_number"], 1)
        restarted = AIStudioService(
            store=self.ai.store,
            projects=self.ai.projects,
            manuscript=self.ai.manuscript,
            runtime=Stage18PipelineRuntime(),
        )
        recovered = restarted.workspace(self.project_id, self.account_id)
        self.assertEqual(recovered["active_run"]["status"], "completed")
        second = asyncio.run(
            restarted.start_director(
                self.project_id,
                self.account_id,
                strategy="pause_at_key_nodes",
                idempotency_key="stage22-restart-2",
                defer=False,
            )
        )
        self.assertEqual(second["active_run"]["chapter_number"], 2)
        completed = asyncio.run(
            restarted.choose(self.project_id, self.account_id, second["active_run"]["run_id"], "role")
        )
        self.assertEqual(completed["active_run"]["status"], "completed")

    def _assert_pending_choice_resumes_in_server_worker(self) -> None:
        waiting = asyncio.run(
            self.ai.start_director(
                self.project_id,
                self.account_id,
                strategy="pause_at_key_nodes",
                idempotency_key="stage22-worker-choice",
                defer=False,
            )
        )
        record = self.ai.store.load(self.project_id)
        assert record is not None
        run = next(item for item in record.runs if item.run_id == waiting["active_run"]["run_id"])
        run.pending_choice_id = "role"
        self.ai.store.save(record)
        processed = asyncio.run(self.ai.process_background_runs_async())
        self.assertGreaterEqual(processed, 1)
        recovered = self.ai.workspace(self.project_id, self.account_id)
        self.assertEqual(recovered["active_run"]["status"], "completed")
        self.assertEqual(recovered["active_run"]["selected_choice_id"], "role")

    def _assert_concurrent_choice_and_worker_commit_once(self) -> None:
        waiting = asyncio.run(
            self.ai.start_director(
                self.project_id,
                self.account_id,
                strategy="pause_at_key_nodes",
                idempotency_key="stage22-concurrent-choice",
                defer=False,
            )
        )
        run_id = waiting["active_run"]["run_id"]

        async def choose_and_scan() -> tuple[dict, int]:
            choose_task = asyncio.create_task(
                self.ai.choose(self.project_id, self.account_id, run_id, "role")
            )
            worker_task = asyncio.create_task(self.ai.process_background_runs_async())
            chosen, processed = await asyncio.gather(choose_task, worker_task)
            return chosen, processed

        chosen, _processed = asyncio.run(choose_and_scan())
        self.assertEqual(chosen["active_run"]["status"], "completed")
        record = self.ai.store.load(self.project_id)
        assert record is not None
        manuscript = self.ai.manuscript.workspace(self.project_id, self.account_id)
        self.assertEqual(len(manuscript["active_version"].chapters), 1)
        self.assertEqual(len(record.runs), 1)
        self.assertEqual(record.runs[0].selected_choice_id, "role")
        self.assertEqual(sum(item.kind == "director_completed" for item in record.notifications), 1)
        self.assertEqual(len(manuscript["active_version"].archive.snapshots), 1)

    def _assert_recover_formal_body_when_text_cache_is_missing(self) -> None:
        completed = self._run_and_choose("stage22-formal-recovery")
        run_id = completed["active_run"]["run_id"]
        record = self.ai.store.load(self.project_id)
        assert record is not None
        run = next(item for item in record.runs if item.run_id == run_id)
        run.status = "failed"
        run.current_stage = "失败，可重试"
        run.selected_choice_id = None
        run.choice_source = "none"
        run.generated_content = ""
        run.error_message = "测试注入的可恢复失败"
        record.text_cache.clear()
        self.ai.store.save(record)
        text_calls_before = len(self.runtime.text_calls)

        waiting = asyncio.run(self.ai.retry(self.project_id, self.account_id, run_id))
        self.assertEqual(waiting["active_run"]["status"], "waiting_for_choice")
        recovered = asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))
        self.assertEqual(recovered["active_run"]["status"], "completed")
        self.assertEqual(len(self.runtime.text_calls), text_calls_before)
        manuscript = self.ai.manuscript.workspace(self.project_id, self.account_id)
        self.assertIsNone(manuscript["pending_changes"])
        self.assertEqual(len(manuscript["active_version"].chapters), 1)


class Stage22FailingArchiveService(AIStudioService):
    def _apply_live_archive(self, record, run, review, archive_update) -> None:  # type: ignore[no-untyped-def]
        raise AIServiceError("archive_commit_failed", "档案提交失败，请重试。", status_code=500)


class Stage22ContinuousAIRegressionTest(Stage22Fixture, unittest.TestCase):
    def test_system_chapters_are_not_author_pending_changes_and_three_runs_are_sequential(self) -> None:
        self._assert_system_chapters_are_not_author_pending_changes_and_three_runs_are_sequential()

    def test_author_edit_still_creates_pending_changes(self) -> None:
        self._assert_author_edit_still_creates_pending_changes()

    def test_review_retry_reuses_successful_body(self) -> None:
        self._assert_review_retry_reuses_successful_body()

    def test_service_recreation_recovers_completed_work(self) -> None:
        self._assert_service_recreation_recovers_completed_work()

    def test_pending_choice_resumes_in_server_worker(self) -> None:
        self._assert_pending_choice_resumes_in_server_worker()

    def test_concurrent_choice_and_worker_commit_once(self) -> None:
        self._assert_concurrent_choice_and_worker_commit_once()

    def test_recover_formal_body_when_text_cache_is_missing(self) -> None:
        self._assert_recover_formal_body_when_text_cache_is_missing()


class Stage22AtomicAndUsageRegressionTest(Stage22Fixture, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ai = Stage22FailingArchiveService(
            store=self.ai.store,
            projects=self.ai.projects,
            manuscript=self.ai.manuscript,
            runtime=self.runtime,
        )

    def test_archive_failure_has_no_formal_chapter_and_keeps_all_safe_call_usage(self) -> None:
        failed = self._run_and_choose("stage22-archive-failure")
        self.assertEqual(failed["active_run"]["status"], "failed")
        manuscript = self.ai.manuscript.workspace(self.project_id, self.account_id)
        self.assertEqual(manuscript["active_version"].chapters[0].formal_content, "")
        self.assertEqual(manuscript["archive"].snapshots, [])
        self.assertFalse(any(item.kind == "director_completed" for item in self.ai.store.load(self.project_id).notifications))
        record = self.ai.store.load(self.project_id)
        assert record is not None
        runtime_call_count = len(self.runtime.calls) + len(self.runtime.text_calls)
        self.assertEqual(len(record.model_calls), runtime_call_count)
        self.assertTrue(all(item.usage.total_tokens > 0 for item in record.model_calls))


class Stage22UnknownUsageRuntime(Stage18PipelineRuntime):
    async def structured(self, *, call_id: str, messages: list[dict[str, str]], response_model: type, max_tokens: int) -> LLMResult:
        if response_model is DirectorReviewResponse:
            self.calls.append({"call_id": call_id, "stage": response_model.__name__, "messages": messages, "max_tokens": max_tokens})
            return LLMResult(
                call_id=call_id,
                text='{"summary":"缺少来源章节"}',
                data={"summary": "缺少来源章节"},
                provider=self.provider,
                model=self.model,
                usage=LLMUsage(prompt_tokens=13, completion_tokens=17, total_tokens=30),
                latency_ms=23,
            )
        return await super().structured(call_id=call_id, messages=messages, response_model=response_model, max_tokens=max_tokens)


class Stage22UsageObservabilityTest(Stage22Fixture, unittest.TestCase):
    def test_failed_provider_without_usage_is_explicit_unknown(self) -> None:
        self.runtime.fail_review_once = True
        failed = self._run_and_choose("stage22-unknown-usage")
        self.assertEqual(failed["active_run"]["status"], "failed")
        record = self.ai.store.load(self.project_id)
        assert record is not None
        review_call = next(item for item in record.model_calls if item.stage == "reviewing")
        self.assertFalse(review_call.usage_known)
        self.assertEqual(review_call.usage.total_tokens, 0)
        self.assertGreaterEqual(self.ai.workspace(self.project_id, self.account_id)["model_runtime"]["usage_unknown_calls"], 1)

    def test_invalid_structured_result_keeps_provider_usage_metadata(self) -> None:
        self.runtime = Stage22UnknownUsageRuntime()
        self.ai.runtime = self.runtime
        failed = self._run_and_choose("stage22-invalid-usage")
        self.assertEqual(failed["active_run"]["status"], "failed")
        record = self.ai.store.load(self.project_id)
        assert record is not None
        review_call = next(item for item in record.model_calls if item.stage == "reviewing")
        self.assertTrue(review_call.usage_known)
        self.assertEqual(review_call.usage.total_tokens, 30)
        self.assertEqual(review_call.latency_ms, 23)


if __name__ == "__main__":
    unittest.main()
