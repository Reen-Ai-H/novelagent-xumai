"""作品拆解 MVP 的持久化与 API 数据合同。

作品拆解是独立创作内部的一项可回溯分析，不是第三条顶层创作路径。
本文件只描述已经通过安全校验、可公开给当前账户的结构化结论；不保存
prompt、原始模型输出或整本正文。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DeconstructionStatus = Literal[
    "empty",
    "queued",
    "running",
    "completed",
    "failed_retryable",
    "stale",
    "rebuild_required",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceRef(BaseModel):
    """能回到同一稿本、同一章节和最小片段的证据定位。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    evidence_id: str
    source_version_id: str
    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    start_offset: int = Field(default=0, ge=0)
    end_offset: int = Field(default=0, ge=0)
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


class DeconstructionResponse(BaseModel):
    """浏览器/客户端合同，省略账户归属和内部协调字段。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    title: str
    status: DeconstructionStatus
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
    actions: dict[str, bool] = Field(default_factory=dict)
    deconstruction: dict[str, object] = Field(default_factory=dict)
    # 路由使用去除 account_id 的公开投影；内部文档模型不能直接作为浏览器合同。
    document: dict[str, object] | None = None
    history: list[dict[str, object]] = Field(default_factory=list)


class DeconstructionEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    title: str
    evidence: EvidenceRef
    chapter: dict[str, object]
