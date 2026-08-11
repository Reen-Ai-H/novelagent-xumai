from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from app.core.ai_service import AIStudioService
from app.core.ai_store import AIStore
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore
from schemas.ai import DirectorBodyResponse, StoryCharacterSimulationResponse

from tests.test_stage15_model_runtime import FakeRuntime


class Stage17AdversarialRuntime(FakeRuntime):
    def __init__(self) -> None:
        super().__init__()
        self.cross_character_secret = "顾遥私有哨兵·白色回声"
        self.inject_character_secret = False
        self.inject_coordination_secret = False
        self.inject_body_secret = False

    async def structured(self, *, call_id: str, messages: list[dict[str, str]], response_model: type, max_tokens: int):
        result = await super().structured(
            call_id=call_id,
            messages=messages,
            response_model=response_model,
            max_tokens=max_tokens,
        )
        if response_model is StoryCharacterSimulationResponse and self.inject_character_secret:
            data = dict(result.data)
            data["current_goal"] = self.cross_character_secret
            return result.__class__(
                call_id=result.call_id,
                text=json.dumps(data, ensure_ascii=False),
                data=data,
                provider=result.provider,
                model=result.model,
                usage=result.usage,
                latency_ms=result.latency_ms,
                attempts=result.attempts,
            )
        if response_model is DirectorBodyResponse and self.inject_body_secret:
            data = dict(result.data)
            data["content"] = ("正文推进段落。" + self.cross_character_secret) * 80
            return result.__class__(
                call_id=result.call_id,
                text=json.dumps(data, ensure_ascii=False),
                data=data,
                provider=result.provider,
                model=result.model,
                usage=result.usage,
                latency_ms=result.latency_ms,
                attempts=result.attempts,
            )
        if response_model.__name__ == "DirectorCoordinationResponse" and self.inject_coordination_secret:
            data = dict(result.data)
            choices = [dict(choice) for choice in data["choices"]]
            choices[0]["description"] = self.cross_character_secret
            data["choices"] = choices
            return result.__class__(
                call_id=result.call_id,
                text=json.dumps(data, ensure_ascii=False),
                data=data,
                provider=result.provider,
                model=result.model,
                usage=result.usage,
                latency_ms=result.latency_ms,
                attempts=result.attempts,
            )
        return result


class Stage17ModelSecurityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        projects = JsonProjectStore(root / "projects")
        independent = IndependentWorkspaceService(
            store=IndependentStore(root / "independent"),
            projects=projects,
        )
        self.runtime = Stage17AdversarialRuntime()
        self.ai = AIStudioService(
            store=AIStore(root / "ai"),
            projects=projects,
            manuscript=independent,
            runtime=self.runtime,
        )
        self.project_id = "stage17-security-project"
        self.account_id = "stage17-security-account"
        asyncio.run(self.ai.send_message(self.project_id, self.account_id, "主角是林舟，顾遥守住一封回信。"))
        workspace = self.ai.workspace(self.project_id, self.account_id)
        self.ai.confirm_blueprint(
            self.project_id,
            self.account_id,
            workspace["blueprint_revision"],
            "stage17-confirm",
        )
        record = self.ai.store.load(self.project_id)
        assert record is not None
        by_name = {item.name: item for item in record.story_characters}
        by_name["林舟"].private_memory = ["林舟私有哨兵·潮汐钥匙"]
        by_name["顾遥"].private_memory = [self.runtime.cross_character_secret]
        by_name["顾遥"].experiences = ["顾遥内部经历·未公开录音"]
        self.ai.store.save(record)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _start_paused(self) -> dict:
        return asyncio.run(
            self.ai.start_director(
                self.project_id,
                self.account_id,
                strategy="pause_at_key_nodes",
                idempotency_key="stage17-run",
                defer=False,
            )
        )

    def test_cross_character_model_output_fails_before_state_persist(self) -> None:
        self.runtime.inject_character_secret = True
        workspace = self._start_paused()
        self.assertEqual(workspace["active_run"]["status"], "failed")

        record = self.ai.store.load(self.project_id)
        assert record is not None
        linzhou = next(item for item in record.story_characters if item.name == "林舟")
        self.assertNotEqual(linzhou.goal, self.runtime.cross_character_secret)
        persisted = json.dumps(
            {
                "model_calls": [item.model_dump(mode="json") for item in record.model_calls],
                "model_cache": record.model_cache,
                "notifications": [item.model_dump(mode="json") for item in record.notifications],
                "run": record.runs[0].model_dump(mode="json"),
            },
            ensure_ascii=False,
        )
        self.assertNotIn(self.runtime.cross_character_secret, persisted)
        self.assertNotIn("顾遥内部经历·未公开录音", persisted)
        self.assertFalse(record.model_cache.get(record.runs[0].model_calls[-1].call_id, {}))
        raw_sidecar = (Path(self.tmp.name) / "ai" / f"{self.project_id}.json").read_text(encoding="utf-8")
        self.assertNotIn('"result"', raw_sidecar)
        manuscript = self.ai.manuscript.workspace(self.project_id, self.account_id)
        self.assertEqual(manuscript["active_version"].chapters[0].content, "")

        self.assertNotIn(self.runtime.cross_character_secret, json.dumps(workspace, ensure_ascii=False, default=str))

    def test_cross_character_coordinator_output_fails_without_choices_or_cache(self) -> None:
        self.runtime.inject_coordination_secret = True
        workspace = self._start_paused()
        self.assertEqual(workspace["active_run"]["status"], "failed")
        self.assertNotIn(self.runtime.cross_character_secret, json.dumps(workspace, ensure_ascii=False, default=str))
        record = self.ai.store.load(self.project_id)
        assert record is not None
        self.assertEqual(record.runs[0].choices, [])
        self.assertFalse(any(item.stage == "coordination" and item.status == "completed" for item in record.model_calls))
        coordination_call_ids = {item.call_id for item in record.model_calls if item.stage == "coordination"}
        self.assertFalse(coordination_call_ids & set(record.model_cache))

    def test_cross_character_body_output_fails_without_writing_chapter(self) -> None:
        self.runtime.inject_body_secret = True
        waiting = self._start_paused()
        self.assertEqual(waiting["active_run"]["status"], "waiting_for_choice")
        failed = asyncio.run(
            self.ai.choose(
                self.project_id,
                self.account_id,
                waiting["active_run"]["run_id"],
                "role",
            )
        )
        self.assertEqual(failed["active_run"]["status"], "failed")
        record = self.ai.store.load(self.project_id)
        assert record is not None
        persisted = json.dumps(
            {
                "model_calls": [item.model_dump(mode="json") for item in record.model_calls],
                "model_cache": record.model_cache,
                "notifications": [item.model_dump(mode="json") for item in record.notifications],
                "run": record.runs[0].model_dump(mode="json"),
            },
            ensure_ascii=False,
        )
        self.assertNotIn(self.runtime.cross_character_secret, persisted)
        body_call_id = next(item.call_id for item in record.model_calls if item.stage == "body_generation")
        self.assertNotIn(body_call_id, record.model_cache)
        manuscript = self.ai.manuscript.workspace(self.project_id, self.account_id)
        self.assertEqual(manuscript["active_version"].chapters[0].content, "")


if __name__ == "__main__":
    unittest.main()
