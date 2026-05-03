"""Librarian Agent 的结构化输出模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.character import CharacterCard


class LibrarianOutput(BaseModel):
    """LLM 从章节正文中抽取出的设定增量。"""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    global_lore_updates: dict[str, str] = Field(
        default_factory=dict,
        description="需要合并进全局设定库的新增设定，key 应简短稳定",
    )
    character_updates: list[CharacterCard] = Field(
        default_factory=list,
        description="新人物或已有角色状态变化后的完整人物卡",
    )
    extraction_notes: list[str] = Field(
        default_factory=list,
        description="抽取说明或后续需要人工确认的设定风险",
    )
