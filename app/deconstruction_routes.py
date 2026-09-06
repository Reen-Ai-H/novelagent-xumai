"""独立创作内部的作品拆解 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from schemas.analysis_report import AnalysisImport

from app import entry_routes, independent_routes
from app.core.deconstruction_service import DeconstructionService, DeconstructionServiceError
from schemas.deconstruction import (
    DeconstructionActionRequest,
    DeconstructionEvidenceResponse,
    DeconstructionResponse,
)


router = APIRouter(prefix="/api/independent", tags=["deconstruction"])
deconstruction_service = DeconstructionService(independent=independent_routes.independent_service)
independent_routes.independent_service.deconstruction_service = deconstruction_service


@router.post("/projects/{project_id}/deconstruction/import", response_model=DeconstructionResponse)
async def import_deconstruction(project_id: str, request: Request, payload: AnalysisImport):
    account = _current_independent_account(request, project_id)
    try:
        return _service().import_report(project_id, account.account_id, payload)
    except DeconstructionServiceError as exc:
        _raise_service_error(exc)


def _raise_service_error(error: DeconstructionServiceError) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message, "data": error.data},
    ) from error


def _current_independent_account(request: Request, project_id: str):
    account = entry_routes._current_account(request)
    link = next((item for item in account.project_links if item.project_id == project_id), None)
    if link is None:
        raise HTTPException(status_code=404, detail={"code": "project_missing", "message": "作品不存在。"})
    if link.mode != "independent":
        raise HTTPException(
            status_code=409,
            detail={"code": "mode_mismatch", "message": "作品拆解目前位于独立创作内部。"},
        )
    return account


def _service() -> DeconstructionService:
    """让隔离测试替换 independent service 时，路由仍使用同一份侧车。"""

    current = independent_routes.independent_service
    if deconstruction_service.independent is not current:
        deconstruction_service.independent = current
        current.deconstruction_service = deconstruction_service
    return deconstruction_service


@router.get("/projects/{project_id}/deconstruction", response_model=DeconstructionResponse)
async def read_deconstruction(project_id: str, request: Request) -> dict[str, object]:
    account = _current_independent_account(request, project_id)
    try:
        return _service().read(project_id, account.account_id)
    except DeconstructionServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")

@router.post("/projects/{project_id}/deconstruction/rebuild", response_model=DeconstructionResponse)
async def rebuild_deconstruction(
    project_id: str,
    request: Request,
    payload: DeconstructionActionRequest | None = None,
) -> dict[str, object]:
    account = _current_independent_account(request, project_id)
    try:
        action = payload or DeconstructionActionRequest()
        _service().enqueue_for_project(
            project_id,
            account.account_id,
            reason="作者主动更新",
            idempotency_key=action.idempotency_key,
            expected_source_version_id=action.expected_source_version_id,
            expected_source_revision=action.expected_source_revision,
            expected_source_hash=action.expected_source_hash,
        )
        return _service().read(project_id, account.account_id)
    except DeconstructionServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.post("/projects/{project_id}/deconstruction/retry", response_model=DeconstructionResponse)
async def retry_deconstruction(
    project_id: str,
    request: Request,
    payload: DeconstructionActionRequest | None = None,
) -> dict[str, object]:
    account = _current_independent_account(request, project_id)
    try:
        action = payload or DeconstructionActionRequest()
        _service().retry(
            project_id,
            account.account_id,
            idempotency_key=action.idempotency_key,
            expected_source_version_id=action.expected_source_version_id,
            expected_source_revision=action.expected_source_revision,
            expected_source_hash=action.expected_source_hash,
        )
        return _service().read(project_id, account.account_id)
    except DeconstructionServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")


@router.get(
    "/projects/{project_id}/deconstruction/evidence/{evidence_id}",
    response_model=DeconstructionEvidenceResponse,
)
async def read_deconstruction_evidence(
    project_id: str,
    evidence_id: str,
    request: Request,
) -> dict[str, object]:
    account = _current_independent_account(request, project_id)
    try:
        return _service().evidence(project_id, account.account_id, evidence_id)
    except DeconstructionServiceError as exc:
        _raise_service_error(exc)
    raise AssertionError("unreachable")
