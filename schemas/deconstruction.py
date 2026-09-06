"""作品拆解 MVP 的持久化与 API 数据合同。

作品拆解是独立创作内部的一项可回溯分析，不是第三条顶层创作路径。
本文件只描述已经通过安全校验、可公开给当前账户的结构化结论；不保存
prompt、原始模型输出或整本正文。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from schemas.analysis_report import AnalysisReport


DeconstructionStatus = Literal[
    "empty",
    "queued",
    "running",
    "completed",
    "failed_retryable",
    "stale",
    "rebuild_required",
]
DeconstructionEffectiveStatus = DeconstructionStatus
DeconstructionRunStatus = Literal["none", "queued", "running", "completed", "failed_retryable"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceRef(BaseModel):
    """能回到同一稿本、同一章节和最小片段的证据定位。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    evidence_id: str
    document_id: str = ""
    source_version_id: str
    source_revision: int = Field(default=0, ge=0)
    source_hash: str = ""
    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    start_offset: int = Field(default=0, ge=0)
    end_offset: int = Field(default=0, ge=0)
    offset_unit: Literal["utf16_code_unit"] = "utf16_code_unit"
    excerpt: str = Field(default="", max_length=180)
    label: str = Field(default="正文证据", max_length=120)
    target_path: str | None = Field(default=None, max_length=500)


class DeconstructionObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(default="", max_length=500)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: list[str] = Field(default_factory=list, max_length=8)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=8)


class DeconstructionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label: str = Field(default="候选", max_length=80)
    value: str = Field(..., min_length=1, max_length=300)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: list[str] = Field(default_factory=list, max_length=8)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=8)


class DeconstructionOverview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(default="未命名作品", max_length=200)
    total_word_count: int = Field(default=0, ge=0)
    chapter_count: int = Field(default=0, ge=0)
    structure_units: list[str] = Field(default_factory=list, max_length=40)
    main_character_candidates: list[DeconstructionCandidate] = Field(default_factory=list, max_length=30)
    core_conflict_candidates: list[DeconstructionCandidate] = Field(default_factory=list, max_length=20)
    opening: DeconstructionObservation = Field(default_factory=DeconstructionObservation)
    development: DeconstructionObservation = Field(default_factory=DeconstructionObservation)
    climax: DeconstructionObservation = Field(default_factory=DeconstructionObservation)
    ending: DeconstructionObservation = Field(default_factory=DeconstructionObservation)
    uncertainty: list[str] = Field(default_factory=list, max_length=20)


class TimelineNode(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    node_id: str
    label: str = Field(..., max_length=160)
    normalized_start: float = Field(..., ge=0.0, le=100.0)
    normalized_end: float = Field(..., ge=0.0, le=100.0)
    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    chapter_title: str = Field(default="", max_length=200)
    word_start: int = Field(default=0, ge=0)
    word_end: int = Field(default=0, ge=0)
    event: str = Field(default="", max_length=600)
    narrative_function: str = Field(default="不确定", max_length=160)
    characters: list[str] = Field(default_factory=list, max_length=30)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: list[str] = Field(default_factory=list, max_length=8)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=8)


class ChapterBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    title: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=500)
    core_events: list[str] = Field(default_factory=list, max_length=12)
    narrative_function: str = Field(default="不确定", max_length=160)
    scenes: list[str] = Field(default_factory=list, max_length=12)
    conflict: str = Field(default="不确定", max_length=500)
    information_release: str = Field(default="不确定", max_length=500)
    relationship_change: str = Field(default="不确定", max_length=500)
    emotional_change: str = Field(default="不确定", max_length=500)
    foreshadowing: list[str] = Field(default_factory=list, max_length=12)
    opening_hook: str = Field(default="", max_length=300)
    ending_hook: str = Field(default="", max_length=300)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: list[str] = Field(default_factory=list, max_length=12)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=16)


class DeconstructionDocument(BaseModel):
    """一次绑定到稿本来源的拆解运行和完成结果。"""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    project_id: str
    account_id: str
    source_version_id: str
    source_revision: int = Field(default=0, ge=0)
    source_hash: str = Field(..., min_length=16, max_length=128)
    status: DeconstructionStatus = "queued"
    progress_percent: int = Field(default=0, ge=0, le=100)
    current_stage: str = Field(default="等待拆解", max_length=120)
    idempotency_key: str
    retry_count: int = Field(default=0, ge=0)
    analysis_label: str = "确定性结构拆解（无模型）"
    overview: DeconstructionOverview | None = None
    timeline: list[TimelineNode] = Field(default_factory=list)
    report: AnalysisReport | None = None
    chapter_breakdowns: list[ChapterBreakdown] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list, max_length=40)
    error_message: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class DeconstructionProjectRecord(BaseModel):
    """按作品保存当前运行与历史拆解，不改写独立正文侧车。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    account_id: str
    active_document_id: str | None = None
    documents: list[DeconstructionDocument] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class DeconstructionActions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retry: bool = False
    rebuild: bool = False


class DeconstructionProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    percent: int = Field(default=0, ge=0, le=100)
    current_stage: str = Field(default="等待拆解", max_length=120)


class DeconstructionSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: str | None = None
    revision: int | None = Field(default=None, ge=0)
    hash: str | None = None
    match: bool = False
    chapter_count: int = Field(default=0, ge=0)
    total_word_count: int = Field(default=0, ge=0)


class DeconstructionError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    retryable: bool = False


class DeconstructionActiveRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    run_status: DeconstructionRunStatus
    source_version_id: str
    source_revision: int = Field(default=0, ge=0)
    source_hash: str
    retry_count: int = Field(default=0, ge=0)
    idempotency_key: str
    analysis_label: str = "确定性结构拆解（无模型）"
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class DeconstructionDocumentPublic(BaseModel):
    """阶段 31A 兼容投影；不含内部 account_id。"""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    project_id: str
    source_version_id: str
    source_revision: int = Field(default=0, ge=0)
    source_hash: str
    status: DeconstructionStatus
    progress_percent: int = Field(default=0, ge=0, le=100)
    current_stage: str = Field(default="等待拆解", max_length=120)
    idempotency_key: str
    retry_count: int = Field(default=0, ge=0)
    analysis_label: str = "确定性结构拆解（无模型）"
    overview: DeconstructionOverview | None = None
    timeline: list[TimelineNode] = Field(default_factory=list)
    report: AnalysisReport | None = None
    chapter_breakdowns: list[ChapterBreakdown] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list, max_length=40)
    error_message: str | None = Field(default=None, max_length=500)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class DeconstructionResult(BaseModel):
    """只承载与当前 source 匹配的已完成结果。"""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    status: Literal["completed"] = "completed"
    source_version_id: str
    source_revision: int = Field(default=0, ge=0)
    source_hash: str
    analysis_label: str = "确定性结构拆解（无模型）"
    overview: DeconstructionOverview
    timeline: list[TimelineNode] = Field(default_factory=list)
    report: AnalysisReport | None = None
    chapter_breakdowns: list[ChapterBreakdown] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list, max_length=40)


class DeconstructionHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    status: DeconstructionStatus
    source_version_id: str
    source_revision: int = Field(default=0, ge=0)
    source_hash: str
    retry_count: int = Field(default=0, ge=0)
    analysis_label: str = "确定性结构拆解（无模型）"
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class DeconstructionEvidenceChapter(BaseModel):
    """证据回链公开的稳定章节定位，不包含正文或内部字段。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    title: str = Field(default="", max_length=200)
    read_only: Literal[True] = True
    source_available: bool = False


class DeconstructionState(BaseModel):
    """兼容旧客户端的嵌套投影；字段与顶层 canonical state 保持一致。"""

    model_config = ConfigDict(extra="forbid")

    effective_status: DeconstructionEffectiveStatus
    run_status: DeconstructionRunStatus
    source_match: bool
    progress: DeconstructionProgress
    current_stage: str = Field(default="等待拆解", max_length=120)
    source: DeconstructionSource
    active_run: DeconstructionActiveRun | None = None
    result: DeconstructionResult | None = None
    actions: DeconstructionActions
    error: DeconstructionError | None = None


class DeconstructionResponse(BaseModel):
    """浏览器/客户端合同，省略账户归属和内部协调字段。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    project_id: str
    title: str
    mode: Literal["independent"] = "independent"
    effective_status: DeconstructionEffectiveStatus
    run_status: DeconstructionRunStatus = "none"
    source_match: bool = False
    progress: DeconstructionProgress = Field(default_factory=DeconstructionProgress)
    source: DeconstructionSource = Field(default_factory=DeconstructionSource)
    active_run: DeconstructionActiveRun | None = None
    result: DeconstructionResult | None = None
    error: DeconstructionError | None = None
    actions: DeconstructionActions = Field(default_factory=DeconstructionActions)
    history: list[DeconstructionHistoryItem] = Field(default_factory=list)
    # 兼容阶段 31A 客户端；这些字段始终由 canonical state 同步生成。
    status: DeconstructionEffectiveStatus
    progress_percent: int = Field(default=0, ge=0, le=100)
    current_stage: str = "等待拆解"
    source_version_id: str | None = None
    source_revision: int | None = Field(default=None, ge=0)
    source_hash: str | None = None
    analysis_label: str = "确定性结构拆解（无模型）"
    empty_reason: str | None = None
    error_message: str | None = None
    retryable: bool = False
    initialized: bool = False
    deconstruction: DeconstructionState | None = None
    # 路由使用去除 account_id 的公开投影；内部文档模型不能直接作为浏览器合同。
    document: DeconstructionDocumentPublic | None = None

    @model_validator(mode="after")
    def validate_canonical_projection(self) -> "DeconstructionResponse":
        """拒绝顶层兼容字段与 canonical state 互相矛盾的公开响应。"""

        if self.status != self.effective_status:
            raise ValueError("status 必须与 effective_status 一致")
        if self.progress_percent != self.progress.percent or self.current_stage != self.progress.current_stage:
            raise ValueError("兼容进度字段必须与 progress 一致")
        if (
            self.source_version_id != self.source.version_id
            or self.source_revision != self.source.revision
            or self.source_hash != self.source.hash
            or self.source_match != self.source.match
        ):
            raise ValueError("兼容来源字段必须与 source 一致")
        if self.effective_status != "completed" and self.result is not None:
            raise ValueError("非 completed 状态不得返回正式 result")
        if self.result is not None and (not self.source_match or self.run_status != "completed"):
            raise ValueError("result 必须绑定当前来源且运行已完成")
        if self.deconstruction is not None:
            if (
                self.deconstruction.effective_status != self.effective_status
                or self.deconstruction.run_status != self.run_status
                or self.deconstruction.source_match != self.source_match
                or self.deconstruction.result != self.result
            ):
                raise ValueError("嵌套 deconstruction 必须与顶层 canonical state 一致")
        if self.active_run is not None and self.active_run.run_status != self.run_status:
            raise ValueError("active_run 必须与 run_status 一致")
        if self.effective_status in {"empty", "stale", "rebuild_required"} and self.document is not None:
            raise ValueError("空态或来源非当前状态不得返回当前 document")
        return self


class DeconstructionEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    title: str
    evidence: EvidenceRef
    chapter: DeconstructionEvidenceChapter
    source_matches_current: bool = False
    historical: bool = True


class DeconstructionActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    idempotency_key: str | None = Field(default=None, max_length=160)
    expected_source_version_id: str | None = Field(default=None, max_length=160)
    expected_source_revision: int | None = Field(default=None, ge=0)
    expected_source_hash: str | None = Field(default=None, min_length=16, max_length=128)
