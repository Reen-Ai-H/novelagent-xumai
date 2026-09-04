# 阶段 33 任务书：独立创作体验收口

本文是阶段 32 合并后的独立创作体验合同。它冻结产品范围、跨页面状态、数据安全、失败恢复、实现分工和验收设计，不代表功能已经实现，也不替代独立审计结论。

阶段 33 的基线是 GitHub 最新 `main`，当前接棒时为 `ec2f31a`。阶段 32 已把作品拆解的 2.0 报告、七种 `effective_status`、来源 token、证据回链、项目锁和 CAS 发布合同冻结并通过独立审计；本阶段不重做这些合同，只把它们接回作者的编辑、章末、档案和稿本恢复路径。

## 1. 为什么现在做

阶段 32 解决了“作品可以被深度理解”的结构问题，但作者完成一章之后仍要在多个页面之间自行拼接状态。当前摩擦集中在以下几个接缝：

| 接缝 | 作者可能遇到的摩擦 | 阶段 33 的收口方向 |
| --- | --- | --- |
| 编辑器与保存 | 标题、正文、服务器 revision 和本地缓冲不是一个可解释的事实；保存失败后作者不知道能否离开。 | 标题和正文同次保存，明确保存状态，失败保留输入并可重试，过期写入不覆盖服务器内容。 |
| 完成本章与后台分析 | 完成本章、章节分析、档案快照和拆解结果的先后关系不够直观；重复点击可能制造重复任务。 | 完成本章只接受最近一次已保存内容，任务/outbox/通知幂等，后台状态可离页恢复。 |
| 档案与历史快照 | “最新状态”和“第 N 章时”容易混淆，查看历史后不应改变当前编辑上下文。 | 每个页面显示稿本和快照上下文，历史视图只读，返回最新是显式动作。 |
| 旧章批量修改 | 修改第 3、20、67 章时需要一次决定，但弹层打开期间可能已经产生新改动。 | 当前稿本只有一个待确认批次，批次有公开身份和版本号，确认使用前置条件和幂等键。 |
| 版本恢复 | 现有只读预览不能充分说明“将恢复什么、会影响什么”；直接恢复容易误操作。 | 先预览目标稿本与影响，再确认恢复；恢复永远产生新的当前稿本，历史记录不改写。 |
| 档案/拆解与重建 | 新稿本重建期间，旧档案或空档案可能被误读为当前事实。 | 页面显示服务端重建/失败状态，旧来源只读，不把历史结果冒充当前结果。 |

阶段 33 不追求增加入口，而是让一位中文长篇作者可以沿着一条路径完成写作、回看、修改和恢复，并且在每一步都知道哪一份正文是当前正式内容。

## 2. 唯一验收锚点

使用授权或合成的中文长篇文本，不使用受版权保护的原文。主流程至少覆盖 100 章，核心情节可以是以下结构：

1. 作者登录并新建“独立创作”作品，导入或从空白开始。
2. 在预览中确认标题、章节数、字数和无法识别片段；确认后才写入正式稿本。
3. 选择一章，编辑标题和正文，观察本地缓冲、保存中、已保存和 revision；刷新后正文逐字一致。
4. 点击“完成本章”，离开正文进入故事档案和作品拆解；后台任务完成后看到当前档案、章节快照、深度六视角和当前证据回链。
5. 在不改变当前稿本的前提下查看第 3 章历史档案快照，明确只读，再回到最新状态。
6. 修改第 3、20、67 章的标题或正文。自动保存只形成一个待确认批次，不创建版本、不立即全文重建。
7. 打开“确认全部修改”，核对三章范围和差异；取消后改动仍在。选择“忽略轻微措辞并继续”时，当前稿本 ID 不变，旧档案明确标为截至旧来源；选择“根据当前全文重建”时，旧稿本进入 30 天恢复期，新稿本成为唯一 active 版本。
8. 在重建完成后打开版本记录，先只读预览旧稿本和影响，再取消一次确认，确认一次恢复。恢复创建新的当前稿本，旧稿本正文、标题、创建时间和恢复期限保持不变。
9. 刷新、退出重登，重新进入同一作品，能够继续看到当前稿本、任务、档案、拆解来源和历史记录。

失败分支至少在同一套确定性运行时中覆盖一次：保存网络失败后重试、章末分析失败后重试、后台服务重启后恢复、批次或稿本前置条件过期、历史版本过期，以及拆解 outbox 派发失败后补偿。失败分支不能替代成功主流程。

## 3. 范围

### 3.1 必须完成

- 独立编辑器的章节选择、标题/正文同次保存、保存状态、revision 冲突和失败恢复。
- “完成本章”的服务端任务、快照、档案更新、通知和拆解 outbox 接缝；重复请求只产生一份有效结果。
- 当前稿本、历史快照、待确认修改批次和版本记录的统一上下文显示。
- 多章修改批次的查看、取消、忽略、全文重建和并发过期保护。
- 历史稿本的只读预览、影响摘要、显式恢复确认、幂等恢复和 30 天过期边界。
- 重建/恢复期间的档案与作品拆解状态，失败和重启后的可恢复展示。
- 阶段 32 深度拆解结果在本流程中的来源版本、revision、hash 和证据只读边界。
- 1440×900、1024×900、键盘、焦点、reduced-motion、错误/加载/禁用/空态的真实浏览器验收。
- API 的严格公开投影、账户隔离、请求前置条件和安全错误合同。

### 3.2 不在范围内

- AI 创作室、AI 导演台、主编对话、角色私有记忆和生成质量重构。
- 类型蒸馏、类型结构引擎、文笔表达引擎、真实模型质量增益或 Q3 A/B。
- 新的公共语料库、训练数据上传、受版权保护原文打包或可还原语料。
- 分享、公开发布、投稿、云同步、多人协作、管理员、正式支付、真实生产部署和原生移动端。
- 第二条正式正文、长期平行分支、分支树或把作品拆解结果写回作者正文/故事档案。
- 自动生成具象角色图、全员插画或图片服务质量评测。
- 通过修改阶段 32 2.0 schema、七种 canonical 状态或证据定位单位来绕开接缝问题。

## 4. 不可回退的产品不变量

1. 作者正文永远优先。任何后台分析、拆解、重建或恢复都不能覆盖已保存的作者正文。
2. 同一作品只有一个 `active` 稿本。重建和恢复通过新稿本表达，不就地改写历史稿本。
3. 标题和正文是一个作者保存事实。标题来源明确，独立创作不出现 AI 续写、改写或代写操作。
4. 普通保存不触发全文重建。已有正式正文的章节改动只能进入当前稿本唯一待确认批次。
5. 只有作者明确选择后才结算批次。弹层取消不能丢改动，批次变旧不能按旧摘要继续执行。
6. 完成本章只使用最近一次已保存的正文和标题；同一稿本、章节、正文 hash 的重复请求复用任务、快照、通知和拆解事件。
7. 历史档案快照、历史稿本、历史拆解证据都只读。返回最新状态是显式动作，历史页面不能改变当前编辑器输入。
8. 阶段 32 的深度结果只有在当前来源匹配、运行完成和 `report_version="2.0"` 时才显示为当前完成结果。
9. 页面文字、颜色、动画和浏览器内存都不能单独代表持久状态；刷新/重登后的服务端读取必须能恢复事实。

## 5. 跨页面公开状态合同

阶段 33 不新增一套互相独立的状态机。编辑器、档案、版本记录使用同一个 workspace 上下文；作品拆解继续使用 `STAGE_32_CONTRACT.md` 的 canonical 投影。

### 5.1 workspace 上下文

所有独立 workspace、档案和版本操作的公开响应必须能表达以下信息，字段名可以按现有 API 命名保持一致，但语义不能省略：

| 信息 | 必须表达的内容 |
| --- | --- |
| 作品身份 | `project_id`、标题、模式；只在当前账户授权后返回。 |
| 当前稿本 | `active_version_id`、label、`status`、创建/更新时间、`recoverable_until`；只有一份 active。 |
| 编辑章节 | 章节 ID、章节号、标题、正文、`server_revision`、字数、章节状态；标题和正文来自同一保存结果。 |
| 正式边界 | 当前草稿与上次正式正文的差异状态、上次完成 hash 或等价来源；作者可以知道“已保存但尚未完成/分析”。 |
| 待确认批次 | `batch_id`、`version_id`、公开 `batch_revision`、创建/更新时间、每章差异摘要和建议；不放正文副本以外的内部材料。 |
| 任务 | 任务 ID、类型、状态、稿本/章节归属、可重试标记、安全错误 code/message、时间；不返回请求幂等键。 |
| 档案上下文 | `context_version_id`、`view=latest|snapshot`、选中章节、`read_only`、档案分析状态和来源 revision；历史视图明确只读。 |
| 拆解上下文 | 阶段 32 的 `effective_status`、`run_status`、`source_match`、来源 version/revision/hash 和 actions；不由前端猜测。 |
| 能力 | 由服务端返回是否可保存、完成、确认、重建、重试、恢复或返回最新；前端不能只按按钮样式猜测。 |

作者自己的当前正文和历史正文可以在已授权的编辑/只读预览响应中返回，因为恢复前必须能核对内容；作品拆解结果、history 和 evidence 接口仍不得返回整章正文。

### 5.2 状态语义

客户端保存状态是短暂 UI 状态，只在当前页面内存在，不作为服务端事实：

```text
idle → dirty → saving → saved
                 └→ failed → retrying → saved
                 └→ conflict → reload_server | keep_local_and_retry
```

服务端章节和任务沿用现有枚举，但阶段 33 固定其解释：

| 层 | 状态 | 语义 |
| --- | --- | --- |
| 章节 | `drafting` | 当前输入已保存，但尚未成为本章最近正式分析来源，或仍有待确认修改。 |
| 章节 | `analyzing` | 本章最近正式内容已锁定为分析输入，任务仍在运行；编辑器可以继续打开。 |
| 章节 | `ready` | 最近正式内容已有成功的档案分析和快照。 |
| 章节 | `failed` | 分析失败但正文保留；页面必须提供可理解的重试动作。 |
| 任务 | `queued` / `running` | 服务端后台状态；离页和刷新不改变任务身份。 |
| 任务 | `completed` | 任务和对应产出已经持久化。 |
| 任务 | `failed` | 失败信息已脱敏且可按合同重试；不能清空正文。 |
| 版本 | `active` | 唯一可继续写入的当前稿本。 |
| 版本 | `recoverable` | 历史只读稿本，处于恢复期限内。 |
| 版本 | `archived` | 历史只读稿本，不能恢复或已过期；记录仍可查看。 |
| 档案视图 | `latest` | 当前 active 稿本的最新已分析状态。 |
| 档案视图 | `snapshot` | 当前稿本指定章节的只读快照。 |
| 档案视图 | `rebuilding` / `failed_retryable` | 当前稿本的档案尚在重建或可重试，不能展示旧稿本档案为当前结果。 |
| 拆解 | 七种 canonical 状态 | 完全继承阶段 32：`empty`、`queued`、`running`、`completed`、`failed_retryable`、`stale`、`rebuild_required`。 |

## 6. API、并发和持久化边界

### 6.1 写入前置条件

以下请求必须携带当前上下文前置条件；实际字段可复用现有 request model，但不能只靠路径和最后一次 JSON replace：

| 动作 | 必要前置条件 | 幂等要求 |
| --- | --- | --- |
| 保存标题/正文 | `expected_version_id`、章节 `expected_revision`、正文/标题、客户端 mutation key。 | 同 mutation key 且 payload 相同返回原保存结果；不同内容不能覆盖更新后的 revision。 |
| 完成本章 | `expected_version_id`、章节 `expected_revision`、与已保存内容一致的正文/标题、idempotency key。 | 同稿本/章节/hash 复用同一任务；不重复快照、通知或 outbox。 |
| 确认批次 | `batch_id`、`expected_version_id`、`expected_batch_revision`、`decision`、idempotency key。 | 同一批次和 key 重复返回同一结算结果；批次变旧返回安全 409。 |
| 重建/重试 | 当前 source 或 active version 前置条件；pending changes 存在时不能绕过确认。 | 同 source/合同身份复用同一活动任务，不追加 history。 |
| 预览恢复 | 目标 version、只读 preview、当前 active version 和影响摘要。 | 预览不写正文，不改变 active version。 |
| 确认恢复 | `preview_token` 或等价短期确认身份、`expected_active_version_id`、idempotency key。 | 重复确认不创建第二个新稿本；目标历史内容不变。 |

前置条件不匹配使用安全的 `409`，返回新的上下文摘要但不返回 prompt、内部 revision 或不必要的正文副本。锁不可用使用可重试的 `503`，不能在无锁状态写入。

### 6.2 写入顺序

作者保存、完成本章、批次结算、重建和恢复都进入同一作品级持久项目锁。正文/稿本主记录和拆解 outbox 事件按原子写入；分析和拆解大段读取在锁外进行，发布前重新比较 version、revision、hash 和 CAS revision。

固定顺序为：

```text
授权 → project lock → 读取并校验 active version / chapter revision / batch revision
     → 写入正文或稿本及 outbox → 原子提交 → 释放锁
     → 锁外后台分析 → 发布前重新读取 source → source/CAS 相等才发布
```

禁止持有 deconstruction-specific lock 后反向进入 independent store。阶段 32 已冻结的 `source_version_id + source_revision + source_hash` 绑定、历史 evidence 只读和旧结果保留规则继续有效。

### 6.3 结果可见性

- 本章分析完成前，正文保存结果可以看到，档案快照不能冒充已完成。
- 全文重建/恢复开始后，新稿本正文是当前正式内容，但档案和拆解显示 `rebuilding`/`queued` 等服务端状态；不能把旧稿本档案塞回新稿本。
- 失败只改变任务和派生状态，作者正文、标题、历史稿本和已完成历史结果不删除。
- 服务重启扫描 `queued`/`running` 任务和 outbox；恢复同一个任务身份，不能因为刷新或 GET 创建新任务。

## 7. 失败恢复合同

| 失败点 | 作者看到的状态 | 必须保留 | 允许的恢复动作 |
| --- | --- | --- | --- |
| 文件预览失败 | 导入失败，输入已保留，说明格式/编码/大小原因。 | 原始输入的服务端受控保留记录；不创建 active 版本。 | 重新选择文件或重试预览。 |
| 自动保存失败 | 保存失败·重试；当前输入仍在页面内。 | textarea 内当前输入、已保存服务器版本和冲突信息。 | 重试；离开前 flush，仍失败则警告或阻止离开。 |
| 多端 revision 冲突 | 另一端已更新；可载入服务器版本或保留本地草稿。 | 服务器逐字正文和 revision；本地未发送输入。 | 作者明确选择，不静默合并或覆盖。 |
| 完成本章失败 | 本章正文已保存，分析失败，可重试。 | 正文、标题、task、错误 code、历史档案。 | 重试原任务或在保存新内容后按合同重新提交。 |
| outbox 派发失败 | 正文已保存；拆解稍后恢复或可重试。 | 正文和安全 outbox 事件。 | worker/启动/读取入口补派，不能回滚正文。 |
| 批次确认过期 | 修改批次已更新，请重新读取后确认。 | 所有已保存改动，原 batch 不被半结算。 | 重新打开批次摘要，再次确认。 |
| 全文重建失败 | 新稿本仍为当前，档案/拆解失败可重试。 | 新稿本正文、旧稿本恢复记录、错误信息。 | 重试，不回滚成第二条正文。 |
| 服务重启 | 页面显示后台任务恢复中或最终状态。 | task/outbox/document identity。 | 服务端 worker 继续，GET 只读取/触发幂等 reconcile。 |
| 历史版本过期 | 不能恢复，历史记录仍可查看。 | 历史稿本的只读摘要和过期时间。 | 作者选择仍在恢复期的版本。 |
| 恢复确认过期/active version 变化 | 恢复前置条件已变化，请重新预览。 | 当前作者内容和历史稿本。 | 重新预览并重新确认。 |

## 8. 可访问性和响应式合同

### 8.1 可访问性

- 所有动作使用原生 button、link、input、select 或 textarea；章节、快照、版本和重试入口有可读名称。
- 当前章节、当前稿本、历史只读和后台状态必须同时有文本/语义表达，不能只依赖颜色、图标、闪烁或动画。
- 保存/分析/重建状态使用 `aria-live="polite"`；阻断性错误使用可读的 alert 区域；状态变化不把焦点强行移走。
- 待确认修改和恢复预览使用 native dialog 或等价 modal：打开后焦点进入对话框，Escape/关闭按钮可退出，关闭后焦点回到触发按钮；确认按钮在请求期间禁用。
- 章节目录和六视角 tabs 维持键盘可达。章节目录至少支持 Tab、Enter/Space、Home/End 和方向键；阶段 32 的 roving tabs 方向键合同不能回退。
- 历史快照和历史稿本的所有正文控件为只读或禁用，并显示“历史只读”；不把只读文本放进可提交的当前编辑表单。
- `prefers-reduced-motion: reduce` 下不依赖过渡、打字机或轮询动画表达状态，改为即时更新和状态文字；焦点环仍清晰。

### 8.2 响应式

- 真实 CSS viewport 为 1440×900 和 1024×900 时，`document.documentElement.scrollWidth` 和 `document.body.scrollWidth` 不超过 viewport；不能通过裁切、缩放截图或隐藏溢出制造通过。
- 1024 宽度可以将章节目录、写作区和档案摘要堆叠或收起，但编辑、保存、完成、档案、版本和恢复操作仍可达；长章节列表和预览内容在自己的容器内滚动。
- 中文长标题、emoji、连续无空格文本、错误信息和三章批次摘要都要换行，不覆盖按钮、对话框标题或焦点环。
- 1440 宽度保持正文优先，档案摘要和拆解关系视图不能挤压到无法编辑；宽表格只在局部容器滚动。

## 9. 公开数据与反泄漏边界

### 9.1 允许公开的最小数据

- 已授权作者自己的作品标题、稿本摘要、章节正文和只读版本预览。
- 用于一致性判断的 source version/revision/hash、章节号、最小 evidence excerpt 和作者可理解的状态文字。
- 任务/版本/档案/拆解的稳定 ID 和时间字段，只要不暴露账户归属或内部锁信息。

### 9.2 永远不得出现在公开响应、OpenAPI schema、DOM 或日志

```text
account_id
record_revision / CAS revision
lock owner / lease / worker checkpoint
idempotency_key / client mutation secret
prompt / raw_completion / model chain
private_memory / API key / Authorization header
拆解接口中的整章正文、正文副本或可还原全文的连续片段
内部异常堆栈、文件系统路径、真实用户数据
```

编辑器 textarea 作为作者当前工作区可以包含当前章节正文；上述正文副本禁令针对拆解/档案派生接口、历史列表、错误和浏览器存储，不能用删除作者编辑器内容来“通过”安全门。

未登录返回 401；跨账户访问作品、章节、task、version、archive、deconstruction 或 evidence 返回 404，不泄露存在性。自动化测试只能使用临时隔离目录、合成正文和禁止付费调用的 fake/deterministic runtime，不读取、删除、批量改写或提交 `.novel_*`、`.env`、浏览器现场和审计证据。

## 10. 测试设计

阶段 33 的测试要验证持久事实和跨页面接缝，不用静态文案或一批手工构造结果代替真实流程。建议由管理任务新增以下专项；名称可按仓库现有命名调整，但覆盖项不可删减。

### 10.1 纯合同测试

建议文件：`tests/test_stage33_independent_contract.py`。

- 请求模型拒绝缺少 active version、chapter revision、batch revision、恢复确认或幂等键的写请求，以及额外字段、错误类型和超长文本。
- workspace/archive/version/task 的公开投影不含账户、内部 CAS、锁、幂等键、prompt、raw completion、private memory、路径或异常堆栈。
- current/latest、snapshot、rebuilding、failed、historical/read-only 的投影字段互相一致；历史视图不能标为 current。
- 每次保存 revision 单调增加；标题和正文同一响应；同 mutation key 不重复写入。
- pending batch 的 `batch_id + batch_revision + version_id` 变化可检测；过期确认不能改变正文、active version 或 outbox。
- restore preview 只读，restore confirmation 过期或 active version 变化被拒绝；历史版本只能有一个 active 结果。
- 阶段 32 `DeconstructionResponse` 继续通过严格 schema，pending/rebuilding 时不返回可见旧 result。

### 10.2 真实 API/服务流程测试

建议文件：`tests/test_stage33_independent_flow.py`，使用 `TestClient`、真实本地 store、真实独立服务和合成中文正文；不得 mock 被测核心服务。

1. 导入预览 → 确认：标题、章节号、章节标题和正文逐字持久化，确认前没有 active version。
2. 新章保存 → 完成本章：标题/正文/revision 正确，重复 complete 返回同一 task，只有一份快照/通知/outbox。
3. 分析失败 → 修改/重试：正文不丢、错误脱敏、重试成功后档案和 task 完整。
4. 服务实例重建/worker 恢复：queued/running 和 outbox 最终完成，不重复 document、task、snapshot 或通知。
5. 多端保存冲突：旧 revision 返回 409，服务器正文保留，本地候选没有覆盖；同 mutation retry 可安全收敛。
6. 第 3、20、67 章集中修改：只有一个 pending batch，改动期间没有新版本/全文重建；取消保留改动，忽略保留 active version 并标明旧分析来源。
7. 批次确认竞态：另一端先保存后，旧 batch revision 的 ignore/rebuild 都被拒绝；重新读取后再操作成功且只结算一次。
8. 全文重建：旧版本 recoverable、当前只有新版本，重建期间不显示旧档案为当前；成功后新 archive/deconstruction source 一致，失败后新正文仍可重试。
9. 版本预览/恢复：预览显示目标稿本和影响，预览不写入；取消无副作用；确认一次创建新版本；重复 key 不重复创建；目标历史内容不变。
10. 恢复过期和并发：过期返回 410；active version 变化返回安全 409；作者新正文、历史版本和任务状态均保留。
11. 档案上下文：latest、章节 snapshot、重建中和历史稿本的 `read_only`、version/source/status 一致；回到最新后继续编辑不会带入旧快照。
12. 阶段 32 接缝：当前 evidence 可以按绑定 source 定位；正文/版本变化后旧 evidence 变 historical/read-only，六视角结果不会跳到当前同编号章节。
13. 账户隔离：匿名 401、跨账户所有相关资源 404；公开序列化和错误 body 扫描无禁用字段。

### 10.3 静态前端合同测试

建议扩展 `tests/test_stage31c_deconstruction_frontend.py` 或新增 `tests/test_stage33_frontend_contract.py`，只检查结构性边界，不用静态结果 fixture 伪造运行态。

- 独立编辑器没有 AI 续写/改写/代写操作；标题输入和正文输入走同一保存请求。
- 保存状态包含 dirty/saving/saved/failed/conflict 的文本语义，失败动作保留重试和冲突选择。
- 完成本章按钮只在已保存且正文非空时可用，请求携带当前 version/revision 和幂等键。
- pending dialog 显示批次章节列表，确认/取消/过期响应都回到真实服务端状态；不从页面数组自行推断当前版本。
- version preview 显示只读和影响，restore 在明确确认前不发写请求；恢复后重新读取 workspace。
- archive latest/snapshot/rebuilding/historical 有清晰上下文，历史正文控件不可编辑。
- deconstruction 继续只读取阶段 32 canonical state，证据当前/历史定位规则不变。
- native dialog 的焦点回收、`aria-live`、`aria-busy`、focus-visible、reduced-motion 和无 local/session storage 约束存在。

### 10.4 真实 Windows 浏览器验收

建议新增 `tests/browser_stage33.cjs`，复用 `tests/browser_server.py` 的隔离临时目录方式，但使用独立端口/输出目录。测试必须启动真实 FastAPI app 和 worker，使用 Microsoft Edge + Playwright，不拦截请求、不注入响应、不用 `page.setContent`，仅允许确定性禁止付费 runtime。

每个 viewport 都必须：

- 创建唯一临时账户和合成 100 章中文作品，完成导入预览/确认；断言 UI 与 API 的章节数、标题和正文一致。
- 在编辑器保存带中文标题、emoji 和连续段落的章节，刷新后逐字一致；采集 `save_state` 文本，模拟一次保存失败后使用真实重试动作恢复。
- 完成本章并离开页面，回到作品内看到同一个 task；档案 latest、章节 snapshot、作品拆解 2.0 和当前 evidence 都来自真实服务端。
- 用键盘走完章节目录、档案快照、版本记录和 pending dialog；断言焦点、只读标识、Escape/关闭后的焦点回收和 `prefers-reduced-motion`。
- 修改第 3、20、67 章，确认只出现一个待确认批次；检查三章差异、取消保留、ignore/rebuild 的服务端后果。
- 重建后预览旧版本，核对影响摘要和正文片段；取消确认无版本变化，确认恢复只创建一份新 active version，刷新/重登仍一致。
- 在不同页面/旧 tab 中触发过期操作，看到安全冲突或历史只读，不覆盖新正文。
- 捕获每个页面的 `console` warning/error、`pageerror` 和 `requestfailed`，最终必须全为空；检查根和 body scrollWidth 不超过实际 innerWidth。

输出至少包括：每个 viewport 的 JSON 结果、编辑器/保存失败/待确认/版本预览/档案历史/拆解完成/恢复后的截图。截图是证据，不替代 API 和 DOM 断言。

### 10.5 反作弊门禁

阶段 33 不得以以下方式制造通过：

- `skip`、`todo`、expected failure、放宽已有断言、删除旧测试、吞异常、`|| true` 或只断言 HTTP 200。
- 在 `frontend/**` 内嵌阶段 33 结果、人物/章节/版本 fixture，或用静态 HTML/本地数组掩盖没有接通的 API。
- 使用 `page.route`、`context.route`、mock fetch、拦截响应、`page.setContent`、浏览器 storage 或手工注入后台状态通过真实浏览器门禁。
- 用测试代码直接修改业务 JSON、绕过 API 改 `.novel_*`、把 store 内部写入当作用户流程，或用固定 sleep 代替轮询服务端状态。
- 在成功主流程中使用显式失败哨兵、假的正文、假的版本 ID、假的 source hash 或合同样例代替真实自然中文正文；失败哨兵只允许用于单独验证失败恢复。
- 只截图不检查持久化 API、版本数量、正文逐字一致性、source token、历史只读和账户隔离。
- 裁切、缩放、隐藏 overflow、只检查截图尺寸，或忽略浏览器 console error/warn 来冒充双尺寸响应式通过。
- 读取、输出、提交 `.env`、真实密钥、`.novel_*`、浏览器现场、审计证据或受版权保护原文。

## 11. 建议的实现拆分顺序

管理任务冻结本合同后，建议按不重叠目录分工：

1. **后端合同与数据接缝**：先补公开 workspace/version/restore/pending request/response 合同、前置条件、任务幂等、project lock/CAS 和 safe projection。此任务只改 `schemas/**`、`app/core/**`、独立/档案路由及后端专项测试，不改 `frontend/**`。
2. **后端独立流程**：在冻结合同上接通保存、完成、批次、档案、版本恢复与阶段 32 deconstruction outbox/worker，优先完成真实 API 流程、并发和重启测试。不得以静态 UI 先宣称可用。
3. **前端体验**：后端合同稳定后只改 `frontend/**` 与前端合同测试，接入 server-backed 状态、上下文、失败恢复、dialog、键盘和 1024 响应式；不复制后端状态机，不内嵌正文/结果 fixture。
4. **管理集成与浏览器**：管理任务只新增/维护隔离浏览器脚本、合成正文和质量门，运行 1440/1024 真实 Edge 流程、全量测试、OpenAPI 和静态检查，修复接缝但不把审计断言改宽。
5. **独立审计**：未参与实现的任务检查账户隔离、正文/版本安全、竞态、失败恢复、DOM/响应泄漏、键盘和双尺寸布局；发现 P0/P1/P2/P3 后回派原实现任务，全部为 0 才进入 Draft PR 复核和合并。

## 12. 完成条件

- 阶段 33 专项、全量回归、静态、OpenAPI、真实 Edge 双尺寸和失败反向验证全部有可复跑记录；`failed=0`、`skipped=0`，测试总数不低于阶段 32 基线 204。
- OpenAPI 不低于 58 paths / 61 operations，旧 `/novel` 保持 16 paths / 19 operations；compileall、`node --check frontend/app.js`、`git diff --check` 通过。
- 真实 Edge 在 1440×900、1024×900 完成主流程，实际 CSS viewport 与脚本记录一致，console error/warn、pageerror、requestfailed 均为 0，页面无整页横向溢出。
- API 和浏览器均证明标题/正文逐字保存、任务/版本/批次幂等、历史只读、作者 revision 优先、source token 正确和账户隔离；不能只凭文案或截图通过。
- 阶段 32 深度拆解七态、2.0 报告、证据 source gate 和历史回链不回退。
- 相关文档已同步，阶段分支已提交并推送，Draft PR 的 Ubuntu/Windows CI 通过；独立审计 P0/P1/P2/P3 均为 0 后才可合并。
- 阶段 33 仍不等于文学质量通过、真实生成质量增益通过或生产部署通过；这些状态继续标为 pending。
