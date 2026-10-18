# 阶段37接缝合同

## 10/18现役预览：逐章冻结与统一核对

生产编排已由`chapter_preview.py`替代下方整稿首步，详细字段/边界见[章级合同](STAGE_37_CHAPTER_PREVIEW_CONTRACT.md)，实现与独立/真实质量状态见PROGRESS。每章`ChapterFacts`只含章号、局部人物和原子事实，服务器仅转换ID命名空间；最终`ChapterOutcome`严格区分success报告和blocked有源问题。人物完整分组、主配展示子集、实际主张及未解项映射均校验，不修改冻结事实或确定未知人物端点。

N章正常N+1、最多2(N+1)个HTTP，逐章12,288输出，最终使用`preview_max_tokens`原有配置边界。每次至多一次格式修复；有效blocked不重试，任何来源/预算/结构失败均停止并保留旧报告。公共成功AnalysisImport与旧book/delta/import不变，旧私有两阶段直接校验保留兼容测试，不再作为生产预览编排。

## 10/18早期两阶段记录（历史，生产已由上节替代）

以[最新决定](DECISIONS.md)为准：`analyze_preview`先生成严格来源绑定的事实包，再生成现有PreviewGroundedReport及紧凑事实对应附件。两阶段使用同一完整无损原文；人物/动作ID稳定，第二阶段不得偷偷改写第一阶段事实。对应附件覆盖人物身份、事件参与者/动作、关系端点及明确时间约束，结论的实际引文须来自其所对应事实的有效来源；不以字符串相等冒称语义蕴含。未决线索可显式留待核对，不强造关系；不能无理由丢失主要事实和明确连接。

服务器只检验映射、来源、身份/端点、已知时序与协议，最终候选原样进入现有来源绑定/范围派生，不自动反转边、删除非法项、合并实体或补写正文。正常2请求，最多4个格式请求；CAS及预算逐HTTP检查，阶段间失败不进入下一步。公开响应/旧book、delta、import协议不变。两阶段实际schema、输出大小与失败测试须随实现冻结，独立审计通过后才进行真实请求。

人物作为事实的主体或对象均可提供身份/经历依据（如被收徒者）；不得为了代码约束强行反写、重复事实。无关第三人不能借该事实，知情/情感仍只属于明确持有者。结构验证与自然语言蕴含分开，不能用固定关键词伪装通用语义判断。

私有第一步`PreviewFacts`含characters、atoms、cues：人物ID/姓名/别名/来源；原子事实主体/对象、kind、status、phase、time_anchor和来源；线索绑定具体动作端点与依据。第二步`PreviewCheckedReport`含report、supports（字段→事实及阶段集合）、event_bindings、edge_bindings、cue_resolutions。实际report引文须覆盖映射事实且不串入其他来源；名称/ID/别名保持，已知依赖不能倒置。只作为文本明确表达的目的、目标尚未actual时，允许在报告保留具体理由，不强画已发生关系或实际时间依赖。共享提示、公开import、book/delta及运行时预算底层不改；自然语言蕴含仍需实稿独立核对。

2026-10-17冻结，实施与验收状态见[PROGRESS](../PROGRESS.md)。目标见[任务书](goals/STAGE_37_USABLE_WORKSPACE.md)，本文件不表示接口已经验收。

## 章节预览

统一前缀 `/api/independent/projects/{project_id}`，沿用登录、归属和写入锁。

| 方法/路径 | 请求 | 返回 |
| --- | --- | --- |
| POST `/chapter-previews/import` | filename, content_base64 | preview |
| POST `/chapter-previews/resegment` | expected_version_id, expected_source_hash | preview |
| GET `/chapter-previews/{preview_id}` | 无 | preview |
| PUT `/chapter-previews/{preview_id}` | expected_revision, boundaries[{start,title}] | preview |
| POST `/chapter-previews/{preview_id}/confirm` | expected_revision | workspace, version_id, previous_version_id, preview_id |
| GET `/versions/{version_id}/source` | 可选query chapter_id | snapshot |

新导入使用chapter-previews，旧imports接口兼容保留。workspace新增 `chapter_source`，含version_id、source_hash、chapter_revisions、can_resegment、blocked_reason；前端原样传来源令牌，不计算哈希。

preview含preview_id、kind(import/resegment)、status、revision、source_version_id、source_hash、source_length、source_text、source_chapters、chapters、warnings、created_at、expires_at、confirmed_version_id。chapters条目含chapter_number/title/start/end/char_count/word_count/confidence/reason；confidence为explicit/inferred/manual/fallback。

所有偏移采用UTF-16半开区间。首切点0，其余严格递增，不能切开代理对或CRLF；end由服务端推导，全部片段按顺序覆盖原文。纠正不接受content/end/source_text，作者不能通过此接口意外替换正文。预览24小时有效，revision随纠正递增。

确认重新校验当前版本、正式稿hash、所有章revision、草稿和待定事务，创建新现役版本及新章ID，保存旧来源，不自动付费。冲突保留当前编辑和其他未确认导入。

## 历史证据

`IndependentWorkspaceService.read_source_snapshot(project_id, account_id, version_id, chapter_id=None)` 返回project_id/source_version_id/source_revision/source_hash/read_only/historical/chapters。章含chapter_id/chapter_number/title/content/server_revision/utf16_length/content_hash，只返回已鉴权正式稿。

未知version/章ID报错，不按章号回退。即使请求单章，source_hash和source_revision仍代表完整所选版本；revision为非空正式章最大revision。hash对齐拆解_source规范化JSON：version_id加有序非空正式章的ID、章号、formal_title或title、formal_content，UTF-8且sort_keys/compact separators。旧报告先核验绑定来源，再读取旧章；不能伪造当前可编辑链接。

## 人物关系

`model.1`报告可选 `character_relations`，缺失时默认为空，不推导关系。条目为 `{from_id,to_id,label,text,status,evidence_ids}`。端点必须为报告人物ID且不自连；label是短关系标签，text为判断，status为fact/reported/inferred/unknown，证据沿用严格引用。语义方向是from到to，反向查看不能倒置称谓。事件参与独立放在经历视图。

试拆/增量的来源编号、模型内部修复和总预算实现由模型worker负责；主Agent只在完成免费验证、确认持久化总额限制后启用本轮授权试跑。任何旧结果或手工改写报告不能代替本轮产品结果。

## 格式定点修复（10/17补充）

拆解模型配置显式启用有界候选修复，默认运行时保持原行为。完整且不超过65,536字符的失败输出可作为标注的不可信user数据进入唯一一次格式修复，不能进入system；空、截断、超限候选不截取回传。修复输入连同全部schema必须计入原持久账本请求前预留，预算不足或来源变化仍拒绝发起。输出重新走全部严格校验，不在代码中删除多余字段或补写JSON。候选未通过时现有报告不变，原始文本不进入默认日志。

真实试验未证明thinking模式有效后，拆解factory恢复默认disabled、预览12,288 token。显式官方enabled运行时仍以24,576为上限，推理与答案全部计费但只返回答案，不把该实验当作默认质量承诺。每次初始/修复HTTP须同时遵守共享预算和书级任务自身预算，完整输入、schema及输出上限在发送前持久预留。明确未发送的拒绝不虚增模型调用；取消或未知用量仍保守占用。本轮同一2元授权与账本不因这些改动重置。

预览模型输入只发送一份完整原文，以章节内有序text片段承载；可引用片段附原source_id，不可引用片段照常保留。按序拼接须逐字符等于原章，包括空白、换行、重复短句和标点；原bank全部编号与quote逐一对应。不匹配、重叠或不属于本次章的来源须请求前拒绝，不能自行修正文或静默丢编号。该优化不改变book增量消息协议，不新增摘要式输入或外部公开API格式。

## 预览事件范围的确定性装配（10/17补充）

仅预览使用专用事件wire，事件不允许`chapter_number/chapter_end`，不能接收后删除这两个字段。来源ID逐字绑定、全局ID唯一性、claim引用、人物/事件端点与story_order完整性全部严格校验，未知/缺失引用不忽略。服务器只根据每个事件action/consequence/sub_events已验证证据的章节计算min/max；单章两个值相同。不得用人物字段、其他事件、标题或正文长度推测范围。装配后再次校验完整AnalysisReport及事件范围，CAS/预算/原报告不覆盖保护照常。

book/delta和公开import输入不变，旧失败模型候选不变成新wire。原候选额外章号仍拒绝，不通过删除字段、补写引用或扩大重试达到通过。模型和语义审查仍负责引用是否真正支持结论，确定性范围不能代替内容质量。
