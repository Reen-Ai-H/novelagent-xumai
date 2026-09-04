# 阶段 32 深度作品拆解合同

本文冻结阶段 32 的数据、状态、证据、并发和前后端接缝。它服务于独立创作工作区中的作品拆解，不新增顶层创作路径，不允许拆解结果改写作者正文或故事档案。

本文与 `schemas/deconstruction.py` 同步维护。代码中的 Pydantic 模型是可执行约束，本文说明字段语义、发布边界和实现顺序。阶段 31 的旧投影继续可读，但旧基础拆解不等于阶段 32 深度报告。

## 1. 版本和对象边界

### 1.1 两个版本

| 名称 | 值 | 作用 |
| --- | --- | --- |
| API `schema_version` | `"1.0"` | 保持阶段 31 浏览器响应的顶层形状和七种 canonical 状态。 |
| 分析 `analysis_contract_version` | `"1.0"` / `"2.0"` | 标识一次运行使用的分析合同。`1.0` 是阶段 31 兼容结果，`2.0` 才能承载本合同的六视角报告。 |
| 深度 `report_version` | `"2.0"` | `DeconstructionDepthReport` 的严格版本。只允许 `"2.0"`。 |

`analysis_contract_version="2.0"` 的 `completed` 文档必须有 `report_version="2.0"` 的报告。`analysis_contract_version="1.0"` 的旧文档可以 `completed` 且 `report=None`，这只是兼容的基础结果，不能在深度页面冒充完成。

一个来源快照允许同时保留一个 1.0 文档和一个 2.0 文档。升级必须创建新的 2.0 文档并把旧文档留在 history，不能把旧文档就地改写成深度报告。

### 1.2 来源快照

深度报告绑定以下不可变 token：

```text
(project_id, source_version_id, source_revision, source_hash)
```

其中 `source_hash` 是正式正文快照的 SHA-256 小写十六进制值。`source_revision` 是作者正文服务的 revision，不是 worker 重试次数；两者不能混用。报告、每条深度证据和发布时的 active run 必须绑定同一 token。

`document_id` 是本次报告的运行/历史身份。它用于回链和历史区分，但稳定分析项 ID 不依赖它，因此同一来源快照的安全重试不会产生另一组人物、事件或伏笔 ID。

内部 `record_revision` 是拆解侧车记录的 CAS 版本，只用于持久写入，不进入浏览器响应。

## 2. 严格类型和公共深度报告

所有 `Depth*` 模型都使用 `extra="forbid"`、严格类型和实例重新校验。未知字段、字符串数字、布尔数字、`NaN`、无穷值、空白必填文本都必须拒绝。

### 2.1 基础类型

| 类型 | 约束 |
| --- | --- |
| `DepthID` | 非空、最多 160 字符，只允许 ASCII 字母、数字、`_`、`-`。 |
| `DepthCategory` | 非空、最多 80 字符，不能全为空白。 |
| `DepthText` | 非空、最多 1200 字符，不能全为空白。用于结论、观察、解释和学习说明。 |
| `DepthHash` | 小写 `[0-9a-f]{64}`。 |
| `DepthScore` | 有限浮点数，范围 `0..1`。节奏、好奇、悬念等指标只使用这个范围。 |
| `DepthProgress` | 有限浮点数，范围 `0..100`，表示阅读顺序中的相对位置。 |

### 2.2 来源和章节

`DepthSource` 的完整字段如下：

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `project_id` | `DepthID` | 独立作品。 |
| `document_id` | `DepthID` | 本次深度运行的文档身份。 |
| `source_version_id` | `DepthID` | 正式稿本版本。 |
| `source_revision` | `int >= 0` | 正文来源 revision。 |
| `source_hash` | `DepthHash` | 正文快照 hash。 |

`DepthChapter` 的完整字段如下：

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `chapter_id` | `DepthID` | 稳定章节身份。 |
| `chapter_number` | `int >= 1` | 阅读顺序中的章节号；报告内唯一且升序。 |
| `title` | `str <= 200` | 章节标题，可为空，因为作者可能没有标题。 |
| `utf16_length` | `int >= 0` | 该章节正式正文的 UTF-16 code unit 数。 |
| `normalized_start` / `normalized_end` | `DepthProgress` | 章节在全书阅读轴上的区间。首章从 `0` 开始，末章到 `100`，相邻章节连续。空章只能占零长度区间。 |

报告内 `chapters` 至少一项，最多 5000 项。章节表是阅读顺序，不是故事发生顺序；倒叙事件另由 `story_order` 表示。

### 2.3 证据

`DepthEvidence` 的完整字段如下：

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `project_id` / `document_id` / `source_version_id` | `DepthID` | 必须与报告 `source` 完全相同。 |
| `source_revision` | `int >= 0` | 必须与报告相同。 |
| `source_hash` | `DepthHash` | 必须与报告相同。 |
| `evidence_id` | `DepthID` | 报告内唯一的证据 ID。 |
| `chapter_id` | `DepthID` | 证据所在章节。 |
| `chapter_number` | `int >= 1` | 必须与该章节的章节号相同。 |
| `granularity` | `"span"` / `"chapter"` | 精确片段或只有章节级定位。 |
| `start_offset` / `end_offset` | `int >= 0` 或 `null` | `span` 必须有序且落在章节 UTF-16 长度内；`chapter` 必须都是 `null`。 |
| `offset_unit` | `"utf16_code_unit"` | 唯一允许的定位单位，和浏览器文本选区一致。 |
| `excerpt` | `str <= 180` | `span` 必须是正文的精确、未裁剪片段；`chapter` 必须为空。 |
| `label` | `str 1..120` | 面向作者的证据用途说明，不放 prompt 或内部链路名。 |

报告至少有一条证据。章节级证据是诚实的粗粒度定位，不得伪造 `0..0`、整章复制或空字段来假装精确证据。

### 2.4 所有分析项的公共字段

以下字段由人物、人物状态、剧情线、事件、伏笔、伏笔状态、节奏、读者体验、文笔技法和关系项共同继承：

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `item_id` | `DepthID` | 报告内跨视角唯一稳定 ID。 |
| `kind` | 受限字面量 | `character`、`character_state`、`plotline`、`event`、`foreshadowing`、`foreshadowing_state`、`rhythm`、`reader_experience`、`technique` 或 `relation`。 |
| `category` | `DepthCategory` | 面向作者的结论类别。 |
| `conclusion` | `DepthText` | 一句话结论，不能只填标签。 |
| `epistemic_status` | `observed` / `inferred` / `unknown` | 区分正文直接观察、基于证据的推断和当前未知。 |
| `chapter_ids` | `DepthID[]`，至少一项 | 结论来源章节，按阅读顺序，不得重复。 |
| `normalized_start` / `normalized_end` | `DepthProgress` | 结论在阅读轴上的区间，必须落在 `chapter_ids` 覆盖范围内。 |
| `evidence_ids` | `DepthID[]` | 引用报告 `evidence` 中的证据；`observed` 和 `inferred` 至少一条，`unknown` 可以为空。 |
| `related_item_ids` | `DepthID[]` | 跨视角相关项引用；必须存在、不得自指、不得重复。 |
| `confidence` | `DepthScore` | 置信度，不是质量分数。`unknown` 必须为 `0`。 |
| `uncertainty` | `DepthText[]` | 不确定性和适用边界。`inferred` 至少一条；`unknown` 至少一条。 |

`unknown` 不是把结论留空：它仍需非空 `conclusion`、章节范围和明确说明缺少什么证据。人物和伏笔集合可以为空，但相应视角必须有非空的视角级 `uncertainty`，例如“当前正文未提供可可靠识别的伏笔证据”。不能为了满足数量制造不存在的实体。

### 2.5 六个视角的字段

#### 人物与人物弧

`DepthCharacter` 在公共字段外增加：

| 字段 | 类型 |
| --- | --- |
| `name` | `str 1..80` |
| `aliases` | `DepthText[]`，最多 40 项 |
| `role` | `DepthText` |
| `motivation` | `DepthText` |
| `inner_conflict` | `DepthText` |
| `arc_summary` | `DepthText` |

`DepthCharacterState` 增加 `character_id`、`goal`、`belief`、`emotion`、`agency`、`change`、`trigger_event_ids`。`character_id` 必须引用人物项，`trigger_event_ids` 必须引用事件项。人物有候选时至少要有一个状态快照，状态按阅读进度排列；人物候选不存在时，人物和状态列表可以为空但必须说明原因。

人物关系 `DepthRelation` 使用 `allies`、`opposes`、`depends_on` 或 `changes_to`。前三者的端点是人物，`changes_to` 的端点是同一人物的两个状态，且后一个状态不能回到更早的阅读位置。

#### 剧情线、事件因果和叙述顺序

`DepthPlotline` 增加 `title`、`central_question`、`stakes`、`resolution`、`character_ids`。每条剧情线至少被一个事件引用。

`DepthEvent` 增加：

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `plotline_ids` | `DepthID[]`，至少一项 | 所属剧情线。 |
| `character_ids` | `DepthID[]` | 参与人物，可以为空。 |
| `story_order` | `int >= 0` 或 `null` | 故事世界中的相对顺序。倒叙可以早于当前叙述位置；跨线关系未知时可以为 `null`。 |
| `narrative_order` | `int >= 0` | 正文呈现顺序，报告内唯一升序。 |
| `temporal_mode` | `linear` / `flashback` / `flashforward` / `parallel` / `unknown` | 叙述与故事时间的关系。 |
| `action` | `DepthText` | 事件动作。 |
| `consequence` | `DepthText` | 可观察后果；未知时也要写明未知，不留空。 |
| `plotline_status` | `introduced` / `developing` / `turning` / `resolved` / `open` / `unknown` | 该事件对剧情线状态的作用。 |

`story_order` 和 `narrative_order` 永远分开。某个事件有倒叙标记但不能确定它和所有其他事件的全局关系时，允许 `story_order=null`，但 `uncertainty` 必须说明相对时间未知。`precedes` 关系只验证 `narrative_order` 方向，绝不自动等价于 `causes`；因果关系必须另有正文证据和解释。

剧情关系端点为事件或剧情线，关系类型是 `causes`、`enables`、`prevents`、`precedes`、`parallel_to` 或 `intersects`。

#### 伏笔、铺垫与回收

`DepthForeshadowing` 增加 `label`、`planted_detail`、`expected_payoff`、`interpretation`。

`DepthForeshadowingState` 增加 `foreshadowing_id`、`status`、`payoff`、`event_ids`。状态为 `planted`、`reinforced`、`paid_off`、`subverted`、`unresolved` 或 `unknown`；已知状态至少引用一个事件，`unknown` 必须同时使用 `epistemic_status=unknown` 并说明不确定性。状态快照按阅读进度排列，允许同一伏笔在多个章节经历铺垫、强化、回收或改写。

伏笔关系端点是事件到伏笔，类型为 `plants`、`reinforces`、`pays_off` 或 `subverts`。没有证据的“伏笔”不得以高置信度写入；没有可可靠识别的伏笔时返回空集合和明确视角级未知说明。

#### 章节结构与共享节奏曲线

`DepthRhythm` 增加 `narrative_function`、`scene_summary`、`pace`、`tension`、`information_density`、`transition`。三个指标可以为 `null`，表示该指标没有足够证据，但对象本身的结论和不确定性不能为空。

#### 读者体验曲线

`DepthReaderExperience` 增加 `expectation`、`information_gap`、`emotional_effect`、`curiosity`、`suspense`、`emotional_valence`、`payoff`。`curiosity` 和 `suspense` 为 `0..1` 或 `null`，`emotional_valence` 为 `-1..1` 或 `null`。

节奏和读者体验都使用 `normalized_start` / `normalized_end` 作为同一条 `0..100` 阅读轴，首项从 `0` 开始、末项到 `100`，区间不倒退。两者不是同一指标：节奏描述叙事推进，读者体验描述期待、信息差和情绪影响。

#### 文笔与叙事技法

`DepthTechnique` 增加 `technique`、`observation`、`mechanism`、`effect`、`learning_note`、`applicability` 和 `example_evidence_ids`。

`example_evidence_ids` 至少一项，且必须是该项 `evidence_ids` 的子集。例证复用受限的 `DepthEvidence.excerpt`，不再存第二份自由文本正文。观察说明正文看到了什么，mechanism 说明如何起作用，effect 说明读者/结构效果，`learning_note` 给作者可执行的学习提示，`applicability` 明确适用边界，避免把局部技巧包装成通用模板。

### 2.6 关系项

`DepthEndpoint` 只有 `item_id` 和受限 `kind`，不接受正文内容。`DepthRelation` 除公共字段外有 `start`、`end`、`relation_type` 和 `explanation`。允许的端点如下：

| 关系 | 起点 → 终点 |
| --- | --- |
| `allies` / `opposes` / `depends_on` | `character → character` |
| `changes_to` | `character_state → character_state` |
| `causes` / `enables` / `prevents` / `precedes` / `parallel_to` | `event → event` |
| `intersects` | `plotline → plotline` |
| `plants` / `reinforces` / `pays_off` / `subverts` | `event → foreshadowing` |

所有端点必须存在、不能自指，关系项自身也必须有章节、进度、证据和不确定性。关系引用的存在性、类型和方向由 schema 校验；因果、人物身份和技法语义不能只靠结构校验证明。

### 2.7 视角容器和报告

六个容器字段固定如下：

| 容器 | 字段 |
| --- | --- |
| `DepthCharactersView` | `summary`、`uncertainty`、`characters`、`states`、`relations` |
| `DepthPlotView` | `summary`、`uncertainty`、`plotlines`、`events`、`relations` |
| `DepthForeshadowingView` | `summary`、`uncertainty`、`threads`、`states`、`relations` |
| `DepthRhythmView` | `summary`、`uncertainty`、`items` |
| `DepthReaderView` | `summary`、`uncertainty`、`items` |
| `DepthTechniqueView` | `summary`、`uncertainty`、`items` |

`DeconstructionDepthReport` 的完整字段是 `report_version`、`source`、`chapters`、`evidence`、`characters`、`plot`、`foreshadowing`、`rhythm`、`reader_experience`、`technique`。六个容器都必须存在。节奏、读者体验和技法不能用空列表或全 `unknown` 项完成；人物、剧情线和伏笔可以在确实没有可靠候选时为空，但要写清楚视角级不确定性。报告的整体实质性和语义质量还要通过后端自然正文验收，不能用一批格式正确的占位对象宣称完成。

## 3. 稳定 ID和报告校验

### 3.1 稳定分析项 ID

`depth_stable_id(source, kind, anchor)` 的规范算法是：

```python
identity = [
    "2.0", source.project_id, source.source_version_id,
    source.source_revision, source.source_hash, kind, anchor,
]
digest = sha256(json.dumps(
    identity, ensure_ascii=False, separators=(",", ":")
).encode("utf-8")).hexdigest()
item_id = "d32_" + digest[:40]
```

`anchor` 是规范化的语义身份，例如 canonical character key，不得直接使用正文长句、列表下标或 worker run ID。相同来源快照、相同 kind 和 anchor 的重试必须得到相同 ID；source version、revision 或 hash 变化会得到新的来源作用域 ID，旧 ID 仍只属于历史稿本。

### 3.2 纯结构报告校验

`DeconstructionDepthReport.model_validate(...)` 负责：

- 版本、类型、额外字段、数值和文本边界。
- 章节唯一性、阅读顺序、`0..100` 首尾和相邻连续性。
- 证据唯一性、来源 token、章节号和 UTF-16 长度边界。
- 分析项 ID 唯一性、章节和证据存在性、父子项引用、关系端点类型和方向。
- 事件的叙述顺序、状态快照进度、共享节奏/读者曲线覆盖范围。
- `unknown`、`inferred`、技法例证和空视角的最低诚实条件。

这一步不能证明“阿岚就是主角”“事件 A 确实导致事件 B”“这是一处伏笔”或“这个技巧适合所有小说”。后端必须在发布前使用授权/合成的自然中文样本做语义正例和负例，特别要覆盖无 `人物：`、`伏笔：` 等标签的正文；语义负例应包含结构上有章节和片段、但分析结论与正文含义不相符的候选，确保引擎不会把字符串命中当作理解。

### 3.3 正文证据边界

`validate_depth_report_source(report, source=..., chapters=...)` 只接受已经授权的、不可变的当前正文快照。`chapters` 仅在调用期间存在于内存，函数不保存正文、不计算或替换来源 hash。

它会重新验证报告，检查：

1. 报告 source token 与传入 token 完全相同，章节 ID 集合完全相同。
2. 每章实际 UTF-16 code unit 长度等于 `DepthChapter.utf16_length`。
3. span 的 start/end 在实际章节范围内，且不切断 surrogate pair。
4. 解码后的原文片段与 `excerpt` 逐字符相等，包括空格和标点；不能先 `strip()` 再验。
5. chapter 级证据没有偏移和正文副本。

调用方必须在生成 snapshot token 时使用正式正文服务的 canonical hash，并在发布 CAS 阶段再次比较 version、revision、hash。这个纯函数看不到章节标题、server revision 等 hash 输入，不能单独重新计算服务层的 source hash。异常只返回安全的校验错误，不把正文、prompt、raw completion 或内部堆栈带进公开 error。

## 4. 七种 canonical 状态、恢复和历史

`effective_status` 是“当前正式正文相对于当前拆解结果”的公开投影；它不是任意 worker 标签。`run_status` 只描述 active document 的运行状态，可为 `none`、`queued`、`running`、`completed` 或 `failed_retryable`。

| `effective_status` | 进入条件 | 公开 result | action / UI 语义 |
| --- | --- | --- | --- |
| `empty` | 当前没有足够的已完成正式章节。 | `null`。 | 展示空态和需要正文的原因；不能自动伪造报告。 |
| `queued` | 当前 source 已通过前置检查，2.0 运行已持久化但尚未开始。 | `null`。 | 展示排队和可恢复进度；刷新不改变任务身份。 |
| `running` | 2.0 运行正在提取、归并或验证。 | `null`。 | 展示服务端 progress/current stage；不能从前端猜阶段。 |
| `completed` | active 2.0 run 完成，source token 当前匹配，报告通过结构和正文证据门禁。 | 当前 `DeconstructionResult`，其中 2.0 必有完整 report。 | 展示六视角、关系、共享时间轴和证据入口。 |
| `failed_retryable` | 分析或服务错误被安全归类，未发布部分报告。 | `null`。 | 展示脱敏错误和 `actions.retry=true`；retry 不新建同 source 的重复文档。 |
| `stale` | 已有结果的 source version/revision/hash 与当前正文不一致。 | `null`。 | 旧结果只留 history；source 足够且无 pending changes 时 `actions.rebuild=true`。 |
| `rebuild_required` | 作者修改尚未确认，或仅有阶段 31 1.0 结果而没有 2.0 深度结果。 | `null`。 | pending changes 时禁止 rebuild；来源就绪或需要升级时显示 rebuild/升级入口。 |

`source_match` 只表示 active 文档的 source version/revision/hash 是否与当前来源 token 相等，不等于允许发布。作者修改可能使 `effective_status=rebuild_required` 但 source token 仍相等，原因是修改仍在 pending confirmation；此时仍然隐藏 result。

允许的持久状态迁移由 `DECONSTRUCTION_STATUS_TRANSITIONS` 和 `is_valid_deconstruction_transition` 冻结：

```text
empty            -> empty | queued
queued           -> queued | running | completed | failed_retryable | stale | rebuild_required
running          -> queued | running | completed | failed_retryable | stale | rebuild_required
completed        -> completed | stale | rebuild_required
failed_retryable -> failed_retryable | queued | stale | rebuild_required
stale            -> stale | queued | rebuild_required
rebuild_required -> rebuild_required | queued | stale
```

自迁移是幂等的。`running -> queued` 用于崩溃/重启后重新排队；也可以由 worker 在恢复时继续同一个文档。`completed -> stale/rebuild_required` 不删除历史结果，新的 source 或合同版本必须形成新的 active document。

### 4.1 阶段 31 → 2.0 升级

后端每次读 active project 都要区分“基础结果完成”和“深度结果完成”：

1. 如果已有 1.0 `completed` 文档但 `report=None`，第一次读取不得直接返回深度 `completed`。
2. 当前 source 足够且无 pending changes 时，公开深度投影返回 `rebuild_required`，`result=null`，`actions.rebuild=true`，并保留 1.0 项在 `history`。
3. 如果作者有 pending changes，仍返回 `rebuild_required`，但 `actions.rebuild=false`，提示先完成/确认修改。
4. rebuild 为 source token 和 `analysis_contract_version=2.0` 创建新的 document/idempotency identity。旧 document 不被覆盖，旧证据保持历史只读。
5. 2.0 报告完成后，history 同时能看见旧基础结果和新深度结果；深度证据回链按自己的 `source_version_id` 定位，不跳到当前同编号章节。

同一 source 的运行身份至少包含 `(project_id, source_version_id, source_revision, source_hash, analysis_contract_version)`。因此现有阶段 31 的“按 version/hash 命中 existing 就返回”的逻辑不能直接复用于深度升级。2.0 文档即使尚无 report，也必须标为 2.0 且只能是 `queued`/`running` 等未完成状态；2.0 `completed` 没有 report 必须拒绝。

### 4.2 重试、重启和重复请求

- enqueue、rebuild、retry 使用客户端可选的 `idempotency_key` 作为请求去重输入，但服务端不得把它回显到公共 JSON。
- 相同 source token 和合同版本的重复 enqueue 返回同一个持久 document；不追加重复 history。
- 分析在锁外运行。进程重启后扫描 `queued`/`running`，按 document identity 恢复；checkpoint 可以持久化在内部，但不能进入任何公开模型。
- 失败只清除未发布的临时报告并进入 `failed_retryable`；作者正文、故事档案和历史完成结果不变。
- retry 只把同一 source 的失败文档重新排队并增加内部 `retry_count`。source 已变化时转为新 source 的 rebuild，不覆盖旧文档。
- outbox 确认可能重复到达；派发、确认和 report 发布都必须以 source/contract identity 幂等。

## 5. 持久项目锁与 CAS 发布合同

### 5.1 当前风险

现有 `DeconstructionStore` 的实例 `RLock` 只覆盖同一个 Python 对象。两个服务实例、两个 worker 进程或一次重启后的 writer 各自持有不同的 `RLock`，可能同时读取旧 JSON、分别修改，再由最后一次 `replace` 覆盖前一次更新，形成 lost update。它不能作为跨进程一致性保证。

此外，当前 `run_document` 的“开始前 source 检查 → 锁外分析 → 末次 source 检查 → 加拆解锁并 publish”之间仍有窗口：末次检查结束后，作者可以先写入更高 revision，再由旧分析结果发布。只在末次检查后调用 `save` 不是 CAS。

### 5.2 一个共享的 per-project 持久锁

后端实现必须提供跨服务、跨进程的 `(authorized account, project)` 级 project transaction lock。建议使用 `.novel_deconstruction` 旁的受控 lock 文件和 Windows `msvcrt` / Unix `fcntl` 等 OS advisory lock；锁元数据可包含随机 owner token 和 lease 时间，但 stale metadata 不能阻止恢复，OS lock 在进程退出时必须释放。锁文件名使用安全 project key；若不同账户允许相同 project ID，应使用账户作用域的不可逆 key，不把账户信息放进公开路径或响应。

要求如下：

- `RLock` 可以保留作进程内重入优化，但不能取代持久 OS lock。
- 获取失败、超时或底层锁不可用时 fail closed，返回可重试的 503；不在无锁状态写 JSON。
- 只在读当前 record、读当前 source token、校验 CAS、写临时文件和提交 sidecar 的短窗口持锁；模型分析、正文大段读取和网络调用都在锁外。
- 作者保存正文及 durable deconstruction outbox 时，必须使用同一个 project transaction lock；作者正文和 outbox 仍在独立侧车的原子提交内。
- 不允许持有 `DeconstructionStore._lock` 或任何 deconstruction-specific lock 后调用 independent service/store。最安全的实现是由一个 coordinator 持有单一 shared project lock，并调用各 store 的 lock-aware 原子原语；不能形成 `deconstruction → independent` 的反向锁嵌套，也不能让两个服务各自再套另一把锁。

### 5.3 两阶段 source/CAS 发布

执行流程必须具有以下语义：

```text
phase A  锁外读取授权正式 source snapshot S0
         S0 = (version_id, source_revision, source_hash, chapters)

phase B  锁外构建六视角 candidate，candidate.source = S0

phase C  获取 shared project transaction lock
         在该事务锁内重新读取当前 source S1 和 deconstruction record R1
         比较 S1 == S0 的 version、revision、hash 三项
         比较 R1.record_revision == expected_record_revision
         两项都满足才允许把 candidate 写为 completed

phase D  用 save_if_revision(expected_record_revision, R1+candidate)
         原子 temp write + fsync + replace + directory fsync
         record_revision 单调增加
```

如果 C 阶段发现作者已经提交了更高 revision，worker 必须放弃旧 candidate，CAS 地把任务标为 `stale` 或 `rebuild_required`，不得写入旧 report；作者正文保持原样。如果发现 record revision 被另一个 worker 改过，必须重新加载并按 source/contract identity 幂等判断，有限重试或安全返回冲突，不能覆盖未知字段。

作者写入与发布的竞态因此只有两个安全结果：

1. 共享锁先由 publish 获得，旧报告原子发布；作者随后提交正文，产生新的 revision/outbox，下一次投影为 stale/rebuild_required。
2. 共享锁先由作者获得，publish 随后重新读取到新 source token，旧 candidate 不发布。

不能存在“末次 source check 成功但 author revision 在 publish 前被覆盖”的第三种结果。

### 5.4 record revision 和冲突

`DeconstructionProjectRecord.record_revision` 是内部单调整数。旧阶段 31 sidecar 缺字段时按 `0` 读取；任何成功的 sidecar mutation 都必须在 shared lock 内把它增加，并通过 `save_if_revision` 比较旧值。`record_revision`、lock owner、lease、worker checkpoint、raw completion 和账户 ID 都不进入 `DeconstructionResponse`、证据响应或 DOM。

用户动作可携带 `expected_source_version_id`、`expected_source_revision`、`expected_source_hash`。不匹配返回 HTTP `409` 的安全 `source_conflict` 和新的 source 摘要，不返回正文。worker 内部 source race 以 stale/rebuild_required 收敛，不把并发当成分析失败；持久锁不可用或侧车损坏才进入 503/`failed_retryable` 边界。

## 6. 后端接口接线

阶段 32 后端只改独立作品拆解链路；不改作者正式正文内容。现有路径保持：

| 方法和路径 | 请求 | 成功响应 |
| --- | --- | --- |
| `GET /api/independent/projects/{project_id}/deconstruction` | 无 body。先做账户授权和 outbox reconcile。 | `DeconstructionResponse`，由服务端返回七状态、source 摘要、progress、history 和当前可见结果。 |
| `POST /api/independent/projects/{project_id}/deconstruction/rebuild` | `DeconstructionActionRequest`。可带 `idempotency_key` 和三项 expected source token。 | `DeconstructionResponse`，通常是 `queued`；重复请求复用同一 2.0 document。 |
| `POST /api/independent/projects/{project_id}/deconstruction/retry` | 同上；当前路径重试 active document，不接受 document ID。 | `DeconstructionResponse`，仅允许 retryable 失败或明确可重建状态。 |
| `GET /api/independent/projects/{project_id}/deconstruction/evidence/{evidence_id}` | 无 body。 | `DeconstructionEvidenceResponse`，当前证据只读；历史证据最小定位。 |

统一要求：

- 未登录返回 401；已登录但跨账户 project 返回 404，不泄露存在性。
- 先账户授权，再读取拆解和正文侧车；任何公开模型都用去账户的 projection。
- worker 顺序为 source snapshot → 章节事实 → 跨章归并 → 六视角分析 → 结构/证据/语义校验 → shared-lock CAS publish。
- `DeconstructionDepthReport` 只有在 2.0、source token 全等、正文证据门禁通过后写入 completed 文档。
- `report=None` 的阶段 31 result 保持可读，不能被解释成深度报告；首次读取和显式 rebuild 必须按第 4.1 节完成升级。
- 历史摘要必须带 `analysis_contract_version`；source-match 和 publish gate 必须比较 version、revision、hash 三项，不能沿用阶段 31 只比较 version/hash 的快捷路径。
- 任何异常公开成有限的安全 code/message/retryable，不含异常文本、正文、prompt、raw completion、private memory、密钥或栈。
- API model validation 失败必须拒绝写入；不使用 skip、todo、吞异常、静态假报告或放宽断言。

## 7. 前端接线

前端只读服务端 canonical state，不从 `history`、旧 `status` 或本地缓存推断当前状态。

### 7.1 状态和导航

- 以 `effective_status` 决定空态、排队、运行、完成、失败、过期和待重建；`run_status` 只补充 active run 状态。
- 深度报告存在的充分条件是 `effective_status=completed`、`result.analysis_contract_version="2.0"` 且 `result.report` 非空。旧 1.0 `completed` 显示“基础拆解已有，深度拆解可生成”，不显示六视角完成态。
- 完成页提供六个入口：人物与人物弧、剧情线与事件因果、伏笔与回收、章节结构与节奏、读者体验、文笔与叙事技法。
- 人物、剧情、伏笔关系视图只使用稳定 ID 引用；节奏和读者体验使用同一条 `0..100` 轴；技法卡展示 observation、例证 evidence 和 learning note。
- 操作按钮由 `actions.retry` / `actions.rebuild` 决定。pending changes 时不得自行启用 rebuild。

### 7.2 证据抽屉和历史

- 点击结论只携带 evidence ID 请求证据接口；不把 `excerpt` 之外的正文复制到 DOM 或 localStorage。
- `historical=true` 或 `source_matches_current=false` 的证据显示稿本/章节/编号最小定位，始终 `read_only=true`，不能把链接改写成当前同编号章节。
- 当前证据也只允许只读定位；证据页面可携带 `version_id`、`chapter_id` 和 `evidence_id`，但不能允许拆解结果写正文。
- 刷新、重登和离开页面后重新 GET；不把 worker checkpoint、账户字段、完整 source text 或内部错误放入浏览器存储。

### 7.3 可达性和布局

六视角标签、关系节点、证据按钮和重试/重建操作必须键盘可达。时间轴在 1440×900 和 1024×900 不横向溢出；`prefers-reduced-motion` 下不依赖动画传达状态。浏览器问题（旧页面没有六视角 tab、favicon 404）属于前端任务，不能通过改变本合同字段掩盖。

## 8. 公开投影和隐私清单

### 8.1 `DeconstructionResponse` 顶层字段

顶层字段固定为：

`schema_version`、`project_id`、`title`、`mode`、`effective_status`、`run_status`、`source_match`、`progress`、`source`、`active_run`、`result`、`error`、`actions`、`history`、`status`、`progress_percent`、`current_stage`、`source_version_id`、`source_revision`、`source_hash`、`analysis_label`、`empty_reason`、`error_message`、`retryable`、`initialized`、`deconstruction`、`document`。

其中 `status`、`progress_percent`、`current_stage`、`source_version_id`、`source_revision`、`source_hash` 是阶段 31 兼容字段，必须与 canonical `effective_status`、`progress` 和 `source` 同步。`deconstruction` 是同一 canonical state 的兼容嵌套投影，不得与顶层矛盾。

### 8.2 嵌套投影

- `DeconstructionSource`：`version_id`、`revision`、`hash`、`match`、`chapter_count`、`total_word_count`。
- `DeconstructionProgress`：`percent`、`current_stage`。
- `DeconstructionActions`：`retry`、`rebuild`。
- `DeconstructionError`：`code`、`message`、`retryable`。
- `DeconstructionState`：`effective_status`、`run_status`、`source_match`、`progress`、`current_stage`、`source`、`active_run`、`result`、`actions`、`error`。
- `DeconstructionActiveRun`：`document_id`、`run_status`、`source_version_id`、`source_revision`、`source_hash`、`analysis_contract_version`、`retry_count`、`analysis_label`、`created_at`、`updated_at`、`completed_at`。
- `DeconstructionResult`：`document_id`、`status="completed"`、`source_version_id`、`source_revision`、`source_hash`、`analysis_contract_version`、`analysis_label`、`overview`、`report`、`timeline`、`chapter_breakdowns`、`evidence`、`uncertainty`。2.0 result 必须有 report。
- `DeconstructionDocumentPublic`：`document_id`、`project_id`、`source_version_id`、`source_revision`、`source_hash`、`analysis_contract_version`、`status`、`progress_percent`、`current_stage`、`retry_count`、`analysis_label`、`overview`、`report`、`timeline`、`chapter_breakdowns`、`evidence`、`uncertainty`、`error_message`、`created_at`、`updated_at`、`completed_at`；去掉 `account_id`，2.0 completed 文档必须有 report。
- `DeconstructionHistoryItem`：`document_id`、`status`、source version/revision/hash、`analysis_contract_version`、`retry_count`、`analysis_label`、创建/更新时间和完成时间；不含 report、正文或证据片段。
- `DeconstructionEvidenceResponse`：`project_id`、`title`、`evidence`、`chapter`、`source_matches_current`、`historical`。`chapter` 只含 `chapter_id`、`chapter_number`、`title`、`read_only=true`、`source_available`。

为了接续阶段 31，模型可以解析旧构造器传入的 `idempotency_key`，但 `DeconstructionActiveRun` 和 `DeconstructionDocumentPublic` 会在序列化及 response JSON schema 中剔除它。`DeconstructionActionRequest` 可以接收客户端提供的 `idempotency_key` 作为请求去重输入；它不得被响应回显。以下内容永远不得出现在公开 response JSON、response OpenAPI schema 或 DOM：

```text
account_id, record_revision, idempotency_key, lock owner/lease,
worker checkpoint, prompt, raw_completion, private_memory,
full chapter/body copy, model chain, internal stack trace, secret
```

`DepthEvidence.excerpt` 是经过长度和 source gate 限制的最小例证，不是正文副本。公开 source hash 可以用于版本一致性判断，但不提供恢复正文的接口。

## 9. 可执行样例和验收边界

仓库内 `tests/test_stage32_contract.py` 的 `report_payload()` 是本合同的合成完整样例，包含人物弧、事件的 `enables` 关系、伏笔 `planted → paid_off` 状态、共享节奏/读者曲线以及带 `example_evidence_ids` 的文笔技法。`ev1` 是“阿岚把钥匙交给周砚”，`ev2` 是“周砚用钥匙打开门”，每条都是支持相应推断的最小短句，而不是只引用人物名字。

从仓库根目录运行。解释器路径使用当前 checkout 的本地环境，不绑定某台电脑：

```powershell
# Windows PowerShell
& '.venv/Scripts/python.exe' -W ignore -m unittest tests.test_stage32_contract -v
```

```bash
# macOS / Linux
.venv/bin/python -W ignore -m unittest tests.test_stage32_contract -v
```

关键等价调用如下：

```python
from tests.test_stage32_contract import SOURCE, TEXTS, report_payload
from schemas.deconstruction import (
    DeconstructionDepthReport,
    DepthSource,
    validate_depth_report_source,
)

report = DeconstructionDepthReport.model_validate(report_payload())
validate_depth_report_source(
    report,
    source=DepthSource(**SOURCE),
    chapters=TEXTS,
)
assert report.report_version == "2.0"
assert report.foreshadowing.states[-1].status == "paid_off"
assert report.plot.relations[0].relation_type == "enables"
```

合同测试至少覆盖：

| 类别 | 要求 |
| --- | --- |
| 单章/普通多章/100 章 | 章节不因数量产生小书上限，首尾阅读轴有效。 |
| 前导空白、emoji、Unicode | UTF-16 长度和 surrogate 边界正确，证据不因 `strip` 或 code point/code unit 混淆而漂移。 |
| 多线/非线性 | `narrative_order` 可与 `story_order` 分开，倒叙和相对时间未知不被强行排序。 |
| 无人物/无伏笔正文 | 允许空候选，但需要视角级无发现说明；不生成虚假实体。 |
| 自然中文语义正负例 | 没有固定标签时仍应提取真实语义；结构合法但语义不相符的报告不得发布。此项由后端引擎验收，不由纯 schema 假装完成。 |
| source 安全和并发 | 作者 revision 变化、末次检查与 publish 间竞态、CAS lost update、历史证据只读、账户隔离均需黑盒验证。 |
| 旧侧车升级 | 1.0 completed/report=None 首次读取和显式 rebuild 进入 2.0，不覆盖旧 history，也不直接显示深度完成。 |

本架构任务只冻结 schema、合同测试和本文；引擎、持久 store、worker、路由和前端按第 5–7 节由后续独立任务接线。

## 10. 非目标

本阶段不建设公共语料库、类型创作引擎、AI 续写/改写、导出出版物、真实支付、管理员、多人协作、公开分享、云同步或生产部署。深度报告只分析作者拥有或获授权的正式正文，不能作为训练语料打包。
