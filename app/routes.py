"""FastAPI 路由定义。"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.chain import chat_chain
from schemas.chat import ChatRequest


router = APIRouter()


@router.post("/chat")
async def chat_with_agent(request: ChatRequest):
    """基于 LangChain 的流式对话接口（SSE 协议）。"""
    if chat_chain is None:
        raise HTTPException(
            status_code=503,
            detail="当前未配置模型服务，聊天接口暂不可用。",
        )

    print(f"✅ 收到请求: {request.query}")

    async def generate_stream():
        # astream 是 LangChain 提供的异步流式调用方法
        async for chunk in chat_chain.astream({"input": request.query}):
            yield chunk

    return StreamingResponse(generate_stream(), media_type="text/event-stream")
