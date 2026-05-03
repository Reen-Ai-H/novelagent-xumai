"""服务入口：仅做装配，不承载业务逻辑。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.novel_routes import router as novel_router
from app.routes import router as chat_router

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"


app = FastAPI(
    title="多智能体网文共创引擎",
    description="基于 LangGraph、LangChain 与 FastAPI 的 Human-in-the-Loop 小说生成服务",
)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

app.include_router(chat_router)
app.include_router(novel_router)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """前端工作台入口。"""

    return FileResponse(FRONTEND_DIR / "index.html")
