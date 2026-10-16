# 叙脉开发与运维手册

## 快速开始

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Windows PowerShell 的等价步骤见 [`docs/WINDOWS_MIGRATION.md`](WINDOWS_MIGRATION.md)。仓库 CI 在 Ubuntu 和 Windows、Python 3.12、Node LTS 上运行完整 unittest、compileall 和 `node --check`；不加载 `.env`，不调用模型、图片或付费服务。

服务默认只监听本机。不要把本地数据目录当成配置文件编辑，不要把 `.env` 或任何 `.novel_*` 目录加入 Git。

## 配置合同

配置加载器只读取变量名，不在日志或响应中输出密钥值。支持 `OPENAI_API_KEY`、`DASHSCOPE_API_KEY`，以及 `OPENAI_BASE_URL`、`DASHSCOPE_BASE_URL`、`LLM_BASE_URL`、`LLM_MODEL`、`OPENAI_MODEL`、`DASHSCOPE_MODEL`、`LLM_TEMPERATURE`。显式 base URL 和 model 优先；无 Key 时 runtime 为 unavailable，业务走清楚标注的演示分支并显示 0 积分。

阶段 34 增加显式 `LLM_PROVIDER=mimo`、`MIMO_API_KEY`、`MIMO_BASE_URL` 和 `MIMO_MODEL`。选择 MiMo 后只读取该供应商凭据，不回退旧 OpenAI/DeepSeek 配置；默认官方按量端点和 `mimo-v2.6-pro`。用户授权的 macOS RTF 凭据可通过 `scripts/configure_mimo.py <文件路径>` 安全配置，不输出密钥并保留其他配置。

有 Key 的开发测试会显示“模型已连接·开发测试，不结算创作积分”。供应商错误必须进入 failed/retryable，不得悄悄回退模板。自动化测试使用 fake runtime，不调用真实模型。

## 检查命令

在仓库根目录运行：

```bash
.venv/bin/python -W ignore scripts/verify_offline.py
.venv/bin/python -m compileall -q app schemas main.py
node --check frontend/app.js
git diff --check
```

历史基线：阶段 28 为 107 tests，阶段 31 为 135 tests，阶段 32 候选为 204 tests。当前测试数量和结果以 `PROGRESS.md` 顶部的实际命令为准，不能把旧数字作为新阶段通过依据。任何测试减少、跳过或路由减少都应先停止交付并记录证据。

有真实凭据的开发目录使用上述隔离入口，复制源码到临时目录、剥离模型环境变量并阻断网络；原始 unittest 命令仍用于干净 CI。阶段 35 新增前端脚本也需分别执行 `node --check`：`deconstruction-report.js`、`report-browser.js`、`rule-report.js`。

## 代码和测试约定

- 变更产品决策先更新 `docs/DECISIONS.md`，再同步规格、流程和验收。
- 先做确定性 fake 测试，再做最小本地浏览器/API 烟雾；不要在测试中使用真实付费服务。
- 结构化模型输出必须严格 schema 校验；正文是独立纯文本协议，长度、截断、私密哨兵和业务字段不合格时整次失败，不截断、不脱敏后落库。
- 事务写入遵循 journal/staging/commit marker；不通过 UI 隐藏半成品，不捕获所有异常伪造 200，不用 `|| true`。
- 作者正文、revision、pending changes 和历史恢复不得被后台覆盖；所有 AI 作品只有一条正式正文。
- 新旧 API 都必须做 HttpOnly 会话、账户 owner 和 mode 校验；私有记忆只在服务端单人物推演使用。

## GitHub 阶段工作流

当前叠加阶段例外（2026-10-17）：阶段34–37仍为Draft PR，最新候选在 `codex/stage-37-usable-workspace`；工程、真实内容及独立复核状态分别见PROGRESS，候选不自动等于已验收。网页端接续应从该分支最新远端提交创建下一阶段分支，不能直接从旧 `main` 开始；不因此自动合并既有PR。详见 [网页端交接](CODEX_WEB_HANDOFF.md)。下列“从main创建”适用于前置阶段已合并的常规流程。

1. 从最新 `main` 创建 `codex/stage-<编号>-<主题>` 分支；一个阶段只承载一个可验收目标。
2. 开工时记录基线，完成后运行与改动匹配的测试、静态检查和安全检查，并把真实结果写入 `PROGRESS.md`。
3. 只显式暂存本阶段文件；确认没有 `.env`、`.novel_*`、`.codex`、审计/浏览器现场或项目外研究后再提交。
4. 阶段一旦结束就推送到 GitHub，并在 `PROGRESS.md` 记录分支名、提交 SHA 和 PR URL。需要独立审计、模型质量评测或视觉终审时，PR 保持 Draft。
5. 对应门禁通过后再合并到 `main`。合并分支不代表已部署、已发布正式 Release 或已通过尚未执行的质量评测。

完成阶段不得只停留在本机工作树。若网络或 GitHub 权限阻止推送，把原始错误和可续跑命令写入 `BLOCKED.md`，不得把“本地已完成”描述成“已同步”。

## 数据备份与恢复

停服务后备份完整的 `.novel_accounts`、`.novel_ai`、`.novel_independent`、`.novel_projects`、`.novel_memory`、`.novel_transactions` 目录。备份前保留原目录，恢复前先复制当前目录作为回滚副本；不要直接手改 JSON。恢复后先跑匿名首页/登录/书架和确定性测试，再做写入验证。

阶段36新增的 DOCX 标题样式元数据可由新服务兼容读取旧记录，但旧版严格 schema 不认识新字段。新旧服务不得共享写入同一数据目录；回退应用时使用升级前的完整备份，不通过删字段或批量改 JSON 回退。当前验收服务始终使用独立副本，作者原目录不切换。

## 常见开发故障

- `author_revision_conflict`：作者 revision 优先；确认页面显示作者正文和可重试状态，不手动删 journal。
- `provider_bad_json`：检查结构化供应商响应；一次格式修复仍失败就保持 retryable failed。
- 空白导入：只在 preview/confirm 阶段返回明确错误，不创建 active version。
- 事务卡在 projecting：重启服务让 worker/reconcile 接管；公开入口必须在有限步骤内显示旧完整状态或新完整状态。
- 页面显示 demo/live/failed 不一致：先确认会话恢复和 `/api/ai/.../workspace` 的服务端状态，不以浏览器 storage 作为真相。

## 作品拆解前端集成

独立作品拆解的 canonical 入口是 `/independent/{project_id}?view=deconstruction`，API 为 `GET /api/independent/projects/{project_id}/deconstruction`，重试、重建和证据回链使用同一作品路径下的 POST/GET 合同。前端只轮询读取，后台推进由 FastAPI worker 完成。

验证页面时依次检查：空正文提示、服务端排队/运行进度、完成结果、可重试失败、过期结果和待确认修改；再刷新深链确认作品标题、来源 revision/hash 与状态仍来自服务端。宽表格必须在窄屏容器内横向滚动，不得让整页横向溢出。

阶段 31E 的前端集成顺序固定为 `8028865` → `341bad8`，在阶段 31B 后分别落为 `d614118`、`be6fde2`；若需要回溯，保留这两个提交的父子关系，不使用并行草稿提交。

阶段 32 的完成态响应必须同时满足 `analysis_contract_version="2.0"` 和 `report.report_version="2.0"`。验证时覆盖总览、六视角、roving tabs、筛选、当前证据精确定位、历史证据只读、修改后重建与刷新/重登；浏览器脚本使用隔离临时数据和禁止付费调用的 runtime。后端专项必须保留否定/拒绝/阻止/模态否定、双重与三重否定、稳定 ID、跨进程锁和 CAS 竞态回归。

## 阶段 35 专项验证

阶段 35 浏览器回归使用 `tests/browser_server.py` 的隔离数据与 fake runtime，覆盖 `browser_stage35_workspace_ui.cjs`、`browser_stage35_reading.cjs`、`browser_stage35_density.cjs`、`browser_stage35_history.cjs`、`browser_stage35_model_roles.cjs`，并保留阶段 32/34 保存、来源与历史回归。先运行reading建立原生新版夹具，再执行density；旧版升级提醒和原生新版无提醒分别验证。history脚本中的旧版元数据标签是组件验证，不能替代后端真实升级测试。合成样本只证明界面和合同，不证明文学质量；正文预览应逐字比较，不能用 `trim()` 隐藏空白变化。浏览器截图与测试现场不提交。

新版规则升级必须验证旧报告和旧证据继续可读、显式新建、重复幂等、正文改变后不返回当前结果。规则和模型导入都不得按固定历史数量裁掉仍可引用的报告。保留历史会增加本地侧车体积；自动归档/清理不在本阶段实施。

## 发布边界

GitHub `main` 是当前 V1 开发基线，但不是 deployed 或 live verified。阶段 32 深度作品拆解独立审计 P0/P1/P2/P3 均为 0；真实 DeepSeek 三章链路已验证，但文学质量阶段 23B 仍为 C。项目外离线质量门 Q2 已验证；真实生成质量增益和叙脉产品集成仍 pending，Q3 不在本阶段执行。清理本地分支、worktree、审计现场、数据或研究现场必须逐项确认；含 `.novel_*` 或未提交工作成果的 worktree 不得删除。

GitHub `main` 是当前 V1 开发基线，但不是 deployed 或 live verified。阶段 27 功能独立审计通过；真实 DeepSeek 三章链路已验证，但文学质量阶段 23B 仍为 C。项目外离线质量门 Q2 已验证；真实生成质量增益和叙脉产品集成仍 pending，Q3 不在本阶段执行。清理本地分支、worktree、审计现场、数据或研究现场必须逐项确认；含 `.novel_*` 或未提交工作成果的 worktree 不得删除。


## 独立拆解模型配置

在本地 `.env` 配置 `DECONSTRUCTION_API_KEY`、`DECONSTRUCTION_BASE_URL`、`DECONSTRUCTION_MODEL`。密钥仅由服务端读取，勿提交或回显。默认使用 MiMo 官方按量端点与 `mimo-v2.6-pro`；显式设置仍支持其他兼容服务。专用拆解配置与通用生成配置分离，安全配置脚本会同时设置两者。

官方配置和计价依据为 [MiMo 首次调用](https://mimo.mi.com/docs/zh-CN/quick-start/summary/first-api-call) 与 [按量定价](https://mimo.mi.com/docs/zh-CN/price/pay-as-you-go)。模型价格按精确名称选取并持久化版本，不能用历史 DeepSeek 价格估算 MiMo。

`scripts/live_deconstruction.py` 是旧阶段独立研究入口，默认10元不是当前授权；不得用它的默认值推导用户许可。阶段37必须从产品 `analyze-preview` / 全文接口验证来源绑定，以同一个 `DeconstructionService(model_budget_cny=2.0, model_budget_scope=...)` 和同一持久数据目录执行本轮授权样本，失败与重试也计入2元。不得更换 scope、重置账本或启动默认10元路径绕过上限。自动化测试断网并用 fake runtime，真实接口运行单独记录。

真实验收前独立复核预算与来源安全。验收正文、完整报告、引文、账本和现场仅留忽略目录；不得提交或复制密钥。`scripts/review_server.py` 旧研究入口不能代替产品生成成功证据，也不能覆盖作者现有数据。同一轮使用量未知时保留保守占用，预算不足先停止，不通过删除失败记录释放余额。

API 规则在 `app/agents/deconstruction_prompt.md`，继承 v0.5 细读规则并加入真实验收发现的对话归属、借体主体、动作先后和连线方向检查。选择章节试拆后先预览，采用通过已有来源/引文校验接口。调试自动化使用 fake runtime，不读取真实配置；真实请求仅在用户授权的手工试拆或后台全文任务中运行。

真实验收中结构与引文通过不等于文学质量通过。`--repair-report` 与 `--repair-issues` 使用真实模型输出修正声明，保留修正前报告供核查；不得直接补写语义冒充模型产物。本地验收入口只接收经过独立内容复核、来源和报告哈希匹配的结果。原始稿本、模型响应、失败结果和质量证据仍只在忽略目录中。

当前参数依据：[MiMo 结构化输出](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/text-generation/structured-output)。DeepSeek 的 [JSON Output](https://api-docs.deepseek.com/guides/json_mode/) 与 [思考模式](https://api-docs.deepseek.com/guides/thinking_mode/) 仅为仍保留的兼容供应商资料。
