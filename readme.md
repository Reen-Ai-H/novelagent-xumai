# 多智能体网文共创引擎

Human-in-the-Loop Web Novel Agent 是一个基于 FastAPI、LangGraph、LangChain 和 RAG 的长篇网文半自动生成系统。它的目标是让大模型参与长篇小说创作时，不再只做一次性文本生成，而是围绕“规划、人工审核、写作、审查、设定抽取、长期记忆”形成可持续推进的创作流程。

项目当前已经可以完成单章创作闭环，并正在从“可演示原型”推进到“稳定化小说工程”：接受章节后会写入长期记忆，作品目录模型和本地 JSON 持久化层已经具备雏形，后续重点是把作品目录持久化正式接入工作流。

## 核心流程

系统采用 LangGraph 状态机架构，多个 Agent 共享并更新同一个 `NovelState`。

```text
Planner -> 人工审核 -> Writer -> Reviewer -> 用户确认 -> Librarian -> 长期记忆
```

- `Planner Agent`：根据世界观、人物卡、前文摘要和用户要求生成本章剧情节点。
- `Writer Agent`：读取用户确认后的剧情节点，并结合 RAG 检索到的长期记忆生成章节草稿。
- `Reviewer Agent`：结合正文、人物卡、世界观和长期记忆检查 OOC、逻辑漏洞、设定冲突和伏笔断裂。
- `Librarian Agent`：只在用户接受章节后抽取章节摘要、世界观增量、人物变化、地点、道具和伏笔。
- `MemoryStore`：将已接受章节的稳定信息写入 `.novel_memory/{project_id}.json`，供后续章节检索。

## 当前阶段

阶段六：稳定化小说工程。

已完成：

- FastAPI 后端入口和静态前端工作台。
- LangGraph 小说工作流：`Planner -> Writer -> Reviewer -> Librarian`。
- Planner 后的人工审核断点：用户可以修改剧情节点后再进入正文生成。
- Writer、Reviewer、Librarian 均接入 LangChain + Pydantic 结构化输出，并保留本地降级逻辑。
- 章节流程拆分为 `Writer -> Reviewer -> 用户确认 -> Librarian`，正文、审查和设定抽取分阶段展示。
- 前端工作台支持总览、章节创作、剧情审核、草稿审查、人物设定、剧情设定、一键发表前瞻和小说预览。
- 新增作品级模型 `NovelProject`、`VolumePlan`、`ChapterRecord`，可在内存中维护章节目录。
- 新增 RAG 记忆模型 `MemoryItem`、`RetrievalContext`。
- 新增本地 JSON 记忆库 `JsonMemoryStore`，按作品写入 `.novel_memory/{project_id}.json`。
- Writer / Reviewer 会在生成或审查前检索长期记忆并注入 prompt。
- 已修复 RAG 闭环：长期记忆只在 `accept_chapter` 中，Librarian 成功抽取且章节进入 `completed` 后写入；Writer 草稿和 Reviewer 审查阶段不会污染记忆库。
- 新增 `tests/test_accept_chapter_memory.py`，验证接受章节后会生成 JSON 记忆文件并产生 `MemoryItem`。
- 新增 `app/core/project_store.py`，提供 `ProjectStore` 抽象和 `JsonProjectStore` 本地 JSON 持久化实现。
- 新增 `requirements.txt` 和 `.env.example`，整理启动依赖与环境变量模板。

仍未完成：

- `JsonProjectStore` 已完成独立存储层，但尚未接入 `NovelWorkflowService`；当前 API 读取的作品目录仍主要来自进程内内存。
- 服务重启后，章节目录还不能自动从 `.novel_projects/{project_id}.json` 恢复。
- 分卷规划 `VolumePlan` 还没有接入 Planner 的节奏控制。
- 章节重写、版本记录、修稿对比和人工定稿记录尚未完成。
- 当前 RAG 是本地 JSON + 关键词重叠检索，尚未接入 embedding、Chroma、FAISS 等语义向量库。
- Writer 正文生成还不是 token 流式输出。
- 小说级主线/支线、伏笔生命周期、角色成长弧线还未完整建模。

## 技术栈

- Python 3.10+
- FastAPI
- LangGraph
- LangChain / LangChain OpenAI
- Pydantic v2
- pydantic-settings / python-dotenv
- 原生 HTML / CSS / JavaScript 前端
- 本地 JSON RAG 记忆库
- 本地 JSON 作品目录持久化层

## 目录结构

```text
novelagent/
├── app/
│   ├── agents/
│   │   ├── librarian_chain.py     # Librarian 结构化 LLM 输出链
│   │   ├── novel_nodes.py         # LangGraph 节点：Planner / Writer / Reviewer / Librarian
│   │   ├── planner_chain.py       # Planner 结构化 LLM 输出链
│   │   ├── reviewer_chain.py      # Reviewer 结构化 LLM 输出链
│   │   └── writer_chain.py        # Writer 结构化 LLM 输出链
│   ├── core/
│   │   ├── memory.py              # RAG 记忆库抽象与本地 JSON 实现
│   │   ├── novel_graph.py         # LangGraph 状态图和会话服务
│   │   ├── project_store.py       # 作品目录持久化抽象与本地 JSON 实现
│   │   └── retriever.py           # RAG 检索和记忆条目构造
│   ├── models/
│   │   ├── character.py           # CharacterCard
│   │   ├── chapter.py             # PlotBeat / ChapterDraft
│   │   ├── librarian.py           # LibrarianOutput
│   │   ├── memory.py              # MemoryItem / RetrievalContext
│   │   ├── planner.py             # PlannerOutput
│   │   ├── project.py             # NovelProject / VolumePlan / ChapterRecord
│   │   ├── reviewer.py            # ReviewerOutput
│   │   ├── state.py               # NovelState
│   │   └── writer.py              # WriterOutput
│   ├── chain.py                   # 保留的通用 LangChain 对话链路
│   ├── novel_routes.py            # /novel 小说工作流 API
│   └── routes.py                  # /chat 流式聊天 API
├── core/
│   └── config.py                  # 环境变量和 LLM 配置
├── frontend/
│   ├── app.js                     # 前端工作台交互逻辑
│   ├── index.html                 # 前端工作台页面
│   └── styles.css                 # 前端样式
├── schemas/
│   ├── chat.py                    # 通用聊天接口 Schema
│   └── novel.py                   # 小说工作流 API Schema
├── tests/
│   ├── __init__.py
│   └── test_accept_chapter_memory.py
├── .env.example                   # 环境变量模板
├── requirements.txt               # Python 运行依赖
├── main.py                        # FastAPI 应用入口
└── readme.md
```

运行时会产生两个本地目录，均已加入 `.gitignore`：

```text
.novel_memory/       # RAG 长期记忆
.novel_projects/     # 作品目录持久化文件，存储层已完成，工作流接入待完成
```

## 核心数据模型

- `CharacterCard`：人物卡片，记录姓名、别名、叙事定位、长期人设、当前心理状态、当前物理状态、关系、物品、秘密和时间线。
- `PlotBeat`：剧情节点，记录节点顺序、摘要、叙事目的、出场人物、地点、冲突、预期结果和连续性约束。
- `ChapterDraft`：章节草稿，记录章节号、标题、采用的剧情节点、正文、审查意见、修订记录、质量评分和草稿状态。
- `NovelState`：LangGraph 全局状态，记录世界观、章节号、当前阶段、人物图谱、剧情节点、草稿、RAG 检索结果、人工反馈、审查反馈和设定抽取结果。
- `MemoryItem`：长期记忆条目，记录作品 ID、分类、标题、正文、来源章节、标签、重要度和来源信息。
- `RetrievalContext`：一次 RAG 检索命中的上下文，记录命中条目、相关性分数、命中原因和可注入 prompt 的格式化文本。
- `NovelProject`：作品级工程，记录作品标题、世界观、分卷规划、章节目录、当前章节、最近会话和总字数。
- `VolumePlan`：分卷规划模型，预留分卷标题、主线摘要和章节范围。
- `ChapterRecord`：章节目录记录，记录章节状态、关联会话、摘要、字数、草稿快照和更新时间。

## 安装与启动

当前本机验证使用的 conda 环境是 `ai_project`。如果旧文档或旧命令里出现 `ai-agent`，请以当前可用环境为准，或把下面命令中的环境名替换成你的实际环境。

准备环境：

```bash
conda activate ai_project
python -m pip install -r requirements.txt
copy .env.example .env
```

编辑 `.env`，填入真实配置。不要提交真实 `.env`。

```env
OPENAI_API_KEY="sk-your-api-key"
OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL="qwen3.6-plus"
LLM_TEMPERATURE="0.7"
```

启动服务：

```bash
conda activate ai_project
python -m uvicorn main:app --reload
```

如果当前 shell 没有 `conda` 命令，也可以直接使用本机已验证的 Python 路径：

```bash
C:\Users\asus\anaconda3\envs\ai_project\python.exe -m uvicorn main:app --reload
```

浏览器打开：

```text
http://127.0.0.1:8000/
```

## 前端工作台

- `总览`：展示小说总字数、当前章节、剧情节点数量、工作流阶段、审查状态和章节目录。
- `开始创作`：输入世界观、章节号、前文摘要、创作要求和人物卡。
- `剧情审核`：展示 Planner 输出的剧情节点，用户可逐项修改后提交。
- `草稿审查`：展示 Writer 正文、Reviewer 审查意见、修稿按钮和接受章节按钮。
- `人物设定`：展示 Librarian 抽取出的人物卡片和状态变化。
- `剧情设定`：以横向鱼骨线展示世界观增量、道具、地点、伏笔和章节摘要。
- `一键发表`：功能前瞻页，当前不可操作。
- `小说预览`：以阅读页形式展示当前选中章节正文。

## 小说工作流 API

生成剧情节点并暂停在 Writer 前：

```bash
curl -X POST http://127.0.0.1:8000/novel/chapters/plan \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "default",
    "project_title": "月光禁区",
    "global_worldview": "玄幻都市，灵气复苏，主角逐步揭开家族秘密。",
    "chapter_number": 1,
    "previous_summary": "主角刚收到一封神秘信件。",
    "user_instruction": "结尾要留下强悬念",
    "characters": []
  }'
```

提交人工确认后的剧情节点，生成章节草稿：

```bash
curl -X POST http://127.0.0.1:8000/novel/chapters/{session_id}/approve \
  -H "Content-Type: application/json" \
  -d '{
    "plot_beats": [],
    "human_feedback": "剧情节点确认，可以继续写作。"
  }'
```

触发 Reviewer 审查：

```bash
curl -X POST http://127.0.0.1:8000/novel/chapters/{session_id}/review
```

根据 Reviewer 意见修稿：

```bash
curl -X POST http://127.0.0.1:8000/novel/chapters/{session_id}/revise \
  -H "Content-Type: application/json" \
  -d '{"human_feedback": "同意按 Reviewer 意见修订。"}'
```

接受章节并触发 Librarian 抽取设定。只有这个阶段会写入长期记忆：

```bash
curl -X POST http://127.0.0.1:8000/novel/chapters/{session_id}/accept \
  -H "Content-Type: application/json" \
  -d '{"human_feedback": "接受本章节。"}'
```

读取会话状态：

```bash
curl http://127.0.0.1:8000/novel/sessions/{session_id}
```

读取作品目录：

```bash
curl http://127.0.0.1:8000/novel/projects/current
curl http://127.0.0.1:8000/novel/projects/default
```

基于上一章摘要继续规划下一章：

```bash
curl -X POST http://127.0.0.1:8000/novel/projects/default/chapters/next \
  -H "Content-Type: application/json" \
  -d '{
    "user_instruction": "延续上一章悬念，开头承接钥匙异动。",
    "characters": []
  }'
```

保留的通用聊天接口：

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "你的问题"}'
```

## RAG 长文本记忆

当前 RAG 是轻量本地实现，重点是先把接口和工作流稳定下来。

写入路径：

```text
.novel_memory/{project_id}.json
```

相关文件：

- `app/models/memory.py`：定义 `MemoryItem` 和 `RetrievalContext`。
- `app/core/memory.py`：定义 `MemoryStore` 抽象和 `JsonMemoryStore` 本地 JSON 实现。
- `app/core/retriever.py`：把 `NovelState` 转成检索 query，并把最终章节状态转成 `MemoryItem`。
- `app/agents/novel_nodes.py`：Writer / Reviewer 调用 RAG 检索。
- `app/core/novel_graph.py`：`accept_chapter` 在章节完成后写入长期记忆。

检索流程：

```text
NovelState
-> _build_query
-> JsonMemoryStore.search
-> RetrievalContext
-> format_retrieved_context
-> 注入 Writer / Reviewer prompt
```

写入流程：

```text
用户接受章节
-> Librarian 抽取设定
-> current_stage = completed
-> build_memory_items_from_state
-> memory_store.add_items
-> .novel_memory/{project_id}.json
```

当前检索策略：

- 英文/数字按正则切词。
- 中文按连续汉字生成二字词。
- 使用 query 和记忆条目的关键词重叠做召回。
- 根据关键词重叠度、记忆重要度、章节距离、记忆分类加权排序。

## 作品目录持久化

`app/core/project_store.py` 已新增独立持久化层：

- `ProjectStore`：抽象接口。
- `JsonProjectStore`：本地 JSON 实现。
- `save_project(project)`：保存 `NovelProject`。
- `load_project(project_id)`：读取指定作品。
- `list_projects()`：列出所有本地作品。
- `delete_project(project_id)`：删除作品目录文件。

写入路径：

```text
.novel_projects/{project_id}.json
```

当前状态：存储层已完成，但还没有接入 `NovelWorkflowService`。下一步应在 `_ensure_project`、`_upsert_chapter_record`、`get_project` 等路径中加载和保存 `NovelProject`，让服务重启后仍能恢复章节目录。

## 验证命令

建议在 `ai_project` 环境中执行：

```bash
conda activate ai_project

python -m compileall app schemas tests main.py

python -m unittest tests.test_accept_chapter_memory

python -c "from app.core.novel_graph import build_novel_graph; graph=build_novel_graph(); print('graph_ok')"

python -c "import main; from app.novel_routes import router; print('main_import_ok'); print(len(router.routes))"

python -m uvicorn main:app --reload
```

如果 `conda` 不在 PATH 中，可直接使用：

```bash
C:\Users\asus\anaconda3\envs\ai_project\python.exe -m compileall app schemas tests main.py
C:\Users\asus\anaconda3\envs\ai_project\python.exe -m unittest tests.test_accept_chapter_memory
C:\Users\asus\anaconda3\envs\ai_project\python.exe -c "from app.core.novel_graph import build_novel_graph; graph=build_novel_graph(); print('graph_ok')"
C:\Users\asus\anaconda3\envs\ai_project\python.exe -c "import main; from app.novel_routes import router; print('main_import_ok'); print(len(router.routes))"
```

本次 README 更新前已通过：

```text
compileall: OK
tests.test_accept_chapter_memory: OK
```

## 下一步路线

1. 接入作品目录持久化
   - 将 `JsonProjectStore` 接入 `NovelWorkflowService`。
   - 规划、审查、修稿、接受章节后自动保存 `NovelProject`。
   - 服务启动或首次读取时从 `.novel_projects/{project_id}.json` 恢复目录。

2. 章节版本与重写
   - 增加章节版本号。
   - 保存原草稿、Reviewer 修订意见、修订稿和人工定稿。
   - 支持版本对比和回滚。

3. RAG 升级
   - 保留 `MemoryStore` 接口。
   - 新增 embedding 字段和语义检索实现。
   - 可替换接入 Chroma、FAISS 或其它向量库。

4. 流式与异步体验
   - Writer 正文改成 token 流式输出。
   - Reviewer 和 Librarian 后台执行。
   - 前端展示真实 Agent 状态，而不是预制动态文案。

5. 小说级规划
   - 增加全书卖点、主线目标、分卷节奏、高潮节点和结局方向。
   - Planner 基于卷纲控制单章节奏。
   - 建模伏笔生命周期：埋下、强化、误导、回收、废弃。
