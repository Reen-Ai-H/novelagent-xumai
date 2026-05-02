from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """对话接口的请求体。"""

    query: str = Field(..., description="用户输入的问题或指令", min_length=1)
