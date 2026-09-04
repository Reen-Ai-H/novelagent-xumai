"""独立作品拆解服务。

本阶段先提供可审计的确定性拆解引擎：它只读取当前独立稿本的正式正文，
将结构化结论和最小证据片段写入独立侧车。未来接入模型时可以替换
``_build_document``，而不改变账户、来源、任务、回链和失败合同。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from app.core.deconstruction_store import DeconstructionStore, DeconstructionStoreError
from app.core.independent_service import IndependentServiceError, IndependentWorkspaceService
from schemas.deconstruction import (
    ChapterBreakdown,
    DeconstructionActions,
    DeconstructionActiveRun,
    DeconstructionCandidate,
    DeconstructionDocument,
    DeconstructionDocumentPublic,
    DeconstructionError,
    DeconstructionHistoryItem,
    DeconstructionObservation,
    DeconstructionOverview,
    DeconstructionProgress,
    DeconstructionProjectRecord,
    DeconstructionResult,
    DeconstructionSource,
    DeconstructionState,
    DeconstructionStatus,
    EvidenceRef,
    TimelineNode,
)


ANALYSIS_LABEL = "确定性结构拆解（无模型）"
MAX_HISTORY = 20
MAX_EXCERPT = 150


class DeconstructionServiceError(Exception):
    """可安全返回给当前账户的拆解业务错误。"""

    def __init__(self, code: str, message: str, *, status_code: int = 400, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data


class DeconstructionAnalysisError(Exception):
    """内部确定性分析失败，不携带正文原文。"""


@dataclass(frozen=True)
class _SourceChapter:
    chapter_id: str
    chapter_number: int
    title: str
    content: str
    server_revision: int


@dataclass(frozen=True)
class _Source:
    project_id: str
    account_id: str
    title: str
    version_id: str | None
    source_revision: int | None
    source_hash: str | None
    chapters: tuple[_SourceChapter, ...]
    pending_changes: bool
    character_names: tuple[str, ...]

    @property
    def sufficient(self) -> bool:
        return bool(self.version_id and self.chapters)


class DeconstructionService:
    """作品拆解的读取、排队、恢复和确定性分析。"""

    def __init__(
        self,
        *,
        independent: IndependentWorkspaceService,
        store: DeconstructionStore | None = None,
    ) -> None:
        self.independent = independent
        self.store = store or DeconstructionStore()
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _slug(value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()[:20]

    @staticmethod
    def _word_count(text: str) -> int:
        return len(re.sub(r"\s+", "", text))

    @staticmethod
    def _clip(text: str, limit: int = 240) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        return normalized[:limit]

    @staticmethod
    def _sentences(text: str) -> list[str]:
        parts = re.split(r"(?<=[。！？!?；;])|\n+", text)
        return [part.strip() for part in parts if part.strip()]

    @staticmethod
    def _paragraphs(text: str) -> list[str]:
        parts = re.split(r"\n\s*\n|\n", text)
        return [part.strip() for part in parts if part.strip()]

    def _load_independent_record(self, project_id: str, account_id: str):
        try:
            return self.independent._load(project_id, account_id)  # noqa: SLF001 - 同一后端侧车的内部来源边界。
        except IndependentServiceError as exc:
            if exc.code != "workspace_not_started":
                raise DeconstructionServiceError(exc.code, exc.message, status_code=exc.status_code, data=exc.data) from None
            try:
                return self.independent._ensure_record(project_id, account_id)  # noqa: SLF001 - 读取未初始化作品的诚实空态。
            except IndependentServiceError as ensure_exc:
                raise DeconstructionServiceError(
                    ensure_exc.code,
                    ensure_exc.message,
                    status_code=ensure_exc.status_code,
                    data=ensure_exc.data,
                ) from None

    def _source(self, project_id: str, account_id: str) -> _Source:
        record = self._load_independent_record(project_id, account_id)
        version = next(
            (item for item in record.versions if item.version_id == record.active_version_id),
            None,
        )
        if version is None:
            return _Source(
                project_id=project_id,
                account_id=account_id,
                title=record.title,
                version_id=None,
                source_revision=None,
                source_hash=None,
                chapters=(),
                pending_changes=record.pending_changes is not None,
                character_names=(),
            )

        chapters: list[_SourceChapter] = []
        for chapter in sorted(version.chapters, key=lambda item: item.chapter_number):
            content = chapter.formal_content or ""
            if not content.strip():
                continue
            chapters.append(
                _SourceChapter(
                    chapter_id=chapter.chapter_id,
                    chapter_number=chapter.chapter_number,
                    title=chapter.formal_title or chapter.title,
                    content=content,
                    server_revision=chapter.server_revision,
                )
            )

        source_payload = {
            "version_id": version.version_id,
            "chapters": [
                {
                    "chapter_id": chapter.chapter_id,
                    "chapter_number": chapter.chapter_number,
                    "title": chapter.title,
                    "content": chapter.content,
                    "server_revision": chapter.server_revision,
                }
                for chapter in chapters
            ],
        }
        source_hash = hashlib.sha256(
            json.dumps(source_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        archive_names = tuple(
            str(item.name).strip()
            for item in version.archive.characters
            if str(item.name).strip()
        )
        return _Source(
            project_id=project_id,
            account_id=account_id,
            title=record.title,
            version_id=version.version_id,
            source_revision=max((chapter.server_revision for chapter in chapters), default=0),
            source_hash=source_hash,
            chapters=tuple(chapters),
            pending_changes=record.pending_changes is not None,
            character_names=archive_names,
        )

    def _record(self, project_id: str, account_id: str) -> DeconstructionProjectRecord | None:
        try:
            record = self.store.load(project_id)
        except DeconstructionStoreError:
            raise DeconstructionServiceError(
                "deconstruction_store_unavailable",
                "作品拆解暂时不可读取，请稍后重试。",
                status_code=503,
            ) from None
        if record is not None and record.account_id != account_id:
            raise DeconstructionServiceError("project_forbidden", "无权访问这部作品。", status_code=403)
        return record

    @staticmethod
    def _document(record: DeconstructionProjectRecord | None, document_id: str | None) -> DeconstructionDocument | None:
        if record is None or not document_id:
            return None
        return next((item for item in record.documents if item.document_id == document_id), None)

    @staticmethod
    def _document_summary(document: DeconstructionDocument) -> dict[str, object]:
        payload = document.model_dump(mode="json")
        payload = {
            key: payload[key]
            for key in (
                "document_id",
                "status",
                "source_version_id",
                "source_revision",
                "source_hash",
                "retry_count",
                "analysis_label",
                "created_at",
                "updated_at",
                "completed_at",
            )
        }
        return DeconstructionHistoryItem.model_validate(payload).model_dump(mode="json")

    @staticmethod
    def _public_document(document: DeconstructionDocument | None) -> dict[str, object] | None:
        if document is None:
            return None
        payload = document.model_dump(mode="json")
        payload.pop("account_id", None)
        return DeconstructionDocumentPublic.model_validate(payload).model_dump(mode="json")

    @staticmethod
    def _run_status(document: DeconstructionDocument | None) -> str:
        if document is None:
            return "none"
        if document.status in {"queued", "running", "completed", "failed_retryable"}:
            return document.status
        return "completed" if document.overview is not None else "none"

    @staticmethod
    def _result(
        document: DeconstructionDocument | None,
        source_match: bool,
        *,
        effective_status: DeconstructionStatus | None = None,
    ) -> DeconstructionResult | None:
        if (
            document is None
            or not source_match
            or effective_status not in {None, "completed"}
            or document.status != "completed"
            or document.overview is None
        ):
            return None
        payload = document.model_dump(
            mode="json",
            exclude={
                "account_id",
                "project_id",
                "progress_percent",
                "current_stage",
                "idempotency_key",
                "retry_count",
                "error_message",
                "created_at",
                "updated_at",
                "completed_at",
            },
        )
        payload["status"] = "completed"
        return DeconstructionResult.model_validate(payload)

    @staticmethod
    def _source_summary(source: _Source, source_match: bool) -> DeconstructionSource:
        return DeconstructionSource(
            version_id=source.version_id,
            revision=source.source_revision,
            hash=source.source_hash,
            match=source_match,
            chapter_count=len(source.chapters),
            total_word_count=sum(DeconstructionService._word_count(item.content) for item in source.chapters),
        )

    def _response(
        self,
        source: _Source,
        record: DeconstructionProjectRecord | None,
        *,
        force_status: DeconstructionStatus | None = None,
        empty_reason: str | None = None,
    ) -> dict[str, object]:
        active = self._document(record, record.active_document_id if record else None)
        source_match = bool(
            active is not None
            and source.sufficient
            and active.source_version_id == source.version_id
            and active.source_hash == source.source_hash
        )
        status: DeconstructionStatus
        if force_status is not None:
            status = force_status
        elif not source.sufficient:
            status = "empty"
            empty_reason = empty_reason or "完成并保存至少一章正文后，作品拆解才有足够材料。"
        elif source.pending_changes:
            status = "rebuild_required"
        elif active is None:
            status = "rebuild_required"
        elif not source_match:
            status = "stale"
        else:
            status = active.status

        if status == "empty":
            progress = 0
            current_stage = "等待正文"
            error_message = None
            retryable = False
            error_code = None
        elif status in {"stale", "rebuild_required"}:
            progress = active.progress_percent if active else 0
            current_stage = "等待根据当前正文更新"
            error_message = (
                "当前正式正文已变化，请生成一版新的作品拆解。"
                if status == "stale"
                else "当前作者修改尚未确认，请先完成修改后再生成作品拆解。"
            )
            retryable = False
            error_code = "source_stale" if status == "stale" else "pending_changes"
        else:
            progress = active.progress_percent if active else 0
            current_stage = active.current_stage if active else "等待拆解"
            error_message = active.error_message if active else None
            retryable = status == "failed_retryable"
            error_code = "deconstruction_failed" if status == "failed_retryable" else None

        history: list[dict[str, object]] = []
        if record is not None:
            history = [self._document_summary(item) for item in record.documents[-MAX_HISTORY:]]
        run_status = self._run_status(active)
        source_summary = self._source_summary(source, source_match)
        progress_model = DeconstructionProgress(percent=progress, current_stage=current_stage)
        actions_model = DeconstructionActions(
            retry=status == "failed_retryable",
            rebuild=status in {"stale", "rebuild_required", "empty"} and source.sufficient and not source.pending_changes,
        )
        result_model = self._result(active, source_match, effective_status=status)
        active_run = None
        if active is not None:
            active_run = DeconstructionActiveRun(
                document_id=active.document_id,
                run_status=run_status,  # type: ignore[arg-type]
                source_version_id=active.source_version_id,
                source_revision=active.source_revision,
                source_hash=active.source_hash,
                retry_count=active.retry_count,
                idempotency_key=active.idempotency_key,
                analysis_label=active.analysis_label,
                created_at=active.created_at,
                updated_at=active.updated_at,
                completed_at=active.completed_at,
            )
        error_model = None
        if error_code is not None and error_message is not None:
            error_model = DeconstructionError(code=error_code, message=error_message, retryable=retryable)
        canonical = DeconstructionState(
            effective_status=status,
            run_status=run_status,  # type: ignore[arg-type]
            source_match=source_match,
            progress=progress_model,
            current_stage=current_stage,
            source=source_summary,
            active_run=active_run,
            result=result_model,
            actions=actions_model,
            error=error_model,
        )
        public_active = (
            self._public_document(active)
            if active is not None and source_match and status not in {"stale", "rebuild_required"}
            else None
        )
        payload = {
            "schema_version": "1.0",
            "initialized": source.sufficient,
            "project_id": source.project_id,
            "title": source.title,
            "mode": "independent",
            "effective_status": status,
            "run_status": run_status,
            "source_match": source_match,
            "progress": progress_model.model_dump(mode="json"),
            "source": source_summary.model_dump(mode="json"),
            "active_run": active_run.model_dump(mode="json") if active_run is not None else None,
            "result": result_model.model_dump(mode="json") if result_model is not None else None,
            "error": error_model.model_dump(mode="json") if error_model is not None else None,
            "actions": actions_model.model_dump(mode="json"),
            "history": history,
            "status": status,
            "progress_percent": progress,
            "current_stage": current_stage,
            "source_version_id": source.version_id,
            "source_revision": source.source_revision,
            "source_hash": source.source_hash,
            "analysis_label": ANALYSIS_LABEL,
            "empty_reason": empty_reason,
            "error_message": error_message,
            "retryable": retryable,
            "document": public_active,
        }
        payload["deconstruction"] = canonical.model_dump(mode="json")
        return payload

    @staticmethod
    def _source_precondition_data(source: _Source) -> dict[str, object]:
        return {"source": DeconstructionService._source_summary(source, source_match=False).model_dump(mode="json")}

    def _check_source_precondition(
        self,
        source: _Source,
        *,
        expected_source_version_id: str | None = None,
        expected_source_revision: int | None = None,
        expected_source_hash: str | None = None,
    ) -> None:
        checks = (
            expected_source_version_id is None or expected_source_version_id == source.version_id,
            expected_source_revision is None or expected_source_revision == source.source_revision,
            expected_source_hash is None or expected_source_hash == source.source_hash,
        )
        if not all(checks):
            raise DeconstructionServiceError(
                "source_conflict",
                "作品正文已变化，请刷新后再执行拆解操作。",
                status_code=409,
                data=self._source_precondition_data(source),
            )

    def reconcile_outbox(
        self,
        project_id: str,
        account_id: str,
        *,
        reason: str | None = None,
        limit: int = 8,
    ) -> int:
        """派发与正文同文件提交的 outbox；不持拆解锁调用独立服务。"""

        del reason
        try:
            record = self.independent._load(project_id, account_id)  # noqa: SLF001 - 同一后端恢复边界。
        except IndependentServiceError as exc:
            if exc.code == "workspace_not_started":
                return 0
            raise DeconstructionServiceError(exc.code, exc.message, status_code=exc.status_code, data=exc.data) from None
        except (OSError, UnicodeError, ValueError, TypeError):
            raise DeconstructionServiceError(
                "workspace_unavailable",
                "作品正文暂时不可读取，拆解事件会在恢复后重试。",
                status_code=503,
            ) from None
        events = list(record.deconstruction_outbox[: max(0, limit)])
        processed = 0
        for event in events:
            try:
                self.enqueue_for_project(project_id, account_id, reason=event.reason)
            except DeconstructionServiceError as exc:
                self.independent.mark_deconstruction_event_retry(
                    project_id,
                    account_id,
                    error_code=exc.code,
                )
                continue
            except (OSError, ValueError, KeyError, TypeError):
                self.independent.mark_deconstruction_event_retry(
                    project_id,
                    account_id,
                    error_code="dispatch_unavailable",
                )
                continue
            try:
                self.independent.ack_deconstruction_event(project_id, account_id, event.event_id)
            except (IndependentServiceError, OSError, UnicodeError, ValueError, TypeError):
                # 拆解结果已按稳定 source 幂等写入，但 outbox 确认失败时保留
                # 事件；下一轮会再次命中同一文档而不会创建重复结果。
                self.independent.mark_deconstruction_event_retry(
                    project_id,
                    account_id,
                    error_code="ack_unavailable",
                )
                continue
            processed += 1
        return processed

    def reconcile_all_outboxes(self, *, limit: int = 32) -> int:
        processed = 0
        for record in self.independent.store.list_records():
            if processed >= limit or not record.deconstruction_outbox:
                continue
            try:
                processed += self.reconcile_outbox(record.project_id, record.account_id, limit=limit - processed)
            except (DeconstructionServiceError, OSError, ValueError, KeyError, TypeError):
                continue
        return processed

    def read(self, project_id: str, account_id: str) -> dict[str, object]:
        self.reconcile_outbox(project_id, account_id)
        source = self._source(project_id, account_id)
        record = self._record(project_id, account_id)
        if source.sufficient and not source.pending_changes and record is None:
            self.enqueue_for_project(project_id, account_id, reason="首次读取补建")
            record = self._record(project_id, account_id)
        return self._response(source, record)

    def enqueue_for_project(
        self,
        project_id: str,
        account_id: str,
        *,
        reason: str = "正文更新",
        idempotency_key: str | None = None,
        expected_source_version_id: str | None = None,
        expected_source_revision: int | None = None,
        expected_source_hash: str | None = None,
    ) -> DeconstructionDocument:
        del reason  # 触发原因保存在正文 outbox；拆解结果只保留安全状态。
        source = self._source(project_id, account_id)
        self._check_source_precondition(
            source,
            expected_source_version_id=expected_source_version_id,
            expected_source_revision=expected_source_revision,
            expected_source_hash=expected_source_hash,
        )
        if not source.sufficient:
            raise DeconstructionServiceError(
                "deconstruction_empty",
                "完成并保存至少一章正文后，才能生成作品拆解。",
                status_code=422,
            )
        if source.pending_changes:
            raise DeconstructionServiceError(
                "deconstruction_rebuild_required",
                "当前有作者修改待确认，请先确认修改后再生成作品拆解。",
                status_code=409,
            )
        assert source.version_id is not None
        assert source.source_hash is not None
        with self._lock:
            record = self._record(project_id, account_id)
            if record is None:
                record = DeconstructionProjectRecord(project_id=project_id, account_id=account_id)
            existing = next(
                (
                    item
                    for item in record.documents
                    if item.source_version_id == source.version_id and item.source_hash == source.source_hash
                ),
                None,
            )
            if existing is not None:
                if existing.status == "failed_retryable":
                    existing.status = "queued"
                    existing.progress_percent = 0
                    existing.current_stage = "等待重新拆解"
                    existing.error_message = None
                    existing.updated_at = self._now()
                    record.active_document_id = existing.document_id
                    record.updated_at = existing.updated_at
                    self.store.save(record)
                elif record.active_document_id != existing.document_id:
                    record.active_document_id = existing.document_id
                    record.updated_at = self._now()
                    self.store.save(record)
                return existing

            now = self._now()
            document_id = self._slug(f"deconstruction:{project_id}:{source.version_id}:{source.source_hash}")
            document = DeconstructionDocument(
                document_id=document_id,
                project_id=project_id,
                account_id=account_id,
                source_version_id=source.version_id,
                source_revision=source.source_revision or 0,
                source_hash=source.source_hash,
                status="queued",
                progress_percent=0,
                current_stage="等待拆解",
                idempotency_key=idempotency_key or document_id,
                created_at=now,
                updated_at=now,
            )
            record.documents.append(document)
            record.documents = record.documents[-MAX_HISTORY:]
            record.active_document_id = document.document_id
            record.updated_at = now
            self.store.save(record)
            return document

    def retry(
        self,
        project_id: str,
        account_id: str,
        document_id: str | None = None,
        *,
        idempotency_key: str | None = None,
        expected_source_version_id: str | None = None,
        expected_source_revision: int | None = None,
        expected_source_hash: str | None = None,
    ) -> DeconstructionDocument:
        source = self._source(project_id, account_id)
        self._check_source_precondition(
            source,
            expected_source_version_id=expected_source_version_id,
            expected_source_revision=expected_source_revision,
            expected_source_hash=expected_source_hash,
        )
        record = self._record(project_id, account_id)
        document = self._document(record, document_id or (record.active_document_id if record else None))
        if document is None:
            return self.enqueue_for_project(
                project_id,
                account_id,
                reason="手动重建",
                idempotency_key=idempotency_key,
                expected_source_version_id=expected_source_version_id,
                expected_source_revision=expected_source_revision,
                expected_source_hash=expected_source_hash,
            )
        if document.status not in {"failed_retryable", "stale", "rebuild_required"}:
            if document.status in {"queued", "running", "completed"}:
                return document
            raise DeconstructionServiceError("deconstruction_not_retryable", "当前拆解没有可执行的重试。", status_code=409)
        if not source.sufficient or source.pending_changes:
            raise DeconstructionServiceError(
                "deconstruction_rebuild_required",
                "请先完成并确认当前正文修改，再重试作品拆解。",
                status_code=409,
            )
        if document.source_version_id != source.version_id or document.source_hash != source.source_hash:
            return self.enqueue_for_project(
                project_id,
                account_id,
                reason="基于新稿本重建",
                idempotency_key=idempotency_key,
            )
        with self._lock:
            record = self._record(project_id, account_id)
            document = self._document(record, document.document_id)
            if document is None:
                return self.enqueue_for_project(project_id, account_id, reason="重试材料重新读取")
            document.status = "queued"
            document.progress_percent = 0
            document.current_stage = "等待重新拆解"
            document.error_message = None
            document.retry_count += 1
            if idempotency_key:
                document.idempotency_key = idempotency_key
            document.updated_at = self._now()
            assert record is not None
            record.active_document_id = document.document_id
            record.updated_at = document.updated_at
            self.store.save(record)
            return document

    @staticmethod
    def _utf16_length(text: str) -> int:
        """浏览器 textarea 的 offset 单位：UTF-16 code units。"""

        return len(text.encode("utf-16-le")) // 2

    def _evidence(
        self,
        source: _Source,
        chapter: _SourceChapter,
        document: DeconstructionDocument,
        phrase: str,
        label: str,
        *,
        offset_hint: int = 0,
    ) -> EvidenceRef:
        content = chapter.content
        phrase = phrase.strip() or content
        position = content.find(phrase, max(0, offset_hint))
        if position < 0:
            position = content.find(phrase)
        if position < 0:
            position = 0
        end = min(len(content), position + MAX_EXCERPT)
        excerpt = content[position:end].strip()
        evidence_id = self._slug(
            f"evidence:{document.document_id}:{source.version_id}:{chapter.chapter_id}:{label}:{position}:{excerpt}"
        )
        target_path = (
            f"/independent/{source.project_id}?version_id={source.version_id}"
            f"&chapter_id={chapter.chapter_id}&evidence_id={evidence_id}"
            f"&document_id={document.document_id}"
        )
        return EvidenceRef(
            evidence_id=evidence_id,
            document_id=document.document_id,
            source_version_id=source.version_id or "",
            source_revision=source.source_revision or 0,
            source_hash=source.source_hash or "",
            chapter_id=chapter.chapter_id,
            chapter_number=chapter.chapter_number,
            start_offset=self._utf16_length(content[:position]),
            end_offset=self._utf16_length(content[:end]),
            offset_unit="utf16_code_unit",
            excerpt=excerpt,
            label=label,
            target_path=target_path,
        )

    def _first_matching_sentence(self, text: str, patterns: tuple[str, ...]) -> str | None:
        for sentence in self._sentences(text):
            if any(pattern in sentence for pattern in patterns):
                return sentence
        return None

    def _character_names_for_chapter(self, source: _Source, chapter: _SourceChapter) -> list[str]:
        names = list(source.character_names)
        for group in re.findall(r"人物\s*[:：]\s*([^\n。；;]+)", chapter.content):
            for candidate in re.split(r"[、，,；;和与及]\s*", group):
                candidate = candidate.strip(" ：:，,、；;")
                if 1 < len(candidate) <= 20 and candidate not in names:
                    names.append(candidate)
        return names[:12]

    def _chapter_function(self, index: int, total: int, text: str) -> str:
        if total == 1:
            return "单章观察"
        if index == 0:
            return "开端观察"
        if index == total - 1:
            return "收束观察"
        if re.search(r"转折|决定|危机|爆发|终于|对抗", text):
            return "推进与转折观察"
        return "发展观察"

    def _build_document(self, source: _Source, document: DeconstructionDocument) -> None:
        if any("[[deconstruction-fail]]" in chapter.content for chapter in source.chapters):
            raise DeconstructionAnalysisError("demo_failure")
        if not source.chapters or not source.version_id:
            raise DeconstructionAnalysisError("empty_source")

        evidence: list[EvidenceRef] = []
        chapter_breakdowns: list[ChapterBreakdown] = []
        timeline: list[TimelineNode] = []
        total_chars = sum(len(chapter.content) for chapter in source.chapters)
        total_words = sum(self._word_count(chapter.content) for chapter in source.chapters)
        global_offset = 0

        for index, chapter in enumerate(source.chapters):
            text = chapter.content
            sentences = self._sentences(text)
            paragraphs = self._paragraphs(text) or [text]
            function = self._chapter_function(index, len(source.chapters), text)
            first_sentence = sentences[0] if sentences else self._clip(text)
            last_sentence = sentences[-1] if sentences else self._clip(text)
            chapter_refs: list[EvidenceRef] = []

            first_ref = self._evidence(source, chapter, document, first_sentence, "章节开头")
            last_ref = self._evidence(source, chapter, document, last_sentence, "章节结尾")
            chapter_refs.append(first_ref)
            if last_ref.evidence_id != first_ref.evidence_id:
                chapter_refs.append(last_ref)

            explicit_event_sentences = [
                sentence
                for sentence in sentences
                if re.search(r"发现|进入|离开|遇见|决定|收到|看见|寻找|回到|打开|听见", sentence)
            ]
            core_events = [self._clip(item, 220) for item in (explicit_event_sentences or sentences[:3])[:4]]
            if not core_events:
                core_events = ["不确定：正文暂未提供可提炼的核心事件。"]

            conflict_sentence = self._first_matching_sentence(
                text,
                ("冲突", "对抗", "危险", "争执", "阻止", "追赶", "必须", "却", "但是"),
            )
            information_sentence = self._first_matching_sentence(
                text,
                ("发现", "知道", "揭开", "线索", "秘密", "原来", "看见"),
            )
            relationship_sentence = self._first_matching_sentence(
                text,
                ("相信", "不信", "合作", "保护", "告别", "争吵", "关系"),
            )
            emotional_sentence = self._first_matching_sentence(
                text,
                ("害怕", "紧张", "平静", "愤怒", "惊讶", "犹豫", "悲伤", "孤独", "开心"),
            )
            foreshadowing_sentences = [
                self._clip(sentence, 220)
                for sentence in sentences
                if re.search(r"伏笔|线索|秘密|约定|信封|钥匙|门缝", sentence)
            ][:6]
            if foreshadowing_sentences:
                ref = self._evidence(source, chapter, document, foreshadowing_sentences[0], "伏笔或线索")
                if ref.evidence_id not in {item.evidence_id for item in chapter_refs}:
                    chapter_refs.append(ref)
            evidence.extend(chapter_refs)

            scenes = [f"正文片段 {scene_index + 1}：{self._clip(paragraph, 140)}" for scene_index, paragraph in enumerate(paragraphs[:8])]
            uncertainty: list[str] = []
            if not conflict_sentence:
                uncertainty.append("未从正文明确识别核心冲突。")
            if not information_sentence:
                uncertainty.append("信息释放点不明显，仍需更多正文确认。")
            if len(source.chapters) < 3:
                uncertainty.append("章节数量较少，长程结构暂不能确定。")
            chapter_breakdowns.append(
                ChapterBreakdown(
                    chapter_id=chapter.chapter_id,
                    chapter_number=chapter.chapter_number,
                    title=chapter.title,
                    summary=self._clip(first_sentence, 260),
                    core_events=core_events,
                    narrative_function=function,
                    scenes=scenes,
                    conflict=self._clip(conflict_sentence, 300) if conflict_sentence else "不确定：未从正文明确识别。",
                    information_release=self._clip(information_sentence, 300) if information_sentence else "不确定：未从正文明确识别。",
                    relationship_change=self._clip(relationship_sentence, 300) if relationship_sentence else "不确定：未从正文明确识别。",
                    emotional_change=self._clip(emotional_sentence, 300) if emotional_sentence else "不确定：未从正文明确识别。",
                    foreshadowing=foreshadowing_sentences,
                    opening_hook=self._clip(first_sentence, 220),
                    ending_hook=self._clip(last_sentence, 220),
                    confidence=0.78 if explicit_event_sentences else 0.56,
                    uncertainty=uncertainty,
                    evidence_refs=chapter_refs,
                )
            )

            chapter_local_offset = 0
            for scene_index, paragraph in enumerate(paragraphs[:8]):
                local_offset = text.find(paragraph, chapter_local_offset)
                if local_offset < 0:
                    local_offset = chapter_local_offset
                local_end = min(len(text), local_offset + len(paragraph))
                chapter_local_offset = local_end
                global_start = global_offset + local_offset
                global_end = global_offset + local_end
                start_percent = round(global_start / total_chars * 100, 2) if total_chars else 0.0
                end_percent = round(global_end / total_chars * 100, 2) if total_chars else 100.0
                if index == len(source.chapters) - 1 and scene_index == len(paragraphs[:8]) - 1:
                    end_percent = 100.0
                word_start = sum(self._word_count(item.content) for item in source.chapters[:index]) + self._word_count(text[:local_offset])
                word_end = sum(self._word_count(item.content) for item in source.chapters[:index]) + self._word_count(text[:local_end])
                event = self._clip(self._sentences(paragraph)[0] if self._sentences(paragraph) else paragraph, 240)
                ref = self._evidence(source, chapter, document, paragraph, f"时间线片段 {scene_index + 1}", offset_hint=local_offset)
                evidence.append(ref)
                timeline.append(
                    TimelineNode(
                        node_id=self._slug(f"timeline:{source.project_id}:{source.version_id}:{chapter.chapter_id}:{scene_index}"),
                        label=f"第 {chapter.chapter_number} 章 · 片段 {scene_index + 1}",
                        normalized_start=start_percent,
                        normalized_end=end_percent,
                        chapter_id=chapter.chapter_id,
                        chapter_number=chapter.chapter_number,
                        chapter_title=chapter.title,
                        word_start=word_start,
                        word_end=word_end,
                        event=event,
                        narrative_function=function,
                        characters=self._character_names_for_chapter(source, chapter),
                        confidence=0.72 if event else 0.4,
                        uncertainty=[] if event else ["正文片段不足以判断事件。"],
                        evidence_refs=[ref],
                    )
                )
            global_offset += len(text)

        first_chapter = source.chapters[0]
        last_chapter = source.chapters[-1]
        opening_sentence = self._sentences(first_chapter.content)[0] if self._sentences(first_chapter.content) else first_chapter.content
        ending_sentence = self._sentences(last_chapter.content)[-1] if self._sentences(last_chapter.content) else last_chapter.content
        opening_ref = self._evidence(source, first_chapter, document, opening_sentence, "开端观察")
        ending_ref = self._evidence(source, last_chapter, document, ending_sentence, "结尾观察")
        evidence.extend([opening_ref, ending_ref])

        development_chapter = source.chapters[min(1, len(source.chapters) - 1)]
        development_sentence = self._first_matching_sentence(
            development_chapter.content,
            ("推进", "发展", "冲突", "决定", "进入", "继续"),
        )
        if development_sentence:
            development = DeconstructionObservation(
                text=f"发展观察：{self._clip(development_sentence, 360)}",
                confidence=0.65,
                evidence_refs=[self._evidence(source, development_chapter, document, development_sentence, "发展观察")],
            )
        else:
            development = DeconstructionObservation(
                text="发展观察：不确定，当前正文尚不足以判断中段推进。",
                confidence=0.3,
                uncertainty=["需要更多章节或更明确的事件转折。"],
            )

        climax_chapter = next(
            (
                chapter
                for chapter in reversed(source.chapters)
                if self._first_matching_sentence(chapter.content, ("终于", "危机", "爆发", "转折", "真相", "决定"))
            ),
            None,
        )
        climax_sentence = (
            self._first_matching_sentence(climax_chapter.content, ("终于", "危机", "爆发", "转折", "真相", "决定"))
            if climax_chapter
            else None
        )
        climax = (
            DeconstructionObservation(
                text=f"高潮候选：{self._clip(climax_sentence, 360)}",
                confidence=0.58,
                uncertainty=["这是基于正文词句的候选，不代表结构已确认。"],
                evidence_refs=[self._evidence(source, climax_chapter, document, climax_sentence, "高潮候选")],
            )
            if climax_chapter and climax_sentence
            else DeconstructionObservation(
                text="高潮观察：不确定，当前正文没有足够的转折或危机证据。",
                confidence=0.25,
                uncertainty=["需要更多章节或明确的高潮事件。"],
            )
        )

        character_candidates: list[DeconstructionCandidate] = []
        all_names = list(source.character_names)
        for chapter in source.chapters:
            for name in self._character_names_for_chapter(source, chapter):
                if name not in all_names:
                    all_names.append(name)
        for name in all_names[:12]:
            chapter = next(
                (item for item in source.chapters if name in item.content),
                first_chapter,
            )
            ref = self._evidence(source, chapter, document, name, "人物候选")
            character_candidates.append(
                DeconstructionCandidate(
                    label="主要人物候选",
                    value=name,
                    confidence=0.82 if name in source.character_names else 0.65,
                    uncertainty=[] if name in source.character_names else ["人物身份和重要性仍需正文确认。"],
                    evidence_refs=[ref],
                )
            )

        conflict_candidates: list[DeconstructionCandidate] = []
        for chapter in source.chapters:
            sentence = self._first_matching_sentence(
                chapter.content,
                ("核心冲突", "冲突", "对抗", "危险", "必须", "追赶"),
            )
            if sentence:
                ref = self._evidence(source, chapter, document, sentence, "核心冲突候选")
                conflict_candidates.append(
                    DeconstructionCandidate(
                        label="核心冲突候选",
                        value=self._clip(sentence, 300),
                        confidence=0.62,
                        uncertainty=["这是从正文观察出的候选，尚未由作者确认。"],
                        evidence_refs=[ref],
                    )
                )
            if len(conflict_candidates) >= 5:
                break

        overview_uncertainty: list[str] = []
        if len(source.chapters) < 3:
            overview_uncertainty.append("当前只有少量正式章节，长程节奏和结尾判断仍不稳定。")
        if not character_candidates:
            overview_uncertainty.append("未发现明确人物标记，人物候选暂为空。")
        if not conflict_candidates:
            overview_uncertainty.append("未发现明确核心冲突标记，冲突候选暂为空。")
        volume_titles = [
            chapter.title
            for chapter in source.chapters
            if re.search(r"卷|篇|部", chapter.title)
        ]
        structure_units = [
            f"章节结构（共 {len(source.chapters)} 章）",
            f"正文片段（共 {len(timeline)} 段）",
        ]
        if volume_titles:
            structure_units.insert(0, "已识别卷/篇标题：" + "、".join(volume_titles[:8]))

        overview = DeconstructionOverview(
            title=source.title,
            total_word_count=total_words,
            chapter_count=len(source.chapters),
            structure_units=structure_units,
            main_character_candidates=character_candidates,
            core_conflict_candidates=conflict_candidates,
            opening=DeconstructionObservation(
                text=f"开端观察：{self._clip(opening_sentence, 360)}",
                confidence=0.78,
                evidence_refs=[opening_ref],
            ),
            development=development,
            climax=climax,
            ending=DeconstructionObservation(
                text=f"结尾观察：{self._clip(ending_sentence, 360)}",
                confidence=0.72,
                evidence_refs=[ending_ref],
            ),
            uncertainty=overview_uncertainty,
        )
        document.overview = overview
        document.timeline = timeline
        document.chapter_breakdowns = chapter_breakdowns
        deduplicated: dict[str, EvidenceRef] = {item.evidence_id: item for item in evidence}
        document.evidence = list(deduplicated.values())
        document.uncertainty = overview_uncertainty

    @staticmethod
    def _clear_result(document: DeconstructionDocument) -> None:
        document.overview = None
        document.timeline = []
        document.chapter_breakdowns = []
        document.evidence = []
        document.uncertainty = []
        document.completed_at = None

    def _mark_not_current(self, project_id: str, account_id: str, document_id: str, source: _Source) -> DeconstructionDocument:
        with self._lock:
            record = self._record(project_id, account_id)
            document = self._document(record, document_id)
            if document is None:
                raise DeconstructionServiceError("deconstruction_missing", "作品拆解任务不存在。", status_code=404)
            if document.status == "completed" and source.sufficient and document.source_version_id == source.version_id and document.source_hash == source.source_hash:
                return document
            document.status = "rebuild_required" if source.pending_changes or not source.sufficient else "stale"
            document.current_stage = "等待根据当前正文更新"
            document.error_message = "正文来源已变化，当前拆解没有覆盖作者的新内容。"
            document.updated_at = self._now()
            assert record is not None
            record.updated_at = document.updated_at
            self.store.save(record)
            return document

    def _mark_failed(self, project_id: str, account_id: str, document_id: str, message: str) -> DeconstructionDocument:
        """把分析异常归类为可重试状态；错误消息不携带异常原文或正文。"""

        with self._lock:
            record = self._record(project_id, account_id)
            document = self._document(record, document_id)
            if document is None:
                raise DeconstructionServiceError("deconstruction_missing", "作品拆解任务不存在。", status_code=404)
            if document.status == "completed":
                return document
            document.status = "failed_retryable"
            document.progress_percent = 0
            document.current_stage = "拆解失败"
            document.error_message = message
            self._clear_result(document)
            document.updated_at = self._now()
            assert record is not None
            record.updated_at = document.updated_at
            self.store.save(record)
            return document

    def run_document(self, project_id: str, account_id: str, document_id: str) -> DeconstructionDocument:
        # 只在极短窗口内持拆解侧车锁；来源读取必须在锁外，避免反向拿独立/事务锁。
        with self._lock:
            record = self._record(project_id, account_id)
            document = self._document(record, document_id)
            if document is None:
                raise DeconstructionServiceError("deconstruction_missing", "作品拆解任务不存在。", status_code=404)
            if document.status == "completed":
                return document
            if document.status not in {"queued", "running"}:
                return document

        try:
            source = self._source(project_id, account_id)
        except (KeyboardInterrupt, SystemExit):
            raise
        except IndependentServiceError:
            return self._mark_failed(project_id, account_id, document_id, "拆解来源暂时不可用，正文没有被修改；可以重试。")
        except Exception:
            return self._mark_failed(project_id, account_id, document_id, "拆解来源读取失败，正文没有被修改；可以重试。")

        if (
            not source.sufficient
            or source.pending_changes
            or document.source_version_id != source.version_id
            or document.source_hash != source.source_hash
        ):
            return self._mark_not_current(project_id, account_id, document_id, source)

        with self._lock:
            record = self._record(project_id, account_id)
            document = self._document(record, document_id)
            if document is None:
                raise DeconstructionServiceError("deconstruction_missing", "作品拆解任务不存在。", status_code=404)
            if document.status == "completed":
                return document
            if document.status not in {"queued", "running"}:
                return document
            document.status = "running"
            document.progress_percent = 8
            document.current_stage = "读取正文结构"
            document.error_message = None
            document.updated_at = self._now()
            assert record is not None
            record.updated_at = document.updated_at
            self.store.save(record)
            working = document.model_copy(deep=True)

        try:
            working.current_stage = "提取章节与证据"
            working.progress_percent = 42
            self._build_document(source, working)
            working.current_stage = "整理节奏与章节拆解"
            working.progress_percent = 82

            # 分析期间作者可能产生新 revision；完成前再做一次来源门禁，且仍在拆解锁外。
            final_source = self._source(project_id, account_id)
            if (
                not final_source.sufficient
                or final_source.pending_changes
                or final_source.version_id != source.version_id
                or final_source.source_hash != source.source_hash
            ):
                return self._mark_not_current(project_id, account_id, document_id, final_source)

            with self._lock:
                record = self._record(project_id, account_id)
                latest = self._document(record, document_id)
                if latest is None:
                    raise DeconstructionServiceError("deconstruction_missing", "作品拆解任务不存在。", status_code=404)
                if latest.status == "completed":
                    return latest
                if latest.source_version_id != source.version_id or latest.source_hash != source.source_hash:
                    return self._mark_not_current(project_id, account_id, document_id, final_source)
                working.status = "completed"
                working.progress_percent = 100
                working.current_stage = "拆解完成"
                working.completed_at = self._now()
                working.updated_at = working.completed_at
                assert record is not None
                index = record.documents.index(latest)
                record.documents[index] = working
                record.updated_at = working.updated_at
                self.store.save(record)
                return working
        except (KeyboardInterrupt, SystemExit):
            raise
        except DeconstructionAnalysisError:
            return self._mark_failed(project_id, account_id, document_id, "确定性拆解没有完成，正文没有被修改；可以重试。")
        except (ValueError, TypeError, KeyError):
            return self._mark_failed(project_id, account_id, document_id, "拆解结果无法通过结构校验，正文没有被修改；可以重试。")
        except Exception:
            return self._mark_failed(project_id, account_id, document_id, "拆解过程发生可重试异常，正文没有被修改；可以重试。")

    def process_background_tasks(self, *, limit: int = 8) -> int:
        processed = self.reconcile_all_outboxes(limit=limit)
        for record in self.store.list_records():
            if processed >= limit:
                break
            for document in record.documents:
                if document.status not in {"queued", "running"}:
                    continue
                try:
                    self.run_document(record.project_id, record.account_id, document.document_id)
                except (KeyboardInterrupt, SystemExit):
                    raise
                except (DeconstructionServiceError, DeconstructionStoreError, OSError, ValueError, TypeError, KeyError):
                    # 单项恢复失败不能阻断同一轮其他作品；run_document 已尽力持久化安全失败状态。
                    pass
                except Exception:
                    # 进程级 worker 边界的最后保险；下一轮仍会扫描 queued/running。
                    pass
                processed += 1
                if processed >= limit:
                    break
        return processed

    async def process_background_tasks_async(self, *, limit: int = 8) -> int:
        return await asyncio.to_thread(self.process_background_tasks, limit=limit)

    def evidence(self, project_id: str, account_id: str, evidence_id: str) -> dict[str, object]:
        source = self._source(project_id, account_id)
        record = self._record(project_id, account_id)
        if record is None:
            raise DeconstructionServiceError("evidence_missing", "这条拆解证据不存在。", status_code=404)
        for document in record.documents:
            for item in document.evidence:
                if item.evidence_id != evidence_id:
                    continue
                source_matches_current = bool(
                    source.sufficient
                    and item.source_version_id == source.version_id
                    and item.source_hash == source.source_hash
                )
                chapter = next((chapter for chapter in source.chapters if chapter.chapter_id == item.chapter_id), None)
                if not source_matches_current or chapter is None:
                    # 历史稿本不再是当前正文时，返回最小历史定位；不把旧证据
                    # 默认跳到当前同编号章节，也不复制历史正文。
                    return {
                        "project_id": project_id,
                        "title": source.title,
                        "evidence": item.model_dump(mode="json"),
                        "chapter": {
                            "chapter_id": item.chapter_id,
                            "chapter_number": item.chapter_number,
                            "title": "历史稿本章节",
                            "read_only": True,
                            "source_available": False,
                        },
                        "source_matches_current": False,
                        "historical": True,
                    }
                return {
                    "project_id": project_id,
                    "title": source.title,
                    "evidence": item.model_dump(mode="json"),
                    "chapter": {
                        "chapter_id": chapter.chapter_id,
                        "chapter_number": chapter.chapter_number,
                        "title": chapter.title,
                        "read_only": True,
                        "source_available": True,
                    },
                    "source_matches_current": True,
                    "historical": False,
                }
        raise DeconstructionServiceError("evidence_missing", "这条拆解证据不存在。", status_code=404)
