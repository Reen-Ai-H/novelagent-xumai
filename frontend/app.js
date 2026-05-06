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
  awaiting_chapter_acceptance: "待接受入库",
  completed: "已完成入库",
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
  projects: [],
  nextSnapshot: null,
  previewChapterNumber: 1,
  latestBatchTask: null,
  latestBatchResults: [],
  projectCodex: null,
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
  homeBtn: $("#homeBtn"),
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
  loreCodex: $("#loreCodex"),
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
  newBookTitle: $("#newBookTitleInput"),
  newBookGenre: $("#newBookGenreInput"),
  newBookWorldview: $("#newBookWorldviewInput"),
  newBookHero: $("#newBookHeroInput"),
  showNewBookBtn: $("#showNewBookBtn"),
  cancelNewBookBtn: $("#cancelNewBookBtn"),
  createBookBtn: $("#createBookBtn"),
  newBookDraftPanel: $("#newBookDraftPanel"),
  draftTitle: $("#draftTitleInput"),
  draftPremise: $("#draftPremiseInput"),
  draftWorldview: $("#draftWorldviewInput"),
  draftHero: $("#draftHeroInput"),
  confirmSettingDraftBtn: $("#confirmSettingDraftBtn"),
  refreshHomeProjectsBtn: $("#refreshHomeProjectsBtn"),
  newBookPanel: $("#newBookPanel"),
  homeProjectGrid: $("#homeProjectGrid"),
  homeProjectCount: $("#homeProjectCount"),
  premise: $("#premiseInput"),
  coreConflict: $("#coreConflictInput"),
  ending: $("#endingInput"),
  themes: $("#themesInput"),
  planNotes: $("#planNotesInput"),
  targetChapterCount: $("#targetChapterCountInput"),
  volumes: $("#volumesInput"),
  chapterPlanTable: $("#chapterPlanTable"),
  generateFullPlanBtn: $("#generateFullPlanBtn"),
  saveFullPlanBtn: $("#saveFullPlanBtn"),
  enterFirstChapterBtn: $("#enterFirstChapterBtn"),
  batchStart: $("#batchStartInput"),
  batchCount: $("#batchCountSelect"),
  batchInstruction: $("#batchInstructionInput"),
  batchPlanBtn: $("#batchPlanBtn"),
  batchGenerateBtn: $("#batchGenerateBtn"),
  batchStatusPanel: $("#batchStatusPanel"),
  batchQueuePanel: $("#batchQueuePanel"),
  batchOutlineTable: $("#batchOutlineTable"),
  nextSeedPanel: $("#nextSeedPanel"),
  readerCatalog: $("#readerCatalog"),
  previewStatus: $("#previewStatus"),
  prevChapterBtn: $("#prevChapterBtn"),
  nextChapterBtn: $("#nextChapterBtn"),
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
  const isHome = viewName === "home";
  elements.appShell.classList.toggle("home-mode", isHome);
  $$(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `${viewName}View`);
  });

  $$(".nav-card, .sub-nav-card, .stage-nav-card").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewName);
  });

  if (!isHome && !appState.project) {
    showToast("请先从首页选择或创建作品。");
    switchView("home");
    return;
  }
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

function splitListText(text) {
  return String(text || "")
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function getProjectChapters() {
  return [...(appState.project?.chapters || [])].sort((a, b) => a.chapter_number - b.chapter_number);
}

function getChapterPlans() {
  return [...(appState.project?.chapter_plans || [])].sort((a, b) => a.chapter_number - b.chapter_number);
}

function getReadableChapters() {
  return getProjectChapters().filter((chapter) => chapter.draft?.content);
}

function normalizeFullPlan() {
  return {
    premise: elements.premise.value.trim(),
    core_conflict: elements.coreConflict.value.trim(),
    ending_direction: elements.ending.value.trim(),
    themes: splitListText(elements.themes.value),
    target_chapter_count: Number(elements.targetChapterCount.value || 10),
    notes: splitListText(elements.planNotes.value),
  };
}

function parseJsonEditor(text, fallback, label) {
  const raw = String(text || "").trim();
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(`${label} JSON 格式不正确：${error.message}`);
  }
}

function getStatusLabel(status) {
  return {
    planned: "已规划",
    drafted: "草稿，不会进入长期记忆",
    awaiting_review: "待审查",
    reviewed: "AI 已审查，待人工确认",
    needs_revision: "建议修订",
    awaiting_revision_decision: "建议修订",
    awaiting_acceptance: "待接受入库",
    approved: "待接受入库",
    awaiting_chapter_acceptance: "待接受入库",
    completed: "已完成入库",
    failed: "失败",
  }[status] || stageText[status] || status || "未开始";
}

function getNextGeneratedChapterNumber(project = appState.project) {
  const chapters = project?.chapters || [];
  const usedNumbers = chapters
    .filter((chapter) => chapter.draft || chapter.session_id || chapter.status === "completed")
    .map((chapter) => Number(chapter.chapter_number || 0));
  const plannedNumbers = project?.chapter_plans?.map((plan) => Number(plan.chapter_number || 0)) || [];
  return Math.max(0, ...usedNumbers, ...plannedNumbers.filter((number) => number < 1)) + 1;
}

function hasExistingDraftInRange(start, end) {
  return getProjectChapters().some((chapter) =>
    chapter.chapter_number >= start &&
    chapter.chapter_number <= end &&
    (chapter.draft || chapter.session_id),
  );
}

function getFirstExistingDraftInRange(start, end) {
  return getProjectChapters().find((chapter) =>
    chapter.chapter_number >= start &&
    chapter.chapter_number <= end &&
    (chapter.draft || chapter.session_id),
  );
}

function getProjectBrief(project) {
  return project?.project_brief
    || project?.full_plan?.premise
    || project?.global_worldview
    || "还没有写下作品简介。";
}

function getProjectLatestChapter(project) {
  if (project?.latest_chapter_number) {
    return {
      chapter_number: project.latest_chapter_number,
      title: project.latest_chapter_title,
      status: project.latest_chapter_status,
      session_id: project.latest_session_id,
    };
  }
  return [...(project?.chapters || [])].sort((a, b) => a.chapter_number - b.chapter_number).at(-1);
}

function renderHomeProjectGrid() {
  const projects = appState.projects.length ? appState.projects : appState.project ? [appState.project] : [];
  elements.homeProjectCount.textContent = `${projects.length} 部作品`;
  if (!projects.length) {
    elements.homeProjectGrid.className = "home-project-empty";
    elements.homeProjectGrid.textContent = "暂无作品。点击“新建作品”开始第一本书。";
    return;
  }

  elements.homeProjectGrid.className = "home-project-grid";
  elements.homeProjectGrid.innerHTML = projects
    .map((project, index) => {
      const latestChapter = getProjectLatestChapter(project);
      const latestStatus = getStatusLabel(project.latest_chapter_status || latestChapter?.status);
      const updatedAt = project.updated_at ? new Date(project.updated_at).toLocaleString("zh-CN") : "未记录";
      return `
        <article class="project-card" data-project-id="${escapeHtml(project.project_id)}" style="--cover-index: ${index % 5}">
          <button class="project-card-main" type="button" data-project-action="open" data-project-id="${escapeHtml(project.project_id)}">
            <div class="project-cover">
              <span>${escapeHtml((project.title || "书").slice(0, 1))}</span>
            </div>
            <div class="project-card-body">
              <p class="eyebrow">Project</p>
              <h3>${escapeHtml(project.title || "未命名作品")}</h3>
              <p>${escapeHtml(getProjectBrief(project)).slice(0, 92)}</p>
              <div class="project-meta">
                <span>${project.total_word_count || 0} 字</span>
                <span>${project.chapter_count || 0} 章 / 完成 ${project.completed_chapter_count || 0}</span>
                <span>${escapeHtml(latestStatus)}</span>
              </div>
              <small>更新：${escapeHtml(updatedAt)}</small>
            </div>
          </button>
          <div class="project-card-actions">
            <button class="primary-btn compact" type="button" data-project-action="continue" data-project-id="${escapeHtml(project.project_id)}">继续创作</button>
            <button class="ghost-btn compact" type="button" data-project-action="preview" data-project-id="${escapeHtml(project.project_id)}">小说预览</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderFullPlanForm() {
  const fullPlan = appState.project?.full_plan || {};
  elements.premise.value = fullPlan.premise || "";
  elements.coreConflict.value = fullPlan.core_conflict || "";
  elements.ending.value = fullPlan.ending_direction || "";
  elements.themes.value = (fullPlan.themes || []).join(", ");
  elements.targetChapterCount.value = fullPlan.target_chapter_count || appState.project?.chapter_plans?.length || 10;
  elements.planNotes.value = (fullPlan.notes || []).join("\n");
  elements.volumes.value = JSON.stringify(appState.project?.volumes || [], null, 2);
  renderChapterPlanTable(elements.chapterPlanTable, getChapterPlans(), { editable: true });
  bindAutoResize(document);
}

function renderChapterPlanTable(container, plans, { editable = false } = {}) {
  if (!plans.length) {
    container.className = "chapter-plan-empty";
    container.textContent = "暂无章节规划。可以生成全文规划骨架，或到“多章节任务”里先规划 3 / 5 / 10 章。";
    return;
  }

  container.className = "chapter-plan-table";
  container.innerHTML = `
    <div class="chapter-plan-head">
      <span>章节</span>
      <span>标题</span>
      <span>摘要</span>
      <span>叙事目的</span>
    </div>
    ${plans
      .map(
        (plan, index) => `
          <div class="chapter-plan-row" data-plan-index="${index}" data-chapter-number="${plan.chapter_number}">
            <strong>第 ${plan.chapter_number} 章</strong>
            ${
              editable
                ? `<input data-plan-field="title" value="${escapeHtml(plan.title || "")}" placeholder="章节标题" />`
                : `<span>${escapeHtml(plan.title || "未命名章节")}</span>`
            }
            ${
              editable
                ? `<textarea data-plan-field="summary" rows="2">${escapeHtml(plan.summary || "")}</textarea>`
                : `<p>${escapeHtml(plan.summary || "暂无摘要。")}</p>`
            }
            ${
              editable
                ? `<textarea data-plan-field="purpose" rows="2">${escapeHtml(plan.purpose || "")}</textarea>`
                : `<p>${escapeHtml(plan.purpose || "暂无目的。")}</p>`
            }
          </div>
        `,
      )
      .join("")}
  `;
  bindAutoResize(container);
}

function collectChapterPlansFromTable(selector = "#chapterPlanTable") {
  const existing = getChapterPlans();
  return $$(`${selector} .chapter-plan-row`).map((row) => {
    const index = Number(row.dataset.planIndex || 0);
    const chapterNumber = Number(row.dataset.chapterNumber || index + 1);
    const base = existing.find((plan) => plan.chapter_number === chapterNumber) || { chapter_number: chapterNumber };
    return {
      ...base,
      title: row.querySelector('[data-plan-field="title"]')?.value.trim() || null,
      summary: row.querySelector('[data-plan-field="summary"]')?.value.trim() || "",
      purpose: row.querySelector('[data-plan-field="purpose"]')?.value.trim() || null,
    };
  });
}

function renderBatchStatus(task) {
  if (!task) {
    elements.batchStatusPanel.className = "batch-status-empty";
    elements.batchStatusPanel.textContent = "先生成章节级大纲，确认章节规划表后再批量生成草稿。";
    elements.batchQueuePanel.className = "batch-queue-empty";
    elements.batchQueuePanel.textContent = "批量生成后，这里会按章节展示待审查、需修订、待接受入库等状态。";
    renderChapterPlanTable(elements.batchOutlineTable, [], { editable: false });
    return;
  }

  elements.batchStatusPanel.className = "batch-status";
  elements.batchStatusPanel.innerHTML = `
    <strong>${task.kind === "plan" ? "多章节规划" : "批量生成草稿"} · ${escapeHtml(task.status)}</strong>
    <span>${escapeHtml(task.message || "任务已返回。")}</span>
    <small>章节：${(task.chapter_numbers || []).join(", ") || "未记录"}</small>
  `;

  const results = appState.latestBatchResults || task.chapter_results || [];
  const numbers = new Set(results.length ? results.map((result) => result.chapter_number) : task.chapter_numbers || []);
  const planned = getChapterPlans().filter((plan) => numbers.has(plan.chapter_number));
  renderChapterPlanTable(elements.batchOutlineTable, planned, { editable: true });
  renderBatchQueue(results);
}

function renderBatchQueue(chapterResults) {
  const plansByNumber = new Map(getChapterPlans().map((plan) => [plan.chapter_number, plan]));
  const results = (chapterResults || []).length
    ? chapterResults
    : (appState.latestBatchTask?.chapter_numbers || []).map((chapterNumber) => ({
        chapter_number: chapterNumber,
        status: "pending",
        can_review: false,
        can_accept: false,
        can_revise: false,
        conflict_type: null,
      }));
  if (!results.length) {
    elements.batchQueuePanel.className = "batch-queue-empty";
    elements.batchQueuePanel.textContent = "批量生成后，这里会按章节展示待审查、需修订、待接受入库等状态。";
    return;
  }

  elements.batchQueuePanel.className = "batch-queue";
  elements.batchQueuePanel.innerHTML = results
    .map((result) => {
      const number = result.chapter_number;
      const plan = plansByNumber.get(number);
      const status = getBatchChapterStatusLabel(result);
      const canView = Boolean(result.session_id || result.draft_status);
      const conflict = result.conflict_type ? ` · ${escapeHtml(result.conflict_type)}` : "";
      return `
        <article class="batch-queue-row ${result.conflict_type ? "has-conflict" : ""}" data-batch-chapter="${number}">
          <div>
            <strong>第 ${number} 章：${escapeHtml(status)}${conflict}</strong>
            <p>${escapeHtml(plan?.title || "未命名章节")} · ${escapeHtml(plan?.summary || result.review_status || result.draft_status || "暂无摘要")}</p>
          </div>
          <div class="batch-row-actions">
            <button class="ghost-btn compact" type="button" data-batch-action="view" data-chapter-number="${number}" ${canView ? "" : "disabled"}>查看草稿</button>
            <button class="ghost-btn compact" type="button" data-batch-action="review" data-chapter-number="${number}" ${result.can_review ? "" : "disabled"}>AI 审查</button>
            <button class="ghost-btn compact" type="button" data-batch-action="revise" data-chapter-number="${number}" ${result.can_revise ? "" : "disabled"}>同意修订</button>
            <button class="ghost-btn compact" type="button" data-batch-action="accept" data-chapter-number="${number}" ${result.can_accept ? "" : "disabled"}>接受入库</button>
            <button class="ghost-btn compact" type="button" data-batch-action="compare" data-chapter-number="${number}" ${result.conflict_type ? "" : "disabled"}>对比替换</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function getBatchChapterStatusLabel(result) {
  if (result.conflict_type) {
    return "已有章节冲突";
  }
  if (result.can_accept) {
    return "待接受入库";
  }
  if (result.can_revise) {
    return "建议修订";
  }
  if (result.can_review) {
    return "待审查";
  }
  if (result.review_status) {
    return "AI 已审查，待人工确认";
  }
  if (result.draft_status) {
    return "草稿，不会进入长期记忆";
  }
  return {
    pending: "排队中",
    planned: "已规划",
    generated: "草稿，不会进入长期记忆",
    reviewed: "AI 已审查，待人工确认",
    skipped: "已跳过",
    conflict: "已有章节冲突",
    failed: "失败",
  }[result.status] || getStatusLabel(result.status);
}

function renderReaderCatalog() {
  const chapters = getProjectChapters();
  if (!chapters.length) {
    elements.readerCatalog.className = "reader-catalog-empty";
    elements.readerCatalog.textContent = "暂无章节目录。";
    return;
  }

  elements.readerCatalog.className = "reader-catalog-list";
  elements.readerCatalog.innerHTML = chapters
    .map((chapter) => {
      const active = chapter.chapter_number === appState.previewChapterNumber;
      const readable = Boolean(chapter.draft?.content);
      const status = {
        planned: "未成稿",
        drafted: "草稿，不会进入长期记忆",
        reviewed: "AI 已审查，待人工确认",
        needs_revision: "建议修订",
        approved: "待接受入库",
        completed: "已完成入库",
        failed: "失败",
      }[chapter.status] || chapter.status;
      return `
        <button class="reader-chapter ${active ? "active" : ""} ${readable ? "" : "locked"}" type="button" data-preview-chapter="${chapter.chapter_number}">
          <span>第 ${chapter.chapter_number} 章</span>
          <strong>${escapeHtml(chapter.title || "未命名章节")}</strong>
          <small>${escapeHtml(status)}</small>
        </button>
      `;
    })
    .join("");
}

function renderPreviewChapter(chapter) {
  if (!chapter) {
    elements.previewTitle.textContent = "暂无章节";
    elements.previewStatus.textContent = "未开始";
    elements.previewContent.textContent = "这里会像正式小说阅读页一样展示已经生成的正文。完成一次章节生成后，内容会自动同步到这里。";
    return;
  }

  appState.previewChapterNumber = chapter.chapter_number;
  elements.previewTitle.textContent = chapter.title || `第 ${chapter.chapter_number} 章`;
  elements.previewStatus.textContent = chapter.draft?.content
    ? `第 ${chapter.chapter_number} 章 · ${getStatusLabel(chapter.status)} · ${chapter.word_count || countChineseWords(chapter.draft.content)} 字`
    : `第 ${chapter.chapter_number} 章 · ${getStatusLabel(chapter.status)}`;
  if (chapter.draft?.content) {
    elements.previewContent.textContent = chapter.draft.content;
  } else {
    elements.previewContent.innerHTML = `
      <div class="reader-status-panel">
        <strong>本章尚未形成可阅读正文</strong>
        <p>当前状态：${escapeHtml(getStatusLabel(chapter.status))}。你可以进入章节工作区继续处理本章。</p>
        <button class="primary-btn secondary compact" type="button" data-preview-action="process" data-chapter-number="${chapter.chapter_number}">去处理本章</button>
      </div>
    `;
  }
  renderReaderCatalog();
}

function renderNextSeedPanel(snapshot) {
  if (!snapshot) {
    elements.nextSeedPanel.classList.add("is-hidden");
    elements.nextSeedPanel.innerHTML = "";
    return;
  }

  const source = snapshot.source_chapter_number ? `第 ${snapshot.source_chapter_number} 章` : "作品设定";
  elements.nextSeedPanel.classList.remove("is-hidden");
  elements.nextSeedPanel.innerHTML = `
    <div class="seed-head">
      <div>
        <p class="eyebrow">Next Chapter Seed</p>
        <h3>根据${source}和作品设定预填</h3>
      </div>
      <span>准备第 ${snapshot.chapter_number} 章</span>
    </div>
    <div class="seed-grid">
      <div><strong>上一章钩子</strong><p>${escapeHtml(snapshot.last_chapter_hook || "暂无记录")}</p></div>
      <div><strong>未解决伏笔</strong><p>${escapeHtml((snapshot.unresolved_foreshadowing || []).join("；") || "暂无记录")}</p></div>
      <div><strong>推荐方向</strong><p>${escapeHtml((snapshot.recommended_next_directions || []).join("；") || "暂无推荐")}</p></div>
      <div><strong>命中章节规划</strong><p>${escapeHtml(snapshot.chapter_plan?.summary || "暂无命中规划")}</p></div>
    </div>
  `;
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
  appState.nextSnapshot = appState.project.next_chapter_input_snapshot || null;
  elements.batchStart.value = String(getNextGeneratedChapterNumber(appState.project));
  renderChapterCatalog();
  renderReaderCatalog();
  renderFullPlanForm();
  renderBatchStatus(appState.latestBatchTask);
  renderNextSeedPanel(appState.nextSnapshot);
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
  elements.reviewStat.textContent = appState.draft?.status ? getStatusLabel(appState.draft.status) : "待生成";

  if (appState.draft && appState.draft.chapter_number === appState.previewChapterNumber) {
    renderPreviewChapter({
      chapter_number: appState.draft.chapter_number || chapterNumber,
      title: appState.draft.title,
      status: appState.draft.status,
      word_count: countChineseWords(draftContent),
      draft: appState.draft,
    });
  } else if (!appState.project?.chapters?.length) {
    renderPreviewChapter(null);
  }
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
      const status = getStatusLabel(chapter.status);
      const canProcess = Boolean(chapter.session_id || chapter.status !== "completed");
      return `
        <article class="chapter-record ${isActive ? "active" : ""}" data-chapter-number="${chapter.chapter_number}">
          <button class="chapter-record-main" type="button" data-chapter-action="preview" data-chapter-number="${chapter.chapter_number}">
            <span>第 ${chapter.chapter_number} 章</span>
            <strong>${escapeHtml(chapter.title || "未命名章节")}</strong>
            <small>${escapeHtml(status)} · ${chapter.word_count || 0} 字</small>
          </button>
          <div class="chapter-record-actions">
            <button class="ghost-btn compact" type="button" data-chapter-action="preview" data-chapter-number="${chapter.chapter_number}">查看正文</button>
            <button class="ghost-btn compact" type="button" data-chapter-action="process" data-chapter-number="${chapter.chapter_number}" ${canProcess ? "" : "disabled"}>继续处理</button>
            <button class="ghost-btn compact" type="button" data-chapter-action="review" data-chapter-number="${chapter.chapter_number}" ${chapter.session_id ? "" : "disabled"}>审查/接受</button>
          </div>
        </article>
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
  renderCharacterCards(appState.projectCodex?.character_codex || []);
  renderLoreCodex(appState.projectCodex?.lore_codex || {});
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
  const entries = Array.isArray(characters) ? characters : Object.values(characters || {});
  if (!entries.length) {
    elements.characterCards.className = "character-empty";
    elements.characterCards.textContent = "项目级人物设定库暂无记录。接受章节入库后会在这里聚合。";
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

function renderLoreCodex(loreUpdates) {
  const entries = Object.entries(loreUpdates || {});
  if (!entries.length) {
    elements.loreCodex.className = "lore-codex-empty";
    elements.loreCodex.textContent = "项目级设定库暂无记录。全文规划、章节摘要和入库设定会汇总到这里。";
    return;
  }

  elements.loreCodex.className = "lore-codex";
  elements.loreCodex.innerHTML = `
    <div class="lore-codex-grid">
      ${entries
        .filter(([key]) => !/^chapter[_-]?\d+/i.test(key))
        .map(
          ([key, value]) => `
            <article class="lore-codex-card">
              <span>设定</span>
              <h3>${escapeHtml(localizeLoreKey(key))}</h3>
              <p>${escapeHtml(value)}</p>
            </article>
          `,
        )
        .join("")}
    </div>
    <div class="lore-timeline">
      ${entries
        .filter(([key]) => /^chapter[_-]?\d+/i.test(key))
        .map(
          ([key, value], index) => `
            <article class="lore-timeline-item">
              <strong>${index + 1}</strong>
              <div>
                <h3>${escapeHtml(localizeLoreKey(key))}</h3>
                <p>${escapeHtml(value)}</p>
              </div>
            </article>
          `,
        )
        .join("") || '<div class="lore-codex-empty">暂无章节时间线。</div>'}
    </div>
  `;
}

function renderLoreFishbone(loreUpdates) {
  renderLoreCodex(loreUpdates);
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
    elements.decisionTitle.textContent = "AI 已审查，待人工确认";
    elements.decisionMessage.textContent = "草稿暂不会进入长期记忆。人工确认后，才能接受入库并交给 Librarian 抽取稳定设定。";
    elements.acceptChapterBtn.classList.remove("is-hidden");
    return;
  }

  elements.decisionTitle.textContent = "建议修订";
  elements.decisionMessage.textContent = "AI 建议先修订草稿。你可以立即同意修订、暂停等待，或人工判断后接受入库。";
  elements.acceptChapterBtn.classList.remove("is-hidden");
  elements.reviseNowBtn.classList.remove("is-hidden");
  elements.waitRevisionBtn.classList.remove("is-hidden");
  startRevisionCountdown();
}

function holdRevisionDecision() {
  clearRevisionCountdown();
  elements.decisionTitle.textContent = "已暂停自动修改";
  elements.decisionMessage.textContent = "当前章节停在 AI 审查结果处。你可以接受入库，或重新确认打回 Writer 修订。";
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
        <strong>${escapeHtml(draft.status === "needs_revision" ? "建议修订" : "AI 已审查，待人工确认")}</strong>
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

async function loadProjectCodex(projectId = appState.projectId) {
  if (!projectId) {
    return null;
  }
  const data = await requestJson(`/novel/projects/${projectId}/codex`);
  appState.projectCodex = data;
  renderMemoryPanels();
  return data;
}

async function loadProjects() {
  const data = await requestJson("/novel/projects");
  appState.projects = data.projects || [];
  if (!appState.projects.some((project) => project.project_id === appState.projectId) && appState.project) {
    appState.projects.unshift(appState.project);
  }
  renderHomeProjectGrid();
  return appState.projects;
}

async function selectProject(projectId) {
  if (!projectId) {
    return null;
  }
  appState.projectId = projectId;
  const project = await loadProject(projectId);
  await loadProjectCodex(project.project_id);
  appState.previewChapterNumber = project.latest_edited_chapter_number || project.current_chapter_number || 1;
  const previewChapter = getProjectChapters().find((chapter) => chapter.chapter_number === appState.previewChapterNumber)
    || getProjectChapters()[0];
  renderPreviewChapter(previewChapter || null);
  return project;
}

async function createNewBook() {
  const title = elements.newBookTitle.value.trim();
  const genre = elements.newBookGenre.value.trim();
  const worldview = elements.newBookWorldview.value.trim();
  const hero = elements.newBookHero.value.trim();
  if (![title, genre, worldview, hero].some(Boolean)) {
    showToast("作品名、题材、世界观、主角设定任填一项即可启动。");
    return;
  }

  try {
    setLoading(elements.createBookBtn, true, "生成草案中...");
    const draftTitle = title || `${genre || "未命名题材"}新作`;
    const draftPremise = [
      genre ? `题材方向：${genre}` : "题材方向：由 AI 根据已有信息补完。",
      hero ? `主角驱动：${hero}` : "主角驱动：待补完主角欲望、缺陷与初始困境。",
      "叙事目标：建立清晰卖点、可连续推进的主线冲突，以及适合长篇连载的悬念结构。",
    ].join("\n");
    const draftWorldview = worldview || [
      "世界观草案：围绕主角目标搭建一套可持续制造冲突的规则。",
      "需要补完：时代背景、力量/职业体系、核心秘密、主要势力、第一卷舞台。",
    ].join("\n");
    const draftHero = hero || [
      "主角草案：拥有明确欲望和一个会制造麻烦的缺陷。",
      "需要补完：身份、动机、初始资源、关系压力、第一章触发事件。",
    ].join("\n");

    elements.draftTitle.value = draftTitle;
    elements.draftPremise.value = draftPremise;
    elements.draftWorldview.value = draftWorldview;
    elements.draftHero.value = draftHero;
    elements.newBookDraftPanel.classList.remove("is-hidden");
    bindAutoResize(elements.newBookDraftPanel);
    showToast("作品设定草案已生成，可编辑确认后再生成全文规划。");
  } catch (error) {
    showToast(error.message);
  } finally {
    setLoading(elements.createBookBtn, false);
  }
}

async function confirmSettingDraft() {
  const title = elements.draftTitle.value.trim();
  const premise = elements.draftPremise.value.trim();
  const worldview = elements.draftWorldview.value.trim();
  const hero = elements.draftHero.value.trim();
  if (![title, premise, worldview, hero].some(Boolean)) {
    showToast("请至少保留一项作品设定草案。");
    return;
  }

  const finalTitle = title || elements.newBookTitle.value.trim() || "未命名作品";
  const globalWorldview = [
    premise ? `作品定位：${premise}` : "",
    worldview ? `世界观：${worldview}` : "",
    hero ? `主角设定：${hero}` : "",
  ].filter(Boolean).join("\n\n");

  try {
    setLoading(elements.confirmSettingDraftBtn, true, "生成全文规划中...");
    const created = await requestJson("/novel/projects", {
      method: "POST",
      body: JSON.stringify({
        title: finalTitle,
        global_worldview: globalWorldview,
      }),
    });
    syncProject(created.project);
    elements.projectTitle.value = created.project.title;
    elements.worldview.value = created.project.global_worldview;
    elements.premise.value = premise;
    elements.planNotes.value = hero;

    await generateFullPlan({ silent: true });
    await loadProjects();
    elements.newBookPanel.classList.add("is-hidden");
    switchView("fullPlan");
    showToast("全文规划草案已生成，请确认或继续让 AI 补完。");
  } catch (error) {
    showToast(error.message);
  } finally {
    setLoading(elements.confirmSettingDraftBtn, false);
  }
}

async function generateFullPlan({ silent = false } = {}) {
  if (!appState.projectId) {
    showToast("请先选择或创建作品。");
    return;
  }

  try {
    setLoading(elements.generateFullPlanBtn, true, "生成中...");
    const data = await requestJson(`/novel/projects/${appState.projectId}/full-plan`, {
      method: "POST",
      body: JSON.stringify({
        target_chapter_count: Number(elements.targetChapterCount.value || 10),
      }),
    });
    syncProject(data.project);
    if (!silent) {
      showToast("全文规划骨架已生成。");
    }
  } catch (error) {
    showToast(error.message);
  } finally {
    setLoading(elements.generateFullPlanBtn, false);
  }
}

async function saveFullPlan() {
  if (!appState.projectId) {
    showToast("请先选择或创建作品。");
    return;
  }

  try {
    setLoading(elements.saveFullPlanBtn, true, "保存中...");
    const data = await requestJson(`/novel/projects/${appState.projectId}/full-plan`, {
      method: "PUT",
      body: JSON.stringify({
        full_plan: normalizeFullPlan(),
        volumes: parseJsonEditor(elements.volumes.value, [], "分卷规划"),
        chapter_plans: collectChapterPlansFromTable(),
      }),
    });
    syncProject(data.project);
    showToast("全文规划已保存。");
  } catch (error) {
    showToast(error.message);
  } finally {
    setLoading(elements.saveFullPlanBtn, false);
  }
}

function enterFirstChapter() {
  elements.chapter.value = "1";
  elements.session.value = "";
  updateSession("");
  elements.projectTitle.value = appState.project?.title || elements.projectTitle.value;
  elements.worldview.value = appState.project?.global_worldview || elements.worldview.value;
  const firstPlan = getChapterPlans().find((plan) => plan.chapter_number === 1);
  elements.summary.value = "";
  elements.instruction.value = firstPlan
    ? [firstPlan.summary, firstPlan.purpose].filter(Boolean).join("\n")
    : "生成第一章，建立主角处境、作品基调和核心悬念。";
  appState.nextSnapshot = null;
  renderNextSeedPanel(null);
  renderBeats([]);
  switchView("studioPlan");
  showToast("已进入第一章 Planner 输入区。");
}

function getBatchRange() {
  const start = Number(elements.batchStart.value || appState.project?.current_chapter_number || 1);
  const count = Number(elements.batchCount.value || 5);
  return {
    start,
    end: start + count - 1,
  };
}

function confirmBatchOverwriteIfNeeded(start, end) {
  const existing = getFirstExistingDraftInRange(start, end);
  if (!existing) {
    return true;
  }
  return window.confirm(`第 ${existing.chapter_number} 章已有草稿，是否对比生成？`);
}

async function runBatchPlan() {
  const { start, end } = getBatchRange();
  if (!confirmBatchOverwriteIfNeeded(start, end)) {
    return;
  }
  try {
    setLoading(elements.batchPlanBtn, true, "规划中...");
    const data = await requestJson(`/novel/projects/${appState.projectId}/batch/plan`, {
      method: "POST",
      body: JSON.stringify({
        start_chapter: start,
        end_chapter: end,
        user_instruction: elements.batchInstruction.value.trim() || null,
        characters: collectCharacters(),
        overwrite_policy: hasExistingDraftInRange(start, end) ? "compare" : "block",
      }),
    });
    appState.latestBatchTask = data.task;
    appState.latestBatchResults = data.chapter_results || [];
    if (data.suggested_batch_start_chapter) {
      elements.batchStart.value = String(data.suggested_batch_start_chapter);
    }
    await loadProject();
    renderBatchStatus(data.task);
    switchView("batchStudio");
    showToast("多章节规划已生成，请确认章节规划表。");
  } catch (error) {
    showToast(error.message);
  } finally {
    setLoading(elements.batchPlanBtn, false);
  }
}

async function runBatchGenerate() {
  const { start, end } = getBatchRange();
  if (!confirmBatchOverwriteIfNeeded(start, end)) {
    return;
  }
  try {
    setLoading(elements.batchGenerateBtn, true, "生成中...");
    const editedBatchPlans = collectChapterPlansFromTable("#batchOutlineTable");
    if (editedBatchPlans.length) {
      const byNumber = new Map(getChapterPlans().map((plan) => [plan.chapter_number, plan]));
      editedBatchPlans.forEach((plan) => byNumber.set(plan.chapter_number, plan));
      await requestJson(`/novel/projects/${appState.projectId}/full-plan`, {
        method: "PUT",
        body: JSON.stringify({
          full_plan: normalizeFullPlan(),
          volumes: parseJsonEditor(elements.volumes.value, [], "分卷规划"),
          chapter_plans: [...byNumber.values()].sort((a, b) => a.chapter_number - b.chapter_number),
        }),
      });
    }
    const data = await requestJson(`/novel/projects/${appState.projectId}/batch/generate`, {
      method: "POST",
      body: JSON.stringify({
        start_chapter: start,
        end_chapter: end,
        user_instruction: elements.batchInstruction.value.trim() || null,
        characters: collectCharacters(),
        overwrite_policy: hasExistingDraftInRange(start, end) ? "compare" : "block",
      }),
    });
    appState.latestBatchTask = data.task;
    appState.latestBatchResults = data.chapter_results || [];
    if (data.suggested_batch_start_chapter) {
      elements.batchStart.value = String(data.suggested_batch_start_chapter);
    }
    await loadProject();
    renderBatchStatus(data.task);
    showToast("批量草稿任务已完成，章节进入待确认列表。");
  } catch (error) {
    showToast(error.message);
  } finally {
    setLoading(elements.batchGenerateBtn, false);
  }
}

async function selectPreviewChapter(chapterNumber) {
  const localChapter = getProjectChapters().find((chapter) => chapter.chapter_number === chapterNumber);
  if (!localChapter) {
    return;
  }

  try {
    const data = await requestJson(`/novel/projects/${appState.projectId}/chapters/${chapterNumber}`);
    renderPreviewChapter(data.chapter);
  } catch (error) {
    renderPreviewChapter(localChapter);
    showToast(error.message);
  }
}

function movePreviewChapter(direction) {
  const chapters = getProjectChapters();
  if (!chapters.length) {
    return;
  }
  const currentIndex = chapters.findIndex((chapter) => chapter.chapter_number === appState.previewChapterNumber);
  const nextIndex = Math.min(Math.max((currentIndex === -1 ? 0 : currentIndex) + direction, 0), chapters.length - 1);
  selectPreviewChapter(chapters[nextIndex].chapter_number);
}

function getChapterByNumber(chapterNumber) {
  return getProjectChapters().find((chapter) => chapter.chapter_number === chapterNumber);
}

async function handleBatchChapterAction(action, chapterNumber) {
  const chapter = getChapterByNumber(chapterNumber);
  if (!chapter && action !== "compare") {
    showToast("这一章还没有生成记录。");
    return;
  }

  if (action === "view") {
    await selectPreviewChapter(chapterNumber);
    switchView("preview");
    return;
  }

  if (action === "compare") {
    if (chapter?.draft) {
      selectChapter(chapterNumber);
      renderMetaMessage("已进入当前草稿。对比替换需要后端提供候选稿后才能执行真正替换。");
      switchView("studioDraft");
    } else {
      elements.batchStart.value = String(chapterNumber);
      showToast(`第 ${chapterNumber} 章暂无草稿，可从该章开始对比生成。`);
    }
    return;
  }

  if (!chapter?.session_id) {
    showToast("这一章缺少会话 ID，暂不能执行该操作。");
    return;
  }

  updateSession(chapter.session_id);
  if (action === "review") {
    await reviewDraft();
  } else if (action === "revise") {
    await reviseDraft(`批量队列中确认第 ${chapterNumber} 章按 AI 审查意见修订。`);
  } else if (action === "accept") {
    await acceptChapter();
  }
  await loadProject();
  renderBatchStatus(appState.latestBatchTask);
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
  } else {
    appState.draft = null;
    appState.plotBeats = [];
    elements.draftOutput.textContent = "本章尚未生成草稿。";
    renderBeats(chapter.plot_beats || []);
    renderMetaMessage(`第 ${chapter.chapter_number} 章当前状态：${chapter.status || "未开始"}。`);
  }
  renderPreviewChapter(chapter);
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
      message: "正文已先展示到页面。接下来 AI 审查会判断本章是否建议修订。",
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
    await loadProjectCodex();
    finishAgentRun({
      agent: "Reviewer",
      stage: data.current_stage,
      title: data.current_stage === "awaiting_revision_decision" ? "建议修订" : "AI 已审查，待人工确认",
      message: data.current_stage === "awaiting_revision_decision"
        ? "审查发现需要处理的问题。你可以等待 10 秒自动同意修改，也可以手动选择下一步。"
        : "草稿已完成 AI 审查，仍需人工确认。接受入库后，Librarian 才会抽取稳定设定。",
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
        human_feedback: elements.feedback.value.trim() || "用户确认接受入库。",
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
    showToast("章节已完成入库，并完成设定抽取。");
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
    setLoading(elements.continueNextBtn, true, "准备下一章...");

    const data = await requestJson(`/novel/projects/${appState.projectId}/prepare-next`, {
      method: "POST",
      body: JSON.stringify({
        user_instruction: elements.instruction.value.trim() || null,
        characters: collectCharacters(),
      }),
    });
    const snapshot = data.snapshot;

    appState.nextSnapshot = snapshot;
    appState.draft = null;
    appState.loreUpdates = {};
    appState.characterUpdates = {};
    appState.plotBeats = [];
    elements.chapter.value = String(snapshot.chapter_number);
    elements.worldview.value = snapshot.global_worldview || snapshot.confirmed_worldview || elements.worldview.value;
    elements.summary.value = snapshot.previous_summary || "";
    elements.instruction.value =
      snapshot.user_instruction ||
      (snapshot.recommended_next_directions || []).join("；") ||
      elements.instruction.value;
    const preparedCharacters = snapshot.characters?.length
      ? snapshot.characters
      : snapshot.current_character_state || [];
    if (preparedCharacters.length) {
      appState.characters = preparedCharacters;
      renderCharacterForms();
    }
    renderNextSeedPanel(snapshot);
    setDecisionPanel(null);
    updateStage("planning");
    renderBeats([]);
    elements.draftOutput.textContent = "下一章输入已准备。确认左侧预填内容后，再点击 Planner 生成剧情节点。";
    renderMetaMessage("已从后端读取下一章预填输入。请确认世界观、前文摘要和本章要求后再正式生成 Planner。");
    renderMemoryPanels();
    await loadProject();
    switchView("studioPlan");
    showToast("下一章输入已准备，请确认后再生成 Planner。");
  } catch (error) {
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

async function openProjectWorkbench(projectId, viewName = "overview") {
  await selectProject(projectId);
  switchView(viewName);
}

async function continueProject(projectId) {
  await selectProject(projectId);
  const chapters = getProjectChapters();
  const latest = chapters.at(-1);
  if (latest && latest.status !== "completed") {
    selectChapter(latest.chapter_number);
    switchView(latest.draft ? "studioDraft" : "studioPlan");
    return;
  }
  if (latest) {
    await continueNextChapter();
    return;
  }
  switchView(appState.project?.full_plan ? "studioPlan" : "fullPlan");
}

$$(".nav-card, .sub-nav-card, .stage-nav-card").forEach((button) => {
  button.addEventListener("click", () => {
    switchView(button.dataset.view);
    if (button.dataset.view === "characters" || button.dataset.view === "lore") {
      loadProjectCodex().catch((error) => showToast(error.message));
    }
  });
});

elements.homeBtn.addEventListener("click", () => switchView("home"));
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
  const button = event.target.closest("[data-chapter-action]");
  if (!button) {
    return;
  }
  const chapterNumber = Number(button.dataset.chapterNumber || 1);
  const action = button.dataset.chapterAction;
  if (action === "preview") {
    selectPreviewChapter(chapterNumber);
    switchView("preview");
    return;
  }
  selectChapter(chapterNumber);
  if (action === "review") {
    switchView("studioDraft");
  }
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
elements.showNewBookBtn.addEventListener("click", () => {
  elements.newBookPanel.classList.remove("is-hidden");
  elements.newBookTitle.focus();
});
elements.cancelNewBookBtn.addEventListener("click", () => elements.newBookPanel.classList.add("is-hidden"));
elements.createBookBtn.addEventListener("click", createNewBook);
elements.confirmSettingDraftBtn.addEventListener("click", confirmSettingDraft);
elements.refreshHomeProjectsBtn.addEventListener("click", () => loadProjects().then(() => showToast("作品列表已刷新。")).catch((error) => showToast(error.message)));
elements.homeProjectGrid.addEventListener("click", (event) => {
  const actionButton = event.target.closest("[data-project-action]");
  if (!actionButton) {
    return;
  }
  const projectId = actionButton.dataset.projectId;
  const action = actionButton.dataset.projectAction;
  if (action === "preview") {
    openProjectWorkbench(projectId, "preview").catch((error) => showToast(error.message));
    return;
  }
  if (action === "continue") {
    continueProject(projectId).catch((error) => showToast(error.message));
    return;
  }
  openProjectWorkbench(projectId, "overview").catch((error) => showToast(error.message));
});
elements.generateFullPlanBtn.addEventListener("click", () => generateFullPlan());
elements.saveFullPlanBtn.addEventListener("click", saveFullPlan);
elements.enterFirstChapterBtn.addEventListener("click", enterFirstChapter);
elements.batchPlanBtn.addEventListener("click", runBatchPlan);
elements.batchGenerateBtn.addEventListener("click", runBatchGenerate);
elements.batchQueuePanel.addEventListener("click", (event) => {
  const button = event.target.closest("[data-batch-action]");
  if (!button) {
    return;
  }
  handleBatchChapterAction(button.dataset.batchAction, Number(button.dataset.chapterNumber || 1))
    .catch((error) => showToast(error.message));
});
elements.readerCatalog.addEventListener("click", (event) => {
  const button = event.target.closest(".reader-chapter");
  if (!button) {
    return;
  }
  selectPreviewChapter(Number(button.dataset.previewChapter || 1));
});
elements.previewContent.addEventListener("click", (event) => {
  const button = event.target.closest('[data-preview-action="process"]');
  if (!button) {
    return;
  }
  selectChapter(Number(button.dataset.chapterNumber || appState.previewChapterNumber || 1));
});
elements.prevChapterBtn.addEventListener("click", () => movePreviewChapter(-1));
elements.nextChapterBtn.addEventListener("click", () => movePreviewChapter(1));
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
loadProject()
  .then((project) => {
    appState.previewChapterNumber = project.latest_edited_chapter_number || project.current_chapter_number || 1;
    const previewChapter = getProjectChapters().find((chapter) => chapter.chapter_number === appState.previewChapterNumber)
      || getProjectChapters()[0];
    renderPreviewChapter(previewChapter || null);
    return loadProjectCodex(project.project_id).then(() => loadProjects());
  })
  .catch((error) => showToast(error.message));
