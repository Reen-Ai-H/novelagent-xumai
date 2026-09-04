# 当前任务进度

## 阶段 31E：作品拆解前后端总集成与候选冻结（2026-09-04）

- 目标：在阶段 31B 后按 `8028865` → `341bad8` 顺序整合真实作品拆解前端，不新增阶段 32 功能。
- 实际落地：前端提交分别为 `d614118`、`be6fde2`；页面使用 `/independent/{project_id}?view=deconstruction` 和 canonical `effective_status/run_status/source_match` 合同。
- 基线：整合前 124 tests；整合后当前候选 133 tests，0 failed / 0 skipped；OpenAPI 当前 `58 paths / 61 operations`，旧 `/novel` `16 paths / 19 operations`。
- API 实测：隔离 TestClient 已验证 `empty`、`queued`、`running`、`completed`、`failed_retryable`、`stale`、`rebuild_required`，匿名 401、跨账户 404，结果含概览/时间线/章节拆解/证据。
- 浏览器实测：本地 8021 真实服务完成新建独立作品、空白正文、自动保存、完成章节、拆解、刷新深链；完成、空态、排队、失败、过期和待确认页面均已留证。
- 证据路径：`/private/tmp/stage31e-evidence/deconstruction-{completed,empty,queued,failed-retryable,stale,rebuild-required}-1710x887.png`；Chrome 实际 CSS 视口曾为 1710×887，当前重登验证为 1710×831，原生截图为 2x；未将其冒充 1440/1024 目标尺寸。
- 文档：已同步 `README.md`、`docs/README.md`、`docs/USER_GUIDE.md`、`docs/ARCHITECTURE.md`、`docs/DEVELOPMENT.md`、`docs/CLOSEOUT_MATRIX.md`。
- 安全边界：未读取/修改 `.env`，未迁移/删除/提交 `.novel_*`；前端无 localStorage/sessionStorage，不返回侧车账户字段或正文副本。
- 最终门禁：阶段 31 专项 26/26、全量 133/133，均 0 failed / 0 skipped；compileall、`node --check`、`git diff --check`、Markdown 本地链接检查均通过；OpenAPI `58/61`、旧 `/novel` `16/19`。
- 本地候选已收口为当前分支 HEAD（不推送、不建 PR）；不自行宣布独立审计通过，不进入阶段 32。

## 阶段 31B：作品拆解后端架构审查 P1 收敛（2026-09-04）

- 目标：不改 `frontend/**`，收敛锁顺序、拆解 outbox/reconcile、失败持久化、来源证据和四个公开 API 合同。
- 顺序：先复现基线与已有回归 → 修派发/worker/锁边界 → 修 evidence 与 canonical response → 同步权威文档 → 全量回归。
- 最大风险：正文保存、拆解侧车和后台恢复若顺序不清，会造成正文成功但拆解 500、任务卡死或结果错误绑定当前稿本。
- 基线复核：阶段 31A 6 项通过；当前阶段新增 11 项，合计 `124 tests / 0 failed / 0 skipped`。
- 已完成：来源读取移出拆解锁；正文侧车保存 durable outbox；失败派发可重试；worker/读取可恢复；异常进入 `failed_retryable`；证据和公开状态合同已收紧。
- 已同步：`docs/DECISIONS.md`、`docs/PRODUCT_SPEC.md`、`docs/UX_FLOWS.md`、`docs/ACCEPTANCE.md`、`docs/ARCHITECTURE.md`。
- 本阶段不改前端、不调用模型、不改 `.env` 或 `.novel_*`；compileall、OpenAPI/旧路由、node 检查和 diff 检查均已通过。
- 阶段提交：`ab4e056`（`Converge independent deconstruction architecture`）；不推送、不建 PR，等待管理任务与前端任务集成/复核。

## 阶段 31：独立创作中的作品拆解 MVP 后端（2026-09-04）

- 范围：仅负责拆解 schema、侧车 store/service、API、服务端 worker、后端测试和必要架构文档；前端由独立任务负责，本阶段不修改 `frontend/**`，不做总集成。
- 分支：`codex/stage-31-independent-deconstruction`；起点为阶段 30 现役基线；既有未提交用户反馈 `docs/DECISIONS.md` 保留。
- 目标：导入确认/完成本章自动排队，后台离页/重启恢复，概览、0–100% 时间线、章节拆解、evidence 回链、空态/失败/重建和账户隔离可由服务端验证。
- 顺序：决策与合同 → 独立侧车数据模型 → 确定性拆解服务 → 路由/worker 接线 → 红绿测试 → 全量回归与 TestClient 证据 → 后端提交。
- 最大风险：跨稿本正文来源变化可能让拆解覆盖作者内容；采用 source version/revision/hash 门禁，旧结果保留、当前返回 `stale`/`rebuild_required`，不回写既有正文数据。
- 开工基线：`107 tests / 0 failed / 0 skipped`；OpenAPI 与旧 `/novel` 数字待本阶段结束复核；初始 `git status` 为本分支 + 既有 `docs/DECISIONS.md` 修改，无未跟踪文件。
- 已完成：新增 `schemas/deconstruction.py`、`app/core/deconstruction_store.py`、`app/core/deconstruction_service.py`、`app/deconstruction_routes.py`；接入独立服务 hooks、FastAPI 生命周期 worker、`.gitignore`。
- 当前后端合同：`GET /api/independent/projects/{project_id}/deconstruction` 单次读取；另有 rebuild、retry 和 evidence 回链接口；状态 `empty/queued/running/completed/failed_retryable/stale/rebuild_required`；结果含来源版本/revision/hash、概览、timeline、chapter_breakdowns、evidence、history、initialized 和 actions。
- 当前验证（31A 基线记录）：阶段专项 6 tests 全绿；全量 `113 tests / 0 failed / 0 skipped`；compileall、`node --check frontend/app.js`、`git diff --check` 全部通过；OpenAPI `58 paths / 61 operations`（新增拆解 4 paths / 4 operations），旧 `/novel` `16 paths / 19 operations`；受控文件秘密/运行数据清单扫描无保护路径。
- 后端交付：commit `e585070`（`Implement independent work deconstruction MVP backend`）；工作树干净、分支相对 `origin/main` ahead 1。本阶段不做前端修改、总集成或 PR，交由管理任务与前端任务接续。


## 阶段 30：README 产品展示与使用说明（2026-08-13）

- 目标：重写根 README，加入当前实现截图、A 版效果参考、两条使用路径、快速启动、模型配置、验证命令与边界说明。
- 分支：`codex/stage-30-readme-showcase`。
- 变更：`README.md`、`docs/assets/current-home.jpg`、`docs/assets/current-login.jpg`；截图来自本地真实页面，效果图明确标注为 A 版参考。
- 参考结构：采用开源项目常见的首屏定位 → 视觉预览 → Quick Start → 使用方式 → 配置/验证 → 文档/限制层级，保持短段落和可扫描表格。
- 门禁：图片 7 张、文档本地链接 8 个均存在；截图/README 无密钥、机器路径或用户数据。
- 验证：107 tests 全绿、0 skipped；compileall、node --check、git diff --check、OpenAPI 54/57、旧 `/novel` 16/19 均通过。
- 交付：commit `3ee3c5a` 已 push；PR [#4](https://github.com/aswansong/novelagent/pull/4) 已合并，`main` 合并提交为 `09387a82b7f79c92c61bd651d81ba1ae54111a44`。

## 阶段 29：V1 主线晋升与仓库治理（2026-08-12）

- 目标：以阶段 28 的 V1 开发版替换落后的 GitHub `main`，清理经确认可删除的临时项，并建立逐阶段 GitHub 同步制度。
- 状态：已完成。
- 主线结果：`codex/v1-project-closeout` 已通过 [PR #1](https://github.com/aswansong/novelagent/pull/1) 合并；`main` 合并提交为 `0e48def6bd5404615a32e8d02af78cf75635cf70`，其文件树与 V1 提交 `cd3563517a222a4a94c444daebb15d823fd4de8f` 完全一致。远端和本地 V1 临时分支均已删除。
- 阶段制度：后续阶段使用 `codex/stage-<编号>-<主题>`，结束时必须 commit/push，并在本文件记录分支、SHA 和 PR；需复核时保持 Draft。
- 清理结果：5 份被忽略的 `.local.md` 历史副本和阶段 28 PR 临时说明已移到 macOS 废纸篓的 `叙脉-stage29-cleanup-20260812` 目录，可恢复；本项目遗留的 8000 端口开发服务已停止。
- 保留结果：另一个旧 worktree 含未提交源码和 `.novel_*` 本地数据，禁止直接删除；远端 `codex/test1` 含未合并独立历史；项目外质量研究仍供 Q3 使用。三者均保留。
- GitHub 同步：治理决定提交为 `cd3563517a222a4a94c444daebb15d823fd4de8f`；本阶段收尾分支为 `codex/stage-29-main-promotion`，首个收尾提交为 `4e0795ae95165d776c4b80273f02843bc9afe305`，[PR #2](https://github.com/aswansong/novelagent/pull/2)。

## 阶段 28：洁癖知识收口与 GitHub 开发版（2026-08-11）

- 目标：让首次接手者从仓库能理解产品、配置、启动、两条创作路径、当前限制和验证状态；把当前开发版源码、测试、权威文档和设计资产提交到开发分支并开 Draft PR。
- 发布范围：源码、schemas、tests、docs、AGENTS.md、PROGRESS.md、BLOCKED.md、README.md、requirements.txt、.gitignore、无值 .env.example、design-prototypes。
- 绝不纳入：.env、.novel_*、.codex、.venv、缓存、浏览器现场、审计证据、质量研究 quarantine、用户账户/正文/usage 数据。
- 当前事实：阶段 27 独立审计通过；107 tests 全绿、0 skipped；OpenAPI 54/57；旧 /novel 16/19。
- 质量事实：项目外离线质量门 Q2 已验证；真实生成质量增益、叙脉集成和 Q3 仍 pending。文学质量阶段 23B 为 C，不把功能审计写成质量通过。
- 处理顺序：盘点事实面 → 收口规则/README/用户说明/架构/开发文档 → 链接与安全扫描 → 全量验证和 localhost 烟雾 → 显式暂存 → commit/push → Draft PR。
- 最大风险：dirty worktree 含阶段 1–27 既有改动；必须逐路径归属并排除所有本机数据、密钥、审计和研究目录。

## 已完成

- 已执行 neat-freak 只读盘点，确认规则入口、dirty worktree、3 个 worktree 和受保护目录；未清理任何现场。
- 已将根规则、README、用户指南、架构、开发手册、文档索引、产品/流程/验收状态和收口矩阵同步到阶段 28 现役事实。
- 已保留阶段历史；含本机路径/账户/审计现场的原始副本仅留在被 `.gitignore` 排除的本地 `.local.md` 文件，公开 `docs/history/` 只含脱敏摘要。
- 已建立无值 `.env.example` 和覆盖 `.env`、`.novel_*`、`.codex`、`.venv`、缓存与日志的 `.gitignore`。

## 阶段 28 门禁

- 代码、文档和规则以当前实现和本文件链接的权威文档为准；旧阶段历史移至 docs/history/。
- 本地开发可用不等于生产部署；GitHub `main` 开发基线不等于 deployed、live verified。
- 清场候选只列不删，必须等用户阅读本阶段回报后再次明确确认。

## 已交付

- 发布前验证已完成：107 tests 全绿且 0 skipped；compileall、node --check、git diff --check 通过；OpenAPI 54/57，旧 `/novel` 16/19；本地 8017 首页/登录/书架烟雾通过，匿名 API 按合同返回 200/401。
- Markdown 链接 29 文件、20 本地链接缺失 0；staged manifest 103 文件，保护路径 0，真实密钥形状/Authorization/机器绝对路径 0，最大文件 2.26 MB，总暂存约 35.2 MB。
- 已创建分支 `codex/v1-project-closeout`，提交 `Prepare v1 development release`，并推送到 origin。
- 已创建面向 `main` 的 PR #1；阶段 29 将它作为 V1 主线晋升入口。

## 后续边界

- 等待固定独立审计复验；不在本阶段自行宣布审计或文学质量通过。
- 离线质量门 Q2 已验证，但真实生成质量增益、产品集成和 Q3 仍 pending；清场候选等用户确认，不在本阶段删除。
