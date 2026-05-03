"""人物设定模型。

该模块描述小说中可被 RAG 检索、被 Agent 更新的人物卡片。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CharacterRole = Literal["protagonist", "supporting", "antagonist", "minor", "unknown"]


class CharacterCard(BaseModel):
    """人物卡片：维护角色长期设定与当前章节状态。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    name: str = Field(..., min_length=1, description="角色姓名，作为人物图谱中的主键")
    aliases: list[str] = Field(default_factory=list, description="别名、称号或常用伪装身份")
    role: CharacterRole = Field(default="unknown", description="角色在故事中的叙事定位")
    profile: str = Field(..., min_length=1, description="角色简介与长期人设")
    motivation: str | None = Field(default=None, description="当前核心动机或目标")
    current_psychological_state: str = Field(
        default="未记录",
        description="当前心理状态，例如恐惧、怀疑、兴奋、信任崩塌等",
    )
    current_physical_state: str = Field(
        default="未记录",
        description="当前物理状态，例如受伤、疲惫、易容、被囚禁等",
    )
    current_location: str | None = Field(default=None, description="最近一次出现的位置")
    relationships: dict[str, str] = Field(
        default_factory=dict,
        description="与其他角色的关系，key 为角色名，value 为关系描述",
    )
    inventory: list[str] = Field(default_factory=list, description="随身关键物品或能力")
    secrets: list[str] = Field(
        default_factory=list,
        description="角色秘密或伏笔；生成正文时应按权限谨慎暴露",
    )
    timeline_notes: list[str] = Field(
        default_factory=list,
        description="与该角色相关的重要时间线记录",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="卡片最后更新时间",
    )
