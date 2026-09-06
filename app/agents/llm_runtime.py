"""叙脉唯一模型运行时边界。

业务层只依赖 ``structured``、``text`` 和安全元数据，不直接接触供应商 SDK。默认实现
使用 OpenAI-compatible Chat Completions；同步的 urllib 调用始终放进
``asyncio.to_thread``，不会阻塞 FastAPI 的后台任务循环。没有 Key 时运行时
明确不可用，业务层才可以选择确定性的免费演示分支。
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from json import JSONDecodeError
from typing import Any, Callable, Mapping, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from langchain_openai import ChatOpenAI
from pydantic import ValidationError


T = TypeVar("T")
Transport = Callable[[str, Mapping[str, str], bytes, float], tuple[int, bytes]]
TextValidator = Callable[[str], str | None]


@dataclass(frozen=True)
class LLMRuntimeSettings:
    # api_key 只供本模块组装请求头，禁止放进诊断、日志、响应或错误文本。
    api_key: str = ""
    base_url: str | None = None
    model: str = "unavailable"
    provider: str = "unavailable"
    temperature: float = 0.7
    timeout_seconds: float = 45.0
    thinking: str | None = None

    @property
    def key_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def base_host(self) -> str:
        return urlparse(self.base_url or "").hostname or ""


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    known: bool = True

    @classmethod
    def from_payload(cls, payload: Any) -> "LLMUsage":
        if not isinstance(payload, Mapping):
            return cls(known=False)
        known = any(
            key in payload
            for key in ("prompt_tokens", "input_tokens", "completion_tokens", "output_tokens", "total_tokens")
        )
        prompt = int(payload.get("prompt_tokens") or payload.get("input_tokens") or 0)
        completion = int(payload.get("completion_tokens") or payload.get("output_tokens") or 0)
        total = int(payload.get("total_tokens") or prompt + completion)
        return cls(prompt_tokens=prompt, completion_tokens=completion, total_tokens=total, known=known)

    def as_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class LLMResult:
    call_id: str
    text: str
    data: dict[str, Any] = field(default_factory=dict)
    provider: str = "unavailable"
    model: str = "unavailable"
    usage: LLMUsage = field(default_factory=LLMUsage)
    latency_ms: int = 0
    attempts: int = 1

    def metadata(self, *, stage: str, status: str = "completed") -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "stage": stage,
            "provider": self.provider,
            "model": self.model,
            "status": status,
            "usage": self.usage.as_dict(),
            "latency_ms": self.latency_ms,
            "attempts": self.attempts,
        }


class LLMRuntimeError(RuntimeError):
    """只携带可行动、脱敏的模型错误。"""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
        status_code: int = 502,
        attempts: int = 1,
        usage: LLMUsage | None = None,
        latency_ms: int = 0,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code
        self.attempts = attempts
        self.usage = usage if usage is not None else LLMUsage(known=False)
        self.latency_ms = max(0, latency_ms)


class LLMUnavailableError(LLMRuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "model_unavailable",
            "未配置模型 Key，只能使用演示推演。",
            retryable=False,
            status_code=503,
        )


def load_llm_settings() -> LLMRuntimeSettings:
    """读取配置并只在返回对象中保留内部请求所需的值。"""

    try:
        from core.config import settings

        return LLMRuntimeSettings(
            api_key=settings.effective_api_key,
            base_url=settings.effective_base_url,
            model=settings.effective_model,
            provider=settings.provider,
            temperature=settings.llm_temperature,
        )
    except Exception:  # noqa: BLE001 - 无配置必须可安全降级
        return LLMRuntimeSettings()


def _default_transport(url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
    # 这里不记录 URL 查询、请求头或供应商响应；认证值只存在于本次请求对象。
    request = Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - base URL 来自受控配置
            return int(getattr(response, "status", 200)), response.read()
    except HTTPError as exc:
        # 不读取错误 body，避免供应商把认证/请求片段带进异常链。
        return int(exc.code), b""
    except (TimeoutError, URLError) as exc:
        raise TimeoutError from exc


class LLMRuntime:
    """可注入、可重试、可结构化校验的 OpenAI-compatible 运行时。"""

    def __init__(
        self,
        settings: LLMRuntimeSettings | None = None,
        *,
        transport: Transport | None = None,
        max_retries: int = 1,
    ) -> None:
        self.settings = settings or load_llm_settings()
        self._transport = transport or _default_transport
        self.max_retries = max(0, min(int(max_retries), 1))

    @property
    def available(self) -> bool:
        return self.settings.key_configured and bool(self.settings.base_url) and self.settings.model != "unavailable"

    @property
    def provider(self) -> str:
        return self.settings.provider if self.available else "unavailable"

    @property
    def model(self) -> str:
        return self.settings.model if self.available else "unavailable"

    @property
    def safe_metadata(self) -> dict[str, Any]:
        return {
            "key_configured": self.available,
            "base_host": self.settings.base_host if self.available else "",
            "provider": self.provider,
            "model": self.model,
        }

    def _endpoint(self) -> str:
        return f"{(self.settings.base_url or '').rstrip('/')}/chat/completions"

    @staticmethod
    def _content_from_response(payload: Mapping[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise LLMRuntimeError(
                "provider_bad_json",
                "模型服务返回了无法识别的结果，请重试。",
                retryable=True,
            )
        choice = choices[0]
        if isinstance(choice, Mapping) and choice.get("finish_reason") in {"length", "max_tokens"}:
            raise LLMRuntimeError(
                "provider_truncated",
                "模型服务输出被截断，请重试。",
                retryable=True,
            )
        if isinstance(choice, Mapping) and choice.get("finish_reason") == "content_filter":
            raise LLMRuntimeError(
                "provider_filtered_output",
                "模型服务没有返回可用内容，请重试。",
                retryable=True,
            )
        message = choice.get("message") if isinstance(choice, Mapping) else None
        content = message.get("content") if isinstance(message, Mapping) else None
        if isinstance(content, list):
            content = "".join(
                str(item.get("text", "")) for item in content if isinstance(item, Mapping)
            )
        if not isinstance(content, str) or not content.strip():
            raise LLMRuntimeError(
                "provider_empty_output",
                "模型服务没有返回可用内容，请重试。",
                retryable=True,
            )
        return content.strip()

    @staticmethod
    def _text_content_from_response(payload: Mapping[str, Any]) -> str:
        """读取纯文本协议；不会把供应商的 multipart/list 内容拼成正文。"""

        choices = payload.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise LLMRuntimeError(
                "provider_bad_text",
                "模型服务返回了无法识别的正文结果，请重试。",
                retryable=True,
            )
        choice = choices[0]
        if isinstance(choice, Mapping) and choice.get("finish_reason") in {"length", "max_tokens"}:
            raise LLMRuntimeError(
                "provider_truncated",
                "模型服务正文被截断，请重试。",
                retryable=True,
            )
        if isinstance(choice, Mapping) and choice.get("finish_reason") == "content_filter":
            raise LLMRuntimeError(
                "provider_filtered_output",
                "模型服务没有返回可用正文，请重试。",
                retryable=True,
            )
        message = choice.get("message") if isinstance(choice, Mapping) else None
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(content, str):
            raise LLMRuntimeError(
                "provider_bad_text",
                "模型服务返回的正文格式无法识别，请重试。",
                retryable=True,
            )
        if not content.strip():
            raise LLMRuntimeError(
                "provider_empty_output",
                "模型服务没有返回可用正文，请重试。",
                retryable=True,
            )
        return content.strip()

    @staticmethod
    def _strip_json_fence(text: str) -> str:
        cleaned = text.strip()
        if "```" in cleaned and not cleaned.startswith("```"):
            raise ValueError("multiple markdown fences")
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) < 3 or lines[-1].strip() != "```":
                raise ValueError("unclosed markdown fence")
            if lines[0].strip().lower() not in {"```", "```json"}:
                raise ValueError("unsupported markdown fence")
            inner = "\n".join(lines[1:-1]).strip()
            if "```" in inner:
                raise ValueError("multiple markdown fences")
            return inner
        return cleaned

    @classmethod
    def _decode_json_object(cls, text: str) -> Mapping[str, Any]:
        cleaned = cls._strip_json_fence(text)
        decoder = json.JSONDecoder()
        decoded, end = decoder.raw_decode(cleaned)
        if not isinstance(decoded, Mapping) or cleaned[end:].strip():
            raise ValueError("expected one JSON object")
        return decoded

    @staticmethod
    def _schema_error_summary(error: Exception) -> str:
        if isinstance(error, ValidationError):
            locations: list[str] = []
            for item in error.errors(include_url=False, include_context=False):
                location = ".".join(str(part) for part in item.get("loc", ()))
                if location and location not in locations:
                    locations.append(location)
            return "字段结构或类型不符合 schema" + (f"（位置：{', '.join(locations[:8])}）" if locations else "")
        return "JSON 语法或对象外壳不符合 schema"

    @staticmethod
    def _combined_usage(first: LLMUsage, second: LLMUsage) -> LLMUsage:
        return LLMUsage(
            prompt_tokens=first.prompt_tokens + second.prompt_tokens,
            completion_tokens=first.completion_tokens + second.completion_tokens,
            total_tokens=first.total_tokens + second.total_tokens,
            known=first.known and second.known,
        )

    @staticmethod
    def _format_repair_messages(
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        reason: str,
    ) -> list[dict[str, str]]:
        schema_text = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        return [
            *messages,
            {
                "role": "system",
                "content": (
                    "上一轮模型输出没有通过结构化合同。请只重新生成一个 JSON 对象，不要 Markdown、解释文字或多个对象；"
                    f"失败原因摘要：{reason}。必须严格符合以下 schema：{schema_text}"
                ),
            },
        ]

    async def _request(
        self,
        *,
        call_id: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        json_schema: dict[str, Any] | None,
        content_mode: str = "legacy",
    ) -> LLMResult:
        if not self.available:
            raise LLMUnavailableError()
        body_payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        request_messages = list(messages)
        if self.settings.thinking in {"enabled", "disabled"} and self.settings.base_host == "api.deepseek.com":
            body_payload["thinking"] = {"type": self.settings.thinking}
        if json_schema is not None:
            schema_text = json.dumps(json_schema, ensure_ascii=False, separators=(",", ":"))
            if not any("schema" in str(message.get("content", "")) for message in request_messages):
                request_messages.append(
                    {
                        "role": "system",
                        "content": f"只返回一个 JSON 对象，严格符合以下 schema，不要 Markdown 或解释：{schema_text}",
                    }
                )
            body_payload["response_format"] = {"type": "json_object"}
        body_payload["messages"] = request_messages
        body = json.dumps(body_payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.api_key}",
        }
        last_error: LLMRuntimeError | None = None
        for attempt in range(1, self.max_retries + 2):
            started = time.perf_counter()
            try:
                status, raw = await asyncio.to_thread(
                    self._transport,
                    self._endpoint(),
                    headers,
                    body,
                    self.settings.timeout_seconds,
                )
            except TimeoutError:
                last_error = LLMRuntimeError(
                    "provider_timeout",
                    "模型服务响应超时，请稍后重试。",
                    retryable=True,
                    status_code=504,
                    attempts=attempt,
                )
                if attempt <= self.max_retries:
                    await asyncio.sleep(0)
                    continue
                raise last_error
            except Exception:
                last_error = LLMRuntimeError(
                    "provider_unavailable",
                    "模型服务暂时不可用，请稍后重试。",
                    retryable=True,
                    status_code=502,
                    attempts=attempt,
                )
                if attempt <= self.max_retries:
                    await asyncio.sleep(0)
                    continue
                raise last_error

            latency_ms = max(0, round((time.perf_counter() - started) * 1000))
            if status == 401:
                raise LLMRuntimeError(
                    "provider_unauthorized",
                    "模型服务认证失败，请检查模型配置。",
                    retryable=False,
                    status_code=502,
                    attempts=attempt,
                )
            if status == 429:
                last_error = LLMRuntimeError(
                    "provider_rate_limited",
                    "模型服务暂时繁忙，请稍后重试。",
                    retryable=True,
                    status_code=429,
                    attempts=attempt,
                )
                if attempt <= self.max_retries:
                    await asyncio.sleep(0)
                    continue
                raise last_error
            if status >= 500:
                last_error = LLMRuntimeError(
                    "provider_unavailable",
                    "模型服务暂时不可用，请稍后重试。",
                    retryable=True,
                    status_code=502,
                    attempts=attempt,
                )
                if attempt <= self.max_retries:
                    await asyncio.sleep(0)
                    continue
                raise last_error
            if status < 200 or status >= 300:
                raise LLMRuntimeError(
                    "provider_request_rejected",
                    "模型服务拒绝了本次请求，请检查创作配置。",
                    retryable=False,
                    status_code=502,
                    attempts=attempt,
                )
            usage = LLMUsage(known=False)
            try:
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, Mapping):
                    raise ValueError
                usage = LLMUsage.from_payload(payload.get("usage"))
                text = (
                    self._text_content_from_response(payload)
                    if content_mode == "text"
                    else self._content_from_response(payload)
                )
            except LLMRuntimeError as exc:
                raise LLMRuntimeError(
                    exc.code,
                    exc.message,
                    retryable=exc.retryable,
                    status_code=exc.status_code,
                    attempts=attempt,
                    usage=usage,
                    latency_ms=latency_ms,
                ) from None
            except (UnicodeDecodeError, JSONDecodeError, ValueError, TypeError):
                raise LLMRuntimeError(
                    "provider_bad_json",
                    "模型服务返回了无法识别的结果，请重试。",
                    retryable=True,
                    status_code=502,
                    attempts=attempt,
                    usage=usage,
                    latency_ms=latency_ms,
                ) from None
            return LLMResult(
                call_id=call_id,
                text=text,
                provider=self.settings.provider,
                model=self.settings.model,
                usage=usage,
                latency_ms=latency_ms,
                attempts=attempt,
            )
        raise last_error or LLMRuntimeError("provider_unavailable", "模型服务暂时不可用，请稍后重试。", retryable=True)

    async def complete(
        self,
        *,
        call_id: str,
        messages: list[dict[str, str]],
        max_tokens: int = 1200,
        temperature: float | None = None,
    ) -> LLMResult:
        return await self._request(
            call_id=call_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=self.settings.temperature if temperature is None else temperature,
            json_schema=None,
        )

    @staticmethod
    def _text_repair_messages(messages: list[dict[str, str]], reason: str) -> list[dict[str, str]]:
        """只携带脱敏原因，不把上一轮正文回送给供应商。"""

        return [
            *messages,
            {
                "role": "system",
                "content": (
                    "上一轮正文没有通过纯文本合同。请针对以下失败原因重新生成一段完整中文小说正文："
                    f"{reason}。只输出正文，不要 JSON、Markdown 代码围栏、标题前缀、解释或创作说明。"
                ),
            },
        ]

    async def text(
        self,
        *,
        call_id: str,
        messages: list[dict[str, str]],
        max_tokens: int = 2600,
        temperature: float | None = None,
        validator: TextValidator | None = None,
    ) -> LLMResult:
        """执行正文纯文本协议，最多为合同问题发起一次定向修复。"""

        request_temperature = self.settings.temperature if temperature is None else temperature
        first_result: LLMResult | None = None
        first_error: LLMRuntimeError | None = None
        reason: str | None = None
        try:
            first_result = await self._request(
                call_id=call_id,
                messages=messages,
                max_tokens=max_tokens,
                temperature=request_temperature,
                json_schema=None,
                content_mode="text",
            )
            if validator is not None:
                reason = validator(first_result.text)
        except LLMRuntimeError as exc:
            if exc.code not in {
                "provider_bad_json",
                "provider_bad_text",
                "provider_empty_output",
                "provider_truncated",
                "provider_filtered_output",
            }:
                raise
            first_error = exc
            reason = exc.message

        if reason is None:
            assert first_result is not None
            return first_result

        first_attempts = first_result.attempts if first_result is not None else first_error.attempts
        first_usage = first_result.usage if first_result is not None else first_error.usage
        first_latency = first_result.latency_ms if first_result is not None else first_error.latency_ms
        repair_result: LLMResult | None = None
        try:
            repair_result = await self._request(
                call_id=f"{call_id}:text-repair",
                messages=self._text_repair_messages(messages, reason),
                max_tokens=max_tokens,
                temperature=request_temperature,
                json_schema=None,
                content_mode="text",
            )
            repair_reason = validator(repair_result.text) if validator is not None else None
            if repair_reason is not None:
                raise LLMRuntimeError(
                    "provider_bad_text",
                    "模型返回的正文没有通过纯文本合同，请重试。",
                    retryable=True,
                    status_code=502,
                    attempts=repair_result.attempts,
                    usage=repair_result.usage,
                    latency_ms=repair_result.latency_ms,
                )
        except LLMRuntimeError as exc:
            combined_attempts = first_attempts + exc.attempts
            combined_usage = self._combined_usage(first_usage, exc.usage)
            code = exc.code if exc.code in {"provider_truncated", "provider_empty_output", "provider_filtered_output"} else "provider_bad_text"
            message = exc.message if code != "provider_bad_text" else "模型返回的正文没有通过纯文本合同，请重试。"
            raise LLMRuntimeError(
                code,
                message,
                retryable=True,
                status_code=exc.status_code,
                attempts=combined_attempts,
                usage=combined_usage,
                latency_ms=first_latency + exc.latency_ms,
            ) from None
        assert repair_result is not None
        return LLMResult(
            call_id=call_id,
            text=repair_result.text,
            provider=repair_result.provider,
            model=repair_result.model,
            usage=self._combined_usage(first_usage, repair_result.usage),
            latency_ms=first_latency + repair_result.latency_ms,
            attempts=first_attempts + repair_result.attempts,
        )

    async def structured(
        self,
        *,
        call_id: str,
        messages: list[dict[str, str]],
        response_model: type[T],
        max_tokens: int = 1600,
        temperature: float | None = None,
    ) -> LLMResult:
        schema = response_model.model_json_schema()  # type: ignore[attr-defined]
        request_temperature = self.settings.temperature if temperature is None else temperature
        first_attempts = 1
        first_usage = LLMUsage()
        first_latency = 0
        try:
            result = await self._request(
                call_id=call_id,
                messages=messages,
                max_tokens=max_tokens,
                temperature=request_temperature,
                json_schema=schema,
                content_mode="structured",
            )
            decoded = self._decode_json_object(result.text)
            validated = response_model.model_validate(decoded, strict=True)  # type: ignore[attr-defined]
            return LLMResult(
                call_id=result.call_id,
                text=result.text,
                data=validated.model_dump(mode="json"),  # type: ignore[attr-defined]
                provider=result.provider,
                model=result.model,
                usage=result.usage,
                latency_ms=result.latency_ms,
                attempts=result.attempts,
            )
        except LLMRuntimeError as first_error:
            if first_error.code not in {"provider_bad_json", "provider_empty_output", "provider_truncated", "provider_filtered_output"}:
                raise
            reason = first_error.message
            first_result = None
            first_attempts = max(1, first_error.attempts)
            first_usage = first_error.usage
            first_latency = first_error.latency_ms
        except (JSONDecodeError, TypeError, ValueError, ValidationError) as first_error:
            reason = self._schema_error_summary(first_error)
            first_result = result
            first_attempts = max(1, result.attempts)
            first_usage = result.usage
            first_latency = result.latency_ms

        # 只为格式/结构问题发起一次专门修复；不把上一轮原始输出回送供应商。
        repair_result: LLMResult | None = None
        repair_error: LLMRuntimeError | None = None
        try:
            repair_result = await self._request(
                call_id=f"{call_id}:format-repair",
                messages=self._format_repair_messages(messages, schema, reason),
                max_tokens=max_tokens,
                temperature=request_temperature,
                json_schema=schema,
                content_mode="structured",
            )
            decoded = self._decode_json_object(repair_result.text)
            validated = response_model.model_validate(decoded, strict=True)  # type: ignore[attr-defined]
        except LLMRuntimeError as exc:
            repair_error = exc
        except Exception:
            pass
        if repair_error is not None or repair_result is None or "validated" not in locals():
            repair_attempts = repair_error.attempts if repair_error is not None else repair_result.attempts if repair_result is not None else 1
            repair_usage = repair_error.usage if repair_error is not None else repair_result.usage if repair_result is not None else LLMUsage()
            repair_latency = repair_error.latency_ms if repair_error is not None else repair_result.latency_ms if repair_result is not None else 0
            raise LLMRuntimeError(
                "provider_bad_json",
                "模型返回的结构化内容无法通过校验，请重试。",
                retryable=True,
                status_code=502,
                attempts=first_attempts + repair_attempts,
                usage=self._combined_usage(first_usage, repair_usage),
                latency_ms=first_latency + repair_latency,
            ) from None
        return LLMResult(
            call_id=call_id,
            text=repair_result.text,
            data=validated.model_dump(mode="json"),  # type: ignore[attr-defined]
            provider=repair_result.provider,
            model=repair_result.model,
            usage=self._combined_usage(first_usage, repair_result.usage),
            latency_ms=first_latency + repair_result.latency_ms,
            attempts=first_attempts + repair_result.attempts,
        )


def build_runtime() -> LLMRuntime:
    return LLMRuntime()


def build_chat_model(*, temperature: float | None = None) -> ChatOpenAI | None:
    """旧 Planner/Writer 链的兼容入口；新 AI 产品路径只使用 ``LLMRuntime``。"""

    runtime = load_llm_settings()
    if not runtime.key_configured:
        return None
    kwargs: dict[str, object] = {
        "model": runtime.model,
        "api_key": runtime.api_key,
        "temperature": runtime.temperature if temperature is None else temperature,
        "streaming": False,
    }
    if runtime.base_url:
        kwargs["base_url"] = runtime.base_url
    return ChatOpenAI(**kwargs)
