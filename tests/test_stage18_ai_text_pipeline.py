from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from app.agents.llm_runtime import LLMResult, LLMRuntimeError, LLMUsage
from app.core.ai_service import AIStudioService
from app.core.ai_store import AIStore
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore
from app.core.ai_service import LIVE_AI_LABEL
from schemas.ai import DirectorArchiveResponse, DirectorReviewResponse

from tests.test_stage15_model_runtime import FakeRuntime


def body_text(length: int = 1500) -> str:
    seed = "“她把信纸展开：‘如果你读到这里，就说明门已经开了。’林舟看见{蓝色纸角}，没有立即回答。”\n"
    return (seed * ((length // len(seed)) + 2))[:length]


class Stage18PipelineRuntime(FakeRuntime):
    def __init__(self) -> None:
        super().__init__()
        self.text_outputs: list[str] = []
        self.text_calls: list[dict[str, object]] = []
        self.fail_review_once = False

    async def text(self, *, call_id: str, messages: list[dict[str, str]], max_tokens: int, validator=None) -> LLMResult:
        self.text_calls.append({"call_id": call_id, "stage": "body_generation", "messages": messages, "max_tokens": max_tokens})
        content = self.text_outputs.pop(0) if self.text_outputs else body_text()
        return LLMResult(
            call_id=call_id,
            text=content,
            provider=self.provider,
            model=self.model,
            usage=LLMUsage(prompt_tokens=3, completion_tokens=8, total_tokens=11),
            latency_ms=7,
        )

    async def structured(self, *, call_id: str, messages: list[dict[str, str]], response_model: type, max_tokens: int) -> LLMResult:
        if response_model is DirectorReviewResponse:
            self.calls.append({"call_id": call_id, "stage": response_model.__name__, "messages": messages, "max_tokens": max_tokens})
            if self.fail_review_once:
                self.fail_review_once = False
                raise LLMRuntimeError(
                    "provider_timeout",
                    "模型服务响应超时，请稍后重试。",
                    retryable=True,
                    status_code=504,
                )
            payload = json.loads(messages[-1]["content"])
            data = {
                "source_chapter": payload["chapter_number"],
                "summary": "审校确认正文中的公开行动与当前选择一致，不确定内容保留为疑问点。",
                "public_character_updates": ["林舟确认了公开线索。"],
            }
            return LLMResult(
                call_id=call_id,
                text=json.dumps(data, ensure_ascii=False),
                data=data,
                provider=self.provider,
                model=self.model,
                usage=LLMUsage(prompt_tokens=4, completion_tokens=5, total_tokens=9),
                latency_ms=6,
            )
        if response_model is DirectorArchiveResponse:
            self.calls.append({"call_id": call_id, "stage": response_model.__name__, "messages": messages, "max_tokens": max_tokens})
            payload = json.loads(messages[-1]["content"])
            data = {
                "source_chapter": payload["chapter_number"],
                "plotline_updates": ["追查旧档案的主线继续推进。"],
                "foreshadowing_candidates": ["蓝色纸角的出处仍待回看。"],
                "question_points": ["顾遥的隐瞒是否会改变关系线？"],
            }
            return LLMResult(
                call_id=call_id,
                text=json.dumps(data, ensure_ascii=False),
                data=data,
                provider=self.provider,
                model=self.model,
                usage=LLMUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
                latency_ms=6,
            )
        return await super().structured(
            call_id=call_id,
            messages=messages,
            response_model=response_model,
            max_tokens=max_tokens,
        )


class Stage18AITextPipelineTest(unittest.TestCase):
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
        self.project_id = "stage18-text-project"
        self.account_id = "stage18-text-account"
        asyncio.run(self.ai.send_message(self.project_id, self.account_id, "主角是林舟，顾遥守住一封回信。"))
        workspace = self.ai.workspace(self.project_id, self.account_id)
        self.ai.confirm_blueprint(
            self.project_id,
            self.account_id,
            workspace["blueprint_revision"],
            "stage18-confirm",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def start_waiting(self) -> dict:
        return asyncio.run(
            self.ai.start_director(
                self.project_id,
                self.account_id,
                strategy="pause_at_key_nodes",
                idempotency_key="stage18-run",
                defer=False,
            )
        )

    def test_body_is_text_then_review_and_archive_are_structured_and_idempotent(self) -> None:
        waiting = self.start_waiting()
        run_id = waiting["active_run"]["run_id"]
        completed = asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))

        self.assertEqual(completed["active_run"]["status"], "completed")
        self.assertEqual(len(completed["active_run"]["generated_content"]), 1500)
        self.assertEqual(completed["active_run"]["archive_source_chapter"], 1)
        self.assertEqual({call["stage"] for call in self.runtime.calls if call["stage"] in {"DirectorReviewResponse", "DirectorArchiveResponse"}}, {"DirectorReviewResponse", "DirectorArchiveResponse"})
        self.assertEqual(len(self.runtime.text_calls), 1)
        self.assertNotIn("DirectorBodyResponse", {str(call["stage"]) for call in self.runtime.calls})

        record = self.ai.store.load(self.project_id)
        assert record is not None
        body_call = next(call for call in record.model_calls if call.stage == "body_generation")
        self.assertEqual(body_call.status, "completed")
        self.assertNotIn("result", body_call.model_dump(mode="json"))
        self.assertTrue(record.text_cache)
        manuscript = self.ai.manuscript.workspace(self.project_id, self.account_id)
        self.assertEqual(len(manuscript["active_version"].chapters[0].content), 1500)
        self.assertEqual(manuscript["archive"].analysis_label, LIVE_AI_LABEL)
        self.assertEqual(len(manuscript["archive"].characters), 2)
        self.assertEqual(len(manuscript["archive"].storylines), 1)
        self.assertEqual(len(manuscript["archive"].foreshadowing), 1)
        self.assertEqual(manuscript["archive"].storylines[0].source_chapter_number, 1)
        self.assertEqual(manuscript["archive"].snapshots[-1].analysis_label, LIVE_AI_LABEL)
        self.assertNotIn("text_cache", completed)

        call_count = len(self.runtime.calls) + len(self.runtime.text_calls)
        duplicate = asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))
        self.assertEqual(duplicate["active_run"]["status"], "completed")
        self.assertEqual(len(self.runtime.calls) + len(self.runtime.text_calls), call_count)
        self.assertEqual(len(self.ai.manuscript.workspace(self.project_id, self.account_id)["active_version"].chapters), 1)

    def test_private_sentinel_in_text_rejects_whole_chapter_and_archive(self) -> None:
        secret = "顾遥私有哨兵·白色回声"
        record = self.ai.store.load(self.project_id)
        assert record is not None
        next(agent for agent in record.story_characters if agent.name == "顾遥").private_memory = [secret]
        self.ai.store.save(record)
        self.runtime.text_outputs = [("正文推进。" + secret) * 200]

        waiting = self.start_waiting()
        failed = asyncio.run(self.ai.choose(self.project_id, self.account_id, waiting["active_run"]["run_id"], "role"))

        self.assertEqual(failed["active_run"]["status"], "failed")
        self.assertEqual(failed["active_run"]["generated_content"], "")
        self.assertFalse(any(call["stage"] == "DirectorArchiveResponse" for call in self.runtime.calls))
        record = self.ai.store.load(self.project_id)
        assert record is not None
        self.assertFalse(record.text_cache)
        manuscript = self.ai.manuscript.workspace(self.project_id, self.account_id)
        self.assertEqual(manuscript["active_version"].chapters[0].content, "")
        self.assertNotIn(secret, json.dumps(failed, ensure_ascii=False, default=str))

    def test_review_failure_keeps_body_pending_and_retry_reuses_body_without_duplicate_chapter(self) -> None:
        self.runtime.fail_review_once = True
        waiting = self.start_waiting()
        run_id = waiting["active_run"]["run_id"]
        failed = asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))
        self.assertEqual(failed["active_run"]["status"], "failed")
        self.assertEqual(len(self.runtime.text_calls), 1)
        self.assertEqual(self.ai.manuscript.workspace(self.project_id, self.account_id)["active_version"].chapters[0].content, "")

        completed = asyncio.run(self.ai.retry(self.project_id, self.account_id, run_id))
        self.assertEqual(completed["active_run"]["status"], "waiting_for_choice")
        completed = asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))
        self.assertEqual(completed["active_run"]["status"], "completed")
        self.assertEqual(len(self.runtime.text_calls), 1)
        self.assertEqual(len(self.ai.manuscript.workspace(self.project_id, self.account_id)["active_version"].chapters), 1)
        self.assertEqual(completed["active_run"]["used_credits"], 0)


if __name__ == "__main__":
    unittest.main()
