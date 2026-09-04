"""阶段 2：独立创作、档案与稿本版本的数据合同。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


VersionStatus = Literal["active", "recoverable", "archived"]
ChapterStatus = Literal["drafting", "analyzing", "ready", "failed"]
ImportStatus = Literal["pending", "confirmed", "failed"]
TaskKind = Literal["chapter_analysis", "full_rebuild", "restore"]
TaskStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
ChangeDecision = Literal["ignore", "rebuild"]


class StoryCharacter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_id: str
    name: str
    role: str = "未分类"
    profile: str
    current_state: str = "未记录"
    source_chapter_number: int = Field(..., ge=1)
    card_style: str = "折页角色牌"
    image_status: Literal["not_requested", "unconfigured"] = "not_requested"


class StorylineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storyline_id: str
    title: str
    summary: str
    source_chapter_number: int = Field(..., ge=1)


class ForeshadowingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    foreshadowing_id: str
    text: str
    status: Literal["open", "resolved"] = "open"
    source_chapter_number: int = Field(..., ge=1)


class QuestionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    text: str
    source_chapter_number: int = Field(..., ge=1)
    tone: Literal["gentle"] = "gentle"


class ArchiveSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    chapter_number: int = Field(..., ge=1)
    created_at: datetime
    analysis_label: str = "确定性演示分析（未配置模型 Key）"
    characters: list[StoryCharacter] = Field(default_factory=list)
    storylines: list[StorylineItem] = Field(default_factory=list)
    foreshadowing: list[ForeshadowingItem] = Field(default_factory=list)
    questions: list[QuestionItem] = Field(default_factory=list)


class StoryArchive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_label: str = "确定性演示分析（未配置模型 Key）"
    latest_chapter_number: int | None = Field(default=None, ge=1)
    characters: list[StoryCharacter] = Field(default_factory=list)
    storylines: list[StorylineItem] = Field(default_factory=list)
    foreshadowing: list[ForeshadowingItem] = Field(default_factory=list)
    questions: list[QuestionItem] = Field(default_factory=list)
    snapshots: list[ArchiveSnapshot] = Field(default_factory=list)


class ChapterDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    title: str
    formal_title: str | None = None
    content: str = ""
    formal_content: str = ""
    server_revision: int = Field(default=0, ge=0)
    word_count: int = Field(default=0, ge=0)
    formal_word_count: int = Field(default=0, ge=0)
    status: ChapterStatus = "drafting"
    last_completed_hash: str | None = None
    updated_at: datetime


class ManuscriptVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: str
    label: str
    status: VersionStatus = "active"
    created_at: datetime
    updated_at: datetime
    recoverable_until: datetime | None = None
    source_version_id: str | None = None
    chapters: list[ChapterDocument] = Field(default_factory=list)
    archive: StoryArchive = Field(default_factory=StoryArchive)


class ImportChapterPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_number: int = Field(..., ge=1)
    title: str
    content: str
    word_count: int = Field(default=0, ge=0)


class ImportPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_id: str
    filename: str
    format: Literal["txt", "md", "docx"] | None = None
    title: str
    chapter_count: int = Field(default=0, ge=0)
    total_word_count: int = Field(default=0, ge=0)
    chapters: list[ImportChapterPreview] = Field(default_factory=list)
    unrecognized_fragments: list[str] = Field(default_factory=list)
    status: ImportStatus = "pending"
    error_message: str | None = None
    input_size_bytes: int = Field(default=0, ge=0)
    raw_preserved: bool = True
    created_at: datetime


class ImportPreviewRecord(ImportPreview):
    """带原始文本的内部记录；原文不会通过公开响应合同返回。"""

    raw_text: str = ""


class ChangeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    title: str
    before_word_count: int = Field(default=0, ge=0)
    after_word_count: int = Field(default=0, ge=0)
    delta_word_count: int = 0
    changed_ranges: list[str] = Field(default_factory=list)
    recommendation: str


class PendingChangeBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: str
    version_id: str
    created_at: datetime
    updated_at: datetime
    changes: list[ChangeSummary] = Field(default_factory=list)
    last_decision: ChangeDecision | None = None
    decision_note: str | None = None


class AnalysisTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    kind: TaskKind
    status: TaskStatus = "queued"
    project_id: str
    version_id: str
    chapter_id: str | None = None
    content_hash: str | None = None
    idempotency_key: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class DeconstructionOutboxItem(BaseModel):
    """与正文同文件落盘的拆解触发事件，不携带正文或模型材料。"""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    reason: str = Field(default="正文更新", max_length=120)
    created_at: datetime
    attempts: int = Field(default=0, ge=0)
    last_error_code: str | None = Field(default=None, max_length=80)


class NotificationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notification_id: str
    kind: Literal["analysis_completed", "analysis_failed", "version_created", "change_decision"]
    message: str
    created_at: datetime
    read: bool = False


class IndependentProjectRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    account_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    active_version_id: str | None = None
    versions: list[ManuscriptVersion] = Field(default_factory=list)
    pending_imports: list[ImportPreviewRecord] = Field(default_factory=list)
    pending_changes: PendingChangeBatch | None = None
    tasks: list[AnalysisTask] = Field(default_factory=list)
    notifications: list[NotificationRecord] = Field(default_factory=list)
    change_history: list[str] = Field(default_factory=list)
    deconstruction_outbox: list[DeconstructionOutboxItem] = Field(default_factory=list, max_length=50)


class StartIndependentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source: Literal["blank"] = "blank"


class ImportPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    filename: str = Field(..., min_length=1, max_length=255)
    content_base64: str = Field(..., min_length=1)


class SaveDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., max_length=2_000_000)
    title: str | None = Field(default=None, max_length=200)
    expected_revision: int = Field(..., ge=0)


class CompleteChapterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., max_length=2_000_000)
    expected_revision: int = Field(..., ge=0)
    idempotency_key: str | None = Field(default=None, max_length=120)


class ResolveChangesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ChangeDecision


class TrialSketchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    style: Literal["水墨线稿", "铅笔速写", "版画剪影"]
    confirm: bool = False
