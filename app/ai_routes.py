"""阶段 3：AI 创作室、蓝图和导演台 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app import entry_routes, independent_routes
from app.core.ai_service import AIServiceError, AIStudioService
from schemas.ai import (
    AIMessageRequest,
    BlueprintUpdateRequest,
    ConfirmBlueprintRequest,
    DirectorChoiceRequest,
    DirectorSettingsRequest,
    DirectorStartRequest,
)


router = APIRouter(prefix="/api/ai", tags=["ai"])
ai_service = AIStudioService(
    projects=entry_routes.entry_service.projects,
    manuscript=independent_routes.independent_service,
)
# 书架/通知入口使用自己的轻量 store 实例，但与 AIService 指向同一数据目录；
# 注入同一 durable coordinator，旁路读取也能先恢复 committed journal。
entry_routes.entry_service.transaction_coordinator = ai_service.transactions


def _raise_service_error(error: AIServiceError) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message, "data": error.data},
    ) from error


def _redact_context_value(value: object, *, key: str | None = None) -> object:
    """递归建立最小浏览器合同，不让内部记忆借嵌套字段漏出。"""

    if key in {"private_memory", "own_experiences"}:
        return None
    if isinstance(value, dict):
        return {
            str(item_key): redacted
            for item_key, item_value in value.items()
            if (redacted := _redact_context_value(item_value, key=str(item_key))) is not None
        }
    if isinstance(value, list):
        return [
            redacted
            for item in value
            if (redacted := _redact_context_value(item)) is not None
        ]
    return value


def _public_contexts(contexts: list[object]) -> list[dict]:
    """浏览器只拿脱敏合同；人物私有记忆永远留在服务端推演边界内。"""

    public: list[dict] = []
    for context in contexts:
        if hasattr(context, "model_dump"):
            payload = context.model_dump(mode="json")  # type: ignore[union-attr]
        else:
            payload = dict(context)  # type: ignore[arg-type]
        redacted = _redact_context_value(payload)
        public.append(redacted if isinstance(redacted, dict) else {})
    return public


def _current_ai_account(request: Request, project_id: str):
    account = entry_routes._current_account(request)
    link = next((item for item in account.project_links if item.project_id == project_id), None)
    if link is None:
        raise HTTPException(status_code=404, detail={"code": "project_missing", "message": "作品不存在。"})
    if link.mode != "ai_assisted":
        raise HTTPException(
            status_code=409,
            detail={"code": "mode_mismatch", "message": "这部作品属于独立创作，不能进入 AI 创作室。"},
        )
    return account


@router.get("/projects/{project_id}")
async def read_ai_workspace(project_id: str, request: Request) -> dict:
    account = _current_ai_account(request, project_id)
    try:
        return ai_service.workspace(project_id, account.account_id)
    except AIServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/messages")
async def send_ai_message(project_id: str, request: Request, payload: AIMessageRequest) -> dict:
    account = _current_ai_account(request, project_id)
    try:
        return await ai_service.send_message(project_id, account.account_id, payload.content)
    except AIServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.put("/projects/{project_id}/blueprint")
async def update_ai_blueprint(project_id: str, request: Request, payload: BlueprintUpdateRequest) -> dict:
    account = _current_ai_account(request, project_id)
    try:
        return ai_service.update_blueprint(project_id, account.account_id, payload.model_dump(exclude_none=True))
    except AIServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/blueprint/confirm")
async def confirm_ai_blueprint(project_id: str, request: Request, payload: ConfirmBlueprintRequest) -> dict:
    account = _current_ai_account(request, project_id)
    try:
        return ai_service.confirm_blueprint(
            project_id,
            account.account_id,
            payload.expected_revision,
            payload.idempotency_key,
        )
    except AIServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.put("/projects/{project_id}/settings")
async def update_ai_settings(project_id: str, request: Request, payload: DirectorSettingsRequest) -> dict:
    account = _current_ai_account(request, project_id)
    try:
        return ai_service.update_settings(
            project_id,
            account.account_id,
            strategy=payload.strategy,
            reveal_consequences=payload.reveal_consequences,
        )
    except AIServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/director/start")
async def start_ai_director(project_id: str, request: Request, payload: DirectorStartRequest) -> dict:
    account = _current_ai_account(request, project_id)
    try:
        return await ai_service.start_director(
            project_id,
            account.account_id,
            strategy=payload.strategy,
            idempotency_key=payload.idempotency_key,
            defer=payload.defer,
        )
    except AIServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.get("/projects/{project_id}/director/runs/{run_id}")
async def read_ai_director(project_id: str, run_id: str, request: Request) -> dict:
    account = _current_ai_account(request, project_id)
    try:
        return ai_service.read_run(project_id, account.account_id, run_id)
    except AIServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/director/runs/{run_id}/choice")
async def choose_ai_director(project_id: str, run_id: str, request: Request, payload: DirectorChoiceRequest) -> dict:
    account = _current_ai_account(request, project_id)
    try:
        return await ai_service.choose(project_id, account.account_id, run_id, payload.choice_id)
    except AIServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/director/runs/{run_id}/pause")
async def pause_ai_director(project_id: str, run_id: str, request: Request) -> dict:
    account = _current_ai_account(request, project_id)
    try:
        return ai_service.pause(project_id, account.account_id, run_id)
    except AIServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/director/runs/{run_id}/resume")
async def resume_ai_director(project_id: str, run_id: str, request: Request) -> dict:
    account = _current_ai_account(request, project_id)
    try:
        return await ai_service.resume(project_id, account.account_id, run_id)
    except AIServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/director/runs/{run_id}/retry")
async def retry_ai_director(project_id: str, run_id: str, request: Request) -> dict:
    account = _current_ai_account(request, project_id)
    try:
        return await ai_service.retry(project_id, account.account_id, run_id)
    except AIServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/director/runs/{run_id}/advance")
async def advance_ai_director(project_id: str, run_id: str, request: Request) -> dict:
    account = _current_ai_account(request, project_id)
    try:
        return await ai_service.advance(project_id, account.account_id, run_id)
    except AIServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.get("/projects/{project_id}/director/runs/{run_id}/contexts")
async def read_ai_role_contexts(project_id: str, run_id: str, request: Request) -> dict:
    account = _current_ai_account(request, project_id)
    try:
        return {
            "contexts": _public_contexts(ai_service.role_contexts(project_id, account.account_id, run_id)),
            "contract": "专业角色只读取职责所需的共享材料；内部记忆字段不会返回浏览器。",
        }
    except AIServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.get("/projects/{project_id}/director/runs/{run_id}/character-contexts")
async def read_ai_story_character_contexts(project_id: str, run_id: str, request: Request) -> dict:
    account = _current_ai_account(request, project_id)
    try:
        return {
            "contexts": _public_contexts(ai_service.story_character_contexts(project_id, account.account_id, run_id)),
            "contract": "故事人物只接收共享规则、公开事实、必须知道的事实和自己的经历；人物内部记忆不会返回浏览器。",
        }
    except AIServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")
