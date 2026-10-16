## 5. 预览输出合同与紧凑呈现

只输出一个完整的无缩进紧凑JSON，不加Markdown、解释、自检报告或额外字段；不换行美化，不输出思考过程。事件短标题配简短行动和后果，不写章节梗概式长段落。先删可选的重复观察与附带分句，不靠删除必要人物、关键前因或主事件压缩篇幅。允许省略无内容的可选字段；必填字段、已声明对象的引用和story_order必须完整，不截断JSON凑通过。

遵守本次PreviewGroundedReport schema。报告chapter_numbers恰好覆盖提供章节，不声称读完全书；events、relations、story_order、time_note、evidence、open_questions与characters同级。identity/motivation/change/portrait/action/consequence是{"text":"简短判断","status":"inferred","evidence_ids":["Q1"]}对象，不能写成字符串。findings每项必须有id；contradictions、人物insights、事件sub_events每项只含title/text/status/evidence_ids，不含id。evidence每项只输出{"id":"Q1","source_id":"来源片段编号"}，由服务端装配原文，不输出quote、章号或偏移。只选输入segments中提供的source_id；没有编号的正文仍须阅读，但不可冒充可引用来源。所有引用存在，人物、事件、发现与证据使用全报告唯一的ASCII ID；producer由服务端填写。人物与事件优先使用简短可辨认的ASCII语义ID（姓名拼音或事件含义），遵守既有ID格式和唯一性，回读端点对应的人物或事件；这只是命名偏好，C1等格式合法的ID仍可使用。

每个事件内action、consequence、sub_events必须同级；action/consequence各自只含必填的text/status/evidence_ids，不能把后果或子事件嵌入action。事件同级骨架（占位值须替换为本轮有据内容）：`{"id":"E1","title":"事件短标题","story_time":"有据时段","actor_ids":["C1"],"action":{"text":"简短行动","status":"fact","evidence_ids":["Q1"]},"consequence":{"text":"简短后果","status":"fact","evidence_ids":["Q2"]},"sub_events":[]}`。

预览事件禁止输出chapter_number/chapter_end，不能照旧报告填写章号；服务器严格验证来源和全部引用后，仅由该事件action/consequence/sub_events所选证据的最小/最大章节装配范围，单章两端相同。模型仍负责有据的story_time、story_order和事件语义，来源章节不等于故事时间。返回前复核：主体、时序、因果与关系方向是否一致，状态和每个分句是否获所引来源支持，必要内容是否保留。
