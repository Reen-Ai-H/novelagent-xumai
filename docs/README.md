# 叙脉文档索引

2026-10-18 当前实施为[阶段37 · 独立创作本机完整可用版](goals/STAGE_37_USABLE_WORKSPACE.md)：正式六章、A版分层与状态页已复核，真实分析未通过；三次整稿首包失败后，[章级事实预览](STAGE_37_CHAPTER_PREVIEW_CONTRACT.md)已集成并完成主免费测试，独立复核进行中，暂不追加同类付费试跑。用户新授权5元，独立于旧2元账；Notion仅作者选择已验收。下方阶段36是继承基线，不再代表当前交互目标；决定和结果分别见[DECISIONS](DECISIONS.md)与[PROGRESS](../PROGRESS.md)。

2026-10-16 网页端接手见 [CODEX_WEB_HANDOFF](CODEX_WEB_HANDOFF.md)：当前最新进度在阶段36分支，尚未合并到 `main`；含基线、环境、验证及本机私有材料边界。

> 继承基线为 [阶段 36 · 工作台减法与结构化阅读](goals/STAGE_36_VISUAL_READING.md)。用户认可主配区分，不代表界面和导入已验收。研究依据见[图形阅读设计](research/STAGE_36_VISUAL_READING_2026-10-13.md)。

阶段 35 的外部机制参考、真实问题与受控试跑口径见 [识别与阅读组织](research/STAGE_35_RECOGNITION_AND_READING_2026-10-13.md)。

模型接入的未完成目标继续见 [阶段34](goals/STAGE_34_MIMO_INDEPENDENT.md)；当前进度与实际门禁统一见 [PROGRESS](../PROGRESS.md) 和 [BLOCKED](../BLOCKED.md)。

2026-09-23 新增 [完整平台演进与架构评估](research/PLATFORM_EVOLUTION_ASSESSMENT_2026-09-23.md)：区分最新主线与未合并拆解候选，含竞品研究复核、隔离测试、定向重构建议与完整平台交付路线。该报告不是新的产品决策或功能验收结论；其中标明本页旧状态与远端实际状态的差异。

轻量范围沿用2026-09-13决定：优先主要人物、大剧情、主要明暗线与必要节奏，不照搬竞品、不要求六视角全部建齐。来源见 [阶段32目标](goals/STAGE_32_DECONSTRUCTION_DEPTH.md)和[机制调研](research/NOVEL_GENERATION_PRODUCT_RESEARCH_2026-09-13.md)。

这里保存跨会话仍然有效的产品知识。聊天记录、临时计划和历史 README 不再作为现役产品事实来源。

## 事实优先级

发生冲突时按以下顺序裁决：

1. 用户后来明确确认的决定，并已经写入 `DECISIONS.md`。
2. `PRODUCT_SPEC.md`、`UX_FLOWS.md`、`DESIGN_SYSTEM.md`、`ACCEPTANCE.md`。
3. A 版视觉原型 `../design-prototypes/style-a-archive/`。
4. 当前代码、schema 和测试所描述的“已实现状态”。
5. 根目录 `README.md`、`docs/USER_GUIDE.md` 和 `docs/DEVELOPMENT.md` 的现役使用说明；`docs/history/` 只作阶段回溯。

产品目标与当前代码不一致不叫文档冲突：产品文档说明“要做成什么”，代码和 README 说明“现在已经做到什么”。智能体不得因为旧代码仍是 Human-in-the-Loop，就删掉已经确认的 AI 自动导演模式。

## 文档分工

| 文件 | 唯一职责 | 何时更新 |
| --- | --- | --- |
| `PRODUCT_SPEC.md` | 产品定位、功能范围、硬约束 | 产品决策改变时 |
| `UX_FLOWS.md` | 用户流程、状态变化、数据语义 | 流程或状态合同改变时 |
| `DESIGN_SYSTEM.md` | A 版视觉、页面、动效规则 | 视觉方向或组件规则改变时 |
| `DECISIONS.md` | 已确认决定和延期事项 | 每次产品讨论拍板后 |
| `ACCEPTANCE.md` | 首版可交付标准 | 版本范围或验收改变时 |
| `AGENT_WORKFLOW.md` | 长任务如何开始、续跑和交接 | 协作方式改变时 |
| `ROADMAP.md` | 后续阶段顺序、依赖和完成门槛 | 长期优先级或阶段顺序改变时 |
| `USER_GUIDE.md` | 面向作者的安装、操作、备份和常见问题 | 用户流程或限制改变时 |
| `ARCHITECTURE.md` | 当前分层、数据、事务和隐私边界 | 架构合同改变时 |
| `DEVELOPMENT.md` | 本地开发、检查、恢复与发布边界 | 工程流程改变时 |
| `CLOSEOUT_MATRIX.md` | 代码、运行态、文档、规则和质量事实矩阵 | 收口状态改变时 |
| `templates/` | 任务级进度与阻塞模板 | 模板结构改变时 |
| `goals/V1_IMPLEMENTATION.md` | 已排队的 A 版首版实现目标 | 首版范围或完成状态改变时 |
| `goals/STAGE_32_DECONSTRUCTION_DEPTH.md` | Windows 接棒后可直接执行的阶段 32 任务书 | 阶段 32 范围、顺序或验收改变时 |
| `STAGE_32_CONTRACT.md` | 阶段 32 冻结的版本化 schema、证据、状态、锁与前后端接缝 | 架构合同经复核调整时 |

## 当前状态

- 2026-10-15：阶段36图形阅读与章内目录已完成自测和独立复核，Notion同步完成，保持 [Draft PR #13](https://github.com/Reen-Ai-H/novelagent-xumai/pull/13)。本地可编辑验收副本不覆盖原运行目录；未合并、未部署。
- 代码、运行态、规则与文档状态见 [交付矩阵](CLOSEOUT_MATRIX.md)；准确测试数字与 SHA 只在 [PROGRESS](../PROGRESS.md) 维护，不能沿用旧阶段数字。
- 独立作品拆解保留来源校验、后台恢复、证据回链和账户隔离，新增图形阅读与只读章内目录；图不编造关系，目录不改正式章。
- 项目外离线质量门 Q2 已验证：36 例脱敏黄金集、宏 F1=1.000、semantic-needed 覆盖率 1.000、14 项测试通过、外部请求/Token/费用为 0。真实生成质量增益、产品集成和 Q3 仍 pending。
- 文学质量阶段 23B 为 C；本开发版未部署生产，也不提供正式支付、管理员或云同步。
- A、B、C 共 21 张探索图保留；A 是现役实现基准，B/C 只作后续灵感参考。
- Windows 迁移步骤见 `WINDOWS_MIGRATION.md`；CI 覆盖 Ubuntu/Windows、Python 3.12 和 Node LTS。
- 后续每个阶段必须在独立 `codex/stage-<编号>-<主题>` 分支提交并推送；需复核的阶段保持 Draft PR，通过后再合并主线。
- 下一步及长期顺序以 `ROADMAP.md` 为唯一入口，不沿用历史阶段的默认排期。

## 给新智能体的最短入口

先读根目录 `AGENTS.md`、`PROGRESS.md`、`BLOCKED.md`，再按任务读取规格和本索引。长任务继续维护根目录进度与阻塞；阶段历史在 `history/IMPLEMENTATION_HISTORY_2026-08.md`。
