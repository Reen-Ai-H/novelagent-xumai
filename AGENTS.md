# 叙脉项目规则

## 一句话定位

叙脉是面向中文长篇作者的 Web 写作与作品记忆工具，唯一标语是“新一代写作体验”，同时支持“独立创作”和“AI 辅助写作”。

## 现役入口

- 产品规格：[docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md)
- 使用说明：[docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- 架构：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 开发与运维：[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- 文档索引：[docs/README.md](docs/README.md)
- 阶段状态：[PROGRESS.md](PROGRESS.md)、[BLOCKED.md](BLOCKED.md)

## 技术与命令

- Python、FastAPI、Pydantic、LangGraph/LangChain；前端为原生 HTML/CSS/JS；入口是 main.py。
- 本地开发：uv venv .venv；uv pip install --python .venv/bin/python -r requirements.txt。
- 测试：.venv/bin/python -W ignore -m unittest discover -s tests -q。
- 静态检查：.venv/bin/python -m compileall -q app schemas main.py；node --check frontend/app.js；git diff --check。
- 启动：.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000。

## 数据与安全硬约束

- .env 及真实密钥绝不读取后输出、提交或写入报告；只维护无值的 .env.example。
- .novel_accounts、.novel_ai、.novel_independent、.novel_projects、.novel_memory、.novel_transactions 是本地数据，禁止删除、批量改写或提交。
- 不提交 .codex、.venv、缓存、浏览器现场、审计证据、质量研究 quarantine。
- 正文始终由作者拥有；独立创作不出现 AI 续写/改写；AI 只维护一条正式正文。
- 不新增真实支付、管理员、多人协作、分享发布、平行正文或生产部署。
- 自动化测试使用 fake/确定性运行时，不调用真实模型、图片或付费服务。

## 协作与交付

- 产品决策先写 docs/DECISIONS.md，再同步相关规格、流程和验收。
- 长任务先读本文件、PROGRESS.md、BLOCKED.md 和 docs/README.md；每轮记录真实命令结果。
- 不用 skip、放宽断言、吞异常或假数据制造通过；保留既有 dirty worktree 并区分归属。
- 当前是 GitHub 开发版准备阶段：阶段 27 独立审计已通过；离线质量门 Q2 已验证，但真实生成质量增益与产品集成仍 pending；未部署生产。
