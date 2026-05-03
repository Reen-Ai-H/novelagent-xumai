# 多智能体网文共创引擎

Human-in-the-Loop Web Novel Agent 是一个基于大模型、多智能体协作和 RAG 的长篇网文半自动生成系统。项目目标是缓解 LLM 写长篇小说时常见的上下文遗忘、逻辑发散和角色崩坏问题，并允许用户在关键节点介入审核。

## 核心思路

系统采用 LangGraph 状态机架构，多个 Agent 共享并修改同一个 `NovelState`：

- `Planner Agent`：根据世界观、人物图谱和上一章进度生成本章剧情节点。
- `Writer Agent`：结合剧情节点和 RAG 检索到的设定撰写章节草稿。
- `Reviewer Agent`：检查 OOC、逻辑漏洞、设定冲突和节奏问题。
- `Librarian Agent`：在用户最终接受章节后，从正文中抽取新人物、新道具、关系变化和世界观增量。

Planner 生成剧情节点后，工作流会进入 `awaiting_human_review` 阶段。用户确认或修改节点后，Writer 先生成正文并立即返回前端展示，再由 Reviewer 单独审查。只有用户最终接受本章节后，Librarian 才会抽取设定并完成本章记忆更新。

## 技术栈

- Python 3.10+
- FastAPI
- LangGraph
- LangChain
- Pydantic v2
- python-dotenv / pydantic-settings
- RAG：用于检索长篇世界观、人物卡、历史章节摘要和伏笔

## 当前阶段

阶段四：单章节共创闭环基本成型。

已完成：

- 创建 `app/models`、`app/agents`、`app/core` 等基础目录。
- 使用 Pydantic v2 定义 `CharacterCard`、`PlotBeat`、`ChapterDraft`。
- 使用 `TypedDict` 定义 LangGraph 全局状态 `NovelState`。
- 创建 Planner、Writer、Librarian、Reviewer 节点骨架。
- 创建 LangGraph 状态图，并在 Writer 前设置人工审核断点。
- 新增小说工作流 API：生成剧情节点、提交审核结果、读取会话状态。
- 新增 FastAPI 托管的前端工作台，支持左侧功能导航、折叠侧栏、项目总览、开始创作、一键发表前瞻和小说预览。
- `开始创作` 下新增独立子页面：人物设定以游戏角色卡展示，剧情设定以横向可滚动鱼骨线展示。
- 顶部条幅会在 Agent 运行时展示预制动态文案，生成结果统一在正文、设定和审查面板中展示。
- Planner Agent 已接入 LangChain + Pydantic 结构化输出；调用失败时自动降级到本地剧情节点，保证流程可继续演示。
- Writer Agent 已接入 LangChain + Pydantic 结构化输出；调用失败时自动降级为剧情节点草稿。
- Librarian Agent 已接入 LangChain + Pydantic 结构化输出；调用失败时自动降级为章节摘要设定。
- Reviewer Agent 已接入 LangChain + Pydantic 结构化输出；调用失败时自动降级为基础规则审查。
- 章节流程已拆分为 `Writer -> Reviewer -> 用户确认 -> Librarian`：正文先展示，审查后可自动或手动打回修稿，用户接受章节后再抽取设定。
- `开始创作` 已拆成章节规划、剧情审核、草稿审查三个阶段页，并在页面右侧提供可折叠阶段导航。
- 人物卡片输入已从 JSON 文本框改为可视化表单，支持随窗口宽度自适应多列展示。
- 草稿审查页已将章节正文与审查/设定面板并排展示，降低单页拥挤感。
- 保留现有 FastAPI 与 LangChain 对话链路，后续继续接入真正的 token 流式状态输出和 RAG 长文本记忆库。

当前项目已经基本具备“单个章节”的完整半自动共创能力：用户输入设定，Planner 规划剧情节点，用户审核后 Writer 生成正文，Reviewer 审查并可触发修稿，用户接受后 Librarian 抽取章节记忆。下一阶段重点不再只是单章生成，而是把多个章节串联成一本可持续维护的小说工程。

## 当前能力边界

已具备：

- 单章规划：根据世界观、前文摘要、人物卡和本章要求生成剧情节点。
- 人工审核：用户可以修改 Planner 输出后再进入正文生成。
- 正文生成：Writer 根据确认后的剧情节点生成章节草稿。
- 审查修稿：Reviewer 给出结构化审查意见；不通过时可自动或手动触发 Writer 修稿。
- 设定抽取：用户接受章节后，Librarian 抽取人物状态、世界观增量、道具、地点和伏笔。
- 前端工作台：支持章节创作、人物设定、剧情设定、小说预览和一键发表前瞻。

暂未完成：

- 多章节连续创作还没有形成稳定的章节队列、卷纲和长期进度管理。
- RAG 长文本记忆库尚未真正落地，当前主要依赖会话状态和单次设定抽取。
- Writer 正文生成还不是 token 流式输出，前端仍需等待单次 LLM 请求返回。
- Reviewer 只负责审查和触发修稿，还没有形成多轮版本对比、差异查看和人工定稿记录。
- 小说级结构如作品信息、分卷、主线/支线、伏笔生命周期、角色成长弧线还未建模。

## 下一阶段路线

从“单章可用”走向“正式生成一本小说”，建议按下面顺序推进：

1. 多章节连续创作
   - 增加作品级 `NovelProject` / `VolumePlan` / `ChapterPlan` 概念。
   - 支持从上一章摘要、已确认设定和未回收伏笔中生成下一章。
   - 前端增加章节列表、章节状态、继续写下一章和重写某章能力。

2. 长文本记忆与 RAG
   - 将已接受章节、章节摘要、人物卡、地点、道具、伏笔写入可检索记忆库。
   - Writer 和 Reviewer 在生成/审查前检索相关历史设定，减少长篇上下文遗忘。
   - Librarian 从“展示设定”升级为“维护可检索设定库”。

3. 小说级规划
   - 增加整本书的题材、卖点、主线目标、阶段爽点、分卷结构和结局方向。
   - Planner 不只规划单章，还能根据卷纲控制节奏，避免剧情发散。
   - 加入伏笔生命周期：埋下、强化、误导、回收、废弃。

4. 流式与异步体验
   - Writer 正文生成改为 token 流式输出，边生成边显示。
   - Reviewer 和 Librarian 可放到后台异步执行，减少用户等待。
   - 前端展示真实 Agent 状态，而不是只用预制动态文案。

5. 成稿管理与发布准备
   - 支持章节版本、人工定稿、导出 Markdown / TXT。
   - 增加小说预览目录、章节切换、总字数统计和章节质量概览。
   - 一键发表仍保持前瞻页，待账号安全、平台适配和人工确认机制完善后再接入真实发布。

## 目录结构

```text
novelagent/
├── app/
│   ├── agents/              # LangGraph Agent 节点：Planner / Writer / Librarian / Reviewer
│   │   ├── librarian_chain.py # Librarian 结构化 LLM 输出链
│   │   ├── novel_nodes.py    # 小说工作流节点
│   │   ├── planner_chain.py  # Planner 结构化 LLM 输出链
│   │   ├── reviewer_chain.py # Reviewer 结构化 LLM 输出链
│   │   └── writer_chain.py   # Writer 结构化 LLM 输出链
│   ├── core/                # 应用基础设施：配置、日志、RAG、图编排等
│   │   └── novel_graph.py    # LangGraph 状态图和会话服务
│   ├── models/              # 小说领域模型与 LangGraph 状态定义
│   │   ├── character.py     # CharacterCard 人物卡片
│   │   ├── chapter.py       # PlotBeat 与 ChapterDraft
│   │   ├── librarian.py     # LibrarianOutput 结构化输出
│   │   ├── planner.py       # PlannerOutput 结构化输出
│   │   ├── reviewer.py      # ReviewerOutput 结构化输出
│   │   ├── writer.py        # WriterOutput 结构化输出
│   │   └── state.py         # NovelState 全局状态
│   ├── chain.py             # 现有 LangChain 对话链路
│   ├── novel_routes.py      # /novel 小说工作流接口
│   └── routes.py            # 现有 /chat 流式接口
├── core/
│   └── config.py            # 现有配置管理
├── frontend/
│   ├── index.html           # 前端工作台页面
│   ├── styles.css           # 朴素写作风格与纸张/书本拟物化样式
│   └── app.js               # 调用 /novel API 的交互逻辑
├── schemas/
│   ├── chat.py              # 现有聊天接口 Schema
│   └── novel.py             # 小说工作流 API Schema
├── main.py                  # FastAPI 应用入口
└── readme.md
```

## 核心数据模型

- `CharacterCard`：人物卡片，记录姓名、别名、叙事定位、长期人设、当前心理状态、当前物理状态、关系、物品、秘密和时间线。
- `PlotBeat`：剧情节点，记录节点顺序、摘要、叙事目的、出场人物、地点、冲突、预期结果和连续性约束。
- `ChapterDraft`：章节草稿，记录章节号、标题、采用的剧情节点、正文、审查意见、修订记录、质量评分和草稿状态。
- `NovelState`：LangGraph 全局状态，记录世界观、当前章节、当前阶段、人物图谱、RAG 检索上下文、人工反馈、设定抽取结果、审查反馈和用户接受状态。

## 启动方式

```bash
uvicorn main:app --reload
```

浏览器打开：

```text
http://127.0.0.1:8000/
```

前端工作台包含：

- `总览`：展示小说总字数、当前章节、剧情节点数量、工作流阶段和审查状态。
- `开始创作`：当前主功能，支持生成剧情节点、人工审核修改、继续生成章节草稿。
- `人物设定`：展示 Librarian 抽取出的人物卡片和状态变化。
- `剧情设定`：以横向可滚动鱼骨线展示世界观增量、道具、地点、伏笔和章节摘要。
- `一键发表`：功能前瞻页，仅展示晋江、番茄、起点等平台的未来发布能力，当前不可操作。
- `小说预览`：以正式阅读页形式展示已生成章节正文。

当前仍可调用既有 `POST /chat` 接口，请求体：

```json
{"query": "你的问题"}
```

## 小说工作流 API

生成剧情节点并暂停在 Writer 前：

```bash
curl -X POST http://127.0.0.1:8000/novel/chapters/plan \
  -H "Content-Type: application/json" \
  -d '{
    "global_worldview": "玄幻都市，灵气复苏，主角逐步揭开家族秘密。",
    "chapter_number": 1,
    "previous_summary": "主角刚收到一封神秘信件。",
    "user_instruction": "结尾要留下强悬念",
    "characters": []
  }'
```

接口会返回 `session_id` 和 `plot_beats`。用户确认或修改剧情节点后，提交继续生成正文：

```bash
curl -X POST http://127.0.0.1:8000/novel/chapters/{session_id}/approve \
  -H "Content-Type: application/json" \
  -d '{
    "plot_beats": [],
    "human_feedback": "剧情节点确认，可以继续写作。"
  }'
```

随后可依次触发 Reviewer 审查、Writer 修稿或接受章节后的 Librarian 设定抽取：

```bash
curl -X POST http://127.0.0.1:8000/novel/chapters/{session_id}/review

curl -X POST http://127.0.0.1:8000/novel/chapters/{session_id}/revise \
  -H "Content-Type: application/json" \
  -d '{"human_feedback": "同意按 Reviewer 意见修订。"}'

curl -X POST http://127.0.0.1:8000/novel/chapters/{session_id}/accept \
  -H "Content-Type: application/json" \
  -d '{"human_feedback": "接受本章节。"}'
```

调试时可读取当前会话状态：

```bash
curl http://127.0.0.1:8000/novel/sessions/{session_id}
```

当前 Planner、Writer、Librarian、Reviewer 均已接入基于 LangChain 的 Pydantic 结构化输出，并保留本地降级逻辑。后续可继续接入 RAG 检索、长文本记忆库和真正的 token 流式状态输出。
