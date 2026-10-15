# 叙脉现役交付矩阵

核对范围：2026-10-13阶段36独立工作台返修。过程、准确测试数字和提交SHA见 [PROGRESS](../PROGRESS.md)，未闭合项见 [BLOCKED](../BLOCKED.md)；本表不复制第二套进度账。

状态枚举：`verified-current`（核对一致）、`changed-and-verified`（本轮修改并核验）、`pending`（仍需收口）、`out-of-scope`（本轮不做）、`not-applicable`（不适用）。

| 事实面 | 状态 | 当前答案与证据入口 |
| --- | --- | --- |
| 代码与路由 | pending | 章内目录与人物/剧情图已集成checkpoint；独立反例与交互返修后才能冻结。保留FastAPI/原生前端，不增生产路由或付费调用。 |
| 运行态与数据 | changed-and-verified | 8052为当前阶段可编辑隔离验收副本，模型调用关闭；原工作区与原作品文件hash保持。目录绑定当前正文，保存和证据仍受来源/revision门禁保护。 |
| 权威文档 | changed-and-verified | 决策、规格、交互、设计、验收和使用/架构/开发说明对齐章→节、图形优先与历史入口延期；准确验证结果留在进度页。 |
| 规则与交接 | changed-and-verified | 当前项目规则是根AGENTS.md，指向阶段36；只读盘点未发现上级规则文件或同源软链要求。敏感文件与测试现场保持ignore。 |
| 记忆面 | not-applicable | generated-read-only；不读取或改写平台生成记忆，不建立平行项目知识库。 |
| 工作区与现场 | pending | 原dirty工作区、各阶段worktree、私有样本及审计现场均保留；未执行删除或归档。用户复核后若要清场，需单独确认。 |
| 设计依据 | verified-current | 延续已有A版首页；官方Scrivener概要/目录和Detroit路径阅读仅作机制参考，不复制资产，不生成无依据关系或游戏选项。 |
| 自动化与独立验收 | pending | 基线回归通过，但本阶段独立反例和最终浏览器/同SHA CI仍需收口；详细证据见进度页，不能把旧阶段通过当成本轮通过。 |
| 真实模型产品化 | pending | 本篇MiMo候选复用，不新增费用；来源编号选择、绑定及定点修复尚未接入产品一键试拆/全书增量。 |
| Q2/Q3与文学质量 | out-of-scope | 项目外Q2既有结论保留，本轮不重跑Q3、不外推通用文学质量或整书成本。 |
| 生产部署与平台扩张 | out-of-scope | 不部署，不新增支付、管理员、云同步、多人协作、分享发布或平行正文。 |
| GitHub开发版交付 | pending | [Draft PR #13](https://github.com/Reen-Ai-H/novelagent-xumai/pull/13)堆叠在阶段35/34候选上；部分checkpoint已推送，最终提交与双平台CI待收口。未合并、未切原目录。 |

## 公开发布原则

公开分支只包含源码、schema、测试、权威文档、规则、无值.env.example和设计参考。真实Key、账户、正文、模型缓存、usage数据、审计截图报告、浏览器profile、.codex和项目外质量研究全部排除。

GitHub main是V1开发基线，不等于本地候选或生产部署。各阶段依照根规则独立提交推送；工程检查、独立审计、作者验收分别记录。新旧服务不要共享数据目录，回退边界见 [开发与运维](DEVELOPMENT.md)。
