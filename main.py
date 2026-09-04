"""服务入口：仅做装配，不承载业务逻辑。"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import ai_routes
from app import deconstruction_routes
from app.entry_routes import router as entry_router
from app.ai_routes import router as ai_router
from app.archive_routes import router as archive_router
from app.independent_routes import router as independent_router
from app.novel_routes import router as novel_router
from app.routes import router as chat_router

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
logger = logging.getLogger("xumai.ai_worker")


async def _ai_background_worker() -> None:
    """服务端持久 worker：页面离开或服务重启后仍扫描并恢复导演台任务。"""

    while True:
        try:
            await ai_routes.ai_service.process_background_runs_async()
        except Exception:  # pragma: no cover - 记录异常后保持 worker 存活
            logger.exception("AI 后台任务扫描失败，下一轮将继续恢复")
        await asyncio.sleep(0.15)


async def _deconstruction_background_worker() -> None:
    """服务端拆解 worker：导入/完成章节后离页仍会继续，重启会恢复。"""

    while True:
        try:
            await deconstruction_routes.deconstruction_service.process_background_tasks_async()
        except Exception:  # pragma: no cover - worker 必须保持存活，业务错误已持久化
            logger.exception("作品拆解后台任务扫描失败，下一轮将继续恢复")
        await asyncio.sleep(0.2)


@asynccontextmanager
async def lifespan(_: FastAPI):
    worker = asyncio.create_task(_ai_background_worker(), name="xumai-ai-worker")
    deconstruction_worker = asyncio.create_task(
        _deconstruction_background_worker(),
        name="xumai-deconstruction-worker",
    )
    try:
        yield
    finally:
        worker.cancel()
        deconstruction_worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker
        with suppress(asyncio.CancelledError):
            await deconstruction_worker


app = FastAPI(
    title="叙脉",
    description="新一代写作体验：让长篇故事记得自己。",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

app.include_router(chat_router)
app.include_router(novel_router)
app.include_router(entry_router)
app.include_router(independent_router)
app.include_router(deconstruction_routes.router)
app.include_router(ai_router)
app.include_router(archive_router)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """产品首页入口。"""

    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/login", include_in_schema=False)
async def login_page() -> FileResponse:
    """登录页深链接，实际视图由统一前端壳切换。"""

    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/library", include_in_schema=False)
async def library_page() -> FileResponse:
    """书架页深链接，实际视图由统一前端壳切换。"""

    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/independent/{project_id}", include_in_schema=False)
async def independent_page(project_id: str) -> FileResponse:
    """独立创作深链接，仍由统一前端壳切换工作区视图。"""

    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/ai/{project_id}", include_in_schema=False)
async def ai_page(project_id: str) -> FileResponse:
    """AI 创作室深链接。"""

    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/ai/{project_id}/director", include_in_schema=False)
async def ai_director_page(project_id: str) -> FileResponse:
    """AI 导演台深链接。"""

    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/archive/{project_id}", include_in_schema=False)
async def archive_page(project_id: str) -> FileResponse:
    """独立与 AI 共用的完整故事档案深链接。"""

    return FileResponse(FRONTEND_DIR / "index.html")
