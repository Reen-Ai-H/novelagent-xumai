"""阶段 2/3：共用正文、档案与稿本版本 API。

独立作品和 AI 作品共用同一套服务端正文合同；AI 专属入口仍由
``app.ai_routes`` 控制，避免复制 pending_changes、快照和恢复规则。
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app import entry_routes
from app.core.independent_service import IndependentServiceError, IndependentWorkspaceService
from schemas.independent import (
    CompleteChapterRequest,
    ImportPreviewRequest,
    ResolveChangesRequest,
    SaveDraftRequest,
    StartIndependentRequest,
    TrialSketchRequest,
)


router = APIRouter(prefix="/api/independent", tags=["independent"])
independent_service = IndependentWorkspaceService(projects=entry_routes.entry_service.projects)


def _raise_service_error(error: IndependentServiceError) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message, "data": error.data},
    ) from error


def _current_independent_account(request: Request, project_id: str):
    account = entry_routes._current_account(request)
    link = next((item for item in account.project_links if item.project_id == project_id), None)
    if link is None:
        raise HTTPException(status_code=404, detail={"code": "project_missing", "message": "作品不存在。"})
    return account


@router.get("/projects/{project_id}")
async def read_independent_workspace(project_id: str, request: Request) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        workspace = independent_service.workspace(project_id, account.account_id)
        link = next(item for item in account.project_links if item.project_id == project_id)
        workspace["mode"] = link.mode
        return workspace
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/start")
async def start_independent_workspace(
    project_id: str,
    request: Request,
    payload: StartIndependentRequest,
) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        independent_service.start_blank(project_id, account.account_id)
        return independent_service.workspace(project_id, account.account_id)
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/imports/preview")
async def preview_independent_import(
    project_id: str,
    request: Request,
    payload: ImportPreviewRequest,
) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        preview = independent_service.preview_import(
            project_id,
            account.account_id,
            filename=payload.filename,
            content_base64=payload.content_base64,
        )
        return {"preview": independent_service._public_import(preview)}
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/imports/{preview_id}/confirm")
async def confirm_independent_import(project_id: str, preview_id: str, request: Request) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        independent_service.confirm_import(project_id, account.account_id, preview_id)
        return independent_service.workspace(project_id, account.account_id)
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/chapters")
async def add_independent_chapter(project_id: str, request: Request, title: str | None = None) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        chapter = independent_service.add_chapter(project_id, account.account_id, title)
        return {"chapter": chapter}
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.put("/projects/{project_id}/chapters/{chapter_id}/draft")
async def save_independent_draft(
    project_id: str,
    chapter_id: str,
    request: Request,
    payload: SaveDraftRequest,
) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        chapter = independent_service.save_draft(
            project_id,
            account.account_id,
            chapter_id,
            content=payload.content,
            title=payload.title,
            expected_revision=payload.expected_revision,
        )
        return {"save_state": "saved", "chapter": chapter, "workspace": independent_service.workspace(project_id, account.account_id)}
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/chapters/{chapter_id}/complete")
async def complete_independent_chapter(
    project_id: str,
    chapter_id: str,
    request: Request,
    payload: CompleteChapterRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        task = independent_service.complete_chapter(
            project_id,
            account.account_id,
            chapter_id,
            content=payload.content,
            expected_revision=payload.expected_revision,
            idempotency_key=payload.idempotency_key,
        )
        if task.status == "queued":
            background_tasks.add_task(independent_service.run_task, project_id, account.account_id, task.task_id)
        return {"task": task, "message": "本章已保存，后台分析会继续运行。"}
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.get("/projects/{project_id}/tasks/{task_id}")
async def read_independent_task(project_id: str, task_id: str, request: Request) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        independent_service.recover_pending_tasks(project_id, account.account_id)
        return {"task": independent_service.task(project_id, account.account_id, task_id)}
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/tasks/{task_id}/retry")
async def retry_independent_task(
    project_id: str,
    task_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        task = independent_service.retry_task(project_id, account.account_id, task_id)
        if task.status == "queued":
            background_tasks.add_task(independent_service.run_task, project_id, account.account_id, task.task_id)
        return {"task": task}
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.get("/projects/{project_id}/archive")
async def read_independent_archive(project_id: str, request: Request, chapter_number: int | None = None) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        return independent_service.archive(project_id, account.account_id, chapter_number)
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.get("/projects/{project_id}/pending-changes")
async def read_pending_changes(project_id: str, request: Request) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        workspace = independent_service.workspace(project_id, account.account_id)
        return {"pending_changes": workspace["pending_changes"]}
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/pending-changes/resolve")
async def resolve_pending_changes(
    project_id: str,
    request: Request,
    payload: ResolveChangesRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        result = independent_service.resolve_changes(project_id, account.account_id, payload.decision)
        task = result.get("task")
        if task is not None and task.status == "queued":
            background_tasks.add_task(independent_service.run_task, project_id, account.account_id, task.task_id)
        result["workspace"] = independent_service.workspace(project_id, account.account_id)
        return result
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.get("/projects/{project_id}/versions/{version_id}/preview")
async def preview_independent_version(project_id: str, version_id: str, request: Request) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        return independent_service.version_preview(project_id, account.account_id, version_id)
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/versions/{version_id}/restore")
async def restore_independent_version(
    project_id: str,
    version_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        result = independent_service.restore_version(project_id, account.account_id, version_id)
        task = result["task"]
        if task.status == "queued":
            background_tasks.add_task(independent_service.run_task, project_id, account.account_id, task.task_id)
        result["workspace"] = independent_service.workspace(project_id, account.account_id)
        return result
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/characters/{character_id}/trial-sketch")
async def trial_independent_character_sketch(
    project_id: str,
    character_id: str,
    request: Request,
    payload: TrialSketchRequest,
) -> dict:
    account = _current_independent_account(request, project_id)
    try:
        result = independent_service.trial_sketch(
            project_id,
            account.account_id,
            style=payload.style,
            confirm=payload.confirm,
        )
        result["character_id"] = character_id
        return result
    except IndependentServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")
