# 叙脉架构说明

## 现状边界

叙脉是 FastAPI + 原生 HTML/CSS/JavaScript 的本地开发版。`main.py` 创建应用、挂载静态前端、注册新 API 与旧 `/novel` 兼容路由，并在生命周期内启动可恢复的后台 AI worker。当前实现不是生产部署，也没有云端同步、支付或管理员平面。

## 分层

```text
frontend/index.html + app.js + styles.css
        ↓ fetch / 应用内导航
FastAPI routes (entry / independent / ai / archive / novel)
        ↓ 会话、owner、mode、revision 校验
core services (account / entry / independent / ai / transaction)
        ↓ 原子 JSON store + 安全元数据
.novel_accounts  .novel_independent  .novel_ai
.novel_projects  .novel_memory       .novel_transactions
.novel_deconstruction
```

- `app/entry_routes.py`：登录、书架、通知和应用入口。
- `app/independent_routes.py`、`app/archive_routes.py`：独立作品、稿本、编辑、故事档案和恢复。
- `app/ai_routes.py`：创作室、蓝图、导演运行、选择、暂停/重试和状态恢复。
- `app/novel_routes.py`：旧 `/novel` 合同；保留 16 个路径/19 个 HTTP 操作，并执行鉴权和归属校验。
- `app/core/`：账户、作品、独立创作、AI、条目和跨 store 事务服务。
- `schemas/`：API 和持久化边界的 Pydantic 合同。
- `app/agents/llm_runtime.py`：唯一可注入模型运行时。结构化阶段严格 JSON，正文阶段使用经过长度、截断、私密信息校验的纯文本协议。

## 数据与身份

浏览器的 cookie 只承载 HttpOnly 会话；作品、正文、蓝图、通知、后台任务、usage 安全元数据和版本都以服务端本地 JSON 为准。所有新接口和旧兼容接口都检查当前账户、作品 owner 和 mode。没有 owner 的历史文件继续留存，但不会被首次访问的新账户认领。

`.novel_*` 是用户数据或运行数据，既不提交到 Git，也不在升级时批量迁移。备份和恢复必须在服务停止后进行。

## 独立创作状态

独立导入先生成预览，作者确认后才写正式稿本。正文自动保存使用 revision 门禁；作者修改旧章先进入同一批 `pending_changes`，最后选择轻改忽略或全文重建。章末任务分析人物、剧情线、伏笔、疑问点并创建章节快照。历史快照只读，旧稿本保留业务设定的 30 天恢复期。

阶段 34 将旧版本冻结为最后确认的正式正文，历史预览和恢复不得带入其未确认草稿。存在待确认修改时拒绝历史恢复；同一恢复结果的重复请求复用既有版本和任务。

## 阶段 34 的定向扩展

继续使用模块化单体，不拆微服务、不迁移用户数据库。保留确定性深度报告 `2.0`，模型细读报告使用独立 `model.1` 标记和 `AnalysisReport`，两者不得在同一字段下靠猜测混用。旧预览模型报告读入时转换标记，原始文件不批量重写。

模型报告经章节范围、逐字且唯一引文、当前稿本版本、范围内容指纹和写锁校验后才发布。API 可携带 `document_id` 读取指定报告的证据，防止不同报告重复使用 Q1 等局部编号时串卷。旧报告保持只读，不将历史证据默认为当前正文。

`BookAnalysis` 保存分段游标、派生草稿、阅读摘要和预算。模型只声明新增/修正/撤回对象，程序稳定映射 ID、合并及校验；全书综合是独立步骤。服务启动恢复 running 任务，不依赖浏览器 GET。未知 usage 和在途请求保留保守预算占用，不能重启后清零。

MiMo 通过唯一运行时接入，官方主机使用 `max_completion_tokens` 和 SSE。只有完整结束并通过输出合同才采用结果；错误只对外提供脱敏代码。凭据不进前端、报告、Git 或测试，真实质量验收与离线 fake 测试分离。

## 阶段 35 的识别与阅读组织

阶段 35 将导入标题解析抽到 `chapter_parser.py`，人物候选/身份/重要性抽到 `person_recognition.py`，原文阅读段落抽到 `reading_projection.py`。保留确定性 `2.0` 合同，使用 `engine_revision=stage35.relevance.1` 区分新版规则。没有当前引擎标记的同源旧报告只读可见并提示更新；显式更新生成新 ID，重复更新幂等，不在读取时改写历史。

`reading_segments` 是细节事件的来源投影，不是模型大纲。字符范围使用正文 UTF-16 偏移，原事件与证据继续保留；人物候选与正式卡片分别记录，重要性不靠固定人数截断。前端 `report-browser.js` 负责全文记录搜索/筛选/分页，`rule-report.js` 负责规则摘要和懒展开，`deconstruction-report.js` 保留模型报告渲染。规则与模型来源显式显示，模型不会因打开页面或导入默认自动付费。

阶段35的 Source-ID 引文选择当时仅为私有试验；阶段37已将来源编号绑定接入产品，见下节。真实运行与内容质量仍以当前 PROGRESS 的证据为准。

## 阶段 36 的章内导航与图形阅读（继承合同）

下列章内目录仅保留兼容实现；阶段37当前工作台改为真正章节，不再以章内目录代替分章。

章内目录是当前编辑正文的只读投影，不是正式章节迁移。`workspace.chapter_sections` 按 `chapter_id` 返回 `section_id/title/start/end/kind`；导入预览按 `chapter_number` 返回相同结构。范围是当前 `content` 的 UTF-16 半开区间；前端编辑后不得继续使用旧偏移。DOCX 标题层级提示仅在导入内容指纹仍匹配时参与识别。

人物图和剧情路径只投影现有报告：共同参与事件不等于亲属或敌友，排列顺序不等于因果，原报告的明确连线类型必须保留。图中紧凑节点与选中详情分层，完整记录仍可通过搜索、分页或文本列表访问。游戏式路径只借鉴阅读形式，不生成正文没有的选择或分支。

独立创作隐藏常规版本记录与恢复入口，但不移除旧版本、恢复 API、来源校验和 AI 工作区兼容能力。旧章保存仍保留 revision/CAS 与待确认修改合同；局部重新拆解未在本阶段实现。

## 阶段 37 的正式分章与来源绑定

接口细节见 [STAGE_37_CONTRACT](STAGE_37_CONTRACT.md)。`chapter_segmentation.py` 为导入及旧稿重分章建立服务端预览；边界使用 UTF-16 半开区间，不允许拆开代理对或 CRLF。客户端只能提交起点和标题，服务器根据原文重算每章，不接收替换正文。编号缺口仅在同层明确编号之间、唯一裸题且两侧正文充分时保守补识别；不硬编码样本标题。

确认预览检查有效期、预览 revision、当前版本、来源 hash、各章 revision、未确认草稿和待定事务。成功后生成新当前版本与新章 ID，旧版本冻结为正式正文；重复确认幂等。旧拆解继续绑定旧版本，由 `read_source_snapshot` 提供可核对的只读原文，不跳到当前同编号章节。

`analysis_grounding.py` 根据正式章节建立原句来源库。模型在 `GroundedReport` / `GroundedDelta` 中选择来源 ID，服务器逐字绑定唯一原文后，再运行完整报告与章节范围校验。适用于章节试拆、全文分段和综合；没有手工补造引文或宽松模糊匹配。`model.1` 新增可选 `character_relations`，旧报告默认空列表；语义边保留来源、方向及事实/传闻/推断状态，共同经历单独展示。

章节试拆与全文分析共用 `DurableModelBudget`，账本位于拆解数据目录的 `model-budgets/<scope>.json`。每次真实请求和格式修复均先持久预留；未知、缺项、非法或不一致的 usage 不释放占用。重启、跨作品、失败和并发共享同一轮上限。模型格式错误仅以 schema 白名单路径和固定错误类别进入系统修复指令，模型可控键值不得提升为系统指令。

拆解专用配置可将完整且不超过65,536字符的失败输出，以不可信用户数据用于唯一一次定点格式修复；默认运行时不启用。失败候选不进入系统指令、不记录到默认日志，空/截断/超限内容不截取回传。新增候选输入计入原预算预留，结果仍通过相同schema与来源绑定；代码不规范化或删除错误字段来绕过验证。

官方MiMo拆解启用深度思考，预览输出总上限24,576 token（包含推理与最终JSON），其他运行时缺省不变。流式收集只取最终content，usage使用供应商完整completion计费；MiMo思考模式不发送自定义temperature/top_p。增加输出空间不增加重试或费用授权，书级分步上限仍须独立验证。

## AI 状态与记忆边界

```text
blueprint drafting → confirmed
director queued → character_simulation → waiting_for_choice
             → writing → reviewing → updating_archive → completed
             └→ paused / failed_retryable / author_revision_conflict
```

主编是唯一前台对话角色；剧情、人物、世界观、节奏是后台专业角色。林舟、顾遥等故事人物每次单独组装上下文，只获得共享世界规则、公开事实、本人经历和私有记忆；其他人物的私有记忆绝不进入其请求、浏览器响应或 DOM。专业角色可以读取完成职责所需的全局档案，但不能被当作故事人物卡片。

有有效配置时模型调用记录脱敏的 provider、model、usage、latency、attempts、status、call_id 和错误类别；不保存 Key、headers、raw prompt、raw completion 或私有记忆。没有 Key 时才走明确的确定性演示，不消耗开发积分。

## 跨 store 事务与作者优先

AI 正式章节提交使用 durable journal、staging payload 和 commit marker。marker 之前新状态不对外可见；marker 后由启动、worker、读入口、选择和重试入口进行幂等 reconcile。事务记录只含安全元数据、版本前置条件、payload hash 和脱敏业务载荷，不含提示词或私有记忆。

作者正文永远优先。正常作者写入口和未终结 AI 事务使用持久项目写锁/版本门禁串行化。若 marker 后检测到作者 revision 漂移且不能安全无冲突合并，事务进入明确的 `author_revision_conflict`/superseded 终态：作者正文保留，AI 正式章、快照、完成通知不可见，run 可重试，安全 usage ledger 不删除。无冲突事务可以在有限步骤内完成，重复恢复不会重复写章、选择、通知或积分。

公开 workspace、editor、archive、library、notifications 必须看到同一个完整旧状态或完整新状态，不用前端乐观状态掩盖跨 store 半成品，也不因可恢复事务向用户抛 500。

## 路由与本地运行

新用户页面是 `/`、`/login`、`/library`、`/independent/{project_id}`、`/ai/{project_id}`、`/ai/{project_id}/director`、`/archive/{project_id}`。服务启动不需要模型 Key；真实模型只在配置存在且用户触发 live 流程时调用。自动化测试注入 fake runtime，禁止真实供应商请求。

## 保护边界

不新增分享、发布、支付、管理员、多人协作、平行正文或生产部署。设计原型只作 A 版视觉基准；本地数据、审计证据、浏览器现场和项目外质量研究不属于公开源码发布清单。

## 作品拆解侧车（阶段 31）

阶段 32 的扩展合同与现役实现见 [深度拆解合同](STAGE_32_CONTRACT.md)。六视角 2.0 schema、确定性分析引擎、共享持久项目锁、source/CAS 发布、旧侧车显式升级和前端工作区均已接入。

作品拆解是独立创作内部的版本化派生侧车，不改变既有正文和故事档案文件：

```text
独立稿本正式正文
        ↓ source_version_id + source_revision + source_hash
DeconstructionService
        ↓ queued → running → completed / failed_retryable / rebuild_required
.novel_deconstruction/{project_id}.json
        ↓ 单次 GET
总览 · 人物 · 剧情 · 伏笔 · 章节节奏 · 读者体验 · 文笔技法 · EvidenceRef 回链
```

- `schemas/deconstruction.py` 定义拆解运行、概览观察、候选、时间线节点、章节拆解和证据定位合同。结果只保存最小证据摘录，不保存整本正文、prompt 或内部分析过程。
- `app/core/deconstruction_store.py` 按作品原子保存当前运行和历史运行；该目录是本地运行数据，继承 `.novel_*` 保护规则，不加入 Git。
- `app/core/deconstruction_service.py` 读取独立稿本的正式正文，计算绑定来源的 hash，执行可审计确定性结构拆解，并为每个判断附 `EvidenceRef`、confidence 与 uncertainty。正文/版本来源变化时不覆盖旧结果，而返回 `stale`；作者有未确认修改时返回 `rebuild_required`。
- `app/deconstruction_routes.py` 提供 `GET /api/independent/projects/{project_id}/deconstruction`、`POST .../deconstruction/rebuild`、`POST .../deconstruction/retry` 和 evidence 定位接口；入口复用邮箱会话、作品归属和独立模式门禁，跨账户不暴露侧车。
- `main.py` 生命周期启动独立拆解 worker，扫描 `queued/running` 记录并在服务重启后继续；前端只读取服务端状态，不驱动分析进度。导入确认、完成本章、全文重建和历史恢复会自动排队。
- 读取不回写旧正文；作者未确认修改不会被拆解任务覆盖。已有历史项目即使没有拆解侧车，在拥有至少一章正式正文时首次读取会进入排队状态，材料不足则诚实返回 `empty`。

### 阶段 31B：锁顺序、outbox 与公开状态

正文侧车记录 `deconstruction_outbox` 与正文/稿本变更同次保存。事件只含稳定 `event_id`、原因、创建时间、重试次数和安全错误码，不含正文、提示词或内部材料。`DeconstructionService.reconcile_outbox()` 在服务启动、worker 扫描、拆解读取和重试入口运行；先读取正文来源，再短暂写拆解侧车，释放拆解锁后才确认 outbox 事件。这样固定为“作者写门禁 → 正文侧车”和“拆解短锁 → 拆解侧车”，不会出现 `deconstruction → independent` 的反向锁嵌套。

拆解运行先以 `queued/running` 保存，再在锁外构造确定性结果，完成前重新检查稿本版本、revision/hash。任意可预期或意外分析异常都会保存为 `failed_retryable`，不暴露异常原文；单个损坏侧车只被扫描器跳过，不阻断其他项目。正文侧车和拆解侧车均采用临时文件、替换、文件刷盘及目录刷盘，保证 outbox 触发在重启后可被发现。

四个拆解接口的公开合同由 `DeconstructionResponse` 与 `DeconstructionEvidenceResponse` 强制校验。`effective_status` 是用户动作状态，`run_status` 是运行状态，`source_match` 是结果来源门禁；兼容旧字段必须与 canonical state 相等，只有 `effective_status=completed`、`run_status=completed` 且 `source_match=true` 时才返回 `result`。证据绑定 `document_id + source_version_id + source_revision + source_hash`，偏移单位为 UTF-16 code unit；历史来源只返回只读定位，不重绑当前章节。

### 阶段 31E：前端总集成

`frontend/app.js` 通过单一 `deconstructionApi` adapter 读取上述 canonical 顶层字段，不读取兼容投影来猜状态。页面支持 `empty`、`queued`、`running`、`completed`、`failed_retryable`、`stale` 和 `rebuild_required` 七种服务端状态；轮询只重新读取状态，不向服务端发送推进动作。深链 `/independent/{project_id}?view=deconstruction` 在刷新时先恢复 HttpOnly 会话，再读取真实作品和侧车，未登录与跨账户仍沿既有门禁处理。

拆解结果中的 `EvidenceRef` 在跳回正文前会再次校验文档、稿本版本、revision、hash、章节和 UTF-16 偏移。校验不通过时只显示历史章节级只读证据；前端不保存正文副本、私有记忆或结果 fixture，服务端仍是唯一数据来源。

### 阶段 32：六视角深度报告

`app/core/deconstruction_depth.py` 按章节事实、跨章关系、六视角分析、证据校验和发布顺序构造 `report_version="2.0"`。事件、人物状态和证据 ID 使用来源 token 与章节/span 等固有锚点，不使用遍历序号；否定、拒绝、阻止、能力/许可否定与双重否定按局部谓词作用域处理，缺少证据时保持未知或降低置信。

作者写入、后台分析和跨 store 事务统一进入持久项目锁；发布前重新校验 active version、revision、hash 与 CAS token，正文变更时放弃旧发布并进入 `stale` 或 `rebuild_required`。前端只接受严格 2.0 报告，提供总览和六视角 roving tabs、筛选与证据抽屉；当前来源允许精确定位，历史来源只读且禁用定位。
