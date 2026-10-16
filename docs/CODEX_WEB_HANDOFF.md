# 网页 Codex 接手说明

更新于 2026-10-16。此次只同步研发进度，不启动新功能、不合并 PR、不部署。

## 从这里开始

- 仓库：[`Reen-Ai-H/novelagent-xumai`](https://github.com/Reen-Ai-H/novelagent-xumai)。
- 接手基线：`codex/stage-36-visual-reading` 的最新远端提交，**不要直接从 `main` 开发**。交接前已验证的收口提交为 `728bd2c2012b484b11574d96f6d8afdfbede43a1`；其后的本次交接提交只改文档。
- [Draft PR #13](https://github.com/Reen-Ai-H/novelagent-xumai/pull/13) 基于阶段35；[PR #12](https://github.com/Reen-Ai-H/novelagent-xumai/pull/12) 基于阶段34；[PR #11](https://github.com/Reen-Ai-H/novelagent-xumai/pull/11) 基于 `main`。阶段36已包含前两阶段的已提交成果，不需要重新拼接或合并这三份 PR 才能继续。
- 在云端先核对当前分支和远端基线。若环境默认检出 `main`，先检查工作区是否干净，再取得阶段36分支；有未提交修改时保留现场，不能强制重置。下一阶段确定目标后，再从该基线创建独立 `codex/stage-<编号>-<主题>` 分支。

阅读顺序：[AGENTS](../AGENTS.md) → [PROGRESS](../PROGRESS.md) → [BLOCKED](../BLOCKED.md) → [文档索引](README.md) → [ROADMAP](ROADMAP.md)。实际进度以最新日期为准，旧“进行中”记录保留作历史，不重新执行已完成任务。

## 已交付与尚未完成

| 范围 | 当前事实 |
| --- | --- |
| 人物阅读 | 主配角分层、共同经历图、按需展开摘要与依据；没有足够证据时不编造亲属或敌友关系 |
| 剧情阅读 | 节点式路径、叙事/故事顺序切换保留选中；已有关系保留方向，不虚构游戏选择分支 |
| 正文导航 | 章内小节只读目录、精确光标/引用定位、导入层级修复；不改作者正式章或原文 |
| 界面与保存 | 延续首页A版、窄屏减法、资源刷新升级、保存失败及冲突保护；历史恢复入口按要求暂缓 |
| 后续缺口 | 来源编号绑定、严格校验与模型定点修复尚未完整接入一键试拆/全书增量流程；全书质量与费用仍待验证 |

阶段36已有全量离线、八套浏览器、独立前后端复核及双平台CI证据；准确数字与提交见 [PROGRESS](../PROGRESS.md)。Notion已同步，工程通过不等于作者已验收。模型样例可读不等于产品已能一键复现，也不能外推普遍准确率。

下一轮优先延续 [阶段34的模型产品化目标](goals/STAGE_34_MIMO_INDEPENDENT.md)，具体范围以用户的新任务和最新验收反馈为准。不重新设计整个产品，不扩展到 AI 代写、支付或生产部署。若继续使用子Agent，沿用用户指定的 `gpt-6.1-sol / ultra`；云端是否支持以实际能力为准，不声称已配置、不静默替换模型。

## 云端环境与验证

按仓库CI准备 Python 3.12、Node LTS。在仓库根目录安装依赖并执行隔离检查，不需要真实模型密钥：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -W ignore scripts/verify_offline.py
git diff --check
```

干净、无凭据的CI还执行 `python -W ignore tests/run_quality_gates.py`，包含完整测试、零跳过、OpenAPI与静态门禁。不要用本机的绝对路径或已安装依赖作为云端前提。

前端变更仍需运行 `tests/browser_server.py` 与对应浏览器脚本；先读 [开发手册](DEVELOPMENT.md) 和脚本的环境变量约定。先运行 `browser_stage35_reading.cjs` 建立夹具，再运行依赖它的密度/大数据回归。使用独立端口、合成数据与禁止付费的运行时；Playwright及浏览器需在云端另行确认安装。无法运行时如实记录未验证项，不能以单测替代浏览器验收。

云端环境创建和发布按 [OpenAI官方说明](https://learn.chatgpt.com/docs/environments/cloud-environments)操作；本机个人技能不会自动同步。此交接未创建或配置用户的云端环境，也未验证其浏览器自动化可用性。

## 没有上传的内容

- `.env`、密钥、所有 `.novel_*` 数据、私有正文/报告、`.codex`、浏览器与独立审计现场都不进入 GitHub。云端不能直接访问本机的 `127.0.0.1:8052` 验收副本，勿把这个地址当作云端入口。
- 原阶段34工作区仍有未整合修改，包含提示词、`analysis_delta.py`、真实试跑/离线验证脚本和文档；未跟踪的 `grounded_deconstruction.py`、`repair_analysis_quotes.py`、两份对应测试及一份研究报告也保留在本机。这些不是阶段36已验证基线，不应假设云端已有它们。后续需要复用时先单独检查、脱离私有数据验证，再提交；本轮未删除或盲目打包。
- 真实样本复验需要另行取得授权材料、可用凭据及明确预算。历史2元/10元授权不自动成为云端新试跑授权；本次不新增付费调用。
- Notion连接不保证随本机迁移。连接可用时读取原验收意见并按结果更新；不可用时先以仓库进度继续，不捏造已同步或作者已验收。

本次交接只保证 GitHub 中的代码、测试与进度可接续；本机私有数据和实验现场仍独立保留。
