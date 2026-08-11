# 叙脉视觉原型 B：夜航排演室

## 生成方式

- 使用 Codex 内置 `image_gen`（默认图像生成路径），每个页面单独调用一次。
- 原始生成图为 1536×1024 PNG；复制到项目目录后居中裁切为 1536×960，保持 16:10 桌面页面构图。
- 03 页在 QA 中发现新建弹层遮挡 AI 作品标识，因此用下列最终提示词做了一次针对性重生成；目录内保存的是重生成版本。
- 未使用参考图片、CLI、外部 API、透明背景或后期合成。

## 统一视觉意图

夜紫 `#191526`、幕布紫 `#28213A`、月白 `#F3F0F7`、导演蓝 `#7186FF`、旧铜 `#D1A064`、暗玫瑰 `#B85D70`。思源宋体承担少量戏剧性标题，HarmonyOS Sans 承担界面文字，JetBrains Mono 承担章节与运行状态。页面像深夜剧场排演和电影剪辑台，但始终是清晰、可实现的软件；营销页的签名元素是串起手稿、人物、蓝图和选择的“导演光轨”。避免黑底霓虹 AI、玻璃拟态、粒子宇宙与概念艺术。

## 01-landing.png

```text
Use case: ui-mockup
Asset type: desktop web product landing page, final high-fidelity visual prototype
Primary request: Create the complete visible landing page for “叙脉”, a Chinese long-form fiction writing web product, in the “夜航排演室” direction. The page itself fills the canvas; no device frame or browser chrome.
Composition/framing: exact 16:10 landscape composition simulating a 1440×900 desktop viewport. Clear top navigation, strong left-aligned hero statement, and a large embedded real-product composition on the right and lower half. The product composition visibly combines a manuscript page, nonfigurative character cards, a plot timeline, and a compact AI director console. A single illuminated “导演光轨” begins at the manuscript, threads through character cards and story blueprint, then forks into two clearly labeled routes, “独立创作” and “AI 辅助写作”, and continues beyond the fold to imply scroll-driven 2.5D SVG/DOM motion. Layered planes and soft perspective offsets may imply motion, but every panel remains front-facing and implementable.
Style/medium: shippable mature Chinese SaaS UI, theatrical editorial restraint, modern midnight rehearsal room and film editing suite. Not concept art. Deep paper-and-stage surfaces, precise spacing, restrained soft spotlights, tactile matte paper and subtle curtain texture. Dramatic but credible.
Color palette: night violet #191526, curtain violet #28213A, moon white #F3F0F7, director blue #7186FF, aged brass #D1A064, dark rose #B85D70. Use director blue only for AI route and main action; aged brass for scene markers and fine details.
Typography: sparse Source Han Serif-style Chinese for the large hero title; HarmonyOS Sans-style interface typography; JetBrains Mono-like numerals/status. Large, crisp, readable Chinese. No gratuitous English.
Text (verbatim): brand “叙脉”; nav “功能” “作品示例” “登录”; primary nav button “开始试用”; eyebrow and only tagline “新一代写作体验”; hero title “让长篇故事记得自己”; supporting line “独立创作，或让 AI 辅助写完整部长篇。人物、剧情线与章节记忆始终清晰。”; hero buttons “开始试用” and “看看如何工作”; route labels “独立创作” and “AI 辅助写作”.
Constraints: render the quoted text as accurately and legibly as possible, each phrase only where appropriate. Show actual product UI, not a decorative poster. The hero is the thesis: the light track visibly connects manuscript, people, plot and director console. Avoid excessive small cards. No extra slogans, badges, fake analytics, pricing, testimonials, share/publish/privacy features, humanoid AI robots, 3D spheres, particles, galaxy background, neon cyberpunk glow, glassmorphism, acid colors, gradients used as decoration, or watermark. No laptop, phone, monitor shell, tilted screen, hands, room scene, or physical mockup.
```

## 02-login.png

```text
Use case: ui-mockup
Asset type: desktop web email login page, final high-fidelity visual prototype
Primary request: Create the complete login page for the Chinese fiction-writing product “叙脉” in the same “夜航排演室” visual system. The page itself fills the canvas; no device frame or browser chrome.
Composition/framing: exact 16:10 landscape layout simulating 1440×900. Use an elegant asymmetrical split: a broad atmospheric but still UI-native left field where the landing page’s illuminated director track flows through layered fragments of manuscript, nonfigurative character cue cards, and a faint story timeline, then narrows and converges at the login panel on the right. The login form is large, simple, front-facing, credible, and centered vertically. The light track visibly terminates at the email input / continue action, suggesting a smooth page transition. Layered 2.5D DOM planes and subtle curtain-depth shadows imply motion without becoming concept art.
Style/medium: shippable mature Chinese SaaS authentication UI, midnight rehearsal room, quiet cinematic editorial design. Matte stage violet plus moon-white paper; restrained aged brass and director-blue accents; no flashy effects.
Color palette: night violet #191526, curtain violet #28213A, moon white #F3F0F7, director blue #7186FF, aged brass #D1A064, dark rose #B85D70.
Typography: Source Han Serif-style brand / title, HarmonyOS Sans-style UI, crisp Chinese and simple form labels.
Text (verbatim): “叙脉”; “新一代写作体验”; title “继续你的故事”; label “邮箱”; placeholder “请输入邮箱地址”; primary button “使用邮箱继续”; divider “或”; disabled alternative “手机号登录” with small status “即将开放”; disabled alternative “微信登录” with small status “即将开放”; subtle footer text “登录即表示你同意服务条款”.
Constraints: render quoted Chinese accurately and legibly, with no additional marketing slogans or English. The two future login methods must look visually complete but clearly disabled, not dominant. Keep the form trustworthy and uncluttered. Show only the product page. No extra account features, password fields, QR code, illustrations of people, AI robot avatars, 3D spheres, random particles, galaxy backdrop, neon cyberpunk, glassmorphism, acid colors, giant gradients, watermark, browser chrome, device shell, laptop, phone, room scene, or tilted card.
```

## 03-library-new-project.png

```text
Use case: ui-mockup
Asset type: desktop web app library dashboard with new-project selection overlay, targeted final regeneration
Primary request: Recreate the complete “叙脉” bookshelf home in the “夜航排演室” design system, with one correction: the AI project card must visibly show a director-blue strip labeled exactly “AI 辅助写作” even while the new-project modal is open.
Composition/framing: exact 16:10 landscape layout simulating 1440×900, flat front-facing page. Narrow left book-spine navigation; calm main library with welcome, search and credits. Three project cards arranged in a row. Put the AI project card on the far right or place its blue type strip on the unobscured top edge so the strip and exact label remain fully visible outside the centered modal. Open a centered new-project selection overlay slightly left of center and sized so substantial portions of the work cards remain visible. Each project card includes nonfigurative cover, title, chapter count, word count and last edit. Exactly one card has the clearly visible director-blue strip “AI 辅助写作”; independent cards have no blue strip.
Style/medium: practical mature Chinese desktop SaaS UI, midnight rehearsal room and film editing desk translated to implementable interface. Matte cue cards, subtle paper texture, local soft spotlights, spacious hierarchy.
Color palette: night violet #191526, curtain violet #28213A, moon white #F3F0F7, director blue #7186FF, aged brass #D1A064, dark rose #B85D70.
Typography: Source Han Serif-like work titles, HarmonyOS Sans-like UI, JetBrains Mono-like numeric metadata.
Text (verbatim): “叙脉”; left nav “书架” selected, “账户”, “帮助”; “晚上好，林舟”; “搜索作品”; “创作积分 8,420”; “新建作品”; project titles “雾港来信”, “北纬四十度”, “沉睡的钟楼”; visible AI type strip “AI 辅助写作”; modal title “新建作品”; first option “独立创作” and “上传旧稿或从空白章节开始”; second option “AI 辅助写作” and “与主编补全蓝图，再由导演台持续创作”; “取消”.
Constraints: the AI blue type strip and exact text MUST remain unobscured and easy to read. The open modal and both mode choices must also be fully visible. Render major Chinese accurately. Nonfigurative covers only, no realistic faces. No extra modes or out-of-scope actions. No share, publish, privacy, analytics, social, AI robots, galaxy, particles, 3D spheres, glassmorphism, cyberpunk neon, acid colors, device frames, browser chrome, physical room scene, tilted screens or watermark.
```

## 04-independent-editor.png

```text
Use case: ui-mockup
Asset type: desktop long-form Chinese fiction editor, final high-fidelity visual prototype
Primary request: Create the complete independent-writing editor for “叙脉” in the “夜航排演室” visual system. It must look like a calm, practical, shippable web writing workspace rather than a theatrical poster.
Composition/framing: exact 16:10 landscape layout simulating 1440×900, front-facing. Four disciplined bands: very narrow book-spine product rail; a chapter/navigation column on the left; a very wide central moon-white manuscript editor; a slim collapsible story-record sidebar on the right. Current chapter is chapter 101. The central writing page dominates with generous line length and spacing. Top editor bar shows save state, word count and chapter actions. Right sidebar is secondary and quiet, with only four compact sections.
Style/medium: mature Chinese desktop productivity UI translated from a midnight rehearsal / editing suite. Dark violet side structures frame a warm moon-white paper editor under a gentle focused spotlight. Matte surfaces, restrained aged-brass chapter markers, no glow except a subtle director-blue focus state. Cards feel like cue cards, but every control follows normal web conventions.
Color palette: night violet #191526, curtain violet #28213A, moon white #F3F0F7, director blue #7186FF, aged brass #D1A064, dark rose #B85D70.
Typography: Source Han Serif-style for chapter title and novel body; HarmonyOS Sans-style for UI; JetBrains Mono-like chapter numbers and word count.
Text (verbatim): brand “叙脉”; work title “雾港来信”; work nav “写作” selected, “故事档案”, “作品设置”; chapter heading “第 101 章 退潮之后”; chapter list includes “第 98 章 海雾”, “第 99 章 未寄出的信”, “第 100 章 灯塔失声”, “第 101 章 退潮之后”; top status “已保存”; “本章 2,418 字”; button “完成本章”; right sidebar title “故事档案”; section labels “本章变化” “人物状态” “剧情线” “疑问点”; body excerpt “潮水退得比往常更远。林舟站在堤岸尽头，看见礁石之间露出一条从未出现过的路。” and two more natural Chinese novel paragraphs.
Constraints: no AI generation, AI continuation, rewrite, polish, prompt, chat, sparkle or wand buttons anywhere. The primary action is only “完成本章”. Keep the editor content calm and readable; right sidebar clearly collapsible and low pressure. Do not add dashboard charts, publishing, sharing, collaboration, privacy or social features. No browser chrome, device frame, angled screen, physical room, people, AI robots, universe, random particles, spheres, cyberpunk neon, glassmorphism, acid colors, watermark, or excessive decorative cards. Render major quoted Chinese accurately.
```

## 05-story-archive.png

```text
Use case: ui-mockup
Asset type: desktop story-archive dashboard for a long Chinese novel, final high-fidelity visual prototype
Primary request: Create the complete “故事档案” page for “叙脉” in the “夜航排演室” visual system. It must be a usable software screen for tracking characters, story lines, foreshadowing and gentle questions across chapter snapshots.
Composition/framing: exact 16:10 landscape layout simulating 1440×900, flat front-facing. Left side has a narrow book-spine rail plus work navigation; “故事档案” is selected. The large main area begins with an explicit snapshot switcher reading current state through chapter 100 and a visible option/control for chapter 20. Below, use an editorial dashboard with four clearly separated content regions: “人物”, a dominant horizontally traceable “剧情线” timeline, “伏笔”, and “疑问点”. The timeline must be a reversible chronological light rail with chapter markers and source annotations, not a fishbone diagram and not a generic kanban board. Character cards use nonfigurative symbolic portrait cards, with clear status changes and chapter sources. The question card uses compassionate, non-accusatory language.
Style/medium: high-fidelity practical Chinese desktop SaaS UI. Dark midnight rehearsal/control room framing, matte cue-card modules, localized soft spotlights, moon-white text surfaces and old-brass scene marks. Structured and calm, not data-heavy.
Color palette: night violet #191526, curtain violet #28213A, moon white #F3F0F7, director blue #7186FF, aged brass #D1A064, dark rose #B85D70. Use dark rose only for the gentle question indicator, never as an error alarm.
Typography: sparse Source Han Serif-like section title; HarmonyOS Sans-like UI; JetBrains Mono-like chapters and timestamps.
Text (verbatim): brand “叙脉”; work “雾港来信”; nav “写作”, “故事档案” selected, “作品设置”; page title “故事档案”; snapshot control “当前状态 · 截至第 100 章”; alternate “查看第 20 章”; tabs or sections “人物” “剧情线” “伏笔” “疑问点”; character names “林舟” “周烬” “顾沉”; character states such as “仍在雾港 · 第 100 章” “开始怀疑顾沉 · 第 96 章”; timeline events “第 3 章 攀上旧塔” “第 37 章 收到匿名信” “第 68 章 灯塔停摆” “第 100 章 路径显现”; foreshadow item “未寄出的信 · 最后推进于第 99 章”; exact gentle question “林舟本章开始畏惧高处，但第 3 章曾独自攀塔——这是人物变化，还是需要回看？”
Constraints: render major quoted Chinese clearly and accurately. Use nonfigurative character cue cards: geometric silhouettes, wardrobe blocks and symbolic objects; no explicit faces. The page must emphasize source chapter traceability and historical snapshot. Avoid ordinary business charts, KPI cards, pie charts, fishbones, kanban columns, error-red warning banners, share/publish/privacy/social features, AI robots, 3D spheres, universe, particles, cyberpunk neon, glassmorphism, acid colors, device frames, browser chrome, physical room scenes, tilted screens, watermark, or excess decoration.
```

## 06-ai-blueprint-chat.png

```text
Use case: ui-mockup
Asset type: desktop AI-assisted novel blueprint chat workspace, final high-fidelity visual prototype
Primary request: Create the complete “创作室” blueprint-preparation page for “叙脉” in the “夜航排演室” system. The author has selected AI-assisted writing and is discussing the novel with one unified “主编” while the story blueprint fills in live. This must be a real implementable web product screen, not a poster.
Composition/framing: exact 16:10 landscape layout simulating 1440×900, flat front-facing. Narrow book-spine rail plus a left creation-stage navigation where “创作室” is current. Central wide conversation between “你” and “主编”; use only one visible editorial voice, with readable natural Chinese bubbles and a persistent bottom input. Show a restrained horizontal backstage strip for four specialist roles—剧情、人物、世界观、节奏—as small status cue cards, not four chat threads. Right third is a structured “创作蓝图” panel that visibly updates, with six compact fields and completion status. Bottom primary action reads “确认蓝图并开始创作”.
Style/medium: mature high-fidelity Chinese desktop SaaS UI. Midnight theatre rehearsal / film editing desk translated into clear productivity software. Focused soft spotlight on the active conversation and moon-white blueprint cue sheet, matte violet panels, subtle old-brass scene index marks, director blue only for active AI status and primary action. Quiet theatrical depth, no sci-fi spectacle.
Color palette: night violet #191526, curtain violet #28213A, moon white #F3F0F7, director blue #7186FF, aged brass #D1A064, dark rose #B85D70.
Typography: Source Han Serif-style for page / blueprint headings; HarmonyOS Sans-style for UI and messages; JetBrains Mono-like for stage progress.
Text (verbatim): brand “叙脉”; creation stages “创作室” selected, “确认蓝图”, “开始创作”; header “和主编一起搭好故事”; conversation labels “你” and “主编”; user message “我想写一个发生在被海雾封锁的港口城市里的悬疑故事。”; editor response “我们先确定主角最想守住什么。这个答案会决定核心冲突，也会影响结局方向。”; backstage roles “剧情” “人物” “世界观” “节奏”; statuses “正在梳理” and “已同步”; blueprint heading “创作蓝图”; fields “故事前提” “核心冲突” “主角” “世界规则” “结局方向” “目标篇幅”; values “海雾封锁的港口城市”, “寻找真相与守住亲人”, “林渡 · 灯塔维修员”, “海雾会抹去部分记忆”, “尚待确认”, “80 万字”; input placeholder “继续补充你的想法…”; button “确认蓝图并开始创作”.
Constraints: one visible “主编” conversation only; the four specialist roles are subdued backstage status, not talking agents. Render major Chinese accurately and legibly. Blueprint panel must be useful and structured, not a vague mood board. No extra slogans, marketing badges, multiple competing chat columns, avatars with human faces, AI robot imagery, galaxy, particles, 3D spheres, cyberpunk neon, glassmorphism, acid colors, angled screens, devices, physical room, watermark, generic analytics, publishing, sharing, privacy or social features.
```

## 07-ai-director.png

```text
Use case: ui-mockup
Asset type: desktop AI novel director console with key story choice, final high-fidelity visual prototype
Primary request: Create the complete “AI 导演台” for “叙脉” in the “夜航排演室” visual system. The system is autonomously generating chapter 38 and has reached one consequential director choice. This must look like practical, shippable Chinese creative software, not a game poster or sci-fi command center.
Composition/framing: exact 16:10 landscape layout simulating 1440×900, flat front-facing. Left book-spine navigation has “导演台” selected plus “编辑正文”, “故事档案”, “作品设置”. Top run strip clearly shows “正在生成第 38 章”, a three-stage sequence “角色推演 / 正文生成 / 审查” with one stage active, a modest creation-credit budget readout, and a visible “暂停” button. Main upper area displays three separated nonfigurative role-agent cue cards with distinct private-memory layers; a single horizontal public baseline underneath connects them and is labeled shared world knowledge. Main lower area is dominated by one tasteful director cue card for the key node “林渡准备进入封锁区” with exactly three mutually exclusive choices. Possible consequences stay hidden behind a small closed control; do not display spoilers or any parallel-branch tree.
Style/medium: mature high-fidelity Chinese desktop SaaS UI, midnight theatre rehearsal and film editing table. Matte violet structures, localized gentle spotlights, moon-white cue paper, old brass scene marks, director blue for active generation and choice focus. Cinematic but calm and actionable; not overly data-driven.
Color palette: night violet #191526, curtain violet #28213A, moon white #F3F0F7, director blue #7186FF, aged brass #D1A064, dark rose #B85D70.
Typography: Source Han Serif-like for the key-node title; HarmonyOS Sans-like interface; JetBrains Mono-like chapter number, stages, budget.
Text (verbatim): brand “叙脉”; nav “导演台” selected, “编辑正文”, “故事档案”, “作品设置”; work title “雾港来信”; run state “正在生成第 38 章”; stages “角色推演” active, “正文生成”, “审查”; budget “本次预算 12,000 积分”; used “已用 3,680”; button “暂停”; section heading “角色正在推演”; character cards “林渡” “顾遥” “周烬”; on each private layer label “私有记忆”; shared baseline label “共享世界观与必要事实”; key card label “关键节点”; title “林渡准备进入封锁区”; prompt “以导演身份决定故事走向”; options exactly “相信顾遥的警告，暂时撤退” “隐瞒发现，独自进入” “把决定交给林渡”; closed control “可能后果 · 已隐藏”; subtle note “选择后继续创作”.
Constraints: render major Chinese accurately and legibly. Character cue cards are nonfigurative: geometric silhouettes, symbolic object, wardrobe colors, no real faces. Make private-memory separation unmistakable and the shared baseline singular. Exactly one formal storyline; no branch tree, no map of alternate futures, no exposed spoiler outcomes. Avoid dashboards with many charts, KPI overload, video-game HUD, humanoid AI robots, galaxy, particles, 3D spheres, cyberpunk neon, acid colors, glassmorphism, device shells, browser chrome, tilted screens, physical control room, watermark, publishing, sharing, privacy or social features.
```

## 已知图像文字限制

- 图像模型对大标题、按钮和一级导航的中文渲染较稳定，但较小字号的正文、元数据或长句仍可能出现个别字形误差；这些图片用于视觉方向选择，不应作为最终前端文字稿。
- 01 页嵌入式产品面板中的小字号内容以层级和密度为主，部分并非逐字可用；品牌、主标题、两个创作路径及主要操作清晰。
- 03 页为保证 AI 类型标识在弹层打开时仍可见，最终稿把带蓝条的作品放在右侧；中间作品标题与部分首卡信息被弹层合理遮挡。
- 04 页编辑器正文由模型补写，适合验证宋体阅读节奏，不代表正式小说内容。
- 05 页疑问点保留温和语气和章节来源，长句可能有轻微字形差异。
- 07 页按导演节点实际涉及的角色显示三张角色牌（林渡、顾遥、周烬）；角色私有记忆与共享世界观基线均清楚可见。
