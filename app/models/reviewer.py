"""Reviewer Agent 的结构化输出模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewerOutput(BaseModel):
    """LLM 对章节草稿的审查结果。"""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    passed: bool = Field(..., description="章节是否通过本轮审查")
    quality_score: float = Field(..., ge=0, le=10, description="章节质量评分，范围 0-10")
    reviewer_comments: list[str] = Field(
        default_factory=list,
        description="发现的 OOC、逻辑冲突、设定矛盾或节奏问题",
    )
    revision_suggestions: list[str] = Field(
        default_factory=list,
        description="面向 Writer 或人工作者的可执行修改建议",
    )

    @field_validator("reviewer_comments", "revision_suggestions")
    @classmethod
    def drop_empty_items(cls, value: list[str]) -> list[str]:
        """清理空字符串，避免前端展示无意义审查项。"""

        return [item for item in value if item]
