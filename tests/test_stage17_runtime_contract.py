from __future__ import annotations

import asyncio
import json
import unittest

from app.agents.llm_runtime import LLMRuntime, LLMRuntimeError, LLMRuntimeSettings
from schemas.ai import BlueprintAssistantResponse


class QueueTransport:
    def __init__(self, outputs: list[tuple[str | None, str]]) -> None:
        self.outputs = list(outputs)
        self.requests: list[dict] = []

    def __call__(self, url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
        payload = json.loads(body.decode("utf-8"))
        self.requests.append(payload)
        content, finish_reason = self.outputs.pop(0)
        response = {
            "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
        }
        return 200, json.dumps(response, ensure_ascii=False).encode("utf-8")


def valid_json() -> str:
    return json.dumps({"reply": "整理完成", "blueprint_patch": {}}, ensure_ascii=False)


class Stage17RuntimeContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = LLMRuntimeSettings(
            api_key="fake-runtime-secret",
            base_url="https://example.test/v1",
            model="deepseek-chat",
            provider="openai",
        )

    def test_normal_json_whitespace_and_markdown_fence_are_schema_validated(self) -> None:
        transport = QueueTransport([
            ("\n  " + valid_json() + "  ", "stop"),
            ("```json\n" + valid_json() + "\n```", "stop"),
        ])
        runtime = LLMRuntime(self.settings, transport=transport, max_retries=0)
        first = asyncio.run(runtime.structured(call_id="normal", messages=[{"role": "user", "content": "设定"}], response_model=BlueprintAssistantResponse))
        second = asyncio.run(runtime.structured(call_id="fence", messages=[{"role": "user", "content": "设定"}], response_model=BlueprintAssistantResponse))
        self.assertEqual(first.data["reply"], "整理完成")
        self.assertEqual(second.data["reply"], "整理完成")
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(transport.requests[0]["response_format"], {"type": "json_object"})
        self.assertIn("schema", transport.requests[0]["messages"][-1]["content"])

    def test_format_failure_uses_one_dedicated_repair_request_and_stable_call_id(self) -> None:
        transport = QueueTransport([
            ("说明文字：" + valid_json(), "stop"),
            (valid_json(), "stop"),
        ])
        runtime = LLMRuntime(self.settings, transport=transport, max_retries=0)
        result = asyncio.run(runtime.structured(call_id="repairable", messages=[{"role": "user", "content": "设定"}], response_model=BlueprintAssistantResponse))
        self.assertEqual(result.call_id, "repairable")
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.usage.total_tokens, 16)
        self.assertEqual(len(transport.requests), 2)
        repair_prompt = transport.requests[1]["messages"][-1]["content"]
        self.assertIn("结构化合同", repair_prompt)
        self.assertIn("schema", repair_prompt)
        self.assertNotIn("说明文字", repair_prompt)

    def test_empty_truncated_multiple_object_and_extra_field_can_each_repair_once(self) -> None:
        invalid_outputs = [
            (None, "stop"),
            (valid_json(), "length"),
            (valid_json() + " " + valid_json(), "stop"),
            (json.dumps({"reply": "整理完成", "blueprint_patch": {}, "private_memory": "no"}), "stop"),
        ]
        for index, invalid in enumerate(invalid_outputs):
            with self.subTest(index=index):
                transport = QueueTransport([invalid, (valid_json(), "stop")])
                runtime = LLMRuntime(self.settings, transport=transport, max_retries=0)
                result = asyncio.run(runtime.structured(call_id=f"matrix-{index}", messages=[], response_model=BlueprintAssistantResponse))
                self.assertEqual(result.data["reply"], "整理完成")
                self.assertEqual(len(transport.requests), 2)

    def test_second_format_failure_is_provider_bad_json_without_fallback(self) -> None:
        transport = QueueTransport([
            ("not json", "stop"),
            ("still not json", "stop"),
        ])
        runtime = LLMRuntime(self.settings, transport=transport, max_retries=0)
        with self.assertRaises(LLMRuntimeError) as error:
            asyncio.run(runtime.structured(call_id="unrecoverable", messages=[], response_model=BlueprintAssistantResponse))
        self.assertEqual(error.exception.code, "provider_bad_json")
        self.assertEqual(len(transport.requests), 2)
        self.assertNotIn("deterministic", str(error.exception).lower())


if __name__ == "__main__":
    unittest.main()
