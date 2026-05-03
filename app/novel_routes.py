"""小说共创工作流 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.novel_graph import novel_workflow_service
from schemas.novel import (
    NovelActionRequest,
    NovelApprovalRequest,
    NovelPlanRequest,
    NovelPlanResponse,
    NovelRunResponse,
)


router = APIRouter(prefix="/novel", tags=["novel"])


@router.post("/chapters/plan", response_model=NovelPlanResponse)
async def plan_chapter(request: NovelPlanRequest) -> NovelPlanResponse:
    """生成章节剧情节点，并在 Writer 前暂停等待人工审核。"""

    session_id, state = novel_workflow_service.plan_chapter(
        session_id=request.session_id,
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


@router.post("/chapters/{session_id}/approve", response_model=NovelRunResponse)
async def approve_plot_beats(
    session_id: str,
    request: NovelApprovalRequest,
) -> NovelRunResponse:
    """提交人工确认后的剧情节点，并只生成 Writer 正文草稿。"""

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
        message=state.get("error_message")
        or "Writer 已生成章节草稿，等待 Reviewer 审查。",
    )


@router.post("/chapters/{session_id}/review", response_model=NovelRunResponse)
async def review_chapter_draft(session_id: str) -> NovelRunResponse:
    """触发 Reviewer 审查 Writer 已生成的正文草稿。"""

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
        message=state.get("error_message") or "Reviewer 已完成结构化审查。",
    )


@router.post("/chapters/{session_id}/revise", response_model=NovelRunResponse)
async def revise_chapter_draft(
    session_id: str,
    request: NovelActionRequest,
) -> NovelRunResponse:
    """用户同意修改后，触发 Writer 根据审查意见重新生成草稿。"""

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
        message=state.get("error_message") or "Writer 已根据审查意见生成修订草稿。",
    )


@router.post("/chapters/{session_id}/accept", response_model=NovelRunResponse)
async def accept_chapter(
    session_id: str,
    request: NovelActionRequest,
) -> NovelRunResponse:
    """用户接受本章节后，触发 Librarian 抽取设定并完成章节。"""

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
        message=state.get("error_message") or "章节已接受，Librarian 已完成设定抽取。",
    )


@router.get("/sessions/{session_id}", response_model=NovelRunResponse)
async def get_session_state(session_id: str) -> NovelRunResponse:
    """读取小说工作流会话状态，便于 API 调试。"""

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
        message="已读取当前小说工作流会话状态。",
    )
