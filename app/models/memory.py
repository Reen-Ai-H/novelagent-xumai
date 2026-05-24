"""RAG 长文本记忆模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


MemoryCategory = Literal[
    "chapter_summary",
    "character",
    "location",
    "item",
    "foreshadowing",
    "world_lore",
    "plot",
]

MemorySource = Literal["librarian", "manual", "imported"]


class MemoryItem(BaseModel):
    """可被检索的长期记忆条目。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    memory_id: str = Field(default_factory=lambda: uuid4().hex, description="记忆条目唯一标识")
    project_id: str = Field(default="default", description="所属作品 ID")
    category: MemoryCategory = Field(default="world_lore", description="记忆分类")
    title: str = Field(..., min_length=1, description="记忆标题或设定 key")
    content: str = Field(..., min_length=1, description="可注入 prompt 的记忆正文")
    chapter_number: int | None = Field(default=None, ge=1, description="来源章节号")
    source: MemorySource = Field(default="librarian", description="记忆来源")
    source_id: str | None = Field(default=None, description="来源对象 ID，例如 session_id 或角色名")
    tags: list[str] = Field(default_factory=list, description="检索标签")
    importance: float = Field(default=0.5, ge=0, le=1, description="记忆重要度，0-1")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")


class RetrievalContext(BaseModel):
    """一次 RAG 检索命中的上下文。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    item: MemoryItem = Field(..., description="命中的记忆条目")
    score: float = Field(..., ge=0, description="本次检索相关性分数")
    reason: str = Field(default="", description="命中原因，供调试展示")
    formatted_text: str = Field(..., description="已格式化、可直接注入 prompt 的文本")
