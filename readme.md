# 多智能体网文共创台

Human-in-the-Loop Web Novel Agent 是一个面向长篇网文创作的 AI 共创工作台。项目目标不是一次性生成一段小说，而是把“开书规划、章节生成、AI 审查、人工确认、设定沉淀、长期记忆、继续更新、多章节推进”串成可持续运行的生产流程。

当前项目已从单章 Demo 进入作品工程化阶段：后端已经具备作品 JSON 持久化、章节目录、全文规划、下一章预填、多章节批量任务、章节预览和 RAG 长期记忆闭环；前端已经有首页、作品工作台、章节创作、全文规划、多章节任务、设定页和阅读器雏形。下一阶段重点是把网页端体验打磨顺滑，再考虑手机端迁移。

## 当前产品需求

### 1. 首页与作品管理

- 进入系统后先看到首页，而不是直接进入章节工作台。
- 首页展示已经创作过的作品卡片，包括标题、摘要、章节数、完成章节数、字数、最近章节、最近更新时间、是否已有全文规划、是否已有下一章预填。
- 首页可以新建作品，也可以从作品卡片进入工作台、继续创作或打开小说预览。
- 新建作品不应强迫用户填完所有设定；作品名、题材、世界观、主角设定等信息至少填写一项即可启动。
- 新书创建应先生成可编辑的作品设定草案，再进入全文规划草案确认。

### 2. 新书流程

新书流程应服务于“帮用户把模糊想法补成可写的作品工程”：

```text
首页新建作品 -> 任填至少一项设定 -> AI 补全作品设定草案 -> 用户编辑确认
-> 创建 NovelProject -> 生成全文规划草案 -> 用户确认/修改 -> 第一章 Planner 输入
```

新书阶段需要沉淀：

- 作品标题与首页摘要。
- 作品级世界观。
- 人物初始设定。
- 全文规划：故事前提、核心冲突、结局方向、主题/爽点、目标章节数。
- 分卷规划。
- 章节规划列表。

### 3. 旧书更新流程

旧书更新不能等同于开新书。用户点击继续写下一章时，不应该立即开始 Planner，而应该进入下一章工作区，并自动预填输入。

预填来源包括：

- 已完成章节的摘要。
- 已确认世界观和稳定设定。
- 当前人物状态。
- 未解决伏笔。
- 上一章结尾钩子。
- 全文规划或章节规划中命中的下一章规划。
- 系统推荐的下一章创作方向。
- 用户可编辑的本章创作要求。

当前后端通过 `prepare-next` 生成 `NextChapterSeed`，只负责准备输入，不触发正式 Planner；用户确认后才调用正式章节规划接口。

### 4. 单章节创作闭环

单章流程是项目的核心生产闭环：

```text
Planner -> 人工确认剧情节点 -> Writer -> Reviewer -> 人工接受/修订 -> Librarian -> 长期记忆
```

职责边界：

- `Planner`：生成本章剧情节点和结构。
- 人工审核：用户可修改剧情节点，确认后才进入正文写作。
- `Writer`：根据确认后的剧情节点、作品设定、前文摘要和 RAG 记忆生成章节草稿。
- `Reviewer`：严格审查正文质量、承接、人物动机、设定冲突、伏笔回应和节奏重复。
- 人工确认：用户决定接受入库或要求修订。
- `Librarian`：只在用户接受章节后抽取稳定设定、人物变化、章节摘要和伏笔信息。
- `MemoryStore`：只保存已经被接受的稳定信息。

长期记忆写入边界非常重要：

- Planner 阶段不写入长期记忆。
- Writer 草稿阶段不写入长期记忆。
- Reviewer 审查阶段不写入长期记忆。
- 批量草稿生成阶段不写入长期记忆。
- 只有 `accept_chapter` 成功完成且 Librarian 抽取完成后，才写入 `.novel_memory/{project_id}.json`。

### 5. 多章节批量流程

多章节功能不是简单循环生成正文，而是一次性推进多个章节，并保留逐章确认权。

目标流程：

```text
批量规划 3-10 章 -> 用户确认/修改章节规划
-> 批量生成草稿 -> 批量 AI 审查
-> 逐章进入待接受或待修订队列
-> 用户逐章接受/修订
-> accept 后才写长期记忆
```

当前要求：

- 一次批量范围限制为 3-10 章。
- 默认起始章应根据已有章节自动推断，而不是固定从第 1 章开始。
- 如果批量范围内已有章节，默认不能静默覆盖。
- 覆盖策略支持：
  - `block`：发现已有章节直接阻止。
  - `compare`：生成候选稿，保留原稿，供用户对比。
  - `replace`：明确替换。
  - `keep_existing`：跳过已有章节。
- 批量生成需要给后续章节传递临时上下文，例如上一章草稿摘要、结尾钩子、人物状态，避免第 2 章和第 4 章内容重复。
- 临时上下文只放在 `NovelState.temporary_context`，不污染长期记忆。
- AI 审查在批量第一稿中应更严格，默认 8.5 分以下不通过，优先打回修订。

### 6. 全文规划与章节规划

全文规划不是一次性死表单，而是作品级长期控制台。用户可以随时回来修改。

当前规划数据包括：

- `FullNovelPlan`：故事前提、核心冲突、结局方向、主题/爽点、目标章节数、备注。
- `VolumePlan`：分卷标题、分卷主线、章节范围。
- `ChapterOutline`：章节号、标题、所属分卷、章节摘要、叙事目的、剧情节点。

后续 Planner 应逐步更多消费这些规划，保证长篇节奏、章节目标和伏笔生命周期一致。

### 7. 人物设定与剧情设定

项目需要作品级设定库，而不是只展示当前章节抽取结果。

当前后端已有：

- `character_codex`：作品级人物设定集。
- `lore_codex`：作品级剧情与世界观设定集。
- `GET /novel/projects/{project_id}/codex`：读取项目级人物和设定聚合。

产品要求：

- 人物设定页重新进入后仍能看到作品级人物设定。
- 剧情设定不应依赖临时鱼骨图形式，应转为可浏览、可编辑、可被后续 Planner/Writer 消费的设定库。
- 设定来源要区分“AI 抽取建议”和“用户确认入库”。

### 8. 小说预览与阅读器

小说预览应像读者阅读器，而不是跳回草稿设置页。

要求：

- 有章节目录。
- 有上一章/下一章切换。
- 总览点击第几章时默认进入小说预览。
- 未完成章节显示状态和处理入口，不假装是已完成正文。
- 已有候选稿时可以展示原稿、候选稿和对比摘要。

## 当前已实现功能

### 后端能力

- FastAPI 服务入口和静态前端挂载。
- LangGraph 小说状态机。
- Planner / Writer / Reviewer / Librarian 多智能体节点。
- 单章工作流：规划、人工确认、写作、审查、修订、接受。
- 本地 JSON RAG 记忆库：`.novel_memory/{project_id}.json`。
- RAG 检索上下文注入 Writer / Reviewer。
- RAG 写入闭环修正：只在章节接受后写入长期记忆。
- 作品级模型 `NovelProject`。
- 本地 JSON 作品持久化：`.novel_projects/{project_id}.json`。
- 原子写入：临时文件写入后 `replace`。
- `project_id` 简单校验，避免路径穿越。
- 首页项目卡片响应 `ProjectCard`。
- 全文规划、分卷规划、章节规划模型。
- 下一章输入快照 `NextChapterSeed`。
- 批量任务状态 `BatchGenerationRun` 和逐章结果 `BatchChapterResult`。
- 章节预览响应 `ChapterPreviewResponse`，章节不存在时也返回可处理状态。
- 批量覆盖策略和已有章节冲突提示。
- 批量生成后自动进入待接受/待修订队列。
- 批量生成临时上下文链路。
- 严格 Reviewer：8.5 分以下默认不通过，批量第一稿倾向打回。

### 前端能力

- 首页作品入口。
- 首页新建作品流程雏形。
- 作品工作台。
- 一级导航：总览、章节创作、全文规划、多章节任务、人物设定、剧情设定、小说预览、一键发表。
- 继续写下一章改为先 `prepare-next` 预填，不直接 Planner。
- 全文规划编辑页。
- 多章节规划/生成页。
- 批量任务逐章队列。
- 小说阅读器雏形：目录、状态、上一章、下一章。
- 状态文案逐步改为“待审查”“待接受入库”“建议修订”“已完成入库”等产品化表达。

## 核心数据模型

### NovelProject

`NovelProject` 是作品工程的根模型，保存：

- `project_id`
- `title`
- `project_brief`
- `global_worldview`
- `character_codex`
- `lore_codex`
- `full_plan`
- `volumes`
- `chapter_plans`
- `chapters`
- `next_chapter_input_snapshot`
- `batch_tasks`
- `latest_edited_chapter_number`
- `latest_session_id`
- `total_word_count`
- `created_at`
- `updated_at`

### ChapterRecord

章节目录记录，保存章节状态、草稿、审查结果、候选稿和对比摘要。

主要状态：

- `planned`
- `drafted`
- `reviewed`
- `needs_revision`
- `approved`
- `completed`
- `failed`

### NextChapterSeed

下一章输入快照，由 `prepare-next` 生成，供前端展示和用户编辑。

主要字段：

- 下一章章节号。
- 世界观和已确认设定。
- 前文摘要。
- 当前人物状态。
- 未解决伏笔。
- 上一章结尾钩子。
- 推荐创作方向。
- 命中的章节规划。
- 用户可编辑创作要求。

### BatchGenerationRun

批量任务记录，保存任务状态、章节号、会话映射、逐章结果、覆盖策略、待接受队列和待修订队列。

## API 概览

### 作品与首页

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/novel/projects` | 创建作品 |
| `GET` | `/novel/projects` | 首页作品卡片列表 |
| `GET` | `/novel/projects/current` | 当前默认作品 |
| `GET` | `/novel/projects/{project_id}` | 作品完整状态 |
| `GET` | `/novel/projects/{project_id}/codex` | 作品级人物与剧情设定 |

### 全文规划与下一章准备

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/novel/projects/{project_id}/prepare-next` | 生成/读取下一章预填输入 |
| `POST` | `/novel/projects/{project_id}/prepare-next` | 带用户要求生成下一章预填输入 |
| `POST` | `/novel/projects/{project_id}/full-plan` | 生成或保存全文规划骨架 |
| `PUT` | `/novel/projects/{project_id}/full-plan` | 更新全文规划、分卷规划、章节规划 |
| `POST` | `/novel/projects/{project_id}/chapters/next` | 用户确认 seed 后正式规划下一章 |

### 单章工作流

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/novel/chapters/plan` | 生成章节剧情节点 |
| `POST` | `/novel/chapters/{session_id}/approve` | 人工确认剧情节点并进入 Writer |
| `POST` | `/novel/chapters/{session_id}/review` | 对草稿执行 Reviewer 审查 |
| `POST` | `/novel/chapters/{session_id}/revise` | 根据审查意见修订 |
| `POST` | `/novel/chapters/{session_id}/accept` | 接受章节，触发 Librarian 和长期记忆写入 |
| `GET` | `/novel/sessions/{session_id}` | 查询章节会话状态 |

### 批量章节

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/novel/projects/{project_id}/batch/plan` | 批量规划 3-10 章 |
| `POST` | `/novel/projects/{project_id}/batch/generate` | 批量生成草稿并审查 |

`batch/generate` 的 `overwrite_policy`：

- `block`：默认策略，已有章节返回 `409`。
- `compare`：生成候选稿并保留原稿，供对比。
- `replace`：明确覆盖。
- `keep_existing`：跳过已有章节。

### 阅读器

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/novel/projects/{project_id}/chapters/{chapter_number}` | 获取章节预览、正文、状态、上下章和候选稿对比 |

章节不存在时也返回 `200`，状态为 `missing`，前端可以显示“去处理本章”。

## 运行项目

### 1. 创建环境

推荐使用当前工程约定的 `ai_project` 环境。如果已经存在，可以直接跳过创建步骤。

```powershell
conda create -n ai_project python=3.10
conda activate ai_project
pip install -r requirements.txt
```

也可以直接使用当前机器上的解释器：

```powershell
C:\Users\asus\anaconda3\envs\ai_project\python.exe -m pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入真实 Key。

```env
OPENAI_API_KEY="sk-your-api-key"
OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL="qwen3.6-plus"
LLM_TEMPERATURE="0.7"
```

后端使用 `core/config.py` 读取 `.env`。

### 3. 启动服务

```powershell
C:\Users\asus\anaconda3\envs\ai_project\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

访问：

```text
http://127.0.0.1:8000/
```

API 文档：

```text
http://127.0.0.1:8000/docs
```

## 本地数据

运行过程中会生成两个本地目录：

```text
.novel_projects/   # 作品工程 JSON
.novel_memory/     # 已接受章节抽取出的长期记忆 JSON
```

这两个目录已加入 `.gitignore`，不会提交到仓库。

注意：作品目录已经持久化，但 LangGraph 的会话检查点当前仍主要依赖进程内状态。服务重启后，作品列表、章节目录、草稿快照可以从 `.novel_projects` 恢复；正在进行中的细粒度 LangGraph checkpoint 还不是完整持久化队列。

## 验证命令

```powershell
C:\Users\asus\anaconda3\envs\ai_project\python.exe -m compileall app schemas main.py tests
C:\Users\asus\anaconda3\envs\ai_project\python.exe -m unittest discover -s tests -v
C:\Users\asus\anaconda3\envs\ai_project\python.exe -c "import main; print('main_import_ok'); print(len(main.app.routes))"
```

最近一次本地验证结果：

- `compileall` 通过。
- `unittest discover`：10 tests OK。
- `main_import_ok`。
- 当前 FastAPI 路由数量：25。

## 已知问题与下一步

### P0：网页端体验一致性

- 首页作品卡片接口已经返回 `ProjectCard`，前端部分位置仍可能按完整 `NovelProject.chapters` 读取数据，需要统一改为使用卡片字段。
- 工作台视觉已经开始从旧棕色纸张风格迁移，但 CSS 中仍可能残留旧组件类名和局部色值，需要一次完整视觉清理。
- 左侧导航、阅读器、总览章节点击、批量队列的状态跳转需要继续用浏览器逐项回归。

### P0：批量生成质量闭环

- 批量流程已经具备规划、生成、审查和逐章状态队列，但前端的“逐章接受/修订/对比替换”还需要完整验证。
- 批量章节之间虽然已有临时上下文链路，但仍要通过真实生成样本检查重复剧情、钩子承接和人物状态延续。
- 已有章节冲突默认 `block`，前端必须明确提示用户，不允许静默覆盖。

### P1：设定库产品化

- 后端已有 `character_codex` 和 `lore_codex`，但前端设定页还需要从临时抽取展示升级为作品级设定库。
- 剧情设定建议抛弃鱼骨线主展示，改为“设定条目 + 来源章节 + 状态 + 可编辑确认”的结构。
- 需要区分 AI 建议、用户确认、长期记忆、当前草稿临时信息。

### P1：全文规划真正驱动章节

- 当前 `POST /full-plan` 主要是稳定结构化骨架生成/保存入口，不是完整 LLM 自动全文大纲生成器。
- Planner 需要更深入消费全文规划、分卷目标和章节规划，而不是只作为前端展示资料。
- 需要支持用户随时修改全文规划后，对后续章节 seed 和 batch plan 产生影响。

### P2：工程化增强

- RAG 当前是本地 JSON + 关键词检索，未来可升级为 embedding + 向量库。
- 批量任务当前是同步执行，未来可迁移到异步任务队列。
- Writer 暂未流式输出。
- 草稿版本历史、对比 diff、回滚和人工定稿记录仍需补齐。
- 手机端迁移应放在网页端流程稳定之后。

## 建议分工

### 窗口 1：核心工作流与质量

- 保持 RAG 写入边界：只有接受章节后写长期记忆。
- 持续优化 Reviewer 严格度和 Writer 批量上下文承接。
- 检查 batch 临时上下文是否足以避免章节重复。
- 推进 Planner 对全文规划和章节规划的真实消费。

### 窗口 2：数据模型与 API 合同

- 稳定 ProjectCard、ChapterPreviewResponse、BatchTaskResponse 合同。
- 补齐设定库 API：确认、编辑、删除、来源追踪。
- 完善章节候选稿对比、版本历史和覆盖策略。
- 评估 LangGraph checkpoint 持久化方案。

### 窗口 3：网页端产品体验

- 彻底统一视觉风格，清理旧棕色/纸张风残留。
- 修正首页作品卡片字段映射。
- 打磨新书流程：少填也可启动，AI 补完后再确认。
- 打磨旧书流程：prepare-next 工作区必须可编辑，确认后才 Planner。
- 完整实现阅读器目录、上下章切换、章节状态入口。
- 完整实现批量任务逐章接受、修订、对比替换。

## 项目定位

这个项目最终要成为“长篇小说生产工作台”，而不是聊天框或一次性生成器。它的核心价值在于：

- 长篇上下文可持续。
- 设定不会被草稿污染。
- AI 负责规划、写作、审查和抽取。
- 用户保留关键确认权。
- 每一章都能沉淀成下一章可用的作品资产。

