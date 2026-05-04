"""小说工作流 API Schema。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    ChapterDraft,
    CharacterCard,
    NovelProject,
    PlotBeat,
    RetrievalContext,
    WorkflowStage,
)


class NovelPlanRequest(BaseModel):
    """请求生成指定章节的剧情节点。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    session_id: str | None = Field(default=None, description="会话 ID；为空时服务端自动生成")
    project_id: str | None = Field(default=None, description="作品 ID；为空时使用默认作品")
    project_title: str | None = Field(default=None, description="作品标题，仅在创建或更新作品时使用")
    global_worldview: str = Field(..., min_length=1, description="小说世界观、题材和核心设定")
    chapter_number: int = Field(..., ge=1, description="要生成的章节号")
    previous_summary: str | None = Field(default=None, description="前文摘要或上一章进度")
    user_instruction: str | None = Field(default=None, description="用户对本章的额外创作要求")
    characters: list[CharacterCard] = Field(
        default_factory=list,
        description="本次生成可用的人物卡片",
    )


class NovelPlanResponse(BaseModel):
    """Planner 暂停点返回给前端的剧情节点。"""

    session_id: str = Field(..., description="会话 ID，用于后续提交人工审核结果")
    current_stage: WorkflowStage = Field(..., description="当前工作流阶段")
    plot_beats: list[PlotBeat] = Field(..., description="待人工审核的剧情节点")
    message: str = Field(..., description="给 API 调试或前端展示的状态信息")


class ContinueChapterRequest(BaseModel):
    """基于当前作品目录继续规划下一章。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    session_id: str | None = Field(default=None, description="会话 ID；为空时服务端自动生成")
    user_instruction: str | None = Field(default=None, description="下一章额外创作要求")
    characters: list[CharacterCard] = Field(
        default_factory=list,
        description="下一章生成时额外可用的人物卡片",
    )


class NovelApprovalRequest(BaseModel):
    """用户审核、修改剧情节点后的提交体。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    plot_beats: list[PlotBeat] = Field(..., min_length=1, description="用户确认后的剧情节点")
    human_feedback: str | None = Field(default=None, description="人工审核意见或修改说明")


class NovelActionRequest(BaseModel):
    """章节审查、修稿或接受章节时的可选人工说明。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    human_feedback: str | None = Field(default=None, description="用户对本次操作的补充说明")


class NovelRunResponse(BaseModel):
    """状态机完成一轮章节生成后的返回结果。"""

    session_id: str = Field(..., description="会话 ID")
    current_stage: WorkflowStage = Field(..., description="当前工作流阶段")
    draft: ChapterDraft | None = Field(default=None, description="生成并审查后的章节草稿")
    extracted_lore_updates: dict[str, str] = Field(
        default_factory=dict,
        description="Librarian 抽取出的世界观增量",
    )
    extracted_character_updates: dict[str, CharacterCard] = Field(
        default_factory=dict,
        description="Librarian 抽取出的人物卡片增量或状态更新",
    )
    review_feedback: list[str] = Field(default_factory=list, description="Reviewer 审查意见")
    retrieved_context: list[RetrievalContext] = Field(
        default_factory=list,
        description="本轮 Writer 或 Reviewer 使用的长期记忆检索结果",
    )
    message: str = Field(..., description="给 API 调试或前端展示的状态信息")


class NovelProjectResponse(BaseModel):
    """作品级目录和进度返回。"""

    project: NovelProject = Field(..., description="作品级工程状态")
