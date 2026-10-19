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

from app.core.deconstruction_depth import ChapterInput, DepthAnalysisEngine, DepthSnapshot, RULE_ENGINE_REVISION
from app.core.deconstruction_store import (
    DeconstructionStore,
    DeconstructionStoreConflict,
    DeconstructionStoreError,
)
from app.core.independent_service import IndependentServiceError, IndependentWorkspaceService
from app.core.person_recognition import assess_person_identities
from app.core.project_lock import ProjectLockError
from app.core.character_aggregation import CharacterReportSlice, aggregate_character_slices
from schemas.analysis_report import AnalysisImport, AnalysisRequest, AnalysisReport
from schemas.deconstruction import (
    ChapterBreakdown,
    DeconstructionActions,
    DeconstructionActiveRun,
    DeconstructionCandidate,
    DeconstructionDocument,
    DeconstructionDepthReport,
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
    DeconstructionVolumeItem,
    EvidenceRef,
    TimelineNode,
    DepthEvidence,
    DepthSource,
    validate_depth_report_source,
)


ANALYSIS_LABEL = "确定性结构拆解（无模型）"
MAX_HISTORY = 20  # Public summary window only; never a storage retention cap.
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
        return bool(self.version_id and any(chapter.content.strip() for chapter in self.chapters))

    @property
    def analysis_chapters(self) -> tuple[_SourceChapter, ...]:
        return tuple(chapter for chapter in self.chapters if chapter.content.strip())


class DeconstructionService:
    """作品拆解的读取、排队、恢复和确定性分析。"""

    def __init__(
        self,
        *,
        independent: IndependentWorkspaceService,
        store: DeconstructionStore | None = None,
        model_budget_cny: float = 10.0,
        model_budget_scope: str = "default",
    ) -> None:
        self.independent = independent
        self.store = store or DeconstructionStore()
        self._lock = RLock()
        from app.core.model_call_budget import DurableModelBudget
        self.model_budget = DurableModelBudget(self.store.base_dir / "model-budgets",
                                              scope=model_budget_scope, budget_cny=model_budget_cny)

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

    @staticmethod
    def _normalize_timeline(timeline: list[TimelineNode]) -> list[TimelineNode]:
        """把有效正文跨度映射到 0–100，不改动任何绝对证据锚点。"""

        if not timeline:
            return []
        minimum = min(item.normalized_start for item in timeline)
        maximum = max(item.normalized_end for item in timeline)
        span = maximum - minimum
        if span <= 0:
            if len(timeline) == 1:
                return [timeline[0].model_copy(update={"normalized_start": 0.0, "normalized_end": 100.0})]
            span = float(len(timeline) - 1)
            minimum = 0.0
            raw_positions = [float(index) for index in range(len(timeline))]
        else:
            raw_positions = []

        normalized: list[TimelineNode] = []
        previous_end = 0.0
        for index, item in enumerate(timeline):
            if raw_positions:
                start = raw_positions[index]
                end = raw_positions[index] + 1.0
                start = (start / span) * 100.0
                end = (end / span) * 100.0
            else:
                start = ((item.normalized_start - minimum) / span) * 100.0
                end = ((item.normalized_end - minimum) / span) * 100.0
            start = round(max(0.0, min(100.0, start)), 2)
            end = round(max(0.0, min(100.0, end)), 2)
            if index == 0:
                start = 0.0
            start = max(previous_end, start)
            end = max(start, end)
            if index == len(timeline) - 1:
                end = 100.0
            normalized.append(item.model_copy(update={"normalized_start": start, "normalized_end": end}))
            previous_end = end
        return normalized

    # ---- 范围（卷）语义：拆解文档只对自已覆盖的连续章节负责 ----
    @staticmethod
    def _scoped(doc: DeconstructionDocument) -> bool:
        return doc.scope_start is not None and doc.scope_end is not None

    @staticmethod
    def _chapter_digest(chapter) -> str:
        payload = {
            "chapter_number": chapter.chapter_number,
            "title": chapter.title,
            "content": chapter.content,
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _scope_hash(self, source: _Source, start: int, end: int) -> str | None:
        """只统计 [start, end] 范围内章节的正文内容，不含整本哈希或编辑计数。"""
        by_number = {chapter.chapter_number: chapter for chapter in source.chapters}
        if any(number not in by_number for number in range(start, end + 1)):
            return None
        payload = {
            "scope": [start, end],
            "chapters": [
                {"chapter_number": number, "digest": self._chapter_digest(by_number[number])}
                for number in range(start, end + 1)
            ],
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _whole_matches(source: _Source, doc: DeconstructionDocument) -> bool:
        return bool(
            source.sufficient
            and doc.source_version_id == source.version_id
            and doc.source_revision == source.source_revision
            and doc.source_hash == source.source_hash
        )

    def _scope_matches(self, source: _Source, doc: DeconstructionDocument) -> bool:
        if not source.sufficient or not self._scoped(doc):
            return False
        return doc.source_version_id == source.version_id and self._scope_hash(source, doc.scope_start, doc.scope_end) == doc.scope_hash

    def _doc_matches(self, source: _Source, doc: DeconstructionDocument) -> bool:
        if doc is None:
            return False
        return self._scope_matches(source, doc) if self._scoped(doc) else self._whole_matches(source, doc)

    def _document_effective(self, source: _Source, doc: DeconstructionDocument | None) -> DeconstructionStatus | None:
        if doc is None:
            return None
        if not source.sufficient:
            return "empty"
        if source.pending_changes:
            return "rebuild_required"
        if not self._doc_matches(source, doc):
            return "stale"
        if self._engine_update_available(doc):
            return "rebuild_required"
        return doc.status

    @staticmethod
    def _engine_update_available(doc: DeconstructionDocument | None) -> bool:
        return bool(doc and doc.analysis_contract_version == "2.0" and doc.status == "completed"
                    and doc.engine_revision != RULE_ENGINE_REVISION)

    @staticmethod
    def _pick_focus_document(record: DeconstructionProjectRecord | None) -> DeconstructionDocument | None:
        if record is None:
            return None
        scoped = [doc for doc in record.documents if doc.scope_start is not None]
        if scoped:
            pool = [doc for doc in scoped if doc.status == "completed"] or scoped
            return max(pool, key=lambda doc: doc.updated_at)
        return DeconstructionService._document(record, record.active_document_id)

    def _volumes(self, source: _Source, record: DeconstructionProjectRecord | None) -> list[dict[str, object]]:
        if record is None:
            return []
        newest_by_scope: dict[tuple[int, int], DeconstructionDocument] = {}
        for doc in record.documents:
            if not self._scoped(doc):
                continue
            key = (doc.scope_start, doc.scope_end)
            previous = newest_by_scope.get(key)
            if previous is None or doc.updated_at > previous.updated_at:
                newest_by_scope[key] = doc
        items: list[dict[str, object]] = []
        for (start, end), doc in sorted(newest_by_scope.items(), key=lambda pair: pair[0]):
            status = self._document_effective(source, doc)
            items.append(DeconstructionVolumeItem(
                document_id=doc.document_id,
                scope_start=start,
                scope_end=end,
                scope_label=f"第 {start}–{end} 章",
                status=status or doc.status,
                run_status=doc.status if doc.status in {"queued", "running", "failed_retryable"} else "completed",
                match=self._doc_matches(source, doc),
                analysis_label=doc.analysis_label,
                chapter_count=end - start + 1,
                evidence_count=len(doc.evidence),
                latest=True,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
                completed_at=doc.completed_at,
            ).model_dump(mode="json"))
        return items

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

    def _source(self, project_id: str, account_id: str, *, version_id: str | None = None) -> _Source:
        record = self._load_independent_record(project_id, account_id)
        version = next(
            (item for item in record.versions if item.version_id == (version_id or record.active_version_id)),
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
            chapters.append(
                _SourceChapter(
                    chapter_id=chapter.chapter_id,
                    chapter_number=chapter.chapter_number,
                    title=chapter.formal_title or chapter.title,
                    content=content,
                    server_revision=chapter.server_revision,
                )
            )

        analysis_chapters = tuple(chapter for chapter in chapters if chapter.content.strip())
        source_payload = {
            "version_id": version.version_id,
            "chapters": [
                {
                    "chapter_id": chapter.chapter_id,
                    "chapter_number": chapter.chapter_number,
                    "title": chapter.title,
                    "content": chapter.content,
                }
                for chapter in analysis_chapters
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
            # Only completed formal chapters participate in the author source
            # revision. Empty drafting slots are represented in the current
            # chapter table but cannot invalidate a report for the last
            # completed source snapshot.
            source_revision=max((chapter.server_revision for chapter in analysis_chapters), default=0),
            source_hash=source_hash,
            chapters=tuple(chapters),
            pending_changes=record.pending_changes is not None if version.version_id == record.active_version_id else False,
            character_names=archive_names,
        )

    def _historical_source(self, project_id: str, account_id: str, version_id: str) -> _Source:
        """Read Ampere's immutable source seam, without chapter-number fallback."""
        reader = getattr(self.independent, "read_source_snapshot", None)
        if reader is None:
            # Existing installations retain version records; their formal text
            # is still a safe fallback until the snapshot helper is integrated.
            return self._source(project_id, account_id, version_id=version_id)
        try:
            snapshot = reader(project_id, account_id, version_id)
        except IndependentServiceError as exc:
            raise DeconstructionServiceError(exc.code, exc.message, status_code=exc.status_code) from None
        if snapshot["project_id"] != project_id or snapshot["source_version_id"] != version_id:
            raise DeconstructionServiceError("historical_source_invalid", "历史来源绑定不一致。", status_code=409)
        chapters = tuple(_SourceChapter(chapter_id=c["chapter_id"], chapter_number=c["chapter_number"],
                                        title=c["title"], content=c["content"], server_revision=c["server_revision"])
                         for c in sorted(snapshot["chapters"], key=lambda c: c["chapter_number"]))
        return _Source(project_id=project_id, account_id=account_id, title="历史稿本",
                       version_id=snapshot["source_version_id"], source_revision=snapshot["source_revision"],
                       source_hash=snapshot["source_hash"], chapters=chapters,
                       pending_changes=False, character_names=())

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
                "analysis_contract_version",
                "engine_revision",
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
        focus: DeconstructionDocument | None = None,
    ) -> dict[str, object]:
        active = focus if focus is not None else self._pick_focus_document(record)
        source_match = bool(active is not None and self._doc_matches(source, active))
        update_available = self._engine_update_available(active)
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
            empty_reason = empty_reason or "当前还没有可展示的作品拆解，请先生成或导入一卷拆解。"
        elif not source_match:
            status = "stale"
        elif (active.analysis_contract_version == "1.0" and active.status == "completed") or update_available:
            # A completed stage-31 overview is historical compatibility data,
            # not a stage-32 six-view result. Keep it active in history while
            # requiring an explicit 2.0 rebuild.
            status = "rebuild_required"
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
                (
                    f"第 {active.scope_start}–{active.scope_end} 章范围内的正文已变化，"
                    "请为该范围重新生成拆解；其它卷不受影响，不需要全本重跑。"
                    if self._scoped(active)
                    else "当前正式正文已变化，请生成一版新的作品拆解。"
                )
                if status == "stale"
                else "当前作者修改尚未确认，请先完成修改后再生成作品拆解。"
            )
            retryable = False
            error_code = "source_stale" if status == "stale" else "pending_changes"
            if status == "rebuild_required" and update_available and not source.pending_changes:
                current_stage = "有新版识别可用"
                error_message = "新版人物与阅读段落规则已可用；显式更新会生成新报告，并保留原报告和历史证据。"
                error_code = "engine_update_available"
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
        show_legacy_upgrade = bool(status == "rebuild_required" and update_available and source_match
                                   and not source.pending_changes and active and self._whole_matches(source, active))
        result_model = self._result(active, source_match, effective_status="completed" if show_legacy_upgrade else status)
        if show_legacy_upgrade and result_model is not None:
            result_model.read_only = True
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
                analysis_contract_version=active.analysis_contract_version,
                engine_revision=active.engine_revision,
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
            update_available=update_available,
            engine_revision=active.engine_revision if active else None,
            required_engine_revision=RULE_ENGINE_REVISION if active is None or active.analysis_contract_version != "model.1" else None,
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
            "update_available": canonical.update_available,
            "engine_revision": canonical.engine_revision,
            "required_engine_revision": canonical.required_engine_revision,
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
            "analysis_label": active.analysis_label if active else ANALYSIS_LABEL,
            "empty_reason": empty_reason,
            "error_message": error_message,
            "retryable": retryable,
            "document": public_active,
            "focus_document_id": active.document_id if active is not None else None,
            "volumes": self._volumes(source, record),
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

    def read(self, project_id: str, account_id: str, document_id: str | None = None) -> dict[str, object]:
        self.reconcile_outbox(project_id, account_id)
        source = self._source(project_id, account_id)
        record = self._record(project_id, account_id)
        focus = None
        if document_id is not None:
            focus = self._document(record, document_id)
            if focus is None:
                raise DeconstructionServiceError("document_missing", "这份卷拆解不存在或已被移除。", status_code=404)
        if source.sufficient and not source.pending_changes and record is None:
            self.enqueue_for_project(project_id, account_id, reason="首次读取补建")
            record = self._record(project_id, account_id)
        return self._response(source, record, focus=focus)

    def guide(self, project_id: str, account_id: str) -> dict[str, object]:
        """Return the source-bound cross-volume character index.

        Volume reports remain the authoritative, independently checkable
        documents. This projection only groups their character snapshots; it
        never replaces a volume card with a later card and never invents a
        cross-volume literary conclusion.
        """

        source = self._source(project_id, account_id)
        record = self._record(project_id, account_id)
        slices: list[CharacterReportSlice] = []
        if record is not None:
            newest_by_scope: dict[tuple[int, int], DeconstructionDocument] = {}
            for document in record.documents:
                if (
                    not self._scoped(document)
                    or document.status != "completed"
                    or not self._doc_matches(source, document)
                    or not isinstance(document.report, AnalysisReport)
                ):
                    continue
                key = (document.scope_start, document.scope_end)
                previous = newest_by_scope.get(key)
                if previous is None or document.updated_at > previous.updated_at:
                    newest_by_scope[key] = document
            for document in newest_by_scope.values():
                slices.append(CharacterReportSlice(
                    source_key=document.document_id,
                    scope_start=document.scope_start,
                    scope_end=document.scope_end,
                    report=document.report,
                ))
        characters = aggregate_character_slices(slices)
        return {
            "schema_version": "1.0",
            "project_id": project_id,
            "source_version_id": source.version_id,
            "source_hash": source.source_hash,
            "complete": bool(slices) and set(n for item in slices for n in range(item.scope_start, item.scope_end + 1)) == {c.chapter_number for c in source.chapters},
            "volumes": self._volumes(source, record),
            "characters": [item.model_dump(mode="json") for item in characters],
        }
    def report_material(self, project_id: str, account_id: str, payload):
        """Full current source only; run before creating or scheduling a paid job."""
        from app.core.analysis_grounding import source_bank
        from app.core.report_pipeline import REPORT_LIMIT
        source = self._source(project_id, account_id)
        self._check_source_precondition(source, **payload.model_dump())
        if not source.sufficient or source.pending_changes:
            raise DeconstructionServiceError("source_not_ready", "请先确认并保存正文。", status_code=409)
        if sum(len(c.content) for c in source.chapters) > REPORT_LIMIT:
            raise DeconstructionServiceError("report_scope_large", "本轮完整正文超过三万字符，尚不支持此入口；正文没有被截断。", status_code=422)
        numbers = sorted(c.chapter_number for c in source.chapters)
        if not numbers or numbers != list(range(numbers[0], numbers[-1] + 1)):
            raise DeconstructionServiceError("report_scope_invalid", "当前正文的正式章节范围不完整。", status_code=422)
        material = [dict(chapter_number=c.chapter_number, title=c.title, content=c.content) for c in source.chapters]
        read_text = {c.chapter_number: c.content for c in source.chapters}
        return source, material, source_bank(read_text), read_text

    async def analyze_preview(self, project_id: str, account_id: str, payload: AnalysisRequest, runtime) -> AnalysisImport:
        """Read a bounded source snapshot; model failure never replaces the current result."""
        from app.agents.deconstruction_model import chapter_fact_messages, chapter_checked_messages, preview_max_tokens
        from app.agents.llm_runtime import LLMRuntimeError
        from app.core.analysis_grounding import source_bank
        from app.core.chapter_preview import (
            ChapterFacts, ChapterOutcome, ChapterBlocked, CHAPTER_MAX_TOKENS,
            freeze_chapter, chapter_index, bind_chapter_outcome,
        )
        from app.core.model_call_budget import budgeted_structured
        from app.core.model_budget import ModelBudgetExceeded
        source = self._source(project_id, account_id)
        bindings = payload.model_dump(exclude={"chapter_numbers"})
        self._check_source_precondition(source, **bindings)
        if not source.sufficient or source.pending_changes:
            raise DeconstructionServiceError("source_not_ready", "请先确认并保存正文。", status_code=409)
        if not getattr(runtime, "available", True):
            raise DeconstructionServiceError("model_unavailable", "请先配置作品拆解模型。", status_code=503)
        requested = set(payload.chapter_numbers)
        chapters = [c for c in source.chapters if c.chapter_number in requested]
        if len(requested) != len(payload.chapter_numbers) or len(chapters) != len(requested):
            raise DeconstructionServiceError("report_scope_invalid", "请选择当前稿本中不重复的章节。", status_code=422)
        if sorted(requested) != list(range(min(requested), max(requested) + 1)):
            raise DeconstructionServiceError("report_scope_invalid", "请选择连续章节。", status_code=422)
        if sum(len(c.content) for c in chapters) > 30000:
            raise DeconstructionServiceError("report_scope_large", "本轮请缩小章节范围至约三万字以内。", status_code=422)
        read_text = {c.chapter_number: c.content for c in chapters}
        bank = source_bank(read_text)
        def check_source():
            current = self._source(project_id, account_id)
            self._check_source_precondition(current, **bindings)
            if current.pending_changes:
                raise DeconstructionServiceError("source_not_ready", "请先确认并保存正文。", status_code=409)
        material = [dict(chapter_number=c.chapter_number, title=c.title, content=c.content) for c in chapters]
        call_id = f"deconstruction:{project_id}:{source.source_hash}"
        try:
            frozen = ()
            for chapter in material:
                number = chapter["chapter_number"]
                chapter_bank = {key: passage for key, passage in bank.items() if passage.chapter_number == number}
                first = await budgeted_structured(runtime, self.model_budget, check_source=check_source,
                    call_id=call_id + f":chapter-{number}:facts", messages=chapter_fact_messages(chapter, chapter_bank),
                    response_model=ChapterFacts, max_tokens=CHAPTER_MAX_TOKENS, temperature=0.3)
                check_source()
                try:
                    packet = freeze_chapter(first.data, chapter_bank, {number: read_text[number]})
                    frozen = (*frozen, packet)
                    chapter_index(frozen)
                except ValueError:
                    raise DeconstructionServiceError("report_facts_invalid", "模型章级事实、身份或来源未通过校验，现有结果已保留。", status_code=422) from None
            check_source()
            result = await budgeted_structured(runtime, self.model_budget, check_source=check_source,
                call_id=call_id + ":checked", messages=chapter_checked_messages(material, bank, frozen),
                response_model=ChapterOutcome, max_tokens=preview_max_tokens(runtime), temperature=0.3)
        except ModelBudgetExceeded:
            raise DeconstructionServiceError("model_budget_exceeded", "已达到本轮模型总预算上限，现有结果已保留。", status_code=409,
                                            data={"budget": self.model_budget.public(runtime.model)}) from None
        except TimeoutError:
            raise DeconstructionServiceError("model_timeout", "本轮拆解等待超时，请缩小范围后重试；现有结果已保留。", status_code=504) from None
        except LLMRuntimeError as exc:
            raise DeconstructionServiceError(exc.code, "模型拆解未完成，请稍后重试；现有结果已保留。", status_code=exc.status_code) from None
        except (OSError, ValueError):
            raise DeconstructionServiceError("model_budget_unavailable", "模型预算账暂不可用，未采用本次结果。", status_code=503) from None
        try:
            check_source()
            report = bind_chapter_outcome(result.data, frozen, bank, read_text, producer=runtime.model)
        except ValueError:
            raise DeconstructionServiceError("report_evidence_invalid", "模型来源编号、引用或结构未通过校验，现有结果已保留。", status_code=422) from None
        if isinstance(report, ChapterBlocked):
            check_source()
            raise DeconstructionServiceError("report_source_blocked", "冻结章包存在有源问题，本轮未生成可采用报告；现有结果已保留。", status_code=422,
                                            data={"issues": [issue.model_dump(mode="json") for issue in report.issues]})
        if set(report.chapter_numbers) != requested:
            raise DeconstructionServiceError("report_scope_invalid", "模型返回的章节范围不一致，现有结果已保留。", status_code=422)
        check_source()
        return AnalysisImport(**bindings, report=report)

    def import_report(self, project_id: str, account_id: str, payload: AnalysisImport) -> dict[str, object]:
        """Bind model-authored claims to exact current text. Never modify the author's manuscript."""
        try:
            with self.independent._author_write_guard(project_id, account_id), self._lock:
                source = self._source(project_id, account_id)
                self._check_source_precondition(source, **payload.model_dump(exclude={"report"}))
                if not source.sufficient or source.pending_changes:
                    raise DeconstructionServiceError("source_not_ready", "请先确认并保存正文。", status_code=409)
                report = payload.report
                chapters = {x.chapter_number: x for x in source.chapters}
                if not set(report.chapter_numbers) <= set(chapters):
                    raise DeconstructionServiceError("report_scope_invalid", "拆解范围包含当前稿本不存在的章节。", status_code=422)
                ordered = sorted(set(report.chapter_numbers))
                if ordered != list(range(ordered[0], ordered[-1] + 1)):
                    raise DeconstructionServiceError("report_scope_invalid", "每份拆解报告必须覆盖一段连续章节（一个卷）。", status_code=422)
                scope_start, scope_end = ordered[0], ordered[-1]
                scope_hash = self._scope_hash(source, scope_start, scope_end)
                if scope_hash is None:
                    raise DeconstructionServiceError("report_scope_invalid", "拆解范围的章节在当前稿本中不完整。", status_code=422)
                digest = hashlib.sha256(report.model_dump_json().encode("utf-8")).hexdigest()
                record = self._record(project_id, account_id) or DeconstructionProjectRecord(project_id=project_id, account_id=account_id)
                # Equal text in a new manuscript version has different chapter/evidence bindings.
                document_id = self._slug(f"analysis-scope:{project_id}:{source.version_id}:{scope_start}-{scope_end}:{scope_hash}:{digest}")
                legacy_id = self._slug(f"analysis-scope:{project_id}:{scope_start}-{scope_end}:{scope_hash}:{digest}")
                legacy = self._document(record, legacy_id)
                # Keep already-persisted IDs stable for exact same-version retries only.
                # Never migrate an old document or replace its frozen evidence bindings.
                if (legacy is not None and legacy.analysis_contract_version == "model.1"
                        and legacy.status == "completed"
                        and legacy.project_id == project_id and legacy.account_id == account_id
                        and legacy.source_version_id == source.version_id
                        and legacy.scope_start == scope_start and legacy.scope_end == scope_end
                        and legacy.scope_hash == scope_hash and legacy.report == report):
                    document_id = legacy_id
                evidence = []
                for item in report.evidence:
                    chapter = chapters[item.chapter_number]
                    start = chapter.content.find(item.quote)
                    if start < 0 or chapter.content.find(item.quote, start + 1) >= 0:
                        raise DeconstructionServiceError("report_evidence_invalid", f"证据 {item.id} 未在指定章节唯一匹配，请修正引文。", status_code=422)
                    evidence.append(EvidenceRef(
                        evidence_id=item.id, document_id=document_id,
                        source_version_id=source.version_id, source_revision=source.source_revision,
                        source_hash=source.source_hash, chapter_id=chapter.chapter_id,
                        chapter_number=chapter.chapter_number,
                        start_offset=len(chapter.content[:start].encode("utf-16-le")) // 2,
                        end_offset=len(chapter.content[:start + len(item.quote)].encode("utf-16-le")) // 2,
                        excerpt=item.quote, label="拆解依据",
                    ))
                if self._document(record, document_id) is None:
                    now = self._now()
                    record.documents.append(DeconstructionDocument(
                        document_id=document_id, project_id=project_id, account_id=account_id,
                        source_version_id=source.version_id, source_revision=source.source_revision,
                        source_hash=source.source_hash, status="completed", progress_percent=100,
                        analysis_contract_version="model.1",
                        current_stage="拆解结果已导入", idempotency_key=digest,
                        analysis_label=f"{report.producer} · 导入分析",
                        overview=DeconstructionOverview(title=report.title, chapter_count=len(report.chapter_numbers),
                            total_word_count=sum(self._word_count(chapters[n].content) for n in report.chapter_numbers)),
                        report=report, evidence=evidence, completed_at=now,
                        scope_start=scope_start, scope_end=scope_end, scope_hash=scope_hash,
                    ))
                record.active_document_id = document_id
                record.updated_at = self._now()
                # Keep the active result even when re-importing an older identical package.
                active = self._document(record, document_id)
                record.documents = [x for x in record.documents if x.document_id != document_id] + [active]
                self.store.save(record)
                return self._response(source, record, focus=active)
        except IndependentServiceError as exc:
            raise DeconstructionServiceError(exc.code, exc.message, status_code=exc.status_code) from None
        except DeconstructionStoreError:
            raise DeconstructionServiceError("deconstruction_store_unavailable", "拆解结果暂时无法保存，请重试。", status_code=503) from None

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
        with self.store.project_locks.project_lock(project_id):
            # Re-read the source after entering the shared gate so a source
            # update racing the initial snapshot cannot create a document for
            # an already obsolete token.
            locked_source = self._source(project_id, account_id)
            self._check_source_precondition(
                locked_source,
                expected_source_version_id=expected_source_version_id,
                expected_source_revision=expected_source_revision,
                expected_source_hash=expected_source_hash,
            )
            if not locked_source.sufficient or locked_source.pending_changes:
                raise DeconstructionServiceError(
                    "deconstruction_rebuild_required",
                    "当前正式正文尚未形成可分析的稳定来源，请稍后重试。",
                    status_code=409,
                )
            source = locked_source
            with self._lock:
                record = self._record(project_id, account_id)
                if record is None:
                    record = DeconstructionProjectRecord(project_id=project_id, account_id=account_id)
                existing = next(
                    (
                        item
                        for item in record.documents
                        if item.analysis_contract_version == "2.0"
                        and item.engine_revision == RULE_ENGINE_REVISION
                        and item.source_version_id == source.version_id
                        and item.source_revision == source.source_revision
                        and item.source_hash == source.source_hash
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
                        self.store.save_if_revision(record, record.record_revision)
                    elif record.active_document_id != existing.document_id:
                        record.active_document_id = existing.document_id
                        record.updated_at = self._now()
                        self.store.save_if_revision(record, record.record_revision)
                    return existing

                now = self._now()
                document_id = self._slug(
                    f"deconstruction:2.0:{RULE_ENGINE_REVISION}:{project_id}:{source.version_id}:"
                    f"{source.source_revision}:{source.source_hash}"
                )
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
                    analysis_contract_version="2.0",
                    engine_revision=RULE_ENGINE_REVISION,
                    created_at=now,
                    updated_at=now,
                )
                record.documents.append(document)
                record.active_document_id = document.document_id
                record.updated_at = now
                self.store.save_if_revision(record, record.record_revision)
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
        try:
            # Retry uses exactly the same project -> instance lock order as
            # enqueue and publish. Source and record are re-read while the
            # persistent gate is held; no stale retry can overwrite a newer
            # worker or author mutation.
            with self.store.project_locks.project_lock(project_id):
                source = self._source(project_id, account_id)
                self._check_source_precondition(
                    source,
                    expected_source_version_id=expected_source_version_id,
                    expected_source_revision=expected_source_revision,
                    expected_source_hash=expected_source_hash,
                )
                with self._lock:
                    record = self._record(project_id, account_id)
                    document = self._document(
                        record,
                        document_id or (record.active_document_id if record else None),
                    )
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
                if document.analysis_contract_version != "2.0":
                    return self.enqueue_for_project(
                        project_id,
                        account_id,
                        reason="阶段32深度重建",
                        idempotency_key=idempotency_key,
                        expected_source_version_id=expected_source_version_id,
                        expected_source_revision=expected_source_revision,
                        expected_source_hash=expected_source_hash,
                    )
                if document.status not in {"failed_retryable", "stale", "rebuild_required"}:
                    if document.status in {"queued", "running", "completed"}:
                        return document
                    raise DeconstructionServiceError(
                        "deconstruction_not_retryable",
                        "当前拆解没有可执行的重试。",
                        status_code=409,
                    )
                if not source.sufficient or source.pending_changes:
                    raise DeconstructionServiceError(
                        "deconstruction_rebuild_required",
                        "请先完成并确认当前正文修改，再重试作品拆解。",
                        status_code=409,
                    )
                if (
                    document.source_version_id != source.version_id
                    or document.source_revision != source.source_revision
                    or document.source_hash != source.source_hash
                ):
                    return self.enqueue_for_project(
                        project_id,
                        account_id,
                        reason="基于新稿本重建",
                        idempotency_key=idempotency_key,
                    )
                with self._lock:
                    assert record is not None and document is not None
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
                    self.store.save_if_revision(record, record.record_revision)
                    return document
        except ProjectLockError as exc:
            raise DeconstructionServiceError(
                "deconstruction_lock_unavailable",
                "作品拆解暂时被另一项操作占用，请稍后重试。",
                status_code=503,
                data={"retryable": True},
            ) from exc

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
        excerpt = content[position:end]
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
        return [p.name for p in assess_person_identities(source.analysis_chapters, source.character_names)
                if p.importance != "incidental" and any(m.chapter_id == chapter.chapter_id for m in p.mentions)]

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
        chapters = source.analysis_chapters
        if any("[[deconstruction-fail]]" in chapter.content for chapter in chapters):
            raise DeconstructionAnalysisError("demo_failure")
        if not chapters or not source.version_id:
            raise DeconstructionAnalysisError("empty_source")

        evidence: list[EvidenceRef] = []
        chapter_breakdowns: list[ChapterBreakdown] = []
        timeline: list[TimelineNode] = []
        total_chars = sum(len(chapter.content) for chapter in chapters)
        total_words = sum(self._word_count(chapter.content) for chapter in chapters)
        global_offset = 0

        for index, chapter in enumerate(chapters):
            text = chapter.content
            sentences = self._sentences(text)
            paragraphs = self._paragraphs(text) or [text]
            function = self._chapter_function(index, len(chapters), text)
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
            if len(chapters) < 3:
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
            chapter_names = self._character_names_for_chapter(source, chapter)
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
                if index == len(chapters) - 1 and scene_index == len(paragraphs[:8]) - 1:
                    end_percent = 100.0
                word_start = sum(self._word_count(item.content) for item in chapters[:index]) + self._word_count(text[:local_offset])
                word_end = sum(self._word_count(item.content) for item in chapters[:index]) + self._word_count(text[:local_end])
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
                        characters=chapter_names[:30],
                        recognized_character_count=len(chapter_names),
                        confidence=0.72 if event else 0.4,
                        uncertainty=(["时间线摘要最多展示30位候选，完整候选见人物视角。"] if len(chapter_names) > 30 else [])
                        + ([] if event else ["正文片段不足以判断事件。"]),
                        evidence_refs=[ref],
                    )
                )
            global_offset += len(text)

        first_chapter = chapters[0]
        last_chapter = chapters[-1]
        opening_sentence = self._sentences(first_chapter.content)[0] if self._sentences(first_chapter.content) else first_chapter.content
        ending_sentence = self._sentences(last_chapter.content)[-1] if self._sentences(last_chapter.content) else last_chapter.content
        opening_ref = self._evidence(source, first_chapter, document, opening_sentence, "开端观察")
        ending_ref = self._evidence(source, last_chapter, document, ending_sentence, "结尾观察")
        evidence.extend([opening_ref, ending_ref])

        development_chapter = chapters[min(1, len(chapters) - 1)]
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
                for chapter in reversed(chapters)
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
        all_names = [p.name for p in assess_person_identities(chapters, source.character_names) if p.importance != "incidental"]
        for name in all_names:
            chapter = next(
                (item for item in chapters if name in item.content),
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
        for chapter in chapters:
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
        if len(chapters) < 3:
            overview_uncertainty.append("当前只有少量正式章节，长程节奏和结尾判断仍不稳定。")
        if not character_candidates:
            overview_uncertainty.append("未发现明确人物标记，人物候选暂为空。")
        if len(character_candidates) > 30:
            overview_uncertainty.append("总览摘要最多展示30位候选，完整候选见人物视角。")
        if not conflict_candidates:
            overview_uncertainty.append("未发现明确核心冲突标记，冲突候选暂为空。")
        volume_titles = [
            chapter.title
            for chapter in chapters
            if re.search(r"卷|篇|部", chapter.title)
        ]
        structure_units = [
            f"章节结构（共 {len(chapters)} 章）",
            f"正文片段（共 {len(timeline)} 段）",
        ]
        if volume_titles:
            structure_units.insert(0, "已识别卷/篇标题：" + "、".join(volume_titles[:8]))

        overview = DeconstructionOverview(
            title=source.title,
            total_word_count=total_words,
            chapter_count=len(chapters),
            structure_units=structure_units,
            main_character_candidates=character_candidates[:30],
            recognized_character_count=len(all_names),
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
        document.timeline = self._normalize_timeline(timeline)
        document.chapter_breakdowns = chapter_breakdowns
        deduplicated: dict[str, EvidenceRef] = {item.evidence_id: item for item in evidence}
        if document.analysis_contract_version == "2.0":
            document.engine_revision = RULE_ENGINE_REVISION
            assert source.version_id is not None and source.source_hash is not None
            snapshot = DepthSnapshot(
                project_id=source.project_id,
                document_id=document.document_id,
                source_version_id=source.version_id,
                source_revision=source.source_revision or 0,
                source_hash=source.source_hash,
                chapters=tuple(
                    ChapterInput(
                        chapter_id=chapter.chapter_id,
                        chapter_number=chapter.chapter_number,
                        title=chapter.title,
                        content=chapter.content,
                    )
                    for chapter in source.chapters
                ),
                character_names=source.character_names,
            )
            report = DepthAnalysisEngine(snapshot).build()
            validate_depth_report_source(
                report,
                source=DepthSource(
                    project_id=source.project_id,
                    document_id=document.document_id,
                    source_version_id=source.version_id,
                    source_revision=source.source_revision or 0,
                    source_hash=source.source_hash,
                ),
                chapters={chapter.chapter_id: chapter.content for chapter in source.chapters},
            )
            document.report = report
            for item in report.evidence:
                # Stage 31's evidence endpoint accepts the legacy bounded
                # projection. The depth report itself remains the canonical
                # six-view object and retains exact UTF-16 offsets.
                if item.granularity != "span":
                    continue
                assert item.start_offset is not None and item.end_offset is not None
                target_path = (
                    f"/independent/{source.project_id}?version_id={source.version_id}"
                    f"&chapter_id={item.chapter_id}&evidence_id={item.evidence_id}"
                    f"&document_id={document.document_id}"
                )
                deduplicated[item.evidence_id] = EvidenceRef(
                    evidence_id=item.evidence_id,
                    document_id=document.document_id,
                    source_version_id=item.source_version_id,
                    source_revision=item.source_revision,
                    source_hash=item.source_hash,
                    chapter_id=item.chapter_id,
                    chapter_number=item.chapter_number,
                    start_offset=item.start_offset,
                    end_offset=item.end_offset,
                    offset_unit=item.offset_unit,
                    excerpt=item.excerpt,
                    label=item.label,
                    target_path=target_path,
                )
        document.evidence = list(deduplicated.values())
        document.uncertainty = overview_uncertainty

    @staticmethod
    def _clear_result(document: DeconstructionDocument) -> None:
        document.report = None
        document.overview = None
        document.timeline = []
        document.chapter_breakdowns = []
        document.evidence = []
        document.uncertainty = []
        document.completed_at = None

    def _mark_not_current(self, project_id: str, account_id: str, document_id: str, source: _Source) -> DeconstructionDocument:
        try:
            with self.store.project_locks.project_lock(project_id):
                with self._lock:
                    record = self._record(project_id, account_id)
                    document = self._document(record, document_id)
                    if document is None:
                        raise DeconstructionServiceError("deconstruction_missing", "作品拆解任务不存在。", status_code=404)
                    if (
                        document.status == "completed"
                        and document.analysis_contract_version == "2.0"
                        and source.sufficient
                        and document.source_version_id == source.version_id
                        and document.source_revision == source.source_revision
                        and document.source_hash == source.source_hash
                    ):
                        return document
                    assert record is not None
                    return self._mark_not_current_locked(record, document, source)
        except ProjectLockError as exc:
            raise DeconstructionServiceError(
                "deconstruction_lock_unavailable",
                "作品拆解暂时被另一项操作占用，请稍后重试。",
                status_code=503,
                data={"retryable": True},
            ) from exc

    def _mark_failed(self, project_id: str, account_id: str, document_id: str, message: str) -> DeconstructionDocument:
        """把分析异常归类为可重试状态；错误消息不携带异常原文或正文。"""

        try:
            with self.store.project_locks.project_lock(project_id):
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
                    self.store.save_if_revision(record, record.record_revision)
                    return document
        except ProjectLockError as exc:
            raise DeconstructionServiceError(
                "deconstruction_lock_unavailable",
                "作品拆解暂时被另一项操作占用，请稍后重试。",
                status_code=503,
                data={"retryable": True},
            ) from exc

    @staticmethod
    def _document_matches_source(document: DeconstructionDocument, source: _Source) -> bool:
        return bool(
            source.sufficient
            and not source.pending_changes
            and document.source_version_id == source.version_id
            and document.source_revision == source.source_revision
            and document.source_hash == source.source_hash
        )

    def _mark_not_current_locked(
        self,
        record: DeconstructionProjectRecord,
        document: DeconstructionDocument,
        source: _Source,
    ) -> DeconstructionDocument:
        """Mutate one loaded record while project lock is already held."""

        document.status = "rebuild_required" if source.pending_changes or not source.sufficient else "stale"
        document.current_stage = "等待根据当前正文更新"
        document.error_message = "正文来源已变化，当前拆解没有覆盖作者的新内容。"
        self._clear_result(document)
        document.updated_at = self._now()
        record.updated_at = document.updated_at
        self.store.save_if_revision(record, record.record_revision)
        return document

    def run_document(self, project_id: str, account_id: str, document_id: str) -> DeconstructionDocument:
        # First inspect the sidecar without holding the deconstruction mutex.
        # The canonical source snapshot is then captured outside both locks.
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

        if not self._document_matches_source(document, source):
            return self._mark_not_current(project_id, account_id, document_id, source)

        run_record_revision: int | None = None
        try:
            # The common persistent lock is always outermost. Source reload is
            # outside the instance mutex so this path cannot hold a
            # deconstruction lock while waiting for an author/transaction lock.
            with self.store.project_locks.project_lock(project_id):
                locked_source = self._source(project_id, account_id)
                if not self._document_matches_source(document, locked_source):
                    return self._mark_not_current(project_id, account_id, document_id, locked_source)
                with self._lock:
                    record = self._record(project_id, account_id)
                    document = self._document(record, document_id)
                    if document is None:
                        raise DeconstructionServiceError("deconstruction_missing", "作品拆解任务不存在。", status_code=404)
                    if document.status == "completed":
                        return document
                    if document.status not in {"queued", "running"}:
                        return document
                    if not self._document_matches_source(document, locked_source):
                        assert record is not None
                        return self._mark_not_current_locked(record, document, locked_source)
                    document.status = "running"
                    document.progress_percent = 8
                    document.current_stage = "读取正文结构"
                    document.error_message = None
                    document.updated_at = self._now()
                    assert record is not None
                    record.updated_at = document.updated_at
                    self.store.save_if_revision(record, record.record_revision)
                    run_record_revision = record.record_revision
                    working = document.model_copy(deep=True)
        except ProjectLockError as exc:
            raise DeconstructionServiceError(
                "deconstruction_lock_unavailable",
                "作品拆解暂时被另一项操作占用，请稍后重试。",
                status_code=503,
                data={"retryable": True},
            ) from exc

        try:
            working.current_stage = "提取章节与证据"
            working.progress_percent = 42
            self._build_document(source, working)
            working.current_stage = "整理节奏与章节拆解"
            working.progress_percent = 82

            # Phase C: hold the same persistent project gate used by author
            # writes, reload the canonical source and record, then CAS publish.
            # No author revision can land between this source read and save.
            with self.store.project_locks.project_lock(project_id):
                final_source = self._source(project_id, account_id)
                record = self._record(project_id, account_id)
                with self._lock:
                    latest = self._document(record, document_id)
                    if latest is None:
                        raise DeconstructionServiceError("deconstruction_missing", "作品拆解任务不存在。", status_code=404)
                    if latest.status == "completed":
                        return latest
                    if not self._document_matches_source(latest, source) or not self._document_matches_source(latest, final_source):
                        assert record is not None
                        return self._mark_not_current_locked(record, latest, final_source)
                    if run_record_revision is None or record is None or record.record_revision != run_record_revision:
                        # Another durable sidecar mutation won the CAS window.
                        # Never overwrite the newer record with this worker's
                        # stale in-memory copy.
                        return latest
                    working.status = "completed"
                    working.progress_percent = 100
                    working.current_stage = "拆解完成"
                    working.completed_at = self._now()
                    working.updated_at = working.completed_at
                    index = record.documents.index(latest)
                    record.documents[index] = working
                    record.updated_at = working.updated_at
                    self.store.save_if_revision(record, record.record_revision)
                    return working
        except (KeyboardInterrupt, SystemExit):
            raise
        except DeconstructionStoreConflict:
            latest_record = self._record(project_id, account_id)
            latest = self._document(latest_record, document_id)
            if latest is not None:
                return latest
            raise DeconstructionServiceError(
                "deconstruction_conflict",
                "作品拆解已被另一项操作更新，请刷新后重试。",
                status_code=409,
            ) from None
        except (ProjectLockError, DeconstructionStoreError) as exc:
            raise DeconstructionServiceError(
                "deconstruction_lock_unavailable" if isinstance(exc, ProjectLockError) else "deconstruction_store_unavailable",
                "作品拆解暂时不可写入，请稍后重试。",
                status_code=503,
                data={"retryable": True},
            ) from exc
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

    def _evidence_source_matches(self, source: _Source, document: DeconstructionDocument) -> bool:
        """Validate the original version, using exactly the report's scope.

        A scoped model report survives appending outside its read range, even
        when that version subsequently becomes historical. Whole-book reports
        still require the complete source hash; a missing scope hash is never
        treated as permission to bypass source verification.
        """
        if (source.project_id != document.project_id or source.account_id != document.account_id
                or source.version_id != document.source_version_id):
            return False
        if document.analysis_contract_version == "model.1" and self._scoped(document):
            return bool(document.scope_hash and document.scope_start <= document.scope_end
                        and self._scope_hash(source, document.scope_start, document.scope_end) == document.scope_hash)
        return bool(source.source_hash and source.source_hash == document.source_hash)

    def _verified_evidence(self, source: _Source, document: DeconstructionDocument,
                           item: EvidenceRef) -> EvidenceRef | None:
        """Exact source-bound projection; legacy whitespace repair is read-only.

        Never search by current chapter number or fuzzy-match a quote. Recovery
        is limited to the old strip-only bug at the *same* stored UTF-16 span,
        backed by a validated canonical report or the legacy producer's exact
        ID/position/length formula. The returned quote must equal the raw slice.
        """
        if (not self._evidence_source_matches(source, document)
                or item.document_id != document.document_id
                or item.source_version_id != document.source_version_id
                or item.source_revision != document.source_revision
                or item.source_hash != document.source_hash):
            return None
        if (document.analysis_contract_version == "model.1" and self._scoped(document)
                and not document.scope_start <= item.chapter_number <= document.scope_end):
            return None
        chapter = next((c for c in source.chapters if c.chapter_id == item.chapter_id
                        and c.chapter_number == item.chapter_number), None)
        if chapter is None:
            return None
        try:
            raw = chapter.content.encode("utf-16-le")
            if not 0 <= item.start_offset < item.end_offset <= len(raw) // 2:
                return None
            prefix = raw[:item.start_offset * 2].decode("utf-16-le")
            quote = raw[item.start_offset * 2:item.end_offset * 2].decode("utf-16-le")
        except UnicodeError:
            return None
        canonical = None
        if isinstance(document.report, DeconstructionDepthReport):
            canonical = next((e for e in document.report.evidence if e.evidence_id == item.evidence_id), None)
        if canonical is not None:
            if (canonical.granularity != "span" or canonical.excerpt != quote or any(
                getattr(canonical, key) != getattr(item, key) for key in
                ("document_id", "source_version_id", "source_revision", "source_hash", "chapter_id",
                 "chapter_number", "start_offset", "end_offset", "offset_unit")
            )):
                return None
        if quote == item.excerpt:
            return item
        if not item.excerpt or item.excerpt != quote.strip() or document.analysis_contract_version == "model.1":
            return None
        if canonical is not None:
            if canonical.granularity != "span" or canonical.excerpt != quote:
                return None
            try:
                validate_depth_report_source(
                    document.report,
                    source=DepthSource(project_id=source.project_id, document_id=document.document_id,
                                       source_version_id=document.source_version_id,
                                       source_revision=document.source_revision, source_hash=document.source_hash),
                    chapters={c.chapter_id: c.content for c in source.chapters},
                )
            except ValueError:
                return None
        else:
            # The stage-31 producer clipped MAX_EXCERPT code points and then
            # stripped the quote without updating its end offset. Its stable
            # ID proves this precise old projection; arbitrary IDs/spans fail.
            position = len(prefix)
            end = min(len(chapter.content), position + MAX_EXCERPT)
            legacy_id = self._slug(f"evidence:{document.document_id}:{source.version_id}:"
                                   f"{chapter.chapter_id}:{item.label}:{position}:{item.excerpt}")
            if (item.evidence_id != legacy_id
                    or item.end_offset != self._utf16_length(chapter.content[:end])):
                return None
        return EvidenceRef.model_validate({**item.model_dump(), "excerpt": quote})

    def evidence(self, project_id: str, account_id: str, evidence_id: str, *, document_id: str | None = None) -> dict[str, object]:
        source = self._source(project_id, account_id)
        record = self._record(project_id, account_id)
        if record is None:
            raise DeconstructionServiceError("evidence_missing", "这条拆解证据不存在。", status_code=404)
        active = self._document(record, record.active_document_id)
        active_depth = bool(
            active is not None
            and active.status == "completed"
            and active.analysis_contract_version == "2.0"
            and active.engine_revision == RULE_ENGINE_REVISION
            and self._document_matches_source(active, source)
        )
        current_scope_ids = {item["document_id"] for item in self._volumes(source, record) if item["match"]}
        for document in sorted(record.documents, key=lambda item: item.document_id != record.active_document_id):
            if document_id is not None and document.document_id != document_id:
                continue
            for item in document.evidence:
                if item.evidence_id != evidence_id:
                    continue
                verified = self._verified_evidence(source, document, item)
                depth_current = bool(
                    active_depth
                    and active is not None
                    and item.document_id == active.document_id
                    and source.sufficient
                    and item.source_version_id == source.version_id
                    and item.source_revision == source.source_revision
                    and item.source_hash == source.source_hash
                    and verified is not None
                )
                chapter = next((chapter for chapter in source.chapters if chapter.chapter_id == item.chapter_id), None)
                scope_current = bool(
                    document.analysis_contract_version == "model.1"
                    and document.status == "completed"
                    and not source.pending_changes
                    and document.document_id in current_scope_ids
                    and item.document_id == document.document_id
                    and item.source_version_id == document.source_version_id
                    and item.source_revision == document.source_revision
                    and item.source_hash == document.source_hash
                    and chapter is not None
                    and chapter.chapter_number == item.chapter_number
                    and verified is not None
                )
                source_matches_current = depth_current or scope_current
                if not source_matches_current or chapter is None:
                    historical = self._historical_source(project_id, account_id, item.source_version_id)
                    old_chapter = next((c for c in historical.chapters if c.chapter_id == item.chapter_id
                                        and c.chapter_number == item.chapter_number), None)
                    verified = self._verified_evidence(historical, document, item)
                    available = verified is not None and old_chapter is not None
                    return {
                        "project_id": project_id,
                        "title": source.title,
                        "evidence": (verified or item).model_dump(mode="json"),
                        "chapter": {
                            "chapter_id": item.chapter_id,
                            "chapter_number": item.chapter_number,
                            "title": old_chapter.title if available else "历史稿本章节",
                            "read_only": True,
                            "source_available": available,
                            "source_version_id": item.source_version_id,
                            "content": old_chapter.content if available else None,
                        },
                        "source_matches_current": False,
                        "historical": True,
                    }
                return {
                    "project_id": project_id,
                    "title": source.title,
                    "evidence": verified.model_dump(mode="json"),
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
