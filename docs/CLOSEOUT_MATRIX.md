# 阶段 28 知识收口矩阵

状态枚举：`verified-current`（与代码/运行态核对一致）、`changed-and-verified`（本轮修改并核验）、`pending`（有明确后续工作）、`out-of-scope`（本轮不做）、`not-applicable`（不适用）。

| 事实面 | 状态 | 当前答案与证据入口 |
| --- | --- | --- |
| 代码与路由 | changed-and-verified | FastAPI `main.py`、`app/`、`schemas/`、`frontend/`；阶段31作品拆解已整合并通过最终审计；当前 58/61，全站旧 `/novel` 16/19。 |
| 运行态与数据 | verified-current | 本地 JSON store、HttpOnly 会话、journal/staging/commit marker、作者 revision 优先；`.novel_*` 为本机数据，不纳入发布。 |
| 权威文档 | changed-and-verified | `PRODUCT_SPEC`、`UX_FLOWS`、`DESIGN_SYSTEM`、`ACCEPTANCE`、`DECISIONS` 与本文件、`USER_GUIDE`、`ARCHITECTURE`、`DEVELOPMENT` 已指向当前开发版状态。 |
| 规则与交接 | changed-and-verified | 根 `AGENTS.md` 保留下一次 Agent 必须遵守的边界；`PROGRESS.md`/`BLOCKED.md` 为本阶段现状；阶段旧记录在 `docs/history/`。 |
| 记忆面 | not-applicable | Codex 生成记忆、`.codex` 现场和审计证据不属于仓库发布；保持 generated-read-only / n/a，不修改。 |
| 工作区残留 | pending | V1 主工作树已发布；另一个旧 worktree 含未提交源码和 `.novel_*` 本地数据，按数据保护规则保留。可确认无用的本地历史副本和临时文件单独清理。 |
| 设计资产 | verified-current | `design-prototypes/` 作为 A/B/C 只读参考纳入；不改原型，不把原型当终审证明。 |
| 自动化门禁 | changed-and-verified | 阶段31发布候选 135 tests、0 failed、0 skipped；compileall、node check、diff check、OpenAPI、canonical API 与 Ubuntu/Windows CI 均已复核。 |
| 离线质量门 Q2 | changed-and-verified | 项目外脱敏黄金集 36 例，宏 F1=1.000、semantic-needed 覆盖率 1.000、14 项测试通过、外部请求/Token/费用 0；研究目录不复制。 |
| 真实生成质量增益与产品集成 | pending | Q2 离线研究尚未接入叙脉运行时；Q3 真实模型 A/B 未执行，建议上限 12 请求/20,000 tokens。 |
| 文学质量 | pending | 阶段 23B 结论为 C；功能审计通过不等于小说质量门通过。 |
| 生产部署、支付、管理员、云同步 | out-of-scope | 本开发版不部署、不接正式支付、不提供管理员和公网云同步。 |
| Windows 迁移与跨平台 CI | changed-and-verified | `docs/WINDOWS_MIGRATION.md` 提供 PowerShell 启动/数据迁移边界；`.github/workflows/ci.yml` 覆盖 Ubuntu/Windows、Python 3.12、Node LTS；不加载 `.env`。 |
| GitHub 开发版交付 | changed-and-verified | `codex/stage-31-independent-deconstruction-release` 已推送，PR [#1](https://github.com/Reen-Ai-H/novelagent-xumai/pull/1) 已合并；`origin/main` 为 `8e42cb6486e6baa66afd7f463448cb39eb51dc3d`，其树与最终候选一致，Ubuntu/Windows CI 均通过。 |

## 公开发布原则

公开分支只包含源码、schema、测试、权威文档、规则、无值 `.env.example` 和设计参考。真实 Key、账户、正文、模型缓存、usage 数据、审计截图报告、浏览器 profile、`.codex` 和项目外质量研究全部排除。

GitHub `main` 是 V1 开发基线。阶段31候选已审计，阶段31I 已通过 PR [#1](https://github.com/Reen-Ai-H/novelagent-xumai/pull/1) 合并到新仓库主线；后续阶段仍必须在独立 `codex/stage-<编号>-<主题>` 分支完成提交和推送，仍待审计或质量复核的变更以 Draft PR 交接。
