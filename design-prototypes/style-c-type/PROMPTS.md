# 叙脉视觉原型 C：未来活字

## 生成方式

- 使用内置 `image_gen`（gpt-image-2 路径），每个页面独立生成一次。
- 所有页面均为桌面 Web 产品高保真 UI；内置生成结果保存到项目后，以系统图像工具规范化为 1440×900（01 为保留顶栏完整性直接重采样，其余采用居中裁切后重采样）。
- 共同视觉：晴空纸 `#EAF2FF`、深靛 `#14213D`、活字蓝 `#236BFE`、淡紫 `#A995FF`、校样珊瑚 `#FF6B57`、日光黄 `#F5C34B`；少量得意黑风格大标题、MiSans 风格界面字、Roboto Mono 风格章节索引。
- 共同约束：画面就是页面本身；无设备外壳、透视样机、通用 3D、机器人、随机粒子、无意义图表、水印；不做彩色 Bento 卡片堆砌；中文主要文案逐字呈现，不增加无关英文或宣传旗标。

## 01-landing.png

```text
Use case: ui-mockup
Asset type: desktop SaaS product landing page, high-fidelity full browser content
Primary request: Create the first viewport of “叙脉”, a Chinese long-form novel writing web product, in the “未来活字” visual direction. The hero must feel like an implemented modern website with a believable 2.5D SVG/DOM scroll animation, not a poster. Use a large offset typographic composition: movable Chinese type blocks and chapter labels slide on thin horizontal rails and recompose into two functional routes. A continuous blue typographic rail begins in a real manuscript editor preview, passes through a nonfigurative character profile and reversible plot timeline, then separates into “独立创作” and “AI 辅助写作”; the line continues below the fold to imply scroll evolution. Show real product UI previews integrated into the hero, not floating device mockups.
Scene/backdrop: bright sky-paper canvas, generous whitespace, subtle flat paper grain only
Style/medium: shippable desktop web UI; precise editorial typography; bold asymmetric spacing; crisp 2D/2.5D DOM layers; young, rhythmic, optimistic
Composition/framing: exact 16:10 landscape page, simulated 1440×900 browser content. Slim top navigation. Large headline occupies left and center; real editor/archive/director UI composition occupies lower-right and crosses the fold. Preserve breathing room.
Color palette: #EAF2FF sky paper, #14213D deep indigo, #236BFE type blue, #A995FF pale violet, #FF6B57 proof coral, #F5C34B sunlight yellow; mostly blue paper and indigo, accents used sparingly
Typography: Smiley Sans/得意黑-like display only for hero; MiSans-like UI; Roboto Mono-like chapter markers
Text (verbatim): “叙脉”, “功能”, “作品示例”, “登录”, “开始试用”, “新一代写作体验”, “让长篇故事记得自己”, “独立创作，或让 AI 辅助写完整部长篇。人物、剧情线与章节记忆始终清晰。”, “看看如何工作”, “独立创作”, “AI 辅助写作”, “人物档案”, “剧情线”, “导演台”
Constraints: render the Chinese text clearly and exactly; use only one slogan; large whitespace and offset typography rather than colorful Bento tiles; make the product previews visibly usable; no extra marketing badges
Avoid: poster composition, device frame, screen-in-room mockup, generic gradient blocks, card mosaic, 3D blobs, robots, particles, dark neon, watermark, illegible pseudo-text
```

针对性修正（首页初稿误把默认角色牌画成具象人物，最终文件使用一次局部编辑结果）：

```text
Use case: precise-object-edit
Asset type: high-fidelity desktop landing page UI correction
Input images: Image 1 is the edit target, the existing “叙脉” landing-page UI.
Primary request: In the “人物档案” panel only, replace the realistic woman portrait with a nonfigurative abstract typographic character card made from the Chinese character “角”, a cobalt-blue baseline grid, and a small pale-violet role marker. No human face, body, silhouette, or realistic character illustration.
Constraints: change only the portrait area inside the 人物档案 panel; preserve the entire landing-page layout, crop, 16:10 framing, Chinese text, typography, product previews, blue story rail, buttons, colors, spacing, lighting, and all other UI exactly as in Image 1; keep it a shippable web page; no extra words; no watermark.
Avoid: character face, person, anime portrait, concept art, redesign, new decoration, changed text.
```

## 02-login.png

```text
Use case: ui-mockup
Asset type: desktop email login page, high-fidelity full browser content
Primary request: Create the login page for “叙脉” in the same “未来活字” system. The landing page’s moving typographic rails converge from the page edges into a quiet, trustworthy email form. Large scattered chapter words become aligned baseline markers as they approach the form, visually demonstrating the animation resolving into focus. The login panel is simple and practical, not glassmorphic.
Scene/backdrop: #EAF2FF sky-paper full page with generous open space and restrained flat paper texture
Style/medium: shippable desktop web UI; crisp type-led 2.5D SVG/DOM motion cue; youthful but trustworthy
Composition/framing: exact 16:10 page. Brand in top-left. A compact login form slightly right of center. Typographic rails enter from left and upper edge, then settle behind or beside the form without obstructing it.
Color palette: #EAF2FF, #14213D, #236BFE, #A995FF, with tiny #FF6B57 and #F5C34B registration marks
Typography: Smiley Sans-like title sparingly; MiSans-like interface; Roboto Mono-like status labels
Text (verbatim): “叙脉”, “新一代写作体验”, “继续你的故事”, “邮箱”, “name@example.com”, “使用邮箱继续”, “手机号登录”, “微信登录”, “即将开放”
Constraints: clear readable Chinese; one working email action; phone and WeChat controls visually complete but disabled, each marked “即将开放”; no password field; no extra social providers; credible spacing and focus state
Avoid: dramatic illustration, people, devices, login-card glassmorphism, generic gradient sphere, dark neon, extra slogan, watermark, pseudo-text
```

## 03-library-new-project.png

```text
Use case: ui-mockup
Asset type: desktop web app library with new-project selection overlay
Primary request: Create the “叙脉” bookshelf home after login in the “未来活字” system. A slim left navigation is structured like a book spine and chapter index, with “书架” selected. Show a polished, calm workspace with three believable Chinese novel cards, each including a nonfigurative typographic cover/character card, chapter progress, word count, and recent edit time. One novel has a clear vertical cobalt-blue strip labeled “AI 辅助写作”; independent works have no blue strip. Open a large new-project choice layer over the library with exactly two strong, spacious options, not a grid of tiny cards: “独立创作” and “AI 辅助写作”. Use offset type blocks and a baseline rail as the transition motif.
Scene/backdrop: bright #EAF2FF application canvas, white-blue paper surfaces, subtle crisp borders
Style/medium: shippable high-fidelity desktop product UI; clean asymmetric editorial layout; internal workspace mostly static
Composition/framing: exact 16:10. Left book-spine navigation 176px; main library behind a centered choice sheet. Header contains welcome, search and points. Three work cards remain legible around the sheet.
Color palette: #EAF2FF, #14213D, #236BFE, #A995FF, #FF6B57, #F5C34B; accents sparse
Typography: MiSans-like UI; Smiley Sans-like large option titles; Roboto Mono-like chapter/progress metadata
Text (verbatim): “叙脉”, “书架”, “最近创作”, “创作积分 8,420”, “搜索作品”, “欢迎回来”, “雾港来信”, “第 100 / 160 章”, “426,800 字”, “2 小时前编辑”, “纸月亮”, “第 37 / 80 章”, “168,200 字”, “昨天编辑”, “北境回声”, “第 12 / 60 章”, “52,400 字”, “3 天前编辑”, “AI 辅助写作”, “新建作品”, “独立创作”, “上传旧稿或从空白章节开始”, “AI 辅助写作”, “与主编补全蓝图，再由导演台持续创作”
Constraints: no figurative faces in default covers; show real progress information; exact two new-project choices; AI blue strip is functional metadata, not a marketing badge; left nav must resemble a useful spine/index
Avoid: generic colorful Bento dashboard, analytics charts, published/share buttons, 3D book mockups, floating device, dark mode, watermark, meaningless English
```

## 04-independent-editor.png

```text
Use case: ui-mockup
Asset type: desktop long-form Chinese writing editor
Primary request: Create the independent-writing editor for “叙脉” in the “未来活字” system. This is a quiet professional workspace: left book-spine navigation plus chapter list with Chapter 101 selected; a wide centered Chinese manuscript editor; a restrained collapsible story archive sidebar on the right. Keep the signature typographic rhythm only in chapter index tabs, baseline markers and the primary action, not as decoration. No AI writing controls.
Scene/backdrop: pale sky-paper application canvas with a pure light writing sheet
Style/medium: implementation-ready high-fidelity web editor; calm, typographically excellent, dense enough to be useful but never dashboard-like
Composition/framing: exact 16:10. Left column for work navigation and chapters; broad center manuscript; slim right archive sidebar. Top bar shows save status, word count and chapter actions.
Color palette: #EAF2FF and white surfaces, #14213D text, #236BFE selection, small #FF6B57 question accent, minimal #A995FF/#F5C34B
Typography: MiSans-like UI; comfortable Chinese reading type for body; Roboto Mono-like chapter numbers and counts
Text (verbatim): “叙脉”, “返回书架”, “写作”, “故事档案”, “作品设置”, “章节”, “第 99 章 雨夜”, “第 100 章 越界”, “第 101 章 回声”, “已保存”, “2,846 字”, “第 101 章 回声”, “风从封锁区的方向吹来，卷起街角最后一张旧报纸。林舟停在路灯下，没有立刻回头。”, “他记得顾遥说过，门后的世界不会等待任何人准备好。”, “本章变化”, “人物状态”, “剧情线”, “疑问点”, “完成本章”
Constraints: central editor must dominate; sidebar can collapse; no AI续写, no改写, no publish/share controls; real readable paragraphs and credible spacing; internal motion minimal
Avoid: marketing hero, colorful card wall, AI chat, generic toolbar overload, 3D objects, dark neon, watermark, pseudo-text
```

## 05-story-archive.png

```text
Use case: ui-mockup
Asset type: desktop story archive and chapter snapshot page
Primary request: Create the “故事档案” page for “叙脉” in the “未来活字” system. The data is a living typographic timeline, not a Kanban board or fishbone chart. Left book-spine work navigation with “故事档案” selected. At top, a chapter snapshot control says current state through Chapter 100 and offers Chapter 20. Main page has four meaningful zones—人物, 剧情线, 伏笔, 疑问点—organized along a reversible horizontal/vertical chapter rail. Character cards use abstract nonfigurative typographic role cards, never faces. Each state change cites a source chapter. Use colored movable type tabs only to encode category/state.
Scene/backdrop: bright sky-paper workspace with broad negative space and crisp white-blue document layers
Style/medium: shippable high-fidelity product UI; editorial data visualization; calm and legible
Composition/framing: exact 16:10. Left spine navigation; top snapshot selector; central large traceable timeline; character and clue details align to chapter rails; mild asymmetry creates rhythm.
Color palette: #EAF2FF, #14213D, #236BFE; #A995FF secondary state, #FF6B57 questions, #F5C34B unresolved clue
Typography: MiSans-like UI; Smiley Sans-like section initial only; Roboto Mono-like chapter sources
Text (verbatim): “叙脉”, “写作”, “故事档案”, “作品设置”, “当前状态 · 截至第 100 章”, “切换至第 20 章”, “人物”, “剧情线”, “伏笔”, “疑问点”, “林舟”, “顾遥”, “第 17 章受伤”, “第 20 章开始怀疑顾遥”, “第 38 章进入封锁区”, “来源：第 100 章”, “林舟本章开始畏惧高处，但第 3 章曾独自攀塔——这是人物变化，还是需要回看？”
Constraints: snapshot switching must be visually obvious; timeline must be reversible and chapter-based; question wording is calm, not an error alert; nonfigurative character cards; cite chapters
Avoid: ordinary Kanban, fishbone diagram, generic analytics dashboard, character portraits, harsh red warnings, meaningless charts, device frame, watermark, pseudo-English
```

## 06-ai-blueprint-chat.png

```text
Use case: ui-mockup
Asset type: desktop AI-assisted novel setup, editor chat plus live blueprint
Primary request: Create the AI-assisted “创作室” setup page for “叙脉” in the “未来活字” system. Left side shows creation stages with the current stage “创作室”. Center is one coherent natural conversation between the author and a single “主编”; do not stack multiple agent chats. Behind the editor, four specialist roles—剧情、人物、世界观、节奏—are visible as small quiet typographic status tabs on one rail, showing backstage collaboration without taking over. Right side is a live “创作蓝图” document with six fields and visible completion progress. Bottom has a real input composer and one main action.
Scene/backdrop: #EAF2FF app canvas with light document surfaces; no dramatic sci-fi environment
Style/medium: shippable high-fidelity desktop web UI; young type-led system; practical conversation and form layout
Composition/framing: exact 16:10. Left stage spine 160px; center conversation about 52%; right blueprint about 32%; bottom composer spanning the center. Use a few offset type labels to connect dialogue decisions into blueprint fields.
Color palette: #EAF2FF, #14213D, #236BFE, #A995FF, small #FF6B57 and #F5C34B
Typography: MiSans-like UI/chat; Smiley Sans-like blueprint heading; Roboto Mono-like status and completion
Text (verbatim): “叙脉”, “新建 AI 辅助作品”, “创作思路”, “创作室”, “确认蓝图”, “主编”, “你想写一个怎样的故事？”, “我想写一部近未来悬疑小说，主角能读取物品残留的记忆。”, “这个能力最有张力的限制是什么？它会让主角失去自己的记忆吗？”, “剧情”, “人物”, “世界观”, “节奏”, “创作蓝图”, “故事前提”, “核心冲突”, “主角”, “世界规则”, “结局方向”, “目标篇幅”, “80 万字”, “输入你的想法…”, “确认蓝图并开始创作”
Constraints: only the editor communicates with the author; specialists remain quiet status roles; blueprint fields are useful and legible; main action appears once; no extra agents speaking
Avoid: multi-agent chat clutter, robot avatars, generic chatbot-only screen, card mosaic, neon sci-fi, 3D decorations, watermark, irrelevant English
```

## 07-ai-director.png

```text
Use case: ui-mockup
Asset type: desktop AI novel director console with a key decision
Primary request: Create the running AI director console for “叙脉” in the “未来活字” system. Left spine navigation contains 导演台 selected, 编辑正文, 故事档案, 作品设置. Top clearly shows Chapter 38 currently generating and the phase “角色推演”, with a modest budget strip and pause action. The center visualizes separate character agents as distinct abstract typographic role cards with private-memory layers; they do not share memories. A single straight public-world baseline labeled “共享世界观” connects only the necessary common facts. Below/right, a large key decision card asks what the director chooses. Three options are spacious text rows on one decision rail. Possible consequences are hidden by default. No branching-tree visualization.
Scene/backdrop: pale sky-paper professional workspace; restrained internal motion cues in the active chapter rail only
Style/medium: shippable high-fidelity desktop web product; clear operational state; type-led, youthful, calm
Composition/framing: exact 16:10. Left spine nav; top run status; central memory-stage diagram and large key-node card balanced in two zones. Avoid over-dense metrics.
Color palette: #EAF2FF and white-blue paper, #14213D, #236BFE primary AI state, #A995FF private memory, #FF6B57 key-node mark, #F5C34B small director accent
Typography: MiSans-like UI; Smiley Sans-like key-node title; Roboto Mono-like chapter and phase labels
Text (verbatim): “叙脉”, “导演台”, “编辑正文”, “故事档案”, “作品设置”, “正在生成 · 第 38 章”, “角色推演”, “正文生成”, “审查”, “本次预算 12,000 积分”, “已用 3,680”, “暂停创作”, “林渡”, “顾遥”, “沈栖”, “私有记忆”, “共享世界观”, “关键节点”, “林渡准备进入封锁区”, “相信顾遥的警告，暂时撤退”, “隐瞒发现，独自进入”, “把决定交给林渡”, “可能后果已隐藏”
Constraints: character cards are nonfigurative and visibly isolated; public baseline does not imply shared private memories; one formal story line only; consequences hidden; no parallel branch tree; budget information is modest
Avoid: gaming HUD, generic analytics dashboard, network spiderweb, multiverse branches, character faces, neon dark mode, robots, card mosaic, device frame, watermark, pseudo-text
```

## 已知限制

图像模型对密集中文小字号的逐字渲染仍可能存在错字、漏字或伪字；本轮把关键标题、按钮和状态设为高优先级，正文与次级元数据用于验证信息层级与布局，进入代码实现时应使用真实 HTML 文本替换图内文字。
