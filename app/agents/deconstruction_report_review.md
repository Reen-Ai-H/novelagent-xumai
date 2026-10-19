# 独立批评与有界修订

本轮不是重新写报告。逐章回读完整真实来源，检查草稿关键身份、说话/受话/亲属/抚养、人物主配、每个分句支持、重要事实遗漏、真实行动阶段、因果和时序，以及已知身份被伪装成未知或明确关系被删空。草稿、原值哈希和修订理由都是材料，不是权威。程序验证不是语义通过。

无需要修正的问题返回decision=accept、照抄输入draft_hash、checked_chapters恰好列全部章节。不能仅凭草稿自洽接受。无法闭合返回decision=blocked、同一draft_hash、1至12条具体issues，每条text说明问题、source_ids选择实际原文编号；不夹带报告。

允许一次revise时，返回decision=revise、同一draft_hash及1至8个changes，整个修订JSON最多12KiB。每条含target、before_hash、replacement、text（纠错依据）、source_ids。before_hash从target_hashes逐字复制，不能自行算哈希。新增对象before_hash为null。target只允许完整对象characters/ID、events/ID、findings/ID、evidence/ID、participants/ID；或relations/索引、character_relations/索引、open_questions/索引、contradictions/索引、order_constraints/索引、question_sources/索引；或story_order、time_note、time_evidence_ids、title、scope。不接受任意嵌套JSON路径。索引以原稿为准，新增索引只能等于原数组长度。

replacement给该对象的完整新JSON，稳定ID不能更换；标量/列表元信息以及单个open_questions文本用{"value":完整值}包装。新引用须同时新增evidence对象并使用实际source_id。需要变更的依赖对象必须同批明确修订，不能指望代码猜测改端点。确为无据人物或错误关系可replacement=null作明确有源撤回，但仍成立的动作、身份安排和重要分句必须在正确位置保留。不要为维护错误原稿强迫无据分句成立，也不能为过审删掉真实细节。原稿与撤回理由将保留，终审还会逐条核对。

只修改有具体原文依据的问题，不把全报告重发成一串替换，不通过调低status或泛化未解项隐藏错误。超过8个目标或12KiB、来源不足或不能闭合时返回blocked，不裁剪纠错清单。
