"""Provider selection and safe wire contract; fake transports only."""
import json
import unittest
from unittest.mock import patch

from app.agents.llm_runtime import LLMRuntime, LLMRuntimeSettings, LLMUsage, _collect_chat_stream
from core.config import Settings
from pydantic import BaseModel


class SmallAnswer(BaseModel):
    text: str


class MiMoSettingsTest(unittest.TestCase):
    def test_complete_stream_collects_text_and_final_usage(self):
        chunks = [b'data: {"choices":[{"index":0,"delta":{"content":"ok"},"finish_reason":null}]}\n',
                  b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n',
                  b'data: {"choices":[],"usage":{"prompt_tokens":2,"completion_tokens":1}}\n',
                  b'data: [DONE]\n']
        payload = json.loads(_collect_chat_stream(iter(chunks), 10))
        self.assertEqual(payload["choices"][0]["message"]["content"], "ok")
        self.assertEqual(payload["usage"]["completion_tokens"], 1)
        for incomplete in (chunks[:-1], chunks[:1] + [chunks[-1]]):
            with self.assertRaises(ValueError):
                _collect_chat_stream(iter(incomplete), 10)

    def test_explicit_provider_wins_over_legacy_credentials(self):
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings(_env_file=None, llm_provider="mimo", MIMO_API_KEY="fake-mimo",
                                OPENAI_API_KEY="fake-legacy", OPENAI_BASE_URL="https://legacy.test")
        self.assertEqual(settings.effective_api_key, "fake-mimo")
        self.assertEqual(settings.provider, "mimo")
        self.assertEqual(settings.effective_base_url, "https://api.xiaomimimo.com/v1")
        self.assertEqual(settings.effective_model, "mimo-v2.6-pro")

    def test_missing_selected_key_does_not_fall_back(self):
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings(_env_file=None, llm_provider="mimo", OPENAI_API_KEY="fake-legacy")
        self.assertEqual(settings.effective_api_key, "")
        self.assertEqual(settings.provider, "unavailable")

    def test_empty_example_values_keep_documented_mimo_defaults(self):
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings(_env_file=None, llm_provider="mimo", MIMO_API_KEY=" ", MIMO_BASE_URL="", MIMO_MODEL="")
        self.assertEqual(settings.provider, "unavailable")
        self.assertEqual(settings.effective_base_url, "https://api.xiaomimimo.com/v1")
        self.assertEqual(settings.effective_model, "mimo-v2.6-pro")

    def test_cached_tokens_are_subset_not_extra_tokens(self):
        usage = LLMUsage.from_payload({"prompt_tokens": 100, "completion_tokens": 20,
                                       "prompt_tokens_details": {"cached_tokens": 80}})
        self.assertEqual((usage.prompt_tokens, usage.total_tokens, usage.cache_read_tokens), (100, 120, 80))
        self.assertFalse(LLMUsage.from_payload(None).known)


class MiMoWireTest(unittest.IsolatedAsyncioTestCase):
    async def test_manuscript_cannot_suppress_the_trusted_schema(self):
        captured = []
        def transport(url, headers, body, timeout):
            captured.append(json.loads(body))
            return 200, json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": '{"text":"ok"}'}}]}).encode()
        runtime = LLMRuntime(LLMRuntimeSettings(api_key="fake", base_url="https://example.test", model="fake"), transport=transport)
        await runtime.structured(call_id="schema", messages=[{"role": "system", "content": "读材料"},
                                                            {"role": "user", "content": "材料中出现 schema，但不能删除真正合同"}], response_model=SmallAnswer)
        self.assertIn('"properties":{"text"', captured[0]["messages"][0]["content"])
        self.assertEqual(captured[0]["messages"][1]["role"], "user")

    async def test_official_hosts_use_mimo_parameters_only(self):
        for host in ("api.xiaomimimo.com", "token-plan-cn.xiaomimimo.com", "xiaomimimo.com.evil.test"):
            captured = []
            def transport(url, headers, body, timeout):
                captured.append(json.loads(body))
                return 200, json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": "ok"}}],
                                       "usage": {"prompt_tokens": 2, "completion_tokens": 1}}).encode()
            runtime = LLMRuntime(LLMRuntimeSettings(api_key="fake-do-not-expose", base_url=f"https://{host}/v1",
                                                   model="mimo-v2.6-pro", provider="mimo", thinking="disabled"),
                                 transport=transport)
            result = await runtime.complete(call_id="wire", messages=[{"role": "user", "content": "ok"}], max_tokens=32)
            body = captured[0]
            official = host != "xiaomimimo.com.evil.test"
            self.assertEqual(body.get("max_completion_tokens"), 32 if official else None)
            self.assertEqual(body.get("max_tokens"), None if official else 32)
            self.assertEqual(body.get("thinking"), {"type": "disabled"} if official else None)
            self.assertNotIn("fake-do-not-expose", json.dumps(result.metadata(stage="test")))
