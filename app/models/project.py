"""作品级模型：管理长篇小说、分卷和章节目录。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.models.chapter import ChapterDraft


ChapterRecordStatus = Literal[
    "planned",
    "drafted",
    "reviewed",
    "needs_revision",
    "approved",
    "completed",
    "failed",
]


class VolumePlan(BaseModel):
    """分卷规划，后续可用于控制阶段爽点和主线推进。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    volume_number: int = Field(..., ge=1, description="分卷序号")
    title: str = Field(default="第一卷", description="分卷标题")
    summary: str | None = Field(default=None, description="本卷主线或阶段目标")
    chapter_start: int = Field(default=1, ge=1, description="本卷起始章节")
    chapter_end: int | None = Field(default=None, ge=1, description="本卷预计结束章节")


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
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="最近更新时间")


class NovelProject(BaseModel):
    """作品级工程：聚合世界观、卷纲、章节目录和总字数。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: str = Field(default_factory=lambda: uuid4().hex, description="作品 ID")
    title: str = Field(default="未命名作品", description="作品标题")
    global_worldview: str = Field(default="", description="作品级世界观")
    volumes: list[VolumePlan] = Field(default_factory=list, description="分卷规划")
    chapters: list[ChapterRecord] = Field(default_factory=list, description="章节目录")
    current_chapter_number: int = Field(default=1, ge=1, description="当前工作章节")
    latest_session_id: str | None = Field(default=None, description="最近一次章节工作流会话")
    total_word_count: int = Field(default=0, ge=0, description="已完成章节总字数")
