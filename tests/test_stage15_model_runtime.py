from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agents.llm_runtime import (
    LLMResult,
    LLMRuntime,
    LLMRuntimeError,
    LLMRuntimeSettings,
    LLMUsage,
)
from app.core.ai_service import AIServiceError, AIStudioService
from app.core.ai_store import AIStore
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore
from core.config import Settings
from schemas.ai import (
    BlueprintAssistantResponse,
    DirectorBodyResponse,
    DirectorCoordinationResponse,
    StoryCharacterSimulationResponse,
)


class FakeRuntime:
    available = True
    provider = "fake-provider"
    model = "fake-model"

    def __init__(self, *, fail_stage: str | None = None, short_body: bool = False) -> None:
        self.fail_stage = fail_stage
        self.short_body = short_body
        self.calls: list[dict[str, object]] = []

    async def structured(self, *, call_id: str, messages: list[dict[str, str]], response_model: type, max_tokens: int) -> LLMResult:
        stage = response_model.__name__
        self.calls.append({"call_id": call_id, "stage": stage, "messages": messages, "max_tokens": max_tokens})
        if self.fail_stage == stage:
            raise LLMRuntimeError("provider_unauthorized", "模型服务认证失败，请检查模型配置。", retryable=False, status_code=502)
        if response_model is BlueprintAssistantResponse:
            data = {
                "reply": "我已把这轮设定整理成一版可编辑蓝图；作者仍然拥有最终决定权。",
                "blueprint_patch": {
                    "core_premise": "旧档案会改变人们对过去的记忆。",
                    "core_conflict": "林舟必须在公开真相和保护顾遥之间选择。",
                    "protagonist": "林舟",
                    "protagonist_motivation": "找回父亲失踪的真相。",
                    "key_relationships": "林舟与顾遥互相提供线索，却隐瞒不同代价。",
                    "world_rules": "公共档案是共享事实，私密经历不能越过角色视角。",
                    "target_length": "约 60 章，三阶段推进",
                    "ending_direction": "公开真相，留下需要观察的余波。",
                    "volume_outline": ["发现线索", "逼近真相", "承担代价"],
                },
            }
        elif response_model is StoryCharacterSimulationResponse:
            context = json.loads(messages[-1]["content"])
            data = {
                "character_id": context["character_id"],
                "public_intent": f"{context['name']}准备沿公开线索行动。",
                "public_action": "先确认现场留下的公共证据。",
                "emotional_state": "警觉",
                "current_goal": context.get("current_goal") or "确认真相",
            }
        elif response_model is DirectorCoordinationResponse:
            payload = json.loads(messages[-1]["content"])
            character_id = payload["public_character_summaries"][0]["character_id"]
            data = {
                "choices": [
                    {"choice_id": "trust", "label": "相信公开警告后撤退", "description": "保留证据，暂时退开。", "consequence": "关系线获得重新对齐的机会。", "character_id": character_id},
                    {"choice_id": "enter", "label": "独自进入旧档案", "description": "先把证据带出来。", "consequence": "真相推进更快但会失去信任。", "character_id": character_id},
                    {"choice_id": "role", "label": "把决定交给角色", "description": "让当前角色依据自己的视角决定。", "consequence": "保留不确定的后果。", "character_id": character_id},
                ],
                "recommended_choice_id": "role",
            }
        elif response_model is DirectorBodyResponse:
            content = "潮声沿着旧档案馆的墙根缓慢退去。" * (2 if self.short_body else 80)
            data = {
                "content": content,
                "review_summary": "正文已完成结构审校，确定内容进入档案，不确定处保留为疑问点。",
                "public_character_updates": ["林舟确认了一条公开证据。"],
                "plotline_updates": ["追查旧档案的主线继续推进。"],
                "foreshadowing_candidates": ["蓝色纸角的出处仍待回看。"],
                "question_points": ["顾遥的隐瞒是否会改变关系线？"],
            }
        else:  # pragma: no cover - 防止 fake 合同漏接新结构
            raise AssertionError(response_model)
        return LLMResult(
            call_id=call_id,
            text=json.dumps(data, ensure_ascii=False),
            data=data,
            provider=self.provider,
            model=self.model,
            usage=LLMUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
            latency_ms=4,
        )


class Stage15ConfigAndRuntimeTest(unittest.TestCase):
    def test_root_dotenv_loads_from_non_repository_cwd_without_secret_output(self) -> None:
        root = Path(__file__).resolve().parents[1]
        script = """
from core.config import DOTENV_PATH, settings
from urllib.parse import urlparse
import json
import os
print(json.dumps({
    'env_file_exists': DOTENV_PATH.is_file(),
    'dotenv_loaded': settings.effective_api_key == 'isolated-dotenv-test-secret',
    'environment_key_absent': not os.environ.get('OPENAI_API_KEY') and not os.environ.get('DASHSCOPE_API_KEY'),
    'root_resolved': DOTENV_PATH.parent.name == 'fixture-project',
    'key_configured': bool(settings.effective_api_key),
    'key_source_name': 'OPENAI_API_KEY' if settings.openai_api_key else 'DASHSCOPE_API_KEY' if settings.dashscope_api_key else '',
    'base_url_host': urlparse(settings.effective_base_url or '').hostname or '',
    'model': settings.effective_model,
}))
"""
        # Execute the unchanged production module in an isolated project layout.
        # Never read or modify the developer's .env, and never substitute an env
        # key for the dotenv source this test is supposed to exercise.
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "fixture-project"
            (fixture / "core").mkdir(parents=True)
            shutil.copy2(root / "core" / "config.py", fixture / "core" / "config.py")
            (fixture / "core" / "__init__.py").touch()
            (fixture / ".env").write_text(
                "OPENAI_API_KEY=isolated-dotenv-test-secret\n"
                "OPENAI_BASE_URL=https://dotenv.example.test/v1\n"
                "LLM_MODEL=isolated-dotenv-model\n",
                encoding="utf-8",
            )
            outside = Path(temporary) / "unrelated-cwd"
            outside.mkdir()
            (outside / ".env").write_text("OPENAI_API_KEY=wrong-cwd-secret\n", encoding="utf-8")
            environment = {
                key: value for key, value in os.environ.items()
                if not key.upper().startswith(("OPENAI_", "DASHSCOPE_", "LLM_", "PYTHONPATH"))
            }
            environment["PYTHONPATH"] = str(fixture)
            result = subprocess.run(
                [sys.executable, "-c", script], cwd=outside, env=environment,
                capture_output=True, text=True, check=True,
            )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["env_file_exists"])
        self.assertTrue(payload["dotenv_loaded"])
        self.assertTrue(payload["environment_key_absent"])
        self.assertTrue(payload["root_resolved"])
        self.assertTrue(payload["key_configured"])
        self.assertEqual(payload["key_source_name"], "OPENAI_API_KEY")
        self.assertEqual(payload["base_url_host"], "dotenv.example.test")
        self.assertEqual(payload["model"], "isolated-dotenv-model")
        self.assertNotIn("OPENAI_API_KEY=", result.stdout)
        self.assertNotIn("DASHSCOPE_API_KEY=", result.stdout)
        self.assertNotIn("isolated-dotenv-test-secret", result.stdout + result.stderr)
        self.assertNotIn("wrong-cwd-secret", result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")

    def test_dashscope_alias_and_openai_explicit_settings_are_safe(self) -> None:
        dash = Settings(_env_file=None, DASHSCOPE_API_KEY="fake-dashscope")
        self.assertEqual(dash.provider, "dashscope")
        self.assertEqual(dash.effective_base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.assertEqual(dash.effective_model, "qwen3.6-plus")
        explicit = Settings(
            _env_file=None,
            OPENAI_API_KEY="fake-openai",
            OPENAI_BASE_URL="https://example.test/v1",
            LLM_MODEL="example-model",
        )
        self.assertEqual(explicit.provider, "openai")
        self.assertEqual(explicit.effective_base_url, "https://example.test/v1")
        self.assertEqual(explicit.effective_model, "example-model")

    def test_runtime_maps_bad_json_401_rate_limit_and_timeout_without_body_leak(self) -> None:
        settings = LLMRuntimeSettings(
            api_key="fake-secret",
            base_url="https://example.test/v1",
            model="fake-model",
            provider="fake-provider",
        )

        bad = LLMRuntime(settings, transport=lambda *_: (200, b"not-json"))
        with self.assertRaises(LLMRuntimeError) as bad_error:
            asyncio.run(bad.complete(call_id="bad", messages=[], max_tokens=10))
        self.assertEqual(bad_error.exception.code, "provider_bad_json")
        self.assertNotIn("fake-secret", str(bad_error.exception))

        calls = 0

        def rate_limited(*_):
            nonlocal calls
            calls += 1
            if calls == 1:
                return 429, b""
            return 200, json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()

        retry = LLMRuntime(settings, transport=rate_limited)
        result = asyncio.run(retry.complete(call_id="retry", messages=[], max_tokens=10))
        self.assertEqual(result.text, "ok")
        self.assertEqual(result.attempts, 2)

        unauthorized = LLMRuntime(settings, transport=lambda *_: (401, b"provider secret body"))
        with self.assertRaises(LLMRuntimeError) as unauthorized_error:
            asyncio.run(unauthorized.complete(call_id="unauthorized", messages=[], max_tokens=10))
        self.assertEqual(unauthorized_error.exception.code, "provider_unauthorized")

        timeout_calls = 0

        def timeout(*_):
            nonlocal timeout_calls
            timeout_calls += 1
            raise TimeoutError

        timed = LLMRuntime(settings, transport=timeout)
        with self.assertRaises(LLMRuntimeError) as timeout_error:
            asyncio.run(timed.complete(call_id="timeout", messages=[], max_tokens=10))
        self.assertEqual(timeout_error.exception.code, "provider_timeout")
        self.assertEqual(timeout_calls, 2)


class Stage15AIServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        projects = JsonProjectStore(root / "projects")
        independent = IndependentWorkspaceService(store=IndependentStore(root / "independent"), projects=projects)
        self.runtime = FakeRuntime()
        self.ai = AIStudioService(
            store=AIStore(root / "ai"),
            projects=projects,
            manuscript=independent,
            runtime=self.runtime,
        )
        self.project_id = "stage15-project"
        self.account_id = "stage15-account"
        self.ai.ensure_project(self.project_id, self.account_id)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _ready(self) -> dict:
        workspace = asyncio.run(self.ai.send_message(self.project_id, self.account_id, "主角是林舟，顾遥守住一封回信。"))
        self.assertEqual(workspace["mode"], "live")
        confirmed = self.ai.confirm_blueprint(
            self.project_id,
            self.account_id,
            workspace["blueprint_revision"],
            "stage15-confirm",
        )
        return confirmed

    def test_live_editor_patch_author_priority_and_message_idempotency(self) -> None:
        workspace = asyncio.run(self.ai.send_message(self.project_id, self.account_id, "主角是林舟。"))
        self.assertEqual(workspace["mode"], "live")
        self.assertEqual(workspace["provider"], "fake-provider")
        self.assertEqual(workspace["model"], "fake-model")
        self.assertEqual(workspace["analysis_label"], "模型已连接·开发测试，不结算创作积分")
        self.assertEqual(workspace["usage"]["total_tokens"], 3)
        self.assertEqual(len(self.runtime.calls), 1)
        revision = workspace["blueprint_revision"]

        direct = self.ai.update_blueprint(
            self.project_id,
            self.account_id,
            {"expected_revision": revision, "core_premise": "作者直接拍板的命题"},
        )
        repeated = asyncio.run(self.ai.send_message(self.project_id, self.account_id, "主角是林舟。"))
        self.assertEqual(repeated["blueprint"].core_premise, "作者直接拍板的命题")
        self.assertEqual(repeated["blueprint_revision"], direct["blueprint_revision"])
        self.assertEqual(len(self.runtime.calls), 1)

    def test_director_isolates_each_private_memory_and_persists_single_route(self) -> None:
        self._ready()
        record = self.ai.store.load(self.project_id)
        assert record is not None
        by_name = {item.name: item for item in record.story_characters}
        by_name["林舟"].private_memory = ["林舟私有哨兵·潮汐钥匙"]
        by_name["顾遥"].private_memory = ["顾遥私有哨兵·白色回声"]
        self.ai.store.save(record)

        waiting = asyncio.run(
            self.ai.start_director(
                self.project_id,
                self.account_id,
                strategy="pause_at_key_nodes",
                idempotency_key="stage15-run",
                defer=False,
            )
        )
        run = waiting["active_run"]
        self.assertEqual(run["status"], "waiting_for_choice")
        self.assertEqual(len(run["choices"]), 3)
        self.assertFalse(any("possible_consequence" in choice for choice in run["choices"]))
        self.assertEqual({call["stage"] for call in self.runtime.calls}, {
            "BlueprintAssistantResponse",
            "StoryCharacterSimulationResponse",
            "DirectorCoordinationResponse",
        })

        character_calls = [call for call in self.runtime.calls if call["stage"] == "StoryCharacterSimulationResponse"]
        for call in character_calls:
            text = json.dumps(call["messages"], ensure_ascii=False)
            if "潮汐钥匙" in text:
                self.assertNotIn("白色回声", text)
            if "白色回声" in text:
                self.assertNotIn("潮汐钥匙", text)
        coordinator = next(call for call in self.runtime.calls if call["stage"] == "DirectorCoordinationResponse")
        self.assertNotIn("潮汐钥匙", json.dumps(coordinator["messages"], ensure_ascii=False))
        self.assertNotIn("白色回声", json.dumps(coordinator["messages"], ensure_ascii=False))

        completed = asyncio.run(self.ai.choose(self.project_id, self.account_id, run["run_id"], "role"))
        self.assertEqual(completed["active_run"]["status"], "completed")
        self.assertEqual(len(completed["active_run"]["generated_content"]), 1280)
        self.assertNotIn("潮汐钥匙", json.dumps(completed, ensure_ascii=False, default=str))
        self.assertNotIn("白色回声", json.dumps(completed, ensure_ascii=False, default=str))
        self.assertEqual(completed["active_run"]["used_credits"], 0)
        self.assertIn("DirectorBodyResponse", {call["stage"] for call in self.runtime.calls})
        self.assertEqual(len(self.ai.store.load(self.project_id).runs), 1)
        self.assertEqual(self.ai.store.load(self.project_id).runs[0].archive_candidates["questions"], ["顾遥的隐瞒是否会改变关系线？"])

    def test_configured_failure_is_failed_and_never_falls_back_to_demo(self) -> None:
        failing = FakeRuntime(fail_stage="BlueprintAssistantResponse")
        self.ai.runtime = failing
        with self.assertRaises(AIServiceError) as error:
            asyncio.run(self.ai.send_message(self.project_id, self.account_id, "主角是林舟。"))
        self.assertEqual(error.exception.code, "model_call_failed")
        record = self.ai.store.load(self.project_id)
        assert record is not None
        self.assertEqual(record.blueprint_revision, 0)
        self.assertEqual(record.model_calls[-1].status, "failed")
        self.assertEqual(record.model_calls[-1].error_code, "provider_unauthorized")
        self.assertFalse(any(message.role == "editor" for message in record.messages))

    def test_short_live_body_fails_without_formal_chapter(self) -> None:
        self.runtime.short_body = True
        self._ready()
        waiting = asyncio.run(
            self.ai.start_director(
                self.project_id,
                self.account_id,
                strategy="pause_at_key_nodes",
                idempotency_key="stage15-short",
                defer=False,
            )
        )
        run_id = waiting["active_run"]["run_id"]
        failed = asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))
        self.assertEqual(failed["active_run"]["status"], "failed")
        manuscript = self.ai.manuscript.workspace(self.project_id, self.account_id)
        self.assertEqual(manuscript["active_version"].chapters[0].content, "")

    def test_call_id_and_completed_results_survive_service_recreation(self) -> None:
        self._ready()
        waiting = asyncio.run(
            self.ai.start_director(
                self.project_id,
                self.account_id,
                strategy="pause_at_key_nodes",
                idempotency_key="stage15-restart",
                defer=False,
            )
        )
        first_count = len(self.runtime.calls)
        recreated = AIStudioService(
            store=self.ai.store,
            projects=self.ai.projects,
            manuscript=self.ai.manuscript,
            runtime=FakeRuntime(),
        )
        duplicate = asyncio.run(
            recreated.start_director(
                self.project_id,
                self.account_id,
                strategy="pause_at_key_nodes",
                idempotency_key="stage15-restart",
                defer=False,
            )
        )
        self.assertEqual(duplicate["active_run"]["run_id"], waiting["active_run"]["run_id"])
        self.assertEqual(len(self.runtime.calls), first_count)


if __name__ == "__main__":
    unittest.main()
