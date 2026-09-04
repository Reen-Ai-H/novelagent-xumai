# 叙脉文档索引

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
| `USER_GUIDE.md` | 面向作者的安装、操作、备份和常见问题 | 用户流程或限制改变时 |
| `ARCHITECTURE.md` | 当前分层、数据、事务和隐私边界 | 架构合同改变时 |
| `DEVELOPMENT.md` | 本地开发、检查、恢复与发布边界 | 工程流程改变时 |
| `CLOSEOUT_MATRIX.md` | 代码、运行态、文档、规则和质量事实矩阵 | 收口状态改变时 |
| `templates/` | 任务级进度与阻塞模板 | 模板结构改变时 |
| `goals/V1_IMPLEMENTATION.md` | 已排队的 A 版首版实现目标 | 首版范围或完成状态改变时 |

## 当前状态

- 文档收口日期：2026-09-04；阶段 31E 已完成前后端候选集成，等待独立复核。
- GitHub `main` 是当前 V1 开发基线：阶段 27 独立审计 P0/P1/P2/P3 均为 0；基线 107 tests、0 failed、0 skipped。
- 当前 OpenAPI 为 58 paths / 61 operations，旧 `/novel` 为 16 paths / 19 operations；真实 DeepSeek 三章链路已验证。
- 独立作品拆解已接入真实前端工作区：支持七种 canonical 状态、服务端后台恢复、来源证据回链和账户隔离；阶段 31E 候选基线为 133 tests、0 failed、0 skipped。
- 项目外离线质量门 Q2 已验证：36 例脱敏黄金集、宏 F1=1.000、semantic-needed 覆盖率 1.000、14 项测试通过、外部请求/Token/费用为 0。真实生成质量增益、产品集成和 Q3 仍 pending。
- 文学质量阶段 23B 为 C；本开发版未部署生产，也不提供正式支付、管理员或云同步。
- A、B、C 共 21 张探索图保留；A 是现役实现基准，B/C 只作后续灵感参考。
- 后续每个阶段必须在独立 `codex/stage-<编号>-<主题>` 分支提交并推送；需复核的阶段保持 Draft PR，通过后再合并主线。

## 给新智能体的最短入口

先读根目录 `AGENTS.md`、`PROGRESS.md`、`BLOCKED.md`，再按任务读取规格和本索引。长任务继续维护根目录进度与阻塞；阶段历史在 `history/IMPLEMENTATION_HISTORY_2026-08.md`。
