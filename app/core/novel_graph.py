"""LangGraph 小说工作流编排。"""

from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph

from app.agents.novel_nodes import (
    librarian_agent,
    planner_agent,
    reviewer_agent,
    writer_agent,
)
from app.models import CharacterCard, NovelState, PlotBeat


def build_novel_graph():
    """构建 Planner -> Writer -> Reviewer -> Librarian 状态图。"""

    graph = StateGraph(NovelState)

    graph.add_node("planner", planner_agent)
    graph.add_node("writer", writer_agent)
    graph.add_node("librarian", librarian_agent)
    graph.add_node("reviewer", reviewer_agent)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "writer")
    graph.add_edge("writer", "reviewer")
    graph.add_edge("reviewer", "librarian")
    graph.add_edge("librarian", END)

    # Writer 之后的节点由服务层分段推进，便于前端逐步展示正文、审查和设定抽取结果。
    serializer = JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("app.models.chapter", "ChapterDraft"),
            ("app.models.chapter", "PlotBeat"),
            ("app.models.character", "CharacterCard"),
        ],
    )

    return graph.compile(
        checkpointer=InMemorySaver(serde=serializer),
        interrupt_before=["writer", "reviewer", "librarian"],
    )


class NovelWorkflowService:
    """面向 API 层的小说工作流服务。"""

    def __init__(self) -> None:
        self._graph = build_novel_graph()

    @staticmethod
    def _config(session_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": session_id}}

    def _get_state(self, session_id: str) -> NovelState:
        snapshot = self._graph.get_state(self._config(session_id))
        return cast(NovelState, dict(snapshot.values or {}))

    def plan_chapter(
        self,
        *,
        global_worldview: str,
        chapter_number: int,
        characters: list[CharacterCard],
        previous_summary: str | None = None,
        user_instruction: str | None = None,
        session_id: str | None = None,
    ) -> tuple[str, NovelState]:
        """启动章节规划，并在 Writer 前返回暂停状态。"""

        active_session_id = session_id or uuid4().hex
        initial_state: NovelState = {
            "session_id": active_session_id,
            "global_worldview": global_worldview,
            "global_lore": {
                "previous_summary": previous_summary or "",
            },
            "current_chapter_number": chapter_number,
            "current_stage": "planning",
            "current_plot_beats": [],
            "current_draft": None,
            "character_graph": {character.name: character for character in characters},
            "retrieved_context": [],
            "human_feedback": user_instruction,
            "human_approved": False,
            "extracted_lore_updates": {},
            "extracted_character_updates": {},
            "review_feedback": [],
            "error_message": None,
        }

        self._graph.invoke(initial_state, self._config(active_session_id))
        return active_session_id, self._get_state(active_session_id)

    def approve_plan(
        self,
        *,
        session_id: str,
        plot_beats: list[PlotBeat],
        human_feedback: str | None = None,
    ) -> NovelState:
        """提交人工审核后的剧情节点，并只推进 Writer 生成正文。"""

        current_state = self._get_state(session_id)
        if not current_state:
            raise KeyError(f"未找到会话: {session_id}")

        if current_state.get("current_stage") != "awaiting_human_review":
            raise ValueError("当前会话不在剧情节点审核阶段，无法继续。")

        self._graph.update_state(
            self._config(session_id),
            {
                "current_plot_beats": plot_beats,
                "human_feedback": human_feedback,
                "human_approved": True,
                "current_stage": "writing",
            },
            as_node="planner",
        )
        writer_input = self._get_state(session_id)
        writer_update = writer_agent(writer_input)
        self._graph.update_state(
            self._config(session_id),
            writer_update,
            as_node="writer",
        )
        return self._get_state(session_id)

    def review_draft(self, *, session_id: str) -> NovelState:
        """触发 Reviewer 审查当前 Writer 草稿。"""

        current_state = self._get_state(session_id)
        if not current_state:
            raise KeyError(f"未找到会话: {session_id}")

        if current_state.get("current_stage") not in {"awaiting_review", "reviewing"}:
            raise ValueError("当前会话不在可审查阶段，无法触发 Reviewer。")

        self._graph.update_state(
            self._config(session_id),
            {"current_stage": "reviewing"},
            as_node="writer",
        )
        reviewer_update = reviewer_agent(self._get_state(session_id))
        self._graph.update_state(
            self._config(session_id),
            reviewer_update,
            as_node="reviewer",
        )
        return self._get_state(session_id)

    def revise_draft(
        self,
        *,
        session_id: str,
        human_feedback: str | None = None,
    ) -> NovelState:
        """根据 Reviewer 意见重新生成章节草稿。"""

        current_state = self._get_state(session_id)
        if not current_state:
            raise KeyError(f"未找到会话: {session_id}")

        if current_state.get("current_stage") != "awaiting_revision_decision":
            raise ValueError("当前会话不在等待修稿确认阶段，无法重新生成正文。")

        review_feedback = current_state.get("review_feedback", [])
        revision_feedback = human_feedback or "请根据 Reviewer 审查意见修订本章。"
        if review_feedback:
            revision_feedback = (
                f"{revision_feedback}\n\nReviewer 审查意见：\n"
                + "\n".join(f"- {comment}" for comment in review_feedback)
            )

        self._graph.update_state(
            self._config(session_id),
            {
                "human_feedback": revision_feedback,
                "current_stage": "revising",
                "extracted_lore_updates": {},
                "extracted_character_updates": {},
            },
            as_node="reviewer",
        )
        writer_update = writer_agent(self._get_state(session_id))
        self._graph.update_state(
            self._config(session_id),
            writer_update,
            as_node="writer",
        )
        return self._get_state(session_id)

    def accept_chapter(
        self,
        *,
        session_id: str,
        human_feedback: str | None = None,
    ) -> NovelState:
        """用户接受本章节后，触发 Librarian 抽取设定并完成章节。"""

        current_state = self._get_state(session_id)
        if not current_state:
            raise KeyError(f"未找到会话: {session_id}")

        if current_state.get("current_stage") not in {
            "awaiting_chapter_acceptance",
            "awaiting_revision_decision",
        }:
            raise ValueError("当前会话不在可接受章节阶段，无法抽取设定。")

        self._graph.update_state(
            self._config(session_id),
            {
                "human_feedback": human_feedback,
                "current_stage": "extracting_lore",
            },
            as_node="reviewer",
        )
        librarian_update = librarian_agent(self._get_state(session_id))
        self._graph.update_state(
            self._config(session_id),
            {
                **librarian_update,
                "current_stage": "completed"
                if librarian_update.get("current_stage") != "failed"
                else "failed",
            },
            as_node="librarian",
        )
        return self._get_state(session_id)

    def get_state(self, session_id: str) -> NovelState:
        """读取会话状态，供调试接口使用。"""

        state = self._get_state(session_id)
        if not state:
            raise KeyError(f"未找到会话: {session_id}")
        return state


novel_workflow_service = NovelWorkflowService()
