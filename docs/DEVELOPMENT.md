# 叙脉开发与运维手册

## 快速开始

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

服务默认只监听本机。不要把本地数据目录当成配置文件编辑，不要把 `.env` 或任何 `.novel_*` 目录加入 Git。

## 配置合同

配置加载器只读取变量名，不在日志或响应中输出密钥值。支持 `OPENAI_API_KEY`、`DASHSCOPE_API_KEY`，以及 `OPENAI_BASE_URL`、`DASHSCOPE_BASE_URL`、`LLM_BASE_URL`、`LLM_MODEL`、`OPENAI_MODEL`、`DASHSCOPE_MODEL`、`LLM_TEMPERATURE`。显式 base URL 和 model 优先；无 Key 时 runtime 为 unavailable，业务走清楚标注的演示分支并显示 0 积分。

有 Key 的开发测试会显示“模型已连接·开发测试，不结算创作积分”。供应商错误必须进入 failed/retryable，不得悄悄回退模板。自动化测试使用 fake runtime，不调用真实模型。

## 检查命令

在仓库根目录运行：

```bash
.venv/bin/python -W ignore -m unittest discover -s tests -q
.venv/bin/python -m compileall -q app schemas main.py
node --check frontend/app.js
git diff --check
```

开发版阶段 28 收口时的基线为 107 tests、0 failed、0 skipped；OpenAPI 为 54 paths / 57 operations，旧 `/novel` 为 16 paths / 19 operations。任何测试减少、跳过或路由减少都应先停止交付并记录证据。

## 代码和测试约定

- 变更产品决策先更新 `docs/DECISIONS.md`，再同步规格、流程和验收。
- 先做确定性 fake 测试，再做最小本地浏览器/API 烟雾；不要在测试中使用真实付费服务。
- 结构化模型输出必须严格 schema 校验；正文是独立纯文本协议，长度、截断、私密哨兵和业务字段不合格时整次失败，不截断、不脱敏后落库。
- 事务写入遵循 journal/staging/commit marker；不通过 UI 隐藏半成品，不捕获所有异常伪造 200，不用 `|| true`。
- 作者正文、revision、pending changes 和历史恢复不得被后台覆盖；所有 AI 作品只有一条正式正文。
- 新旧 API 都必须做 HttpOnly 会话、账户 owner 和 mode 校验；私有记忆只在服务端单人物推演使用。

## GitHub 阶段工作流

1. 从最新 `main` 创建 `codex/stage-<编号>-<主题>` 分支；一个阶段只承载一个可验收目标。
2. 开工时记录基线，完成后运行与改动匹配的测试、静态检查和安全检查，并把真实结果写入 `PROGRESS.md`。
3. 只显式暂存本阶段文件；确认没有 `.env`、`.novel_*`、`.codex`、审计/浏览器现场或项目外研究后再提交。
4. 阶段一旦结束就推送到 GitHub，并在 `PROGRESS.md` 记录分支名、提交 SHA 和 PR URL。需要独立审计、模型质量评测或视觉终审时，PR 保持 Draft。
5. 对应门禁通过后再合并到 `main`。合并分支不代表已部署、已发布正式 Release 或已通过尚未执行的质量评测。

完成阶段不得只停留在本机工作树。若网络或 GitHub 权限阻止推送，把原始错误和可续跑命令写入 `BLOCKED.md`，不得把“本地已完成”描述成“已同步”。

## 数据备份与恢复

停服务后备份完整的 `.novel_accounts`、`.novel_ai`、`.novel_independent`、`.novel_projects`、`.novel_memory`、`.novel_transactions` 目录。备份前保留原目录，恢复前先复制当前目录作为回滚副本；不要直接手改 JSON。恢复后先跑匿名首页/登录/书架和确定性测试，再做写入验证。

## 常见开发故障

- `author_revision_conflict`：作者 revision 优先；确认页面显示作者正文和可重试状态，不手动删 journal。
- `provider_bad_json`：检查结构化供应商响应；一次格式修复仍失败就保持 retryable failed。
- 空白导入：只在 preview/confirm 阶段返回明确错误，不创建 active version。
- 事务卡在 projecting：重启服务让 worker/reconcile 接管；公开入口必须在有限步骤内显示旧完整状态或新完整状态。
- 页面显示 demo/live/failed 不一致：先确认会话恢复和 `/api/ai/.../workspace` 的服务端状态，不以浏览器 storage 作为真相。

## 发布边界

GitHub `main` 是当前 V1 开发基线，但不是 deployed 或 live verified。阶段 27 功能独立审计通过；真实 DeepSeek 三章链路已验证，但文学质量阶段 23B 仍为 C。项目外离线质量门 Q2 已验证；真实生成质量增益和叙脉产品集成仍 pending，Q3 不在本阶段执行。清理本地分支、worktree、审计现场、数据或研究现场必须逐项确认；含 `.novel_*` 或未提交工作成果的 worktree 不得删除。
