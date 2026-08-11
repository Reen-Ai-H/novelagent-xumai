# 叙脉

> 新一代写作体验

叙脉是面向中文长篇作者的 Web 写作与作品记忆工具。它把作者正文、人物、剧情线、伏笔、疑问点和章节快照长期保存，并提供两条平等路径：

- 独立创作：作者写正文，系统负责保存、章末分析和故事档案。
- AI 辅助写作：作者与主编补全蓝图，导演台在关键节点提供三个互斥选择，AI 继续生成唯一正式正文。

## 开发版状态

这是本地 JSON 持久化的 GitHub 开发版，不是生产服务。阶段 27 独立审计已通过（P0/P1/P2/P3 均为 0）；当前基线为 107 个 unittest，0 failed、0 skipped，OpenAPI 54 paths / 57 operations，旧 /novel 16 paths / 19 operations。

真实 DeepSeek 连续三章产品链已经验证。离线质量门研究 Q2 已验证（项目外脱敏黄金集宏 F1=1.000、semantic-needed 覆盖率 1.000、14 项测试通过、外部请求/Token/费用为 0）；真实生成质量增益及产品集成仍 pending，Q3 不在本阶段执行。文学质量阶段 23B 结论为 C，不能把功能审计通过写成小说质量通过。

## 已实现

- 首页、邮箱本地开发登录、持久会话、书架搜索和作品新建。
- 独立作品：空白建书、TXT/MD/DOCX 预览确认、三栏编辑器、服务端自动保存、保存冲突、章末确定性演示分析、通知、完整故事档案和章节快照。
- 旧章集中修改：确认全部修改、忽略轻微措辞、全文重建、30 天可恢复历史稿本。
- AI 创作室：主编对话、九项蓝图、服务端确认和持久恢复。
- AI 导演台：全自动/关键节点暂停、后台运行、暂停/继续/重试、三选一（含把决定交给角色）、纯文本正文、审校、档案更新和唯一正式正文。
- 安全边界：故事人物私有记忆不返回浏览器；结构化阶段严格 JSON；正文使用受验证的纯文本协议；跨 store 事务有 journal、staging、commit marker、作者 revision 冲突补偿和幂等恢复。
- 旧 /novel 兼容路由仍保留并执行鉴权/归属校验，不代表推荐的新用户入口。

## 明确未实现或不在范围

- 生产部署、云端同步、注册邮件、手机号/微信登录、正式积分计费、支付和管理员后台。
- 分享、发布、多人协作、社交消息中心、平行正文、自动全员人像。
- 离线质量门研究 Q2 已验证，但尚未接入产品运行时；真实生成质量增益、产品集成和 Q3 仍 pending。

## 页面与两条流程

~~~text
首页 → 邮箱登录 → 书架
  ├─ 独立创作 → 空白/导入 → 编辑器 → 完成本章 → 故事档案
  └─ AI 辅助写作 → 主编创作室 → 确认蓝图 → 导演台 → 编辑器/故事档案
~~~

页面深链接包括 /、/login、/library、/independent/{project_id}、/ai/{project_id}、/ai/{project_id}/director、/archive/{project_id}。

## 技术栈与目录

- 后端：FastAPI、Pydantic、Python；兼容旧链路保留 LangGraph/LangChain 依赖。
- 前端：frontend/index.html、frontend/styles.css、frontend/app.js，原生 HTML/CSS/JS。
- API：app/entry_routes.py、app/independent_routes.py、app/ai_routes.py、app/archive_routes.py、app/novel_routes.py。
- 数据合同：schemas/；核心服务：app/core/；自动化测试：tests/；产品与研发文档：docs/；A 版原型：design-prototypes/。

## 5 分钟本地启动

~~~bash
git clone https://github.com/aswansong/novelagent.git
cd novelagent
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
~~~

然后打开 http://127.0.0.1:8000。停止服务使用终端 Ctrl-C。若端口被占用，把 8000 替换为其他本地端口；不要使用 .env 或 .novel 数据目录作为 Git 提交内容。

## 模型配置

无 Key 时可以完整使用确定性演示路径：界面明确标注演示推演，创作积分预算和已用均为 0，不调用供应商。

有 OpenAI-compatible 配置时，在本机 .env 中填写（不要把真实值提交）：

~~~dotenv
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_TEMPERATURE=0.7
~~~

也兼容 OPENAI_BASE_URL、LLM_BASE_URL，以及百炼别名 DASHSCOPE_API_KEY、DASHSCOPE_BASE_URL、DASHSCOPE_MODEL。开发测试显示模型已连接但不结算正式创作积分；供应商失败进入可重试失败态，不静默改用模板。

## 测试与检查

~~~bash
.venv/bin/python -W ignore -m unittest discover -s tests -q
.venv/bin/python -m compileall -q app schemas main.py
node --check frontend/app.js
git diff --check
~~~

基线是 107 tests、0 failed、0 skipped。OpenAPI 与旧 /novel 数量也应保持至少 54/57 和 16/19。

## 数据、隐私与备份

本地服务会使用 .novel_accounts、.novel_ai、.novel_independent、.novel_projects、.novel_memory、.novel_transactions 等目录。它们属于账户、作品、模型安全元数据和事务恢复数据，不要直接编辑 JSON。备份前先停止服务，复制整个相关数据目录到受保护位置；恢复前停止服务并保留原目录副本。更多说明见 docs/USER_GUIDE.md 和 docs/DEVELOPMENT.md。

## 权威文档

- 使用：[docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- 架构：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 开发运维：[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- 产品：[docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md)
- 交互：[docs/UX_FLOWS.md](docs/UX_FLOWS.md)
- 设计：[docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md)
- 验收：[docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)
- 收口矩阵：[docs/CLOSEOUT_MATRIX.md](docs/CLOSEOUT_MATRIX.md)
- 历史阶段：[docs/history/IMPLEMENTATION_HISTORY_2026-08.md](docs/history/IMPLEMENTATION_HISTORY_2026-08.md)
