"""阶段 1 的邮箱账户、持久会话和书架 API。"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from fastapi import APIRouter, HTTPException, Request, Response

from app.core.account_store import (
    ACCOUNT_DATA_PATH,
    SESSION_COOKIE_NAME,
    SESSION_TTL,
    AccountRecord,
    AccountStore,
)
from app.core.entry_service import EntryService
from schemas.entry import (
    AccountPublic,
    AuthResponse,
    CreateProjectRequest,
    EmailLoginRequest,
    LibraryResponse,
    ProjectCreatedResponse,
    SessionResponse,
)


router = APIRouter(prefix="/api", tags=["entry"])
account_store = AccountStore(ACCOUNT_DATA_PATH)
entry_service = EntryService(accounts=account_store)


def _session_error(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=401, detail={"code": code, "message": message})


def _current_account(request: Request) -> AccountRecord:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise _session_error("unauthenticated", "请先使用邮箱登录。")
    account = account_store.account_for_token(token)
    if account is None:
        raise _session_error("session_expired", "会话已失效，请重新登录；作品数据仍会保留。")
    return account


@router.post("/auth/email", response_model=AuthResponse)
async def login_with_email(request: EmailLoginRequest, response: Response) -> AuthResponse:
    try:
        account, token, expires_at = account_store.login(request.email)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_email", "message": str(exc)},
        ) from exc

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=int(SESSION_TTL.total_seconds()),
        expires=int(SESSION_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return AuthResponse(
        account=account.public(),
        session_expires_at=expires_at,
    )


@router.get("/auth/session", response_model=SessionResponse)
async def read_session(request: Request) -> SessionResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return SessionResponse(authenticated=False)

    account = account_store.account_for_token(token)
    if account is None:
        raise _session_error("session_expired", "会话已失效，请重新登录；作品数据仍会保留。")
    return SessionResponse(authenticated=True, account=account.public())


@router.post("/auth/logout", response_model=SessionResponse)
async def logout(request: Request, response: Response) -> SessionResponse:
    account_store.logout(request.cookies.get(SESSION_COOKIE_NAME))
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return SessionResponse(authenticated=False)


@router.get("/library", response_model=LibraryResponse)
async def read_library(request: Request, q: str = "") -> LibraryResponse:
    account = _current_account(request)
    return LibraryResponse(
        account=account.public(),
        projects=entry_service.library(account, q),
        query=q.strip(),
    )


@router.post("/library/projects", response_model=ProjectCreatedResponse)
async def create_library_project(
    request: CreateProjectRequest,
    http_request: Request,
) -> ProjectCreatedResponse:
    account = _current_account(http_request)
    project = entry_service.create_project(
        account=account,
        title=request.title,
        mode=request.mode,
        brief=request.brief,
    )
    next_path = f"/library?created={project.project_id}"
    next_step_label = (
        "下一阶段：进入独立创作编辑器"
        if project.mode == "independent"
        else "下一阶段：进入 AI 创作室"
    )
    return ProjectCreatedResponse(
        project=project,
        next_path=next_path,
        next_step_label=next_step_label,
    )


def _notification_target(project_id: str, mode: str, kind: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", project_id):
        return ""
    if mode == "ai_assisted":
        return (
            f"/ai/{project_id}/director"
            if kind.startswith("director_")
            else f"/ai/{project_id}"
        )
    return (
        f"/archive/{project_id}"
        if kind in {"analysis_completed", "version_created", "change_decision"}
        else f"/independent/{project_id}"
    )


def _notification_source(link, account_id: str):
    record = entry_service.sidecar_for_link(link, account_id)
    if record is None:
        return None, None
    if record is None or record.account_id != account_id:
        return None, None
    project = entry_service.projects.load_project(link.project_id)
    return record, project


@router.get("/notifications")
async def read_notifications(request: Request) -> dict:
    account = _current_account(request)
    items: list[dict] = []
    for link in account.project_links:
        record, project = _notification_source(link, account.account_id)
        if record is None:
            continue
        title = project.title if project is not None else record.title
        for notification in record.notifications:
            payload = notification.model_dump(mode="json")
            payload.update(
                {
                    "project_id": link.project_id,
                    "project_title": title,
                    "mode": link.mode,
                    "target_path": _notification_target(
                        link.project_id,
                        link.mode,
                        notification.kind,
                    ),
                }
            )
            items.append(payload)
    items.sort(
        key=lambda item: (
            EntryService.normalize_timestamp(item.get("created_at")),
            str(item.get("notification_id", "")),
        ),
        reverse=True,
    )
    items = items[:50]
    return {
        "unread_count": sum(1 for item in items if not item["read"]),
        "notifications": items,
    }


@router.post("/notifications/{project_id}/{notification_id}/read")
async def mark_notification_read(
    project_id: str,
    notification_id: str,
    request: Request,
) -> dict:
    account = _current_account(request)
    link = next(
        (
            item
            for item in account.project_links
            if item.project_id == project_id and item.mode in {"independent", "ai_assisted"}
        ),
        None,
    )
    if link is None:
        raise HTTPException(status_code=404, detail="通知不存在")
    record, _ = _notification_source(link, account.account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="通知不存在")
    notification = next(
        (item for item in record.notifications if item.notification_id == notification_id),
        None,
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="通知不存在")
    notification.read = True
    record.updated_at = datetime.now(timezone.utc)
    if link.mode == "ai_assisted":
        entry_service.ai.save(record)
    else:
        entry_service.independent.save(record)
    return await read_notifications(request)
