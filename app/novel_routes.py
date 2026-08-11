"""小说共创工作流 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app import entry_routes
from app.core.novel_graph import novel_workflow_service
from schemas.novel import (
    BatchChapterRequest,
    BatchTaskResponse,
    ChapterPreviewResponse,
    ContinueChapterRequest,
    CreateProjectRequest,
    ExistingChapterConflict,
    FullPlanRequest,
    NovelActionRequest,
    NovelApprovalRequest,
    NovelPlanRequest,
    NovelPlanResponse,
    NovelProjectResponse,
    NovelRunResponse,
    PrepareNextChapterRequest,
    PrepareNextChapterResponse,
    ProjectCard,
    ProjectCodexResponse,
    ProjectListResponse,
)


LEGACY_PROJECT_MODE = "legacy"


def _legacy_account(request: Request):
    """所有旧工作流接口共用阶段 1 的 HttpOnly 会话解析。"""

    return entry_routes._current_account(request)


def _authorized_legacy_project(request: Request, project_id: str):
    """只允许已显式关联到当前账户的旧工作流作品。"""

    account = _legacy_account(request)
    link = next(
        (
            item
            for item in account.project_links
            if item.project_id == project_id and item.mode == LEGACY_PROJECT_MODE
        ),
        None,
    )
    if link is None:
        raise HTTPException(status_code=404, detail="未找到属于当前账户的作品")

    project = next(
        (
            item
            for item in novel_workflow_service.list_projects()
            if item.project_id == project_id
        ),
        None,
    )
    if project is None:
        raise HTTPException(status_code=404, detail="作品不存在")
    return project


def _current_legacy_project(request: Request):
    account = _legacy_account(request)
    project_ids = {
        item.project_id
        for item in account.project_links
        if item.mode == LEGACY_PROJECT_MODE
    }
    project = next(
        (
            item
            for item in novel_workflow_service.list_projects()
            if item.project_id in project_ids
        ),
        None,
    )
    if project is None:
        raise HTTPException(status_code=404, detail="当前账户还没有旧工作流作品")
    return project


def _authorized_legacy_session(request: Request, session_id: str):
    _legacy_account(request)
    try:
        state = novel_workflow_service.get_state(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    project_id = state.get("project_id")
    if not project_id:
        raise HTTPException(status_code=404, detail="会话没有有效的作品归属")
    _authorized_legacy_project(request, project_id)
    return state


router = APIRouter(
    prefix="/novel",
    tags=["novel"],
    dependencies=[Depends(_legacy_account)],
)


@router.post("/projects", response_model=NovelProjectResponse)
async def create_project(
    request: CreateProjectRequest,
    http_request: Request,
) -> NovelProjectResponse:
    """创建新书，并持久化作品级数据。"""

    account = _legacy_account(http_request)
    try:
        project = novel_workflow_service.create_project(
            project_id=request.project_id,
            title=request.title,
            project_brief=request.project_brief,
            global_worldview=request.global_worldview,
            full_plan=request.full_plan,
            volumes=request.volumes,
            chapter_plans=request.chapter_plans,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        entry_routes.account_store.link_project(
            account.account_id,
            project.project_id,
            LEGACY_PROJECT_MODE,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return NovelProjectResponse(project=project)


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(request: Request) -> ProjectListResponse:
    """读取本地已保存的项目列表。"""

    account = _legacy_account(request)
    owned_ids = {
        item.project_id
        for item in account.project_links
        if item.mode == LEGACY_PROJECT_MODE
    }
    projects = [
        ProjectCard.from_project(project)
        for project in novel_workflow_service.list_projects()
        if project.project_id in owned_ids
    ]
    return ProjectListResponse(projects=projects)


@router.post("/chapters/plan", response_model=NovelPlanResponse)
async def plan_chapter(
    request: NovelPlanRequest,
    http_request: Request,
) -> NovelPlanResponse:
    """生成章节剧情节点，并在 Writer 前暂停等待人工审核。"""

    session_project_id: str | None = None
    if request.session_id:
        session_state = _authorized_legacy_session(http_request, request.session_id)
        session_project_id = session_state.get("project_id")
    if request.project_id:
        project = _authorized_legacy_project(http_request, request.project_id)
        if session_project_id and session_project_id != project.project_id:
            raise HTTPException(status_code=409, detail="会话与作品归属不一致")
    else:
        project = _current_legacy_project(http_request)
        if session_project_id and session_project_id != project.project_id:
            raise HTTPException(status_code=409, detail="会话与作品归属不一致")
    session_id, state = novel_workflow_service.plan_chapter(
        session_id=request.session_id,
        project_id=project.project_id,
        project_title=request.project_title,
        global_worldview=request.global_worldview,
        chapter_number=request.chapter_number,
        previous_summary=request.previous_summary,
        user_instruction=request.user_instruction,
        characters=request.characters,
    )

    return NovelPlanResponse(
        session_id=session_id,
        current_stage=state["current_stage"],
        plot_beats=state.get("current_plot_beats", []),
        message=state.get("error_message") or "Planner 已生成剧情节点，工作流已在 Writer 前暂停。",
    )


@router.get("/projects/current", response_model=NovelProjectResponse)
async def get_current_project(request: Request) -> NovelProjectResponse:
    """读取默认作品的章节目录和进度。"""

    project = _current_legacy_project(request)
    return NovelProjectResponse(project=project)


@router.get("/projects/{project_id}", response_model=NovelProjectResponse)
async def get_project(project_id: str, request: Request) -> NovelProjectResponse:
    """读取指定作品的章节目录和进度。"""

    project = _authorized_legacy_project(request, project_id)
    return NovelProjectResponse(project=project)


@router.get("/projects/{project_id}/codex", response_model=ProjectCodexResponse)
async def get_project_codex(project_id: str, request: Request) -> ProjectCodexResponse:
    """读取作品级人物设定与剧情设定聚合。"""

    project = _authorized_legacy_project(request, project_id)
    return ProjectCodexResponse.from_project(project)


@router.get(
    "/projects/{project_id}/prepare-next",
    response_model=PrepareNextChapterResponse,
)
async def prepare_next_chapter(
    project_id: str,
    request: Request,
) -> PrepareNextChapterResponse:
    """准备下一章输入，不触发 Planner。"""

    _authorized_legacy_project(request, project_id)
    try:
        snapshot = novel_workflow_service.prepare_next_chapter(project_id=project_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return PrepareNextChapterResponse(snapshot=snapshot)


@router.post(
    "/projects/{project_id}/prepare-next",
    response_model=PrepareNextChapterResponse,
)
async def prepare_next_chapter_with_payload(
    project_id: str,
    request: PrepareNextChapterRequest,
    http_request: Request,
) -> PrepareNextChapterResponse:
    """带人物卡和额外要求准备下一章输入，不触发 Planner。"""

    _authorized_legacy_project(http_request, project_id)
    try:
        snapshot = novel_workflow_service.prepare_next_chapter(
            project_id=project_id,
            user_instruction=request.user_instruction,
            characters=request.characters,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return PrepareNextChapterResponse(snapshot=snapshot)


@router.post("/projects/{project_id}/full-plan", response_model=NovelProjectResponse)
async def generate_full_plan(
    project_id: str,
    request: FullPlanRequest,
    http_request: Request,
) -> NovelProjectResponse:
    """生成或更新全文规划骨架，并持久化。"""

    _authorized_legacy_project(http_request, project_id)
    project = novel_workflow_service.generate_full_plan(
        project_id=project_id,
        full_plan=request.full_plan,
        volumes=request.volumes,
        chapter_plans=request.chapter_plans,
        target_chapter_count=request.target_chapter_count,
    )
    return NovelProjectResponse(project=project)


@router.put("/projects/{project_id}/full-plan", response_model=NovelProjectResponse)
async def update_full_plan(
    project_id: str,
    request: FullPlanRequest,
    http_request: Request,
) -> NovelProjectResponse:
    """人工修改全文规划、分卷规划和章节规划。"""

    _authorized_legacy_project(http_request, project_id)
    if request.full_plan is None:
        raise HTTPException(status_code=422, detail="full_plan 不能为空")

    project = novel_workflow_service.update_full_plan(
        project_id=project_id,
        full_plan=request.full_plan,
        volumes=request.volumes,
        chapter_plans=request.chapter_plans,
    )
    return NovelProjectResponse(project=project)


@router.post("/projects/{project_id}/batch/plan", response_model=BatchTaskResponse)
async def batch_plan_chapters(
    project_id: str,
    request: BatchChapterRequest,
    http_request: Request,
) -> BatchTaskResponse:
    """同步批量规划多章节。"""

    _authorized_legacy_project(http_request, project_id)
    if request.end_chapter < request.start_chapter:
        raise HTTPException(status_code=422, detail="end_chapter 必须大于等于 start_chapter")
    try:
        conflicts = [
            ExistingChapterConflict.model_validate(conflict)
            for conflict in novel_workflow_service.existing_chapter_conflicts(
                project_id=project_id,
                start_chapter=request.start_chapter,
                end_chapter=request.end_chapter,
            )
        ]
        task = novel_workflow_service.batch_plan_chapters(
            project_id=project_id,
            start_chapter=request.start_chapter,
            end_chapter=request.end_chapter,
            user_instruction=request.user_instruction,
            characters=request.characters,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    project = novel_workflow_service.get_project(project_id)
    return BatchTaskResponse.from_project(
        task=task,
        project=project,
        existing_chapter_conflicts=conflicts,
    )


@router.post("/projects/{project_id}/batch/generate", response_model=BatchTaskResponse)
async def batch_generate_chapters(
    project_id: str,
    request: BatchChapterRequest,
    http_request: Request,
) -> BatchTaskResponse:
    """同步批量生成多章节草稿。"""

    _authorized_legacy_project(http_request, project_id)
    if request.end_chapter < request.start_chapter:
        raise HTTPException(status_code=422, detail="end_chapter 必须大于等于 start_chapter")
    try:
        conflicts = [
            ExistingChapterConflict.model_validate(conflict)
            for conflict in novel_workflow_service.existing_chapter_conflicts(
                project_id=project_id,
                start_chapter=request.start_chapter,
                end_chapter=request.end_chapter,
            )
        ]
        if conflicts and request.overwrite_policy == "block":
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "批量生成会覆盖已有章节，请选择 compare、replace 或 keep_existing。",
                    "existing_chapter_conflicts": [
                        conflict.model_dump(mode="json") for conflict in conflicts
                    ],
                },
            )
        task = novel_workflow_service.batch_generate_chapters(
            project_id=project_id,
            start_chapter=request.start_chapter,
            end_chapter=request.end_chapter,
            user_instruction=request.user_instruction,
            characters=request.characters,
            overwrite_policy=request.overwrite_policy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    project = novel_workflow_service.get_project(project_id)
    return BatchTaskResponse.from_project(
        task=task,
        project=project,
        existing_chapter_conflicts=conflicts,
    )


@router.get(
    "/projects/{project_id}/chapters/{chapter_number}",
    response_model=ChapterPreviewResponse,
)
async def get_project_chapter(
    project_id: str,
    chapter_number: int,
    request: Request,
) -> ChapterPreviewResponse:
    """读取指定章节预览；无正文或无章节记录时也返回明确状态。"""

    project = _authorized_legacy_project(request, project_id)
    return ChapterPreviewResponse.from_project(
        project=project,
        chapter_number=chapter_number,
    )


@router.post("/projects/{project_id}/chapters/next", response_model=NovelPlanResponse)
async def plan_next_chapter(
    project_id: str,
    request: ContinueChapterRequest,
    http_request: Request,
) -> NovelPlanResponse:
    """基于作品目录、上一章摘要和当前世界观继续规划下一章。"""

    _authorized_legacy_project(http_request, project_id)
    if request.session_id:
        session_state = _authorized_legacy_session(http_request, request.session_id)
        if session_state.get("project_id") != project_id:
            raise HTTPException(status_code=409, detail="会话与作品归属不一致")
    try:
        session_id, state = novel_workflow_service.plan_next_chapter(
            project_id=project_id,
            session_id=request.session_id,
            user_instruction=request.user_instruction,
            characters=request.characters,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return NovelPlanResponse(
        session_id=session_id,
        current_stage=state["current_stage"],
        plot_beats=state.get("current_plot_beats", []),
        message=state.get("error_message") or "已根据作品目录规划下一章剧情节点。",
    )


@router.post("/chapters/{session_id}/approve", response_model=NovelRunResponse)
async def approve_plot_beats(
    session_id: str,
    request: NovelApprovalRequest,
    http_request: Request,
) -> NovelRunResponse:
    """提交人工确认后的剧情节点，并只生成 Writer 正文草稿。"""

    _authorized_legacy_session(http_request, session_id)
    try:
        state = novel_workflow_service.approve_plan(
            session_id=session_id,
            plot_beats=request.plot_beats,
            human_feedback=request.human_feedback,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return NovelRunResponse(
        session_id=session_id,
        current_stage=state["current_stage"],
        draft=state.get("current_draft"),
        extracted_lore_updates=state.get("extracted_lore_updates", {}),
        extracted_character_updates=state.get("extracted_character_updates", {}),
        review_feedback=state.get("review_feedback", []),
        retrieved_context=state.get("retrieved_context", []),
        message=state.get("error_message")
        or "Writer 已生成章节草稿，等待 Reviewer 审查。",
    )


@router.post("/chapters/{session_id}/review", response_model=NovelRunResponse)
async def review_chapter_draft(
    session_id: str,
    request: Request,
) -> NovelRunResponse:
    """触发 Reviewer 审查 Writer 已生成的正文草稿。"""

    _authorized_legacy_session(request, session_id)
    try:
        state = novel_workflow_service.review_draft(session_id=session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return NovelRunResponse(
        session_id=session_id,
        current_stage=state["current_stage"],
        draft=state.get("current_draft"),
        extracted_lore_updates=state.get("extracted_lore_updates", {}),
        extracted_character_updates=state.get("extracted_character_updates", {}),
        review_feedback=state.get("review_feedback", []),
        retrieved_context=state.get("retrieved_context", []),
        message=state.get("error_message") or "Reviewer 已完成结构化审查。",
    )


@router.post("/chapters/{session_id}/revise", response_model=NovelRunResponse)
async def revise_chapter_draft(
    session_id: str,
    request: NovelActionRequest,
    http_request: Request,
) -> NovelRunResponse:
    """用户同意修改后，触发 Writer 根据审查意见重新生成草稿。"""

    _authorized_legacy_session(http_request, session_id)
    try:
        state = novel_workflow_service.revise_draft(
            session_id=session_id,
            human_feedback=request.human_feedback,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return NovelRunResponse(
        session_id=session_id,
        current_stage=state["current_stage"],
        draft=state.get("current_draft"),
        extracted_lore_updates=state.get("extracted_lore_updates", {}),
        extracted_character_updates=state.get("extracted_character_updates", {}),
        review_feedback=state.get("review_feedback", []),
        retrieved_context=state.get("retrieved_context", []),
        message=state.get("error_message") or "Writer 已根据审查意见生成修订草稿。",
    )


@router.post("/chapters/{session_id}/accept", response_model=NovelRunResponse)
async def accept_chapter(
    session_id: str,
    request: NovelActionRequest,
    http_request: Request,
) -> NovelRunResponse:
    """用户接受本章节后，触发 Librarian 抽取设定并完成章节。"""

    _authorized_legacy_session(http_request, session_id)
    try:
        state = novel_workflow_service.accept_chapter(
            session_id=session_id,
            human_feedback=request.human_feedback,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return NovelRunResponse(
        session_id=session_id,
        current_stage=state["current_stage"],
        draft=state.get("current_draft"),
        extracted_lore_updates=state.get("extracted_lore_updates", {}),
        extracted_character_updates=state.get("extracted_character_updates", {}),
        review_feedback=state.get("review_feedback", []),
        retrieved_context=state.get("retrieved_context", []),
        message=state.get("error_message") or "章节已接受，Librarian 已完成设定抽取。",
    )


@router.get("/sessions/{session_id}", response_model=NovelRunResponse)
async def get_session_state(session_id: str, request: Request) -> NovelRunResponse:
    """读取小说工作流会话状态，便于 API 调试。"""

    _authorized_legacy_session(request, session_id)
    try:
        state = novel_workflow_service.get_state(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return NovelRunResponse(
        session_id=session_id,
        current_stage=state["current_stage"],
        draft=state.get("current_draft"),
        extracted_lore_updates=state.get("extracted_lore_updates", {}),
        extracted_character_updates=state.get("extracted_character_updates", {}),
        review_feedback=state.get("review_feedback", []),
        retrieved_context=state.get("retrieved_context", []),
        message="已读取当前小说工作流会话状态。",
    )
