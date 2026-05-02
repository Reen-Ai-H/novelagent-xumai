"""服务入口：仅做装配，不承载业务逻辑。"""

from fastapi import FastAPI

from app.routes import router as chat_router


app = FastAPI(
    title="Agent AI 服务",
    description="基于 LangChain 的对话链路，支持流式输出",
)

app.include_router(chat_router)
