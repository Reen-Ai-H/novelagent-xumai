# wayto_aijob

这个将记录我的就业发展和学习规划。

## 项目进度

- 已实现基于 LangChain 的对话链路，支持流式输出。

## 目录结构

```
wayto_aijob/
├── app/              # 核心业务逻辑（LangChain 链路、FastAPI 路由）
│   ├── chain.py      # Prompt | LLM | OutputParser 链路
│   └── routes.py     # /chat 流式接口
├── schemas/          # Pydantic 数据模型（请求 / 响应）
│   └── chat.py
├── core/             # 基础设施
│   └── config.py     # 配置管理（基于 pydantic-settings + .env）
├── main.py           # FastAPI 应用入口
└── .env              # 环境变量（不入库）
```

## 启动方式

```bash
uvicorn main:app --reload
```

调用 `POST /chat`，请求体 `{"query": "你的问题"}`，响应为 SSE 流式文本。
