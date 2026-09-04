# 当前任务进度

## 阶段 33：独立创作体验收口合同冻结（文档/测试设计，2026-09-05）

- 基线：当前 `origin/main=ec2f31a`；阶段 32 已审计通过并合并，2.0 深度拆解、七种 canonical 状态、source token、证据回链、项目锁和 CAS 合同继续有效。
- 本轮完成：完整复核阶段 32 合同、独立 API/服务/前端/浏览器测试设计与编辑器、章末、档案、版本、拆解实现接缝；先把产品裁决写入 `docs/DECISIONS.md`，再新增阶段 33 任务书并同步产品规格、用户流程、验收、架构、路线、索引、用户指南、开发手册和阻塞记录。
- 冻结范围：真实 100 章中文作者路径、标题/正文同次保存、保存/完成/批次/恢复幂等、统一稿本上下文、失败与重启恢复、账户隔离、键盘/焦点/reduced-motion、1440×900 与 1024×900 Edge 验收及反作弊门禁。
- 非目标：AI 创作室、类型/质量引擎、公共语料、分享/云同步/多人协作/支付/管理员/移动端/生产部署、第二条正文，以及阶段 32 schema 或证据单位改写。
- 未实现：本分支没有改 `app/**`、`schemas/**`、`frontend/**` 或本地业务数据；实现应按任务书拆分后由管理任务集成，独立审计任务不得由本合同任务自证。
- 实际门禁：隔离 `.venv` 使用 `requirements.txt` 安装完成；`tests/run_quality_gates.py` 为 `204 tests / 0 failed / 0 skipped`，OpenAPI `58 paths / 61 operations`、旧 `/novel` `16 paths / 19 operations`；compileall、`node --check frontend/app.js`、`git diff --check` 和变更文档本地链接检查均通过。系统 Python 的首次尝试仅因缺依赖产生导入错误，不作为代码回归结果。
- 未执行且不宣称：阶段 33 功能实现、真实 Edge 双尺寸流程、失败反向浏览器证据、CI 和独立审计；这些属于后续管理/实现任务。
- 分支：`codex/stage-33-independent-experience-contract`；提交 SHA、远端分支和 Draft PR 将在提交推送后补录。

## 阶段 32：深度作品拆解（审计通过，已合并，2026-09-05）

- 最新里程碑：集成候选 `a631606` 已通过同一独立审计任务最终复验，P0/P1/P2/P3 均为 0。全量 `204 tests / 0 failed / 0 skipped`，阶段 32 专项 69 项，阶段 31 回归 28 项，并发回归 44 项；OpenAPI 58/61、旧 `/novel` 16/19，compileall、Node 与 diff check 均通过。
- 真实界面：Microsoft Edge 152 在 1440×900 与 1024×900 完成登录、导入、后台拆解、总览和六视角、当前证据精确定位、历史证据只读、刷新/重登及修改后重建；两个视口均 0 console error/warn、无整页横向溢出。
- 审计回派：首轮发现否定动作误生成 enables/paid_off、空白必填字段和顺序型 stable ID；后续扩展反例覆盖拒绝/阻止、答案宾语、模态否定、词法例外及带把/将宾语的双重/三重否定。缺陷均回原后端任务修复并由同一审计任务复验，最终 9 种双重否定 36 例、三重否定 27 例通过。
- GitHub：分支 `codex/stage-32-deconstruction-depth`，Draft PR [#4](https://github.com/Reen-Ai-H/novelagent-xumai/pull/4)。`a631606` 的 push 与 pull_request 两组 Ubuntu/Windows CI 均通过；完成本轮文档提交并取得同 SHA 双平台绿灯后转 Ready 并合并。

### 实施记录

- 架构冻结：可见架构任务完成冻结提交 `ce49277`，管理按 checkpoint → freeze 顺序接入为 `52ca221`、`1272673`。完整阅读合同并复核一致性后，管理全量实际 `180 tests / 12 failures / 0 skipped`（11.676s）：168 项既有/合同检查通过，12 项引擎黑盒验收仍缺 report。六视角 schema 冻结当时不代表功能完成，随后按同一基线创建可见 Luna/max 后端和前端任务并行。
- 并行研发已启动：可见“阶段32 深度拆解后端引擎”使用 `codex/stage-32-backend-depth`；“阶段32 六视角前端体验”使用 `codex/stage-32-frontend-depth`。两者已核实 active，且均 fast-forward 到冻结管理基线 `de736c2`，模型/推理均为 Luna/max。后端不改前端，前端不改后端，管理验收/文档/CI不交给执行任务改写；待集成后再建独立审计。
- 冻结后验收对齐：旧版夹具使用独立的 legacy 文档身份，避免借用新引擎排队 ID；补首读 `rebuild_required`/可升级、旧证据历史只读以及响应不含内部 CAS/去重字段断言。升级单测实跑 1 failure / 0 skipped（0.065s），旧引擎仍误报 completed，确认下一步由后端修复；diff 检查通过。
- 管理浏览器门禁对齐冻结合同：真实端到端不再从阶段31顶层 `result.evidence` 误取证据，改为强制 `analysis_contract_version=2.0`、六视角容器完整、`result.report.evidence` 来源 hash 一致；修改后重建也必须仍为2.0，再用旧深度证据验证历史只读。前端证据抽屉的可访问交互待前端候选接入后继续补齐。
- 前端增量审查发现并回派两项：nullable 深度指标不能被 JavaScript 转成0（前端已改为严格保留null并显示未知）；roving tab 只有当前项可进Tab序列时，必须实现方向键/Home/End，否则六视角对普通键盘用户不可达。管理浏览器门禁已改为从总览仅用 ArrowRight 依次切换六视角并核对焦点，不再通过测试代码逐个强制 focus 掩盖缺陷。

- 管理分支：`codex/stage-32-deconstruction-depth`，从最新 `origin/main=223b414` 建立隔离工作区；原 main 工作区的测试改动、启动脚本和本地数据全部保留。
- 已执行：`git fetch origin main`、`git merge --ff-only origin/main`、`git rev-list --left-right --count HEAD...origin/main`，主线一致（0/0）；完整读取规则、路线、任务书、进度与阻塞。
- 顺序：架构冻结公开合同；后端与前端使用独立工作区并行；管理集成后交独立审计，缺陷回派原实现任务复验。
- 当前未完成：阶段 32 已进入主线；后续以阶段 33 合同冻结和实现接棒为准。六视角实现、专项/全量/浏览器门禁与独立审计均已完成。
- 基线发现：阶段 15 dotenv 测试依赖开发目录已有 `.env` 与有效 key，需改为隔离配置夹具，真实验证跨 cwd 加载，不通过注入环境 key 制造通过。
- 基线复验：干净工作区全量 `135 tests / 1 failure / 0 skipped`，唯一失败为不存在开发 `.env`。改为临时项目布局执行原配置模块、移除继承的模型变量、给无关 cwd 放置反例配置后，全量 `135 tests / 0 failed / 0 skipped`（9.483s）。compileall、node 语法与 diff 检查通过；没有读取或修改用户 `.env`。
- GitHub：初始管理提交 `562513b`、基线修复 `a90682d` 已推送至阶段分支；Draft PR [#4](https://github.com/Reen-Ai-H/novelagent-xumai/pull/4)。`a90682d` 的 [CI run](https://github.com/Reen-Ai-H/novelagent-xumai/actions/runs/33897641025) Ubuntu/Windows 均 success，仅证明此时基线修复通过。
- 验收基础：新增隔离浏览器服务（真实 app/worker、临时测试账户和自有合成正文、禁止模型调用）；Edge 152 已实测视口 1440×900、根 scrollWidth=1440。新的六视角浏览器测试已红测：完成真实登录/创建/导入/后台拆解后，旧前端缺人物 tab，另有 favicon 404 控制台错误；留给前端实现修复，不屏蔽日志。
- 自动门禁入口 `tests/run_quality_gates.py` 已实跑 `135 tests / 0 failed / 0 skipped`（10.245s）、OpenAPI 58/61、旧 `/novel` 16/19，静态通过；CI 改为无需 `.env` 或环境 key，并强制零 skipped 和路由下限。
- 用户更新协作方式：停止隐藏子 Agent，改为侧栏可见的独立对话任务，统一使用 `gpt-5.6-luna` / `max`。原架构执行者已停止关闭，已落盘 schema/24项契约测试保存为 `c59b1a2`（未冻结），交可见架构任务接续；合同冻结后创建可见后端/前端任务，集成后创建可见独立审计任务。每个任务保持隔离 worktree，由管理任务统一集成和 GitHub 交付。
- 可见架构任务“阶段32 架构合同冻结”已确认 active，在独立 `codex/stage-32-architecture-visible` 分支接上 `a53030e` checkpoint，继续审查和编写冻结合同。新建任务列表曾未及时显示，已通过实际任务读取确认运行，未重复创建。
- 管理侧新增 `tests/test_stage32_acceptance.py` 的 9 项黑盒验收，覆盖六类自然/合成正文、真实结构化结果、人物变化/因果/伏笔语义、假因果与假回收反例、来源证据、幂等重建与历史隔离。初始红测 9/9 失败均为现有 stage31 缺少深度 `report`；这是未实现证据，禁止 skip 或改断言转绿。
- 验收复核：导入会 strip 章节边缘空白，因此前导空白/emoji 改由真实 start→draft→complete 写入，逐字断言保存/正式正文后再检查证据；新增首尾/中间空白章用例。专项现为 10 tests / 10 expected failures / 0 skipped（0.552s），均停在尚无深度 report。`a1260a4` 双平台 CI 的 144 tests / 9 failures / 0 skipped 与当时同一缺口一致，不把红测误报为平台故障。
- 旧数据升级红测：新增阶段 31 已完成侧车夹具，经真实读取、显式 rebuild、worker 要获得新版 report，同时保留旧文档/证据和作者正文；旧实现仅按来源哈希去重，不能完成升级。专项实际 `11 tests / 11 failures / 0 skipped`（0.607s），均为尚无深度 report；`git diff --check` 通过。升级身份与公开状态规则已交回可见架构任务冻结，不删除旧结果。
- 合同中途复核：发现“每个视角必须有非 unknown 实体”会迫使无人物/无伏笔文本编造内容，已回派架构任务修正并新增纯景物负例；倒叙有标记不等于可确定全局 story_order，也已要求显式保留未知。管理全量实跑 `147 tests / 12 failures / 0 skipped`（11.525s），135 项既有测试通过、12 项新深度验收均停在未实现 report；compileall、前端/浏览器脚本 node 语法、diff 检查通过。升级用例提交 `b692292` 已推送，当前仍为 Draft 阶段。
- 管理独立预检架构工作区当前 schema/测试：`tests/run_quality_gates.py` 实际 `168 tests / 0 failed / 0 skipped`（11.145s）、OpenAPI 58/61、旧 `/novel` 16/19、静态检查通过；该工作区尚未提交冻结文档，且不含管理侧 12 项引擎黑盒验收，因此不代表深度功能完成。重新 fetch 后管理分支相对 `origin/main` 为 8/0；可见 Luna/max 协作决定同步至 `DECISIONS.md` 和 `AGENT_WORKFLOW.md`，避免换任务后退回隐藏 Agent。

## 阶段 31J：Windows 零上下文接棒任务书（2026-09-05）

- 目标：补齐 GitHub 中缺失的下一阶段正式任务书与长期研发顺序，让 Windows 新管理任务不依赖 Mac 聊天记录即可继续。
- 基线：远端 `main=e55ee722bc755c0f2562895e18f36e39803c8af0`；阶段 31 为 135 tests、0 failed、0 skipped，OpenAPI 58/61、旧 `/novel` 16/19，Windows/Ubuntu CI 通过。
- 发现：现役文档只分散写有“阶段 32+”方向，没有一份同时包含具体范围、角色分工、依赖顺序、反作弊门禁和完成条件的阶段 32 任务书；长期阶段顺序也没有唯一入口。
- 处理：新增 `docs/ROADMAP.md` 和 `docs/goals/STAGE_32_DECONSTRUCTION_DEPTH.md`，同步规则、索引、决策、规格与验收；本阶段只改知识与交接面，不进入阶段 32 研发。
- 分支：`codex/stage-31j-windows-handoff-plan`。完成文档链接、全量基线和 GitHub PR/CI 后再记录最终 SHA 与合并结果。
- 本地门禁：现役 Markdown 本地链接检查通过；全量 135 tests、0 failed、0 skipped；compileall、`node --check frontend/app.js`、`git diff --check` 均通过。
- GitHub 交付：任务书提交 `820dc0e` 已推送；PR [#3](https://github.com/Reen-Ai-H/novelagent-xumai/pull/3) 已创建，Ubuntu/Windows 两组 CI 均通过。PR 合并状态以 GitHub 为准，Windows 接棒前必须从最新 `main` 拉取。

## 阶段 31I：Windows 迁移收口与 GitHub 发布（2026-09-04）

- 目标：不新增产品功能，把阶段31审计候选迁移到 `Reen-Ai-H/novelagent-xumai`，补 Windows 手册与双平台 CI，发布到新仓库 `main`。
- 基线：`7ff0273` 可达，135 tests、0 failed、0 skipped；OpenAPI `58/61`，旧 `/novel` `16/19`；`github-current/main=9c5aabd` 与旧 `origin/main` 文件树一致。
- 分支：从 `github-current/main` 建立 `codex/stage-31-independent-deconstruction-release`，已按 `e0f163a → d7166d1 → d614118 → be6fde2 → cdd7d01 → d480a85 → 7ff0273` 顺序重放；最终树与 `7ff0273` 一致。
- 计划：新增 `docs/WINDOWS_MIGRATION.md`、`.github/workflows/ci.yml`，同步 README/文档/收口矩阵和 GitHub 状态，再完成本地门禁、push、PR、CI、merge。
- 最大风险：跨平台命令/数据迁移说明误导作者，或把 `.env`、`.novel_*`、审计现场带入公开仓库；只使用无值模板和受控文件清单。
- 发布记录：`codex/stage-31-independent-deconstruction-release` 已推送，最终候选提交为 `2350feb`；PR [#1](https://github.com/Reen-Ai-H/novelagent-xumai/pull/1) 已合并，合并提交为 `8e42cb6486e6baa66afd7f463448cb39eb51dc3d`。
- 当前状态：`origin/main` 已回读并与候选树一致；Ubuntu/Windows CI 均通过。不创建 Release/Tag，不清理旧 worktree、分支和本地数据。

## 阶段 31G：审计 P2 定点收口（2026-09-04）

- 目标：只修时间线首尾归一化和证据接口 `chapter` 严格公开 schema，不改 `frontend/**`、后端其他合同或用户数据。
- 顺序：先用前导空白/空白段/emoji/多章与 OpenAPI schema 红测复现，再做最小服务层与 Pydantic 修复，最后全量回归并提交单一 commit。
- 基线：当前候选 HEAD `d480a85`，133 tests、0 failed、0 skipped；OpenAPI `58/61`，旧 `/novel` `16/19`。
- 最大风险：归一化若直接 `strip` 会改变 UTF-16 evidence/hash/offset；schema 收紧若改写历史 payload 会破坏只读兼容。
- 红测：前导空白样本首节点为 `4.82`；证据回链 `chapter` 经模型校验仍为 `dict`。
- 修复：仅对 timeline 展示坐标做有效正文跨度归一化；新增严格 `DeconstructionEvidenceChapter`，历史/当前回链均保留原有只读字段语义。
- 结果：阶段 31G 专项 2/2、阶段 31 相关回归 26/26、全量 135/135，均 0 failed / 0 skipped；compileall、`node --check`、`git diff --check` 通过；OpenAPI `58/61`、旧 `/novel` `16/19`。
- 本阶段不改 `frontend/**`、`.env` 或 `.novel_*`，不调用模型；候选提交完成后等待固定审计复验，不自行宣布通过。

## 阶段 31E：作品拆解前后端总集成与候选冻结（2026-09-04）

- 目标：在阶段 31B 后按 `8028865` → `341bad8` 顺序整合真实作品拆解前端，不新增阶段 32 功能。
- 实际落地：前端提交分别为 `d614118`、`be6fde2`；页面使用 `/independent/{project_id}?view=deconstruction` 和 canonical `effective_status/run_status/source_match` 合同。
- 基线：整合前 124 tests；整合后当前候选 133 tests，0 failed / 0 skipped；OpenAPI 当前 `58 paths / 61 operations`，旧 `/novel` `16 paths / 19 operations`。
- API 实测：隔离 TestClient 已验证 `empty`、`queued`、`running`、`completed`、`failed_retryable`、`stale`、`rebuild_required`，匿名 401、跨账户 404，结果含概览/时间线/章节拆解/证据。
- 浏览器实测：本地 8021 真实服务完成新建独立作品、空白正文、自动保存、完成章节、拆解、刷新深链；完成、空态、排队、失败、过期和待确认页面均已留证。
- 证据：阶段31E真实截图保留在本机临时证据目录、未纳入 Git；Chrome 实际 CSS 视口曾为 1710×887，当前重登验证为 1710×831，原生截图为 2x；未将其冒充 1440/1024 目标尺寸。
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
