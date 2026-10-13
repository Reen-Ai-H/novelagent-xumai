# 当前任务进度

## 2026-10-13 · 阶段 36 验收返修（进行中）

- 用户认可本篇主配角区分，要求图形化人物/剧情与游戏式时间路径、明确章/节目录、工作台减法并对齐首页。已读取Notion全部5条验收意见；历史恢复暂缓，原作者意见原文保留。已将相关条目回到处理中，历史恢复改暂缓，不替作者验收。
- 分支 `codex/stage-36-visual-reading`，基线 b1aa4a0 / Draft PR #12；开工隔离离线实跑355 tests、0 failures/errors/skipped、14.734s。原工作区dirty清单保持不变，原8050只读样例继续保留。
- 实际问题：已保存正文只有一正式章，内部五个未编号短标题未进入目录。采取章内只读投影，保留正式章ID/正文/hash/报告引用，不擅自切割迁移。图展示已有关系或共同经历，先后与因果区分，不造游戏分支。
- 实施Sol复用：Dalton `01a13389-2ca6-79f2-ae4d-5eda1aebbc1b`，stage-36-chapter-outline工作区/分支，负责后端目录与导入；Hume `01a13389-2d63-75d2-8a46-781a49a5fb45`，stage-36-visual-workspace工作区/分支，负责全部前端及浏览器测试。主任务只负责决策、研究、私有样例、集成与验收文档，读写边界隔离；后续由Luna固定审计复验。
- 本轮不新增模型付费调用，复用既有私有样例。下一步是集成两项实现，在可写合成项目自测导入/编辑、在私有副本验证真实章内标题与图形阅读，再推送Draft PR。

## 2026-10-13 · 阶段 35 工程候选交付，内容接入与作者验收待续

- 分支 `codex/stage-35-independent-experience`，最终代码提交 `e9e89a4a54c9b22828810df7b8e13355d0af6763` 已推送，交付 [Draft PR #12](https://github.com/Reen-Ai-H/novelagent-xumai/pull/12)，叠加阶段34 PR #11。回读该代码提交的 push/PR 两组 Ubuntu、Windows CI 四项全部 SUCCESS；未合并、未部署。
- 主任务对该代码运行 `scripts/verify_offline.py`：**355 tests / 0 failures / 0 errors / 0 skipped，21.839s**。Python compileall、app.js / deconstruction-report.js / report-browser.js / rule-report.js 的 Node 语法和 diff 检查通过。无凭据隔离副本运行，自动测试不调用模型。
- Sol 在相同代码 SHA 的全新8051隔离服务上执行六套原浏览器脚本：stage35_reading、density、history、model_roles、stage34、workspace_ui 均 exit 0。覆盖1440/1024/390、720高首屏、全量分页与末页搜索、正文精确空白、证据定位、冲突与历史只读，无未解释控制台错误和整页横溢。旧版元数据的history脚本是组件验证；真实旧规则升级/重复幂等另由主任务在样本副本实点验证。
- Luna 对后端最终实现独立复验：原132项专项和新增14项边界通过；历史裁剪、姓名/普通词/并列主体、来源投影合同、标点标题等六项原缺陷闭合，P0/P1/P2遗留为0。23份规则+1份模型持续保留24份报告、最早引用可读；9种来源投影篡改被拒绝。
- 主任务在最终界面核对本篇模型结果：10人物分为4主要/6配角，别名搜索、6完整事件和原文UTF-16选区可用；390×720无横溢，含私有提示条时首人物完整摘要底部716.20px。规则版10候选/12阅读段落不冒充相同语义质量；原56人物报告仍可读。
- 本篇MiMo试跑已停止：6次HTTP含修复，官方价格估算 **1.0175624元 / 2元上限**，无未知用量。末版10人物/6事件/130条逐字唯一引文经独立内容复核通过，仍有一处低影响分句缺少直接引用链接。只读预览仅在本机8050，原8000目录未切换；原作品、报告hash与原dirty文件均保持。
- **仍待交付**：来源编号绑定与模型定点修复仅为私有试验，尚未接入产品章节试拆/全书增量；不能宣称一键复现、通用准确率、全书成本或作者已验收。Notion界面/导入/编辑项转待验收，人物与剧情继续处理中，作者可直接调整下一步优先级。
- 本机证据保留于忽略目录 `test-results/stage35-e9e89a4-8051/VERIFICATION.md` 与 `.codex/stage35-live-case/`；原始正文、报告全文、费用现场、截图、凭据均不进入Git。下方“进行中”的缺陷记录保留为历史，不代表上述工程问题仍未修。

## 2026-10-13 · 阶段 35 集成复核（进行中）

- 集成候选 `71407d5`：离线 `scripts/verify_offline.py` 实跑 344 tests / 0 failures / 0 errors / 0 skipped（11.906s）；Python compileall、四份前端 JS 语法与 diff 检查通过。规则候选/重要性、来源阅读段落、显式规则升级、搜索分页和720高首屏优化已集成。
- 实际反馈作品的隔离副本：旧规则56卡→新规则10卡（5主/5配），779个细节事件/814条关系保留并归入12个来源阅读段落。仍有别名重复与角色主次偏差，不能据此宣称语义准确率。旧报告页DOM约28196→1248为同一旧报告的展示对照，不是删数据。
- 真实浏览器核对：人物深链、后页关键词搜索、证据抽屉→当前正文UTF-16精确选区、旧报告只读、显式更新与重复幂等均通过；同源两份报告持续保留。390/1024/1440宽度无整页横溢。所有操作仅作用私有副本，原作品与既有报告hash未变。
- 集成浏览器 stage32、stage34、stage35_workspace_ui、stage35_reading 原脚本通过；density 原脚本错误要求原生新版显示旧规则升级条，已如实记录失败并回派维护双场景，不能称五套全过。正文预览/编辑保留精确空白断言，没有trim。真实模型角色前缀与筛选分组接缝、单卷导航首屏占用已回派前端。
- Luna 最终代码审计发现历史模型导入仍裁报告（P1），以及宾语完整姓名、普通词/并列主语、段落来源合同和带标点标题（P2），正在由原后端Sol修复，未宣布工程验收通过。
- 本篇授权MiMo试跑共6次HTTP（含一次格式修复、两次来源编号方案及最后定点修复），累计按官方价格估算 **1.0175624元 / 2元上限**，无未知用量占用。末版10人物/6事件/130条逐字唯一引文；独立Luna内容复核通过，附一个低影响分句缺少直接引用链接的限制。未人工改写模型语义，原失败候选均保留。结果仅在私有只读预览供作者核对，未覆盖原作品、未获作者验收。
- **重要边界**：来源编号绑定和定点修复是本机验收实验，未接入产品 `analyze-preview` 或全书增量；不能把它宣称为点击一次即可复现的生产效果。普通规则仍只是线索索引。小样不外推其他作品准确率或70万字全书成本。
- 依赖阶段34 Draft PR #11 的最新 `e5cb94e` 已回读 Ubuntu/Windows 四项CI成功。阶段35将以其分支为基线建立堆叠Draft PR；主线未合并、无生产部署。

## 2026-10-13 · 阶段 35 开始

- 追加用户实际作品检查：授权项目保存的2.0规则报告，无模型；单章21,224字符，56人物/779事件/814关系，包含语法片段误判人物。8000端口未监听，已在8046只读隔离副本用真实浏览器核对原界面；不改原正文、账户或既有分析。私有内容不进入Git。
- 两个Sol初版已交回并集成，后端fd9f631新增30项回归（327全过），前端dbbd972完成三个视口初验；现按用户实测继续修正人物重要性和剧情组织，未冻结验收。
- 主任务初次集成离线实跑327 tests / 0 failures / 0 errors / 0 skipped（8.924s）；Node语法与diff检查通过。Luna边界审计复现章标题标点、目录吞序章、DOCX嵌套重复、普通宾语误报和截断姓名，已回派后端修复；前端空白保持合同与精确断言不一致已回派，均未宣布闭合。
- 用户批准本篇MiMo独立试跑，含重试累计不超过2元。私有输出、共享费用预留账本和原文件hash保护已准备，配置预检无网络调用；当前开始第一次试跑，质量待逐项复核。实施依据见[识别与阅读组织研究](docs/research/STAGE_35_RECOGNITION_AND_READING_2026-10-13.md)。

- 用户授权建立简化 Notion 表并统筹独立创作窗口与识别效果改进；主任务为 [阶段 35](docs/goals/STAGE_35_INDEPENDENT_EXPERIENCE.md)。继承 A 版，AI 写作暂缓。
- 分支 codex/stage-35-independent-experience，基线 e5cb94e。隔离工作区创建完成；原阶段 34 工作区与全部未提交改动保持原状。
- 开工实测：原项目虚拟环境执行本工作区 scripts/verify_offline.py，297 tests / 0 failures / 0 errors / 0 skipped，8.300 秒，无凭据源码副本并阻断网络。
- Notion 数据库已建立20个功能条目，五列主视图加模块分组；三视图与条目回读通过。本篇人物误报、剧情碎片和展示问题已同步为处理中；未把工程检查标为作者已验收。私人工作区地址只保存在本机忽略管理记录。
- 初步代码证据：章节数字解析只覆盖至九十九，卷与章混作标题；人物候选通过动作前短语产生，需反例验证。下一步由 Sol 分别实现后端和前端，Luna 负责资料与独立验证。

## 2026-10-13 · 阶段 34 断点恢复

- 已推送功能提交 `28d8bc11b1ceba0f4c24e62610a63e96e563ae54`，交付为 [Draft PR #11](https://github.com/Reen-Ai-H/novelagent-xumai/pull/11)，未合并、未部署。原代码审计首轮 P2/P3 全部闭合，同一审计员隔离复验98项通过。
- 该提交 CI 的 Ubuntu 两组通过，Windows 两组失败，原因是新增测试向 Node 中文 stdin 和测试源文件写入未显式 UTF-8（11个encoding errors），不是把失败或跳过计为通过。已定点修正输入输出编码，10/13 隔离全量295项通过；等待对应修复提交的双平台CI。
- 内容断点：第1–5章修正版34条引文，第6–10章现存版38条，均逐字唯一但仍有审计指出的证据支持/推断归属问题。第19次请求的第二卷修正草稿编号已正确，唯新增Q49引文未逐字匹配，整份修正拒绝生效；不截断或自动fuzzy接受。
- 正在以真实MiMo修复第一卷全部剩余清单，第二卷改为只让模型修复未通过的引文再严格合并。每次请求继续进入同一10元验收账；截至第19次，已知费用0.8813694元、6次未知用量占用1.367439元。10/13复核官方定价，所用pro输入3/输出6/缓存0.025元每百万token未变化，仍按保留价格版本估算。
- 使用product-design既定A版与独立审计/真实质量门禁。Mencius、Ohm与Kierkegaard复用原角色和不重叠写边界；11日额度中断不代表本阶段完成。下面历史数字保留，最终内容、真实界面与报告继续待收口。

## 2026-10-11 · 阶段 34 功能冻结、真实内容复核中

- 分支 `codex/stage-34-mimo-independent-completion`；main `ec2f31a` 与候选 `d408595` 的功能已集成，保留主线锁/CAS/确定性深度合同。`git fetch origin` 完成，远端 main 与候选未变。使用 product-design 的门禁流程，复用 A 版，不实施整体重构。
- 已实现：本地 MiMo 显式选择与安全配置、可信系统合同、完整 SSE 接收；2.0/model.1 双合同与文档级证据绑定；增量声明、精确撤回错误边、后台恢复与1220秒结构化总等待；跨来源在途预算保留；独立正文保存冲突/失效保护、正式历史冻结、预览和恢复幂等。无 AI 独立正文代写。
- 离线命令 `.venv/bin/python -W ignore scripts/verify_offline.py`：295 tests / 0 failures / 0 errors / 0 skipped；在无 `.env` 源码副本运行并阻断外连。compileall（含 scripts）、app.js/report.js/浏览器脚本语法与 `git diff --check` 通过。
- Chrome 154.0.8037.99：stage32 和 stage34 均在1440×900、1024×900通过。六视角、独立保存/切章/版本预览/恢复、跨卷重复Q1、9条引用可达、历史只读覆盖；无非预期console error/warn和整页横向溢出。401/409故障探测单列验证，不屏蔽其他诊断。
- 同一只读审计员首轮发现预算跨来源丢失、证据越界、来源错绑、history合同版本遗漏（P2×3、P3×1），均已回派修复并新增可复现回归；最新代码复核以收口记录为准。
- 实际样本从用户本机选取前10章叙事正文，共43,193字符；剔除明确作者公告，不改正文措辞。两份 MiMo 原始报告46条引文逐字且唯一，但独立复核仍发现主体混淆、引文不能支持判断、推断误标事实、对白/时序/连线方向错误。正在由真实MiMo delta修正，原始报告保留为失败证据，尚不宣布文学质量通过。
- 目前账本16次请求中已知费用约0.572元，6次未知用量保留1.367439元预算占用；后续修正也纳入10元初轮上限。金额为官方版本价格估算，不是供应商最终账单，不外推70万字全书。
- 原候选中的 `public_case/` 全书分析包从本次Git交付排除，磁盘原文件保留；新小说正文、报告全文、密钥和浏览器证据仅留忽略目录。无生产部署或现有作者数据改写。
- 功能候选待提交推送并保持Draft PR；最终真实内容、390px界面、同SHA CI与交付链接会在本节之后更新。10月8日及以下记录仅是历史，不代表当前阻塞。

## 2026-10-08 · 阶段 34 MiMo 与独立创作（进行中）

- 分支 `codex/stage-34-mimo-independent-completion`。已接入 main `ec2f31a` 和拆解候选 `d408595`，合并尚未提交；没有覆盖用户数据。现役任务书为 [阶段 34](docs/goals/STAGE_34_MIMO_INDEPENDENT.md)，下方旧“最新”仅为历史。
- 用户已授权凭据配置与付费内容验证，并指定《魔道祖师》前 10 章。凭据已安全配置在忽略文件；已提取 10 章、44700 字符，正文和账本在本地忽略目录，未提交。
- 已实现待集成验证：MiMo 显式供应商选择、流式接收；深度 2.0 与模型 model.1 双合同；指定文档证据定位；历史正式正文冻结、待确认修改阻止恢复、恢复幂等；增量分析和预算恢复正在专项验证。
- 上轮离线全量实际 250 项，1 failure、0 error、0 skipped，唯一失败是新 document_id 参数与旧前端静态断言不一致。前端中断时仍有一处合并标记，不能称为可用版本；本轮继续修复、浏览器和独立审计。
- 真实 MiMo 最小请求成功两次；长报告非流式 IncompleteRead、流式不完整，未产出已通过验证的报告。未知用量保留预算占用，没有零费用或质量通过的结论。
- 角色与写边界：Mencius `01a10bf4-8be9-7693-a1bb-f38dcd8bda55`（Sol，增量/预算）；Ohm `01a10bf4-8c6e-7860-b999-03a02a12d48c`（Luna，前端/浏览器）；Kierkegaard `01a10d26-3e8d-73a3-a98e-ac297627c178`（Sol，只读独立审计）。Parfit 的独立创作后端修复已交回。上轮额度/网络中断均不算验收通过。
- 下一步：完成流式诊断和真实内容；修复合并/全量门禁；实际界面验收、审计修复；有证据后再更新阶段结论并提交 Draft PR。

## 2026-09-23 · 完整平台路线与架构评估（报告，不是功能阶段完成）

- 用户要求：同步最新项目，阅读下一阶段目标和竞品研究，评估是否重构并提供完整平台演进报告。
- 已 fetch 并核实主线 `ec2f31a`；PR #4 已合并，下面历史“待合并”不再代表当前 GitHub 状态。最新拆解体验候选为 Draft PR #8 / `d408595`，包含 9 月 13 日轻量范围与竞品报告，未合入主线。双方共同祖先 `223b414`，main/候选独有提交为 24/10。
- 报告：[完整平台演进评估](docs/research/PLATFORM_EVOLUTION_ASSESSMENT_2026-09-23.md)。建议保留模块化单体，先统一基线和同源内容样例，再按实际缺口改善增量分析、知识范围、费用和编辑体验；远期路线为建议，不修改正式产品决策，不实施重构。
- 隔离复测：main 204 tests / 0 failures / 0 errors / 0 skipped；候选 161 tests / 1 failure / 0 errors / 0 skipped，失败是开发 `.env` 存在性依赖，未伪造配置转绿。两者 compileall、app.js 语法均通过；候选额外 report.js 语法通过；OpenAPI 为 58/61 与 63/66，旧 `/novel` 均 16/19。
- 微型诊断：旧记忆检索以第 3 章查询可返回第 100 章资料；候选账本 100 次未知 usage 后花费仍为 0 且允许后续预检。仅证明函数边界缺口，不宣称真实泄漏或超支；未修改代码，详见报告。
- 安全与限制：只使用隔离源码副本、fake 与合成数据；未读取真实小说、未输出密钥、未调用付费模型、未部署。没有重跑浏览器、文学质量或容量压测。
- 报告分支：`codex/stage-32-platform-assessment`；报告提交 `25ed56c` 已推送，交付为 [Draft PR #9](https://github.com/Reen-Ai-H/novelagent-xumai/pull/9)。三份文档本地链接检查缺失 0，diff 检查通过。未合并候选功能分支；远端 CI 状态以 PR 当前 head 为准。

## 阶段 32：深度作品拆解（审计通过，待合并，2026-09-05）

- 最新里程碑：集成候选 `a631606` 已通过同一独立审计任务最终复验，P0/P1/P2/P3 均为 0。全量 `204 tests / 0 failed / 0 skipped`，阶段 32 专项 69 项，阶段 31 回归 28 项，并发回归 44 项；OpenAPI 58/61、旧 `/novel` 16/19，compileall、Node 与 diff check 均通过。
- 真实界面：Microsoft Edge 152 在 1440×900 与 1024×900 完成登录、导入、后台拆解、总览和六视角、当前证据精确定位、历史证据只读、刷新/重登及修改后重建；两个视口均 0 console error/warn、无整页横向溢出。
- 审计回派：首轮发现否定动作误生成 enables/paid_off、空白必填字段和顺序型 stable ID；后续扩展反例覆盖拒绝/阻止、答案宾语、模态否定、词法例外及带把/将宾语的双重/三重否定。缺陷均回原后端任务修复并由同一审计任务复验，最终 9 种双重否定 36 例、三重否定 27 例通过。
- GitHub：分支 `codex/stage-32-deconstruction-depth`，Draft PR [#4](https://github.com/Reen-Ai-H/novelagent-xumai/pull/4)。`a631606` 的 push 与 pull_request 两组 Ubuntu/Windows CI 均通过；完成本轮文档提交并取得同 SHA 双平台绿灯后转 Ready 并合并。

### 实施记录

- 架构冻结：可见架构任务完成冻结提交 `ce49277`，管理按 checkpoint → freeze 顺序接入为 `52ca221`、`1272673`。完整阅读合同并复核一致性后，管理全量实际 `180 tests / 12 failures / 0 skipped`（11.676s）：168 项既有/合同检查通过，12 项引擎黑盒验收仍缺 report。六视角 schema 冻结当时不代表功能完成，随后按同一基线创建可见 Luna/max 后端和前端任务并行。
- 并行研发已启动：可见“阶段32 深度拆解后端引擎”使用 `codex/stage-32-backend-depth`；“阶段32 六视角前端体验”使用 `codex/stage-32-frontend-depth`。两者已核实 active，且均 fast-forward 到冻结管理基线 `de736c2`，模型/推理均为 Luna/max。后端不改前端，前端不改后端，管理验收/文档/CI不交给执行任务改写；待集成后再建独立审计。
- 冻结后验收对齐：旧版夹具使用独立的 legacy 文档身份，避免借用新引擎排队 ID；补首读 `rebuild_required`/可升级、旧证据历史只读以及响应不含内部 CAS/去重字段断言。升级单测实跑 1 failure / 0 skipped（0.065s），旧引擎仍误报 completed，确认下一步由后端修复；diff 检查通过。
- 管理浏览器门禁对齐冻结合同：真实端到端不再从阶段31顶层 `result.evidence` 误取证据，改为强制 `analysis_contract_version=2.0`、六视角容器完整、`result.report.evidence` 来源 hash 一致；修改后重建也必须仍为2.0，再用旧深度证据验证历史只读。前端证据抽屉的可访问交互待前端候选接入后继续补齐。
- 前端增量审查发现并回派两项：nullable 深度指标不能被 JavaScript 转成0（前端已改为严格保留null并显示未知）；roving tab 只有当前项可进Tab序列时，必须实现方向键/Home/End，否则六视角对普通键盘用户不可达。管理浏览器门禁已改为从总览仅用 ArrowRight 依次切换六视角并核对焦点，不再通过测试代码逐个强制 focus 掩盖缺陷。

- 管理分支：`codex/stage-32-deconstruction-depth`，从最新 `origin/main=223b414` 建立隔离工作区；原 main 工作区的测试改动、启动脚本和本地数据全部保留。
- 已执行：`git fetch origin main`、`git merge --ff-only origin/main`、`git rev-list --left-right --count HEAD...origin/main`，主线一致（0/0）；完整读取规则、路线、任务书、进度与阻塞。
- 顺序：架构冻结公开合同；后端与前端使用独立工作区并行；管理集成后交独立审计，缺陷回派原实现任务复验。
- 当前未完成：仅剩现役文档提交、该提交对应的 GitHub 双平台 CI 和 PR 合并；六视角实现、专项/全量/浏览器门禁与独立审计均已完成。
- 基线发现：阶段 15 dotenv 测试依赖开发目录已有 `.env` 与有效 key，需改为隔离配置夹具，真实验证跨 cwd 加载，不通过注入环境 key 制造通过。
- 基线复验：干净工作区全量 `135 tests / 1 failure / 0 skipped`，唯一失败为不存在开发 `.env`。改为临时项目布局执行原配置模块、移除继承的模型变量、给无关 cwd 放置反例配置后，全量 `135 tests / 0 failed / 0 skipped`（9.483s）。compileall、node 语法与 diff 检查通过；没有读取或修改用户 `.env`。
- GitHub：初始管理提交 `562513b`、基线修复 `a90682d` 已推送至阶段分支；Draft PR [#4](https://github.com/Reen-Ai-H/novelagent-xumai/pull/4)。`a90682d` 的 [CI run](https://github.com/Reen-Ai-H/novelagent-xumai/actions/runs/33897641025) Ubuntu/Windows 均 success，仅证明此时基线修复通过。
- 验收基础：新增隔离浏览器服务（真实 app/worker、临时测试账户和自有合成正文、禁止模型调用）；Edge 152 已实测视口 1440×900、根 scrollWidth=1440。新的六视角浏览器测试已红测：完成真实登录/创建/导入/后台拆解后，旧前端缺人物 tab，另有 favicon 404 控制台错误；留给前端实现修复，不屏蔽日志。
- 自动门禁入口 `tests/run_quality_gates.py` 已实跑 `135 tests / 0 failed / 0 skipped`（10.245s）、OpenAPI 58/61、旧 `/novel` 16/19，静态通过；CI 改为无需 `.env` 或环境 key，并强制零 skipped 和路由下限。
- 用户更新协作方式：停止隐藏子 Agent，改为侧栏可见的独立对话任务，统一使用 `gpt-5.6-luna` / `max`。原架构执行者已停止关闭，已落盘 schema/24项契约测试保存为 `c59b1a2`（未冻结），交可见架构任务接续；合同冻结后创建可见后端/前端任务，集成后创建可见独立审计任务。每个任务保持隔离 worktree，由管理任务统一集成和 GitHub 交付。
- 可见架构任务“阶段32 架构合同冻结”已确认 active，在独立 `codex/stage-32-architecture-visible` 分支接上 `a53030e` checkpoint，继续审查和编写冻结合同。新建任务列表曾未及时显示，已通过实际任务读取确认运行，未重复创建。
- 管理侧新增 `tests/test_stage32_acceptance.py` 的 9 项黑盒验收，覆盖六类自然/合成正文、真实结构化结果、人物变化/因果/伏笔语义、假因果与假回收反例、来源证据、幂等重建与历史隔离。初始红测 9/9 失败均为现有 stage31 缺少深度 `report`；这是未实现证据，禁止 skip 或改断言转绿。
- 验收复核：导入会 strip 章节边缘空白，因此前导空白/emoji 改由真实 start→draft→complete 写入，逐字断言保存/正式正文后再检查证据；新增首尾/中间空白章用例。专项现为 10 tests / 10 expected failures / 0 skipped（0.552s），均停在尚无深度 report。`a1260a4` 双平台 CI 的 144 tests / 9 failures / 0 skipped 与当时同一缺口一致，不把红测误报为平台故障。
- 旧数据升级红测：新增阶段 31 已完成侧车夹具，经真实读取、显式 rebuild、worker 要获得新版 report，同时保留旧文档/证据和作者正文；旧实现仅按来源哈希去重，不能完成升级。专项实际 `11 tests / 11 failures / 0 skipped`（0.607s），均为尚无深度 report；`git diff --check` 通过。升级身份与公开状态规则已交回可见架构任务冻结，不删除旧结果。
- 合同中途复核：发现“每个视角必须有非 unknown 实体”会迫使无人物/无伏笔文本编造内容，已回派架构任务修正并新增纯景物负例；倒叙有标记不等于可确定全局 story_order，也已要求显式保留未知。管理全量实跑 `147 tests / 12 failures / 0 skipped`（11.525s），135 项既有测试通过、12 项新深度验收均停在未实现 report；compileall、前端/浏览器脚本 node 语法、diff 检查通过。升级用例提交 `b692292` 已推送，当前仍为 Draft 阶段。
- 管理独立预检架构工作区当前 schema/测试：`tests/run_quality_gates.py` 实际 `168 tests / 0 failed / 0 skipped`（11.145s）、OpenAPI 58/61、旧 `/novel` 16/19、静态检查通过；该工作区尚未提交冻结文档，且不含管理侧 12 项引擎黑盒验收，因此不代表深度功能完成。重新 fetch 后管理分支相对 `origin/main` 为 8/0；可见 Luna/max 协作决定同步至 `DECISIONS.md` 和 `AGENT_WORKFLOW.md`，避免换任务后退回隐藏 Agent。

## 2026-09-23 · GitHub 同步与 CloudBase 恢复

- 用户澄清本次目标是把本地版本推到 GitHub，不是更新线上公开案例；此前误触发的 CloudBase `xumai-public-case-003` 已停止作为当前线上内容。
- 已从发布前备份恢复 `xumai-public-case` 原静态内容，当前恢复版本为 `xumai-public-case-004`，状态 `SUCCESS`；线上五个静态文件与备份逐项 SHA-256 一致。
- 未创建新 CloudBase 站点，也未上传 FastAPI 主应用、账户、本地 `.novel_*` 数据或生产内容；后续 CloudBase 发布需单独确认。
- 部署脚本的空参数和地址输出修复仍保留在 GitHub 代码中，便于未来明确授权后使用。

## 阶段 32B · 目标收敛（2026-09-13，文档完成／实现待续）

- 根据用户“保持轻量、质量达标即可”的要求，当前顺序改为同源内容样例 → 最小集成与受控试跑 → 整书收口；六视角、独立地点/场景系统和蒸馏/双引擎不再成为近期必经任务。
- 已完成：Novelcrafter、天命源码及相关产品机制调研；DECISIONS、阶段任务书、ROADMAP、PRODUCT_SPEC、ACCEPTANCE 与索引同步目标，区分机制参考和必做需求。
- 下一项实际交付：复用既有结果，整理 1–2 位主要人物、2–3 个相连大事件和一条覆盖前后揭晓的线索，附必要节奏与地点信息，先让用户看内容。
- 本轮仅文档修改。未修改应用或小说数据，未运行真实模型、全量测试或浏览器功能验收；历史测试结果不作为本轮重新验证。10 元整书成本仍未验证。
- 文档核查：研究稿 32 项脚注完整、18 个固定版本源码路径存在、5 个关键文件哈希匹配；`git diff --check` 通过（既有测试文件存在 LF/CRLF 提示）。目标文档的引用、范围一致性与空白检查单独复核。
- 分支仍为 `codex/stage-32-codex-deconstruction-preview`；本轮目标文档、公开案例包和部署脚本已在 `6282520` 提交并推送，继续保留 [Draft PR #8](https://github.com/Reen-Ai-H/novelagent-xumai/pull/8)。功能阶段尚未完成，`xumai_deconstruct_run/` 实验现场继续留在本机。

## 阶段 32B · 全书收口准备（2026-09-11，进行中）

- 分支：`codex/stage-32-codex-deconstruction-preview`。本轮先冻结既有章节/卷级结果，不启动 70 万字真实付费重跑。
- 已实现：跨卷人物阶段聚合接口 `/api/independent/projects/{project_id}/deconstruction/guide`；稳定 `entity_key`/别名字段；旧证据无当前稿本绑定时的静态核对展示；全文任务预算账与请求前止损门；DeepSeek 运行时保留 cache-read token 统计；运行时拆解 prompt 与本地 `xumai-deconstruct` Skill 同步到 v0.5。
- 已同步：`docs/DECISIONS.md`、`docs/ROADMAP.md`、`docs/ACCEPTANCE.md` 和阶段 32 任务书固定“冻结 → 聚合 → 小样 → 成本试验 → 全书整合”顺序。
- 验证：全量 `161 tests / 0 failed / 0 skipped`；`compileall`、两份 `node --check`、`git diff --check` 和 Skill `quick_validate` 通过。未调用真实模型，未做浏览器交互验收。
- 尚未完成：全书层的明暗线/悬念揭示/节奏分析，真实同源小样，真实费用试验，以及全文 runner 从“累计报告重发”改为真正增量合同。当前预算门是安全止损基础，不代表 10 元目标已验证。

## 阶段 32A · 独立档案合并与 DeepSeek 试拆（最新）

- 移除拆解完成说明、发现总览和历史块；左侧作品拆解展开三视角，人物卡进入可返回/刷新的详情页。独立档案合并，正文右侧四项数量同源。
- Codex 样板增加具体人物观察，保持6人物/2大剧情/1文本矛盾/4疑问/39引用；源正文未改。
- Skill v0.4 和便携包已更新。DeepSeek 专用配置与当前生成配置分离；真实认证与两次非思考模式第一章页面试拆成功。高强度思考首个长请求被中止，后加240秒页面等待上限。
- 第二次模型试拆修正了人物卡的传闻限定和匿名群体卡问题，但文本矛盾分类与部分证据支持仍需调试。未采用 DeepSeek 预览，保留用户已认可样板，不宣称模型质量一致。
- 实际浏览器：1440桌面与390窄屏、三视角与导航折叠、人物详情/刷新/返回、正文统计跳转、原文精确选区、试拆输入/返回/关闭，控制台无错误警告。
- 最终隔离全量145 tests，0失败/错误/跳过，13.994秒；compileall、两份node --check、Skill quick_validate通过。自动测试阻断9次依赖外连，真实付费请求仅在授权的手工试拆中执行。
- 本轮实现提交 `612f76c`。继续分支 `codex/stage-32-codex-deconstruction-preview` 与 [Draft PR #8](https://github.com/Reen-Ai-H/novelagent-xumai/pull/8)，未合并或部署。原有test_stage15与两个PowerShell脚本的修改未纳入本次提交。


## 阶段 32A 体验反馈更新

- 人物卡收紧为性格/为人与关键经历，按需展开；剧情缩为序幕、莫家庄两大事件。Skill v0.3 同步偏好。
- 已实际浏览器验证：桌面与390px窄屏、人物展开、大事件选择、键盘时间切换、原文精确选区、9条依据完整显示；控制台无错误/警告。发现并修复证据ID复用时先读旧文档问题。
- 本轮隔离全量141 tests / 0失败错误跳过，13.818秒；compileall、两份node --check及git diff --check通过。测试阻断9次依赖外连，无真实模型调用。
- 继续推送现有Draft PR #8，未合并或部署；文学效果继续按用户反馈调整。


## 阶段 32A：Codex 拆解样板接入平台（2026-09-06，Draft / 待页面验收）

- 用户选择：Codex 先分析真实小说，现有前端展示并自检；暂停生成、蒸馏、双引擎扩张。
- 分支：`codex/stage-32-codex-deconstruction-preview`，基线 `223b414`。保留原有 `tests/test_stage15_model_runtime.py` 改动和两个未跟踪 PowerShell 脚本。
- 原百度云文件读取失败；用户提供桌面本地副本后读取成功，编码 UTF-16。已截取实际开篇第1–5章，排除文案、编辑评价与第一章后作者公告；原文不修改，样本留在项目外本地实验目录。
- 顺序：最小结果合同与来源校验 → Codex 原文分析 → 现有页面人物/剧情/双时间适配 → 隔离测试与真实浏览器自检 → 提交/推送/Draft PR。
- 实现：受账户与当前来源约束的分析包导入；数据驱动的人物卡、剧情地图、双时间视图；沿用原文证据入口，不改作者正文。
- 当前样板：4 条发现、6 张人物卡、12 个剧情节点、39 条原文引文；实际 API 导入、刷新与全部 39 条证据回链核对通过。样板存本地预览账户，小说及结果不提交。Skill v0.2 同步了平台流程及时间/文本矛盾处理。
- 验证：隔离全量 `review_runner.py` 139 tests，0 failed/errors/skipped，13.772 秒；`compileall`、两份前端 JS 的 `node --check`、`git diff --check` 通过。测试阻断 9 次依赖外部连接尝试；无真实模型付费调用。Skill 格式及引用脚本 1 正例 / 6 类反例通过。
- 尚未完成：浏览器控制工具中途不可用，无法进行点击、窄屏、键盘与控制台验收；保留 Draft，不宣称页面或文学质量已获用户认可。详见 [阶段 32A](docs/goals/STAGE_32A_CODEX_PREVIEW.md)。
- GitHub：实现提交 `d9dc76c` 已推送；[Draft PR #8](https://github.com/Reen-Ai-H/novelagent-xumai/pull/8)。浏览器验收前保持 Draft，不合并、不部署。

## 阶段 31J：Windows 零上下文接棒任务书（2026-09-05）

- 目标：补齐 GitHub 中缺失的下一阶段正式任务书与长期研发顺序，让 Windows 新管理任务不依赖 Mac 聊天记录即可继续。
- 基线：远端 `main=e55ee722bc755c0f2562895e18f36e39803c8af0`；阶段 31 为 135 tests、0 failed、0 skipped，OpenAPI 58/61、旧 `/novel` 16/19，Windows/Ubuntu CI 通过。
- 发现：现役文档只分散写有“阶段 32+”方向，没有一份同时包含具体范围、角色分工、依赖顺序、反作弊门禁和完成条件的阶段 32 任务书；长期阶段顺序也没有唯一入口。
- 处理：新增 `docs/ROADMAP.md` 和 `docs/goals/STAGE_32_DECONSTRUCTION_DEPTH.md`，同步规则、索引、决策、规格与验收；本阶段只改知识与交接面，不进入阶段 32 研发。
- 分支：`codex/stage-31j-windows-handoff-plan`。完成文档链接、全量基线和 GitHub PR/CI 后再记录最终 SHA 与合并结果。
- 本地门禁：现役 Markdown 本地链接检查通过；全量 135 tests、0 failed、0 skipped；compileall、`node --check frontend/app.js`、`git diff --check` 均通过。
- GitHub 交付：任务书提交 `820dc0e` 已推送；PR [#3](https://github.com/Reen-Ai-H/novelagent-xumai/pull/3) 已创建，Ubuntu/Windows 两组 CI 均通过。PR 合并状态以 GitHub 为准，Windows 接棒前必须从最新 `main` 拉取。

## 阶段 31I：Windows 迁移收口与 GitHub 发布（2026-09-04）

- 目标：不新增产品功能，把阶段31审计候选迁移到 `Reen-Ai-H/novelagent-xumai`，补 Windows 手册与双平台 CI，发布到新仓库 `main`。
- 基线：`7ff0273` 可达，135 tests、0 failed、0 skipped；OpenAPI `58/61`，旧 `/novel` `16/19`；`github-current/main=9c5aabd` 与旧 `origin/main` 文件树一致。
- 分支：从 `github-current/main` 建立 `codex/stage-31-independent-deconstruction-release`，已按 `e0f163a → d7166d1 → d614118 → be6fde2 → cdd7d01 → d480a85 → 7ff0273` 顺序重放；最终树与 `7ff0273` 一致。
- 计划：新增 `docs/WINDOWS_MIGRATION.md`、`.github/workflows/ci.yml`，同步 README/文档/收口矩阵和 GitHub 状态，再完成本地门禁、push、PR、CI、merge。
- 最大风险：跨平台命令/数据迁移说明误导作者，或把 `.env`、`.novel_*`、审计现场带入公开仓库；只使用无值模板和受控文件清单。
- 发布记录：`codex/stage-31-independent-deconstruction-release` 已推送，最终候选提交为 `2350feb`；PR [#1](https://github.com/Reen-Ai-H/novelagent-xumai/pull/1) 已合并，合并提交为 `8e42cb6486e6baa66afd7f463448cb39eb51dc3d`。
- 当前状态：`origin/main` 已回读并与候选树一致；Ubuntu/Windows CI 均通过。不创建 Release/Tag，不清理旧 worktree、分支和本地数据。

## 阶段 31G：审计 P2 定点收口（2026-09-04）

- 目标：只修时间线首尾归一化和证据接口 `chapter` 严格公开 schema，不改 `frontend/**`、后端其他合同或用户数据。
- 顺序：先用前导空白/空白段/emoji/多章与 OpenAPI schema 红测复现，再做最小服务层与 Pydantic 修复，最后全量回归并提交单一 commit。
- 基线：当前候选 HEAD `d480a85`，133 tests、0 failed、0 skipped；OpenAPI `58/61`，旧 `/novel` `16/19`。
- 最大风险：归一化若直接 `strip` 会改变 UTF-16 evidence/hash/offset；schema 收紧若改写历史 payload 会破坏只读兼容。
- 红测：前导空白样本首节点为 `4.82`；证据回链 `chapter` 经模型校验仍为 `dict`。
- 修复：仅对 timeline 展示坐标做有效正文跨度归一化；新增严格 `DeconstructionEvidenceChapter`，历史/当前回链均保留原有只读字段语义。
- 结果：阶段 31G 专项 2/2、阶段 31 相关回归 26/26、全量 135/135，均 0 failed / 0 skipped；compileall、`node --check`、`git diff --check` 通过；OpenAPI `58/61`、旧 `/novel` `16/19`。
- 本阶段不改 `frontend/**`、`.env` 或 `.novel_*`，不调用模型；候选提交完成后等待固定审计复验，不自行宣布通过。

## 阶段 31E：作品拆解前后端总集成与候选冻结（2026-09-04）

- 目标：在阶段 31B 后按 `8028865` → `341bad8` 顺序整合真实作品拆解前端，不新增阶段 32 功能。
- 实际落地：前端提交分别为 `d614118`、`be6fde2`；页面使用 `/independent/{project_id}?view=deconstruction` 和 canonical `effective_status/run_status/source_match` 合同。
- 基线：整合前 124 tests；整合后当前候选 133 tests，0 failed / 0 skipped；OpenAPI 当前 `58 paths / 61 operations`，旧 `/novel` `16 paths / 19 operations`。
- API 实测：隔离 TestClient 已验证 `empty`、`queued`、`running`、`completed`、`failed_retryable`、`stale`、`rebuild_required`，匿名 401、跨账户 404，结果含概览/时间线/章节拆解/证据。
- 浏览器实测：本地 8021 真实服务完成新建独立作品、空白正文、自动保存、完成章节、拆解、刷新深链；完成、空态、排队、失败、过期和待确认页面均已留证。
- 证据：阶段31E真实截图保留在本机临时证据目录、未纳入 Git；Chrome 实际 CSS 视口曾为 1710×887，当前重登验证为 1710×831，原生截图为 2x；未将其冒充 1440/1024 目标尺寸。
- 文档：已同步 `README.md`、`docs/README.md`、`docs/USER_GUIDE.md`、`docs/ARCHITECTURE.md`、`docs/DEVELOPMENT.md`、`docs/CLOSEOUT_MATRIX.md`。
- 安全边界：未读取/修改 `.env`，未迁移/删除/提交 `.novel_*`；前端无 localStorage/sessionStorage，不返回侧车账户字段或正文副本。
- 最终门禁：阶段 31 专项 26/26、全量 133/133，均 0 failed / 0 skipped；compileall、`node --check`、`git diff --check`、Markdown 本地链接检查均通过；OpenAPI `58/61`、旧 `/novel` `16/19`。
- 本地候选已收口为当前分支 HEAD（不推送、不建 PR）；不自行宣布独立审计通过，不进入阶段 32。

## 阶段 31B：作品拆解后端架构审查 P1 收敛（2026-09-04）

- 目标：不改 `frontend/**`，收敛锁顺序、拆解 outbox/reconcile、失败持久化、来源证据和四个公开 API 合同。
- 顺序：先复现基线与已有回归 → 修派发/worker/锁边界 → 修 evidence 与 canonical response → 同步权威文档 → 全量回归。
- 最大风险：正文保存、拆解侧车和后台恢复若顺序不清，会造成正文成功但拆解 500、任务卡死或结果错误绑定当前稿本。
- 基线复核：阶段 31A 6 项通过；当前阶段新增 11 项，合计 `124 tests / 0 failed / 0 skipped`。
- 已完成：来源读取移出拆解锁；正文侧车保存 durable outbox；失败派发可重试；worker/读取可恢复；异常进入 `failed_retryable`；证据和公开状态合同已收紧。
- 已同步：`docs/DECISIONS.md`、`docs/PRODUCT_SPEC.md`、`docs/UX_FLOWS.md`、`docs/ACCEPTANCE.md`、`docs/ARCHITECTURE.md`。
- 本阶段不改前端、不调用模型、不改 `.env` 或 `.novel_*`；compileall、OpenAPI/旧路由、node 检查和 diff 检查均已通过。
- 阶段提交：`ab4e056`（`Converge independent deconstruction architecture`）；不推送、不建 PR，等待管理任务与前端任务集成/复核。

## 阶段 31：独立创作中的作品拆解 MVP 后端（2026-09-04）

- 范围：仅负责拆解 schema、侧车 store/service、API、服务端 worker、后端测试和必要架构文档；前端由独立任务负责，本阶段不修改 `frontend/**`，不做总集成。
- 分支：`codex/stage-31-independent-deconstruction`；起点为阶段 30 现役基线；既有未提交用户反馈 `docs/DECISIONS.md` 保留。
- 目标：导入确认/完成本章自动排队，后台离页/重启恢复，概览、0–100% 时间线、章节拆解、evidence 回链、空态/失败/重建和账户隔离可由服务端验证。
- 顺序：决策与合同 → 独立侧车数据模型 → 确定性拆解服务 → 路由/worker 接线 → 红绿测试 → 全量回归与 TestClient 证据 → 后端提交。
- 最大风险：跨稿本正文来源变化可能让拆解覆盖作者内容；采用 source version/revision/hash 门禁，旧结果保留、当前返回 `stale`/`rebuild_required`，不回写既有正文数据。
- 开工基线：`107 tests / 0 failed / 0 skipped`；OpenAPI 与旧 `/novel` 数字待本阶段结束复核；初始 `git status` 为本分支 + 既有 `docs/DECISIONS.md` 修改，无未跟踪文件。
- 已完成：新增 `schemas/deconstruction.py`、`app/core/deconstruction_store.py`、`app/core/deconstruction_service.py`、`app/deconstruction_routes.py`；接入独立服务 hooks、FastAPI 生命周期 worker、`.gitignore`。
- 当前后端合同：`GET /api/independent/projects/{project_id}/deconstruction` 单次读取；另有 rebuild、retry 和 evidence 回链接口；状态 `empty/queued/running/completed/failed_retryable/stale/rebuild_required`；结果含来源版本/revision/hash、概览、timeline、chapter_breakdowns、evidence、history、initialized 和 actions。
- 当前验证（31A 基线记录）：阶段专项 6 tests 全绿；全量 `113 tests / 0 failed / 0 skipped`；compileall、`node --check frontend/app.js`、`git diff --check` 全部通过；OpenAPI `58 paths / 61 operations`（新增拆解 4 paths / 4 operations），旧 `/novel` `16 paths / 19 operations`；受控文件秘密/运行数据清单扫描无保护路径。
- 后端交付：commit `e585070`（`Implement independent work deconstruction MVP backend`）；工作树干净、分支相对 `origin/main` ahead 1。本阶段不做前端修改、总集成或 PR，交由管理任务与前端任务接续。


## 阶段 30：README 产品展示与使用说明（2026-08-13）

- 目标：重写根 README，加入当前实现截图、A 版效果参考、两条使用路径、快速启动、模型配置、验证命令与边界说明。
- 分支：`codex/stage-30-readme-showcase`。
- 变更：`README.md`、`docs/assets/current-home.jpg`、`docs/assets/current-login.jpg`；截图来自本地真实页面，效果图明确标注为 A 版参考。
- 参考结构：采用开源项目常见的首屏定位 → 视觉预览 → Quick Start → 使用方式 → 配置/验证 → 文档/限制层级，保持短段落和可扫描表格。
- 门禁：图片 7 张、文档本地链接 8 个均存在；截图/README 无密钥、机器路径或用户数据。
- 验证：107 tests 全绿、0 skipped；compileall、node --check、git diff --check、OpenAPI 54/57、旧 `/novel` 16/19 均通过。
- 交付：commit `3ee3c5a` 已 push；PR [#4](https://github.com/aswansong/novelagent/pull/4) 已合并，`main` 合并提交为 `09387a82b7f79c92c61bd651d81ba1ae54111a44`。

## 阶段 29：V1 主线晋升与仓库治理（2026-08-12）

- 目标：以阶段 28 的 V1 开发版替换落后的 GitHub `main`，清理经确认可删除的临时项，并建立逐阶段 GitHub 同步制度。
- 状态：已完成。
- 主线结果：`codex/v1-project-closeout` 已通过 [PR #1](https://github.com/aswansong/novelagent/pull/1) 合并；`main` 合并提交为 `0e48def6bd5404615a32e8d02af78cf75635cf70`，其文件树与 V1 提交 `cd3563517a222a4a94c444daebb15d823fd4de8f` 完全一致。远端和本地 V1 临时分支均已删除。
- 阶段制度：后续阶段使用 `codex/stage-<编号>-<主题>`，结束时必须 commit/push，并在本文件记录分支、SHA 和 PR；需复核时保持 Draft。
- 清理结果：5 份被忽略的 `.local.md` 历史副本和阶段 28 PR 临时说明已移到 macOS 废纸篓的 `叙脉-stage29-cleanup-20260812` 目录，可恢复；本项目遗留的 8000 端口开发服务已停止。
- 保留结果：另一个旧 worktree 含未提交源码和 `.novel_*` 本地数据，禁止直接删除；远端 `codex/test1` 含未合并独立历史；项目外质量研究仍供 Q3 使用。三者均保留。
- GitHub 同步：治理决定提交为 `cd3563517a222a4a94c444daebb15d823fd4de8f`；本阶段收尾分支为 `codex/stage-29-main-promotion`，首个收尾提交为 `4e0795ae95165d776c4b80273f02843bc9afe305`，[PR #2](https://github.com/aswansong/novelagent/pull/2)。

## 阶段 28：洁癖知识收口与 GitHub 开发版（2026-08-11）

- 目标：让首次接手者从仓库能理解产品、配置、启动、两条创作路径、当前限制和验证状态；把当前开发版源码、测试、权威文档和设计资产提交到开发分支并开 Draft PR。
- 发布范围：源码、schemas、tests、docs、AGENTS.md、PROGRESS.md、BLOCKED.md、README.md、requirements.txt、.gitignore、无值 .env.example、design-prototypes。
- 绝不纳入：.env、.novel_*、.codex、.venv、缓存、浏览器现场、审计证据、质量研究 quarantine、用户账户/正文/usage 数据。
- 当前事实：阶段 27 独立审计通过；107 tests 全绿、0 skipped；OpenAPI 54/57；旧 /novel 16/19。
- 质量事实：项目外离线质量门 Q2 已验证；真实生成质量增益、叙脉集成和 Q3 仍 pending。文学质量阶段 23B 为 C，不把功能审计写成质量通过。
- 处理顺序：盘点事实面 → 收口规则/README/用户说明/架构/开发文档 → 链接与安全扫描 → 全量验证和 localhost 烟雾 → 显式暂存 → commit/push → Draft PR。
- 最大风险：dirty worktree 含阶段 1–27 既有改动；必须逐路径归属并排除所有本机数据、密钥、审计和研究目录。

## 已完成

- 已执行 neat-freak 只读盘点，确认规则入口、dirty worktree、3 个 worktree 和受保护目录；未清理任何现场。
- 已将根规则、README、用户指南、架构、开发手册、文档索引、产品/流程/验收状态和收口矩阵同步到阶段 28 现役事实。
- 已保留阶段历史；含本机路径/账户/审计现场的原始副本仅留在被 `.gitignore` 排除的本地 `.local.md` 文件，公开 `docs/history/` 只含脱敏摘要。
- 已建立无值 `.env.example` 和覆盖 `.env`、`.novel_*`、`.codex`、`.venv`、缓存与日志的 `.gitignore`。

## 阶段 28 门禁

- 代码、文档和规则以当前实现和本文件链接的权威文档为准；旧阶段历史移至 docs/history/。
- 本地开发可用不等于生产部署；GitHub `main` 开发基线不等于 deployed、live verified。
- 清场候选只列不删，必须等用户阅读本阶段回报后再次明确确认。

## 已交付

- 发布前验证已完成：107 tests 全绿且 0 skipped；compileall、node --check、git diff --check 通过；OpenAPI 54/57，旧 `/novel` 16/19；本地 8017 首页/登录/书架烟雾通过，匿名 API 按合同返回 200/401。
- Markdown 链接 29 文件、20 本地链接缺失 0；staged manifest 103 文件，保护路径 0，真实密钥形状/Authorization/机器绝对路径 0，最大文件 2.26 MB，总暂存约 35.2 MB。
- 已创建分支 `codex/v1-project-closeout`，提交 `Prepare v1 development release`，并推送到 origin。
- 已创建面向 `main` 的 PR #1；阶段 29 将它作为 V1 主线晋升入口。

## 后续边界

- 等待固定独立审计复验；不在本阶段自行宣布审计或文学质量通过。
- 离线质量门 Q2 已验证，但真实生成质量增益、产品集成和 Q3 仍 pending；清场候选等用户确认，不在本阶段删除。
