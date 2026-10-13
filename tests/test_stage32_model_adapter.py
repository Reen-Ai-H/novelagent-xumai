import json
import unittest
from app.agents.llm_runtime import LLMRuntime, LLMRuntimeSettings
from pydantic import BaseModel


class Answer(BaseModel):
    text: str


class DeconstructionAdapterTest(unittest.IsolatedAsyncioTestCase):
    async def test_deepseek_thinking_setting_does_not_leak_to_other_providers(self):
        for host, enabled in (("api.deepseek.com", True), ("example.test", False)):
            captured = []
            def transport(url, headers, body, timeout):
                captured.append(json.loads(body))
                return 200, json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": '{"text":"ok"}'}}]}).encode()
            runtime = LLMRuntime(LLMRuntimeSettings(api_key="fake", base_url=f"https://{host}", model="fake", thinking="disabled"), transport=transport)
            await runtime.structured(call_id="test", messages=[{"role":"user", "content":"JSON"}], response_model=Answer)
            self.assertEqual(captured[0].get("thinking"), {"type":"disabled"} if enabled else None)
