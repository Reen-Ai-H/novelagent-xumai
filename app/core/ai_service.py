"""AI 创作室与导演台服务。

模型调用只从本文件的统一 ``LLMRuntime`` 边界进入。没有配置时继续使用明确
免费的确定性演示；一旦配置存在，任何供应商失败都持久化为可重试失败，绝不
静默退回模板。正文仍通过阶段 2 的 ``IndependentWorkspaceService`` 写入同一
个唯一当前稿本和故事档案合同。
"""

from __future__ import annotations

import hashlib
import asyncio
import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.ai_store import AIStore
from app.core.independent_service import IndependentServiceError, IndependentWorkspaceService
from app.core.project_store import ProjectStore, project_store
from app.core.transaction_store import (
    CrossStoreTransactionCoordinator,
    TransactionStore,
    TransactionCommitted,
    TransactionNotCommitted,
)
from app.agents.llm_runtime import LLMResult, LLMRuntimeError, LLMUsage, build_runtime
from schemas.ai import (
    AIMessage,
    AINotification,
    AIProjectRecord,
    AISettings,
    BlueprintStage,
    CreditLedgerEntry,
    DirectorChoice,
    DirectorArchiveResponse,
    DirectorBodyResponse,
    DirectorCoordinationResponse,
    DirectorReviewResponse,
    DirectorRun,
    DirectorStrategy,
    BlueprintAssistantResponse,
    ModelCallMetadata,
    ModelCallRecord,
    ModelUsage,
    ProfessionalRoleStatus,
    RoleContext,
    StoryCharacterAgent,
    StoryCharacterContext,
    StoryBlueprint,
    StoryCharacterSimulationResponse,
)
from schemas.independent import (
    ArchiveSnapshot,
    ForeshadowingItem,
    QuestionItem,
    StoryArchive,
    StoryCharacter,
    StorylineItem,
)
from schemas.transaction import TransactionPayload


DEMO_AI_LABEL = "演示推演（未配置模型 Key，不消耗创作积分）"
LIVE_AI_LABEL = "模型已连接·开发测试，不结算创作积分"
FAILED_AI_LABEL = "模型调用失败，可重试；已有内容不会被覆盖"
DEMO_CREDIT_ESTIMATE = 0


@dataclass
class _PendingModelCall:
    call_id: str
    stage: str
    response: Any
    result: LLMResult
    cached: bool = False
    kind: str = "structured"


@dataclass
class _DirectorStageTransaction:
    calls: list[_PendingModelCall] = field(default_factory=list)
    character_updates: list[tuple[str, str, str]] = field(default_factory=list)
    committed: bool = False

REQUIRED_BLUEPRINT_FIELDS: tuple[tuple[str, str], ...] = (
    ("core_premise", "核心命题"),
    ("core_conflict", "主冲突"),
    ("protagonist", "主角"),
    ("protagonist_motivation", "主角动机"),
    ("key_relationships", "关键人物关系"),
    ("world_rules", "世界规则"),
    ("target_length", "预期体量"),
    ("ending_direction", "结局方向"),
    ("volume_outline", "分卷/阶段大纲"),
)


class AIServiceError(Exception):
    """可安全展示给前端的 AI 业务错误。"""

    def __init__(self, code: str, message: str, *, status_code: int = 400, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data


class _ModelOutputRejected(Exception):
    """模型返回了不可公开或越权内容；不携带原文，避免错误链泄露哨兵。"""


class AIStudioService:
    def __init__(
        self,
        *,
        store: AIStore | None = None,
        projects: ProjectStore = project_store,
        manuscript: IndependentWorkspaceService | None = None,
        runtime: object | None = None,
    ) -> None:
        self.store = store or AIStore()
        self.projects = projects
        self.manuscript = manuscript or IndependentWorkspaceService(projects=projects)
        self.runtime = runtime or build_runtime()
        transaction_base = self.store.base_dir.parent / ".novel_transactions"
        self.transactions = CrossStoreTransactionCoordinator(
            store=TransactionStore(transaction_base),
            apply_ai=self._apply_transaction_ai,
            apply_manuscript=self._apply_transaction_manuscript,
            overlay_ai=self._overlay_transaction_ai,
            overlay_manuscript=self._overlay_transaction_manuscript,
            inspect_manuscript=self._inspect_transaction_manuscript,
            compensate_manuscript=self._compensate_transaction_manuscript,
            compensate_ai=self._compensate_transaction_ai,
            overlay_author_conflict=self._overlay_author_conflict,
        )
        self.manuscript.transaction_coordinator = self.transactions
        # 同一 FastAPI 进程内，API 请求和持久 worker 可能同时看见同一个
        # pending_choice；内存锁只防并发，真正恢复仍依赖侧车里的安全缓存。
        self._processing_runs: set[str] = set()

    def _apply_transaction_ai(
        self,
        payload: TransactionPayload,
        persist: bool,
        *,
        record_override: AIProjectRecord | None = None,
    ) -> AIProjectRecord:
        record = record_override if record_override is not None else self.store.load(payload.project_id)
        if record is None or record.account_id != payload.account_id:
            raise AIServiceError("project_forbidden", "AI 作品不存在或无权访问。", status_code=404)
        final_run = DirectorRun.model_validate(payload.ai_run)
        current_run = next((item for item in record.runs if item.run_id == final_run.run_id), None)
        if current_run is None:
            raise AIServiceError("director_run_missing", "导演台任务不存在，事务没有覆盖它。", status_code=409)
        if current_run.status == "completed" and current_run.selected_choice_id == final_run.selected_choice_id:
            # 已经投影过但 journal flag 尚未更新；只补安全元数据/通知的缺口。
            pass
        elif current_run.status != "completed" and final_run.status == "completed":
            # 同一 run 的 marker 已完成但调用方在恢复前曾把旧 sidecar 标成
            # retryable failed；允许用同一 durable payload 恢复，不产生第二章。
            index = record.runs.index(current_run)
            record.runs[index] = final_run
        elif current_run.run_revision > payload.ai_run.get("run_revision", 0) and current_run.status != "completed":
            raise AIServiceError("ai_revision_conflict", "导演台状态已被另一端更新，事务安全停止。", status_code=409)
        else:
            index = record.runs.index(current_run)
            record.runs[index] = final_run
        if payload.professional_roles:
            record.role_statuses = [ProfessionalRoleStatus.model_validate(item) for item in payload.professional_roles]
        for update in payload.character_updates:
            agent = next((item for item in record.story_characters if item.character_id == update.get("character_id")), None)
            if agent is not None:
                agent.emotional_state = update.get("emotional_state", agent.emotional_state)
                if update.get("goal"):
                    agent.goal = update["goal"]
        if payload.credit_entry is not None:
            entry = CreditLedgerEntry.model_validate(payload.credit_entry)
            if not any(item.ledger_id == entry.ledger_id for item in record.credit_ledger):
                record.credit_ledger.append(entry)
        notification = AINotification.model_validate(payload.notification)
        if not any(item.notification_id == notification.notification_id for item in record.notifications):
            record.notifications.append(notification)
            record.notifications = record.notifications[-50:]
        # 仅合并通过安全合同的调用元数据，不复制 model_cache/text_cache 或任意
        # 原始模型产出；这些安全缓存已经由 runtime 自己持久化。
        by_call = {item.call_id: item for item in record.model_calls}
        for metadata in final_run.model_calls:
            existing = by_call.get(metadata.call_id)
            if existing is not None:
                existing.status = metadata.status
                existing.usage = metadata.usage
                existing.usage_known = metadata.usage_known
                existing.latency_ms = metadata.latency_ms
                existing.attempts = metadata.attempts
            else:
                record.model_calls.append(
                    ModelCallRecord(
                        **metadata.model_dump(mode="json"),
                        result={},
                    )
                )
        record.active_run_id = final_run.run_id
        record.credits_used = max(record.credits_used, final_run.used_credits)
        record.updated_at = self._now()
        if persist:
            self.store.save(record)
        return record

    def _apply_transaction_manuscript(self, payload: TransactionPayload, persist: bool) -> Any:
        journal = self.transactions.store.load_journal(payload.transaction_id)
        if journal is None:
            raise AIServiceError("transaction_missing", "事务协调记录不存在。", status_code=500)
        projection = {
            "project_id": payload.project_id,
            "account_id": payload.account_id,
            "version_id": payload.version_id,
            "expected_chapter_revision": journal.expected_manuscript_revision,
            "chapter": payload.chapter,
            "archive": payload.archive,
            "task": payload.task,
            "baseline_archive": payload.baseline_archive,
        }
        return self.manuscript.apply_system_generated_projection(projection, persist=persist)

    def _overlay_transaction_ai(self, record: Any, payload: TransactionPayload) -> Any:
        return self._apply_transaction_ai(payload, persist=False, record_override=record)

    def _overlay_transaction_manuscript(self, record: Any, payload: TransactionPayload) -> Any:
        journal = self.transactions.store.load_journal(payload.transaction_id)
        if journal is None:
            return record
        projection = {
            "project_id": payload.project_id,
            "account_id": payload.account_id,
            "version_id": payload.version_id,
            "expected_chapter_revision": journal.expected_manuscript_revision,
            "chapter": payload.chapter,
            "archive": payload.archive,
            "task": payload.task,
            "baseline_archive": payload.baseline_archive,
        }
        # overlay callback必须不触碰磁盘；先复用独立服务的投影逻辑，再把
        # caller 当前记录作为输入，避免对 store 做第二次读写。
        return self.manuscript.apply_system_generated_projection_to_record(record, projection)

    def _transaction_manuscript_projection(self, payload: TransactionPayload) -> dict[str, Any]:
        journal = self.transactions.store.load_journal(payload.transaction_id)
        if journal is None:
            raise AIServiceError("transaction_missing", "事务协调记录不存在。", status_code=500)
        return {
            "project_id": payload.project_id,
            "account_id": payload.account_id,
            "version_id": payload.version_id,
            "expected_chapter_revision": journal.expected_manuscript_revision,
            "chapter": payload.chapter,
            "archive": payload.archive,
            "task": payload.task,
            "baseline_archive": payload.baseline_archive,
        }

    def _inspect_transaction_manuscript(self, payload: TransactionPayload, journal: Any) -> str:
        return self.manuscript.inspect_system_generated_projection(self._transaction_manuscript_projection(payload))

    def _compensate_transaction_manuscript(self, payload: TransactionPayload, journal: Any) -> None:
        self.manuscript.compensate_author_revision(self._transaction_manuscript_projection(payload), persist=True)

    def _author_conflict_ai_record(self, record: AIProjectRecord, payload: TransactionPayload, *, persist: bool) -> AIProjectRecord:
        current = record.model_copy(deep=True)
        final_run = DirectorRun.model_validate(payload.ai_run)
        current_run = next((item for item in current.runs if item.run_id == final_run.run_id), None)
        if current_run is None:
            raise AIServiceError("director_run_missing", "导演台任务不存在，无法记录作者冲突。", status_code=409)

        # 保留每次安全 usage/latency 元数据；只清除业务正文/选择/完成投影。
        by_call = {item.call_id: item for item in current.model_calls}
        for metadata in final_run.model_calls:
            existing = by_call.get(metadata.call_id)
            if existing is None:
                current.model_calls.append(ModelCallRecord(**metadata.model_dump(mode="json"), result={}))
            else:
                existing.status = metadata.status
                existing.usage = metadata.usage
                existing.usage_known = metadata.usage_known
                existing.latency_ms = metadata.latency_ms
                existing.attempts = metadata.attempts

        index = current.runs.index(current_run)
        conflicted = current_run.model_copy(deep=True)
        conflicted.status = "failed"
        conflicted.current_stage = "作者修改冲突·可重试"
        conflicted.error_message = "author_revision_conflict"
        conflicted.completed_at = None
        conflicted.selected_choice_id = None
        conflicted.choice_source = "none"
        conflicted.pending_choice_id = None
        conflicted.generated_content = ""
        conflicted.preview_content = ""
        conflicted.review_summary = ""
        conflicted.archive_candidates = {}
        conflicted.archive_source_chapter = None
        conflicted.independent_task_id = None
        conflicted.credits_charged = False
        conflicted.used_credits = 0
        if not any(item == "作者 revision 冲突·可重试" for item in conflicted.stage_history):
            conflicted.stage_history.append("作者 revision 冲突·可重试")
        current.runs[index] = conflicted

        if payload.baseline_professional_roles:
            current.role_statuses = [ProfessionalRoleStatus.model_validate(item) for item in payload.baseline_professional_roles]
        if payload.baseline_character_states:
            for state in payload.baseline_character_states:
                character = next((item for item in current.story_characters if item.character_id == state.get("character_id")), None)
                if character is not None:
                    character.emotional_state = state.get("emotional_state", character.emotional_state)
                    character.goal = state.get("goal", character.goal)

        credit_ids = {str(payload.credit_entry.get("ledger_id"))} if payload.credit_entry else set()
        current.credit_ledger = [
            item for item in current.credit_ledger
            if item.run_id != final_run.run_id and item.ledger_id not in credit_ids
        ]
        current.credits_used = sum(item.credits for item in current.credit_ledger)
        completion_id = str(payload.notification.get("notification_id"))
        current.notifications = [item for item in current.notifications if item.notification_id != completion_id]
        failure_id = self._slug(f"author-revision-conflict:{payload.transaction_id}")
        if not any(item.notification_id == failure_id for item in current.notifications):
            current.notifications.append(
                AINotification(
                    notification_id=failure_id,
                    kind="director_failed",
                    message="作者刚刚保存了新的正文，AI 章节未覆盖；可基于当前正文重试。",
                    created_at=self._now(),
                )
            )
        current.notifications = current.notifications[-50:]
        current.active_run_id = conflicted.run_id
        current.updated_at = self._now()
        if persist:
            self.store.save(current)
        return current

    def _compensate_transaction_ai(self, payload: TransactionPayload, journal: Any) -> None:
        record = self.store.load(payload.project_id)
        if record is None or record.account_id != payload.account_id:
            raise AIServiceError("project_forbidden", "AI 作品不存在或无权记录作者冲突。", status_code=404)
        self._author_conflict_ai_record(record, payload, persist=True)

    def _overlay_author_conflict(self, record: Any, payload: TransactionPayload, kind: str) -> Any:
        if kind == "ai":
            return self._author_conflict_ai_record(record, payload, persist=False)
        return self.manuscript.compensate_author_revision(
            self._transaction_manuscript_projection(payload),
            persist=False,
            record_override=record,
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _slug(value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()[:20]

    def _runtime_available(self) -> bool:
        return bool(getattr(self.runtime, "available", False))

    def _runtime_provider(self) -> str:
        return str(getattr(self.runtime, "provider", "fake" if self._runtime_available() else "unavailable"))

    def _runtime_model(self) -> str:
        return str(getattr(self.runtime, "model", "fake-model" if self._runtime_available() else "unavailable"))

    @staticmethod
    def _result_to_metadata(result: LLMResult, *, stage: str, status: str = "completed") -> ModelCallMetadata:
        return ModelCallMetadata(
            call_id=result.call_id,
            stage=stage,
            provider=result.provider,
            model=result.model,
            status=status,  # type: ignore[arg-type]
            usage=ModelUsage(**result.usage.as_dict()),
            usage_known=result.usage.known,
            latency_ms=result.latency_ms,
            attempts=max(1, result.attempts),
        )

    @staticmethod
    def _model_usage(usage: LLMUsage) -> ModelUsage:
        return ModelUsage(
            **usage.as_dict(),
        )

    @staticmethod
    def _replace_model_call(record: AIProjectRecord, call: ModelCallRecord) -> None:
        record.model_calls = [item for item in record.model_calls if item.call_id != call.call_id]
        record.model_calls.append(call)
        record.model_calls = record.model_calls[-120:]

    def _cache_model_result(
        self,
        record: AIProjectRecord,
        *,
        call_id: str,
        result: dict[str, Any],
    ) -> None:
        """只缓存已通过业务安全校验的结构化结果，不把它放进 model_calls。"""

        record.model_cache[call_id] = deepcopy(result)
        call = next((item for item in record.model_calls if item.call_id == call_id), None)
        if call is not None:
            call.result = {}

    def _cache_text_result(
        self,
        record: AIProjectRecord,
        *,
        call_id: str,
        content: str,
    ) -> None:
        """只缓存已通过正文合同的服务端文本，不把它放入调用元数据。"""

        record.text_cache[call_id] = content
        call = next((item for item in record.model_calls if item.call_id == call_id), None)
        if call is not None:
            call.result = {}

    def _record_model_failure(
        self,
        record: AIProjectRecord,
        *,
        call_id: str,
        stage: str,
        code: str,
        message: str,
        attempts: int = 1,
        usage: ModelUsage | None = None,
        latency_ms: int = 0,
        provider: str | None = None,
        model: str | None = None,
        usage_known: bool | None = None,
        run: DirectorRun | None = None,
    ) -> None:
        """只写安全失败元数据；原始响应和 prompt 永不进入侧车。"""

        known = usage_known if usage_known is not None else usage is not None
        call = ModelCallRecord(
            call_id=call_id,
            stage=stage,
            provider=provider or self._runtime_provider(),
            model=model or self._runtime_model(),
            status="failed",
            usage=usage or ModelUsage(),
            usage_known=known,
            latency_ms=max(0, latency_ms),
            attempts=max(1, attempts),
            error_code=code,
            error_message=message,
        )
        call.result = {}
        self._replace_model_call(record, call)
        record.model_cache.pop(call_id, None)
        record.text_cache.pop(call_id, None)
        metadata = ModelCallMetadata.model_validate(call.model_dump(exclude={"result", "error_code", "error_message"}))
        record.last_model_error = metadata
        self._attach_run_call(run, metadata)
        self.store.save(record)

    def _commit_model_success(self, record: AIProjectRecord, run: DirectorRun | None, pending: _PendingModelCall) -> None:
        if pending.kind == "text":
            content = str(pending.response)
            existing = next((item for item in record.model_calls if item.call_id == pending.call_id), None)
            if existing is None or existing.status != "completed":
                completed = ModelCallRecord(
                    call_id=pending.call_id,
                    stage=pending.stage,
                    provider=pending.result.provider,
                    model=pending.result.model,
                    status="completed",
                    usage=ModelUsage(**pending.result.usage.as_dict()),
                    usage_known=pending.result.usage.known,
                    latency_ms=pending.result.latency_ms,
                    attempts=max(1, pending.result.attempts),
                )
                self._replace_model_call(record, completed)
                existing = completed
            existing.result = {}
            self._cache_text_result(record, call_id=pending.call_id, content=content)
            record.last_model_error = None
            metadata = ModelCallMetadata.model_validate(existing.model_dump(exclude={"result", "error_code", "error_message"}))
            self._attach_run_call(run, metadata)
            return
        data = pending.response.model_dump(mode="json")
        existing = next((item for item in record.model_calls if item.call_id == pending.call_id), None)
        if existing is None or existing.status != "completed":
            completed = ModelCallRecord(
                call_id=pending.call_id,
                stage=pending.stage,
                provider=pending.result.provider,
                model=pending.result.model,
                status="completed",
                usage=ModelUsage(**pending.result.usage.as_dict()),
                usage_known=pending.result.usage.known,
                latency_ms=pending.result.latency_ms,
                attempts=max(1, pending.result.attempts),
            )
            self._replace_model_call(record, completed)
            existing = completed
        existing.result = {}
        self._cache_model_result(record, call_id=pending.call_id, result=data)
        record.last_model_error = None
        metadata = ModelCallMetadata.model_validate(existing.model_dump(exclude={"result", "error_code", "error_message"}))
        self._attach_run_call(run, metadata)

    def _commit_stage_transaction(
        self,
        record: AIProjectRecord,
        run: DirectorRun,
        transaction: _DirectorStageTransaction,
        *,
        persist: bool = True,
    ) -> None:
        if transaction.committed:
            return
        for pending in transaction.calls:
            self._commit_model_success(record, run, pending)
        for character_id, emotional_state, goal in transaction.character_updates:
            agent = next((item for item in record.story_characters if item.character_id == character_id), None)
            if agent is not None:
                agent.emotional_state = emotional_state
                if goal:
                    agent.goal = goal
        transaction.committed = True
        if persist:
            self.store.save(record)

    def _reject_pending_model_call(
        self,
        record: AIProjectRecord,
        pending: _PendingModelCall,
        *,
        run: DirectorRun | None = None,
        code: str = "model_output_rejected",
        message: str = "模型公开产出包含不可公开内容，本轮没有写入作品状态，请重试。",
    ) -> None:
        self._record_model_failure(
            record,
            call_id=pending.call_id,
            stage=pending.stage,
            code=code,
            message=message,
            attempts=pending.result.attempts,
            usage=ModelUsage(**pending.result.usage.as_dict()),
            usage_known=pending.result.usage.known,
            latency_ms=pending.result.latency_ms,
            provider=pending.result.provider,
            model=pending.result.model,
            run=run,
        )
        raise AIServiceError(code, message, status_code=502)

    @staticmethod
    def _payload_has_forbidden_keys(value: Any) -> bool:
        forbidden = {"private_memory", "own_experiences", "experiences", "secret", "private"}
        if isinstance(value, dict):
            if any(str(key).strip().lower() in forbidden for key in value):
                return True
            return any(AIStudioService._payload_has_forbidden_keys(item) for item in value.values())
        if isinstance(value, list):
            return any(AIStudioService._payload_has_forbidden_keys(item) for item in value)
        return False

    def _assert_safe_model_output(self, record: AIProjectRecord, payload: Any) -> None:
        """模型结果必须是公开产出；命中任一人物私有文本就整次拒绝。"""

        if self._payload_has_forbidden_keys(payload):
            raise _ModelOutputRejected
        serialized = json.dumps(payload, ensure_ascii=False, default=str)
        for agent in record.story_characters:
            for secret in [*agent.private_memory, *agent.experiences]:
                if secret and secret in serialized:
                    raise _ModelOutputRejected

    def _assert_public_character_state(self, record: AIProjectRecord) -> None:
        for agent in record.story_characters:
            self._assert_safe_model_output(record, self._public_story_character(agent))

    @staticmethod
    def _attach_run_call(run: DirectorRun | None, metadata: ModelCallMetadata) -> None:
        if run is None:
            return
        run.model_calls = [item for item in run.model_calls if item.call_id != metadata.call_id]
        run.model_calls.append(metadata)

    async def _call_model(
        self,
        record: AIProjectRecord,
        *,
        call_id: str,
        stage: str,
        messages: list[dict[str, str]],
        response_model: type,
        max_tokens: int,
        run: DirectorRun | None = None,
    ) -> tuple[Any, LLMResult, bool]:
        """执行或复用一次结构化调用，并把非敏感结果/元数据落到侧车。"""

        existing = next((item for item in record.model_calls if item.call_id == call_id), None)
        if existing is not None and existing.status == "completed":
            cached_data = record.model_cache.get(call_id) or existing.result
            if not cached_data:
                self._record_model_failure(
                    record,
                    call_id=call_id,
                    stage=stage,
                    code="model_cache_missing",
                    message="模型完成结果缺失，请重试。",
                    run=run,
                )
                raise AIServiceError("model_call_failed", "模型完成结果缺失，请重试。", status_code=502)
            try:
                cached = response_model.model_validate(cached_data, strict=True)
            except Exception:
                self._record_model_failure(
                    record,
                    call_id=call_id,
                    stage=stage,
                    code="model_cache_invalid",
                    message="模型完成结果无法重新校验，请重试。",
                    run=run,
                )
                raise AIServiceError("model_call_failed", "模型完成结果无法重新校验，请重试。", status_code=502)
            cached_result = LLMResult(
                call_id=call_id,
                text="",
                data=cached.model_dump(mode="json"),
                provider=existing.provider,
                model=existing.model,
                usage=LLMUsage(
                    prompt_tokens=existing.usage.prompt_tokens,
                    completion_tokens=existing.usage.completion_tokens,
                    total_tokens=existing.usage.total_tokens,
                    known=existing.usage_known,
                ),
                latency_ms=existing.latency_ms,
                attempts=existing.attempts,
            )
            return cached, cached_result, True
        if not self._runtime_available():
            raise AIServiceError("model_unavailable", "未配置模型 Key，只能使用演示推演。", status_code=503)
        try:
            raw = await self.runtime.structured(  # type: ignore[attr-defined]
                call_id=call_id,
                messages=messages,
                response_model=response_model,
                max_tokens=max_tokens,
            )
            if isinstance(raw, LLMResult):
                result = raw
            elif isinstance(raw, dict):
                result = LLMResult(
                    call_id=call_id,
                    text=json.dumps(raw, ensure_ascii=False),
                    data=raw,
                    provider=self._runtime_provider(),
                    model=self._runtime_model(),
                    usage=LLMUsage(known=False),
                )
            elif hasattr(raw, "model_dump"):
                data = raw.model_dump(mode="json")
                result = LLMResult(
                    call_id=call_id,
                    text=json.dumps(data, ensure_ascii=False),
                    data=data,
                    provider=self._runtime_provider(),
                    model=self._runtime_model(),
                    usage=LLMUsage(known=False),
                )
            else:
                raise ValueError("structured result missing")
            if not result.data:
                raise ValueError("structured result empty")
            validated = response_model.model_validate(result.data, strict=True)
            result = LLMResult(
                call_id=call_id,
                text=result.text,
                data=validated.model_dump(mode="json"),
                provider=result.provider or self._runtime_provider(),
                model=result.model or self._runtime_model(),
                usage=result.usage,
                latency_ms=result.latency_ms,
                attempts=max(1, result.attempts),
            )
        except LLMRuntimeError as exc:
            self._record_model_failure(
                record,
                call_id=call_id,
                stage=stage,
                code=exc.code,
                message=exc.message,
                attempts=exc.attempts,
                usage=ModelUsage(**exc.usage.as_dict()),
                usage_known=exc.usage.known,
                latency_ms=exc.latency_ms,
                provider=self._runtime_provider(),
                model=self._runtime_model(),
                run=run,
            )
            raise AIServiceError(
                "model_call_failed",
                exc.message,
                status_code=exc.status_code,
                data={
                    "mode": "live",
                    "call_id": call_id,
                    "stage": stage,
                    "provider": self._runtime_provider(),
                    "model": self._runtime_model(),
                    "retryable": exc.retryable,
                },
            ) from None
        except Exception:
            failure_usage = ModelUsage(**result.usage.as_dict()) if "result" in locals() and isinstance(result, LLMResult) else None
            failure_usage_known = result.usage.known if "result" in locals() and isinstance(result, LLMResult) else False
            failure_latency = result.latency_ms if "result" in locals() and isinstance(result, LLMResult) else 0
            failure_attempts = result.attempts if "result" in locals() and isinstance(result, LLMResult) else 1
            failure_provider = result.provider if "result" in locals() and isinstance(result, LLMResult) else None
            failure_model = result.model if "result" in locals() and isinstance(result, LLMResult) else None
            self._record_model_failure(
                record,
                call_id=call_id,
                stage=stage,
                code="model_contract_invalid",
                message="模型返回的结构化内容无法通过校验，请重试。",
                attempts=failure_attempts,
                usage=failure_usage,
                usage_known=failure_usage_known,
                latency_ms=failure_latency,
                provider=failure_provider,
                model=failure_model,
                run=run,
            )
            raise AIServiceError(
                "model_contract_invalid",
                "模型返回的结构化内容无法通过校验，请重试。",
                status_code=502,
                data={"mode": "live", "call_id": call_id, "stage": stage, "retryable": True},
            ) from None
        validated_response = response_model.model_validate(result.data, strict=True)
        # 先保存通过 schema 的安全结果和调用元数据；这不是业务状态提交，
        # 因此后续审校/档案事务失败时仍能从侧车恢复并重建 usage。
        self._commit_model_success(
            record,
            run,
            _PendingModelCall(call_id, stage, validated_response, result),
        )
        self.store.save(record)
        return validated_response, result, False

    @staticmethod
    def _generated_text_reason(content: str) -> str | None:
        """正文进入正式流程前的纯文本合同；返回原因而不返回原文。"""

        if not isinstance(content, str):
            return "正文必须是纯文本"
        cleaned = content.strip()
        visible = sum(1 for char in cleaned if not char.isspace())
        if visible == 0:
            return "正文不能为空"
        if visible < 1200 or visible > 2000:
            return "正文可见字符必须在 1200–2000 之间"
        if "```" in cleaned:
            return "正文不得包含 Markdown 代码围栏"
        first_line = cleaned.splitlines()[0].strip() if cleaned.splitlines() else cleaned
        if re.match(r"^(?:正文|小说正文|以下是正文|说明|解释)\s*[:：]", first_line, flags=re.IGNORECASE):
            return "正文不得带解释或标题前缀"
        return None

    async def _call_text(
        self,
        record: AIProjectRecord,
        *,
        call_id: str,
        stage: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        run: DirectorRun | None = None,
    ) -> tuple[str, LLMResult, bool]:
        """执行或复用正文纯文本调用；通过校验后才进入服务端待用缓存。"""

        existing = next((item for item in record.model_calls if item.call_id == call_id), None)
        if existing is not None and existing.status == "completed":
            # 先检查同一 run 是否已经留下可证明属于系统提交的正式稿。旧竞态
            # 可能同时存在一个不同的 text_cache；正式稿证明优先，避免重试把
            # 另一份模型正文拿来覆盖唯一当前稿本。
            if run is not None:
                recovered = self.manuscript.recover_system_generated_chapter(
                    record.project_id,
                    record.account_id,
                    chapter_number=run.chapter_number,
                    idempotency_key=f"ai-director-{run.run_id}",
                )
                if recovered is not None:
                    content, _task_id = recovered
                    recovered_reason = self._generated_text_reason(content)
                    if recovered_reason is None:
                        content = content.strip()
                        self._cache_text_result(record, call_id=call_id, content=content)
                        self.store.save(record)
                        cached_result = LLMResult(
                            call_id=call_id,
                            text=content,
                            provider=existing.provider,
                            model=existing.model,
                            usage=LLMUsage(
                                prompt_tokens=existing.usage.prompt_tokens,
                                completion_tokens=existing.usage.completion_tokens,
                                total_tokens=existing.usage.total_tokens,
                                known=existing.usage_known,
                            ),
                            latency_ms=existing.latency_ms,
                            attempts=existing.attempts,
                        )
                        return content, cached_result, True
            content = record.text_cache.get(call_id)
            if not content:
                self._record_model_failure(
                    record,
                    call_id=call_id,
                    stage=stage,
                    code="model_cache_missing",
                    message="模型完成正文缺失，请重试。",
                    run=run,
                )
                raise AIServiceError("model_call_failed", "模型完成正文缺失，请重试。", status_code=502)
            reason = self._generated_text_reason(content)
            if reason is not None:
                self._record_model_failure(
                    record,
                    call_id=call_id,
                    stage=stage,
                    code="generated_content_invalid",
                    message="已缓存的模型正文未通过校验，请重试。",
                    run=run,
                )
                raise AIServiceError("generated_content_invalid", "模型正文没有通过纯文本合同，请重试。", status_code=502)
            cached_result = LLMResult(
                call_id=call_id,
                text=content,
                provider=existing.provider,
                model=existing.model,
                usage=LLMUsage(
                    prompt_tokens=existing.usage.prompt_tokens,
                    completion_tokens=existing.usage.completion_tokens,
                    total_tokens=existing.usage.total_tokens,
                    known=existing.usage_known,
                ),
                latency_ms=existing.latency_ms,
                attempts=existing.attempts,
            )
            return content, cached_result, True
        if not self._runtime_available():
            raise AIServiceError("model_unavailable", "未配置模型 Key，只能使用演示推演。", status_code=503)
        if not callable(getattr(self.runtime, "text", None)):
            raise AIServiceError("text_runtime_unavailable", "正文纯文本运行时不可用，请重试。", status_code=503)
        try:
            raw = await self.runtime.text(  # type: ignore[attr-defined]
                call_id=call_id,
                messages=messages,
                max_tokens=max_tokens,
                validator=self._generated_text_reason,
            )
            if isinstance(raw, LLMResult):
                result = raw
            elif isinstance(raw, str):
                result = LLMResult(
                    call_id=call_id,
                    text=raw,
                    provider=self._runtime_provider(),
                    model=self._runtime_model(),
                    usage=LLMUsage(known=False),
                )
            else:
                raise ValueError("text result missing")
            content = result.text.strip()
            reason = self._generated_text_reason(content)
            if reason is not None:
                self._record_model_failure(
                    record,
                    call_id=call_id,
                    stage=stage,
                    code="generated_content_invalid",
                    message="模型正文没有通过 1200–2000 字纯文本合同，请重试。",
                    attempts=result.attempts,
                    usage=ModelUsage(**result.usage.as_dict()),
                    usage_known=result.usage.known,
                    latency_ms=result.latency_ms,
                    provider=result.provider or self._runtime_provider(),
                    model=result.model or self._runtime_model(),
                    run=run,
                )
                raise AIServiceError("generated_content_invalid", "模型正文没有通过纯文本合同，请重试。", status_code=502)
            try:
                self._assert_safe_model_output(record, content)
            except _ModelOutputRejected:
                self._record_model_failure(
                    record,
                    call_id=call_id,
                    stage=stage,
                    code="model_output_rejected",
                    message="模型正文包含不可公开内容，本轮没有写入正式稿，请重试。",
                    attempts=result.attempts,
                    usage=ModelUsage(**result.usage.as_dict()),
                    usage_known=result.usage.known,
                    latency_ms=result.latency_ms,
                    provider=result.provider or self._runtime_provider(),
                    model=result.model or self._runtime_model(),
                    run=run,
                )
                raise AIServiceError("model_output_rejected", "模型正文包含不可公开内容，本轮没有写入正式稿，请重试。", status_code=502)
            completed = ModelCallRecord(
                call_id=call_id,
                stage=stage,
                provider=result.provider or self._runtime_provider(),
                model=result.model or self._runtime_model(),
                status="completed",
                usage=ModelUsage(**result.usage.as_dict()),
                usage_known=result.usage.known,
                latency_ms=result.latency_ms,
                attempts=max(1, result.attempts),
            )
            self._replace_model_call(record, completed)
            self._cache_text_result(record, call_id=call_id, content=content)
            record.last_model_error = None
            self._attach_run_call(
                run,
                ModelCallMetadata.model_validate(completed.model_dump(exclude={"result", "error_code", "error_message"})),
            )
            self.store.save(record)
            return content, LLMResult(
                call_id=call_id,
                text=content,
                provider=result.provider or self._runtime_provider(),
                model=result.model or self._runtime_model(),
                usage=result.usage,
                latency_ms=result.latency_ms,
                attempts=max(1, result.attempts),
            ), False
        except LLMRuntimeError as exc:
            self._record_model_failure(
                record,
                call_id=call_id,
                stage=stage,
                code=exc.code,
                message=exc.message,
                attempts=exc.attempts,
                usage=ModelUsage(**exc.usage.as_dict()),
                usage_known=exc.usage.known,
                latency_ms=exc.latency_ms,
                provider=self._runtime_provider(),
                model=self._runtime_model(),
                run=run,
            )
            raise AIServiceError(
                "model_call_failed",
                exc.message,
                status_code=exc.status_code,
                data={
                    "mode": "live",
                    "call_id": call_id,
                    "stage": stage,
                    "provider": self._runtime_provider(),
                    "model": self._runtime_model(),
                    "retryable": exc.retryable,
                },
            ) from None
        except AIServiceError:
            raise
        except Exception:
            failure_usage = ModelUsage(**result.usage.as_dict()) if "result" in locals() and isinstance(result, LLMResult) else None
            failure_usage_known = result.usage.known if "result" in locals() and isinstance(result, LLMResult) else False
            failure_latency = result.latency_ms if "result" in locals() and isinstance(result, LLMResult) else 0
            failure_attempts = result.attempts if "result" in locals() and isinstance(result, LLMResult) else 1
            failure_provider = result.provider if "result" in locals() and isinstance(result, LLMResult) else None
            failure_model = result.model if "result" in locals() and isinstance(result, LLMResult) else None
            self._record_model_failure(
                record,
                call_id=call_id,
                stage=stage,
                code="model_text_contract_invalid",
                message="模型返回的正文无法通过纯文本合同，请重试。",
                attempts=failure_attempts,
                usage=failure_usage,
                usage_known=failure_usage_known,
                latency_ms=failure_latency,
                provider=failure_provider,
                model=failure_model,
                run=run,
            )
            raise AIServiceError(
                "model_text_contract_invalid",
                "模型返回的正文无法通过纯文本合同，请重试。",
                status_code=502,
                data={"mode": "live", "call_id": call_id, "stage": stage, "retryable": True},
            ) from None

    def _load(self, project_id: str, account_id: str) -> AIProjectRecord:
        self.transactions.reconcile_for_read(project_id, account_id)
        record = self.store.load(project_id)
        if record is None:
            raise AIServiceError("ai_workspace_missing", "AI 创作室还没有建立，请从作品入口进入。", status_code=404)
        if record.account_id != account_id:
            raise AIServiceError("project_forbidden", "无权访问这部作品。", status_code=403)
        record = self.transactions.overlay_record(
            record,
            project_id=project_id,
            account_id=account_id,
            kind="ai",
        )
        return record

    def _legacy_title_brief(self, project_id: str) -> tuple[str, str | None]:
        project = self.projects.load_project(project_id)
        if project is None:
            return "未命名 AI 作品", None
        return project.title, project.project_brief

    @staticmethod
    def _default_roles() -> list[ProfessionalRoleStatus]:
        return [
            ProfessionalRoleStatus(role_id="editor", label="主编", state="等待"),
            ProfessionalRoleStatus(role_id="plot", label="剧情", state="等待"),
            ProfessionalRoleStatus(role_id="character", label="人物", state="等待"),
            ProfessionalRoleStatus(role_id="world", label="世界观", state="等待"),
            ProfessionalRoleStatus(role_id="rhythm", label="节奏", state="等待"),
        ]

    @staticmethod
    def _ensure_professional_roles(record: AIProjectRecord) -> bool:
        """让阶段 3 侧车也升级到五个专业角色，保持旧 JSON 可读。"""

        existing = {role.role_id for role in record.role_statuses}
        if "editor" in existing:
            return False
        record.role_statuses.insert(0, ProfessionalRoleStatus(role_id="editor", label="主编", state="已建议"))
        return True

    @staticmethod
    def _character_names(record: AIProjectRecord) -> list[str]:
        blueprint = record.blueprint
        names: list[str] = []
        protagonist = (blueprint.protagonist or "林舟").strip()
        if protagonist:
            names.append(protagonist[:40])
        relationship_text = blueprint.key_relationships or ""
        for match in re.findall(r"(?:与|和|、)\s*([\u4e00-\u9fff]{2,3})(?=(?:互|保|共|在|将|会|，|。|；|;|$))", relationship_text):
            candidate = match.strip()
            if candidate and candidate not in names and candidate not in {"旧档案", "守门人", "关键人物"}:
                names.append(candidate)
        if "顾遥" in relationship_text and "顾遥" not in names:
            names.append("顾遥")
        return names[:8]

    def _sync_story_characters(self, record: AIProjectRecord) -> bool:
        """从当前蓝图/档案得到人物实体，同时保留作者写入的私有记忆。"""

        names = self._character_names(record)
        try:
            manuscript = self.manuscript.workspace(record.project_id, record.account_id)
        except IndependentServiceError:  # 兼容尚未建立正文稿本的 AI 侧车
            manuscript = {}
        archive = manuscript.get("archive") if isinstance(manuscript, dict) else None
        for item in (archive or {}).get("characters", []) if isinstance(archive, dict) else []:
            name = str(item.get("name") or "").strip()
            if name and name not in names:
                names.append(name)

        old_by_name = {agent.name: agent for agent in record.story_characters}
        protagonist = (record.blueprint.protagonist or "林舟").strip()
        shared_facts = [fact for fact in [record.blueprint.core_premise, record.blueprint.core_conflict] if fact]
        next_agents: list[StoryCharacterAgent] = []
        for name in names:
            old = old_by_name.get(name)
            is_lead = name == protagonist
            next_agents.append(
                StoryCharacterAgent(
                    character_id=old.character_id if old else self._slug(f"character:{record.project_id}:{name}"),
                    name=name,
                    role="主角" if is_lead else "关键人物",
                    goal=(old.goal if old and old.goal else (record.blueprint.protagonist_motivation if is_lead else "确认真相需要付出的代价")),
                    known_facts=(old.known_facts if old and old.known_facts else shared_facts[:2]),
                    emotional_state=(old.emotional_state if old else ("警觉" if is_lead else "保留")),
                    current_scene=(old.current_scene if old else "第一章 · 关键节点"),
                    public_facts=(old.public_facts if old and old.public_facts else shared_facts[:1]),
                    experiences=(old.experiences if old and old.experiences else [f"{name}的既往经历以正式正文和来源章节为准。"]),
                    private_memory=(old.private_memory if old and old.private_memory else [f"{name}只保留自己的经历与私有记忆。"]),
                )
            )
        before = [agent.model_dump(mode="json") for agent in record.story_characters]
        after = [agent.model_dump(mode="json") for agent in next_agents]
        if before != after:
            record.story_characters = next_agents
            return True
        return False

    @staticmethod
    def _public_story_character(agent: StoryCharacterAgent) -> dict[str, Any]:
        """工作区公开角色卡只展示角色可知的摘要，不把私有记忆放进 DOM。"""

        return {
            "character_id": agent.character_id,
            "name": agent.name,
            "role": agent.role,
            "goal": agent.goal,
            "known_facts": list(agent.known_facts),
            "emotional_state": agent.emotional_state,
            "current_scene": agent.current_scene,
            "public_facts": list(agent.public_facts),
        }

    @staticmethod
    def _lead_character(record: AIProjectRecord) -> StoryCharacterAgent:
        protagonist = (record.blueprint.protagonist or "林舟").strip()
        return next((item for item in record.story_characters if item.name == protagonist), record.story_characters[0])

    def ensure_project(self, project_id: str, account_id: str) -> AIProjectRecord:
        self.transactions.reconcile_for_read(project_id, account_id)
        record = self.store.load(project_id)
        if record is not None:
            if record.account_id != account_id:
                raise AIServiceError("project_forbidden", "无权访问这部作品。", status_code=403)
            record = self.transactions.overlay_record(
                record,
                project_id=project_id,
                account_id=account_id,
                kind="ai",
            )
            if self._ensure_professional_roles(record):
                record.updated_at = self._now()
                self.store.save(record)
            return record
        title, brief = self._legacy_title_brief(project_id)
        now = self._now()
        record = AIProjectRecord(
            project_id=project_id,
            account_id=account_id,
            title=title,
            brief=brief,
            created_at=now,
            updated_at=now,
            role_statuses=self._default_roles(),
        )
        self.store.save(record)
        return record

    @staticmethod
    def _missing_fields(record: AIProjectRecord) -> list[dict[str, str]]:
        missing: list[dict[str, str]] = []
        for key, label in REQUIRED_BLUEPRINT_FIELDS:
            value = getattr(record.blueprint, key)
            if not value or (isinstance(value, list) and not any(item.strip() for item in value)):
                missing.append({"key": key, "label": label})
        return missing

    def _stage(self, record: AIProjectRecord) -> BlueprintStage:
        if record.confirmed_blueprint_revision == record.blueprint_revision and record.blueprint_revision > 0:
            return "director_ready"
        return "ready_to_confirm" if not self._missing_fields(record) else "drafting"

    def _public_choice(self, choice: DirectorChoice, reveal: bool) -> dict[str, str]:
        payload = {
            "choice_id": choice.choice_id,
            "label": choice.label,
            "description": choice.description,
        }
        if choice.character_id:
            payload["character_id"] = choice.character_id
        if reveal:
            payload["possible_consequence"] = f"可能：{choice.consequence}"
        return payload

    def _public_run(self, record: AIProjectRecord, run: DirectorRun | None) -> dict[str, Any] | None:
        if run is None:
            return None
        payload = run.model_dump(mode="json")
        payload.pop("pending_choice_id", None)
        payload["choices"] = [
            self._public_choice(choice, record.settings.reveal_consequences)
            for choice in run.choices
        ]
        payload.pop("choice_consequences", None)
        return payload

    def _model_summary(self, record: AIProjectRecord) -> dict[str, Any]:
        live = self._runtime_available()
        all_calls = list(record.model_calls)
        known_calls = [item for item in all_calls if item.usage_known]
        usage = {
            "prompt_tokens": sum(item.usage.prompt_tokens for item in known_calls),
            "completion_tokens": sum(item.usage.completion_tokens for item in known_calls),
            "total_tokens": sum(item.usage.total_tokens for item in known_calls),
        }
        latest = all_calls[-1] if all_calls else None
        active_run = next((item for item in record.runs if item.run_id == record.active_run_id), None)
        run_failed = active_run is not None and active_run.status == "failed"
        status = "failed" if run_failed or (live and latest is not None and latest.status == "failed") else "connected" if live else "demo"
        return {
            "mode": "live" if live else "demo",
            "status": status,
            "provider": self._runtime_provider() if live else "demo",
            "model": self._runtime_model() if live else "deterministic-demo",
            "usage": usage,
            "usage_known": not any(not item.usage_known for item in all_calls),
            "usage_unknown_calls": sum(1 for item in all_calls if not item.usage_known),
            "request_count": len(all_calls),
            "provider_attempts": sum(max(1, item.attempts) for item in all_calls),
            "calls": [
                item.model_dump(mode="json", exclude={"result", "error_code", "error_message"})
                for item in record.model_calls[-24:]
            ],
            "key_configured": live,
        }

    def workspace(self, project_id: str, account_id: str) -> dict[str, Any]:
        record = self.ensure_project(project_id, account_id)
        characters_changed = self._sync_story_characters(record) if record.blueprint_revision > 0 else False
        try:
            self._assert_public_character_state(record)
        except _ModelOutputRejected:
            raise AIServiceError(
                "model_output_rejected",
                "作品中存在不可公开的模型产出，当前页面已安全阻断，请重试。",
                status_code=502,
            ) from None
        stage = self._stage(record)
        if record.stage != stage or characters_changed:
            record.stage = stage
            record.updated_at = self._now()
            self.store.save(record)
        active_run = next(
            (
                run
                for run in record.runs
                if run.run_id == record.active_run_id and run.blueprint_revision == record.blueprint_revision
            ),
            None,
        )
        manuscript_workspace: dict[str, Any] | None = None
        if record.confirmed_blueprint_revision is not None:
            manuscript_workspace = self.manuscript.workspace(project_id, account_id)
        next_chapter_number = self._next_chapter_number(record) if record.confirmed_blueprint_revision is not None else 1
        model_summary = self._model_summary(record)
        return {
            "project_id": record.project_id,
            "title": record.title,
            "brief": record.brief,
            "stage": record.stage,
            "blueprint_status": stage,
            "blueprint": record.blueprint,
            "blueprint_revision": record.blueprint_revision,
            "confirmed_blueprint_revision": record.confirmed_blueprint_revision,
            "missing_fields": self._missing_fields(record),
            "can_confirm": not self._missing_fields(record),
            "messages": record.messages,
            "role_statuses": record.role_statuses,
            "professional_roles": record.role_statuses,
            "story_characters": [self._public_story_character(item) for item in record.story_characters],
            "agent_layers": {
                "professional": "主编、剧情、人物、世界观、节奏：读取职责所需的全局材料。",
                "story_character": "故事人物：只接收共享规则、公开事实、必须知道的事实与自己的经历/私有记忆。",
            },
            "settings": record.settings,
            "active_run": self._public_run(record, active_run),
            "runs": [self._public_run(record, run) for run in record.runs[-12:]],
            "next_chapter_number": next_chapter_number,
            "notifications": list(reversed(record.notifications[-20:])),
            "mode": model_summary["mode"],
            "provider": model_summary["provider"],
            "model": model_summary["model"],
            "usage": model_summary["usage"],
            "model_runtime": model_summary,
            "analysis_label": LIVE_AI_LABEL if model_summary["status"] == "connected" else FAILED_AI_LABEL if model_summary["status"] == "failed" else DEMO_AI_LABEL,
            "credits_used": record.credits_used,
            "credit_ledger": record.credit_ledger,
            "credit_unit": "演示免费，不消耗创作积分",
            "manuscript": manuscript_workspace,
        }

    async def send_message(self, project_id: str, account_id: str, content: str) -> dict[str, Any]:
        record = self.ensure_project(project_id, account_id)
        text = content.strip()
        if not text:
            raise AIServiceError("empty_message", "先写下一点故事想法，再交给主编整理。", status_code=422)
        if (
            len(record.messages) >= 2
            and record.messages[-2].role == "author"
            and record.messages[-2].content == text
            and record.messages[-1].role == "editor"
        ):
            return self.workspace(project_id, account_id)
        record.messages.append(AIMessage(message_id=uuid4().hex, role="author", content=text, created_at=self._now()))
        if self._runtime_available():
            call_id = self._slug(f"blueprint:{project_id}:{record.blueprint_revision}:{text}")
            try:
                response, model_result, model_cached = await self._call_model(
                    record,
                    call_id=call_id,
                    stage="blueprint_editor",
                    messages=[
                        {
                            "role": "system",
                            "content": "你是叙脉唯一的主编。只返回严格 JSON：reply 和 blueprint_patch。patch 只补充作者尚未明确的九个蓝图字段，不能臆造确定事实；volume_outline 必须是字符串数组。",
                        },
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "author_message": text,
                                    "current_blueprint": record.blueprint.model_dump(mode="json"),
                                    "missing_fields": self._missing_fields(record),
                                },
                                ensure_ascii=False,
                            ),
                        },
                    ],
                    response_model=BlueprintAssistantResponse,
                    max_tokens=1600,
                )
            except AIServiceError:
                record.updated_at = self._now()
                self.store.save(record)
                raise
            try:
                self._assert_safe_model_output(record, response.model_dump(mode="json"))
            except _ModelOutputRejected:
                self._reject_pending_model_call(
                    record,
                    _PendingModelCall(call_id, "blueprint_editor", response, model_result, model_cached),
                )
            self._commit_model_success(
                record,
                None,
                _PendingModelCall(call_id, "blueprint_editor", response, model_result, model_cached),
            )
            self._apply_model_blueprint_patch(record, response.blueprint_patch)
            record.blueprint_revision += 1
            self._set_role_suggestions(record)
            reply = response.reply.strip()
        else:
            self._deterministic_blueprint_fill(record, text)
            record.blueprint_revision += 1
            self._set_role_suggestions(record)
            reply = self._deterministic_editor_reply(record, text)
        record.messages.append(AIMessage(message_id=uuid4().hex, role="editor", content=reply, created_at=self._now()))
        record.stage = self._stage(record)
        record.updated_at = self._now()
        self.store.save(record)
        return self.workspace(project_id, account_id)

    def _apply_model_blueprint_patch(self, record: AIProjectRecord, patch: Any) -> None:
        """模型只填空字段；作者已经直接编辑的字段永远优先。"""

        for key, _ in REQUIRED_BLUEPRINT_FIELDS:
            value = getattr(patch, key, None)
            if value is None:
                continue
            if key == "volume_outline":
                cleaned = [str(item).strip() for item in value if str(item).strip()]
                if not record.blueprint.volume_outline and cleaned:
                    record.blueprint.volume_outline = cleaned
            elif not str(getattr(record.blueprint, key) or "").strip():
                setattr(record.blueprint, key, str(value).strip())

    def _deterministic_blueprint_fill(self, record: AIProjectRecord, text: str) -> None:
        blueprint = record.blueprint
        brief = (record.brief or "").strip()
        premise = text.splitlines()[0].strip()[:240]
        protagonist_match = re.search(r"(?:主角|主人公)\s*(?:是|为|叫|：|:)\s*([^，。；;\n]+)", text)
        protagonist = protagonist_match.group(1).strip()[:40] if protagonist_match else "林舟"
        if not blueprint.core_premise:
            blueprint.core_premise = brief or premise or f"在《{record.title}》里，一个普通人被迫重新理解自己熟悉的世界。"
        if not blueprint.core_conflict:
            blueprint.core_conflict = "主角必须在守住旧有秩序与追查被掩盖的真相之间做出选择。"
        if not blueprint.protagonist:
            blueprint.protagonist = protagonist
        if not blueprint.protagonist_motivation:
            blueprint.protagonist_motivation = f"{protagonist}想找回被遮蔽的真相，也想保护仍愿意相信他的人。"
        if not blueprint.key_relationships:
            blueprint.key_relationships = f"{protagonist}与顾遥互相提供线索，却对真相的代价有不同判断；与旧档案守门人保持紧张合作。"
        if not blueprint.world_rules:
            blueprint.world_rules = "被封存的档案会改变人们对过去的记忆；任何超出公共记录的事实都必须留下可追溯的来源。"
        if not blueprint.target_length:
            blueprint.target_length = "约 60 章，三阶段推进"
        if not blueprint.ending_direction:
            blueprint.ending_direction = "主角公开真相，但保留一处需要作者继续观察的余波。"
        if not blueprint.volume_outline:
            blueprint.volume_outline = [
                "第一阶段｜发现线索：主角进入旧档案，确认异常并建立关系张力。",
                "第二阶段｜逼近真相：公共秩序与个人记忆发生冲突，关键人物做出选择。",
                "第三阶段｜承担代价：真相被看见，主角决定怎样把故事交回未来。",
            ]

    @staticmethod
    def _set_role_suggestions(record: AIProjectRecord) -> None:
        outputs = {
            "editor": "主编已收束本轮讨论，蓝图仍由作者确认后才会进入导演台。",
            "plot": "已整理主冲突与三段推进，等待作者确认方向。",
            "character": "已记录主角动机和关键关系，后续只使用角色可知视角。",
            "world": "已整理世界规则与事实来源，未知内容不会自动补成确定事实。",
            "rhythm": "已给出阶段体量，关键节点暂停策略可随时调整。",
        }
        now = datetime.now(timezone.utc)
        for role in record.role_statuses:
            role.state = "已建议"
            role.output = outputs[role.role_id]
            role.updated_at = now

    @staticmethod
    def _deterministic_editor_reply(record: AIProjectRecord, text: str) -> str:
        missing = [item["label"] for item in AIStudioService._missing_fields(record)]
        if missing:
            return f"我先把这段想法收进蓝图。还需要你决定：{'、'.join(missing)}。右侧字段也可以直接修改。"
        return "我已经把这段想法整理成一版可编辑蓝图。你可以继续和我讨论，或直接修改右侧字段；确认蓝图后，导演台才会开始创作。"

    def update_blueprint(self, project_id: str, account_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = self.ensure_project(project_id, account_id)
        expected_revision = int(payload.get("expected_revision", -1))
        if expected_revision != record.blueprint_revision:
            raise AIServiceError(
                "blueprint_conflict",
                "蓝图已在另一端更新，本次编辑没有覆盖它。",
                status_code=409,
                data={"blueprint": record.blueprint.model_dump(mode="json"), "blueprint_revision": record.blueprint_revision},
            )
        fields = [key for key, _ in REQUIRED_BLUEPRINT_FIELDS]
        changed = False
        for key in fields:
            if key not in payload or payload[key] is None:
                continue
            value = payload[key]
            if key == "volume_outline":
                value = [str(item).strip() for item in value if str(item).strip()]
            else:
                value = str(value).strip()
            if getattr(record.blueprint, key) != value:
                setattr(record.blueprint, key, value)
                changed = True
        if changed:
            record.blueprint_revision += 1
            if record.confirmed_blueprint_revision is not None:
                record.confirmed_blueprint_revision = record.blueprint_revision
            record.stage = self._stage(record)
            record.updated_at = self._now()
            self.store.save(record)
        return self.workspace(project_id, account_id)

    def confirm_blueprint(self, project_id: str, account_id: str, expected_revision: int, idempotency_key: str | None) -> dict[str, Any]:
        record = self.ensure_project(project_id, account_id)
        if record.confirmed_blueprint_revision == expected_revision and record.stage in {"confirmed", "director_ready"}:
            self.manuscript.start_blank(project_id, account_id)
            return self.workspace(project_id, account_id)
        if expected_revision != record.blueprint_revision:
            raise AIServiceError(
                "blueprint_conflict",
                "蓝图已在另一端更新，请重新载入后再确认。",
                status_code=409,
                data={"blueprint": record.blueprint.model_dump(mode="json"), "blueprint_revision": record.blueprint_revision},
            )
        missing = self._missing_fields(record)
        if missing:
            raise AIServiceError(
                "blueprint_incomplete",
                "蓝图还没有补齐，确认前请先处理标出的字段。",
                status_code=422,
                data={"missing_fields": missing},
            )
        record.confirmed_blueprint_revision = expected_revision
        record.stage = "director_ready"
        record.updated_at = self._now()
        self._notify(record, "blueprint_confirmed", "蓝图已确认，导演台现在可以开始创作。")
        self.store.save(record)
        self.manuscript.start_blank(project_id, account_id)
        return self.workspace(project_id, account_id)

    def _notify(self, record: AIProjectRecord, kind: str, message: str) -> None:
        record.notifications.append(
            AINotification(notification_id=uuid4().hex, kind=kind, message=message, created_at=self._now())  # type: ignore[arg-type]
        )
        record.notifications = record.notifications[-50:]

    def _completion_notification(self, run: DirectorRun) -> AINotification:
        """完成通知使用 run 稳定键，重试/恢复不会生成第二条。"""

        return AINotification(
            notification_id=self._slug(f"director-completed-notification:{run.run_id}"),
            kind="director_completed",
            message="AI 正文已完成，故事档案也已更新。",
            created_at=self._now(),
        )

    def update_settings(
        self,
        project_id: str,
        account_id: str,
        *,
        strategy: DirectorStrategy | None = None,
        reveal_consequences: bool | None = None,
    ) -> dict[str, Any]:
        record = self.ensure_project(project_id, account_id)
        if strategy is not None:
            record.settings.strategy = strategy
        if reveal_consequences is not None:
            record.settings.reveal_consequences = reveal_consequences
        record.updated_at = self._now()
        self.store.save(record)
        return self.workspace(project_id, account_id)

    def _choices(self, record: AIProjectRecord) -> list[DirectorChoice]:
        self._sync_story_characters(record)
        lead = self._lead_character(record)
        protagonist = lead.name
        goal = lead.goal or "依据自己的经历判断下一步"
        return [
            DirectorChoice(
                choice_id="trust-warning",
                label=f"让 {protagonist} 相信警告，暂时撤退",
                description=f"{protagonist}以“{goal}”为优先，把线索带回安全处。",
                consequence="节奏会更克制，关系线可能获得一次重新对齐的机会。",
                character_id=lead.character_id,
            ),
            DirectorChoice(
                choice_id="enter-alone",
                label=f"让 {protagonist} 隐瞒发现，独自进入旧档案",
                description="不让其他人承担风险，先把证据带出来。",
                consequence="真相推进会更快，但主角可能暂时失去一段信任。",
                character_id=lead.character_id,
            ),
            DirectorChoice(
                choice_id="hand-to-role",
                label="把决定交给角色",
                description=f"让 {protagonist} 依据自己的经历和当前情绪做出选择。",
                consequence="由角色当前的私有记忆决定下一步，结果保留不确定性。",
                character_id=lead.character_id,
            ),
        ]

    @staticmethod
    def _is_character_delegation(choice: DirectorChoice | None) -> bool:
        return bool(
            choice is not None
            and (
                choice.choice_id in {"hand-to-role", "role", "role-choice"}
                or "把决定交给角色" in choice.label
            )
        )

    @classmethod
    def _choice_source_for(cls, choices: list[DirectorChoice], choice_id: str, *, fallback: str = "author") -> str:
        choice = next((item for item in choices if item.choice_id == choice_id), None)
        if cls._is_character_delegation(choice):
            return "character"
        return "author" if fallback not in {"character", "role"} else "character"

    @staticmethod
    def _story_character_model_context(record: AIProjectRecord, agent: StoryCharacterAgent) -> dict[str, Any]:
        """构造单人物请求；这里绝不合并其它人物的经历或私有记忆。"""

        return {
            "character_id": agent.character_id,
            "name": agent.name,
            "shared_world_rules": record.blueprint.world_rules or "共享世界规则尚未补充。",
            "public_facts": list(agent.public_facts or [record.blueprint.core_premise, record.blueprint.core_conflict]),
            "necessary_facts": list(agent.known_facts),
            "own_experiences": list(agent.experiences),
            "private_memory": list(agent.private_memory),
            "current_scene": agent.current_scene,
            "current_goal": agent.goal,
            "emotional_state": agent.emotional_state,
        }

    async def _live_character_summaries(
        self,
        record: AIProjectRecord,
        run: DirectorRun,
        transaction: _DirectorStageTransaction | None = None,
    ) -> list[dict[str, str]]:
        owned_transaction = transaction is None
        transaction = transaction or _DirectorStageTransaction()
        self._sync_story_characters(record)
        summaries: list[dict[str, str]] = []
        for agent in record.story_characters:
            call_id = self._slug(f"director:{run.run_id}:character:{agent.character_id}")
            response, result, cached = await self._call_model(
                record,
                call_id=call_id,
                stage="character_simulation",
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个故事人物推演器。只返回严格 JSON 的公开行动摘要；不要在 public_intent、public_action、情绪或目标中复述 private_memory 或 own_experiences 原文。",
                    },
                    {
                        "role": "user",
                        "content": json.dumps(self._story_character_model_context(record, agent), ensure_ascii=False),
                    },
                ],
                response_model=StoryCharacterSimulationResponse,
                max_tokens=800,
                run=run,
            )
            pending = _PendingModelCall(call_id, "character_simulation", response, result, cached)
            if response.character_id != agent.character_id:
                self._reject_pending_model_call(
                    record,
                    pending,
                    run=run,
                    code="model_contract_invalid",
                    message="故事人物模型返回了错误的人物身份，请重试。",
                )
            try:
                self._assert_safe_model_output(record, response.model_dump(mode="json"))
            except _ModelOutputRejected:
                self._reject_pending_model_call(record, pending, run=run)
            emotional = response.emotional_state
            goal = response.current_goal or agent.goal
            transaction.calls.append(pending)
            transaction.character_updates.append((agent.character_id, emotional, goal))
            summaries.append(
                {
                    "character_id": agent.character_id,
                    "name": agent.name,
                    "public_intent": response.public_intent,
                    "public_action": response.public_action,
                    "emotional_state": emotional,
                }
            )
        if owned_transaction:
            self._commit_stage_transaction(record, run, transaction)
        return summaries

    async def _live_choices(
        self,
        record: AIProjectRecord,
        run: DirectorRun,
        summaries: list[dict[str, str]],
        transaction: _DirectorStageTransaction | None = None,
    ) -> list[DirectorChoice]:
        owned_transaction = transaction is None
        transaction = transaction or _DirectorStageTransaction()
        call_id = self._slug(f"director:{run.run_id}:coordinator")
        response, result, cached = await self._call_model(
            record,
            call_id=call_id,
            stage="coordination",
            messages=[
                {
                    "role": "system",
                    "content": "你是叙脉后台协调角色。只使用共享蓝图、全局事实和人物公开行动摘要，不能索取或复述任何故事人物私有记忆。严格返回 3 个互斥 choices；每个 choice 的 character_id 都必须逐字等于下方 public_character_summaries 中某一个 character_id；其中一个 label 必须是或包含“把决定交给角色”。禁止省略 character_id。",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "blueprint": record.blueprint.model_dump(mode="json"),
                            "public_character_summaries": summaries,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_model=DirectorCoordinationResponse,
            max_tokens=1200,
            run=run,
        )
        pending = _PendingModelCall(call_id, "coordination", response, result, cached)
        try:
            self._assert_safe_model_output(record, response.model_dump(mode="json"))
        except _ModelOutputRejected:
            self._reject_pending_model_call(record, pending, run=run)
        choices = response.choices
        if len(choices) != 3 or len({choice.choice_id for choice in choices}) != 3:
            self._reject_pending_model_call(
                record,
                pending,
                run=run,
                code="choice_count_invalid",
                message="模型没有返回恰好三个互斥选择，请重试。",
            )
        if not any("把决定交给角色" in choice.label for choice in choices):
            self._reject_pending_model_call(
                record,
                pending,
                run=run,
                code="role_choice_missing",
                message="模型选择中缺少“把决定交给角色”，请重试。",
            )
        if response.recommended_choice_id not in {choice.choice_id for choice in choices}:
            self._reject_pending_model_call(
                record,
                pending,
                run=run,
                code="recommended_choice_invalid",
                message="模型推荐的导演台选择不存在，请重试。",
            )
        if any(not choice.character_id for choice in choices):
            self._reject_pending_model_call(
                record,
                pending,
                run=run,
                code="choice_character_missing",
                message="模型选择缺少当前故事人物来源，请重试。",
            )
        transaction.calls.append(pending)
        if owned_transaction:
            self._commit_stage_transaction(record, run, transaction)
        return choices

    async def _legacy_live_body(
        self,
        record: AIProjectRecord,
        run: DirectorRun,
        selected: DirectorChoice,
        transaction: _DirectorStageTransaction | None = None,
    ) -> DirectorBodyResponse:
        owned_transaction = transaction is None
        transaction = transaction or _DirectorStageTransaction()
        self._sync_story_characters(record)
        try:
            self._assert_public_character_state(record)
        except _ModelOutputRejected:
            raise AIServiceError(
                "model_output_rejected",
                "作品中存在不可公开的模型产出，正文生成已安全阻断，请重试。",
                status_code=502,
            ) from None
        public_characters = [self._public_story_character(agent) for agent in record.story_characters]
        call_id = self._slug(f"director:{run.run_id}:body:{selected.choice_id}")
        response, result, cached = await self._call_model(
            record,
            call_id=call_id,
            stage="body_generation",
            messages=[
                {
                    "role": "system",
                    "content": "你是叙脉正文生成器。严格返回 JSON；content 必须是 1200 到 2000 个中文字符的单一正式章节，不要输出解释或平行方案。审校和档案候选必须区分确定内容与疑问点。",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "blueprint": record.blueprint.model_dump(mode="json"),
                            "public_characters": public_characters,
                            "selected_choice": selected.model_dump(mode="json"),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_model=DirectorBodyResponse,
            max_tokens=2400,
            run=run,
        )
        pending = _PendingModelCall(call_id, "body_generation", response, result, cached)
        try:
            self._assert_safe_model_output(record, response.model_dump(mode="json"))
        except _ModelOutputRejected:
            self._reject_pending_model_call(record, pending, run=run)
        content = response.content.strip()
        if not 1200 <= len(content) <= 2000:
            self._reject_pending_model_call(
                record,
                pending,
                run=run,
                code="generated_content_invalid",
                message="模型正文长度不在 1200–2000 字范围内，本轮没有写入正式稿。",
            )
        transaction.calls.append(pending)
        if owned_transaction:
            self._commit_stage_transaction(record, run, transaction)
        return response

    async def _live_body_text(
        self,
        record: AIProjectRecord,
        run: DirectorRun,
        selected: DirectorChoice,
    ) -> tuple[str, LLMResult, bool]:
        """正文只走纯文本 runtime；结构化后置阶段不在同一次请求里混入。"""

        self._sync_story_characters(record)
        try:
            self._assert_public_character_state(record)
        except _ModelOutputRejected:
            raise AIServiceError(
                "model_output_rejected",
                "作品中存在不可公开的模型产出，正文生成已安全阻断，请重试。",
                status_code=502,
            ) from None
        public_characters = [self._public_story_character(agent) for agent in record.story_characters]
        call_id = self._slug(f"director:{run.run_id}:body:{selected.choice_id}")
        return await self._call_text(
            record,
            call_id=call_id,
            stage="body_generation",
            messages=[
                {
                    "role": "system",
                    "content": "你是叙脉正文生成器。只输出完整中文小说正文，不要 JSON、Markdown、标题前缀、解释或平行方案。正文必须是一个正式章节，直接从叙事开始并以完整句子结束；请写约 1500 个可见中文字符，控制在 1200 到 1800 个可见字符内，使用自然段、对白和标点，绝不超过 2000 个可见字符。",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "blueprint": record.blueprint.model_dump(mode="json"),
                            "public_characters": public_characters,
                            "selected_choice": selected.model_dump(mode="json"),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            max_tokens=3600,
            run=run,
        )

    async def _live_review_archive(
        self,
        record: AIProjectRecord,
        run: DirectorRun,
        selected: DirectorChoice,
        content: str,
        transaction: _DirectorStageTransaction,
    ) -> tuple[DirectorReviewResponse, DirectorArchiveResponse]:
        """正文通过后才做结构化审校和档案增量；两者均要求当前章节来源。"""

        base_payload = {
            "chapter_number": run.chapter_number,
            "blueprint": record.blueprint.model_dump(mode="json"),
            "selected_choice": selected.model_dump(mode="json"),
            "body": content,
        }
        review_call_id = self._slug(f"director:{run.run_id}:review:{selected.choice_id}")
        review, review_result, review_cached = await self._call_model(
            record,
            call_id=review_call_id,
            stage="reviewing",
            messages=[
                {
                    "role": "system",
                    "content": "你是叙脉专业审校角色。只返回严格 JSON，按当前章节来源输出简洁审校摘要和公开人物状态变化；不得输出私密记忆、内部提示或正文改写。",
                },
                {"role": "user", "content": json.dumps(base_payload, ensure_ascii=False)},
            ],
            response_model=DirectorReviewResponse,
            max_tokens=1200,
            run=run,
        )
        review_pending = _PendingModelCall(
            review_call_id,
            "reviewing",
            review,
            review_result,
            review_cached,
        )
        try:
            self._assert_safe_model_output(record, review.model_dump(mode="json"))
        except _ModelOutputRejected:
            self._reject_pending_model_call(record, review_pending, run=run)
        if review.source_chapter != run.chapter_number:
            self._reject_pending_model_call(
                record,
                review_pending,
                run=run,
                code="archive_source_invalid",
                message="审校结果缺少当前章节来源，本轮没有写入档案。",
            )
        transaction.calls.append(review_pending)
        self._append_stage(run, "updating_archive", "更新档案")

        archive_call_id = self._slug(f"director:{run.run_id}:archive:{selected.choice_id}")
        archive, archive_result, archive_cached = await self._call_model(
            record,
            call_id=archive_call_id,
            stage="archive_update",
            messages=[
                {
                    "role": "system",
                    "content": "你是叙脉档案更新角色。只返回严格 JSON，只记录当前章节可公开的剧情线、伏笔候选和疑问点；所有字段必须标明当前章节来源，不确定内容只能进入疑问点。",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {**base_payload, "review": review.model_dump(mode="json")},
                        ensure_ascii=False,
                    ),
                },
            ],
            response_model=DirectorArchiveResponse,
            max_tokens=1400,
            run=run,
        )
        archive_pending = _PendingModelCall(
            archive_call_id,
            "archive_update",
            archive,
            archive_result,
            archive_cached,
        )
        try:
            self._assert_safe_model_output(record, archive.model_dump(mode="json"))
        except _ModelOutputRejected:
            self._reject_pending_model_call(record, archive_pending, run=run)
        if archive.source_chapter != run.chapter_number:
            self._reject_pending_model_call(
                record,
                archive_pending,
                run=run,
                code="archive_source_invalid",
                message="档案增量缺少当前章节来源，本轮没有写入档案。",
            )
        transaction.calls.append(archive_pending)
        return review, archive

    def _run(self, record: AIProjectRecord, run_id: str) -> DirectorRun:
        run = next((item for item in record.runs if item.run_id == run_id), None)
        if run is None:
            raise AIServiceError("director_run_missing", "导演台任务不存在。", status_code=404)
        return run

    @staticmethod
    def _append_stage(run: DirectorRun, status: str, label: str) -> None:
        run.status = status  # type: ignore[assignment]
        run.current_stage = label
        run.stage_history.append(label)
        run.run_revision += 1
        run.updated_at = datetime.now(timezone.utc)

    def _set_role_running(self, record: AIProjectRecord) -> None:
        now = self._now()
        for role in record.role_statuses:
            role.state = "分析中"
            role.updated_at = now

    def _set_role_done(self, record: AIProjectRecord) -> None:
        self._set_role_suggestions(record)

    def _next_chapter_number(self, record: AIProjectRecord) -> int:
        """取当前唯一稿本中第一个空章，否则追加到最大章节之后。"""

        try:
            manuscript = self.manuscript.workspace(record.project_id, record.account_id)
            active_version = manuscript.get("active_version")
            chapters = list(active_version.chapters) if active_version is not None else []
        except IndependentServiceError:
            chapters = []
        empty_chapter = next(
            (
                chapter
                for chapter in chapters
                if not chapter.content.strip() and not chapter.formal_content.strip()
            ),
            None,
        )
        return empty_chapter.chapter_number if empty_chapter is not None else max(
            (chapter.chapter_number for chapter in chapters),
            default=0,
        ) + 1

    async def start_director(
        self,
        project_id: str,
        account_id: str,
        *,
        strategy: DirectorStrategy,
        idempotency_key: str | None,
        defer: bool = False,
    ) -> dict[str, Any]:
        record = self.ensure_project(project_id, account_id)
        if record.confirmed_blueprint_revision != record.blueprint_revision:
            raise AIServiceError("blueprint_not_confirmed", "请先确认当前蓝图，导演台才会开始创作。", status_code=409)
        record.settings.strategy = strategy
        record.updated_at = self._now()
        self.store.save(record)
        existing = next(
            (
                run
                for run in record.runs
                if idempotency_key and run.idempotency_key == idempotency_key
            ),
            None,
        )
        if existing is not None:
            record.active_run_id = existing.run_id
            return self.workspace(project_id, account_id)
        chapter_number = self._next_chapter_number(record)
        existing = next(
            (
                run
                for run in record.runs
                if run.blueprint_revision == record.blueprint_revision
                and run.chapter_number == chapter_number
                and run.status not in {"failed", "completed"}
            ),
            None,
        )
        if existing is not None:
            return self.workspace(project_id, account_id)
        now = self._now()
        run = DirectorRun(
            run_id=self._slug(
                f"director:{project_id}:{record.blueprint_revision}:chapter:{chapter_number}:"
                f"{idempotency_key or len(record.runs) + 1}:{strategy}"
            ),
            project_id=project_id,
            blueprint_revision=record.blueprint_revision,
            chapter_number=chapter_number,
            strategy=strategy,
            idempotency_key=idempotency_key,
            estimated_credits=DEMO_CREDIT_ESTIMATE,
            created_at=now,
            updated_at=now,
        )
        record.runs.append(run)
        record.active_run_id = run.run_id
        self._sync_story_characters(record)
        run.simulated_character_id = self._lead_character(record).character_id
        self._processing_runs.add(run.run_id)
        try:
            if defer:
                self._append_stage(run, "character_simulation", "角色推演")
                self._set_role_running(record)
                if "[[ai-fail]]" in record.blueprint.core_premise:
                    self._fail_run(record, run, "演示推演遇到显式失败标记，可修改蓝图后重试。")
            else:
                await self._advance_to_safe_point(record, run)
        finally:
            self._processing_runs.discard(run.run_id)
        record.updated_at = self._now()
        self.store.save(record)
        return self.workspace(project_id, account_id)

    async def _advance_to_safe_point(self, record: AIProjectRecord, run: DirectorRun) -> None:
        if run.status in {"completed", "failed"}:
            return
        try:
            if not (run.status == "character_simulation" and run.stage_history and run.stage_history[-1] == "角色推演"):
                self._append_stage(run, "character_simulation", "角色推演")
            self._set_role_running(record)
            try:
                self._assert_public_character_state(record)
            except _ModelOutputRejected:
                raise AIServiceError(
                    "model_output_rejected",
                    "作品中存在不可公开的模型产出，导演台已安全阻断，请重试。",
                    status_code=502,
                ) from None
            if "[[ai-fail]]" in record.blueprint.core_premise:
                raise AIServiceError("director_demo_failed", "演示推演遇到显式失败标记，可修改蓝图后重试。", status_code=500)
            if self._runtime_available():
                transaction = _DirectorStageTransaction()
                summaries = await self._live_character_summaries(record, run, transaction)
                choices = await self._live_choices(record, run, summaries, transaction)
            else:
                self._set_role_done(record)
                choices = self._choices(record)
            if run.strategy == "pause_at_key_nodes":
                if self._runtime_available():
                    self._commit_stage_transaction(record, run, transaction)
                    self._set_role_done(record)
                run.choices = choices
                self._append_stage(run, "waiting_for_choice", "等待关键节点选择")
                self._notify(record, "director_waiting", "导演台已到达关键节点，请选择唯一继续方向。")
                return
            selected_choice_id = "hand-to-role"
            if self._runtime_available():
                selected_choice_id = next(
                    (choice.choice_id for choice in choices if "把决定交给角色" in choice.label),
                    choices[0].choice_id,
                )
            await self._finish_run(
                record,
                run,
                selected_choice_id=selected_choice_id,
                choice_source=self._choice_source_for(choices, selected_choice_id, fallback="character"),
                choices=choices if self._runtime_available() else None,
                transaction=transaction if self._runtime_available() else None,
            )
            if self._runtime_available():
                self._set_role_done(record)
        except TransactionCommitted:
            # durable marker 已存在，不能把已提交事务改写为失败。
            return
        except AIServiceError as exc:
            self._fail_run(record, run, exc.message)
        except Exception:  # pragma: no cover - 防止后台错误丢失任务状态
            self._fail_run(record, run, "导演台后台异常，请重试。")

    async def process_background_runs_async(self) -> int:
        """推进所有持久化中的导演台任务，不依赖浏览器存活。"""

        self.transactions.reconcile_all()
        processed = 0
        for record in self.store.list_records():
            record = self.transactions.overlay_record(
                record,
                project_id=record.project_id,
                account_id=record.account_id,
                kind="ai",
            )
            changed = False
            for run in record.runs:
                if run.run_id in self._processing_runs:
                    continue
                if run.status not in {
                    "queued",
                    "character_simulation",
                    "writing",
                    "reviewing",
                    "updating_archive",
                } and not (run.status == "waiting_for_choice" and run.pending_choice_id):
                    continue
                try:
                    if run.status in {"queued", "character_simulation"}:
                        await self._advance_to_safe_point(record, run)
                    else:
                        selected_choice_id = run.pending_choice_id or run.selected_choice_id or next(
                            (
                                choice.choice_id
                                for choice in run.choices
                                if "把决定交给角色" in choice.label
                            ),
                            run.choices[0].choice_id if run.choices else "hand-to-role",
                        )
                        choice_source = (
                            run.choice_source
                            if run.selected_choice_id
                            else self._choice_source_for(run.choices, selected_choice_id, fallback="character" if not run.pending_choice_id else "author")
                        )
                        await self._finish_run(
                            record,
                            run,
                            selected_choice_id=selected_choice_id,
                            choice_source=choice_source,
                        )
                        if run.selected_choice_id is not None:
                            run.pending_choice_id = None
                except TransactionCommitted:
                    # marker 后的投影由下一次 worker/读请求恢复。
                    pass
                except AIServiceError as exc:
                    self._fail_run(record, run, exc.message)
                except Exception:  # pragma: no cover - worker 不能因单个任务退出
                    self._fail_run(record, run, "导演台后台异常，请重试。")
                changed = True
                processed += 1
            if changed:
                record.updated_at = self._now()
                self.store.save(record)
        return processed

    def process_background_runs(self) -> int:
        """保留同步兼容入口；FastAPI worker 使用 async 入口。"""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.process_background_runs_async())
        raise RuntimeError("事件循环中请 await process_background_runs_async()")

    def _deterministic_generated_content(self, record: AIProjectRecord, choice: DirectorChoice) -> str:
        blueprint = record.blueprint
        self._sync_story_characters(record)
        lead = self._lead_character(record)
        return (
            f"{lead.name}在旧档案室门口停了下来。\n\n"
            f"核心命题：{blueprint.core_premise}\n"
            f"主冲突：{blueprint.core_conflict}\n"
            f"人物：{', '.join(agent.name for agent in record.story_characters)}。\n"
            f"剧情线：{blueprint.core_conflict}\n"
            f"伏笔：门缝里露出的蓝色纸角，仍没有留下出处。\n"
            f"选择：{choice.label}\n"
            f"{choice.description} 这一步留下了一段需要后续验证的余波。\n\n"
            "他没有把这一步交给任何一张空白的地图。灯影向档案深处移动，"
            "而那条尚未命名的故事脉络，第一次有了可以回看的来源。"
        )

    def _write_ai_chapter(
        self,
        record: AIProjectRecord,
        run: DirectorRun,
        content: str,
        *,
        archive: StoryArchive | None = None,
    ) -> str | None:
        try:
            task_id = self.manuscript.commit_system_generated_chapter(
                record.project_id,
                record.account_id,
                chapter_number=run.chapter_number,
                content=content,
                title=f"第{run.chapter_number}章 · 导演台初稿",
                archive=archive,
                idempotency_key=f"ai-director-{run.run_id}",
            )
        except IndependentServiceError as exc:
            raise AIServiceError("manuscript_change_pending", exc.message, status_code=409) from exc
        return task_id

    def _apply_live_archive(
        self,
        record: AIProjectRecord,
        run: DirectorRun,
        review: DirectorReviewResponse,
        archive_update: DirectorArchiveResponse,
    ) -> StoryArchive:
        """构造已通过校验的 live 档案；由正文提交入口与稿本一次保存。"""

        independent_record = self.manuscript.store.load(record.project_id)
        if independent_record is None or independent_record.account_id != record.account_id:
            raise AIServiceError("manuscript_missing", "AI 正文稿本没有建立成功。", status_code=500)
        version = next(
            (item for item in independent_record.versions if item.version_id == independent_record.active_version_id),
            None,
        )
        if version is None:
            raise AIServiceError("manuscript_missing", "AI 正文稿本没有建立成功。", status_code=500)
        current_archive = version.archive.model_copy(deep=True)
        current_archive.analysis_label = LIVE_AI_LABEL
        current_archive.latest_chapter_number = max(
            run.chapter_number,
            current_archive.latest_chapter_number or run.chapter_number,
        )
        # 完成正文时独立服务已经留下了本地演示分析；当前 live 结果应完整
        # 替换同一来源章的演示条目，避免两套分析在档案页并排出现。
        current_archive.characters = [
            item for item in current_archive.characters if item.source_chapter_number != run.chapter_number
        ]
        current_archive.storylines = [
            item for item in current_archive.storylines if item.source_chapter_number != run.chapter_number
        ]
        current_archive.foreshadowing = [
            item for item in current_archive.foreshadowing if item.source_chapter_number != run.chapter_number
        ]
        current_archive.questions = [
            item for item in current_archive.questions if item.source_chapter_number != run.chapter_number
        ]
        updates = list(review.public_character_updates)
        for index, agent in enumerate(record.story_characters):
            profile = updates[index] if index < len(updates) else f"第 {run.chapter_number} 章保留了 {agent.name} 的公开状态。"
            item = StoryCharacter(
                character_id=self._slug(f"live-character:{agent.character_id}"),
                name=agent.name,
                role=agent.role,
                profile=profile,
                current_state=agent.emotional_state,
                source_chapter_number=run.chapter_number,
            )
            existing = next((entry for entry in current_archive.characters if entry.character_id == item.character_id), None)
            if existing is None:
                current_archive.characters.append(item)
            else:
                existing.profile = item.profile
                existing.current_state = item.current_state
                existing.source_chapter_number = item.source_chapter_number
        for index, text in enumerate(archive_update.plotline_updates):
            item = StorylineItem(
                storyline_id=self._slug(f"live-storyline:{record.project_id}:{text}"),
                title=text[:80],
                summary=text,
                source_chapter_number=run.chapter_number,
            )
            existing = next((entry for entry in current_archive.storylines if entry.storyline_id == item.storyline_id), None)
            if existing is None:
                current_archive.storylines.append(item)
            else:
                existing.summary = item.summary
                existing.source_chapter_number = item.source_chapter_number
        for text in archive_update.foreshadowing_candidates:
            item = ForeshadowingItem(
                foreshadowing_id=self._slug(f"live-foreshadowing:{record.project_id}:{text}"),
                text=text,
                source_chapter_number=run.chapter_number,
            )
            if not any(entry.foreshadowing_id == item.foreshadowing_id for entry in current_archive.foreshadowing):
                current_archive.foreshadowing.append(item)
        for text in archive_update.question_points:
            item = QuestionItem(
                question_id=self._slug(f"live-question:{record.project_id}:{text}"),
                text=text,
                source_chapter_number=run.chapter_number,
            )
            if not any(entry.question_id == item.question_id for entry in current_archive.questions):
                current_archive.questions.append(item)
        snapshot = ArchiveSnapshot(
            snapshot_id=self._slug(f"live-snapshot:{version.version_id}:{run.chapter_number}"),
            chapter_number=run.chapter_number,
            created_at=self._now(),
            analysis_label=LIVE_AI_LABEL,
            characters=deepcopy(current_archive.characters),
            storylines=deepcopy(current_archive.storylines),
            foreshadowing=deepcopy(current_archive.foreshadowing),
            questions=deepcopy(current_archive.questions),
        )
        current_archive.snapshots = [
            item for item in current_archive.snapshots if item.chapter_number != run.chapter_number
        ] + [snapshot]
        current_archive.snapshots.sort(key=lambda item: item.chapter_number)
        return current_archive

    def _charge_once(self, record: AIProjectRecord, run: DirectorRun) -> None:
        if run.credits_charged:
            return
        run.credits_charged = True
        run.used_credits = run.estimated_credits
        record.credits_used += run.used_credits
        record.credit_ledger.append(
            CreditLedgerEntry(
                ledger_id=self._slug(f"director-credit:{run.run_id}"),
                run_id=run.run_id,
                label=LIVE_AI_LABEL if self._runtime_available() else DEMO_AI_LABEL,
                credits=run.used_credits,
                created_at=self._now(),
            )
        )

    async def _finish_run(
        self,
        record: AIProjectRecord,
        run: DirectorRun,
        *,
        selected_choice_id: str,
        choice_source: str,
        choices: list[DirectorChoice] | None = None,
        transaction: _DirectorStageTransaction | None = None,
    ) -> None:
        available_choices = choices if choices is not None else (run.choices or self._choices(record))
        selected = next((choice for choice in available_choices if choice.choice_id == selected_choice_id), None)
        if selected is None:
            raise AIServiceError("choice_missing", "这个导演台选择不存在。", status_code=404)
        # 先持久化唯一候选集合，服务重启后可以从安全状态恢复；正式选择仍要
        # 等正文、审校、档案和稿本全部成功后才写入 selected_choice_id。
        run.choices = list(available_choices)
        stage_transaction = transaction or _DirectorStageTransaction()
        self._append_stage(run, "writing", "正文生成")
        review_summary = run.review_summary
        archive_candidates = dict(run.archive_candidates)
        archive_source_chapter = run.archive_source_chapter
        live_review: DirectorReviewResponse | None = None
        live_archive_update: DirectorArchiveResponse | None = None
        live_archive: StoryArchive | None = None
        if self._runtime_available() and not run.generated_content:
            if callable(getattr(self.runtime, "text", None)):
                content, _body_result, _body_cached = await self._live_body_text(record, run, selected)
                self._append_stage(run, "reviewing", "审校")
                review, archive = await self._live_review_archive(
                    record,
                    run,
                    selected,
                    content,
                    stage_transaction,
                )
                live_review = review
                live_archive_update = archive
                review_summary = review.summary
                archive_candidates = {
                    "characters": list(review.public_character_updates),
                    "plotlines": list(archive.plotline_updates),
                    "foreshadowing": list(archive.foreshadowing_candidates),
                    "questions": list(archive.question_points),
                }
                archive_source_chapter = archive.source_chapter
            else:
                # 阶段 15 旧 fake runtime 没有 text 方法，仅保留测试兼容；真实
                # LLMRuntime 永远走上面的纯文本分支。
                legacy_body = await self._legacy_live_body(record, run, selected, stage_transaction)
                content = legacy_body.content.strip()
                review_summary = legacy_body.review_summary
                archive_candidates = {
                    "characters": list(legacy_body.public_character_updates),
                    "plotlines": list(legacy_body.plotline_updates),
                    "foreshadowing": list(legacy_body.foreshadowing_candidates),
                    "questions": list(legacy_body.question_points),
                }
                archive_source_chapter = run.chapter_number
        elif run.generated_content:
            content = run.generated_content
        else:
            content = self._deterministic_generated_content(record, selected)
        if not content.strip():
            raise AIServiceError("empty_generated_content", "模型没有生成正文，本轮没有写入正式稿。", status_code=502)
        if not self._runtime_available() or not callable(getattr(self.runtime, "text", None)):
            self._append_stage(run, "reviewing", "审校")
            self._append_stage(run, "updating_archive", "更新档案")
        elif run.generated_content:
            self._append_stage(run, "reviewing", "审校")
            self._append_stage(run, "updating_archive", "更新档案")
        # 正式稿写入发生在正文、审校和档案候选都通过之后；live 档案只在内存
        # 构造，随后与正文、快照在独立稿本的一次保存中提交。
        if live_review is not None and live_archive_update is not None:
            live_archive = self._apply_live_archive(record, run, live_review, live_archive_update)
        # 先构造稿本/档案/分析任务的 staging projection；此处不写正式稿本。
        try:
            manuscript_projection = self.manuscript.prepare_system_generated_chapter(
                record.project_id,
                record.account_id,
                chapter_number=run.chapter_number,
                content=content,
                title=f"第{run.chapter_number}章 · 导演台初稿",
                archive=live_archive,
                idempotency_key=f"ai-director-{run.run_id}",
            )
        except IndependentServiceError as exc:
            raise AIServiceError("manuscript_change_pending", exc.message, status_code=exc.status_code) from exc
        independent_task_id = str(manuscript_projection["task"]["task_id"])
        # runtime 已经把安全调用 metadata/cache 落在 sidecar；这里仅把本轮
        # 人物公开状态合并到待提交对象，真正公开状态与正文一起过 marker。
        if transaction is not None or stage_transaction.calls:
            self._commit_stage_transaction(record, run, stage_transaction, persist=False)
        expected_ai_revision = run.run_revision
        run.choices = list(available_choices)
        run.selected_choice_id = selected.choice_id
        run.choice_source = "character" if choice_source in {"character", "role"} else "author"  # type: ignore[assignment]
        run.pending_choice_id = None
        run.generated_content = content
        run.preview_content = content[:280]
        run.review_summary = review_summary
        run.archive_candidates = archive_candidates
        run.archive_source_chapter = archive_source_chapter
        run.independent_task_id = independent_task_id
        self._charge_once(record, run)
        self._append_stage(run, "completed", "完成")
        run.completed_at = self._now()
        completion_notification = self._completion_notification(run)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        transaction_id = self._slug(f"director-transaction:{run.run_id}:{content_hash}")
        credit_entry = next(
            (item.model_dump(mode="json") for item in record.credit_ledger if item.run_id == run.run_id),
            None,
        )
        payload = TransactionPayload(
            transaction_id=transaction_id,
            project_id=record.project_id,
            account_id=record.account_id,
            run_id=run.run_id,
            version_id=str(manuscript_projection["version_id"]),
            chapter_number=run.chapter_number,
            idempotency_key=f"ai-director-{run.run_id}",
            content_hash=content_hash,
            ai_run=run.model_dump(mode="json"),
            professional_roles=[item.model_dump(mode="json") for item in record.role_statuses],
            character_updates=[
                {
                    "character_id": character_id,
                    "emotional_state": emotional_state,
                    "goal": goal,
                }
                for character_id, emotional_state, goal in stage_transaction.character_updates
            ],
            chapter=manuscript_projection["chapter"],
            archive=manuscript_projection["archive"],
            task=manuscript_projection["task"],
            notification=completion_notification.model_dump(mode="json"),
            credit_entry=credit_entry,
            baseline_archive=manuscript_projection.get("baseline_archive"),
            baseline_professional_roles=[item.model_dump(mode="json") for item in record.role_statuses],
            baseline_character_states=[
                {
                    "character_id": agent.character_id,
                    "emotional_state": agent.emotional_state,
                    "goal": agent.goal,
                }
                for agent in record.story_characters
            ],
        )
        try:
            journal = self.transactions.prepare(
                payload=payload,
                expected_ai_run_revision=expected_ai_revision,
                expected_manuscript_revision=int(manuscript_projection["expected_chapter_revision"]),
            )
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            raise AIServiceError(
                "director_transaction_not_prepared",
                "本轮没有写入正式正文，事务仍可重试。",
                status_code=503,
                data={"retryable": True},
            ) from exc
        try:
            self.transactions.commit(journal.transaction_id)
            if not any(item.notification_id == completion_notification.notification_id for item in record.notifications):
                record.notifications.append(completion_notification)
                record.notifications = record.notifications[-50:]
        except TransactionNotCommitted as exc:
            raise AIServiceError(
                "director_transaction_not_committed",
                "本轮没有写入正式正文，事务保持可重试状态。",
                status_code=503,
                data={"transaction_id": exc.transaction_id, "retryable": True},
            ) from None
        except TransactionCommitted:
            if not any(item.notification_id == completion_notification.notification_id for item in record.notifications):
                record.notifications.append(completion_notification)
                record.notifications = record.notifications[-50:]
            raise

    def _fail_run(self, record: AIProjectRecord, run: DirectorRun, message: str) -> None:
        self._append_stage(run, "failed", "失败，可重试")
        run.error_message = message
        run.completed_at = None
        run.credits_charged = False
        run.used_credits = 0
        self._notify(record, "director_failed", message)

    async def advance(self, project_id: str, account_id: str, run_id: str) -> dict[str, Any]:
        """推进浏览器工作台延迟展示的一个后台安全节点。"""

        record = self._load(project_id, account_id)
        run = self._run(record, run_id)
        if run.status in {"completed", "failed", "waiting_for_choice", "paused"}:
            return self.workspace(project_id, account_id)
        if run.status != "character_simulation":
            raise AIServiceError("director_not_advancable", "当前后台轮转没有可推进的安全节点。", status_code=409)
        self._processing_runs.add(run.run_id)
        try:
            await self._advance_to_safe_point(record, run)
        finally:
            self._processing_runs.discard(run.run_id)
        record.updated_at = self._now()
        self.store.save(record)
        return self.workspace(project_id, account_id)

    def read_run(self, project_id: str, account_id: str, run_id: str) -> dict[str, Any]:
        record = self._load(project_id, account_id)
        summary = self._model_summary(record)
        return {
            "run": self._public_run(record, self._run(record, run_id)),
            "analysis_label": LIVE_AI_LABEL if summary["status"] == "connected" else FAILED_AI_LABEL if summary["status"] == "failed" else DEMO_AI_LABEL,
            "mode": summary["mode"],
            "provider": summary["provider"],
            "model": summary["model"],
            "usage": summary["usage"],
        }

    async def choose(self, project_id: str, account_id: str, run_id: str, choice_id: str) -> dict[str, Any]:
        record = self._load(project_id, account_id)
        run = self._run(record, run_id)
        if run.selected_choice_id is not None:
            if run.selected_choice_id == choice_id:
                return self.workspace(project_id, account_id)
            raise AIServiceError("choice_already_selected", "这个关键节点已经选择过，不能切换成平行正文。", status_code=409)
        if run.status != "waiting_for_choice":
            raise AIServiceError("choice_not_available", "当前还没有可选择的关键节点。", status_code=409)
        if not any(choice.choice_id == choice_id for choice in run.choices):
            raise AIServiceError("choice_missing", "请选择页面展示的三个方向之一。", status_code=422)
        if run.pending_choice_id is not None:
            if run.pending_choice_id == choice_id:
                return self.workspace(project_id, account_id)
            raise AIServiceError("choice_in_progress", "上一个选择正在接续，请稍候读取导演台状态。", status_code=409)
        self._processing_runs.add(run.run_id)
        run.pending_choice_id = choice_id
        run.updated_at = self._now()
        self.store.save(record)
        committed_marker = False
        try:
            choice_source = self._choice_source_for(run.choices, choice_id)
            await self._finish_run(record, run, selected_choice_id=choice_id, choice_source=choice_source)
            run.pending_choice_id = None
            # coordinator 已经把完整 AI projection（含通知/账本）写入 store；
            # 不再用本地旧 record 覆盖它。
            committed_marker = True
        except TransactionCommitted:
            committed_marker = True
            run.pending_choice_id = None
        except AIServiceError as exc:
            self._fail_run(record, run, exc.message)
        finally:
            self._processing_runs.discard(run.run_id)
        record.updated_at = self._now()
        if not committed_marker:
            self.store.save(record)
        return self.workspace(project_id, account_id)

    def pause(self, project_id: str, account_id: str, run_id: str) -> dict[str, Any]:
        record = self._load(project_id, account_id)
        run = self._run(record, run_id)
        if run.status in {"completed", "failed", "waiting_for_choice", "paused"}:
            return self.workspace(project_id, account_id)
        self._append_stage(run, "paused", "已暂停，等待继续")
        record.updated_at = self._now()
        self.store.save(record)
        return self.workspace(project_id, account_id)

    async def resume(self, project_id: str, account_id: str, run_id: str) -> dict[str, Any]:
        record = self._load(project_id, account_id)
        run = self._run(record, run_id)
        if run.status != "paused":
            return self.workspace(project_id, account_id)
        run.status = "queued"
        run.current_stage = "排队"
        self._processing_runs.add(run.run_id)
        try:
            await self._advance_to_safe_point(record, run)
        finally:
            self._processing_runs.discard(run.run_id)
        record.updated_at = self._now()
        self.store.save(record)
        return self.workspace(project_id, account_id)

    async def retry(self, project_id: str, account_id: str, run_id: str) -> dict[str, Any]:
        record = self._load(project_id, account_id)
        run = self._run(record, run_id)
        if run.status != "failed":
            raise AIServiceError("director_not_retryable", "只有失败的导演台任务可以重试。", status_code=409)
        if run.error_message == "author_revision_conflict":
            # 冲突事务已经是不可复活的 superseded 证据；重试必须创建新的
            # run/transaction/idempotency key，并以作者最新稿本计算下一章基线。
            retry_key = f"{run.idempotency_key or run.run_id}:author-conflict-retry"
            existing_retry = next((item for item in record.runs if item.idempotency_key == retry_key), None)
            if existing_retry is not None:
                record.active_run_id = existing_retry.run_id
                return self.workspace(project_id, account_id)
            chapter_number = self._next_chapter_number(record)
            now = self._now()
            retry_run = DirectorRun(
                run_id=self._slug(f"director-retry:{run.run_id}:{retry_key}"),
                project_id=project_id,
                blueprint_revision=record.blueprint_revision,
                chapter_number=chapter_number,
                strategy=run.strategy,
                idempotency_key=retry_key,
                estimated_credits=DEMO_CREDIT_ESTIMATE,
                created_at=now,
                updated_at=now,
            )
            record.runs.append(retry_run)
            record.active_run_id = retry_run.run_id
            record.updated_at = now
            self.store.save(record)
            self._processing_runs.add(retry_run.run_id)
            try:
                await self._advance_to_safe_point(record, retry_run)
            finally:
                self._processing_runs.discard(retry_run.run_id)
            record.updated_at = self._now()
            self.store.save(record)
            return self.workspace(project_id, account_id)
        # 失败任务可能是在旧蓝图上产生的；重试前把它重新绑定到作者刚确认的版本，
        # 这样修正蓝图后的单一当前任务仍能被工作台恢复和展示。
        run.blueprint_revision = record.blueprint_revision
        run.status = "queued"
        run.current_stage = "排队"
        run.error_message = None
        run.selected_choice_id = None
        run.choice_source = "none"
        run.pending_choice_id = None
        run.choices = []
        self._processing_runs.add(run.run_id)
        try:
            await self._advance_to_safe_point(record, run)
        finally:
            self._processing_runs.discard(run.run_id)
        record.updated_at = self._now()
        self.store.save(record)
        return self.workspace(project_id, account_id)

    def role_contexts(self, project_id: str, account_id: str, run_id: str) -> list[RoleContext]:
        record = self._load(project_id, account_id)
        self._run(record, run_id)
        blueprint = record.blueprint
        shared = blueprint.world_rules or "共享世界观尚未补充。"
        protagonist = blueprint.protagonist or "主角"
        contexts = {
            "plot": ["已知主冲突的推进方向", "关键节点尚未选择"],
            "character": [f"{protagonist}的当前动机", "与顾遥的关系仍在变化"],
            "world": ["公共档案的来源规则", "尚未确认的设定必须保持疑问"],
            "rhythm": [blueprint.target_length or "预期体量尚未明确", "当前章节需要留下可回看节点"],
        }
        private = {
            "plot": ["剧情角色只知道主线推进和已公开事件。"],
            "character": [f"人物角色只知道 {protagonist} 亲历或被告知的事情。"],
            "world": ["世界观角色只知道已写入公共规则的事实。"],
            "rhythm": ["节奏角色只知道篇幅、章末钩子和结构信号。"],
        }
        labels = {"plot": "剧情", "character": "人物", "world": "世界观", "rhythm": "节奏"}
        return [
            RoleContext(
                role_id=role_id,
                role_name=labels[role_id],
                entity_layer="professional",
                access_scope="global",
                shared_worldview=shared,
                necessary_facts=contexts[role_id],
                private_memory=[f"{labels[role_id]}专业角色只保留职责工作笔记，不持有故事人物私有事实。"],
            )
            for role_id in ("plot", "character", "world", "rhythm")
        ]

    def story_character_contexts(self, project_id: str, account_id: str, run_id: str) -> list[StoryCharacterContext]:
        """返回每个故事人物自己的可见上下文，禁止跨人物拼接私有记忆。"""

        record = self._load(project_id, account_id)
        run = self._run(record, run_id)
        self._sync_story_characters(record)
        shared = record.blueprint.world_rules or "共享世界规则尚未补充。"
        public_facts = [fact for fact in [record.blueprint.core_premise, record.blueprint.core_conflict] if fact]
        result: list[StoryCharacterContext] = []
        for agent in record.story_characters:
            necessary = list(agent.known_facts)
            if run.simulated_character_id == agent.character_id and agent.goal:
                necessary.append(agent.goal)
            result.append(
                StoryCharacterContext(
                    character_id=agent.character_id,
                    name=agent.name,
                    shared_world_rules=shared,
                    public_facts=list(agent.public_facts or public_facts[:1]),
                    necessary_facts=necessary,
                    own_experiences=list(agent.experiences),
                    private_memory=list(agent.private_memory),
                    current_scene=agent.current_scene,
                    current_goal=agent.goal,
                    emotional_state=agent.emotional_state,
                )
            )
        return result
