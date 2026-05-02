"""LangChain 链路定义：Prompt | LLM | OutputParser。"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from core.config import settings


# ==========================================
# 初始化 LLM（开启流式支持）
# ==========================================
llm = ChatOpenAI(
    model=settings.llm_model,
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
    temperature=settings.llm_temperature,
    streaming=True,
)


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
chat_chain = prompt | llm | StrOutputParser()
