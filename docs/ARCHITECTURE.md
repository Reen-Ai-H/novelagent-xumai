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
