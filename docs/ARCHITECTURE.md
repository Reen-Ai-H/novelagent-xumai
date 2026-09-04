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

阶段 32 的扩展合同现已冻结，见 [深度拆解合同](STAGE_32_CONTRACT.md)。六视角 2.0 schema 已接入，以下阶段 31 的引擎和实例锁仍待后端升级；共享持久项目锁、source/CAS 发布及旧侧车升级不能仅凭旧实现视为完成。

作品拆解是独立创作内部的版本化派生侧车，不改变既有正文和故事档案文件：

```text
独立稿本正式正文
        ↓ source_version_id + source_revision + source_hash
DeconstructionService
        ↓ queued → running → completed / failed_retryable / rebuild_required
.novel_deconstruction/{project_id}.json
        ↓ 单次 GET
作品概览 · 0–100% 节奏时间线 · 章节拆解 · EvidenceRef 回链
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
