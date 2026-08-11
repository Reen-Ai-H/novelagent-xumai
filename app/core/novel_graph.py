"""LangGraph 小说工作流编排。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph

from app.core.memory import memory_store
from app.core.project_store import ProjectStore, project_store as default_project_store
from app.core.retriever import build_memory_items_from_state
from app.agents.novel_nodes import (
    librarian_agent,
    planner_agent,
    reviewer_agent,
    writer_agent,
)
from app.models import (
    BatchChapterResult,
    BatchTaskRecord,
    ChapterDraft,
    ChapterPlan,
    ChapterRecord,
    CharacterCard,
    FullNovelPlan,
    NextChapterInputSnapshot,
    NovelProject,
    NovelState,
    PlotBeat,
    VolumePlan,
)


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

    def __init__(self, *, store: ProjectStore = default_project_store) -> None:
        self._graph = build_novel_graph()
        self._project_store = store
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
            project = self._project_store.load_project(active_project_id)
            if project is None:
                project = NovelProject(
                    project_id=active_project_id,
                    title=title or "未命名作品",
                    global_worldview=global_worldview or "",
                )
            self._projects[active_project_id] = project
        if title:
            project.title = title
        if global_worldview:
            project.global_worldview = global_worldview
        return project

    def _save_project(self, project: NovelProject) -> NovelProject:
        project.updated_at = datetime.now(timezone.utc)
        saved_project = self._project_store.save_project(project)
        self._projects[saved_project.project_id] = saved_project
        return saved_project

    def create_project(
        self,
        *,
        title: str,
        project_id: str | None = None,
        project_brief: str | None = None,
        global_worldview: str = "",
        full_plan: FullNovelPlan | None = None,
        volumes: list[VolumePlan] | None = None,
        chapter_plans: list[ChapterPlan] | None = None,
    ) -> NovelProject:
        """创建新作品，并立即持久化。"""

        active_project_id = project_id or uuid4().hex
        existing = self._project_store.load_project(active_project_id)
        if existing is not None:
            raise ValueError(f"作品已存在: {active_project_id}")

        project = NovelProject(
            project_id=active_project_id,
            title=title,
            project_brief=project_brief,
            global_worldview=global_worldview,
            full_plan=full_plan,
            volumes=volumes or [],
            chapter_plans=chapter_plans or [],
        )
        return self._save_project(project)

    def list_projects(self) -> list[NovelProject]:
        """读取全部已持久化作品，并同步内存缓存。"""

        projects = self._project_store.list_projects()
        for project in projects:
            self._projects[project.project_id] = project
        return projects

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
        plot_beats = state.get("current_plot_beats", [])
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
        record.quality_score = draft.quality_score if draft else None
        record.review_feedback = state.get("review_feedback", [])
        if record.status in {"reviewed", "approved", "completed"}:
            record.review_status = "passed"
        elif record.status == "needs_revision":
            record.review_status = "needs_revision"
        elif record.status == "drafted":
            record.review_status = "pending"
        else:
            record.review_status = None
        record.can_accept = record.status in {"reviewed", "needs_revision", "approved"}
        record.can_revise = record.status == "needs_revision"
        record.updated_at = datetime.now(timezone.utc)

        if existing is None:
            project.chapters.append(record)
        project.chapters.sort(key=lambda chapter: chapter.chapter_number)
        self._upsert_chapter_plan_from_state(project, state)
        project.current_chapter_number = chapter_number
        project.latest_edited_chapter_number = chapter_number
        project.latest_session_id = state.get("session_id")
        project.total_word_count = sum(
            chapter.word_count for chapter in project.chapters if chapter.status == "completed"
        )
        if plot_beats:
            project.next_chapter_input_snapshot = None
        self._save_project(project)

    def _upsert_chapter_plan_from_state(self, project: NovelProject, state: NovelState) -> None:
        chapter_number = state.get("current_chapter_number", project.current_chapter_number)
        plot_beats = state.get("current_plot_beats", [])
        if not plot_beats:
            return

        existing = next(
            (plan for plan in project.chapter_plans if plan.chapter_number == chapter_number),
            None,
        )
        summary = "；".join(beat.summary for beat in sorted(plot_beats, key=lambda beat: beat.order))
        plan = existing or ChapterPlan(chapter_number=chapter_number)
        plan.summary = summary or plan.summary
        plan.plot_beats = plot_beats
        plan.updated_at = datetime.now(timezone.utc)
        if existing is None:
            project.chapter_plans.append(plan)
        project.chapter_plans.sort(key=lambda plan_item: plan_item.chapter_number)

    def _sync_project_codex_from_state(self, project: NovelProject, state: NovelState) -> None:
        """章节被接受后，把 Librarian 产物同步到作品级人物/设定索引。"""

        merged_lore = {
            **project.lore_codex,
            **{
                key: str(value)
                for key, value in state.get("global_lore", {}).items()
                if str(value).strip()
            },
            **{
                key: str(value)
                for key, value in state.get("extracted_lore_updates", {}).items()
                if str(value).strip()
            },
        }
        project.lore_codex = dict(sorted(merged_lore.items()))

        characters_by_name = {character.name: character for character in project.character_codex}
        for character in state.get("character_graph", {}).values():
            if isinstance(character, CharacterCard):
                characters_by_name[character.name] = character
        for character in state.get("extracted_character_updates", {}).values():
            if isinstance(character, CharacterCard):
                characters_by_name[character.name] = character
        project.character_codex = [
            characters_by_name[name]
            for name in sorted(characters_by_name)
        ]

    @staticmethod
    def _sync_project_codex_from_state(project: NovelProject, state: NovelState) -> None:
        """把章节状态中的人物与设定增量沉淀到作品级 codex。"""

        lore_updates = {
            **state.get("global_lore", {}),
            **state.get("extracted_lore_updates", {}),
        }
        for key, value in lore_updates.items():
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            project.lore_codex[key] = text

        characters_by_name = {character.name: character for character in project.character_codex}
        character_sources = [
            *state.get("character_graph", {}).values(),
            *state.get("extracted_character_updates", {}).values(),
        ]
        for character in character_sources:
            if isinstance(character, CharacterCard):
                characters_by_name[character.name] = character
        project.character_codex = sorted(
            characters_by_name.values(),
            key=lambda character: character.name,
        )

    def _previous_chapter_for_next(self, project: NovelProject) -> ChapterRecord | None:
        return next(
            (chapter for chapter in reversed(project.chapters) if chapter.status == "completed"),
            None,
        )

    def _previous_completed_summary(self, project: NovelProject) -> str:
        previous_chapter = self._previous_chapter_for_next(project)
        return previous_chapter.summary if previous_chapter else ""

    @staticmethod
    def _last_chapter_hook(state: NovelState | None, previous_chapter: ChapterRecord | None) -> str:
        if state:
            lore_updates = state.get("extracted_lore_updates", {})
            for key, value in lore_updates.items():
                lowered = key.lower()
                if any(token in lowered for token in ("hook", "cliffhanger", "ending", "结尾", "钩子", "悬念")):
                    if str(value).strip():
                        return str(value).strip()

            draft = state.get("current_draft")
            if draft and draft.content.strip():
                paragraphs = [part.strip() for part in draft.content.splitlines() if part.strip()]
                if paragraphs:
                    return paragraphs[-1][:220]

        if previous_chapter and previous_chapter.draft and previous_chapter.draft.plot_beats:
            last_beat = sorted(
                previous_chapter.draft.plot_beats,
                key=lambda beat: beat.order,
            )[-1]
            return last_beat.expected_outcome or last_beat.summary
        return ""

    @staticmethod
    def _unresolved_foreshadowing(state: NovelState | None) -> list[str]:
        if not state:
            return []

        foreshadowing: list[str] = []
        for key, value in state.get("extracted_lore_updates", {}).items():
            lowered = key.lower()
            if any(token in lowered for token in ("foreshadow", "clue", "伏笔", "线索", "悬念")):
                text = str(value).strip()
                if text:
                    foreshadowing.append(text)
        return list(dict.fromkeys(foreshadowing))

    @staticmethod
    def _confirmed_worldview(project: NovelProject, state: NovelState | None) -> str:
        if not state:
            if not project.lore_codex:
                return project.global_worldview
            lore_lines = [
                f"{key}: {value}"
                for key, value in sorted(project.lore_codex.items())
                if str(value).strip()
            ]
            return "\n".join([project.global_worldview, *lore_lines])

        lore_lines = []
        for key, value in state.get("global_lore", {}).items():
            text = str(value).strip()
            lowered = key.lower()
            if not text or (("summary" in lowered or "摘要" in key) and "chapter" in lowered):
                continue
            lore_lines.append(f"{key}: {text}")

        if not lore_lines:
            return state.get("global_worldview") or project.global_worldview
        return "\n".join([state.get("global_worldview") or project.global_worldview, *lore_lines])

    @staticmethod
    def _recommended_next_directions(
        *,
        chapter_plan: ChapterPlan | None,
        hook: str,
        unresolved_foreshadowing: list[str],
        project: NovelProject,
    ) -> list[str]:
        directions: list[str] = []
        if chapter_plan and chapter_plan.summary:
            directions.append(f"执行既定章节规划：{chapter_plan.summary}")
        if hook:
            directions.append(f"承接上一章结尾钩子：{hook}")
        directions.extend(f"推进未解决伏笔：{item}" for item in unresolved_foreshadowing[:3])
        if project.full_plan and project.full_plan.core_conflict:
            directions.append(f"继续压强全文核心冲突：{project.full_plan.core_conflict}")
        if not directions:
            directions.append("承接前文摘要，推进主线目标，并在章末留下可延展的钩子。")
        return directions

    def _build_next_chapter_seed(
        self,
        project: NovelProject,
        *,
        user_instruction: str | None = None,
        characters: list[CharacterCard] | None = None,
        state: NovelState | None = None,
    ) -> NextChapterInputSnapshot:
        previous_chapter = self._previous_chapter_for_next(project)
        next_number = (previous_chapter.chapter_number + 1) if previous_chapter else 1
        chapter_plan = next(
            (plan for plan in project.chapter_plans if plan.chapter_number == next_number),
            None,
        )
        previous_summary = previous_chapter.summary if previous_chapter else ""
        if chapter_plan and chapter_plan.summary:
            previous_summary = "\n\n".join(
                part for part in [previous_summary, f"下一章既定规划：{chapter_plan.summary}"] if part
            )

        character_state = characters or project.character_codex
        if state:
            character_state = [
                character
                for character in state.get("character_graph", {}).values()
                if isinstance(character, CharacterCard)
            ] or character_state

        hook = self._last_chapter_hook(state, previous_chapter)
        unresolved_foreshadowing = self._unresolved_foreshadowing(state)
        confirmed_worldview = self._confirmed_worldview(project, state)

        return NextChapterInputSnapshot(
            project_id=project.project_id,
            chapter_number=next_number,
            global_worldview=project.global_worldview,
            confirmed_worldview=confirmed_worldview,
            previous_summary=previous_summary,
            current_character_state=character_state,
            unresolved_foreshadowing=unresolved_foreshadowing,
            last_chapter_hook=hook,
            recommended_next_directions=self._recommended_next_directions(
                chapter_plan=chapter_plan,
                hook=hook,
                unresolved_foreshadowing=unresolved_foreshadowing,
                project=project,
            ),
            user_instruction=user_instruction,
            characters=character_state,
            source_chapter_number=previous_chapter.chapter_number if previous_chapter else None,
            chapter_plan=chapter_plan,
        )

    def _save_next_chapter_seed(
        self,
        project: NovelProject,
        *,
        user_instruction: str | None = None,
        characters: list[CharacterCard] | None = None,
        state: NovelState | None = None,
    ) -> NextChapterInputSnapshot:
        snapshot = self._build_next_chapter_seed(
            project,
            user_instruction=user_instruction,
            characters=characters,
            state=state,
        )
        project.next_chapter_input_snapshot = snapshot
        self._save_project(project)
        return snapshot

    def prepare_next_chapter(
        self,
        *,
        project_id: str,
        user_instruction: str | None = None,
        characters: list[CharacterCard] | None = None,
    ) -> NextChapterInputSnapshot:
        """准备下一章输入快照，不触发 Planner。"""

        project = self._ensure_project(project_id)
        if not project.global_worldview:
            raise ValueError("作品还没有世界观设定，请先规划第一章。")

        return self._save_next_chapter_seed(
            project,
            user_instruction=user_instruction,
            characters=characters,
        )

    def update_full_plan(
        self,
        *,
        project_id: str,
        full_plan: FullNovelPlan,
        volumes: list[VolumePlan] | None = None,
        chapter_plans: list[ChapterPlan] | None = None,
    ) -> NovelProject:
        """人工保存全文规划、分卷规划和章节规划。"""

        project = self._ensure_project(project_id)
        project.full_plan = full_plan.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        if volumes is not None:
            project.volumes = sorted(volumes, key=lambda volume: volume.volume_number)
        if chapter_plans is not None:
            project.chapter_plans = sorted(
                chapter_plans,
                key=lambda chapter_plan: chapter_plan.chapter_number,
            )
        return self._save_project(project)

    def generate_full_plan(
        self,
        *,
        project_id: str,
        full_plan: FullNovelPlan | None = None,
        volumes: list[VolumePlan] | None = None,
        chapter_plans: list[ChapterPlan] | None = None,
        target_chapter_count: int | None = None,
    ) -> NovelProject:
        """生成或更新全文规划的稳定 API 入口。

        当前实现优先保存请求提供的结构化规划；未提供时基于作品信息生成可编辑骨架。
        """

        project = self._ensure_project(project_id)
        generated_full_plan = full_plan or FullNovelPlan(
            premise=project.title,
            core_conflict=project.global_worldview[:240],
            target_chapter_count=target_chapter_count,
            notes=["自动生成的全文规划骨架，请人工补充主线、卷纲和章节目标。"],
        )
        generated_volumes = volumes
        if generated_volumes is None and not project.volumes:
            generated_volumes = [
                VolumePlan(
                    volume_number=1,
                    title="第一卷",
                    summary="开篇建立世界观、主角目标和核心冲突。",
                    chapter_start=1,
                    chapter_end=target_chapter_count,
                )
            ]
        generated_chapter_plans = chapter_plans
        if generated_chapter_plans is None and target_chapter_count:
            generated_chapter_plans = [
                ChapterPlan(
                    chapter_number=number,
                    volume_number=1,
                    summary=f"第 {number} 章规划待细化。",
                )
                for number in range(1, target_chapter_count + 1)
            ]
        return self.update_full_plan(
            project_id=project.project_id,
            full_plan=generated_full_plan,
            volumes=generated_volumes,
            chapter_plans=generated_chapter_plans,
        )

    def get_chapter(self, *, project_id: str, chapter_number: int) -> ChapterRecord:
        """读取指定章节记录。"""

        project = self._ensure_project(project_id)
        chapter = next(
            (record for record in project.chapters if record.chapter_number == chapter_number),
            None,
        )
        if chapter is None:
            raise KeyError(f"未找到章节: {chapter_number}")
        return chapter

    @staticmethod
    def _validate_batch_chapter_range(start_chapter: int, end_chapter: int) -> list[int]:
        if end_chapter < start_chapter:
            raise ValueError("end_chapter 必须大于等于 start_chapter")
        chapter_numbers = list(range(start_chapter, end_chapter + 1))
        if len(chapter_numbers) < 3 or len(chapter_numbers) > 10:
            raise ValueError("多章节规划/生成一次只支持 3-10 章。")
        return chapter_numbers

    @staticmethod
    def _chapter_conflict_type(chapter: ChapterRecord | None) -> str | None:
        if chapter is None:
            return None
        if chapter.draft and chapter.draft.content.strip():
            return "existing_draft"
        if chapter.draft:
            return "existing_empty_draft"
        if chapter.status != "planned":
            return "existing_chapter"
        return None

    def existing_chapter_conflicts(
        self,
        *,
        project_id: str,
        start_chapter: int,
        end_chapter: int,
    ) -> list[dict[str, str | int | None]]:
        """列出批量生成范围内会被覆盖的已有章节。"""

        project = self._ensure_project(project_id)
        chapter_numbers = self._validate_batch_chapter_range(start_chapter, end_chapter)
        chapters_by_number = {chapter.chapter_number: chapter for chapter in project.chapters}
        conflicts: list[dict[str, str | int | None]] = []
        for chapter_number in chapter_numbers:
            chapter = chapters_by_number.get(chapter_number)
            conflict_type = self._chapter_conflict_type(chapter)
            if chapter is None or conflict_type is None:
                continue
            conflicts.append(
                {
                    "chapter_number": chapter_number,
                    "session_id": chapter.session_id,
                    "status": chapter.status,
                    "draft_status": chapter.draft.status if chapter.draft else None,
                    "conflict_type": conflict_type,
                    "message": f"第 {chapter_number} 章已有内容，策略确认前不会覆盖。",
                }
            )
        return conflicts

    @staticmethod
    def _chapter_result(
        *,
        chapter_number: int,
        chapter: ChapterRecord | None,
        status: str | None = None,
        conflict_type: str | None = None,
    ) -> BatchChapterResult:
        chapter_status = chapter.status if chapter else None
        draft_status = chapter.draft.status if chapter and chapter.draft else None
        result_status = status
        if result_status is None:
            if conflict_type:
                result_status = "conflict"
            elif chapter_status == "planned":
                result_status = "planned"
            elif chapter_status in {"reviewed", "needs_revision", "approved", "completed"}:
                result_status = "reviewed"
            elif chapter_status == "drafted":
                result_status = "generated"
            elif chapter_status == "failed":
                result_status = "failed"
            else:
                result_status = "pending"

        review_status = None
        if chapter_status in {"reviewed", "approved", "completed"}:
            review_status = "passed"
        elif chapter_status == "needs_revision":
            review_status = "needs_revision"
        elif chapter_status == "drafted":
            review_status = "pending"

        return BatchChapterResult(
            chapter_number=chapter_number,
            session_id=chapter.session_id if chapter else None,
            status=result_status,  # type: ignore[arg-type]
            draft_status=draft_status,
            review_status=chapter.review_status if chapter and chapter.review_status else review_status,
            can_review=chapter_status == "drafted",
            can_accept=chapter.can_accept if chapter else False,
            can_revise=chapter.can_revise if chapter else False,
            conflict_type=conflict_type,
        )

    def _batch_results_for_project(
        self,
        project: NovelProject,
        chapter_numbers: list[int],
        *,
        skipped_conflicts: dict[int, str] | None = None,
    ) -> list[BatchChapterResult]:
        chapters_by_number = {chapter.chapter_number: chapter for chapter in project.chapters}
        skipped_conflicts = skipped_conflicts or {}
        return [
            self._chapter_result(
                chapter_number=chapter_number,
                chapter=chapters_by_number.get(chapter_number),
                status="skipped" if chapter_number in skipped_conflicts else None,
                conflict_type=skipped_conflicts.get(chapter_number),
            )
            for chapter_number in chapter_numbers
        ]

    @staticmethod
    def _draft_comparison_summary(
        existing_draft: ChapterDraft | None,
        candidate_draft: ChapterDraft | None,
    ) -> str:
        if existing_draft is None or candidate_draft is None:
            return "缺少原稿或候选稿，无法生成完整对比。"
        existing_words = len("".join(existing_draft.content.split()))
        candidate_words = len("".join(candidate_draft.content.split()))
        return (
            f"原稿《{existing_draft.title or '未命名'}》约 {existing_words} 字；"
            f"候选稿《{candidate_draft.title or '未命名'}》约 {candidate_words} 字。"
        )

    def _stage_candidate_draft_for_compare(
        self,
        *,
        project: NovelProject,
        chapter_number: int,
        user_instruction: str | None,
        characters: list[CharacterCard],
    ) -> None:
        chapter = next(
            (record for record in project.chapters if record.chapter_number == chapter_number),
            None,
        )
        if chapter is None or chapter.draft is None:
            return

        chapter_plan = next(
            (plan for plan in project.chapter_plans if plan.chapter_number == chapter_number),
            None,
        )
        plot_beats = chapter.draft.plot_beats or (chapter_plan.plot_beats if chapter_plan else [])
        if not plot_beats:
            plot_beats = [
                PlotBeat(
                    order=1,
                    summary=chapter.summary or (chapter_plan.summary if chapter_plan else "重新生成本章。"),
                )
            ]

        state: NovelState = {
            "session_id": uuid4().hex,
            "project_id": project.project_id,
            "global_worldview": project.global_worldview,
            "global_lore": {
                "previous_summary": self._previous_completed_summary(project),
            },
            "current_chapter_number": chapter_number,
            "current_stage": "writing",
            "current_plot_beats": plot_beats,
            "current_draft": None,
            "character_graph": {character.name: character for character in characters},
            "retrieved_context": [],
            "temporary_context": {
                "batch_generation": "true",
                "compare_candidate": "true",
            },
            "human_feedback": user_instruction,
            "human_approved": True,
            "extracted_lore_updates": {},
            "extracted_character_updates": {},
            "review_feedback": [],
            "error_message": None,
        }
        writer_update = writer_agent(state)
        candidate_draft = writer_update.get("current_draft")
        if isinstance(candidate_draft, ChapterDraft):
            chapter.candidate_draft = candidate_draft
            chapter.draft_comparison_summary = self._draft_comparison_summary(
                chapter.draft,
                candidate_draft,
            )
            chapter.updated_at = datetime.now(timezone.utc)

    def _merge_temporary_context(
        self,
        session_id: str,
        temporary_context: dict[str, str],
    ) -> None:
        if not temporary_context:
            return

        state = self._get_state(session_id)
        if not state:
            return

        merged_context = {
            **state.get("temporary_context", {}),
            **temporary_context,
        }
        stage = state.get("current_stage")
        as_node = "planner"
        if stage in {"awaiting_review", "reviewing"}:
            as_node = "writer"
        elif stage in {"awaiting_chapter_acceptance", "awaiting_revision_decision"}:
            as_node = "reviewer"
        self._graph.update_state(
            self._config(session_id),
            {"temporary_context": merged_context},
            as_node=as_node,
        )

    def _temporary_context_from_state(self, state: NovelState) -> dict[str, str]:
        draft = state.get("current_draft")
        project = self._ensure_project(state.get("project_id"))
        summary = self._chapter_summary(state)
        hook = self._last_chapter_hook(state, None)
        character_lines: list[str] = []
        for character in state.get("character_graph", {}).values():
            if not isinstance(character, CharacterCard):
                continue
            character_lines.append(
                "；".join(
                    part
                    for part in [
                        character.name,
                        character.current_location or "",
                        character.current_psychological_state,
                        character.current_physical_state,
                        character.motivation or "",
                    ]
                    if part
                )
            )

        content_tail = ""
        if draft and draft.content.strip():
            compact = " ".join(draft.content.split())
            content_tail = compact[-320:]
        chapter_number = state.get("current_chapter_number", "")
        current_summary = summary or content_tail
        prior_context = state.get("temporary_context", {})
        prior_summaries = [
            line
            for line in prior_context.get("recent_draft_summaries", "").splitlines()
            if line.strip()
        ]
        if current_summary:
            prior_summaries.append(f"第 {chapter_number} 章：{current_summary}")
        recent_summaries = "\n".join(prior_summaries[-6:])

        return {
            "batch_generation": "true",
            "previous_chapter_number": str(chapter_number),
            "previous_draft_summary": current_summary,
            "previous_hook": hook,
            "previous_character_state": "\n".join(character_lines),
            "recent_draft_summaries": recent_summaries,
            "batch_context_instruction": "避免重复近期章节的场景结构、冲突推进和结尾钩子，尤其要检查非相邻章节是否相似。",
            "project_id": project.project_id,
        }

    def batch_plan_chapters(
        self,
        *,
        project_id: str,
        start_chapter: int,
        end_chapter: int,
        user_instruction: str | None = None,
        characters: list[CharacterCard] | None = None,
    ) -> BatchTaskRecord:
        """同步批量规划多章，并记录任务状态。"""

        project = self._ensure_project(project_id)
        chapter_numbers = self._validate_batch_chapter_range(start_chapter, end_chapter)
        task = BatchTaskRecord(
            kind="plan",
            status="running",
            chapter_numbers=chapter_numbers,
            message="批量规划进行中。",
        )
        project.batch_tasks.append(task)
        self._save_project(project)

        try:
            session_ids: dict[int, str] = {}
            previous_summary = self._previous_completed_summary(project)
            for chapter_number in task.chapter_numbers:
                existing_plan = next(
                    (
                        plan
                        for plan in project.chapter_plans
                        if plan.chapter_number == chapter_number and plan.summary
                    ),
                    None,
                )
                instruction_parts = [
                    user_instruction,
                    existing_plan.summary if existing_plan else None,
                ]
                session_id, state = self.plan_chapter(
                    project_id=project.project_id,
                    global_worldview=project.global_worldview,
                    chapter_number=chapter_number,
                    previous_summary=previous_summary,
                    user_instruction="\n\n".join(part for part in instruction_parts if part),
                    characters=characters or [],
                )
                session_ids[chapter_number] = session_id
                chapter_summary = self._chapter_summary(state)
                if chapter_summary:
                    previous_summary = chapter_summary

            project = self._ensure_project(project.project_id)
            task = self._get_batch_task(project, task.task_id)
            task.status = "completed"
            task.session_ids = session_ids
            task.chapter_results = self._batch_results_for_project(project, task.chapter_numbers)
            task.message = "批量章节规划已完成，等待逐章审核或批量生成草稿。"
        except Exception as exc:  # noqa: BLE001 - 任务状态需要落盘后再向 API 抛错。
            project = self._ensure_project(project.project_id)
            task = self._get_batch_task(project, task.task_id)
            task.status = "failed"
            task.error_message = str(exc)
            task.message = "批量章节规划失败。"
            raise
        finally:
            task.updated_at = datetime.now(timezone.utc)
            self._save_project(project)

        return task

    def batch_generate_chapters(
        self,
        *,
        project_id: str,
        start_chapter: int,
        end_chapter: int,
        user_instruction: str | None = None,
        characters: list[CharacterCard] | None = None,
        overwrite_policy: str = "block",
    ) -> BatchTaskRecord:
        """同步批量生成多章草稿。"""

        project = self._ensure_project(project_id)
        chapter_numbers = self._validate_batch_chapter_range(start_chapter, end_chapter)
        conflicts = self.existing_chapter_conflicts(
            project_id=project.project_id,
            start_chapter=start_chapter,
            end_chapter=end_chapter,
        )
        if conflicts and overwrite_policy == "block":
            conflict_chapters = ", ".join(str(conflict["chapter_number"]) for conflict in conflicts)
            raise ValueError(f"批量生成会覆盖已有章节：{conflict_chapters}。请先选择 compare、replace 或 keep_existing。")

        task = BatchTaskRecord(
            kind="generate",
            status="running",
            chapter_numbers=chapter_numbers,
            overwrite_policy=overwrite_policy,
            message="批量草稿生成进行中。",
        )
        project.batch_tasks.append(task)
        self._save_project(project)

        try:
            session_ids: dict[int, str] = {}
            pending_acceptance: list[int] = []
            needs_revision: list[int] = []
            skipped_conflicts = {
                int(conflict["chapter_number"]): str(conflict["conflict_type"])
                for conflict in conflicts
                if conflict["chapter_number"] is not None
            }
            if conflicts and overwrite_policy == "compare":
                for conflict in conflicts:
                    self._stage_candidate_draft_for_compare(
                        project=project,
                        chapter_number=int(conflict["chapter_number"]),
                        user_instruction=user_instruction,
                        characters=characters or [],
                    )
                task.status = "partial"
                task.chapter_results = self._batch_results_for_project(
                    project,
                    task.chapter_numbers,
                    skipped_conflicts=skipped_conflicts,
                )
                task.message = "检测到已有章节，已生成候选稿对比；未覆盖原章节。"
                return task

            temporary_context: dict[str, str] = {
                "batch_generation": "true",
            }
            for chapter_number in task.chapter_numbers:
                if chapter_number in skipped_conflicts and overwrite_policy == "keep_existing":
                    continue
                session_id = self._ensure_planned_session(
                    project_id=project.project_id,
                    chapter_number=chapter_number,
                    user_instruction=user_instruction,
                    characters=characters or [],
                    temporary_context=temporary_context,
                    force_new_session=overwrite_policy == "replace",
                )
                self._merge_temporary_context(session_id, temporary_context)
                state = self._get_state(session_id)
                if state.get("current_stage") == "awaiting_human_review":
                    state = self.approve_plan(
                        session_id=session_id,
                        plot_beats=state.get("current_plot_beats", []),
                        human_feedback=user_instruction,
                    )
                if state.get("current_stage") == "awaiting_review":
                    state = self.review_draft(session_id=session_id)
                if state.get("current_stage") == "awaiting_chapter_acceptance":
                    pending_acceptance.append(chapter_number)
                elif state.get("current_stage") == "awaiting_revision_decision":
                    needs_revision.append(chapter_number)
                temporary_context = self._temporary_context_from_state(state)
                session_ids[chapter_number] = session_id

            project = self._ensure_project(project.project_id)
            task = self._get_batch_task(project, task.task_id)
            task.status = "completed"
            task.session_ids = session_ids
            task.pending_acceptance_chapter_numbers = pending_acceptance
            task.needs_revision_chapter_numbers = needs_revision
            task.chapter_results = self._batch_results_for_project(
                project,
                task.chapter_numbers,
                skipped_conflicts=skipped_conflicts if overwrite_policy == "keep_existing" else None,
            )
            task.message = "批量生成与审查已完成，请逐章接受或打回修订。"
        except Exception as exc:  # noqa: BLE001
            project = self._ensure_project(project.project_id)
            task = self._get_batch_task(project, task.task_id)
            task.status = "failed"
            task.error_message = str(exc)
            task.message = "批量草稿生成失败。"
            raise
        finally:
            task.updated_at = datetime.now(timezone.utc)
            self._save_project(project)

        return task

    @staticmethod
    def _get_batch_task(project: NovelProject, task_id: str) -> BatchTaskRecord:
        task = next((item for item in project.batch_tasks if item.task_id == task_id), None)
        if task is None:
            raise KeyError(f"未找到批量任务: {task_id}")
        return task

    def _ensure_planned_session(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_instruction: str | None,
        characters: list[CharacterCard],
        temporary_context: dict[str, str] | None = None,
        force_new_session: bool = False,
    ) -> str:
        project = self._ensure_project(project_id)
        existing_chapter = next(
            (chapter for chapter in project.chapters if chapter.chapter_number == chapter_number),
            None,
        )
        if not force_new_session and existing_chapter and existing_chapter.session_id:
            state = self._get_state(existing_chapter.session_id)
            if state:
                return existing_chapter.session_id

        existing_plan = next(
            (plan for plan in project.chapter_plans if plan.chapter_number == chapter_number),
            None,
        )
        if existing_plan and existing_plan.plot_beats:
            session_id = uuid4().hex
            previous_summary = self._previous_completed_summary(project)
            state: NovelState = {
                "session_id": session_id,
                "project_id": project.project_id,
                "global_worldview": project.global_worldview,
                "global_lore": {
                    "previous_summary": previous_summary,
                },
                "current_chapter_number": chapter_number,
                "current_stage": "awaiting_human_review",
                "current_plot_beats": existing_plan.plot_beats,
                "current_draft": None,
                "character_graph": {character.name: character for character in characters},
                "retrieved_context": [],
                "temporary_context": temporary_context or {},
                "human_feedback": user_instruction,
                "human_approved": False,
                "extracted_lore_updates": {},
                "extracted_character_updates": {},
                "review_feedback": [],
                "error_message": None,
            }
            self._graph.update_state(self._config(session_id), state, as_node="planner")
            self._upsert_chapter_record(project, state)
            return session_id

        session_id, _ = self.plan_chapter(
            project_id=project.project_id,
            global_worldview=project.global_worldview,
            chapter_number=chapter_number,
            previous_summary=self._previous_completed_summary(project),
            user_instruction=user_instruction,
            characters=characters,
            temporary_context=temporary_context,
        )
        return session_id

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
        temporary_context: dict[str, str] | None = None,
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
            "temporary_context": temporary_context or {},
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
        project = self._ensure_project(state.get("project_id"))
        if state.get("current_stage") == "completed":
            self._sync_project_codex_from_state(project, state)
        self._upsert_chapter_record(project, state)
        if state.get("current_stage") == "completed":
            self._save_next_chapter_seed(project, state=state)
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
        snapshot = project.next_chapter_input_snapshot or self.prepare_next_chapter(
            project_id=project.project_id,
            user_instruction=user_instruction,
            characters=characters,
        )
        next_number = snapshot.chapter_number
        previous_summary = snapshot.previous_summary
        instruction_parts = [
            snapshot.user_instruction,
            f"上一章结尾钩子：{snapshot.last_chapter_hook}" if snapshot.last_chapter_hook else None,
            "未解决伏笔：\n" + "\n".join(
                f"- {item}" for item in snapshot.unresolved_foreshadowing
            )
            if snapshot.unresolved_foreshadowing
            else None,
            "推荐的下一章创作方向：\n" + "\n".join(
                f"- {item}" for item in snapshot.recommended_next_directions
            )
            if snapshot.recommended_next_directions
            else None,
            user_instruction,
        ]

        return self.plan_chapter(
            project_id=project.project_id,
            global_worldview=snapshot.confirmed_worldview or snapshot.global_worldview,
            chapter_number=next_number,
            previous_summary=previous_summary,
            user_instruction="\n\n".join(part for part in instruction_parts if part),
            characters=characters or snapshot.current_character_state or snapshot.characters,
            session_id=session_id,
        )


novel_workflow_service = NovelWorkflowService()
