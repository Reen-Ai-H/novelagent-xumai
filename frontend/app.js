const stageOrder = [
  "planning",
  "awaiting_human_review",
  "writing",
  "awaiting_review",
  "reviewing",
  "awaiting_revision_decision",
  "revising",
  "awaiting_chapter_acceptance",
  "extracting_lore",
  "completed",
];

const stageText = {
  planning: "规划中",
  awaiting_human_review: "等待人工审核",
  writing: "正文生成中",
  awaiting_review: "等待审查",
  extracting_lore: "设定抽取中",
  reviewing: "审查中",
  awaiting_revision_decision: "等待修稿确认",
  revising: "修稿中",
  awaiting_chapter_acceptance: "等待接受章节",
  completed: "已完成",
  failed: "失败",
};

const stageStepIndex = {
  planning: 0,
  awaiting_human_review: 1,
  writing: 2,
  awaiting_review: 2,
  reviewing: 3,
  awaiting_revision_decision: 3,
  revising: 2,
  awaiting_chapter_acceptance: 3,
  extracting_lore: 4,
  completed: 4,
};

const appState = {
  projectId: "default",
  project: null,
  sessionId: "",
  plotBeats: [],
  activeBeatIndex: 0,
  reviewDecision: "approved",
  draft: null,
  loreUpdates: {},
  characterUpdates: {},
  characters: [],
  stage: "planning",
  agentTimer: null,
  typeTimer: null,
  revisionTimer: null,
  revisionCountdown: 10,
  stageSidebarCollapsed: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const characterRoleOptions = [
  { value: "protagonist", label: "主角" },
  { value: "supporting", label: "重要配角" },
  { value: "antagonist", label: "反派" },
  { value: "minor", label: "次要人物" },
  { value: "unknown", label: "暂未确定" },
];

const elements = {
  appShell: $("#appShell"),
  sidebarToggle: $("#sidebarToggle"),
  projectTitle: $("#projectTitleInput"),
  worldview: $("#worldviewInput"),
  chapter: $("#chapterInput"),
  session: $("#sessionInput"),
  summary: $("#summaryInput"),
  instruction: $("#instructionInput"),
  charactersBuilder: $("#charactersBuilder"),
  addCharacterBtn: $("#addCharacterBtn"),
  feedback: $("#feedbackInput"),
  planBtn: $("#planBtn"),
  approveBtn: $("#approveBtn"),
  approveDecisionBtn: $("#approveDecisionBtn"),
  rejectDecisionBtn: $("#rejectDecisionBtn"),
  refreshBtn: $("#refreshBtn"),
  fillExampleBtn: $("#fillExampleBtn"),
  beatsContainer: $("#beatsContainer"),
  sessionBadge: $("#sessionBadge"),
  draftOutput: $("#draftOutput"),
  metaOutput: $("#metaOutput"),
  characterCards: $("#characterCards"),
  loreFishbone: $("#loreFishbone"),
  stageLabel: $("#stageLabel"),
  agentEyebrow: $("#agentEyebrow"),
  agentTitle: $("#agentTitle"),
  agentStream: $("#agentStream"),
  toast: $("#toast"),
  wordCountStat: $("#wordCountStat"),
  projectStat: $("#projectStat"),
  chapterStat: $("#chapterStat"),
  sessionStat: $("#sessionStat"),
  progressStat: $("#progressStat"),
  beatsStat: $("#beatsStat"),
  reviewStat: $("#reviewStat"),
  previewTitle: $("#previewTitle"),
  previewContent: $("#previewContent"),
  chapterCatalog: $("#chapterCatalog"),
  continueNextBtn: $("#continueNextBtn"),
  chapterDecisionPanel: $("#chapterDecisionPanel"),
  decisionTitle: $("#decisionTitle"),
  decisionMessage: $("#decisionMessage"),
  revisionCountdown: $("#revisionCountdown"),
  acceptChapterBtn: $("#acceptChapterBtn"),
  reviseNowBtn: $("#reviseNowBtn"),
  waitRevisionBtn: $("#waitRevisionBtn"),
  confirmReviseBtn: $("#confirmReviseBtn"),
};

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  window.setTimeout(() => elements.toast.classList.remove("show"), 2600);
}

function setAgentBanner({ eyebrow, title, message, running = false }) {
  if (eyebrow) {
    elements.agentEyebrow.textContent = eyebrow;
  }
  if (title) {
    elements.agentTitle.textContent = title;
  }
  elements.agentStream.classList.toggle("running", running);
  if (message !== undefined) {
    typeAgentMessage(message, running);
  }
}

function typeAgentMessage(message, running = false) {
  window.clearInterval(appState.typeTimer);
  elements.agentStream.textContent = "";
  const text = String(message || "");
  let index = 0;

  appState.typeTimer = window.setInterval(() => {
    elements.agentStream.textContent = text.slice(0, index);
    index += 1;
    if (index > text.length) {
      window.clearInterval(appState.typeTimer);
      if (!running) {
        elements.agentStream.classList.remove("running");
      }
    }
  }, 22);
}

function startAgentRun({ agent, stage, title, messages }) {
  window.clearInterval(appState.agentTimer);
  window.clearInterval(appState.typeTimer);
  updateStage(stage);

  let index = 0;
  setAgentBanner({
    eyebrow: `${agent} Agent 运行中`,
    title,
    message: messages[index],
    running: true,
  });

  appState.agentTimer = window.setInterval(() => {
    index = (index + 1) % messages.length;
    setAgentBanner({
      eyebrow: `${agent} Agent 运行中`,
      title,
      message: messages[index],
      running: true,
    });
  }, 2600);
}

function finishAgentRun({ agent, stage, title, message }) {
  window.clearInterval(appState.agentTimer);
  updateStage(stage);
  setAgentBanner({
    eyebrow: `${agent} Agent 已完成`,
    title,
    message,
    running: false,
  });
}

function failAgentRun({ agent, title, message }) {
  window.clearInterval(appState.agentTimer);
  setAgentBanner({
    eyebrow: `${agent} Agent 提醒`,
    title,
    message,
    running: false,
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setLoading(button, isLoading, text) {
  if (!button.dataset.idleText) {
    button.dataset.idleText = button.textContent;
  }
  button.disabled = isLoading;
  button.textContent = isLoading ? text : button.dataset.idleText;
}

function autoResizeTextarea(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 220)}px`;
}

function bindAutoResize(scope = document) {
  scope.querySelectorAll("textarea").forEach((textarea) => {
    autoResizeTextarea(textarea);
    textarea.addEventListener("input", () => autoResizeTextarea(textarea));
  });
}

function switchView(viewName) {
  $$(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `${viewName}View`);
  });

  $$(".nav-card, .sub-nav-card, .stage-nav-card").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewName);
  });
}

function toggleSidebar() {
  const collapsed = elements.appShell.classList.toggle("sidebar-collapsed");
  elements.sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
  elements.sidebarToggle.setAttribute("aria-label", collapsed ? "展开侧边栏" : "折叠侧边栏");
}

function setStageSidebarCollapsed(collapsed) {
  appState.stageSidebarCollapsed = collapsed;
  $$(".stage-sidebar").forEach((sidebar) => {
    sidebar.classList.toggle("collapsed", collapsed);
  });
  $$(".stage-collapse-btn").forEach((button) => {
    button.setAttribute("aria-expanded", String(!collapsed));
    button.setAttribute("aria-label", collapsed ? "展开创作阶段导航" : "折叠创作阶段导航");
  });
}

function toggleStageSidebar() {
  setStageSidebarCollapsed(!appState.stageSidebarCollapsed);
}

function setReviewDecision(decision) {
  appState.reviewDecision = decision;
  elements.approveDecisionBtn.classList.toggle("active", decision === "approved");
  elements.rejectDecisionBtn.classList.toggle("active", decision === "rejected");
  elements.approveBtn.textContent = decision === "approved" ? "提交审核并继续生成" : "打回并保留修改意见";
}

function countChineseWords(text) {
  const compact = String(text || "").replace(/\s/g, "");
  return compact.length;
}

function syncProject(project) {
  appState.project = project || appState.project;
  if (!appState.project) {
    return;
  }
  appState.projectId = appState.project.project_id || "default";
  if (appState.project.title && appState.project.title !== "未命名作品" && !elements.projectTitle.value) {
    elements.projectTitle.value = appState.project.title;
  }
  if (appState.project.global_worldview && !elements.worldview.value) {
    elements.worldview.value = appState.project.global_worldview;
  }
  renderChapterCatalog();
  updateOverview();
}

function updateOverview() {
  const draftContent = appState.draft?.content || "";
  const chapterNumber = Number(elements.chapter.value || appState.draft?.chapter_number || 1);
  const wordCount = appState.project?.total_word_count || countChineseWords(draftContent);

  elements.wordCountStat.textContent = String(wordCount);
  elements.projectStat.textContent = appState.project?.title || "默认作品";
  elements.chapterStat.textContent = `第 ${chapterNumber} 章`;
  elements.sessionStat.textContent = appState.sessionId
    ? `Session: ${appState.sessionId.slice(0, 8)}...`
    : "尚未创建会话";
  elements.progressStat.textContent = stageText[appState.stage] || "未开始";
  elements.beatsStat.textContent = `${appState.plotBeats.length} 个剧情节点`;
  elements.reviewStat.textContent = appState.draft?.status || "待生成";

  elements.previewTitle.textContent = appState.draft?.title || `第 ${chapterNumber} 章`;
  elements.previewContent.textContent =
    draftContent ||
    "这里会像正式小说阅读页一样展示已经生成的正文。完成一次章节生成后，内容会自动同步到这里。";
}

function renderChapterCatalog() {
  const chapters = appState.project?.chapters || [];
  if (!chapters.length) {
    elements.chapterCatalog.className = "chapter-catalog-empty";
    elements.chapterCatalog.textContent =
      "接受章节后，这里会形成作品目录。你可以切换已生成章节，也可以从上一章摘要继续规划下一章。";
    return;
  }

  elements.chapterCatalog.className = "chapter-catalog";
  elements.chapterCatalog.innerHTML = chapters
    .map((chapter) => {
      const isActive = Number(elements.chapter.value || 1) === chapter.chapter_number;
      const status = stageText[chapter.status] || {
        planned: "已规划",
        drafted: "已成稿",
        reviewed: "已审查",
        needs_revision: "需修改",
        approved: "已接受",
        completed: "已完成",
        failed: "失败",
      }[chapter.status] || chapter.status;
      return `
        <button class="chapter-record ${isActive ? "active" : ""}" type="button" data-chapter-number="${chapter.chapter_number}">
          <span>第 ${chapter.chapter_number} 章</span>
          <strong>${escapeHtml(chapter.title || "未命名章节")}</strong>
          <small>${escapeHtml(status)} · ${chapter.word_count || 0} 字</small>
        </button>
      `;
    })
    .join("");
}

function chapterStatusToStage(status) {
  return {
    planned: "awaiting_human_review",
    drafted: "awaiting_review",
    reviewed: "awaiting_chapter_acceptance",
    needs_revision: "awaiting_revision_decision",
    approved: "awaiting_chapter_acceptance",
    completed: "completed",
    failed: "failed",
  }[status] || "planning";
}

function renderMemoryPanels() {
  renderCharacterCards(appState.characterUpdates);
  renderLoreFishbone(appState.loreUpdates);
}

function localizeLoreKey(key) {
  const rawKey = String(key || "").trim();
  if (!rawKey) {
    return "未命名设定";
  }

  const chapterSummary = rawKey.match(/^chapter[_-]?(\d+)[_-]?summary$/i);
  if (chapterSummary) {
    return `第 ${chapterSummary[1]} 章摘要`;
  }

  const dictionaries = {
    global: "全局",
    lore: "设定",
    worldview: "世界观",
    chapter: "章节",
    summary: "摘要",
    item: "道具",
    prop: "道具",
    object: "物品",
    location: "地点",
    place: "地点",
    scene: "场景",
    city: "城市",
    school: "学校",
    classroom: "教室",
    home: "家",
    house: "宅邸",
    old: "旧",
    family: "家族",
    study: "书房",
    room: "房间",
    forbidden: "禁区",
    zone: "区域",
    coordinate: "坐标",
    coordinates: "坐标",
    clue: "线索",
    foreshadow: "伏笔",
    secret: "秘密",
    relation: "关系",
    relationship: "关系",
    character: "人物",
    bronze: "青铜",
    key: "钥匙",
    letter: "信件",
    moonlight: "月光",
    father: "父亲",
    spirit: "灵气",
    revival: "复苏",
    night: "夜晚",
    forest: "森林",
    gate: "门",
  };

  const normalized = rawKey
    .replace(/([a-z])([A-Z])/g, "$1_$2")
    .replace(/[^a-zA-Z0-9\u4e00-\u9fa5]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
  const parts = normalized.split("_").filter(Boolean);
  if (!parts.length) {
    return rawKey;
  }

  const translated = parts.map((part) => dictionaries[part] || part).join("");
  if (/^[a-z0-9_ -]+$/i.test(rawKey)) {
    return translated;
  }
  return rawKey;
}

function renderCharacterCards(characters) {
  const entries = Object.values(characters || {});
  if (!entries.length) {
    elements.characterCards.className = "character-empty";
    elements.characterCards.textContent = "Librarian 抽取到人物变化后，会在这里以游戏角色卡形式展示。";
    return;
  }

  elements.characterCards.className = "character-grid";
  elements.characterCards.innerHTML = entries
    .map((character) => {
      const name = character.name || "未命名角色";
      const avatar = escapeHtml(name.slice(0, 1));
      return `
        <article class="character-card">
          <div class="character-avatar">${avatar}</div>
          <h3>${escapeHtml(name)}</h3>
          <span class="character-role">${escapeHtml(character.role || "unknown")}</span>
          <p class="character-profile">${escapeHtml(character.profile || "暂无角色简介。")}</p>
          <div class="character-state">
            <span>心理状态：${escapeHtml(character.current_psychological_state || "未记录")}</span>
            <span>物理状态：${escapeHtml(character.current_physical_state || "未记录")}</span>
            <span>当前位置：${escapeHtml(character.current_location || "未记录")}</span>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderLoreFishbone(loreUpdates) {
  const entries = Object.entries(loreUpdates || {});
  if (!entries.length) {
    elements.loreFishbone.className = "fishbone-empty";
    elements.loreFishbone.textContent = "章节生成后，世界观增量、道具、地点、伏笔会沿剧情线展示。";
    return;
  }

  elements.loreFishbone.className = "fishbone";
  elements.loreFishbone.innerHTML = entries
    .map(
      ([key, value], index) => `
        <div class="fishbone-item">
          <span class="fishbone-dot">${index + 1}</span>
          <article class="fishbone-card">
            <h3>${escapeHtml(localizeLoreKey(key))}</h3>
            <p>${escapeHtml(value)}</p>
          </article>
        </div>
      `,
    )
    .join("");
}

function updateStage(stage) {
  const normalized = stage || "planning";
  const activeIndex = stageStepIndex[normalized] ?? stageOrder.indexOf(normalized);

  appState.stage = normalized;
  elements.stageLabel.textContent = stageText[normalized] || normalized || "未开始";
  document.querySelector(".status-dot").classList.toggle("done", normalized === "completed");

  $$(".step").forEach((step, index) => {
    step.classList.remove("active", "done");
    if (activeIndex === -1) {
      return;
    }
    if (index < activeIndex) {
      step.classList.add("done");
    }
    if (index === activeIndex) {
      step.classList.add("active");
    }
  });

  updateOverview();
}

function clearRevisionCountdown() {
  window.clearInterval(appState.revisionTimer);
  appState.revisionTimer = null;
  appState.revisionCountdown = 10;
  elements.revisionCountdown.classList.add("is-hidden");
}

function setDecisionPanel(mode) {
  clearRevisionCountdown();
  elements.chapterDecisionPanel.classList.toggle("is-hidden", !mode);
  elements.acceptChapterBtn.classList.add("is-hidden");
  elements.reviseNowBtn.classList.add("is-hidden");
  elements.waitRevisionBtn.classList.add("is-hidden");
  elements.confirmReviseBtn.classList.add("is-hidden");

  if (!mode) {
    return;
  }

  if (mode === "accept") {
    elements.decisionTitle.textContent = "Reviewer 审查通过";
    elements.decisionMessage.textContent = "当前章节可以接受。接受后才会交给 Librarian 抽取人物、地点、道具和伏笔设定。";
    elements.acceptChapterBtn.classList.remove("is-hidden");
    return;
  }

  elements.decisionTitle.textContent = "Reviewer 建议修改";
  elements.decisionMessage.textContent = "系统会在倒计时结束后自动同意修改。你也可以立即修改、先暂停等待，或直接接受本章节。";
  elements.acceptChapterBtn.classList.remove("is-hidden");
  elements.reviseNowBtn.classList.remove("is-hidden");
  elements.waitRevisionBtn.classList.remove("is-hidden");
  startRevisionCountdown();
}

function holdRevisionDecision() {
  clearRevisionCountdown();
  elements.decisionTitle.textContent = "已暂停自动修改";
  elements.decisionMessage.textContent = "当前章节停在审查结果处。你可以接受本章节，或重新确认打回 Writer 修改。";
  elements.acceptChapterBtn.classList.remove("is-hidden");
  elements.reviseNowBtn.classList.add("is-hidden");
  elements.waitRevisionBtn.classList.add("is-hidden");
  elements.confirmReviseBtn.classList.remove("is-hidden");
}

function startRevisionCountdown() {
  clearRevisionCountdown();
  appState.revisionCountdown = 10;
  elements.revisionCountdown.classList.remove("is-hidden");
  elements.revisionCountdown.textContent = `${appState.revisionCountdown} 秒后自动同意修改`;

  appState.revisionTimer = window.setInterval(() => {
    appState.revisionCountdown -= 1;
    elements.revisionCountdown.textContent = `${appState.revisionCountdown} 秒后自动同意修改`;
    if (appState.revisionCountdown <= 0) {
      clearRevisionCountdown();
      reviseDraft("倒计时结束，自动同意 Writer 按 Reviewer 意见修订。");
    }
  }, 1000);
}

function getRoleLabel(role) {
  return characterRoleOptions.find((option) => option.value === role)?.label || "暂未确定";
}

function createEmptyCharacter() {
  return {
    name: "",
    role: "unknown",
    profile: "",
    motivation: "",
    current_psychological_state: "",
    current_physical_state: "",
    current_location: "",
  };
}

function syncCharacterForms() {
  $$(".character-form-card").forEach((card) => {
    const index = Number(card.dataset.index || 0);
    const read = (field) => card.querySelector(`[data-character-field="${field}"]`)?.value.trim() || "";
    appState.characters[index] = {
      ...appState.characters[index],
      name: read("name"),
      role: read("role") || "unknown",
      profile: read("profile"),
      motivation: read("motivation"),
      current_psychological_state: read("current_psychological_state"),
      current_physical_state: read("current_physical_state"),
      current_location: read("current_location"),
    };
  });
}

function renderCharacterForms() {
  if (!appState.characters.length) {
    elements.charactersBuilder.innerHTML = `
      <div class="form-empty">
        暂未添加人物。可以直接生成剧情，也可以先添加主角、配角或反派来约束人设。
      </div>
    `;
    return;
  }

  elements.charactersBuilder.innerHTML = appState.characters
    .map((character, index) => {
      const roleOptions = characterRoleOptions
        .map(
          (option) => `
            <option value="${option.value}" ${character.role === option.value ? "selected" : ""}>
              ${option.label}
            </option>
          `,
        )
        .join("");

      return `
        <article class="character-form-card" data-index="${index}">
          <div class="character-form-head">
            <span class="character-form-index">${index + 1}</span>
            <div>
              <strong>${escapeHtml(character.name || `人物 ${index + 1}`)}</strong>
              <small>${escapeHtml(getRoleLabel(character.role))}</small>
            </div>
            <button class="ghost-btn compact remove-character-btn" type="button" data-index="${index}">删除</button>
          </div>
          <div class="two-col">
            <label>
              角色姓名
              <input data-character-field="name" type="text" value="${escapeHtml(character.name)}" placeholder="例如：林澈" />
            </label>
            <label>
              叙事定位
              <select data-character-field="role">${roleOptions}</select>
            </label>
          </div>
          <label>
            角色简介
            <textarea data-character-field="profile" rows="2" placeholder="例如：隐忍、敏锐，习惯先观察再行动。">${escapeHtml(character.profile)}</textarea>
          </label>
          <label>
            当前动机
            <textarea data-character-field="motivation" rows="2" placeholder="例如：查清父亲失踪真相。">${escapeHtml(character.motivation)}</textarea>
          </label>
          <div class="two-col">
            <label>
              心理状态
              <input data-character-field="current_psychological_state" type="text" value="${escapeHtml(character.current_psychological_state)}" placeholder="例如：怀疑、警惕" />
            </label>
            <label>
              身体状态
              <input data-character-field="current_physical_state" type="text" value="${escapeHtml(character.current_physical_state)}" placeholder="例如：疲惫、轻伤" />
            </label>
          </div>
          <label>
            当前位置
            <input data-character-field="current_location" type="text" value="${escapeHtml(character.current_location)}" placeholder="例如：旧宅书房" />
          </label>
        </article>
      `;
    })
    .join("");

  bindAutoResize(elements.charactersBuilder);
}

function collectCharacters() {
  syncCharacterForms();
  return appState.characters
    .map((character) => ({
      name: character.name,
      role: character.role || "unknown",
      profile: character.profile,
      motivation: character.motivation || null,
      current_psychological_state: character.current_psychological_state || "未记录",
      current_physical_state: character.current_physical_state || "未记录",
      current_location: character.current_location || null,
    }))
    .filter((character) => {
      const hasAnyInput = [
        character.name,
        character.profile,
        character.motivation,
        character.current_location,
      ].some(Boolean);
      if (!hasAnyInput) {
        return false;
      }
      if (!character.name || !character.profile) {
        throw new Error("人物卡片至少需要填写“角色姓名”和“角色简介”。");
      }
      return true;
    });
}

function addCharacter(character = createEmptyCharacter()) {
  syncCharacterForms();
  appState.characters.push(character);
  renderCharacterForms();
}

function removeCharacter(index) {
  syncCharacterForms();
  appState.characters.splice(index, 1);
  renderCharacterForms();
}

function renderMetaMessage(message) {
  elements.metaOutput.className = "output-box meta-panel";
  elements.metaOutput.innerHTML = `
    <div class="form-empty">${escapeHtml(message || "设定管理员与审稿人的结果会显示在这里。")}</div>
  `;
}

function renderListBlock(title, items, emptyText) {
  const list = (items || []).filter(Boolean);
  return `
    <section class="meta-card">
      <h3>${escapeHtml(title)}</h3>
      ${
        list.length
          ? `<ul>${list.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
          : `<p>${escapeHtml(emptyText)}</p>`
      }
    </section>
  `;
}

function renderKeyValueBlock(title, entries, emptyText, options = {}) {
  const formatKey = options.formatKey || ((key) => key);
  return `
    <section class="meta-card">
      <h3>${escapeHtml(title)}</h3>
      ${
        entries.length
          ? `<div class="meta-kv-list">${entries
              .map(
                ([key, value]) => `
                  <div class="meta-kv">
                    <strong>${escapeHtml(formatKey(key))}</strong>
                    <span>${escapeHtml(value)}</span>
                  </div>
                `,
              )
              .join("")}</div>`
          : `<p>${escapeHtml(emptyText)}</p>`
      }
    </section>
  `;
}

function renderMetaPanel(data) {
  const draft = data.draft || {};
  const loreEntries = Object.entries(data.extracted_lore_updates || {});
  const characterEntries = Object.values(data.extracted_character_updates || {}).map((character) => [
    character.name || "未命名角色",
    character.profile || "暂无角色简介。",
  ]);

  elements.metaOutput.className = "output-box meta-panel";
  elements.metaOutput.innerHTML = `
    <section class="meta-summary">
      <div>
        <span>草稿状态</span>
        <strong>${escapeHtml(stageText[data.current_stage] || data.current_stage || "未知")}</strong>
      </div>
      <div>
        <span>章节评分</span>
        <strong>${draft.quality_score ?? "待评分"}</strong>
      </div>
      <div>
        <span>审查结论</span>
        <strong>${escapeHtml(draft.status === "needs_revision" ? "需要修改" : "已通过")}</strong>
      </div>
    </section>
    ${renderListBlock("Reviewer 审查意见", data.review_feedback, "未发现明显问题。")}
    ${renderListBlock("修改建议", draft.revision_notes, "暂无修改建议。")}
    ${renderKeyValueBlock("Librarian 设定增量", loreEntries, "暂无新的世界观、道具、地点或伏笔。", {
      formatKey: localizeLoreKey,
    })}
    ${renderKeyValueBlock("人物状态更新", characterEntries, "暂无人物卡片更新。")}
  `;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail || `请求失败：${response.status}`;
    throw new Error(Array.isArray(detail) ? JSON.stringify(detail, null, 2) : detail);
  }
  return data;
}

async function loadProject(projectId = appState.projectId) {
  const endpoint = projectId && projectId !== "default" ? `/novel/projects/${projectId}` : "/novel/projects/current";
  const data = await requestJson(endpoint);
  syncProject(data.project);
  return data.project;
}

function selectChapter(chapterNumber) {
  const chapter = (appState.project?.chapters || []).find(
    (item) => item.chapter_number === chapterNumber,
  );
  if (!chapter) {
    return;
  }

  elements.chapter.value = String(chapter.chapter_number);
  elements.summary.value = chapter.summary || elements.summary.value;
  if (chapter.session_id) {
    updateSession(chapter.session_id);
    elements.session.value = chapter.session_id;
  }
  if (chapter.draft) {
    appState.draft = chapter.draft;
    appState.plotBeats = chapter.draft.plot_beats || [];
    elements.draftOutput.textContent = chapter.draft.content || "草稿为空。";
    renderBeats(appState.plotBeats);
    renderMetaMessage(`已切换到第 ${chapter.chapter_number} 章目录记录。`);
  }
  updateStage(chapterStatusToStage(chapter.status));
  renderChapterCatalog();
  updateOverview();
  switchView(chapter.draft ? "studioDraft" : "studioPlan");
}

function renderBeats(beats) {
  appState.plotBeats = beats || [];
  appState.activeBeatIndex = 0;

  if (!appState.plotBeats.length) {
    elements.beatsContainer.className = "beats-empty";
    elements.beatsContainer.textContent = "暂无剧情节点。请先生成 Planner 输出。";
    elements.approveBtn.disabled = true;
    updateOverview();
    return;
  }

  elements.beatsContainer.className = "";
  renderActiveBeat();

  elements.approveBtn.disabled = false;
  updateOverview();
}

function renderActiveBeat() {
  const beat = appState.plotBeats[appState.activeBeatIndex];
  if (!beat) {
    return;
  }

  const tabs = appState.plotBeats
    .map(
      (item, index) => `
        <button class="beat-tab ${index === appState.activeBeatIndex ? "active" : ""}" type="button" data-index="${index}">
          节点 ${item.order || index + 1}
        </button>
      `,
    )
    .join("");

  elements.beatsContainer.innerHTML = `
    <div class="beat-tabs">${tabs}</div>
    <div class="beat-card" data-index="${appState.activeBeatIndex}">
      <div class="beat-head">
        <span class="beat-index">${beat.order || appState.activeBeatIndex + 1}</span>
        <div>
          <strong>剧情节点 ${beat.order || appState.activeBeatIndex + 1}</strong>
          <p class="beat-summary-line">${escapeHtml((beat.summary || "").slice(0, 48))}${(beat.summary || "").length > 48 ? "..." : ""}</p>
        </div>
      </div>
      <label>
        节点摘要
        <textarea data-field="summary" rows="3">${escapeHtml(beat.summary)}</textarea>
      </label>
      <label>
        叙事目的
        <textarea data-field="purpose" rows="2">${escapeHtml(beat.purpose)}</textarea>
      </label>
      <label>
        冲突
        <textarea data-field="conflict" rows="2">${escapeHtml(beat.conflict)}</textarea>
      </label>
      <label>
        预期结果
        <textarea data-field="expected_outcome" rows="2">${escapeHtml(beat.expected_outcome)}</textarea>
      </label>
      <div class="small-grid">
        <label>
          地点
          <textarea data-field="location" rows="1">${escapeHtml(beat.location)}</textarea>
        </label>
        <label>
          出场人物（逗号分隔）
          <textarea data-field="involved_characters" rows="1">${escapeHtml((beat.involved_characters || []).join(", "))}</textarea>
        </label>
      </div>
      <label>
        连续性约束（逗号分隔）
        <textarea data-field="continuity_constraints" rows="2">${escapeHtml((beat.continuity_constraints || []).join(", "))}</textarea>
      </label>
    </div>
  `;

  bindAutoResize(elements.beatsContainer);
}

function saveActiveBeatEdits() {
  const card = elements.beatsContainer.querySelector(".beat-card");
  const beat = appState.plotBeats[appState.activeBeatIndex];
  if (!card || !beat) {
    return;
  }

  const read = (field) => card.querySelector(`[data-field="${field}"]`)?.value.trim() || "";
  const readList = (field) =>
    read(field)
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

  appState.plotBeats[appState.activeBeatIndex] = {
    ...beat,
    summary: read("summary"),
    purpose: read("purpose") || null,
    location: read("location") || null,
    conflict: read("conflict") || null,
    expected_outcome: read("expected_outcome") || null,
    involved_characters: readList("involved_characters"),
    continuity_constraints: readList("continuity_constraints"),
  };
}

function collectEditedBeats() {
  saveActiveBeatEdits();
  return appState.plotBeats.map((beat, index) => {
    return {
      ...beat,
      order: beat.order || index + 1,
    };
  });
}

function updateSession(sessionId) {
  appState.sessionId = sessionId || "";
  if (appState.sessionId) {
    elements.session.value = appState.sessionId;
  }
  elements.sessionBadge.textContent = appState.sessionId
    ? `Session: ${appState.sessionId}`
    : "尚未创建会话";
  updateOverview();
}

function renderRunResult(data) {
  if (data.session_id) {
    updateSession(data.session_id);
  }

  appState.draft = data.draft || appState.draft;
  appState.loreUpdates = data.extracted_lore_updates || appState.loreUpdates || {};
  appState.characterUpdates = data.extracted_character_updates || appState.characterUpdates || {};
  updateStage(data.current_stage);

  if (data.draft) {
    elements.draftOutput.textContent = data.draft.content || "草稿为空。";
    renderMetaPanel(data);
  } else {
    renderMetaMessage(data.message || "已读取当前会话状态。");
  }

  renderMemoryPanels();
  if (data.current_stage === "awaiting_revision_decision") {
    setDecisionPanel("revision");
  } else if (data.current_stage === "awaiting_chapter_acceptance") {
    setDecisionPanel("accept");
  } else {
    setDecisionPanel(null);
  }
  updateOverview();
}

async function planChapter() {
  try {
    setLoading(elements.planBtn, true, "Planner 生成中...");
    startAgentRun({
      agent: "Planner",
      stage: "planning",
      title: "Planner 正在推演本章剧情节点",
      messages: [
        "正在读取世界观、前文摘要和人物卡片，整理本章必须遵守的连续性约束。",
        "正在拆解章节目标：开场承接、冲突升级、悬念收束。",
        "正在生成可供人工审核的剧情节点，尽量避免角色 OOC 和逻辑跳跃。",
      ],
    });
    const payload = {
      session_id: elements.session.value.trim() || null,
      project_id: appState.projectId,
      project_title: elements.projectTitle.value.trim() || null,
      global_worldview: elements.worldview.value.trim(),
      chapter_number: Number(elements.chapter.value || 1),
      previous_summary: elements.summary.value.trim() || null,
      user_instruction: elements.instruction.value.trim() || null,
      characters: collectCharacters(),
    };

    const data = await requestJson("/novel/chapters/plan", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    appState.draft = null;
    appState.loreUpdates = {};
    appState.characterUpdates = {};
    setDecisionPanel(null);
    updateSession(data.session_id);
    updateStage(data.current_stage);
    renderBeats(data.plot_beats);
    elements.draftOutput.textContent = "剧情节点已生成。请审核并提交后继续生成正文。";
    renderMetaMessage(data.message);
    renderMemoryPanels();
    await loadProject();
    switchView("studioReview");
    finishAgentRun({
      agent: "Planner",
      stage: data.current_stage,
      title: "Planner 已完成剧情节点规划",
      message: "剧情节点已生成。请在左侧审核每个节点，确认后交给 Writer 扩写正文。",
    });
    showToast("Planner 已生成剧情节点，等待人工审核。");
  } catch (error) {
    failAgentRun({
      agent: "Planner",
      title: "Planner 生成时遇到问题",
      message: error.message,
    });
    showToast(error.message);
  } finally {
    setLoading(elements.planBtn, false);
  }
}

async function approvePlan() {
  if (!appState.sessionId) {
    showToast("请先生成剧情节点。");
    return;
  }

  if (appState.reviewDecision === "rejected") {
    saveActiveBeatEdits();
    renderMetaMessage(elements.feedback.value.trim() || "已打回剧情节点，请修改节点后再提交，或重新生成 Planner 输出。");
    showToast("已打回剧情节点。请修改节点或重新生成 Planner 输出。");
    return;
  }

  try {
    setLoading(elements.approveBtn, true, "状态机流转中...");
    startAgentRun({
      agent: "Writer",
      stage: "writing",
      title: "Writer 正在扩写章节正文",
      messages: [
        "正在读取你确认后的剧情节点，把节点转成连续的正文段落。",
        "正在保持人物动机、冲突推进和章节钩子，避免只复述大纲。",
        "正文完成后会先展示到页面，再交给 Reviewer 单独审查。",
      ],
    });
    const data = await requestJson(`/novel/chapters/${appState.sessionId}/approve`, {
      method: "POST",
      body: JSON.stringify({
        plot_beats: collectEditedBeats(),
        human_feedback: elements.feedback.value.trim() || "同意当前剧情节点。",
      }),
    });

    renderRunResult(data);
    switchView("studioDraft");
    finishAgentRun({
      agent: "Writer",
      stage: data.current_stage,
      title: "Writer 已生成章节正文",
      message: "正文已先展示到页面。接下来 Reviewer 会单独审查本章是否需要修改。",
    });
    showToast("Writer 已生成正文，开始 Reviewer 审查。");
    await reviewDraft();
  } catch (error) {
    failAgentRun({
      agent: "Writer",
      title: "章节生成时遇到问题",
      message: error.message,
    });
    showToast(error.message);
  } finally {
    setLoading(elements.approveBtn, false);
  }
}

async function reviewDraft() {
  if (!appState.sessionId) {
    showToast("暂无可审查的会话。");
    return;
  }

  try {
    startAgentRun({
      agent: "Reviewer",
      stage: "reviewing",
      title: "Reviewer 正在审查章节草稿",
      messages: [
        "正在检查人物行为是否 OOC，尤其关注动机和当前状态是否一致。",
        "正在核对剧情节点、世界观设定和正文细节，寻找逻辑断裂或设定冲突。",
        "正在整理可执行的修改建议，如果问题较轻也会允许你直接接受本章。",
      ],
    });

    const data = await requestJson(`/novel/chapters/${appState.sessionId}/review`, {
      method: "POST",
    });
    renderRunResult(data);
    await loadProject();
    finishAgentRun({
      agent: "Reviewer",
      stage: data.current_stage,
      title: data.current_stage === "awaiting_revision_decision" ? "Reviewer 建议修订" : "Reviewer 审查通过",
      message: data.current_stage === "awaiting_revision_decision"
        ? "审查发现需要处理的问题。你可以等待 10 秒自动同意修改，也可以手动选择下一步。"
        : "审查未发现必须修改的问题。接受本章节后，Librarian 才会抽取设定。",
    });
  } catch (error) {
    failAgentRun({
      agent: "Reviewer",
      title: "Reviewer 审查时遇到问题",
      message: error.message,
    });
    showToast(error.message);
  }
}

async function reviseDraft(reason = "用户同意 Writer 按 Reviewer 意见修订。") {
  if (!appState.sessionId) {
    showToast("暂无可修订的会话。");
    return;
  }

  try {
    clearRevisionCountdown();
    setLoading(elements.reviseNowBtn, true, "修稿中...");
    setLoading(elements.confirmReviseBtn, true, "修稿中...");
    startAgentRun({
      agent: "Writer",
      stage: "revising",
      title: "Writer 正在根据审查意见修订",
      messages: [
        "正在读取 Reviewer 的审查意见，保留通过的剧情结构。",
        "正在修正人物动机、逻辑衔接和设定冲突。",
        "修订版生成后会再次交给 Reviewer 审查。",
      ],
    });

    const data = await requestJson(`/novel/chapters/${appState.sessionId}/revise`, {
      method: "POST",
      body: JSON.stringify({
        human_feedback: reason,
      }),
    });
    renderRunResult(data);
    finishAgentRun({
      agent: "Writer",
      stage: data.current_stage,
      title: "Writer 已生成修订版",
      message: "修订版正文已更新到页面。接下来 Reviewer 会再次审查。",
    });
    await reviewDraft();
  } catch (error) {
    failAgentRun({
      agent: "Writer",
      title: "Writer 修稿时遇到问题",
      message: error.message,
    });
    showToast(error.message);
  } finally {
    setLoading(elements.reviseNowBtn, false);
    setLoading(elements.confirmReviseBtn, false);
  }
}

async function acceptChapter() {
  if (!appState.sessionId) {
    showToast("暂无可接受的会话。");
    return;
  }

  try {
    clearRevisionCountdown();
    setLoading(elements.acceptChapterBtn, true, "抽取设定中...");
    startAgentRun({
      agent: "Librarian",
      stage: "extracting_lore",
      title: "Librarian 正在抽取设定",
      messages: [
        "正在从你接受的章节中抽取稳定事实，而不是临时猜测。",
        "正在整理人物状态、地点、道具、伏笔和章节摘要。",
        "设定抽取完成后，本章节才会进入完成状态。",
      ],
    });

    const data = await requestJson(`/novel/chapters/${appState.sessionId}/accept`, {
      method: "POST",
      body: JSON.stringify({
        human_feedback: elements.feedback.value.trim() || "用户接受本章节。",
      }),
    });
    renderRunResult(data);
    await loadProject();
    finishAgentRun({
      agent: "Librarian",
      stage: data.current_stage,
      title: "章节已完成",
      message: "本章节已被接受，设定增量也已抽取到人物设定和剧情设定页面。",
    });
    showToast("章节已接受并完成设定抽取。");
  } catch (error) {
    failAgentRun({
      agent: "Librarian",
      title: "设定抽取时遇到问题",
      message: error.message,
    });
    showToast(error.message);
  } finally {
    setLoading(elements.acceptChapterBtn, false);
  }
}

async function continueNextChapter() {
  try {
    syncCharacterForms();
    setLoading(elements.continueNextBtn, true, "规划下一章...");
    startAgentRun({
      agent: "Planner",
      stage: "planning",
      title: "Planner 正在承接上一章继续规划",
      messages: [
        "正在读取作品目录和最近完成章节摘要，整理下一章承接点。",
        "正在把未解决冲突和新的章节目标合并成剧情节点。",
        "正在生成下一章 Planner 输出，稍后进入人工审核。",
      ],
    });

    const data = await requestJson(`/novel/projects/${appState.projectId}/chapters/next`, {
      method: "POST",
      body: JSON.stringify({
        session_id: null,
        user_instruction: elements.instruction.value.trim() || null,
        characters: collectCharacters(),
      }),
    });

    appState.draft = null;
    appState.loreUpdates = {};
    appState.characterUpdates = {};
    elements.chapter.value = String(data.plot_beats?.[0]?.chapter_number || Number(elements.chapter.value || 0) + 1);
    setDecisionPanel(null);
    updateSession(data.session_id);
    updateStage(data.current_stage);
    renderBeats(data.plot_beats);
    elements.draftOutput.textContent = "下一章剧情节点已生成。请审核并提交后继续生成正文。";
    renderMetaMessage(data.message);
    renderMemoryPanels();
    await loadProject();
    const plannedChapter = appState.project?.chapters?.find((chapter) => chapter.session_id === data.session_id);
    if (plannedChapter) {
      elements.chapter.value = String(plannedChapter.chapter_number);
      elements.summary.value = plannedChapter.summary || elements.summary.value;
    }
    switchView("studioReview");
    finishAgentRun({
      agent: "Planner",
      stage: data.current_stage,
      title: "下一章剧情节点已生成",
      message: "目录已追加新的章节记录。请审核剧情节点后继续生成正文。",
    });
    showToast("已开始规划下一章。");
  } catch (error) {
    failAgentRun({
      agent: "Planner",
      title: "继续写下一章时遇到问题",
      message: error.message,
    });
    showToast(error.message);
  } finally {
    setLoading(elements.continueNextBtn, false);
  }
}

async function refreshState() {
  if (!appState.sessionId) {
    showToast("暂无可刷新的会话。");
    return;
  }

  try {
    const data = await requestJson(`/novel/sessions/${appState.sessionId}`);
    renderRunResult(data);
    await loadProject();
    showToast("状态已刷新。");
  } catch (error) {
    showToast(error.message);
  }
}

function fillExample() {
  elements.projectTitle.value = "月光禁区";
  elements.worldview.value =
    "玄幻都市，灵气复苏刚刚开始。主角林澈出身没落修行世家，家族旧宅里藏着一枚会回应月光的青铜钥匙。";
  elements.chapter.value = "1";
  elements.summary.value = "故事开篇前，林澈收到一封没有寄件人的信，信中提到父亲失踪当夜的禁区坐标。";
  elements.instruction.value = "本章要突出神秘感，结尾让主角发现钥匙和禁区产生共鸣。";
  appState.characters = [
    {
      name: "林澈",
      role: "protagonist",
      profile: "隐忍、敏锐，习惯先观察再行动的少年。",
      motivation: "查清父亲失踪当夜的真相。",
      current_psychological_state: "警惕但被好奇心推动",
      current_physical_state: "普通高中生状态",
      current_location: "家族旧宅",
    },
    {
      name: "许知夏",
      role: "supporting",
      profile: "林澈的同学，表面活泼，实际知道部分禁区传闻。",
      motivation: "阻止林澈贸然进入危险区域。",
      current_psychological_state: "担心又有所隐瞒",
      current_physical_state: "状态正常",
      current_location: "学校附近",
    },
  ];
  renderCharacterForms();
  switchView("studioPlan");
  updateOverview();
  showToast("示例已填入。");
}

$$(".nav-card, .sub-nav-card, .stage-nav-card").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

elements.sidebarToggle.addEventListener("click", toggleSidebar);
document.addEventListener("click", (event) => {
  if (!event.target.closest(".stage-collapse-btn")) {
    return;
  }
  toggleStageSidebar();
});
elements.beatsContainer.addEventListener("click", (event) => {
  const tab = event.target.closest(".beat-tab");
  if (!tab) {
    return;
  }
  saveActiveBeatEdits();
  appState.activeBeatIndex = Number(tab.dataset.index || 0);
  renderActiveBeat();
});
elements.chapterCatalog.addEventListener("click", (event) => {
  const record = event.target.closest(".chapter-record");
  if (!record) {
    return;
  }
  selectChapter(Number(record.dataset.chapterNumber || 1));
});
elements.approveDecisionBtn.addEventListener("click", () => setReviewDecision("approved"));
elements.rejectDecisionBtn.addEventListener("click", () => setReviewDecision("rejected"));
elements.addCharacterBtn.addEventListener("click", () => addCharacter());
elements.charactersBuilder.addEventListener("click", (event) => {
  const removeButton = event.target.closest(".remove-character-btn");
  if (!removeButton) {
    return;
  }
  removeCharacter(Number(removeButton.dataset.index || 0));
});
elements.planBtn.addEventListener("click", planChapter);
elements.approveBtn.addEventListener("click", approvePlan);
elements.refreshBtn.addEventListener("click", refreshState);
elements.fillExampleBtn.addEventListener("click", fillExample);
elements.continueNextBtn.addEventListener("click", continueNextChapter);
elements.acceptChapterBtn.addEventListener("click", acceptChapter);
elements.reviseNowBtn.addEventListener("click", () => reviseDraft("用户立即同意 Writer 按 Reviewer 意见修订。"));
elements.waitRevisionBtn.addEventListener("click", holdRevisionDecision);
elements.confirmReviseBtn.addEventListener("click", () => reviseDraft("用户重新确认打回 Writer 修改。"));

renderCharacterForms();
renderMetaMessage();
updateStage("planning");
updateOverview();
renderMemoryPanels();
setReviewDecision("approved");
bindAutoResize();
loadProject().catch((error) => showToast(error.message));
