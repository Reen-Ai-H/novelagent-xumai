"""小说工作流 API Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    BatchChapterResult,
    BatchGenerationRun,
    BatchTaskRecord,
    ChapterDraft,
    ChapterOutline,
    ChapterPlan,
    ChapterRecord,
    CharacterCard,
    FullNovelPlan,
    NextChapterSeed,
    NextChapterInputSnapshot,
    NovelProject,
    PlotBeat,
    RetrievalContext,
    VolumePlan,
    WorkflowStage,
)

_FIELD_CONTRACTS = (
    NextChapterSeed,
    FullNovelPlan,
    ChapterOutline,
    BatchGenerationRun,
)

OverwritePolicy = Literal["block", "compare", "replace", "keep_existing"]


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


class CreateProjectRequest(BaseModel):
    """创建新作品。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: str | None = Field(default=None, description="作品 ID；为空时自动生成")
    title: str = Field(..., min_length=1, description="作品标题")
    project_brief: str | None = Field(default=None, description="作品摘要，供首页卡片展示")
    global_worldview: str = Field(default="", description="作品级世界观")
    full_plan: FullNovelPlan | None = Field(default=None, description="可选全文规划")
    volumes: list[VolumePlan] = Field(default_factory=list, description="可选分卷规划")
    chapter_plans: list[ChapterPlan] = Field(default_factory=list, description="可选章节规划")


class ProjectCard(BaseModel):
    """首页作品卡片数据。"""

    project_id: str = Field(..., description="作品 ID")
    title: str = Field(..., description="作品名")
    project_brief: str = Field(default="", description="作品摘要")
    total_word_count: int = Field(default=0, ge=0, description="总字数")
    chapter_count: int = Field(default=0, ge=0, description="章节数")
    completed_chapter_count: int = Field(default=0, ge=0, description="完成章节数")
    latest_chapter_number: int | None = Field(default=None, ge=1, description="最新章节号")
    latest_chapter_title: str | None = Field(default=None, description="最新章节标题")
    latest_chapter_status: str | None = Field(default=None, description="最新章节状态")
    latest_session_id: str | None = Field(default=None, description="最近会话 ID")
    latest_edited_chapter_number: int | None = Field(default=None, ge=1, description="最近编辑章节")
    suggested_next_chapter_number: int = Field(default=1, ge=1, description="推荐下一章章节号")
    suggested_batch_start_chapter: int = Field(default=1, ge=1, description="推荐批量生成起始章")
    updated_at: datetime = Field(..., description="最近更新时间")
    created_at: datetime = Field(..., description="创建时间")
    has_full_plan: bool = Field(default=False, description="是否已有全文规划")
    has_next_chapter_seed: bool = Field(default=False, description="是否已有下一章预填")

    @classmethod
    def from_project(cls, project: NovelProject) -> "ProjectCard":
        latest_chapter = _latest_chapter(project)
        return cls(
            project_id=project.project_id,
            title=project.title,
            project_brief=_project_brief(project),
            total_word_count=project.total_word_count,
            chapter_count=len(project.chapters),
            completed_chapter_count=sum(
                1 for chapter in project.chapters if chapter.status == "completed"
            ),
            latest_chapter_number=latest_chapter.chapter_number if latest_chapter else None,
            latest_chapter_title=latest_chapter.title if latest_chapter else None,
            latest_chapter_status=latest_chapter.status if latest_chapter else None,
            latest_session_id=project.latest_session_id,
            latest_edited_chapter_number=project.latest_edited_chapter_number,
            suggested_next_chapter_number=_suggested_next_chapter_number(project),
            suggested_batch_start_chapter=_suggested_batch_start_chapter(project),
            updated_at=project.updated_at,
            created_at=project.created_at,
            has_full_plan=project.full_plan is not None,
            has_next_chapter_seed=project.next_chapter_input_snapshot is not None,
        )


class ProjectListResponse(BaseModel):
    """作品列表。"""

    projects: list[ProjectCard] = Field(default_factory=list, description="首页作品卡片列表")


class PrepareNextChapterRequest(BaseModel):
    """准备下一章输入的查询参数。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_instruction: str | None = Field(default=None, description="下一章额外创作要求")
    characters: list[CharacterCard] = Field(default_factory=list, description="预填人物卡片")


class PrepareNextChapterResponse(BaseModel):
    """下一章预填输入。"""

    snapshot: NextChapterInputSnapshot = Field(..., description="下一章输入快照")


class FullPlanRequest(BaseModel):
    """生成或人工保存全文规划。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    full_plan: FullNovelPlan | None = Field(default=None, description="全文规划")
    volumes: list[VolumePlan] | None = Field(default=None, description="分卷规划")
    chapter_plans: list[ChapterPlan] | None = Field(default=None, description="章节规划列表")
    target_chapter_count: int | None = Field(default=None, ge=1, description="自动骨架章节数")


class BatchChapterRequest(BaseModel):
    """多章节同步任务请求。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    start_chapter: int = Field(..., ge=1, description="起始章节")
    end_chapter: int = Field(..., ge=1, description="结束章节")
    user_instruction: str | None = Field(default=None, description="批量任务额外要求")
    characters: list[CharacterCard] = Field(default_factory=list, description="人物卡片")
    overwrite_policy: OverwritePolicy = Field(
        default="block",
        description="已有章节覆盖策略：block/compare/replace/keep_existing",
    )


class ExistingChapterConflict(BaseModel):
    """批量生成前检测到的已有章节冲突。"""

    chapter_number: int = Field(..., ge=1, description="章节号")
    session_id: str | None = Field(default=None, description="已有会话 ID")
    status: str = Field(..., description="已有章节状态")
    draft_status: str | None = Field(default=None, description="已有草稿状态")
    conflict_type: str = Field(..., description="冲突类型")
    message: str = Field(..., description="冲突说明")


class BatchTaskResponse(BaseModel):
    """批量任务状态返回。"""

    task: BatchTaskRecord = Field(..., description="批量任务状态")
    chapter_results: list[BatchChapterResult] = Field(default_factory=list, description="逐章处理状态")
    suggested_next_chapter_number: int = Field(default=1, ge=1, description="推荐下一章章节号")
    suggested_batch_start_chapter: int = Field(default=1, ge=1, description="推荐批量生成起始章")
    existing_chapter_conflicts: list[ExistingChapterConflict] = Field(
        default_factory=list,
        description="本次请求范围内已有章节冲突",
    )

    @classmethod
    def from_project(
        cls,
        *,
        task: BatchTaskRecord,
        project: NovelProject,
        existing_chapter_conflicts: list[ExistingChapterConflict] | None = None,
    ) -> "BatchTaskResponse":
        chapter_results = task.chapter_results or _batch_chapter_results_from_project(
            task=task,
            project=project,
        )
        return cls(
            task=task,
            chapter_results=chapter_results,
            suggested_next_chapter_number=_suggested_next_chapter_number(project),
            suggested_batch_start_chapter=_suggested_batch_start_chapter(project),
            existing_chapter_conflicts=existing_chapter_conflicts or [],
        )


class ProjectCodexResponse(BaseModel):
    """作品级人物与剧情设定聚合。"""

    project_id: str = Field(..., description="作品 ID")
    character_codex: list[CharacterCard] = Field(default_factory=list, description="人物设定集")
    lore_codex: dict[str, str] = Field(default_factory=dict, description="剧情与世界观设定集")
    character_count: int = Field(default=0, ge=0, description="人物设定数量")
    lore_count: int = Field(default=0, ge=0, description="剧情设定数量")

    @classmethod
    def from_project(cls, project: NovelProject) -> "ProjectCodexResponse":
        character_codex = _project_character_codex(project)
        lore_codex = _project_lore_codex(project)
        return cls(
            project_id=project.project_id,
            character_codex=character_codex,
            lore_codex=lore_codex,
            character_count=len(character_codex),
            lore_count=len(lore_codex),
        )


class ChapterRecordResponse(BaseModel):
    """章节预览返回。"""

    chapter: ChapterRecord = Field(..., description="章节记录")


class ChapterPreviewResponse(BaseModel):
    """小说预览页章节读取结果。"""

    project_id: str = Field(..., description="作品 ID")
    chapter_number: int = Field(..., ge=1, description="章节号")
    title: str | None = Field(default=None, description="章节标题")
    status: str = Field(..., description="章节状态；missing 表示尚未生成记录")
    session_id: str | None = Field(default=None, description="关联会话 ID")
    summary: str = Field(default="", description="章节摘要或规划摘要")
    word_count: int = Field(default=0, ge=0, description="章节字数")
    draft: ChapterDraft | None = Field(default=None, description="章节草稿")
    existing_draft: ChapterDraft | None = Field(default=None, description="已有草稿，用于对比")
    candidate_draft: ChapterDraft | None = Field(default=None, description="候选草稿，用于对比")
    draft_comparison_summary: str | None = Field(default=None, description="草稿对比摘要")
    content: str = Field(default="", description="可阅读正文；没有正文时为空字符串")
    has_body: bool = Field(default=False, description="是否有正文")
    can_continue: bool = Field(default=False, description="是否可继续处理")
    can_review: bool = Field(default=False, description="是否可进入审查")
    can_accept: bool = Field(default=False, description="是否可接受章节")
    previous_chapter_number: int | None = Field(default=None, ge=1, description="上一章号")
    next_chapter_number: int | None = Field(default=None, ge=1, description="下一章号")
    chapter: ChapterRecord | None = Field(default=None, description="原始章节记录")
    chapter_plan: ChapterPlan | None = Field(default=None, description="章节规划")
    message: str = Field(..., description="给阅读器展示的状态说明")

    @classmethod
    def from_project(
        cls,
        *,
        project: NovelProject,
        chapter_number: int,
    ) -> "ChapterPreviewResponse":
        chapter = next(
            (item for item in project.chapters if item.chapter_number == chapter_number),
            None,
        )
        chapter_plan = next(
            (item for item in project.chapter_plans if item.chapter_number == chapter_number),
            None,
        )
        known_numbers = sorted(
            {
                *[item.chapter_number for item in project.chapters],
                *[item.chapter_number for item in project.chapter_plans],
            }
        )
        previous_number = next(
            (number for number in reversed(known_numbers) if number < chapter_number),
            None,
        )
        next_number = next(
            (number for number in known_numbers if number > chapter_number),
            None,
        )

        if chapter is None:
            return cls(
                project_id=project.project_id,
                chapter_number=chapter_number,
                title=chapter_plan.title if chapter_plan else None,
                status="missing",
                summary=chapter_plan.summary if chapter_plan else "",
                previous_chapter_number=previous_number,
                next_chapter_number=next_number,
                chapter_plan=chapter_plan,
                can_continue=True,
                message="本章尚未生成正文，可进入章节创作开始处理。",
            )

        content = chapter.draft.content if chapter.draft else ""
        has_body = bool(content.strip())
        return cls(
            project_id=project.project_id,
            chapter_number=chapter.chapter_number,
            title=chapter.title or (chapter.draft.title if chapter.draft else None),
            status=chapter.status,
            session_id=chapter.session_id,
            summary=chapter.summary or (chapter_plan.summary if chapter_plan else ""),
            word_count=chapter.word_count,
            draft=chapter.draft,
            existing_draft=chapter.draft,
            candidate_draft=chapter.candidate_draft,
            draft_comparison_summary=chapter.draft_comparison_summary,
            content=content,
            has_body=has_body,
            can_continue=chapter.status
            in {"planned", "drafted", "reviewed", "needs_revision", "failed"},
            can_review=chapter.status == "drafted",
            can_accept=chapter.status in {"reviewed", "needs_revision", "approved"},
            previous_chapter_number=previous_number,
            next_chapter_number=next_number,
            chapter=chapter,
            chapter_plan=chapter_plan,
            message=_chapter_preview_message(chapter.status, has_body),
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


def _latest_chapter(project: NovelProject) -> ChapterRecord | None:
    if not project.chapters:
        return None
    if project.latest_edited_chapter_number is not None:
        latest_edited = next(
            (
                chapter
                for chapter in project.chapters
                if chapter.chapter_number == project.latest_edited_chapter_number
            ),
            None,
        )
        if latest_edited is not None:
            return latest_edited
    return max(project.chapters, key=lambda chapter: chapter.updated_at)


def _suggested_next_chapter_number(project: NovelProject) -> int:
    if project.next_chapter_input_snapshot:
        return project.next_chapter_input_snapshot.chapter_number
    completed_numbers = [
        chapter.chapter_number for chapter in project.chapters if chapter.status == "completed"
    ]
    if completed_numbers:
        return max(completed_numbers) + 1
    if project.chapters:
        return max(chapter.chapter_number for chapter in project.chapters) + 1
    return 1


def _suggested_batch_start_chapter(project: NovelProject) -> int:
    known_numbers = {
        *[chapter.chapter_number for chapter in project.chapters],
        *[chapter_plan.chapter_number for chapter_plan in project.chapter_plans],
    }
    max_known = max(known_numbers, default=0)
    chapters_by_number = {chapter.chapter_number: chapter for chapter in project.chapters}
    for chapter_number in range(1, max_known + 2):
        chapter = chapters_by_number.get(chapter_number)
        if chapter is None or chapter.draft is None or not chapter.draft.content.strip():
            return chapter_number
    return max_known + 1


def _batch_chapter_results_from_project(
    *,
    task: BatchTaskRecord,
    project: NovelProject,
) -> list[BatchChapterResult]:
    """为旧 batch task 推导只读逐章结果。"""

    chapters_by_number = {chapter.chapter_number: chapter for chapter in project.chapters}
    results: list[BatchChapterResult] = []
    for chapter_number in task.chapter_numbers:
        chapter = chapters_by_number.get(chapter_number)
        chapter_status = chapter.status if chapter else None
        draft_status = chapter.draft.status if chapter and chapter.draft else None
        if chapter_status == "planned":
            status = "planned"
        elif chapter_status == "drafted":
            status = "generated"
        elif chapter_status in {"reviewed", "needs_revision", "approved", "completed"}:
            status = "reviewed"
        elif chapter_status == "failed":
            status = "failed"
        else:
            status = "pending"

        review_status = None
        if chapter_status in {"reviewed", "approved", "completed"}:
            review_status = "passed"
        elif chapter_status == "needs_revision":
            review_status = "needs_revision"
        elif chapter_status == "drafted":
            review_status = "pending"

        results.append(
            BatchChapterResult(
                chapter_number=chapter_number,
                session_id=task.session_ids.get(chapter_number) or (chapter.session_id if chapter else None),
                status=status,  # type: ignore[arg-type]
                draft_status=draft_status,
                review_status=review_status,
                can_review=chapter_status == "drafted",
                can_accept=chapter_status in {"reviewed", "needs_revision", "approved"},
                can_revise=chapter_status == "needs_revision",
                conflict_type=None,
            )
        )
    return results


def _project_character_codex(project: NovelProject) -> list[CharacterCard]:
    characters_by_name = {character.name: character for character in project.character_codex}
    for snapshot in [project.next_chapter_input_snapshot]:
        if snapshot is None:
            continue
        for character in [*snapshot.current_character_state, *snapshot.characters]:
            characters_by_name[character.name] = character
    return sorted(characters_by_name.values(), key=lambda character: character.name)


def _project_lore_codex(project: NovelProject) -> dict[str, str]:
    lore_codex = dict(project.lore_codex)
    if project.full_plan:
        full_plan = project.full_plan
        if full_plan.premise:
            lore_codex.setdefault("full_plan.premise", full_plan.premise)
        if full_plan.core_conflict:
            lore_codex.setdefault("full_plan.core_conflict", full_plan.core_conflict)
        if full_plan.ending_direction:
            lore_codex.setdefault("full_plan.ending_direction", full_plan.ending_direction)
    for chapter in project.chapters:
        if chapter.summary:
            lore_codex.setdefault(
                f"chapter_{chapter.chapter_number}_summary",
                chapter.summary,
            )
    return lore_codex


def _project_brief(project: NovelProject) -> str:
    if project.project_brief:
        return project.project_brief
    if project.full_plan:
        for candidate in (
            project.full_plan.premise,
            project.full_plan.core_conflict,
            project.full_plan.ending_direction,
        ):
            if candidate:
                return candidate
    return project.global_worldview[:160]


def _chapter_preview_message(status: str, has_body: bool) -> str:
    if status == "completed" and has_body:
        return "本章已完成，可直接阅读。"
    if has_body:
        return "本章已有草稿，可预览正文并继续处理。"
    return {
        "planned": "本章已规划，尚未生成正文。",
        "drafted": "本章已生成草稿，但正文为空，请返回章节创作检查。",
        "reviewed": "本章已审查，等待接受或继续处理。",
        "needs_revision": "本章需要修改，请进入章节创作继续处理。",
        "approved": "本章已接受，等待完成归档。",
        "completed": "本章已完成，但暂未保存正文。",
        "failed": "本章处理失败，可进入章节创作重试。",
    }.get(status, "本章暂无可阅读正文。")
