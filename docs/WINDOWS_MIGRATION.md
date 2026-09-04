# Windows 迁移与本地运行

这是一份面向首次接手者的 Windows 开发版手册。叙脉使用本地 JSON 数据，不承诺公网云同步；GitHub 仓库只放源码、测试、文档和设计参考。

## 1. 安装与启动

先安装：

- Git for Windows
- Python 3.11+（推荐 3.12）
- Node.js LTS（只用于 `node --check`）

在 PowerShell 中执行：

```powershell
git clone https://github.com/Reen-Ai-H/novelagent-xumai.git
Set-Location novelagent-xumai

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 首次体验不需要模型 Key；需要模型时再在本机填写 .env
Copy-Item .env.example .env

.\.venv\Scripts\python.exe -W ignore -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m compileall -q app schemas main.py
node --check frontend/app.js

.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

浏览器打开 <http://127.0.0.1:8000>。停止服务时回到运行窗口按 `Ctrl-C`。端口被占用时，把 `--port 8000` 换成其他本机端口。

## 2. 两条创作路径

- **独立创作**：新建作品 → 空白开始或导入 TXT/MD/DOCX → 预览确认 → 编辑正文 → 完成本章 → 故事档案/作品拆解。
- **AI 辅助写作**：新建作品 → 主编创作室 → 补全并确认蓝图 → 导演台 → 关键节点三选一或交给角色 → 正文与档案。

无 Key 时是明确标注的确定性演示，不消耗创作积分。配置模型时只在本机 `.env` 中填写值；供应商失败会进入可重试状态，不静默替换为演示模板。

## 3. 源码与私有数据分离

以下内容被 `.gitignore` 排除，不能上传 GitHub：`.env`、`.codex`、`.novel_accounts`、`.novel_ai`、`.novel_independent`、`.novel_projects`、`.novel_memory`、`.novel_transactions`、`.novel_deconstruction`。

如果要把 Mac 上的本地作品延续到 Windows：

1. 在 Mac 停止叙脉服务，并保留一份原始备份。
2. 通过加密磁盘、私有直传或其他不经过 GitHub 的方式传输需要的 `.novel_*` 目录和 `.env`。
3. 把它们放到 Windows 仓库根目录；不要在聊天、终端日志或 Git diff 中打印密钥，也不要直接编辑 JSON。
4. 先在 Windows 完成匿名首页、邮箱登录、书架读取和测试，再进行一次小范围写入验证。
5. Windows 验证成功前保留 Mac 副本；恢复失败时停止服务并从备份恢复，不覆盖原目录。

`.codex/config.toml` 也被忽略。若当前 Codex 客户端支持这些字段，可以在 Windows 本地手工创建类似配置：

```toml
model = "gpt-5.6-luna"
model_reasoning_effort = "max"
approval_policy = "never"
sandbox_mode = "danger-full-access"
```

它只减少常规 Codex 审批，不绕过 Windows、浏览器、平台或账户权限限制；字段名以当前客户端版本为准。

## 4. 本地配置

`.env.example` 只列变量名和安全默认值。常用字段：

```dotenv
OPENAI_API_KEY=
OPENAI_BASE_URL=
LLM_MODEL=
LLM_TEMPERATURE=0.7
```

也支持 `DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`、`DASHSCOPE_MODEL` 和 `LLM_BASE_URL`。不要提交 `.env`，不要把 Key 写进源码或 issue。

## 5. 验证与排错

```powershell
.\.venv\Scripts\python.exe -W ignore -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m compileall -q app schemas main.py
node --check frontend/app.js
git diff --check
```

常见情况：

- `py` 找不到：重新安装 Python 并勾选 Add Python to PATH，或用完整 Python 路径创建虚拟环境。
- 端口占用：换一个端口启动，并用对应地址打开浏览器。
- 依赖安装失败：确认 Git/Python/Node 版本和网络代理，再重新执行 `pip install -r requirements.txt`。
- 空白导入：先看预览错误；没有有效章节时不会创建正式稿本。
- `author_revision_conflict`：保留作者正文，回到页面处理冲突，不要手改事务 JSON。
- `provider_bad_json` 或模型超时：确认 `.env` 配置和供应商可用性，使用页面的重试；无 Key 可先用演示路径验证产品流程。

当前状态：阶段31功能审计已通过，离线质量门 Q2 已验证，但真实生成质量增益与产品集成仍 pending；这是开发版，未部署生产，不提供正式支付、管理员或公网云同步。
