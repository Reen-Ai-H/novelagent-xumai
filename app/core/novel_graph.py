"""LangGraph 小说工作流编排。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph

from app.core.memory import memory_store
from app.core.retriever import build_memory_items_from_state
from app.agents.novel_nodes import (
    librarian_agent,
    planner_agent,
    reviewer_agent,
    writer_agent,
)
from app.models import ChapterRecord, CharacterCard, NovelProject, NovelState, PlotBeat


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
            ("app.models.memory", "MemoryItem"),
            ("app.models.memory", "RetrievalContext"),
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
        self._projects: dict[str, NovelProject] = {}

    @staticmethod
    def _config(session_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": session_id}}

    def _get_state(self, session_id: str) -> NovelState:
        snapshot = self._graph.get_state(self._config(session_id))
        return cast(NovelState, dict(snapshot.values or {}))

    def _ensure_project(
        self,
        project_id: str | None,
        *,
        title: str | None = None,
        global_worldview: str | None = None,
    ) -> NovelProject:
        active_project_id = project_id or "default"
        project = self._projects.get(active_project_id)
        if project is None:
            project = NovelProject(
                project_id=active_project_id,
                title=title or "未命名作品",
                global_worldview=global_worldview or "",
            )
            self._projects[active_project_id] = project
        else:
            if title:
                project.title = title
            if global_worldview:
                project.global_worldview = global_worldview
        return project

    @staticmethod
    def _word_count(text: str) -> int:
        return len("".join(str(text or "").split()))

    @staticmethod
    def _chapter_summary(state: NovelState) -> str:
        chapter_number = state.get("current_chapter_number", 1)
        lore_updates = state.get("extracted_lore_updates", {})
        candidate_keys = [
            f"chapter_{chapter_number}_summary",
            f"chapter{chapter_number}_summary",
            f"chapter-{chapter_number}-summary",
            "chapter_summary",
            "summary",
        ]
        lowered = {key.lower(): value for key, value in lore_updates.items()}
        for key in candidate_keys:
            summary = lowered.get(key.lower())
            if summary:
                return summary

        draft = state.get("current_draft")
        if draft and draft.content:
            compact = " ".join(draft.content.split())
            return compact[:220]
        return ""

    @staticmethod
    def _record_status(state: NovelState) -> str:
        stage = state.get("current_stage")
        draft = state.get("current_draft")
        if stage == "completed":
            return "completed"
        if stage == "failed":
            return "failed"
        if draft and draft.status == "needs_revision":
            return "needs_revision"
        if draft and draft.status == "reviewed":
            return "reviewed"
        if draft:
            return "drafted"
        return "planned"

    def _upsert_chapter_record(self, project: NovelProject, state: NovelState) -> None:
        chapter_number = state.get("current_chapter_number", project.current_chapter_number)
        draft = state.get("current_draft")
        existing = next(
            (chapter for chapter in project.chapters if chapter.chapter_number == chapter_number),
            None,
        )
        record = existing or ChapterRecord(chapter_number=chapter_number)
        record.session_id = state.get("session_id")
        record.title = draft.title if draft and draft.title else record.title
        record.status = self._record_status(state)  # type: ignore[assignment]
        record.summary = self._chapter_summary(state) or record.summary
        record.word_count = self._word_count(draft.content) if draft else record.word_count
        record.draft = draft
        record.updated_at = datetime.utcnow()

        if existing is None:
            project.chapters.append(record)
        project.chapters.sort(key=lambda chapter: chapter.chapter_number)
        project.current_chapter_number = chapter_number
        project.latest_session_id = state.get("session_id")
        project.total_word_count = sum(
            chapter.word_count for chapter in project.chapters if chapter.status == "completed"
        )

    def plan_chapter(
        self,
        *,
        global_worldview: str,
        chapter_number: int,
        characters: list[CharacterCard],
        previous_summary: str | None = None,
        user_instruction: str | None = None,
        session_id: str | None = None,
        project_id: str | None = None,
        project_title: str | None = None,
    ) -> tuple[str, NovelState]:
        """启动章节规划，并在 Writer 前返回暂停状态。"""

        active_session_id = session_id or uuid4().hex
        project = self._ensure_project(
            project_id,
            title=project_title,
            global_worldview=global_worldview,
        )
        initial_state: NovelState = {
            "session_id": active_session_id,
            "project_id": project.project_id,
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
        state = self._get_state(active_session_id)
        self._upsert_chapter_record(project, state)
        return active_session_id, state

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
        state = self._get_state(session_id)
        self._upsert_chapter_record(self._ensure_project(state.get("project_id")), state)
        return state

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
        state = self._get_state(session_id)
        self._upsert_chapter_record(self._ensure_project(state.get("project_id")), state)
        return state

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
        state = self._get_state(session_id)
        self._upsert_chapter_record(self._ensure_project(state.get("project_id")), state)
        return state

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
        state = self._get_state(session_id)
        if state.get("current_stage") == "completed":
            try:
                memory_store.add_items(
                    state.get("project_id") or "default",
                    build_memory_items_from_state(state),
                )
            except Exception as exc:  # noqa: BLE001 - 长期记忆失败不应回滚已接受章节。
                memory_error = f"长期记忆写入失败，章节已完成但未更新 RAG 记忆库：{exc}"
                self._graph.update_state(
                    self._config(session_id),
                    {"error_message": memory_error},
                    as_node="librarian",
                )
                state = self._get_state(session_id)
        self._upsert_chapter_record(self._ensure_project(state.get("project_id")), state)
        return state

    def get_state(self, session_id: str) -> NovelState:
        """读取会话状态，供调试接口使用。"""

        state = self._get_state(session_id)
        if not state:
            raise KeyError(f"未找到会话: {session_id}")
        return state

    def get_project(self, project_id: str | None = None) -> NovelProject:
        """读取作品级目录，供前端展示章节列表。"""

        return self._ensure_project(project_id)

    def plan_next_chapter(
        self,
        *,
        project_id: str | None = None,
        session_id: str | None = None,
        user_instruction: str | None = None,
        characters: list[CharacterCard] | None = None,
    ) -> tuple[str, NovelState]:
        """基于作品目录和上一章摘要继续规划下一章。"""

        project = self._ensure_project(project_id)
        if not project.global_worldview:
            raise ValueError("作品还没有世界观设定，请先规划第一章。")

        last_completed = next(
            (chapter for chapter in reversed(project.chapters) if chapter.status == "completed"),
            None,
        )
        latest_chapter = project.chapters[-1] if project.chapters else None
        previous_chapter = last_completed or latest_chapter
        next_number = (previous_chapter.chapter_number + 1) if previous_chapter else 1
        previous_summary = previous_chapter.summary if previous_chapter else ""

        return self.plan_chapter(
            project_id=project.project_id,
            global_worldview=project.global_worldview,
            chapter_number=next_number,
            previous_summary=previous_summary,
            user_instruction=user_instruction,
            characters=characters or [],
            session_id=session_id,
        )


novel_workflow_service = NovelWorkflowService()
