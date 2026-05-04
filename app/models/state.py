"""LangGraph 全局状态定义。"""

from __future__ import annotations

from typing import Literal, TypedDict

from app.models.chapter import ChapterDraft, PlotBeat
from app.models.character import CharacterCard
from app.models.memory import RetrievalContext


WorkflowStage = Literal[
    "planning",
    "awaiting_human_review",
    "writing",
    "awaiting_review",
    "extracting_lore",
    "reviewing",
    "awaiting_revision_decision",
    "revising",
    "awaiting_chapter_acceptance",
    "completed",
    "failed",
]


class NovelState(TypedDict, total=False):
    """多智能体小说生成工作流的共享状态。

    LangGraph 节点会读写该字典。Pydantic 模型负责约束复杂字段，
    TypedDict 则让状态图在 Python 层获得更清晰的类型提示。
    """

    # 全局故事设定，可由用户初始化，并由 Librarian Agent 在章节后增量更新。
    global_worldview: str
    global_lore: dict[str, str]

    # 当前章节上下文。
    current_chapter_number: int
    current_stage: WorkflowStage
    current_plot_beats: list[PlotBeat]
    current_draft: ChapterDraft | None

    # 人物图谱：key 建议使用 CharacterCard.name，value 保存长期设定与当前状态。
    character_graph: dict[str, CharacterCard]

    # RAG 检索结果：写作前注入相关人物、地点、伏笔和历史章节摘要。
    retrieved_context: list[RetrievalContext]

    # Human-in-the-loop：Planner 后暂停，前端/API 可覆盖这里的节点后再继续。
    human_feedback: str | None
    human_approved: bool

    # Librarian 与 Reviewer 的产物。
    extracted_lore_updates: dict[str, str]
    extracted_character_updates: dict[str, CharacterCard]
    review_feedback: list[str]

    # 运行时辅助信息，便于 API 层追踪错误和请求。
    session_id: str
    project_id: str
    error_message: str | None
