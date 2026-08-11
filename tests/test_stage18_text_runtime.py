from __future__ import annotations

import asyncio
import json
import unittest
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.agents.llm_runtime import LLMRuntime, LLMRuntimeError, LLMRuntimeSettings


def valid_body(length: int = 1500) -> str:
    seed = "“他问：‘你看见那封信了吗？’她没有回答，只把{蓝色纸角}压进书脊。”\n"
    return (seed * ((length // len(seed)) + 2))[:length]


def body_reason(text: str) -> str | None:
    visible = sum(1 for char in text.strip() if not char.isspace())
    if not 1200 <= visible <= 2000:
        return "正文可见字符必须在 1200–2000 之间"
    if "```" in text:
        return "正文不得包含 Markdown 代码围栏"
    if text.lstrip().startswith(("正文：", "正文:")):
        return "正文不得带解释或标题前缀"
    return None


class QueueTransport:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, _url: str, _headers: dict[str, str], body: bytes, _timeout: float) -> tuple[int, bytes]:
        self.requests.append(json.loads(body.decode("utf-8")))
        response = self.responses.pop(0)
        if isinstance(response, tuple):
            return response
        return 200, json.dumps(response, ensure_ascii=False).encode("utf-8")


def completion(content: Any, *, finish_reason: str = "stop", total_tokens: int = 3) -> dict[str, Any]:
    return {
        "choices": [{"finish_reason": finish_reason, "message": {"content": content}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": total_tokens - 1, "total_tokens": total_tokens},
    }


class TinyStructured(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


class Stage18TextRuntimeTest(unittest.TestCase):
    def settings(self) -> LLMRuntimeSettings:
        return LLMRuntimeSettings(
            api_key="stage18-fake-key",
            base_url="https://example.test/v1",
            model="stage18-model",
            provider="stage18-provider",
        )

    def test_text_keeps_natural_quotes_braces_and_never_sends_json_protocol(self) -> None:
        transport = QueueTransport([completion(valid_body())])
        runtime = LLMRuntime(self.settings(), transport=transport, max_retries=0)

        result = asyncio.run(
            runtime.text(
                call_id="body-natural",
                messages=[{"role": "system", "content": "只输出中文小说正文。"}],
                max_tokens=2600,
                validator=body_reason,
            )
        )

        self.assertEqual(result.call_id, "body-natural")
        self.assertEqual(len(result.text), 1500)
        self.assertIn("{蓝色纸角}", result.text)
        self.assertNotIn("response_format", transport.requests[0])
        self.assertNotIn("schema", json.dumps(transport.requests[0], ensure_ascii=False).lower())

    def test_text_bad_first_output_gets_one_targeted_repair_without_raw_echo(self) -> None:
        bad = "正文：太短了"
        transport = QueueTransport([completion(bad), completion(valid_body(), total_tokens=5)])
        runtime = LLMRuntime(self.settings(), transport=transport, max_retries=0)

        result = asyncio.run(
            runtime.text(
                call_id="body-repair",
                messages=[{"role": "user", "content": "继续这一章。"}],
                validator=body_reason,
            )
        )

        self.assertEqual(result.call_id, "body-repair")
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.usage.total_tokens, 8)
        self.assertEqual(len(transport.requests), 2)
        self.assertNotIn("response_format", transport.requests[1])
        repair_text = json.dumps(transport.requests[1]["messages"], ensure_ascii=False)
        self.assertIn("纯文本合同", repair_text)
        self.assertNotIn(bad, repair_text)

    def test_provider_empty_truncated_and_abnormal_text_are_repaired_once(self) -> None:
        cases = [
            completion(""),
            completion("被截断", finish_reason="length"),
            completion([{"type": "text", "text": valid_body()}]),
        ]
        for index, first in enumerate(cases):
            with self.subTest(index=index):
                transport = QueueTransport([first, completion(valid_body())])
                runtime = LLMRuntime(self.settings(), transport=transport, max_retries=0)
                result = asyncio.run(
                    runtime.text(
                        call_id=f"body-shape-{index}",
                        messages=[],
                        validator=body_reason,
                    )
                )
                self.assertEqual(len(result.text), 1500)
                self.assertEqual(result.attempts, 2)
                self.assertEqual(len(transport.requests), 2)

    def test_text_second_invalid_output_fails_without_third_request(self) -> None:
        transport = QueueTransport([completion("短"), completion("仍然短")])
        runtime = LLMRuntime(self.settings(), transport=transport, max_retries=0)

        with self.assertRaises(LLMRuntimeError) as error:
            asyncio.run(runtime.text(call_id="body-fails", messages=[], validator=body_reason))

        self.assertEqual(error.exception.code, "provider_bad_text")
        self.assertEqual(error.exception.attempts, 2)
        self.assertEqual(len(transport.requests), 2)

    def test_structured_protocol_still_requires_json_object(self) -> None:
        transport = QueueTransport([completion('{"value":"ok"}')])
        runtime = LLMRuntime(self.settings(), transport=transport, max_retries=0)

        result = asyncio.run(
            runtime.structured(
                call_id="structured-still-json",
                messages=[],
                response_model=TinyStructured,
            )
        )

        self.assertEqual(result.data["value"], "ok")
        self.assertEqual(transport.requests[0]["response_format"], {"type": "json_object"})


if __name__ == "__main__":
    unittest.main()
