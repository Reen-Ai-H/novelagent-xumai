"""独立与 AI 共用的完整故事档案工作区 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app import entry_routes, independent_routes
from app.core.independent_service import IndependentServiceError


router = APIRouter(prefix="/api/archive", tags=["archive"])


def _current_archive_account(request: Request, project_id: str):
    account = entry_routes._current_account(request)
    link = next((item for item in account.project_links if item.project_id == project_id), None)
    if link is None:
        raise HTTPException(status_code=404, detail={"code": "project_missing", "message": "作品不存在。"})
    return account, link


@router.get("/projects/{project_id}")
async def read_archive_workspace(project_id: str, request: Request, chapter_number: int | None = None) -> dict:
    account, link = _current_archive_account(request, project_id)
    service = independent_routes.independent_service
    try:
        workspace = service.workspace(project_id, account.account_id)
        if not workspace["initialized"]:
            return {
                "initialized": False,
                "project_id": project_id,
                "title": workspace["title"],
                "mode": link.mode,
                "read_only": False,
                "selected_chapter_number": None,
                "available_snapshots": [],
                "archive": workspace["archive"],
            }
        result = service.archive(project_id, account.account_id, chapter_number)
        result.update({"initialized": True, "project_id": project_id, "title": workspace["title"], "mode": link.mode})
        return result
    except IndependentServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "data": exc.data},
        ) from exc
