# 阶段 32A：真实拆解与前端体验

用户当前认可 Codex 局部样板质量。近期只改进拆解及体验，暂停生成、蒸馏、双引擎。继续分支 codex/stage-32-codex-deconstruction-preview 和 Draft PR #8，不合并或部署。

## 当前行为

- 独立创作导航为正文、作品拆解、版本记录。旧故事档案路径跳转拆解；AI 辅助写作档案保持原用途，不删除历史数据。
- 作品拆解展开剧情地图、人物卡、双时间线。完成后直接展示内容，移除完成说明、发现总览、来源标识与运行历史。
- 人物总览两段短文，点击进入可刷新/返回的人物详情，按原文提供具体行为观察与依据。剧情节点代表完整大事件。
- 正文右侧只显示当前有效结果的人物、大剧情、矛盾和疑问数量。未拆解、过期、正在修改时显示未知；点击跳转对应拆解。
- Codex 样板覆盖实际第1–5章，6个人物、2段大剧情、1个文本矛盾、4个疑问、39条唯一匹配引文。原小说、报告与本地账户均不入库。

## API 与 Skill

`schemas/analysis_report.py` 为平台合同。人物 insights 和 contradictions 均有 title/text/status/evidence_ids。所有引用由程序在指定章唯一匹配并计算 UTF-16；新结果不得越过来源版本或待确认修改。

`POST /api/independent/projects/{id}/deconstruction/analyze-preview` 接收当前 expected_source_version_id/revision/hash 和 chapter_numbers。最多20章、30000字符；整个模型等待最多240秒。一次正常调用，格式错误最多一次修复；失败保留当前正式结果。

试拆返回 AnalysisImport 预览包，不自动替换；用户点击采用后走已有 `/deconstruction/import` 再次核对来源。页面刷新会丢弃尚未采用的预览，已采用结果持久保存。预览内显示引文，采用后可精确回正文。

拆解使用独立 DECONSTRUCTION_API_KEY/BASE_URL/MODEL 配置，不改变 AI 创作室模型。当前 DeepSeek 模型通过认证列表选定 V4 Pro，非思考模式；配置只保存在本地 .env。可换 OpenAI-compatible API，换模型不保证文学质量一致。

本机 xumai-deconstruct Skill v0.4 与便携包在项目外更新；API 使用 app/agents/deconstruction_prompt.md，其语义规则与 Skill 对齐，不依赖用户机器上的绝对路径。

## 针对性验证

浏览器实际检查桌面人物卡/详情、左侧三视角、折叠导航、刷新人物页、正文四项统计及跳转、原文精确选区。新接口以 fake 模型测试来源、坏引文、不替换旧结果及采用；自动化测试隔离凭证并阻断外网。

DeepSeek 已通过真实认证及第一章试拆。首轮发现传闻在摘要中变成定论、匿名群众被凑为人物，已加强可见措辞规则并重试；结构校验不代表质量已达到 Codex 样板，默认保留原样板。

最终验证145项通过（13.994秒、0失败/错误/跳过），两次真实页面试拆可返回预览；第二次仍存在传闻/文本矛盾分类和部分证据支持不足，因此未采用。
