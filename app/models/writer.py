"""Writer Agent 的结构化输出模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WriterOutput(BaseModel):
    """LLM 生成的章节正文结果。"""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    title: str | None = Field(default=None, description="章节标题")
    content: str = Field(..., min_length=1, description="章节正文")
    writing_notes: list[str] = Field(
        default_factory=list,
        description="写作说明，例如节奏安排、伏笔处理或需要后续关注的点",
    )
