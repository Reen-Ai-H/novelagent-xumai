"""章节与剧情节点模型。"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


DraftStatus = Literal["planned", "drafted", "reviewed", "approved", "needs_revision"]


class PlotBeat(BaseModel):
    """剧情节点：Planner Agent 输出、人工审核的最小剧情单元。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    beat_id: str = Field(default_factory=lambda: uuid4().hex, description="剧情节点唯一标识")
    order: int = Field(..., ge=1, description="节点在本章中的顺序，从 1 开始")
    summary: str = Field(..., min_length=1, description="节点摘要，描述本节点要发生的核心事件")
    purpose: str | None = Field(default=None, description="叙事目的，例如铺垫、反转、冲突升级")
    involved_characters: list[str] = Field(
        default_factory=list,
        description="出场或被显著影响的人物姓名列表",
    )
    location: str | None = Field(default=None, description="事件发生地点")
    conflict: str | None = Field(default=None, description="本节点的外部冲突或内心冲突")
    expected_outcome: str | None = Field(default=None, description="节点结束后应达成的剧情结果")
    continuity_constraints: list[str] = Field(
        default_factory=list,
        description="必须遵守的前文设定、伏笔或逻辑约束",
    )

    @field_validator("involved_characters")
    @classmethod
    def deduplicate_characters(cls, value: list[str]) -> list[str]:
        """保持人物列表稳定去重，避免同一角色在提示词中重复出现。"""

        return list(dict.fromkeys(value))


class ChapterDraft(BaseModel):
    """章节草稿：Writer 输出与 Reviewer 审查结果的聚合。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    chapter_number: int = Field(..., ge=1, description="章节序号，从 1 开始")
    title: str | None = Field(default=None, description="章节标题")
    plot_beats: list[PlotBeat] = Field(default_factory=list, description="本章采用的剧情节点")
    content: str = Field(default="", description="章节正文草稿")
    status: DraftStatus = Field(default="planned", description="章节草稿当前状态")
    reviewer_comments: list[str] = Field(
        default_factory=list,
        description="Reviewer Agent 给出的逻辑漏洞、OOC 或节奏问题",
    )
    revision_notes: list[str] = Field(
        default_factory=list,
        description="人工或 Agent 修改记录，便于追踪版本变化",
    )
    quality_score: float | None = Field(
        default=None,
        ge=0,
        le=10,
        description="审查评分，0-10；为空表示尚未审查",
    )

    @field_validator("plot_beats")
    @classmethod
    def ensure_unique_beat_order(cls, value: list[PlotBeat]) -> list[PlotBeat]:
        """同一章节中不允许出现重复的剧情节点顺序。"""

        orders = [beat.order for beat in value]
        if len(orders) != len(set(orders)):
            raise ValueError("plot_beats 中存在重复的 order")
        return value
