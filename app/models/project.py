"""作品级模型：管理长篇小说、分卷和章节目录。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.models.chapter import ChapterDraft, PlotBeat
from app.models.character import CharacterCard


ChapterRecordStatus = Literal[
    "planned",
    "drafted",
    "reviewed",
    "needs_revision",
    "approved",
    "completed",
    "failed",
]

BatchTaskKind = Literal["plan", "generate"]
BatchTaskStatus = Literal["pending", "running", "completed", "failed", "partial"]
BatchChapterStatus = Literal["pending", "planned", "generated", "reviewed", "skipped", "conflict", "failed"]


class VolumePlan(BaseModel):
    """分卷规划，后续可用于控制阶段爽点和主线推进。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    volume_number: int = Field(..., ge=1, description="分卷序号")
    title: str = Field(default="第一卷", description="分卷标题")
    summary: str | None = Field(default=None, description="本卷主线或阶段目标")
    chapter_start: int = Field(default=1, ge=1, description="本卷起始章节")
    chapter_end: int | None = Field(default=None, ge=1, description="本卷预计结束章节")


class FullNovelPlan(BaseModel):
    """全文规划：保存作品级主线、结局方向和整体结构。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    premise: str = Field(default="", description="一句话故事前提或核心卖点")
    core_conflict: str = Field(default="", description="贯穿全文的核心冲突")
    ending_direction: str = Field(default="", description="预期结局或终局方向")
    themes: list[str] = Field(default_factory=list, description="主题、爽点或情绪关键词")
    target_chapter_count: int | None = Field(
        default=None,
        ge=1,
        description="目标章节数",
    )
    notes: list[str] = Field(default_factory=list, description="全文规划备注")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="最近更新时间")


class ChapterOutline(BaseModel):
    """章节级大纲：保存章节目标与可复用的 Planner 节点。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chapter_number: int = Field(..., ge=1, description="章节号")
    title: str | None = Field(default=None, description="章节标题")
    volume_number: int | None = Field(default=None, ge=1, description="所属分卷")
    summary: str = Field(default="", description="章节规划摘要")
    purpose: str | None = Field(default=None, description="章节叙事目的")
    plot_beats: list[PlotBeat] = Field(default_factory=list, description="本章剧情节点")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="最近更新时间")


ChapterPlan = ChapterOutline


class NextChapterSeed(BaseModel):
    """下一章输入快照：prepare-next 生成，供前端确认后再正式 Planner。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: str = Field(..., description="作品 ID")
    chapter_number: int = Field(..., ge=1, description="建议生成的下一章号")
    global_worldview: str = Field(default="", description="预填世界观")
    confirmed_worldview: str = Field(default="", description="已确认世界观和已接受设定")
    previous_summary: str = Field(default="", description="预填前文摘要")
    current_character_state: list[CharacterCard] = Field(
        default_factory=list,
        description="当前人物状态",
    )
    unresolved_foreshadowing: list[str] = Field(
        default_factory=list,
        description="未解决伏笔",
    )
    last_chapter_hook: str = Field(default="", description="上一章结尾钩子")
    recommended_next_directions: list[str] = Field(
        default_factory=list,
        description="推荐的下一章创作方向",
    )
    user_instruction: str | None = Field(default=None, description="预填本章创作要求")
    characters: list[CharacterCard] = Field(default_factory=list, description="预填人物卡片")
    source_chapter_number: int | None = Field(default=None, ge=1, description="承接的上一章号")
    chapter_plan: ChapterOutline | None = Field(default=None, description="命中的章节规划")
    prepared_at: datetime = Field(default_factory=datetime.utcnow, description="准备时间")


NextChapterInputSnapshot = NextChapterSeed


class BatchChapterResult(BaseModel):
    """批量任务中的单章处理状态，供前端逐章展示。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chapter_number: int = Field(..., ge=1, description="章节号")
    session_id: str | None = Field(default=None, description="关联会话 ID")
    status: BatchChapterStatus = Field(default="pending", description="批量处理状态")
    draft_status: str | None = Field(default=None, description="草稿状态")
    review_status: str | None = Field(default=None, description="审查状态")
    can_review: bool = Field(default=False, description="是否可进入审查")
    can_accept: bool = Field(default=False, description="是否可接受章节")
    can_revise: bool = Field(default=False, description="是否可修订章节")
    conflict_type: str | None = Field(default=None, description="冲突类型")


class BatchGenerationRun(BaseModel):
    """批量任务状态：同步任务也写入状态，后续可平滑迁移到异步队列。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    task_id: str = Field(default_factory=lambda: uuid4().hex, description="批量任务 ID")
    kind: BatchTaskKind = Field(..., description="任务类型")
    status: BatchTaskStatus = Field(default="pending", description="任务状态")
    chapter_numbers: list[int] = Field(default_factory=list, description="涉及章节号")
    session_ids: dict[int, str] = Field(default_factory=dict, description="章节号到会话 ID 的映射")
    chapter_results: list[BatchChapterResult] = Field(
        default_factory=list,
        description="逐章处理状态",
    )
    overwrite_policy: str = Field(default="block", description="已有章节覆盖策略")
    pending_acceptance_chapter_numbers: list[int] = Field(
        default_factory=list,
        description="已审查通过、等待用户接受的章节号",
    )
    needs_revision_chapter_numbers: list[int] = Field(
        default_factory=list,
        description="审查后等待修订的章节号",
    )
    message: str = Field(default="", description="任务状态说明")
    error_message: str | None = Field(default=None, description="失败原因")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")


BatchTaskRecord = BatchGenerationRun


class ChapterRecord(BaseModel):
    """章节目录记录：把单章会话沉淀成作品级进度。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chapter_number: int = Field(..., ge=1, description="章节号")
    title: str | None = Field(default=None, description="章节标题")
    status: ChapterRecordStatus = Field(default="planned", description="章节状态")
    session_id: str | None = Field(default=None, description="关联的 LangGraph 会话 ID")
    summary: str = Field(default="", description="章节摘要，供下一章规划使用")
    word_count: int = Field(default=0, ge=0, description="章节正文字数")
    draft: ChapterDraft | None = Field(default=None, description="当前章节草稿快照")
    quality_score: float | None = Field(default=None, ge=0, le=10, description="最近审查评分")
    review_feedback: list[str] = Field(default_factory=list, description="最近审查意见")
    review_status: str | None = Field(default=None, description="最近审查状态")
    can_accept: bool = Field(default=False, description="是否可接受章节")
    can_revise: bool = Field(default=False, description="是否可修订章节")
    candidate_draft: ChapterDraft | None = Field(default=None, description="重新生成候选草稿")
    draft_comparison_summary: str | None = Field(default=None, description="原稿与候选稿对比摘要")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="最近更新时间")


class NovelProject(BaseModel):
    """作品级工程：聚合世界观、卷纲、章节目录和总字数。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: str = Field(default_factory=lambda: uuid4().hex, description="作品 ID")
    title: str = Field(default="未命名作品", description="作品标题")
    project_brief: str | None = Field(default=None, description="作品摘要，供首页卡片展示")
    global_worldview: str = Field(default="", description="作品级世界观")
    character_codex: list[CharacterCard] = Field(default_factory=list, description="作品级人物设定集")
    lore_codex: dict[str, str] = Field(default_factory=dict, description="作品级剧情与世界观设定集")
    full_plan: FullNovelPlan | None = Field(default=None, description="全文规划")
    volumes: list[VolumePlan] = Field(default_factory=list, description="分卷规划")
    chapter_plans: list[ChapterPlan] = Field(default_factory=list, description="章节规划列表")
    chapters: list[ChapterRecord] = Field(default_factory=list, description="章节目录")
    next_chapter_input_snapshot: NextChapterInputSnapshot | None = Field(
        default=None,
        description="最近一次下一章输入快照",
    )
    batch_tasks: list[BatchTaskRecord] = Field(default_factory=list, description="批量任务状态")
    latest_edited_chapter_number: int | None = Field(
        default=None,
        ge=1,
        description="最近编辑章节",
    )
    current_chapter_number: int = Field(default=1, ge=1, description="当前工作章节")
    latest_session_id: str | None = Field(default=None, description="最近一次章节工作流会话")
    total_word_count: int = Field(default=0, ge=0, description="已完成章节总字数")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="最近更新时间")
