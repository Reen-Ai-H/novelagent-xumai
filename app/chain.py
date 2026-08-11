"""LangChain 链路定义：Prompt | LLM | OutputParser。"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.agents.llm_runtime import build_chat_model


# ==========================================
# 初始化 LLM（开启流式支持）
# ==========================================
llm = build_chat_model()


# ==========================================
# Prompt Template
# ==========================================
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是一个极其专业的 AI 工程师助理。你的回答需要简明扼要、直击痛点。"
            "如果用户问你代码问题，请直接给出关键代码。",
        ),
        ("user", "{input}"),
    ]
)


# ==========================================
# LCEL 语法构建 Chain
# StrOutputParser 负责剥离大模型返回的复杂结构，只保留纯文本
# ==========================================
chat_chain = prompt | llm | StrOutputParser() if llm else None
