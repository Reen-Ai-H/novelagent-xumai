/* 叙脉阶段 1/2/3 应用壳：所有工作区真相来自服务端。 */
(function () {
  "use strict";

  const state = {
    screen: "landing",
    account: null,
    projects: [],
    notifications: [],
    unreadNotifications: 0,
    query: "",
    selectedMode: null,
    readyProject: null,
    sessionExpired: false,
    loadingLibrary: false,
    workspace: null,
    editorProjectId: null,
    editorLoadToken: 0,
    editorMode: "independent",
    activeChapterId: null,
    editorBuffer: "",
    editorTitleBuffer: "",
    editorRevision: 0,
    editorDirty: false,
    editorSaving: false,
    editorConflict: null,
    editorSaveFailed: false,
    editorSavedRevision: null,
    editorAnalysisState: "",
    editorChangeToken: 0,
    editorReadOnly: false,
    saveTimer: null,
    savePromise: null,
    completeInFlight: false,
    addChapterInFlight: false,
    editorTaskPollTimer: null,
    activeArchive: null,
    trialCharacterId: null,
    archiveProjectId: null,
    archiveMode: "independent",
    archiveWorkspace: null,
    aiProjectId: null,
    aiWorkspace: null,
    aiRunId: null,
    aiLoadToken: 0,
    directorPollTimer: null,
    aiSaving: false,
    archiveAnchorObserver: null,
    archiveAnchorIntent: null,
    archiveAnchorUnlockTimer: null,
    archiveScrollSpyCleanup: null,
    deconstructionProjectId: null,
    deconstructionWorkspace: null,
    deconstructionLoadToken: 0,
    deconstructionPollTimer: null,
    deconstructionView: "overview",
    deconstructionProgress: 100,
    deconstructionChapterId: "",
    deconstructionEvidenceRequestToken: 0,
    pendingEvidence: null,
    versionPreviewId: null,
    versionPreview: null,
    restoreConfirmVersionId: null,
    restoreInFlight: false,
    dialogFocus: new WeakMap(),
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const elements = {
    landingScreen: $("#landingScreen"),
    loginScreen: $("#loginScreen"),
    libraryScreen: $("#libraryScreen"),
    independentScreen: $("#independentScreen"),
    archiveScreen: $("#archiveScreen"),
    deconstructionScreen: $("#deconstructionScreen"),
    aiStudioScreen: $("#aiStudioScreen"),
    aiDirectorScreen: $("#aiDirectorScreen"),
    emailForm: $("#emailLoginForm"),
    emailInput: $("#emailInput"),
    emailField: $("#emailField"),
    emailError: $("#emailError"),
    emailSubmitButton: $("#emailSubmitButton"),
    loginStatus: $("#loginStatus"),
    sessionExpiredNotice: $("#sessionExpiredNotice"),
    librarySearch: $("#librarySearch"),
    libraryContent: $("#libraryContent"),
    readyContent: $("#readyContent"),
    libraryError: $("#libraryError"),
    accountEmail: $("#accountEmail"),
    creditBalance: $("#creditBalance"),
    dialog: $("#newProjectDialog"),
    notificationsDialog: $("#notificationsDialog"),
    notificationsList: $("#notificationsList"),
    newProjectForm: $("#newProjectForm"),
    projectDetails: $("#projectDetails"),
    selectedModeLabel: $("#selectedModeLabel"),
    projectTitleInput: $("#projectTitleInput"),
    projectBriefInput: $("#projectBriefInput"),
    projectError: $("#projectError"),
    createProjectButton: $("#createProjectButton"),
    modeOptions: $$(".mode-option"),
    toastRegion: $("#toastRegion"),
    editorProjectTitle: $("#editorProjectTitle"),
    editorModeLabel: $("#editorModeLabel"),
    writingModeNote: $("#writingModeNote"),
    editorChapterHeading: $("#editorChapterHeading"),
    editorSaveState: $("#editorSaveState"),
    editorAnalysisState: $("#editorAnalysisState"),
    editorWordCount: $("#editorWordCount"),
    completeChapterButton: $("#completeChapterButton"),
    editorNotice: $("#editorNotice"),
    startWorkspaceContent: $("#startWorkspaceContent"),
    editorWorkspaceContent: $("#editorWorkspaceContent"),
    chapterList: $("#chapterList"),
    chapterTitleInput: $("#chapterTitleInput"),
    chapterEditor: $("#chapterEditor"),
    editorRevisionLabel: $("#editorRevisionLabel"),
    archiveDrawer: $("#archiveDrawer"),
    archiveDrawerTitle: $("#archiveDrawerTitle"),
    archiveSummary: $("#archiveSummary"),
    archiveSnapshotSelect: $("#archiveSnapshotSelect"),
    analysisLabel: $("#analysisLabel"),
    importFileInput: null,
    pendingChangesDialog: $("#pendingChangesDialog"),
    pendingChangesContent: $("#pendingChangesContent"),
    ignoreChangesButton: $("#ignoreChangesButton"),
    rebuildChangesButton: $("#rebuildChangesButton"),
    versionHistoryDialog: $("#versionHistoryDialog"),
    versionHistoryContent: $("#versionHistoryContent"),
    versionPreviewContent: $("#versionPreviewContent"),
    restoreVersionDialog: $("#restoreVersionDialog"),
    restoreVersionTitle: $("#restoreVersionTitle"),
    restoreVersionContent: $("#restoreVersionContent"),
    confirmRestoreVersionButton: $("#confirmRestoreVersionButton"),
    trialDialog: $("#trialDialog"),
    trialStyleSelect: $("#trialStyleSelect"),
    trialEstimate: $("#trialEstimate"),
    confirmTrialButton: $("#confirmTrialButton"),
    archivePageProjectTitle: $("#archivePageProjectTitle"),
    archiveModeLabel: $("#archiveModeLabel"),
    archivePageStatus: $("#archivePageStatus"),
    archivePageSnapshotSelect: $("#archivePageSnapshotSelect"),
    archivePageContent: $("#archivePageContent"),
    archivePageNotice: $("#archivePageNotice"),
    archiveAiLink: $("#archiveAiLink"),
    deconstructionProjectTitle: $("#deconstructionProjectTitle"),
    deconstructionStatusPill: $("#deconstructionStatusPill"),
    deconstructionRefreshButton: $("#deconstructionRefreshButton"),
    deconstructionNotice: $("#deconstructionNotice"),
    deconstructionPageContent: $("#deconstructionPageContent"),
    deconstructionEvidenceDialog: $("#deconstructionEvidenceDialog"),
    deconstructionEvidenceTitle: $("#deconstructionEvidenceTitle"),
    deconstructionEvidenceContent: $("#deconstructionEvidenceContent"),
    locateDeconstructionEvidenceButton: $("#locateDeconstructionEvidenceButton"),
    aiStudioProjectTitle: $("#aiStudioProjectTitle"),
    aiStudioModelLabel: $("#aiStudioModelLabel"),
    aiStudioBlueprintState: $("#aiStudioBlueprintState"),
    aiStudioNotice: $("#aiStudioNotice"),
    aiConversation: $("#aiConversation"),
    aiConversationCount: $("#aiConversationCount"),
    aiMessageForm: $("#aiMessageForm"),
    aiMessageInput: $("#aiMessageInput"),
    aiMessageButton: $("#aiMessageButton"),
    blueprintForm: $("#blueprintForm"),
    blueprintRevision: $("#blueprintRevision"),
    blueprintHint: $("#blueprintHint"),
    blueprintMissing: $("#blueprintMissing"),
    saveBlueprintButton: $("#saveBlueprintButton"),
    confirmBlueprintButton: $("#confirmBlueprintButton"),
    professionalRoleStatus: $("#professionalRoleStatus"),
    directorProjectTitle: $("#aiDirectorProjectTitle"),
    aiDirectorNotice: $("#aiDirectorNotice"),
    directorStageTrack: $("#directorStageTrack"),
    directorPageContent: $("#directorPageContent"),
    directorCreditsUsed: $("#directorCreditsUsed"),
    directorCreditsEstimate: $("#directorCreditsEstimate"),
    aiDirectorModelLabel: $("#aiDirectorModelLabel"),
    directorCreditsUsedNote: $("#directorCreditsUsedNote"),
    directorCreditsEstimateNote: $("#directorCreditsEstimateNote"),
    directorPauseButton: $("#directorPauseButton"),
  };

  const modeText = {
    independent: {
      label: "独立创作",
      next: "下一阶段：进入独立创作编辑器",
      description: "你写正文，叙脉负责保存作品记忆。",
    },
    ai_assisted: {
      label: "AI 辅助写作",
      next: "下一阶段：进入 AI 创作室",
      description: "先和主编聊清蓝图，再由导演台持续创作。",
    },
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    return new Intl.DateTimeFormat("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date).replaceAll("/", "-");
  }

  function showToast(message, variant = "") {
    const toast = document.createElement("div");
    toast.className = `toast ${variant ? `toast-${variant}` : ""}`;
    toast.textContent = message;
    elements.toastRegion.appendChild(toast);
    window.setTimeout(() => toast.remove(), 3600);
  }

  async function requestJson(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    let payload = null;
    try {
      payload = await response.json();
    } catch (error) {
      payload = null;
    }
    if (!response.ok) {
      const detail = payload?.detail;
      const apiError = new Error(
        typeof detail === "object" ? detail.message : detail || "请求没有完成。",
      );
      apiError.status = response.status;
      apiError.code = typeof detail === "object" ? detail.code : "request_failed";
      apiError.data = typeof detail === "object" ? detail.data : null;
      throw apiError;
    }
    return payload;
  }

  function routeFromLocation() {
    if (window.location.pathname === "/login") return "login";
    if (window.location.pathname === "/library") return "library";
    if (/^\/archive\/[A-Za-z0-9_-]+$/.test(window.location.pathname)) return "archive";
    if (/^\/ai\/[A-Za-z0-9_-]+\/director$/.test(window.location.pathname)) return "aiDirector";
    if (/^\/ai\/[A-Za-z0-9_-]+$/.test(window.location.pathname)) return "aiStudio";
    if (/^\/independent\/[A-Za-z0-9_-]+$/.test(window.location.pathname)
      && new URLSearchParams(window.location.search).get("view") === "deconstruction") return "deconstruction";
    if (/^\/independent\/[A-Za-z0-9_-]+$/.test(window.location.pathname)) return "independent";
    return "landing";
  }

  function chapterIdFromLocation() {
    return new URLSearchParams(window.location.search).get("chapter") || null;
  }

  function editorPath(projectId, chapterId = state.activeChapterId) {
    const params = new URLSearchParams();
    if (chapterId) params.set("chapter", chapterId);
    const query = params.toString();
    return `/independent/${encodeURIComponent(projectId)}${query ? `?${query}` : ""}`;
  }

  function archivePath(projectId, chapterId = chapterIdFromLocation()) {
    const params = new URLSearchParams();
    if (chapterId) params.set("chapter", chapterId);
    const query = params.toString();
    return `/archive/${encodeURIComponent(projectId)}${query ? `?${query}` : ""}`;
  }

  function deconstructionPath(projectId, chapterId = chapterIdFromLocation()) {
    const params = new URLSearchParams();
    params.set("view", "deconstruction");
    if (chapterId) params.set("chapter", chapterId);
    return `/independent/${encodeURIComponent(projectId)}?${params.toString()}`;
  }

  function updateChapterUrl(chapterId, { replace = true, view = null } = {}) {
    const params = new URLSearchParams(window.location.search);
    if (chapterId) params.set("chapter", chapterId);
    else params.delete("chapter");
    if (view !== null) {
      if (view) params.set("view", view);
      else params.delete("view");
    }
    const query = params.toString();
    const path = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash || ""}`;
    if (replace) window.history.replaceState({}, "", path);
    else window.history.pushState({}, "", path);
    return path;
  }

  function chooseActiveChapter(version) {
    const chapters = Array.isArray(version?.chapters)
      ? [...version.chapters].sort((left, right) => Number(left.chapter_number || 0) - Number(right.chapter_number || 0))
      : [];
    const requestedChapterId = chapterIdFromLocation();
    const requested = chapters.find((chapter) => chapter.chapter_id === requestedChapterId);
    if (requested) return requested;
    const unfinished = chapters.filter((chapter) => chapter.status !== "ready");
    // 缺失或无效参数回退到最大的未完成章节，全部完成时回退到最后一章。
    return unfinished.at(-1) || chapters.at(-1) || null;
  }

  function syncActiveChapterUrl(chapterId) {
    if (chapterId && chapterIdFromLocation() !== chapterId) updateChapterUrl(chapterId);
  }

  function independentProjectIdFromLocation() {
    const match = window.location.pathname.match(/^\/independent\/([A-Za-z0-9_-]+)$/);
    return match ? match[1] : null;
  }

  function aiProjectIdFromLocation() {
    const match = window.location.pathname.match(/^\/ai\/([A-Za-z0-9_-]+)(?:\/director)?$/);
    return match ? match[1] : null;
  }

  function archiveProjectIdFromLocation() {
    const match = window.location.pathname.match(/^\/archive\/([A-Za-z0-9_-]+)$/);
    return match ? match[1] : null;
  }

  function setActiveScreen(screen) {
    if (state.screen === "archive" && screen !== "archive") state.archiveScrollSpyCleanup?.();
    if (state.screen === "independent" && screen !== "independent") {
      window.clearTimeout(state.editorTaskPollTimer);
      state.editorTaskPollTimer = null;
    }
    if (state.screen === "deconstruction" && screen !== "deconstruction") {
      window.clearTimeout(state.deconstructionPollTimer);
      state.deconstructionPollTimer = null;
      closeDeconstructionEvidenceDialog?.();
    }
    state.screen = screen;
    const screens = {
      landing: elements.landingScreen,
      login: elements.loginScreen,
      library: elements.libraryScreen,
      independent: elements.independentScreen,
      archive: elements.archiveScreen,
      deconstruction: elements.deconstructionScreen,
      aiStudio: elements.aiStudioScreen,
      aiDirector: elements.aiDirectorScreen,
    };
    Object.entries(screens).forEach(([name, node]) => {
      if (!node) return;
      const active = name === screen;
      node.classList.toggle("is-hidden", !active);
      node.setAttribute("aria-hidden", active ? "false" : "true");
    });
    document.body.classList.toggle("workspace-active", ["library", "independent", "archive", "deconstruction", "aiStudio", "aiDirector"].includes(screen));
    if (screen === "login") {
      window.setTimeout(() => elements.emailInput?.focus(), 80);
    }
  }

  async function navigate(path, { replace = false } = {}) {
    const sameProjectPath = path.startsWith(`/independent/${encodeURIComponent(state.editorProjectId || "")}`);
    const leavingEditor = state.screen === "independent"
      && (!sameProjectPath || new URL(path, window.location.origin).searchParams.get("view") === "deconstruction")
      && (state.editorDirty || state.editorSaving || state.editorConflict);
    if (leavingEditor && (state.editorSaveFailed || state.editorConflict)) return false;
    if (leavingEditor && !(await flushPendingSave())) return false;
    const method = replace ? "replaceState" : "pushState";
    window.history[method]({}, "", path);
    setActiveScreen(routeFromLocation());
    if (state.screen === "login") {
      renderLoginState();
    } else if (state.screen === "library") {
      if (state.account) {
        loadLibrary(new URLSearchParams(window.location.search).get("q") || "");
      } else {
        restoreSession("library");
      }
    } else if (state.screen === "independent") {
      const projectId = independentProjectIdFromLocation();
      if (state.account && projectId) {
        loadIndependentWorkspace(projectId);
      } else if (projectId) {
        restoreSession("independent");
      }
    } else if (state.screen === "archive") {
      const projectId = archiveProjectIdFromLocation();
      if (state.account && projectId) loadArchiveWorkspace(projectId);
      else if (projectId) restoreSession("archive");
    } else if (state.screen === "deconstruction") {
      const projectId = independentProjectIdFromLocation();
      if (state.account && projectId) loadDeconstructionWorkspace(projectId);
      else if (projectId) restoreSession("deconstruction");
    } else if (state.screen === "aiStudio" || state.screen === "aiDirector") {
      const projectId = aiProjectIdFromLocation();
      if (state.account && projectId) loadAIWorkspace(projectId, state.screen === "aiDirector");
      else if (projectId) restoreSession(state.screen);
    }
    window.scrollTo({
      top: 0,
      behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
    return true;
  }

  function renderLoginState() {
    elements.sessionExpiredNotice.classList.toggle("is-hidden", !state.sessionExpired);
    elements.emailError.textContent = "";
    elements.emailField.classList.remove("has-error");
    elements.loginStatus.textContent = "";
    elements.loginStatus.classList.remove("is-error");
  }

  function setEmailError(message) {
    elements.emailError.textContent = message;
    elements.emailField.classList.toggle("has-error", Boolean(message));
  }

  function showLoginFailure(message) {
    elements.loginStatus.textContent = message;
    elements.loginStatus.classList.add("is-error");
  }

  function validEmail(email) {
    return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim());
  }

  function setLoginSubmitting(submitting) {
    elements.emailSubmitButton.disabled = submitting;
    elements.emailSubmitButton.innerHTML = submitting
      ? "正在保存会话…"
      : '使用邮箱继续 <span aria-hidden="true">→</span>';
  }

  async function submitEmail(event) {
    event.preventDefault();
    const email = elements.emailInput.value.trim();
    setEmailError("");
    elements.loginStatus.textContent = "";
    elements.loginStatus.classList.remove("is-error");
    if (!validEmail(email)) {
      setEmailError("请填写有效的邮箱地址，例如 name@example.com");
      elements.emailInput.focus();
      return;
    }

    setLoginSubmitting(true);
    try {
      const payload = await requestJson("/api/auth/email", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      state.account = payload.account;
      state.sessionExpired = false;
      navigate("/library", { replace: true });
      await loadLibrary();
    } catch (error) {
      if (error.code === "invalid_email") {
        setEmailError(error.message);
      } else if (error.status) {
        showLoginFailure(error.message || "登录没有完成，请稍后重试。");
      } else {
        showLoginFailure("暂时无法连接叙脉服务，请确认本地服务正在运行后重试。");
      }
    } finally {
      setLoginSubmitting(false);
    }
  }

  function renderLibraryHeader() {
    const account = state.account || {};
    elements.accountEmail.textContent = account.email || "—";
    elements.creditBalance.textContent = Number(account.credit_balance || 0).toLocaleString("zh-CN");
    elements.librarySearch.value = state.query;
  }

  function updateNotificationCount() {
    $$('[data-notification-count]').forEach((node) => {
      node.textContent = String(state.unreadNotifications || 0);
      node.classList.toggle("is-hidden", !state.unreadNotifications);
    });
  }

  function renderNotifications() {
    const items = state.notifications || [];
    elements.notificationsList.innerHTML = items.length ? items.map((item) => `
      <article class="notification-item ${item.read ? "is-read" : "is-unread"}">
        <button type="button" data-action="open-notification-target" data-notification-id="${escapeHtml(item.notification_id)}" data-notification-project="${escapeHtml(item.project_id)}" data-notification-target="${escapeHtml(item.target_path)}">
          <span class="notification-dot" aria-hidden="true"></span><span class="notification-copy"><strong>${escapeHtml(item.project_title)}</strong><span>${escapeHtml(item.message)}</span><small>${escapeHtml(formatDate(item.created_at))} · ${item.read ? "已读" : "未读"}</small></span><span class="notification-arrow" aria-hidden="true">→</span>
        </button>
      </article>`).join("") : `<div class="notifications-empty"><span class="empty-mark">⌁</span><p>还没有需要回看的作品通知。</p></div>`;
  }

  function notificationTargetPath(rawTarget) {
    if (typeof rawTarget !== "string" || !rawTarget.trim()) return null;
    const target = rawTarget.trim();
    if (!target.startsWith("/") || target.startsWith("//")) return null;
    let url;
    try {
      url = new URL(target, window.location.origin);
    } catch (error) {
      return null;
    }
    if (url.origin !== window.location.origin) return null;
    const knownPath = /^\/library(?:[?#].*)?$|^\/independent\/[A-Za-z0-9_-]+(?:\?view=deconstruction)?(?:[#].*)?$|^\/archive\/[A-Za-z0-9_-]+(?:[?#].*)?$|^\/ai\/[A-Za-z0-9_-]+(?:\/director)?(?:[?#].*)?$/;
    if (!knownPath.test(target)) return null;
    return `${url.pathname}${url.search}${url.hash}`;
  }

  async function loadNotifications() {
    if (!state.account) return false;
    try {
      const payload = await requestJson("/api/notifications");
      state.notifications = payload.notifications || [];
      state.unreadNotifications = Number(payload.unread_count || 0);
      updateNotificationCount();
      if (elements.notificationsDialog?.open) renderNotifications();
      return true;
    } catch (error) {
      updateNotificationCount();
      return false;
    }
  }

  async function openNotifications() {
    await loadNotifications();
    renderNotifications();
    rememberDialogFocus(elements.notificationsDialog);
    if (typeof elements.notificationsDialog.showModal === "function") elements.notificationsDialog.showModal();
    else elements.notificationsDialog.setAttribute("open", "");
  }

  async function openNotificationTarget(actionNode) {
    const targetPath = notificationTargetPath(actionNode.dataset.notificationTarget);
    if (!targetPath) {
      showToast("通知目标不可用，已留在当前页面。", "red");
      return;
    }
    try {
      const payload = await requestJson(`/api/notifications/${encodeURIComponent(actionNode.dataset.notificationProject)}/${encodeURIComponent(actionNode.dataset.notificationId)}/read`, { method: "POST" });
      state.notifications = payload.notifications || [];
      state.unreadNotifications = Number(payload.unread_count || 0);
      updateNotificationCount();
      renderNotifications();
      if (typeof elements.notificationsDialog.close === "function") elements.notificationsDialog.close();
      else elements.notificationsDialog.removeAttribute("open");
      const navigated = await navigate(targetPath);
      if (!navigated) showToast("当前正文尚未保存，通知已读但暂未离开当前页面。", "red");
    } catch (error) {
      showToast(error.message || "通知没有打开，请稍后重试。", "red");
    }
  }

  function renderLibraryLoading() {
    elements.libraryContent.classList.remove("is-hidden");
    elements.readyContent.classList.add("is-hidden");
    elements.libraryContent.innerHTML = '<div class="library-state loading-state">正在从服务端读取作品…</div>';
  }

  function renderLibraryError(message) {
    elements.libraryContent.innerHTML = `
      <div class="library-state empty-state">
        <div class="empty-mark">!</div>
        <h2>书架暂时没有回应</h2>
        <p>${escapeHtml(message)}</p>
        <button class="button button-outline" type="button" data-action="retry-library">重新读取</button>
      </div>`;
  }

  function renderEmptyLibrary() {
    elements.libraryContent.innerHTML = `
      <div class="library-state empty-state">
        <div class="empty-mark">⌁</div>
        <h2>还没有作品</h2>
        <p>从一条想法开始。先选创作方式，作品会保存到你的账户书架。</p>
        <button class="button button-primary" type="button" data-action="open-new-project">新建第一部作品 <span aria-hidden="true">→</span></button>
      </div>`;
  }

  function projectCard(project, index) {
    const ai = project.mode === "ai_assisted";
    const target = project.target_chapter_count ? ` / ${project.target_chapter_count}` : "";
    const statusClass = project.status.includes("失败") ? "status-failed" : project.status.includes("处理") ? "status-processing" : "";
    return `
      <article class="project-card" data-project-id="${escapeHtml(project.project_id)}">
        <div class="project-cover">
          <small>PROJECT / ${String(index + 1).padStart(2, "0")}</small>
          <h3>${escapeHtml(project.title)}</h3>
        </div>
        <div class="project-body">
          <div class="project-meta">
            ${ai ? '<span class="mode-flag">AI 辅助写作</span>' : '<span class="mode-note">独立创作</span>'}
            <button class="project-menu" type="button" aria-label="作品选项" disabled>···</button>
          </div>
          <h4>${escapeHtml(project.brief || modeText[project.mode]?.description || "作品基础已保存")}</h4>
          <div class="project-stats"><span>${project.chapter_count} 章${target}</span><span>${Number(project.total_word_count || 0).toLocaleString("zh-CN")} 字</span>${ai ? `<span>创作积分 ${Number(project.credits_used || 0).toLocaleString("zh-CN")} · 暂不结算</span>` : ""}</div>
          <div class="progress-line" aria-label="创作进度 ${project.progress_percent}%"><b style="width: ${project.progress_percent}%"></b></div>
          <div class="project-footer"><span class="project-status ${statusClass}">${escapeHtml(project.status)}</span><button class="project-continue" type="button" data-action="open-project">查看作品 →</button></div>
          <div class="project-footer"><span>最近编辑：${escapeHtml(formatDate(project.latest_edited_at))}</span><span class="mono">${project.progress_percent}%</span></div>
        </div>
      </article>`;
  }

  function renderProjects(projects) {
    if (!projects.length) {
      renderEmptyLibrary();
      return;
    }
    elements.libraryContent.innerHTML = `<div class="project-grid">${projects.map(projectCard).join("")}</div>`;
  }

  function renderReady(project) {
    state.readyProject = project;
    elements.libraryContent.classList.add("is-hidden");
    elements.readyContent.classList.remove("is-hidden");
    const ai = project.mode === "ai_assisted";
    elements.readyContent.innerHTML = `
      <article class="ready-card ${ai ? "ai-ready" : ""}">
        <span class="ready-overline">PROJECT SAVED / ${escapeHtml(project.project_id.slice(0, 8).toUpperCase())}</span>
        <h2>作品已保存。</h2>
        <p><strong>${escapeHtml(project.title)}</strong> 已经进入你的账户书架。${escapeHtml(modeText[project.mode]?.description || "")}</p>
        <span class="ready-mode">${escapeHtml(project.mode_label)}</span>
        <div class="ready-divider"></div>
        <div class="ready-next"><div><span>当前阶段完成</span><strong>${escapeHtml(ai ? "下一阶段：进入 AI 创作室" : "下一阶段：进入独立创作编辑器")}</strong></div><button class="ready-back" type="button" data-action="back-library">回到书架 →</button></div>
      </article>`;
  }

  async function loadLibrary(query = state.query) {
    if (!state.account) return;
    state.loadingLibrary = true;
    state.query = query;
    renderLibraryHeader();
    renderLibraryLoading();
    elements.libraryError.classList.add("is-hidden");
    try {
      const payload = await requestJson(`/api/library${query ? `?q=${encodeURIComponent(query)}` : ""}`);
      state.account = payload.account;
      state.projects = payload.projects || [];
      renderLibraryHeader();
      const createdId = new URLSearchParams(window.location.search).get("created");
      if (createdId) {
        const created = state.projects.find((project) => project.project_id === createdId);
        if (created) renderReady(created);
        else renderProjects(state.projects);
      } else {
        renderProjects(state.projects);
      }
      await loadNotifications();
    } catch (error) {
      if (error.code === "session_expired" || error.status === 401) {
        state.account = null;
        state.sessionExpired = error.code === "session_expired";
        navigate("/login", { replace: true });
        renderLoginState();
      } else {
        renderLibraryError(error.message || "无法读取书架，请稍后重试。");
        elements.libraryError.textContent = error.message || "无法读取书架，请稍后重试。";
        elements.libraryError.classList.remove("is-hidden");
      }
    } finally {
      state.loadingLibrary = false;
    }
  }

  function openNewProject() {
    resetProjectDialog();
    rememberDialogFocus(elements.dialog);
    if (typeof elements.dialog.showModal === "function") {
      elements.dialog.showModal();
    } else {
      elements.dialog.setAttribute("open", "");
    }
  }

  function rememberDialogFocus(dialog) {
    if (dialog) state.dialogFocus.set(dialog, document.activeElement);
  }

  function restoreDialogFocus(dialog) {
    const target = dialog ? state.dialogFocus.get(dialog) : null;
    if (target && typeof target.focus === "function") window.setTimeout(() => target.focus(), 0);
  }

  function dialogFocusableElements(dialog) {
    return $$('button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])', dialog)
      .filter((node) => node.getClientRects().length > 0);
  }

  function trapDialogFocus(event) {
    const dialog = event.currentTarget;
    if (!dialog?.open) return;
    if (event.key === "Escape") {
      event.preventDefault();
      dialog.close?.();
      return;
    }
    if (event.key === "Tab") {
      // Tab stays inside the open dialog; Escape closes it and restores its trigger.
    } else {
      return;
    }
    const focusable = dialogFocusableElements(dialog);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function bindDialogFocus(dialog) {
    dialog?.addEventListener("keydown", trapDialogFocus);
  }

  function resetProjectDialog() {
    state.selectedMode = null;
    elements.modeOptions.forEach((option) => option.classList.remove("is-selected"));
    elements.projectDetails.classList.add("is-hidden");
    elements.selectedModeLabel.textContent = "—";
    elements.projectTitleInput.value = "";
    elements.projectBriefInput.value = "";
    elements.projectError.textContent = "";
    elements.createProjectButton.disabled = false;
    elements.createProjectButton.innerHTML = '保存作品并进入下一阶段 <span aria-hidden="true">→</span>';
  }

  function chooseMode(mode) {
    if (!modeText[mode]) return;
    state.selectedMode = mode;
    elements.modeOptions.forEach((option) => option.classList.toggle("is-selected", option.dataset.mode === mode));
    elements.projectDetails.classList.remove("is-hidden");
    elements.selectedModeLabel.textContent = `已选择：${modeText[mode].label}`;
    elements.projectError.textContent = "";
    window.setTimeout(() => elements.projectTitleInput.focus(), 50);
  }

  async function submitProject(event) {
    if (event.submitter?.value === "cancel") return;
    event.preventDefault();
    if (!state.selectedMode) return;
    const title = elements.projectTitleInput.value.trim();
    if (!title) {
      elements.projectError.textContent = "请先写一个作品标题。";
      elements.projectTitleInput.focus();
      return;
    }
    elements.projectError.textContent = "";
    elements.createProjectButton.disabled = true;
    elements.createProjectButton.textContent = "正在保存作品…";
    try {
      const payload = await requestJson("/api/library/projects", {
        method: "POST",
        body: JSON.stringify({
          title,
          mode: state.selectedMode,
          brief: elements.projectBriefInput.value.trim() || null,
        }),
      });
      elements.dialog.close();
      if (payload.project.mode === "independent") {
        const nextPath = `/independent/${encodeURIComponent(payload.project.project_id)}`;
        navigate(nextPath, { replace: true });
        await loadIndependentWorkspace(payload.project.project_id);
      } else {
        const nextPath = `/ai/${encodeURIComponent(payload.project.project_id)}`;
        navigate(nextPath, { replace: true });
        await loadAIWorkspace(payload.project.project_id, false);
      }
      showToast("作品已保存到你的账户书架。");
    } catch (error) {
      elements.projectError.textContent = error.status === 401
        ? "会话已失效，请重新登录后再保存。"
        : error.message || "作品保存失败，请重试。";
      elements.createProjectButton.disabled = false;
      elements.createProjectButton.innerHTML = '保存作品并进入下一阶段 <span aria-hidden="true">→</span>';
    }
  }

  async function logout() {
    if (!(await flushPendingSave())) return;
    try {
      await requestJson("/api/auth/logout", { method: "POST", body: "{}" });
    } catch (error) {
      showToast("退出请求没有完成，请稍后重试。", "red");
      return;
    }
    state.account = null;
    state.projects = [];
    state.notifications = [];
    state.unreadNotifications = 0;
    updateNotificationCount();
    state.readyProject = null;
    state.sessionExpired = false;
    navigate("/login", { replace: true });
    showToast("已退出当前账户。");
  }

  async function restoreSession(preferredScreen = routeFromLocation()) {
    try {
      const payload = await requestJson("/api/auth/session");
      if (payload.authenticated) {
        state.account = payload.account;
        state.sessionExpired = false;
        if (preferredScreen === "library") {
          setActiveScreen("library");
          await loadLibrary();
        } else if (preferredScreen === "independent") {
          setActiveScreen("independent");
          const projectId = independentProjectIdFromLocation();
          if (projectId) await loadIndependentWorkspace(projectId);
        } else if (preferredScreen === "archive") {
          setActiveScreen("archive");
          const projectId = archiveProjectIdFromLocation();
          if (projectId) await loadArchiveWorkspace(projectId);
        } else if (preferredScreen === "deconstruction") {
          setActiveScreen("deconstruction");
          const projectId = independentProjectIdFromLocation();
          if (projectId) await loadDeconstructionWorkspace(projectId);
        } else if (preferredScreen === "aiStudio" || preferredScreen === "aiDirector") {
          setActiveScreen(preferredScreen);
          const projectId = aiProjectIdFromLocation();
          if (projectId) await loadAIWorkspace(projectId, preferredScreen === "aiDirector");
        } else {
          setActiveScreen("landing");
        }
        return;
      }
      state.account = null;
      if (["library", "independent", "archive", "deconstruction", "aiStudio", "aiDirector"].includes(preferredScreen)) {
        navigate("/login", { replace: true });
      } else {
        setActiveScreen(preferredScreen);
      }
    } catch (error) {
      if (["library", "independent", "archive", "deconstruction", "aiStudio", "aiDirector"].includes(preferredScreen)) {
        state.sessionExpired = error.code === "session_expired";
        state.account = null;
        navigate("/login", { replace: true });
      } else {
        setActiveScreen(preferredScreen);
      }
    }
  }

  function countEditorWords(value) {
    return String(value || "").replace(/\s+/g, "").length;
  }

  function setEditorSaveState(label, variant = "") {
    elements.editorSaveState.textContent = label;
    elements.editorSaveState.className = `editor-save-state ${variant ? `is-${variant}` : ""}`;
  }

  function setEditorAnalysisState(label, variant = "") {
    state.editorAnalysisState = label;
    if (!elements.editorAnalysisState) return;
    elements.editorAnalysisState.textContent = label;
    elements.editorAnalysisState.className = `editor-analysis-state ${variant ? `is-${variant}` : ""}`;
  }

  function focusChapterTitle() {
    const focus = () => {
      if (!elements.chapterTitleInput || elements.chapterTitleInput.disabled) return;
      elements.chapterTitleInput.focus();
      elements.chapterTitleInput.select?.();
    };
    focus();
    window.setTimeout(focus, 0);
  }

  function focusVersionPreviewTitle() {
    window.setTimeout(() => document.getElementById("versionPreviewTitle")?.focus(), 0);
  }

  function setEditorNotice(message, variant = "") {
    elements.editorNotice.textContent = message || "";
    elements.editorNotice.className = `notice editor-notice ${message ? "" : "is-hidden"} ${variant ? `notice-${variant}` : "notice-blue"}`;
  }

  function setEditorNoticeHtml(html, variant = "") {
    elements.editorNotice.innerHTML = html || "";
    elements.editorNotice.className = `notice editor-notice ${html ? "" : "is-hidden"} ${variant ? `notice-${variant}` : "notice-blue"}`;
  }

  function activeEditorVersion() {
    return state.workspace?.active_version || null;
  }

  function replaceActiveVersionChapter(chapter) {
    const version = activeEditorVersion();
    if (!version || !chapter?.chapter_id || !Array.isArray(version.chapters)) return;
    version.chapters = version.chapters.map((item) => item.chapter_id === chapter.chapter_id ? { ...item, ...chapter } : item);
  }

  function renderStartWorkspace(workspace) {
    elements.editorWorkspaceContent.classList.add("is-hidden");
    elements.startWorkspaceContent.classList.remove("is-hidden");
    elements.completeChapterButton.disabled = true;
    elements.editorProjectTitle.textContent = workspace.title || "—";
    elements.editorModeLabel.textContent = workspace.mode === "ai_assisted" ? "AI 辅助写作" : "独立创作";
    elements.writingModeNote.textContent = workspace.mode === "ai_assisted" ? "AI 辅助写作 · 唯一正式正文" : "独立创作 · 正式正文";
    elements.editorChapterHeading.textContent = "先把故事带回来";
    setEditorSaveState("等待开始");
    setEditorAnalysisState("尚未开始");
    elements.editorWordCount.textContent = "0 字";
    elements.startWorkspaceContent.innerHTML = `
      <article class="start-workspace-card paper-card">
        <span class="ready-overline">INDEPENDENT / START</span>
        <h2>把旧稿带回故事，<br /><em>或者从一张白纸开始。</em></h2>
        <p>导入会先生成可检查的预览：标题、章节识别、字数和无法识别的片段。你确认之后，正文才会写入正式稿本。</p>
        <div class="start-choice-grid">
          <button class="start-choice" type="button" data-action="start-blank"><span class="start-choice-mark">Ⅰ</span><strong>从空白开始</strong><small>先写第一章，保存后再完成本章。</small><span class="text-link">打开空白稿本 →</span></button>
          <button class="start-choice" type="button" data-action="open-import"><span class="start-choice-mark">Ⅱ</span><strong>导入旧稿</strong><small>支持 TXT、MD、DOCX，确认预览后正式写入。</small><span class="text-link">选择文件 →</span></button>
        </div>
        <input id="importFileInput" class="visually-hidden" type="file" accept=".txt,.md,.docx,text/plain,text/markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document" />
        <div id="importPreviewRegion" class="import-preview-region"></div>
        <p class="start-footnote"><span class="mono">LIMIT / 5 MB</span>　文件太大或格式不支持时，输入会保留并明确说明原因。</p>
      </article>`;
    elements.importFileInput = $("#importFileInput");
    elements.importFileInput.addEventListener("change", (event) => {
      const file = event.target.files?.[0];
      if (file) previewImportFile(file);
    });
    const latestPreview = workspace.pending_imports?.[workspace.pending_imports.length - 1];
    if (latestPreview) renderImportPreview(latestPreview);
  }

  function renderImportPreview(preview) {
    const region = $("#importPreviewRegion");
    if (!region) return;
    const failure = preview.status === "failed";
    region.innerHTML = `
      <div class="import-preview-card ${failure ? "is-failed" : ""}">
        <div class="import-preview-head"><div><span class="eyebrow">${failure ? "导入失败，输入已保留" : "导入预览"}</span><strong>${escapeHtml(preview.filename)}</strong></div><span class="mono">${escapeHtml(preview.format || "未知格式")}</span></div>
        ${failure ? `<p class="import-error-text">${escapeHtml(preview.error_message || "文件无法识别，请重新选择。")}</p>` : `
          <div class="import-facts"><span><strong>${preview.chapter_count}</strong> 章</span><span><strong>${Number(preview.total_word_count || 0).toLocaleString("zh-CN")}</strong> 字</span><span><strong>${preview.unrecognized_fragments?.length || 0}</strong> 段待确认</span></div>
          <div class="import-chapter-list">${(preview.chapters || []).map((chapter) => `<div><span class="mono">第 ${chapter.chapter_number} 章</span><strong>${escapeHtml(chapter.title)}</strong><span>${Number(chapter.word_count || 0).toLocaleString("zh-CN")} 字</span></div>`).join("")}</div>
          ${(preview.unrecognized_fragments || []).length ? `<div class="unrecognized-fragments"><strong>无法识别片段</strong>${preview.unrecognized_fragments.map((fragment) => `<p>${escapeHtml(fragment)}</p>`).join("")}</div>` : ""}
          <button class="button button-primary" type="button" data-action="confirm-import" data-preview-id="${escapeHtml(preview.preview_id)}">确认预览并写入正式正文 <span aria-hidden="true">→</span></button>`}
      </div>`;
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
      reader.onerror = () => reject(new Error("文件读取失败，请保留原文件后重试。"));
      reader.readAsDataURL(file);
    });
  }

  async function previewImportFile(file) {
    setEditorSaveState("正在读取导入…");
    try {
      const contentBase64 = await fileToBase64(file);
      const payload = await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/imports/preview`, {
        method: "POST",
        body: JSON.stringify({ filename: file.name, content_base64: contentBase64 }),
      });
      renderImportPreview(payload.preview);
      setEditorSaveState(payload.preview.status === "failed" ? "导入失败" : "等待确认");
    } catch (error) {
      setEditorSaveState("导入失败", "error");
      setEditorNotice(error.message || "文件预览失败，请保留输入后重试。", "red");
    }
  }

  async function startBlankWorkspace() {
    try {
      await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/start`, {
        method: "POST",
        body: JSON.stringify({ source: "blank" }),
      });
      await loadIndependentWorkspace(state.editorProjectId);
      showToast("空白稿本已创建，可以开始写作。");
    } catch (error) {
      setEditorNotice(error.message || "空白稿本创建失败，请重试。", "red");
    }
  }

  async function confirmImport(previewId) {
    const button = $(`[data-action="confirm-import"][data-preview-id="${CSS.escape(previewId)}"]`);
    if (button) button.disabled = true;
    try {
      await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/imports/${encodeURIComponent(previewId)}/confirm`, {
        method: "POST",
      });
      await loadIndependentWorkspace(state.editorProjectId);
      showToast("导入已确认，正文已经写入正式稿本。");
    } catch (error) {
      if (button) button.disabled = false;
      setEditorNotice(error.message || "导入确认失败，正文没有被覆盖。", "red");
    }
  }

  async function loadIndependentWorkspace(projectId) {
    if (!projectId) return;
    const loadToken = ++state.editorLoadToken;
    const projectChanged = state.editorProjectId !== projectId;
    if (projectChanged) {
      state.activeChapterId = null;
      state.editorBuffer = "";
      state.editorTitleBuffer = "";
      state.editorRevision = 0;
      state.editorDirty = false;
      state.editorSaving = false;
      state.editorConflict = null;
      state.editorSaveFailed = false;
      state.editorSavedRevision = null;
      state.editorChangeToken = 0;
    }
    state.editorProjectId = projectId;
    setActiveScreen("independent");
    elements.editorProjectTitle.textContent = "正在读取…";
    try {
      const workspace = await requestJson(`/api/independent/projects/${encodeURIComponent(projectId)}`);
      if (loadToken !== state.editorLoadToken || state.editorProjectId !== projectId) return;
      state.workspace = workspace;
      state.editorMode = workspace.mode || state.editorMode || "independent";
      state.activeArchive = workspace.archive;
      state.editorConflict = null;
      if (!workspace.initialized) {
        renderStartWorkspace(workspace);
      } else {
        const selectedChapter = chooseActiveChapter(workspace.active_version);
        if (selectedChapter && (!state.editorDirty || state.activeChapterId === selectedChapter.chapter_id)) {
          state.activeChapterId = selectedChapter.chapter_id;
          syncActiveChapterUrl(selectedChapter.chapter_id);
        }
        renderEditorWorkspace();
      }
      void loadNotifications();
    } catch (error) {
      if (error.status === 401) {
        state.account = null;
        state.sessionExpired = error.code === "session_expired";
        navigate("/login", { replace: true });
        return;
      }
      elements.editorProjectTitle.textContent = "读取失败";
      elements.startWorkspaceContent.classList.remove("is-hidden");
      elements.editorWorkspaceContent.classList.add("is-hidden");
      setEditorNotice(error.message || "独立作品读取失败，请稍后重试。", "red");
    }
  }

  function renderChapterList(version) {
    elements.chapterList.innerHTML = version.chapters.map((chapter) => `
      <button class="chapter-list-item ${chapter.chapter_id === state.activeChapterId ? "is-active" : ""} ${chapter.status === "failed" ? "is-failed" : ""}" type="button" data-action="select-chapter" data-chapter-id="${escapeHtml(chapter.chapter_id)}">
        <span class="chapter-list-number mono">${String(chapter.chapter_number).padStart(2, "0")}</span><span class="chapter-list-copy"><strong>${escapeHtml(chapter.title || `第${chapter.chapter_number}章`)}</strong><small>${Number(chapter.word_count || 0).toLocaleString("zh-CN")} 字 · ${escapeHtml(chapter.status === "ready" ? "已分析" : chapter.status === "analyzing" ? "分析中" : chapter.status === "failed" ? "分析失败" : "写作中")}</small></span><span class="chapter-list-arrow">${chapter.chapter_id === state.activeChapterId ? "·" : ""}</span>
      </button>`).join("");
  }

  function renderArchiveSummary(archive, selectedChapterNumber = null) {
    state.activeArchive = archive || { characters: [], storylines: [], foreshadowing: [], questions: [], snapshots: [] };
    const characters = state.activeArchive.characters || [];
    const storylines = state.activeArchive.storylines || [];
    const foreshadowing = state.activeArchive.foreshadowing || [];
    const questions = state.activeArchive.questions || [];
    elements.archiveDrawerTitle.textContent = selectedChapterNumber ? `第 ${selectedChapterNumber} 章快照 · 只读` : "最新状态";
    elements.analysisLabel.textContent = state.activeArchive.analysis_label || "确定性演示分析（未配置模型 Key）";
    elements.archiveSummary.innerHTML = `
      <section class="archive-summary-section"><div class="archive-summary-heading"><strong>人物</strong><span>${characters.length}</span></div>${characters.length ? characters.map((character) => `<article class="archive-character-card"><div class="character-glyph" aria-hidden="true"><span></span></div><div class="archive-character-copy"><strong>${escapeHtml(character.name)}</strong><small>${escapeHtml(character.role)} · 来源第 ${character.source_chapter_number} 章</small><p>${escapeHtml(character.profile)}</p><button type="button" class="text-link character-trial-link" data-action="open-trial" data-character-id="${escapeHtml(character.character_id)}">试绘这个角色</button></div></article>`).join("") : `<p class="archive-empty-note">完成本章后，人物会在这里留下来源。</p>`}</section>
      <section class="archive-summary-section"><div class="archive-summary-heading"><strong>剧情线</strong><span>${storylines.length}</span></div>${storylines.length ? `<ul class="archive-list">${storylines.map((item) => `<li><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.summary)} · 第 ${item.source_chapter_number} 章</span></li>`).join("")}</ul>` : `<p class="archive-empty-note">还没有记录剧情线。</p>`}</section>
      <section class="archive-summary-section"><div class="archive-summary-heading"><strong>伏笔</strong><span>${foreshadowing.length}</span></div>${foreshadowing.length ? `<ul class="archive-list compact-list">${foreshadowing.map((item) => `<li><strong>${escapeHtml(item.status === "open" ? "未解" : "已解")}</strong><span>${escapeHtml(item.text)} · 第 ${item.source_chapter_number} 章</span></li>`).join("")}</ul>` : `<p class="archive-empty-note">完成本章后，伏笔会按来源保留。</p>`}</section>
      <section class="archive-summary-section"><div class="archive-summary-heading"><strong>疑问点</strong><span>${questions.length}</span></div>${questions.length ? `<ul class="archive-list compact-list question-list">${questions.map((item) => `<li><span>${escapeHtml(item.text)} · 来源第 ${item.source_chapter_number} 章</span></li>`).join("")}</ul>` : `<p class="archive-empty-note">暂无疑问点。</p>`}</section>`;
    const snapshots = state.workspace?.active_version?.archive?.snapshots || [];
    elements.archiveSnapshotSelect.innerHTML = `<option value="">最新状态</option>${snapshots.map((snapshot) => `<option value="${snapshot.chapter_number}" ${String(selectedChapterNumber) === String(snapshot.chapter_number) ? "selected" : ""}>第 ${snapshot.chapter_number} 章快照</option>`).join("")}`;
  }

  function renderEditorWorkspace() {
    const workspace = state.workspace;
    const version = activeEditorVersion();
    if (!workspace || !version) return;
    const selectedByLocation = chooseActiveChapter(version);
    const activeChapterInVersion = version.chapters.find((chapter) => chapter.chapter_id === state.activeChapterId);
    if (!activeChapterInVersion || (!state.editorDirty && selectedByLocation && selectedByLocation.chapter_id !== state.activeChapterId)) {
      state.activeChapterId = selectedByLocation?.chapter_id || null;
      state.editorDirty = false;
      state.editorConflict = null;
      state.editorSaveFailed = false;
      state.editorSavedRevision = null;
      syncActiveChapterUrl(state.activeChapterId);
    }
    elements.startWorkspaceContent.classList.add("is-hidden");
    elements.editorWorkspaceContent.classList.remove("is-hidden");
    elements.editorProjectTitle.textContent = workspace.title || "—";
    const aiEditor = workspace.mode === "ai_assisted" || state.editorMode === "ai_assisted";
    elements.editorModeLabel.textContent = aiEditor ? "AI 辅助写作" : "独立创作";
    elements.writingModeNote.textContent = aiEditor ? "AI 辅助写作 · 唯一正式正文" : "独立创作 · 正式正文";
    const chapter = version.chapters.find((item) => item.chapter_id === state.activeChapterId);
    if (!chapter) return;
    if (!state.editorDirty) {
      state.editorBuffer = chapter.content || "";
      state.editorTitleBuffer = chapter.title || "";
      state.editorRevision = chapter.server_revision || 0;
      state.editorSavedRevision = chapter.server_revision || 0;
    }
    elements.editorChapterHeading.textContent = chapter.title || `第${chapter.chapter_number}章`;
    elements.chapterTitleInput.value = state.editorTitleBuffer;
    elements.chapterEditor.value = state.editorBuffer;
    elements.editorWordCount.textContent = `${countEditorWords(state.editorBuffer).toLocaleString("zh-CN")} 字`;
    elements.editorRevisionLabel.textContent = `REV / ${state.editorRevision}`;
    renderChapterList(version);
    renderArchiveSummary(state.activeArchive || workspace.archive);
    if (workspace.pending_changes?.changes?.length) {
      setEditorNoticeHtml(`<strong>有 ${workspace.pending_changes.changes.length} 章旧稿修改等待确认。</strong><button class="notice-action" type="button" data-action="review-changes">确认全部修改 →</button>`);
    } else if (!state.editorConflict && !state.editorSaving) {
      elements.editorNotice.classList.add("is-hidden");
    }
    const latestTask = (workspace.tasks || []).find((task) => task.version_id === version.version_id && ["queued", "running", "failed"].includes(task.status));
    const taskRunning = Boolean(latestTask && ["queued", "running"].includes(latestTask.status));
    const completedCurrent = chapter.status === "ready" && !state.editorDirty && !taskRunning;
    elements.completeChapterButton.dataset.nextChapter = completedCurrent ? "true" : "false";
    elements.completeChapterButton.textContent = completedCurrent ? "新建下一章 →" : "完成本章 →";
    elements.completeChapterButton.disabled = state.completeInFlight
      || state.addChapterInFlight
      || state.editorReadOnly
      || (!completedCurrent && !state.editorBuffer.trim())
      || taskRunning;
    if (latestTask && latestTask.status === "failed") {
      setEditorNoticeHtml(`<strong>后台分析失败。</strong> ${escapeHtml(latestTask.error_message || "可以修改正文后重试。")} <button class="notice-action" type="button" data-action="retry-task" data-task-id="${escapeHtml(latestTask.task_id)}">重试 →</button>`, "red");
      setEditorAnalysisState("分析失败", "error");
    } else if (taskRunning) {
      setEditorAnalysisState("分析中…", "saving");
      scheduleIndependentTaskPoll(latestTask.task_id);
    } else {
      setEditorAnalysisState(chapter.status === "ready" ? "已分析" : "写作中", chapter.status === "ready" ? "saved" : "");
    }
    if (state.editorSaving) {
      setEditorSaveState("保存中…", "saving");
    } else if (state.editorConflict) {
      setEditorSaveState("保存冲突", "error");
    } else if (state.editorDirty) {
      setEditorSaveState(state.editorSaveFailed ? "保存失败" : "本地待保存", state.editorSaveFailed ? "error" : "");
    } else if (state.editorSaveFailed) {
      setEditorSaveState("保存失败", "error");
    } else if (state.editorSavedRevision !== null && Number(state.editorSavedRevision) === Number(chapter.server_revision || 0)) {
      setEditorSaveState("已保存", "saved");
    } else {
      setEditorSaveState("等待保存");
    }
  }

  function handleEditorInput() {
    if (state.editorReadOnly) return;
    state.editorBuffer = elements.chapterEditor.value;
    state.editorTitleBuffer = elements.chapterTitleInput.value;
    state.editorDirty = true;
    state.editorChangeToken += 1;
    state.editorConflict = null;
    state.editorSaveFailed = false;
    elements.editorWordCount.textContent = `${countEditorWords(state.editorBuffer).toLocaleString("zh-CN")} 字`;
    // 已完成章节被重新编辑后，主动作必须回到完成门禁，不能继续显示新建下一章。
    elements.completeChapterButton.dataset.nextChapter = "false";
    elements.completeChapterButton.textContent = "完成本章 →";
    elements.completeChapterButton.disabled = !state.editorBuffer.trim();
    setEditorSaveState("本地待保存");
    window.clearTimeout(state.saveTimer);
    state.saveTimer = window.setTimeout(() => { flushPendingSave(); }, 720);
  }

  function renderSaveConflict(error) {
    state.editorConflict = error.data?.chapter || null;
    setEditorSaveState("保存冲突", "error");
    setEditorNoticeHtml(`<strong>另一端已经保存了这章。</strong> 当前草稿没有被静默覆盖。<button class="notice-action" type="button" data-action="reload-server">载入服务器版本</button><button class="notice-action" type="button" data-action="keep-local">保留当前草稿并重试</button>`, "red");
  }

  async function flushPendingSave({ keepalive = false } = {}) {
    window.clearTimeout(state.saveTimer);
    while (state.editorDirty || state.editorSaving) {
      if (state.savePromise) {
        const completed = await state.savePromise;
        if (!completed) return false;
        continue;
      }
      if (!state.editorDirty) return true;
      const completed = await saveEditorDraft({ keepalive });
      if (!completed) return false;
    }
    return true;
  }

  async function saveEditorDraft({ keepalive = false } = {}) {
    const projectId = state.editorProjectId;
    const chapterId = state.activeChapterId;
    const localContent = state.editorBuffer;
    const localTitle = state.editorTitleBuffer;
    const expectedRevision = state.editorRevision;
    const changeToken = state.editorChangeToken;
    state.editorSaving = true;
    setEditorSaveState("保存中…", "saving");
    const promise = (async () => {
      try {
        const payload = await requestJson(`/api/independent/projects/${encodeURIComponent(projectId)}/chapters/${encodeURIComponent(chapterId)}/draft`, {
          method: "PUT",
          keepalive,
          body: JSON.stringify({ content: localContent, title: localTitle, expected_revision: expectedRevision }),
        });
        state.workspace = payload.workspace;
        state.activeArchive = payload.workspace.archive;
        state.editorRevision = payload.chapter.server_revision;
        state.editorSavedRevision = payload.chapter.server_revision;
        state.editorConflict = null;
        state.editorSaveFailed = false;
        if (state.editorChangeToken === changeToken) {
          state.editorDirty = false;
          setEditorSaveState("已保存", "saved");
        } else {
          // 保存请求期间又有输入：只更新 revision，保留新缓冲并让 flush 再写一次。
          state.editorDirty = true;
          setEditorSaveState("本地待保存", "");
        }
        renderEditorWorkspace();
        return true;
      } catch (error) {
        if (error.code === "save_conflict") renderSaveConflict(error);
        else setEditorNotice(error.message || "保存失败，可以稍后重试。", "red");
        state.editorSaveFailed = true;
        setEditorSaveState("保存失败", "error");
        return false;
      } finally {
        state.editorSaving = false;
        state.savePromise = null;
        if (state.workspace?.initialized) renderEditorWorkspace();
      }
    })();
    state.savePromise = promise;
    return promise;
  }

  function handleCompleteButtonClick() {
    if (state.completeInFlight) return;
    if (elements.completeChapterButton.dataset.nextChapter === "true") {
      void addIndependentChapter();
      return;
    }
    void completeCurrentChapter();
  }

  async function completeCurrentChapter() {
    if (state.editorReadOnly || state.completeInFlight) return;
    state.completeInFlight = true;
    const button = elements.completeChapterButton;
    button.disabled = true;
    const saved = await flushPendingSave();
    if (!saved || state.editorDirty) {
      state.completeInFlight = false;
      renderEditorWorkspace();
      return;
    }
    setEditorAnalysisState("分析中…", "saving");
    try {
      const payload = await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/chapters/${encodeURIComponent(state.activeChapterId)}/complete`, {
        method: "POST",
        body: JSON.stringify({ content: state.editorBuffer, expected_revision: state.editorRevision, idempotency_key: `browser-${state.activeChapterId}-${state.editorRevision}` }),
      });
      await pollIndependentTask(payload.task.task_id);
    } catch (error) {
      setEditorNotice(error.message || "完成本章没有提交成功，请确认正文已经保存。", "red");
      setEditorAnalysisState("完成失败", "error");
    } finally {
      state.completeInFlight = false;
      if (state.workspace?.initialized) renderEditorWorkspace();
    }
  }

  function wait(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  async function pollIndependentTask(taskId) {
    for (let attempt = 0; attempt < 50; attempt += 1) {
      const payload = await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/tasks/${encodeURIComponent(taskId)}`);
      if (payload.task.status === "completed") {
        const stillInEditor = state.screen === "independent";
        if (stillInEditor) {
          await loadIndependentWorkspace(state.editorProjectId);
          setEditorNotice("本章完成，故事档案已更新；来源章节已记录。", "blue");
          showToast("本章已完成，档案快照已保存。");
        }
        return;
      }
      if (payload.task.status === "failed") {
        if (state.screen === "independent") {
          await loadIndependentWorkspace(state.editorProjectId);
          setEditorNoticeHtml(`<strong>后台分析失败。</strong> ${escapeHtml(payload.task.error_message || "可以修改正文后重试。")} <button class="notice-action" type="button" data-action="retry-task" data-task-id="${escapeHtml(taskId)}">重试 →</button>`, "red");
        }
        return;
      }
      await wait(260);
    }
    setEditorNotice("后台分析仍在运行，离开或刷新后会继续恢复。", "blue");
  }

  function scheduleIndependentTaskPoll(taskId) {
    if (!taskId || state.editorTaskPollTimer || state.screen !== "independent") return;
    state.editorTaskPollTimer = window.setTimeout(async () => {
      state.editorTaskPollTimer = null;
      if (state.screen !== "independent") return;
      try {
        const payload = await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/tasks/${encodeURIComponent(taskId)}`);
        if (payload.task.status === "completed" || payload.task.status === "failed") {
          await loadIndependentWorkspace(state.editorProjectId);
          if (payload.task.status === "completed") setEditorNotice("本章完成，故事档案已更新；来源章节已记录。", "blue");
          return;
        }
        scheduleIndependentTaskPoll(taskId);
      } catch (error) {
        setEditorNotice(error.message || "后台分析状态暂时读不到，稍后会自动重试。", "red");
        scheduleIndependentTaskPoll(taskId);
      }
    }, 900);
  }

  async function retryIndependentTask(taskId) {
    try {
      const payload = await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/tasks/${encodeURIComponent(taskId)}/retry`, { method: "POST" });
      if (payload.task.status === "completed") {
        await loadIndependentWorkspace(state.editorProjectId);
        setEditorNotice("分析重试完成，故事档案已更新。", "blue");
      } else {
        await pollIndependentTask(taskId);
      }
    } catch (error) {
      setEditorNotice(error.message || "重试没有完成。", "red");
    }
  }

  async function selectEditorChapter(chapterId) {
    if (chapterId === state.activeChapterId) return;
    if (state.editorDirty) {
      const saved = await flushPendingSave();
      if (!saved) return;
    }
    state.activeChapterId = chapterId;
    state.editorDirty = false;
    state.editorConflict = null;
    state.editorSaveFailed = false;
    state.editorSavedRevision = null;
    updateChapterUrl(chapterId);
    renderEditorWorkspace();
  }

  async function addIndependentChapter() {
    if (state.completeInFlight || state.addChapterInFlight) return;
    state.addChapterInFlight = true;
    elements.completeChapterButton.disabled = true;
    try {
      if (state.editorDirty && !(await flushPendingSave())) return;
      const payload = await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/chapters`, { method: "POST" });
      const newChapterId = payload.chapter.chapter_id;
      state.activeChapterId = newChapterId;
      state.editorDirty = false;
      state.editorConflict = null;
      state.editorSaveFailed = false;
      state.editorSavedRevision = null;
      updateChapterUrl(newChapterId);
      await loadIndependentWorkspace(state.editorProjectId);
      focusChapterTitle();
      showToast("新章节已加入目录。");
    } catch (error) {
      setEditorNotice(error.message || "新章节创建失败。", "red");
    } finally {
      state.addChapterInFlight = false;
      if (state.workspace?.initialized) renderEditorWorkspace();
    }
  }

  function openPendingChangesDialog() {
    const changes = state.workspace?.pending_changes?.changes || [];
    elements.pendingChangesContent.innerHTML = changes.length ? `<div class="change-summary-list">${changes.map((change) => `<article><div><span class="mono">第 ${change.chapter_number} 章</span><strong>${escapeHtml(change.title)}</strong></div><p>${change.before_word_count} 字 → ${change.after_word_count} 字（${change.delta_word_count >= 0 ? "+" : ""}${change.delta_word_count}）</p><small>${escapeHtml(change.changed_ranges?.join("；") || "改动范围已记录")} · ${escapeHtml(change.recommendation)}</small></article>`).join("")}</div>` : `<p class="archive-empty-note">当前没有待确认的旧章修改。</p>`;
    rememberDialogFocus(elements.pendingChangesDialog);
    if (typeof elements.pendingChangesDialog.showModal === "function") elements.pendingChangesDialog.showModal();
    else elements.pendingChangesDialog.setAttribute("open", "");
  }

  async function resolvePendingChanges(decision) {
    elements.ignoreChangesButton.disabled = true;
    elements.rebuildChangesButton.disabled = true;
    try {
      const payload = await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/pending-changes/resolve`, { method: "POST", body: JSON.stringify({ decision }) });
      elements.pendingChangesDialog.close();
      state.workspace = payload.workspace;
      state.activeArchive = payload.workspace.archive;
      await loadIndependentWorkspace(state.editorProjectId);
      showToast(decision === "ignore" ? "已保留现有档案并继续。" : "已创建新稿本，档案开始全文重建。");
    } catch (error) {
      setEditorNotice(error.message || "修改确认没有完成。", "red");
    } finally {
      elements.ignoreChangesButton.disabled = false;
      elements.rebuildChangesButton.disabled = false;
    }
  }

  function openVersionHistoryDialog() {
    const versions = state.workspace?.versions || [];
    state.versionPreviewId = null;
    state.versionPreview = null;
    state.restoreConfirmVersionId = null;
    elements.versionHistoryContent.innerHTML = versions.length ? versions.map((version) => `
      <article class="version-history-item ${version.status === "active" ? "is-active" : ""}">
        <div><span class="eyebrow">${escapeHtml(version.status === "active" ? "当前稿本" : "历史稿本")}</span><strong>${escapeHtml(version.label)}</strong><small>${version.chapter_count} 章 · ${Number(version.total_word_count || 0).toLocaleString("zh-CN")} 字 · ${escapeHtml(formatDate(version.created_at))}</small></div>
        <div class="version-actions"><button type="button" class="quiet-link" data-action="preview-version" data-version-id="${escapeHtml(version.version_id)}">只读预览</button></div>
      </article>`).join("") : `<p class="archive-empty-note">还没有历史稿本。</p>`;
    elements.versionPreviewContent.classList.add("is-hidden");
    rememberDialogFocus(elements.versionHistoryDialog);
    if (typeof elements.versionHistoryDialog.showModal === "function") elements.versionHistoryDialog.showModal();
    else elements.versionHistoryDialog.setAttribute("open", "");
  }

  async function previewVersion(versionId) {
    try {
      const payload = await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/versions/${encodeURIComponent(versionId)}/preview`);
      const version = payload.version;
      state.versionPreviewId = version.version_id || versionId;
      state.versionPreview = version;
      const chapters = Array.isArray(version.chapters) ? version.chapters : [];
      const totalWords = chapters.reduce((sum, chapter) => sum + Number(chapter.word_count || countEditorWords(chapter.content || chapter.formal_content || "")), 0);
      const canRestore = version.status !== "active";
      elements.versionPreviewContent.classList.remove("is-hidden");
      // version.chapters.map 逐章渲染完整、可滚动的只读正文，避免只展示首章摘录。
      elements.versionPreviewContent.innerHTML = `<div class="version-preview-head"><div><span class="eyebrow">只读预览 / ${escapeHtml(version.label)}</span><h3 id="versionPreviewTitle" tabindex="-1">${escapeHtml(version.label || "稿本预览")}</h3></div><strong>${chapters.length} 章 · ${totalWords.toLocaleString("zh-CN")} 字</strong></div><div class="version-preview-chapters">${chapters.map((chapter) => `<article class="version-preview-chapter"><header><strong>第 ${chapter.chapter_number} 章 · ${escapeHtml(chapter.title || `第${chapter.chapter_number}章`)}</strong><span>${Number(chapter.word_count || countEditorWords(chapter.content || chapter.formal_content || "")).toLocaleString("zh-CN")} 字 · ${escapeHtml(chapter.status === "ready" ? "已完成" : "草稿")}</span></header><div class="version-preview-body" tabindex="0">${escapeHtml(chapter.content || chapter.formal_content || "") || "这章还没有正文。"}</div></article>`).join("") || `<p class="archive-empty-note">这条稿本还没有章节正文。</p>`}</div><div class="version-preview-actions"><small>历史正文不会被本次预览改写。恢复时会创建新的当前稿本。</small>${canRestore ? `<button type="button" class="button button-outline" data-action="open-restore-confirm" data-version-id="${escapeHtml(state.versionPreviewId)}">打开恢复确认</button>` : `<span class="archive-empty-note">当前稿本无需恢复。</span>`}</div>`;
      focusVersionPreviewTitle();
    } catch (error) {
      setEditorNotice(error.message || "历史稿本预览失败。", "red");
    }
  }

  async function restoreVersion(versionId) {
    if (!versionId || versionId !== state.versionPreviewId || state.versionPreview?.status === "active") return;
    openRestoreVersionConfirm(versionId);
  }

  function openRestoreVersionConfirm(versionId = state.versionPreviewId) {
    if (!versionId || versionId !== state.versionPreviewId || !state.versionPreview || state.versionPreview.status === "active") return;
    state.restoreConfirmVersionId = versionId;
    const version = state.versionPreview;
    const chapters = Array.isArray(version.chapters) ? version.chapters : [];
    const totalWords = chapters.reduce((sum, chapter) => sum + Number(chapter.word_count || countEditorWords(chapter.content || chapter.formal_content || "")), 0);
    elements.restoreVersionTitle.textContent = "恢复确认";
    elements.restoreVersionContent.innerHTML = `<p><strong>${escapeHtml(version.label || "历史稿本")}</strong> 将作为新的当前稿本恢复。</p><dl class="restore-version-facts"><div><dt>作品</dt><dd>${escapeHtml(state.workspace?.title || "当前作品")}</dd></div><div><dt>章节</dt><dd>${chapters.length} 章</dd></div><div><dt>正文</dt><dd>${totalWords.toLocaleString("zh-CN")} 字</dd></div></dl><p class="restore-version-warning">恢复会创建新的当前稿本，保留现有当前稿本和这条历史记录；确认后将创建新的当前稿本。</p>`;
    elements.restoreVersionDialog.dataset.requestCount = "0";
    rememberDialogFocus(elements.restoreVersionDialog);
    if (typeof elements.restoreVersionDialog.showModal === "function" && !elements.restoreVersionDialog.open) elements.restoreVersionDialog.showModal();
    else elements.restoreVersionDialog.setAttribute("open", "");
    window.setTimeout(() => elements.restoreVersionTitle?.focus(), 0);
  }

  async function confirmRestoreVersion() {
    const versionId = state.restoreConfirmVersionId;
    if (!versionId || versionId !== state.versionPreviewId || state.restoreInFlight) return;
    state.restoreInFlight = true;
    const button = elements.confirmRestoreVersionButton;
    if (button) button.disabled = true;
    if (elements.restoreVersionDialog) {
      const requests = Number(elements.restoreVersionDialog.dataset.requestCount || 0) + 1;
      elements.restoreVersionDialog.dataset.requestCount = String(requests);
    }
    try {
      await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/versions/${encodeURIComponent(versionId)}/restore`, { method: "POST" });
      elements.restoreVersionDialog.close();
      elements.versionHistoryDialog.close();
      state.versionPreviewId = null;
      state.versionPreview = null;
      await loadIndependentWorkspace(state.editorProjectId);
      showToast("历史正文已恢复为新的当前稿本。");
    } catch (error) {
      setEditorNotice(error.message || "历史稿本恢复失败。", "red");
    } finally {
      state.restoreInFlight = false;
      if (button) button.disabled = false;
    }
  }

  async function selectArchiveSnapshot(chapterNumber) {
    if (!chapterNumber) {
      renderArchiveSummary(state.workspace?.archive || state.activeArchive);
      return;
    }
    try {
      const payload = await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/archive?chapter_number=${encodeURIComponent(chapterNumber)}`);
      renderArchiveSummary(payload.archive, payload.selected_chapter_number);
    } catch (error) {
      setEditorNotice(error.message || "档案快照读取失败。", "red");
    }
  }

  function openTrialDialog(characterId) {
    state.trialCharacterId = characterId;
    elements.trialEstimate.textContent = "预计 12 积分 · 未配置图片服务";
    rememberDialogFocus(elements.trialDialog);
    if (typeof elements.trialDialog.showModal === "function") elements.trialDialog.showModal();
    else elements.trialDialog.setAttribute("open", "");
  }

  async function confirmTrialSketch() {
    try {
      await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/characters/${encodeURIComponent(state.trialCharacterId)}/trial-sketch`, { method: "POST", body: JSON.stringify({ style: elements.trialStyleSelect.value, confirm: true }) });
    } catch (error) {
      if (error.code === "image_service_unconfigured") {
        elements.trialDialog.close();
        setEditorNotice(error.message || "未配置图片服务，试绘未触发，也未扣除积分。", "blue");
        showToast("试绘未触发，没有扣除积分。");
      } else {
        setEditorNotice(error.message || "试绘请求没有完成。", "red");
      }
    }
  }

  function setWorkspaceNotice(element, message, variant = "") {
    if (!element) return;
    element.textContent = message || "";
    element.className = `notice ${message ? "" : "is-hidden"} ${variant ? `notice-${variant}` : "notice-blue"}`;
  }

  function setWorkspaceNoticeHtml(element, html, variant = "") {
    if (!element) return;
    element.innerHTML = html || "";
    element.className = `notice ${html ? "" : "is-hidden"} ${variant ? `notice-${variant}` : "notice-blue"}`;
  }

  function archiveModeLabel(mode) {
    return mode === "ai_assisted" ? "AI 辅助写作" : "独立创作";
  }

  function archiveAnalysisLabel(value) {
    const label = String(value || "").trim();
    if (!label || label.includes("确定性演示分析") || label.includes("未配置模型 Key")) return "演示分析";
    return label;
  }

  const deconstructionStatusText = Object.freeze({
    empty: "等待正文",
    queued: "已排队",
    running: "拆解中",
    completed: "已完成",
    failed_retryable: "可重试",
    stale: "结果已过期",
    rebuild_required: "需要确认",
  });

  const deconstructionStatusMessages = Object.freeze({
    empty: "先完成并保存至少一章正文，作品拆解才有足够材料。",
    queued: "任务已经进入服务端队列；你可以离开页面，回来后继续查看。",
    running: "正在从当前正式正文提取结构与证据，结果完成前不会覆盖正文。",
    completed: "这版拆解已绑定当前稿本，可以沿时间线回到原文证据。",
    failed_retryable: "这次拆解没有完成，正文没有被修改；可以重试。",
    stale: "当前正式正文已经变化，这版结果只保留作历史参考，需要生成新版本。",
    rebuild_required: "当前作者修改尚未确认，请先回正文处理待确认修改。",
  });

  const deconstructionStatusSet = new Set(Object.keys(deconstructionStatusText));
  const deconstructionRunStatusSet = new Set(["none", "queued", "running", "completed", "failed_retryable"]);
  const DECONSTRUCTION_OFFSET_UNIT = "utf16_code_unit";

  /*
   * 作品拆解 API adapter
   *
   * 这里刻意只读取 31D 的顶层 canonical contract。兼容投影仍由服务端
   * 返回给旧客户端，但新页面不从 nested status、document 或旧别名猜状态。
   */
  const deconstructionApi = Object.freeze({
    workspace: (projectId) => `/api/independent/projects/${encodeURIComponent(projectId)}/deconstruction`,
    action: (projectId, action) => `/api/independent/projects/${encodeURIComponent(projectId)}/deconstruction/${action}`,
    evidence: (projectId, evidenceId) => `/api/independent/projects/${encodeURIComponent(projectId)}/deconstruction/evidence/${encodeURIComponent(evidenceId)}`,
    async read(projectId) {
      return normalizeDeconstructionResponse(await requestJson(this.workspace(projectId)));
    },
    async mutate(projectId, action, payload) {
      return normalizeDeconstructionResponse(await requestJson(this.action(projectId, action), {
        method: "POST",
        body: JSON.stringify(payload || {}),
      }));
    },
    async readEvidence(projectId, evidenceId) {
      return requestJson(this.evidence(projectId, evidenceId));
    },
  });

  function deconstructionNumber(value) {
    if (value === undefined || value === null || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  // Nullable Depth fields must preserve an explicit unknown.  Do not coerce
  // null, booleans, or numeric strings into a plotted zero.
  function deconstructionNullableNumber(value) {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }

  function deconstructionEvidenceExcerptMatches(evidence, content) {
    if (!evidence || typeof content !== "string" || typeof evidence.excerpt !== "string") return false;
    if (evidence.offsetUnit !== DECONSTRUCTION_OFFSET_UNIT
      || !Number.isInteger(evidence.charStart)
      || !Number.isInteger(evidence.charEnd)
      || evidence.charStart < 0
      || evidence.charEnd < evidence.charStart
      || evidence.charEnd > content.length) return false;
    return content.slice(evidence.charStart, evidence.charEnd) === evidence.excerpt;
  }

  function deconstructionText(value, fallback = "") {
    const text = String(value ?? "").trim();
    return text || fallback;
  }

  function deconstructionStringList(value) {
    return Array.isArray(value)
      ? value.map((item) => deconstructionText(item)).filter(Boolean)
      : [];
  }

  function normalizedConfidence(value) {
    const number = deconstructionNumber(value);
    if (number === null) return { value: null, label: "待确认" };
    const percent = Math.round(Math.max(0, Math.min(1, number)) * 100);
    return { value: percent, label: percent >= 80 ? "高置信度" : percent >= 55 ? "中等置信度" : "低置信度" };
  }

  function normalizeEvidenceRef(ref) {
    if (!ref || typeof ref !== "object" || !ref.evidence_id) return null;
    return {
      id: String(ref.evidence_id),
      documentId: String(ref.document_id || ""),
      sourceVersionId: String(ref.source_version_id || ""),
      sourceRevision: deconstructionNumber(ref.source_revision),
      sourceHash: String(ref.source_hash || ""),
      chapterId: String(ref.chapter_id || ""),
      chapterNumber: deconstructionNumber(ref.chapter_number),
      granularity: ref.granularity === "chapter" ? "chapter" : "span",
      charStart: deconstructionNumber(ref.start_offset),
      charEnd: deconstructionNumber(ref.end_offset),
      offsetUnit: String(ref.offset_unit || ""),
      excerpt: typeof ref.excerpt === "string" ? ref.excerpt : "",
      label: deconstructionText(ref.label, "正文证据"),
      targetPath: ref.target_path ? String(ref.target_path) : "",
    };
  }

  function normalizeEvidenceRefs(value) {
    return Array.isArray(value) ? value.map(normalizeEvidenceRef).filter(Boolean) : [];
  }

  function normalizeObservation(value, label) {
    const item = value && typeof value === "object" ? value : {};
    return {
      label,
      text: deconstructionText(item.text, "不确定：当前正文尚不足以判断。"),
      confidence: normalizedConfidence(item.confidence),
      uncertainty: deconstructionStringList(item.uncertainty),
      evidenceRefs: normalizeEvidenceRefs(item.evidence_refs),
    };
  }

  function normalizeCandidate(value) {
    if (!value || typeof value !== "object" || !deconstructionText(value.value)) return null;
    return {
      value: deconstructionText(value.value),
      label: deconstructionText(value.label, "候选"),
      confidence: normalizedConfidence(value.confidence),
      uncertainty: deconstructionStringList(value.uncertainty),
      evidenceRefs: normalizeEvidenceRefs(value.evidence_refs),
    };
  }

  function normalizeOverview(value) {
    const overview = value && typeof value === "object" ? value : {};
    return {
      title: deconstructionText(overview.title, "未命名作品"),
      wordCount: deconstructionNumber(overview.total_word_count),
      chapterCount: deconstructionNumber(overview.chapter_count),
      structureUnits: deconstructionStringList(overview.structure_units),
      mainCharacters: Array.isArray(overview.main_character_candidates) ? overview.main_character_candidates.map(normalizeCandidate).filter(Boolean) : [],
      coreConflicts: Array.isArray(overview.core_conflict_candidates) ? overview.core_conflict_candidates.map(normalizeCandidate).filter(Boolean) : [],
      structure: [
        ["开端", overview.opening],
        ["发展", overview.development],
        ["高潮", overview.climax],
        ["结尾", overview.ending],
      ].map(([label, item]) => normalizeObservation(item, label)),
      uncertainties: deconstructionStringList(overview.uncertainty),
    };
  }

  function normalizeTimelineNode(value, index) {
    const item = value && typeof value === "object" ? value : {};
    return {
      id: String(item.node_id || `timeline-${index + 1}`),
      normalizedStart: deconstructionNumber(item.normalized_start),
      normalizedEnd: deconstructionNumber(item.normalized_end),
      chapterId: String(item.chapter_id || ""),
      chapterNumber: deconstructionNumber(item.chapter_number),
      chapterTitle: deconstructionText(item.chapter_title),
      wordStart: deconstructionNumber(item.word_start),
      wordEnd: deconstructionNumber(item.word_end),
      title: deconstructionText(item.label, "结构节点"),
      event: deconstructionText(item.event, "不确定：正文片段不足以判断事件。"),
      narrativeFunction: deconstructionText(item.narrative_function, "不确定"),
      characters: deconstructionStringList(item.characters),
      confidence: normalizedConfidence(item.confidence),
      uncertainty: deconstructionStringList(item.uncertainty),
      evidenceRefs: normalizeEvidenceRefs(item.evidence_refs),
    };
  }

  function normalizeChapterBreakdown(value) {
    const item = value && typeof value === "object" ? value : {};
    return {
      chapterId: String(item.chapter_id || ""),
      chapterNumber: deconstructionNumber(item.chapter_number),
      title: deconstructionText(item.title, "待命名章节"),
      summary: deconstructionText(item.summary, "不确定：当前章节还没有可提炼的摘要。"),
      coreEvents: deconstructionStringList(item.core_events),
      narrativeFunction: deconstructionText(item.narrative_function, "不确定"),
      scenes: deconstructionStringList(item.scenes),
      conflict: deconstructionText(item.conflict, "不确定"),
      informationRelease: deconstructionText(item.information_release, "不确定"),
      relationshipChange: deconstructionText(item.relationship_change, "不确定"),
      emotionalChange: deconstructionText(item.emotional_change, "不确定"),
      foreshadowing: deconstructionStringList(item.foreshadowing),
      openingHook: deconstructionText(item.opening_hook, "不确定"),
      endingHook: deconstructionText(item.ending_hook, "不确定"),
      confidence: normalizedConfidence(item.confidence),
      uncertainty: deconstructionStringList(item.uncertainty),
      evidenceRefs: normalizeEvidenceRefs(item.evidence_refs),
    };
  }

  const depthPerspectiveMeta = Object.freeze({
    overview: {
      label: "总览",
      title: "拆解总览",
      description: "先看六个视角如何共同落在同一份正文和证据上。",
    },
    characters: {
      label: "人物与人物弧",
      title: "人物与人物弧",
      description: "按阅读进度回看人物状态、动机和关系如何变化。",
    },
    plot: {
      label: "剧情线与事件因果",
      title: "剧情线与事件因果",
      description: "把事件的叙述顺序、故事时间和因果解释分开呈现。",
    },
    foreshadowing: {
      label: "伏笔与回收",
      title: "伏笔与回收",
      description: "沿着铺垫、强化、回收或改写的状态轨迹回看。",
    },
    rhythm: {
      label: "章节结构与节奏",
      title: "章节结构与节奏",
      description: "节奏指标共用正文的 0–100 阅读轴，未知值保持未知。",
    },
    reader: {
      label: "读者体验",
      title: "读者体验",
      description: "回看期待、信息差、情绪影响和回收感怎样推进。",
    },
    technique: {
      label: "文笔与叙事技法",
      title: "文笔与叙事技法",
      description: "每项技法都同时给出观察、例证、学习说明和适用边界。",
    },
  });

  const depthPerspectiveOrder = Object.freeze([
    "overview", "characters", "plot", "foreshadowing", "rhythm", "reader", "technique",
  ]);

  const depthRelationText = Object.freeze({
    allies: "结盟",
    opposes: "对立",
    depends_on: "依赖",
    changes_to: "状态变化为",
    causes: "促成",
    enables: "使……成为可能",
    prevents: "阻止",
    precedes: "叙述上先于",
    parallel_to: "与……并行",
    intersects: "交汇",
    plants: "埋下",
    reinforces: "强化",
    pays_off: "回收",
    subverts: "改写预期",
  });

  const depthTemporalModeText = Object.freeze({
    linear: "线性时间",
    flashback: "倒叙",
    flashforward: "预叙",
    parallel: "并行线",
    unknown: "故事时间未知",
  });

  const depthPlotStatusText = Object.freeze({
    introduced: "引入",
    developing: "发展",
    turning: "转折",
    resolved: "已解决",
    open: "仍开放",
    unknown: "状态未知",
  });

  const depthForeshadowingStatusText = Object.freeze({
    planted: "已埋下",
    reinforced: "已强化",
    paid_off: "已回收",
    subverted: "预期被改写",
    unresolved: "尚未回收",
    unknown: "状态未知",
  });

  const depthEpistemicStatusText = Object.freeze({
    observed: "正文观察",
    inferred: "基于证据推断",
    unknown: "证据状态未知",
  });

  function normalizeDepthSource(value) {
    const source = value && typeof value === "object" ? value : {};
    return {
      projectId: String(source.project_id || ""),
      documentId: String(source.document_id || ""),
      versionId: String(source.source_version_id || ""),
      revision: deconstructionNumber(source.source_revision),
      contentHash: String(source.source_hash || ""),
    };
  }

  function normalizeDepthChapter(value) {
    const chapter = value && typeof value === "object" ? value : {};
    return {
      id: String(chapter.chapter_id || ""),
      number: deconstructionNumber(chapter.chapter_number),
      title: deconstructionText(chapter.title, "未命名章节"),
      utf16Length: deconstructionNumber(chapter.utf16_length),
      start: deconstructionNumber(chapter.normalized_start),
      end: deconstructionNumber(chapter.normalized_end),
    };
  }

  function normalizeDepthItem(value, extra = {}) {
    const item = value && typeof value === "object" ? value : {};
    const epistemicStatus = ["observed", "inferred", "unknown"].includes(item.epistemic_status)
      ? item.epistemic_status
      : "unknown";
    return {
      id: String(item.item_id || ""),
      kind: String(item.kind || ""),
      category: deconstructionText(item.category, "结论"),
      conclusion: deconstructionText(item.conclusion, "不确定：当前正文证据不足。"),
      epistemicStatus,
      chapterIds: deconstructionStringList(item.chapter_ids),
      normalizedStart: deconstructionNumber(item.normalized_start),
      normalizedEnd: deconstructionNumber(item.normalized_end),
      evidenceIds: deconstructionStringList(item.evidence_ids),
      relatedItemIds: deconstructionStringList(item.related_item_ids),
      confidence: epistemicStatus === "unknown" ? normalizedConfidence(null) : normalizedConfidence(item.confidence),
      uncertainty: deconstructionStringList(item.uncertainty),
      ...extra,
    };
  }

  function normalizeDepthEndpoint(value) {
    const endpoint = value && typeof value === "object" ? value : {};
    return { id: String(endpoint.item_id || ""), kind: String(endpoint.kind || "") };
  }

  function normalizeDepthRelation(value) {
    const item = value && typeof value === "object" ? value : {};
    return normalizeDepthItem(item, {
      start: normalizeDepthEndpoint(item.start),
      end: normalizeDepthEndpoint(item.end),
      relationType: String(item.relation_type || ""),
      explanation: deconstructionText(item.explanation, "不确定：关系解释证据不足。"),
    });
  }

  function normalizeDepthView(value) {
    const view = value && typeof value === "object" ? value : {};
    return {
      summary: deconstructionText(view.summary, "当前视角还没有足够证据形成摘要。"),
      uncertainty: deconstructionStringList(view.uncertainty),
    };
  }

  function normalizeDepthReport(value) {
    if (!value || typeof value !== "object" || value.report_version !== "2.0") return null;
    const requiredViews = ["characters", "plot", "foreshadowing", "rhythm", "reader_experience", "technique"];
    if (!value.source || !Array.isArray(value.chapters) || !value.chapters.length
      || !Array.isArray(value.evidence) || !value.evidence.length
      || requiredViews.some((key) => !value[key] || typeof value[key] !== "object")) return null;
    const source = normalizeDepthSource(value.source);
    if (!source.projectId || !source.documentId || !source.versionId || source.revision === null || !source.contentHash) return null;
    const chapters = value.chapters.map(normalizeDepthChapter).filter((chapter) => chapter.id);
    const evidence = value.evidence.map(normalizeEvidenceRef).filter(Boolean);
    if (!chapters.length || !evidence.length
      || chapters.some((chapter) => chapter.number === null || chapter.utf16Length === null || chapter.start === null || chapter.end === null)
      || evidence.some((item) => item.documentId !== source.documentId
        || item.sourceVersionId !== source.versionId
        || item.sourceRevision !== source.revision
        || item.sourceHash !== source.contentHash)) return null;
    if (!Array.isArray(value.rhythm.items) || !value.rhythm.items.length
      || !Array.isArray(value.reader_experience.items) || !value.reader_experience.items.length
      || !Array.isArray(value.technique.items) || !value.technique.items.length) return null;
    const characters = normalizeDepthView(value.characters);
    characters.characters = Array.isArray(value.characters.characters)
      ? value.characters.characters.map((item) => normalizeDepthItem(item, {
        name: deconstructionText(item.name, "未命名人物"),
        aliases: deconstructionStringList(item.aliases),
        role: deconstructionText(item.role, "人物身份未知"),
        motivation: deconstructionText(item.motivation, "动机未知"),
        innerConflict: deconstructionText(item.inner_conflict, "内在冲突未知"),
        arcSummary: deconstructionText(item.arc_summary, "人物弧线仍需回看"),
      }))
      : [];
    characters.states = Array.isArray(value.characters.states)
      ? value.characters.states.map((item) => normalizeDepthItem(item, {
        characterId: String(item.character_id || ""),
        goal: deconstructionText(item.goal, "目标未知"),
        belief: deconstructionText(item.belief, "信念未知"),
        emotion: deconstructionText(item.emotion, "情绪未知"),
        agency: deconstructionText(item.agency, "行动能力未知"),
        change: deconstructionText(item.change, "变化未知"),
        triggerEventIds: deconstructionStringList(item.trigger_event_ids),
      }))
      : [];
    characters.relations = Array.isArray(value.characters.relations)
      ? value.characters.relations.map(normalizeDepthRelation)
      : [];

    const plot = normalizeDepthView(value.plot);
    plot.plotlines = Array.isArray(value.plot.plotlines)
      ? value.plot.plotlines.map((item) => normalizeDepthItem(item, {
        title: deconstructionText(item.title, "未命名剧情线"),
        centralQuestion: deconstructionText(item.central_question, "核心问题未知"),
        stakes: deconstructionText(item.stakes, "代价未知"),
        resolution: deconstructionText(item.resolution, "结局仍开放"),
        characterIds: deconstructionStringList(item.character_ids),
      }))
      : [];
    plot.events = Array.isArray(value.plot.events)
      ? value.plot.events.map((item) => normalizeDepthItem(item, {
        plotlineIds: deconstructionStringList(item.plotline_ids),
        characterIds: deconstructionStringList(item.character_ids),
        storyOrder: deconstructionNullableNumber(item.story_order),
        narrativeOrder: deconstructionNumber(item.narrative_order),
        temporalMode: depthTemporalModeText[item.temporal_mode] ? item.temporal_mode : "unknown",
        action: deconstructionText(item.action, "动作未知"),
        consequence: deconstructionText(item.consequence, "后果未知"),
        plotlineStatus: depthPlotStatusText[item.plotline_status] ? item.plotline_status : "unknown",
      }))
      : [];
    plot.relations = Array.isArray(value.plot.relations)
      ? value.plot.relations.map(normalizeDepthRelation)
      : [];

    const foreshadowing = normalizeDepthView(value.foreshadowing);
    foreshadowing.threads = Array.isArray(value.foreshadowing.threads)
      ? value.foreshadowing.threads.map((item) => normalizeDepthItem(item, {
        label: deconstructionText(item.label, "未命名伏笔"),
        plantedDetail: deconstructionText(item.planted_detail, "铺垫细节未知"),
        expectedPayoff: deconstructionText(item.expected_payoff, "预期回收未知"),
        interpretation: deconstructionText(item.interpretation, "解释仍需回看"),
      }))
      : [];
    foreshadowing.states = Array.isArray(value.foreshadowing.states)
      ? value.foreshadowing.states.map((item) => normalizeDepthItem(item, {
        foreshadowingId: String(item.foreshadowing_id || ""),
        status: depthForeshadowingStatusText[item.status] ? item.status : "unknown",
        payoff: deconstructionText(item.payoff, "回收结果未知"),
        eventIds: deconstructionStringList(item.event_ids),
      }))
      : [];
    foreshadowing.relations = Array.isArray(value.foreshadowing.relations)
      ? value.foreshadowing.relations.map(normalizeDepthRelation)
      : [];

    const rhythm = normalizeDepthView(value.rhythm);
    rhythm.items = Array.isArray(value.rhythm.items)
      ? value.rhythm.items.map((item) => normalizeDepthItem(item, {
        narrativeFunction: deconstructionText(item.narrative_function, "叙事功能未知"),
        sceneSummary: deconstructionText(item.scene_summary, "场景概况未知"),
        pace: deconstructionNullableNumber(item.pace),
        tension: deconstructionNullableNumber(item.tension),
        informationDensity: deconstructionNullableNumber(item.information_density),
        transition: deconstructionText(item.transition, "转场方式未知"),
      }))
      : [];

    const reader = normalizeDepthView(value.reader_experience);
    reader.items = Array.isArray(value.reader_experience.items)
      ? value.reader_experience.items.map((item) => normalizeDepthItem(item, {
        expectation: deconstructionText(item.expectation, "期待变化未知"),
        informationGap: deconstructionText(item.information_gap, "信息差未知"),
        emotionalEffect: deconstructionText(item.emotional_effect, "情绪影响未知"),
        curiosity: deconstructionNullableNumber(item.curiosity),
        suspense: deconstructionNullableNumber(item.suspense),
        emotionalValence: deconstructionNullableNumber(item.emotional_valence),
        payoff: deconstructionText(item.payoff, "回收感未知"),
      }))
      : [];

    const technique = normalizeDepthView(value.technique);
    technique.items = Array.isArray(value.technique.items)
      ? value.technique.items.map((item) => normalizeDepthItem(item, {
        technique: deconstructionText(item.technique, "未命名技法"),
        observation: deconstructionText(item.observation, "观察未知"),
        mechanism: deconstructionText(item.mechanism, "作用机制未知"),
        effect: deconstructionText(item.effect, "结构效果未知"),
        learningNote: deconstructionText(item.learning_note, "学习说明未知"),
        applicability: deconstructionText(item.applicability, "适用边界未知"),
        exampleEvidenceIds: deconstructionStringList(item.example_evidence_ids),
      }))
      : [];

    return {
      reportVersion: "2.0",
      source,
      chapters,
      evidence,
      characters,
      plot,
      foreshadowing,
      rhythm,
      reader,
      technique,
    };
  }

  function normalizeResult(value) {
    if (!value || typeof value !== "object" || value.status !== "completed") return null;
    const analysisContractVersion = String(value.analysis_contract_version || "1.0");
    const depthReport = value.report ? normalizeDepthReport(value.report) : null;
    if (analysisContractVersion === "2.0" && !depthReport) throw new Error("正式深度报告不完整。 ");
    if (depthReport && analysisContractVersion !== "2.0") throw new Error("深度报告版本不一致。 ");
    return {
      documentId: String(value.document_id || ""),
      sourceVersionId: String(value.source_version_id || ""),
      sourceRevision: deconstructionNumber(value.source_revision),
      sourceHash: String(value.source_hash || ""),
      analysisContractVersion,
      depthReport,
      analysisLabel: deconstructionText(value.analysis_label, "服务端结构拆解"),
      overview: normalizeOverview(value.overview),
      timeline: Array.isArray(value.timeline) ? value.timeline.map(normalizeTimelineNode) : [],
      chapters: Array.isArray(value.chapter_breakdowns) ? value.chapter_breakdowns.map(normalizeChapterBreakdown) : [],
      evidenceRefs: normalizeEvidenceRefs(value.evidence),
      uncertainties: deconstructionStringList(value.uncertainty),
    };
  }

  function normalizeActiveRun(value) {
    if (!value || typeof value !== "object") return null;
    return {
      documentId: String(value.document_id || ""),
      runStatus: String(value.run_status || "none"),
      sourceVersionId: String(value.source_version_id || ""),
      sourceRevision: deconstructionNumber(value.source_revision),
      sourceHash: String(value.source_hash || ""),
      retryCount: deconstructionNumber(value.retry_count) || 0,
      analysisLabel: deconstructionText(value.analysis_label, "服务端结构拆解"),
      createdAt: value.created_at || null,
      updatedAt: value.updated_at || null,
      completedAt: value.completed_at || null,
    };
  }

  function normalizeHistoryItem(value) {
    if (!value || typeof value !== "object") return null;
    const analysisContractVersion = ["1.0", "2.0"].includes(value.analysis_contract_version)
      ? value.analysis_contract_version
      : "unknown";
    return {
      documentId: String(value.document_id || ""),
      status: String(value.status || ""),
      sourceVersionId: String(value.source_version_id || ""),
      sourceRevision: deconstructionNumber(value.source_revision),
      sourceHash: String(value.source_hash || ""),
      analysisContractVersion,
      retryCount: deconstructionNumber(value.retry_count) || 0,
      analysisLabel: deconstructionText(value.analysis_label, "服务端结构拆解"),
      createdAt: value.created_at || null,
      updatedAt: value.updated_at || null,
      completedAt: value.completed_at || null,
    };
  }

  function normalizeDeconstructionError(value) {
    if (!value || typeof value !== "object") return null;
    return {
      code: String(value.code || ""),
      message: deconstructionText(value.message),
      retryable: value.retryable === true,
    };
  }

  function normalizeDeconstructionResponse(payload) {
    if (!payload || typeof payload !== "object") throw new Error("拆解服务返回了空响应。");
    const status = String(payload.effective_status || "");
    const runStatus = String(payload.run_status || "none");
    if (!deconstructionStatusSet.has(status) || !deconstructionRunStatusSet.has(runStatus)) {
      throw new Error("拆解服务返回了无法识别的状态。");
    }
    if (!payload.progress || !payload.source || !payload.actions || typeof payload.source_match !== "boolean") {
      throw new Error("拆解服务响应缺少 canonical 状态字段。");
    }
    const sourceMatch = payload.source_match;
    if (Boolean(payload.source.match) !== sourceMatch) throw new Error("拆解服务来源状态不一致。");
    const result = normalizeResult(payload.result);
    if (payload.result && !result) throw new Error("拆解服务返回了无效的正式结果。");
    if (result && (status !== "completed" || runStatus !== "completed" || !sourceMatch)) {
      throw new Error("正式结果没有绑定当前来源。");
    }
    if (result && (
      result.sourceVersionId !== String(payload.source.version_id || "")
      || result.sourceRevision !== deconstructionNumber(payload.source.revision)
      || result.sourceHash !== String(payload.source.hash || "")
    )) {
      throw new Error("正式结果与当前来源版本不一致。");
    }
    if (result?.depthReport && (
      result.depthReport.source.projectId !== String(payload.project_id || "")
      || result.depthReport.source.versionId !== String(payload.source.version_id || "")
      || result.depthReport.source.revision !== deconstructionNumber(payload.source.revision)
      || result.depthReport.source.contentHash !== String(payload.source.hash || "")
      || result.depthReport.source.documentId !== result.documentId
    )) {
      throw new Error("深度报告与当前来源版本不一致。");
    }
    const error = normalizeDeconstructionError(payload.error);
    return {
      projectId: String(payload.project_id || ""),
      title: deconstructionText(payload.title, "—"),
      effectiveStatus: status,
      runStatus,
      sourceMatch,
      progress: {
        percent: deconstructionNumber(payload.progress.percent),
        currentStage: deconstructionText(payload.progress.current_stage, "等待拆解"),
      },
      source: {
        versionId: payload.source.version_id ? String(payload.source.version_id) : "",
        revision: deconstructionNumber(payload.source.revision),
        contentHash: payload.source.hash ? String(payload.source.hash) : "",
        match: Boolean(payload.source.match),
        chapterCount: deconstructionNumber(payload.source.chapter_count),
        wordCount: deconstructionNumber(payload.source.total_word_count),
      },
      activeRun: normalizeActiveRun(payload.active_run),
      result,
      error,
      actions: {
        retry: payload.actions.retry === true,
        rebuild: payload.actions.rebuild === true,
      },
      history: Array.isArray(payload.history) ? payload.history.map(normalizeHistoryItem).filter(Boolean) : [],
      statusLabel: deconstructionStatusText[status],
      message: error?.message || deconstructionStatusMessages[status],
      analysisLabel: result?.analysisLabel || normalizeActiveRun(payload.active_run)?.analysisLabel || "服务端结构拆解",
    };
  }

  function hasDeconstructionResults(data) {
    return Boolean(
      data?.result?.analysisContractVersion === "2.0"
      && data.result.depthReport?.reportVersion === "2.0",
    );
  }

  function formatDeconstructionCount(value, suffix = "") {
    const number = deconstructionNumber(value);
    return number === null ? "—" : `${Math.round(number).toLocaleString("zh-CN")}${suffix}`;
  }

  function deconstructionConfidenceBadge(confidence, compact = false) {
    const item = confidence || normalizedConfidence(null);
    const tone = item.value === null ? "pending" : item.value >= 80 ? "high" : item.value >= 55 ? "medium" : "low";
    return `<span class="deconstruction-confidence is-${tone}">${escapeHtml(compact ? item.label.replace("置信度", "") : item.label)}</span>`;
  }

  function deconstructionAnchorLabel(item) {
    const chapterStart = deconstructionNumber(item?.chapterStart ?? item?.chapterNumber);
    const chapterEnd = deconstructionNumber(item?.chapterEnd);
    const wordStart = deconstructionNumber(item?.wordStart);
    const wordEnd = deconstructionNumber(item?.wordEnd);
    const chapterText = chapterStart === null ? "章节待定位" : chapterEnd !== null && chapterEnd !== chapterStart ? `第 ${chapterStart}–${chapterEnd} 章` : `第 ${chapterStart} 章`;
    const wordText = wordStart === null ? "" : wordEnd !== null && wordEnd !== wordStart ? ` · ${formatDeconstructionCount(wordStart)}–${formatDeconstructionCount(wordEnd)} 字` : ` · ${formatDeconstructionCount(wordStart)} 字起`;
    return `${chapterText}${wordText}`;
  }

  function deconstructionEvidenceAttributes(evidence) {
    return `data-evidence-id="${escapeHtml(evidence.id)}" data-document-id="${escapeHtml(evidence.documentId)}" data-source-version-id="${escapeHtml(evidence.sourceVersionId)}" data-source-revision="${evidence.sourceRevision ?? ""}" data-source-hash="${escapeHtml(evidence.sourceHash)}" data-chapter-id="${escapeHtml(evidence.chapterId)}" data-chapter-number="${evidence.chapterNumber ?? ""}" data-granularity="${escapeHtml(evidence.granularity)}" data-char-start="${evidence.charStart ?? ""}" data-char-end="${evidence.charEnd ?? ""}" data-offset-unit="${escapeHtml(evidence.offsetUnit)}" data-excerpt="${escapeHtml(evidence.excerpt)}"`;
  }

  function renderDeconstructionEvidence(refs) {
    const references = Array.isArray(refs) ? refs : [];
    if (!references.length) return `<span class="deconstruction-no-evidence">暂未绑定来源证据</span>`;
    return `<div class="deconstruction-evidence-list">${references.map((evidence, index) => {
      const chapterNumber = evidence.chapterNumber;
      const label = chapterNumber === null ? `证据 ${index + 1}` : `回到第 ${chapterNumber} 章`;
      const excerpt = evidence.excerpt.replace(/\s+/g, " ").slice(0, 96);
      if (chapterNumber === null) return `<span class="deconstruction-evidence-unresolved"><span>${escapeHtml(label)}</span><small>章节定位待补充</small></span>`;
      const precise = Boolean(evidence.documentId && evidence.sourceVersionId && evidence.sourceRevision !== null && evidence.sourceHash && evidence.offsetUnit === DECONSTRUCTION_OFFSET_UNIT && evidence.charStart !== null && evidence.charEnd !== null);
      return `<button class="deconstruction-evidence-link" type="button" data-action="open-deconstruction-evidence" ${deconstructionEvidenceAttributes(evidence)} aria-label="${escapeHtml(`${label}${excerpt ? `：${excerpt}` : ""}`)}"><span class="deconstruction-evidence-label">${escapeHtml(label)}</span><span class="deconstruction-evidence-excerpt">${escapeHtml(excerpt || deconstructionAnchorLabel(evidence))}</span><small class="deconstruction-evidence-mode">${precise ? "来源已校验 · UTF-16" : "章节级只读回链"}</small><span class="deconstruction-evidence-arrow" aria-hidden="true">↗</span></button>`;
    }).join("")}</div>`;
  }

  function deconstructionStatusHeading(data) {
    const headings = {
      empty: "还没有足够正文可供拆解",
      queued: "拆解任务已排队",
      running: "正在把正文还原成结构线",
      completed: "这份拆解已经可以回看",
      failed_retryable: "这次拆解没有完成",
      stale: "正文变了，旧结果不再冒充当前事实",
      rebuild_required: "需要先确认正文修改",
    };
    return headings[data?.effectiveStatus] || "拆解状态待确认";
  }

  function deconstructionStatusAction(data) {
    if (data.effectiveStatus === "failed_retryable" && data.actions.retry) return `<button class="button button-primary" type="button" data-action="deconstruction-retry">重试拆解 <span aria-hidden="true">→</span></button>`;
    if (data.effectiveStatus === "stale" && data.actions.rebuild) return `<button class="button button-outline" type="button" data-action="deconstruction-rebuild">根据当前正文重建 <span aria-hidden="true">→</span></button>`;
    if (data.effectiveStatus === "rebuild_required") {
      if (data.actions.rebuild === true) return `<button class="button button-primary" type="button" data-action="deconstruction-rebuild">生成深度拆解 <span aria-hidden="true">→</span></button>`;
      return `<button class="button button-outline" type="button" data-action="deconstruction-open-editor">回到正文确认修改 <span aria-hidden="true">→</span></button>`;
    }
    if (data.effectiveStatus === "empty") return `<button class="button button-outline" type="button" data-action="deconstruction-open-editor">回到正文 <span aria-hidden="true">→</span></button>`;
    return "";
  }

  function deconstructionStatusMessage(data) {
    if (data.effectiveStatus === "rebuild_required") {
      if (data.actions.rebuild === true) {
        return "已有阶段 31 基础拆解，但还没有 2.0 深度报告。生成深度拆解会创建新的服务端运行，旧结果保留为历史只读。";
      }
    }
    return data.message;
  }

  function renderDeconstructionStatus(data) {
    const working = ["queued", "running"].includes(data.runStatus);
    const progress = data.progress.percent === null ? 0 : Math.max(0, Math.min(100, data.progress.percent));
    const progressText = data.progress.percent === null ? "服务端尚未提供进度百分比" : `已完成 ${Math.round(data.progress.percent)}%`;
    const sourceText = data.source.chapterCount !== null || data.source.wordCount !== null
      ? `${formatDeconstructionCount(data.source.chapterCount, " 章")} · ${formatDeconstructionCount(data.source.wordCount, " 字")}`
      : "来源规模待识别";
    const sourceLine = data.source.versionId
      ? `SOURCE / ${data.source.versionId.slice(0, 12)} · REV / ${data.source.revision ?? "—"} · HASH / ${data.source.contentHash ? data.source.contentHash.slice(0, 12) : "—"}`
      : "SOURCE / 尚未形成正式稿本";
    return `<section class="deconstruction-state-card is-${escapeHtml(data.effectiveStatus)}" aria-label="拆解状态">
      <div class="deconstruction-state-copy"><div class="deconstruction-state-kicker"><span class="eyebrow">拆解状态</span><span class="deconstruction-status-note">${escapeHtml(data.runStatus === "none" ? "服务端状态" : `运行 / ${data.runStatus}`)}</span></div><h2>${escapeHtml(deconstructionStatusHeading(data))}</h2><p>${escapeHtml(deconstructionStatusMessage(data))}</p><small class="deconstruction-source-line mono">${escapeHtml(sourceLine)}</small></div>
      <div class="deconstruction-state-side">${working ? `<div class="deconstruction-progress" role="progressbar" aria-label="拆解进度" aria-valuemin="0" aria-valuemax="100" ${data.progress.percent === null ? "" : `aria-valuenow="${Math.round(data.progress.percent)}"`}><span style="width: ${progress}%"></span></div><span class="deconstruction-progress-label">${escapeHtml(progressText)} · ${escapeHtml(data.progress.currentStage)}</span>` : `<span class="deconstruction-state-source">来源 / ${escapeHtml(sourceText)}</span>`}${deconstructionStatusAction(data)}</div>
    </section>`;
  }

  function depthClamp(value, fallback = 0) {
    const number = deconstructionNumber(value);
    return number === null ? fallback : Math.max(0, Math.min(100, number));
  }

  function depthProgressRange(item) {
    const start = depthClamp(item?.normalizedStart, 0);
    const end = Math.max(start, depthClamp(item?.normalizedEnd, start));
    return { start, end };
  }

  function depthItemVisibleAt(item, progress) {
    const start = deconstructionNumber(item?.normalizedStart);
    return start === null || start <= progress + 0.0001;
  }

  function depthChapterRange(item, report) {
    const chapters = (item?.chapterIds || [])
      .map((id) => report.chapters.find((chapter) => chapter.id === id))
      .filter(Boolean);
    if (!chapters.length) return "章节待定位";
    const first = chapters[0].number;
    const last = chapters[chapters.length - 1].number;
    return first === last ? `第 ${first} 章` : `第 ${first}–${last} 章`;
  }

  function depthItemProgress(item) {
    const { start, end } = depthProgressRange(item);
    return `${Math.round(start)}–${Math.round(end)}%`;
  }

  function depthVisibleItems(items, progress) {
    return (Array.isArray(items) ? items : []).filter((item) => depthItemVisibleAt(item, progress));
  }

  function depthItemIndex(report) {
    const all = [
      ...report.characters.characters,
      ...report.characters.states,
      ...report.characters.relations,
      ...report.plot.plotlines,
      ...report.plot.events,
      ...report.plot.relations,
      ...report.foreshadowing.threads,
      ...report.foreshadowing.states,
      ...report.foreshadowing.relations,
      ...report.rhythm.items,
      ...report.reader.items,
      ...report.technique.items,
    ];
    return new Map(all.filter((item) => item.id).map((item) => [item.id, item]));
  }

  function depthEndpointLabel(endpoint, index) {
    const item = index.get(endpoint?.id);
    if (!item) return "未命名项";
    if (item.kind === "character") return item.name;
    if (item.kind === "character_state") {
      const character = index.get(item.characterId);
      return character ? `${character.name}的状态` : "人物状态";
    }
    if (item.kind === "plotline") return item.title;
    if (item.kind === "event") return item.action;
    if (item.kind === "foreshadowing") return item.label;
    if (item.kind === "foreshadowing_state") {
      const thread = index.get(item.foreshadowingId);
      return thread ? `${thread.label}的状态` : "伏笔状态";
    }
    return item.conclusion;
  }

  function depthEvidenceForItem(item, report, ids = null) {
    const wanted = Array.isArray(ids) ? ids : item?.evidenceIds || [];
    return wanted
      .map((id) => report.evidence.find((evidence) => evidence.id === id))
      .filter(Boolean);
  }

  function renderDepthItemMeta(item, report) {
    return `<div class="depth-item-meta"><span>${escapeHtml(depthChapterRange(item, report))}</span><span class="mono">${escapeHtml(depthItemProgress(item))}</span><span>${escapeHtml(item.category)}</span><span>${escapeHtml(depthEpistemicStatusText[item.epistemicStatus] || "证据状态未知")}</span></div>`;
  }

  function renderDepthUncertainty(items) {
    const uncertainty = Array.isArray(items) ? items.filter(Boolean) : [];
    return uncertainty.length
      ? `<div class="depth-uncertainty"><strong>不确定性</strong><span>${escapeHtml(uncertainty.join("；"))}</span></div>`
      : "";
  }

  function renderDepthItemEvidence(item, report, ids = null) {
    return renderDeconstructionEvidence(depthEvidenceForItem(item, report, ids));
  }

  function renderDepthViewIntro(view, id) {
    return `<header class="depth-view-heading"><div><span class="eyebrow">${escapeHtml(depthPerspectiveMeta[id].label)}</span><h2 id="depthViewHeading-${escapeHtml(id)}">${escapeHtml(depthPerspectiveMeta[id].title)}</h2></div><p>${escapeHtml(view.summary)}</p></header>${renderDepthUncertainty(view.uncertainty)}`;
  }

  function renderDepthControls(report) {
    const selectedProgress = depthSelectedProgress(report);
    const selectedChapterId = state.deconstructionChapterId || "";
    return `<section class="depth-review-controls" aria-label="深度拆解回看范围"><label for="depthChapterFilter"><span>按章节回看</span><select id="depthChapterFilter" data-action="deconstruction-depth-chapter"><option value="">全书</option>${report.chapters.map((chapter) => `<option value="${escapeHtml(chapter.id)}" ${chapter.id === selectedChapterId ? "selected" : ""}>第 ${escapeHtml(chapter.number)} 章${chapter.title ? ` · ${escapeHtml(chapter.title)}` : ""}</option>`).join("")}</select></label><label class="depth-progress-control" for="depthProgressFilter"><span>按阅读进度回看 <output id="depthProgressOutput" for="depthProgressFilter">${Math.round(selectedProgress)}%</output></span><input id="depthProgressFilter" type="range" min="0" max="100" step="1" value="${Math.round(selectedProgress)}" data-action="deconstruction-depth-progress" aria-label="按阅读进度回看" /></label><p>此处只改变本页的回看位置，不修改服务端报告或正文。</p></section>`;
  }

  function depthSelectedProgress(report) {
    if (state.deconstructionChapterId) {
      const chapter = report.chapters.find((item) => item.id === state.deconstructionChapterId);
      if (chapter) return depthClamp(chapter.end, 100);
    }
    return depthClamp(state.deconstructionProgress, 100);
  }

  function renderDepthAxis(items, report, progress, kind, title) {
    const visible = depthVisibleItems(items, progress);
    const bars = visible.map((item) => {
      const range = depthProgressRange(item);
      const width = Math.max(1.5, range.end - range.start);
      return `<article class="depth-axis-item" style="--depth-start:${range.start}%;--depth-size:${width}%"><div class="depth-axis-bar" aria-hidden="true"></div><div class="depth-axis-item-topline"><span class="mono">${escapeHtml(depthItemProgress(item))}</span>${deconstructionConfidenceBadge(item.confidence, true)}</div><h3>${escapeHtml(kind === "rhythm" ? item.narrativeFunction : item.category)}</h3><p>${escapeHtml(item.conclusion)}</p>${renderDepthItemMeta(item, report)}${renderDepthUncertainty(item.uncertainty)}${renderDepthItemEvidence(item, report)}</article>`;
    }).join("");
    return `<section class="depth-axis-panel" aria-labelledby="${escapeHtml(title)}"><div class="depth-section-heading"><div><span class="eyebrow">共享阅读轴</span><h3 id="${escapeHtml(title)}">${escapeHtml(kind === "rhythm" ? "叙事推进" : "读者感受变化")}</h3></div><span class="depth-section-note">截至 ${Math.round(progress)}% · ${visible.length}/${Array.isArray(items) ? items.length : 0} 项</span></div><div class="depth-axis-scale" aria-hidden="true"><span>0%</span><span>50%</span><span>100%</span></div><p class="depth-axis-caption">0% 起于正文开头，100% 落在正文结尾</p><div class="depth-axis-rail" aria-hidden="true"><i></i><i></i><i></i></div><div class="depth-axis-list">${bars || `<p class="depth-empty-note">这个回看位置没有可展示的服务端记录。</p>`}</div></section>`;
  }

  function renderDepthRelationList(relations, report, progress, index, emptyText) {
    const visible = depthVisibleItems(relations, progress);
    if (!visible.length) return `<p class="depth-empty-note">${escapeHtml(emptyText)}</p>`;
    return `<div class="depth-relation-list">${visible.map((relation) => `<article class="depth-relation-card"><div class="depth-relation-route"><strong>${escapeHtml(depthEndpointLabel(relation.start, index))}</strong><span>${escapeHtml(depthRelationText[relation.relationType] || "关系")}</span><strong>${escapeHtml(depthEndpointLabel(relation.end, index))}</strong></div><p>${escapeHtml(relation.explanation || relation.conclusion)}</p>${renderDepthItemMeta(relation, report)}${renderDepthUncertainty(relation.uncertainty)}${renderDepthItemEvidence(relation, report)}</article>`).join("")}</div>`;
  }

  function renderDepthStatePreview(character, states, report, progress) {
    const visible = states.filter((item) => item.characterId === character.id && depthItemVisibleAt(item, progress));
    visible.sort((left, right) => (left.normalizedStart ?? 0) - (right.normalizedStart ?? 0));
    const current = visible.at(-1);
    if (!current) return `<p class="depth-empty-note">截至当前回看位置，还没有人物状态快照。</p>`;
    return `<div class="depth-state-preview"><div class="depth-card-topline"><span>截至 ${Math.round(progress)}% 的状态</span><span class="mono">${escapeHtml(depthChapterRange(current, report))}</span></div><p>${escapeHtml(current.change)}</p><dl class="depth-fact-list"><div><dt>目标</dt><dd>${escapeHtml(current.goal)}</dd></div><div><dt>信念</dt><dd>${escapeHtml(current.belief)}</dd></div><div><dt>情绪</dt><dd>${escapeHtml(current.emotion)}</dd></div><div><dt>行动</dt><dd>${escapeHtml(current.agency)}</dd></div></dl>${renderDepthItemEvidence(current, report)}</div>`;
  }

  function renderDepthCharactersView(report, progress) {
    const view = report.characters;
    const index = depthItemIndex(report);
    const cards = depthVisibleItems(view.characters, progress).map((character) => `<article class="depth-entity-card"><div class="depth-card-topline"><span class="depth-card-label">人物候选</span>${deconstructionConfidenceBadge(character.confidence, true)}</div><h3>${escapeHtml(character.name)}</h3><p class="depth-conclusion">${escapeHtml(character.conclusion)}</p>${renderDepthItemMeta(character, report)}<dl class="depth-fact-list"><div><dt>角色</dt><dd>${escapeHtml(character.role)}</dd></div><div><dt>动机</dt><dd>${escapeHtml(character.motivation)}</dd></div><div><dt>内在冲突</dt><dd>${escapeHtml(character.innerConflict)}</dd></div><div><dt>人物弧</dt><dd>${escapeHtml(character.arcSummary)}</dd></div>${character.aliases.length ? `<div><dt>别名</dt><dd>${escapeHtml(character.aliases.join("、"))}</dd></div>` : ""}</dl>${renderDepthStatePreview(character, view.states, report, progress)}${renderDepthUncertainty(character.uncertainty)}${renderDepthItemEvidence(character, report)}</article>`).join("");
    const states = depthVisibleItems(view.states, progress).map((item) => {
      const character = index.get(item.characterId);
      return `<article class="depth-track-item"><div><strong>${escapeHtml(character?.name || "未命名人物")}</strong><span>${escapeHtml(depthChapterRange(item, report))} · ${escapeHtml(depthItemProgress(item))}</span></div><p>${escapeHtml(item.change)}</p><small>目标：${escapeHtml(item.goal)} · 信念：${escapeHtml(item.belief)} · 情绪：${escapeHtml(item.emotion)}</small>${renderDepthItemEvidence(item, report)}</article>`;
    }).join("");
    return `${renderDepthViewIntro(view, "characters")}<div class="depth-view-grid depth-entity-grid">${cards || `<p class="depth-empty-note">当前正文没有可靠的人物候选。页面保留无发现，不生成虚假人物。</p>`}</div><section class="depth-subsection"><div class="depth-section-heading"><div><span class="eyebrow">按阅读进度</span><h3>人物状态快照</h3></div><span class="depth-section-note">截至 ${Math.round(progress)}%</span></div><div class="depth-scroll-list">${states || `<p class="depth-empty-note">当前回看位置没有人物状态快照。</p>`}</div></section><section class="depth-subsection"><div class="depth-section-heading"><div><span class="eyebrow">关系视图</span><h3>人物之间的可读关系</h3></div><span class="depth-section-note">${view.relations.length} 条服务端关系</span></div>${renderDepthRelationList(view.relations, report, progress, index, "当前回看位置没有人物关系记录。")}</section>`;
  }

  function renderDepthPlotView(report, progress) {
    const view = report.plot;
    const index = depthItemIndex(report);
    const plotlines = depthVisibleItems(view.plotlines, progress).map((line) => `<article class="depth-entity-card"><div class="depth-card-topline"><span class="depth-card-label">剧情线</span>${deconstructionConfidenceBadge(line.confidence, true)}</div><h3>${escapeHtml(line.title)}</h3><p class="depth-conclusion">${escapeHtml(line.conclusion)}</p>${renderDepthItemMeta(line, report)}<dl class="depth-fact-list"><div><dt>核心问题</dt><dd>${escapeHtml(line.centralQuestion)}</dd></div><div><dt>代价</dt><dd>${escapeHtml(line.stakes)}</dd></div><div><dt>结局方向</dt><dd>${escapeHtml(line.resolution)}</dd></div></dl>${renderDepthUncertainty(line.uncertainty)}${renderDepthItemEvidence(line, report)}</article>`).join("");
    const events = depthVisibleItems(view.events, progress).map((event) => `<article class="depth-track-item"><div><strong>${escapeHtml(event.action)}</strong><span>${escapeHtml(depthChapterRange(event, report))} · ${escapeHtml(depthItemProgress(event))}</span></div><p>${escapeHtml(event.consequence)}</p><small>${escapeHtml(depthTemporalModeText[event.temporalMode] || "故事时间未知")} · ${escapeHtml(depthPlotStatusText[event.plotlineStatus] || "状态未知")}${event.storyOrder === null ? " · 故事顺序未知" : ` · 故事顺序 ${event.storyOrder}`}</small>${renderDepthItemEvidence(event, report)}</article>`).join("");
    return `${renderDepthViewIntro(view, "plot")}<section class="depth-subsection"><div class="depth-section-heading"><div><span class="eyebrow">剧情线</span><h3>每条线在问什么</h3></div><span class="depth-section-note">${view.plotlines.length} 条线</span></div><div class="depth-view-grid">${plotlines || `<p class="depth-empty-note">正文没有可靠的剧情线候选。</p>`}</div></section><section class="depth-subsection"><div class="depth-section-heading"><div><span class="eyebrow">事件轴</span><h3>按正文呈现顺序回看事件</h3></div><span class="depth-section-note">截至 ${Math.round(progress)}% · ${events ? depthVisibleItems(view.events, progress).length : 0} 项</span></div><div class="depth-scroll-list">${events || `<p class="depth-empty-note">当前回看位置没有事件记录。</p>`}</div></section><section class="depth-subsection"><div class="depth-section-heading"><div><span class="eyebrow">关系视图</span><h3>事件因果与叙述顺序</h3></div><span class="depth-section-note">“先于”不自动等于“导致”</span></div>${renderDepthRelationList(view.relations, report, progress, index, "当前回看位置没有剧情关系记录。")}</section>`;
  }

  function renderDepthForeshadowingView(report, progress) {
    const view = report.foreshadowing;
    const index = depthItemIndex(report);
    const threads = depthVisibleItems(view.threads, progress).map((thread) => {
      const states = view.states.filter((item) => item.foreshadowingId === thread.id && depthItemVisibleAt(item, progress));
      states.sort((left, right) => (left.normalizedStart ?? 0) - (right.normalizedStart ?? 0));
      const current = states.at(-1);
      return `<article class="depth-entity-card"><div class="depth-card-topline"><span class="depth-card-label">伏笔线索</span>${deconstructionConfidenceBadge(thread.confidence, true)}</div><h3>${escapeHtml(thread.label)}</h3><p class="depth-conclusion">${escapeHtml(thread.conclusion)}</p>${renderDepthItemMeta(thread, report)}<dl class="depth-fact-list"><div><dt>埋下的细节</dt><dd>${escapeHtml(thread.plantedDetail)}</dd></div><div><dt>预期回收</dt><dd>${escapeHtml(thread.expectedPayoff)}</dd></div><div><dt>当前解释</dt><dd>${escapeHtml(thread.interpretation)}</dd></div></dl><div class="depth-chain"><span class="depth-chain-label">截至 ${Math.round(progress)}% 的状态</span>${current ? `<strong>${escapeHtml(depthForeshadowingStatusText[current.status] || "状态未知")}</strong><p>${escapeHtml(current.payoff)}</p><small>${escapeHtml(depthChapterRange(current, report))}</small>${renderDepthItemEvidence(current, report)}` : `<p class="depth-empty-note">当前回看位置还没有状态快照。</p>`}</div>${renderDepthUncertainty(thread.uncertainty)}${renderDepthItemEvidence(thread, report)}</article>`;
    }).join("");
    const states = depthVisibleItems(view.states, progress).map((item) => {
      const thread = index.get(item.foreshadowingId);
      return `<article class="depth-track-item"><div><strong>${escapeHtml(thread?.label || "未命名伏笔")}</strong><span>${escapeHtml(depthForeshadowingStatusText[item.status] || "状态未知")} · ${escapeHtml(depthChapterRange(item, report))}</span></div><p>${escapeHtml(item.payoff)}</p>${renderDepthItemEvidence(item, report)}</article>`;
    }).join("");
    return `${renderDepthViewIntro(view, "foreshadowing")}<section class="depth-subsection"><div class="depth-section-heading"><div><span class="eyebrow">回收轨迹</span><h3>伏笔如何改变状态</h3></div><span class="depth-section-note">截至 ${Math.round(progress)}%</span></div><div class="depth-view-grid">${threads || `<p class="depth-empty-note">当前正文没有可靠的伏笔候选。页面保留无发现，不把普通细节硬判为伏笔。</p>`}</div></section><section class="depth-subsection"><div class="depth-section-heading"><div><span class="eyebrow">状态快照</span><h3>按章节查看铺垫与回收</h3></div><span class="depth-section-note">${depthVisibleItems(view.states, progress).length} 项已发生</span></div><div class="depth-scroll-list">${states || `<p class="depth-empty-note">当前回看位置没有伏笔状态记录。</p>`}</div></section><section class="depth-subsection"><div class="depth-section-heading"><div><span class="eyebrow">关系视图</span><h3>事件与伏笔的链路</h3></div><span class="depth-section-note">${view.relations.length} 条服务端关系</span></div>${renderDepthRelationList(view.relations, report, progress, index, "当前回看位置没有伏笔关系记录。")}</section>`;
  }

  function depthMetric(value, label, formatter = (number) => `${Math.round(number * 100)}%`) {
    const number = deconstructionNumber(value);
    if (number === null) return `<div class="depth-metric is-unknown"><span>${escapeHtml(label)}</span><strong>未知</strong><small>证据不足，未绘制数值曲线</small></div>`;
    return `<div class="depth-metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(formatter(number))}</strong><small>服务端指标</small></div>`;
  }

  function renderDepthRhythmView(report, progress) {
    const view = report.rhythm;
    const items = depthVisibleItems(view.items, progress);
    const cards = items.map((item) => `<article class="depth-analysis-card"><div class="depth-card-topline"><span class="depth-card-label">${escapeHtml(item.narrativeFunction)}</span>${deconstructionConfidenceBadge(item.confidence, true)}</div><h3>${escapeHtml(item.conclusion)}</h3>${renderDepthItemMeta(item, report)}<p>${escapeHtml(item.sceneSummary)}</p><div class="depth-metric-grid">${depthMetric(item.pace, "推进速度")}${depthMetric(item.tension, "张力")}${depthMetric(item.informationDensity, "信息密度")}</div><p class="depth-detail-line"><span>转场</span>${escapeHtml(item.transition)}</p>${renderDepthUncertainty(item.uncertainty)}${renderDepthItemEvidence(item, report)}</article>`).join("");
    return `${renderDepthViewIntro(view, "rhythm")}${renderDepthAxis(view.items, report, progress, "rhythm", "rhythmAxisTitle")}<section class="depth-subsection"><div class="depth-section-heading"><div><span class="eyebrow">逐段观察</span><h3>节奏指标与章节结构</h3></div><span class="depth-section-note">${items.length}/${view.items.length} 项</span></div><div class="depth-view-grid">${cards || `<p class="depth-empty-note">当前回看位置没有节奏记录。</p>`}</div></section>`;
  }

  function renderDepthReaderView(report, progress) {
    const view = report.reader;
    const items = depthVisibleItems(view.items, progress);
    const cards = items.map((item) => `<article class="depth-analysis-card"><div class="depth-card-topline"><span class="depth-card-label">读者体验</span>${deconstructionConfidenceBadge(item.confidence, true)}</div><h3>${escapeHtml(item.conclusion)}</h3>${renderDepthItemMeta(item, report)}<dl class="depth-fact-list"><div><dt>期待</dt><dd>${escapeHtml(item.expectation)}</dd></div><div><dt>信息差</dt><dd>${escapeHtml(item.informationGap)}</dd></div><div><dt>情绪影响</dt><dd>${escapeHtml(item.emotionalEffect)}</dd></div><div><dt>回收感</dt><dd>${escapeHtml(item.payoff)}</dd></div></dl><div class="depth-metric-grid">${depthMetric(item.curiosity, "好奇心")}${depthMetric(item.suspense, "悬念")}${depthMetric(item.emotionalValence, "情绪倾向", (number) => `${number > 0 ? "+" : ""}${number.toFixed(2)}`)}</div>${renderDepthUncertainty(item.uncertainty)}${renderDepthItemEvidence(item, report)}</article>`).join("");
    return `${renderDepthViewIntro(view, "reader")}${renderDepthAxis(view.items, report, progress, "reader", "readerAxisTitle")}<section class="depth-subsection"><div class="depth-section-heading"><div><span class="eyebrow">逐段观察</span><h3>期待、信息差与情绪效果</h3></div><span class="depth-section-note">${items.length}/${view.items.length} 项</span></div><div class="depth-view-grid">${cards || `<p class="depth-empty-note">当前回看位置没有读者体验记录。</p>`}</div></section>`;
  }

  function renderDepthTechniqueView(report, progress) {
    const view = report.technique;
    const items = depthVisibleItems(view.items, progress);
    const cards = items.map((item) => `<article class="depth-technique-card"><div class="depth-card-topline"><span class="depth-card-label">${escapeHtml(item.technique)}</span>${deconstructionConfidenceBadge(item.confidence, true)}</div><h3>${escapeHtml(item.conclusion)}</h3>${renderDepthItemMeta(item, report)}<dl class="depth-fact-list"><div><dt>观察</dt><dd>${escapeHtml(item.observation)}</dd></div><div><dt>作用机制</dt><dd>${escapeHtml(item.mechanism)}</dd></div><div><dt>效果</dt><dd>${escapeHtml(item.effect)}</dd></div><div><dt>学习说明</dt><dd>${escapeHtml(item.learningNote)}</dd></div><div class="depth-boundary"><dt>适用边界</dt><dd>${escapeHtml(item.applicability)}</dd></div></dl><div class="depth-example-block"><strong>例证</strong>${renderDepthItemEvidence(item, report, item.exampleEvidenceIds)}</div>${renderDepthUncertainty(item.uncertainty)}</article>`).join("");
    return `${renderDepthViewIntro(view, "technique")}<section class="depth-subsection"><div class="depth-section-heading"><div><span class="eyebrow">可学习的观察</span><h3>技法、例证与边界</h3></div><span class="depth-section-note">${items.length}/${view.items.length} 项</span></div><div class="depth-view-grid depth-technique-grid">${cards || `<p class="depth-empty-note">当前回看位置没有技法记录。</p>`}</div></section>`;
  }

  function renderDeconstructionHistory(data) {
    if (!data.history.length) return "";
    const items = data.history.slice().reverse().slice(0, 6).map((item) => {
      const versionLabel = item.analysisContractVersion === "2.0"
        ? "深度 2.0"
        : item.analysisContractVersion === "1.0" ? "基础 1.0" : "版本未知";
      return `<li><div><strong>${escapeHtml(deconstructionStatusText[item.status] || item.status || "历史运行")}</strong><small>${escapeHtml(versionLabel)} · ${escapeHtml(item.analysisLabel)} · REV / ${escapeHtml(item.sourceRevision ?? "—")}</small></div><span class="mono">${escapeHtml(item.sourceHash ? item.sourceHash.slice(0, 12) : "—")}</span></li>`;
    }).join("");
    return `<section class="deconstruction-history-panel" aria-labelledby="deconstructionHistoryTitle"><header class="deconstruction-panel-heading"><div><span class="eyebrow">运行历史 / 只读</span><h2 id="deconstructionHistoryTitle">旧稿记录仍然可辨认</h2></div><span class="deconstruction-panel-note">不回链当前正文</span></header><ul>${items}</ul><p>历史运行只用于说明来源，不会跳到当前同编号章节伪装成精确证据。</p></section>`;
  }

  function renderDeconstructionOverview(data) {
    const report = data.result.depthReport;
    const counts = [
      ["人物候选", report.characters.characters.length, "人物弧与状态"],
      ["剧情事件", report.plot.events.length, "事件因果与叙述顺序"],
      ["伏笔线索", report.foreshadowing.threads.length, "铺垫与回收状态"],
      ["正文证据", report.evidence.length, "最小可回链片段"],
    ];
    const summaries = depthPerspectiveOrder.slice(1).map((id) => {
      const view = id === "reader" ? report.reader : report[id];
      const count = id === "characters" ? view.characters.length : id === "plot" ? view.events.length : id === "foreshadowing" ? view.threads.length : view.items.length;
      return `<button class="depth-overview-link" type="button" data-action="deconstruction-depth-tab" data-depth-tab="${escapeHtml(id)}"><span class="depth-overview-link-topline"><strong>${escapeHtml(depthPerspectiveMeta[id].label)}</strong><span class="mono">${count} 项</span></span><span>${escapeHtml(view.summary)}</span><b aria-hidden="true">→</b></button>`;
    }).join("");
    return `<section class="deconstruction-panel depth-overview-panel" aria-labelledby="deconstructionOverviewTitle"><header class="deconstruction-panel-heading"><div><span class="eyebrow">深度报告 / 2.0</span><h2 id="deconstructionOverviewTitle">作品总览</h2></div><span class="deconstruction-panel-note">六个视角共享同一稿本、阅读轴和证据池</span></header><div class="deconstruction-metric-row">${counts.map(([label, value, note]) => `<div class="deconstruction-metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(formatDeconstructionCount(value))}</strong><small>${escapeHtml(note)}</small></div>`).join("")}</div><div class="depth-overview-source"><div><span class="eyebrow">来源范围</span><strong>${escapeHtml(formatDeconstructionCount(report.chapters.length, " 章"))} · 当前稿本 REV / ${escapeHtml(data.source.revision ?? "—")}</strong></div><p>所有结论只来自作者正式正文。章节回看按阅读顺序，故事世界中的时间关系会单独标注。</p></div><div class="depth-overview-links">${summaries}</div>${renderDepthUncertainty([...report.characters.uncertainty, ...report.plot.uncertainty, ...report.foreshadowing.uncertainty, ...report.rhythm.uncertainty, ...report.reader.uncertainty, ...report.technique.uncertainty])}</section>`;
  }

  function renderDepthTabNavigation(activeView) {
    return `<div class="depth-tablist" role="tablist" aria-label="作品拆解六个视角"><button class="depth-tab" type="button" role="tab" id="deconstructionTab-overview" aria-controls="deconstructionPanel-overview" aria-selected="${activeView === "overview"}" tabindex="${activeView === "overview" ? "0" : "-1"}" data-action="deconstruction-depth-tab" data-depth-tab="overview">总览</button>${depthPerspectiveOrder.slice(1).map((id) => `<button class="depth-tab" type="button" role="tab" id="deconstructionTab-${escapeHtml(id)}" aria-controls="deconstructionPanel-${escapeHtml(id)}" aria-label="${escapeHtml(depthPerspectiveMeta[id].label)}视角" aria-selected="${activeView === id}" tabindex="${activeView === id ? "0" : "-1"}" data-action="deconstruction-depth-tab" data-depth-tab="${escapeHtml(id)}">${escapeHtml(depthPerspectiveMeta[id].label)}</button>`).join("")}</div>`;
  }

  function renderDepthPerspectivePanel(report, activeView, progress) {
    let body = renderDeconstructionOverview(state.deconstructionWorkspace);
    if (activeView === "characters") body = renderDepthCharactersView(report, progress);
    if (activeView === "plot") body = renderDepthPlotView(report, progress);
    if (activeView === "foreshadowing") body = renderDepthForeshadowingView(report, progress);
    if (activeView === "rhythm") body = renderDepthRhythmView(report, progress);
    if (activeView === "reader") body = renderDepthReaderView(report, progress);
    if (activeView === "technique") body = renderDepthTechniqueView(report, progress);
    return `<section class="depth-tabpanel" id="deconstructionPanel-${escapeHtml(activeView)}" role="tabpanel" aria-labelledby="deconstructionTab-${escapeHtml(activeView)}" tabindex="0">${body}</section>`;
  }

  function renderDeconstructionResult(data) {
    const report = data.result?.depthReport;
    if (!report || report.reportVersion !== "2.0") return "";
    const activeView = depthPerspectiveMeta[state.deconstructionView] ? state.deconstructionView : "overview";
    const progress = depthSelectedProgress(report);
    return `<div class="deconstruction-depth-result"><div class="depth-result-intro"><div><span class="eyebrow">可回证的深度拆解</span><h2>从总览进入六个视角</h2></div><p>点击任一结论下的证据按钮，会从服务端重新读取证据；历史稿本始终保持只读。</p></div>${renderDepthTabNavigation(activeView)}${renderDepthControls(report)}${renderDepthPerspectivePanel(report, activeView, progress)}</div>`;
  }

  function renderDeconstructionPage(data) {
    state.deconstructionWorkspace = data;
    state.deconstructionProjectId = data.projectId || state.deconstructionProjectId;
    elements.deconstructionProjectTitle.textContent = data.title || "—";
    elements.deconstructionStatusPill.textContent = data.statusLabel;
    elements.deconstructionStatusPill.className = `deconstruction-status-pill is-${data.effectiveStatus}`;
    const working = ["queued", "running"].includes(data.runStatus);
    elements.deconstructionRefreshButton.disabled = working;
    elements.deconstructionPageContent.setAttribute("aria-busy", String(working));
    const content = [renderDeconstructionStatus(data)];
    if (data.effectiveStatus === "empty") {
      content.push(`<section class="deconstruction-empty-panel"><div class="deconstruction-empty-mark">⌇</div><h2>先让正文留下可观察的章节</h2><p>作品拆解只读取这本作品当前稿本的真实正文。完成导入或写下至少一章后，服务端才会生成概览、节奏节点和章节证据；这里不会用标题、简介或固定模板填充结果。</p><div class="deconstruction-empty-actions"><button class="button button-outline" type="button" data-action="deconstruction-open-editor">回到正文 <span aria-hidden="true">→</span></button></div></section>`);
    } else if (hasDeconstructionResults(data) && data.effectiveStatus === "completed" && data.sourceMatch) {
      content.push(renderDeconstructionResult(data));
    } else if (data.effectiveStatus === "completed") {
      const legacy = data.result?.analysisContractVersion === "1.0";
      content.push(legacy
        ? `<section class="deconstruction-working-panel is-upgrade-required"><div class="deconstruction-empty-mark">↗</div><h2>基础拆解已有，深度拆解可生成</h2><p>当前是分析合同 1.0 的基础结果，不会在六个视角中冒充完成。请从服务端提供的升级入口生成 2.0 深度报告；旧结果会保留为历史只读。</p>${data.actions.rebuild ? `<button class="button button-primary" type="button" data-action="deconstruction-rebuild">生成深度拆解 <span aria-hidden="true">→</span></button>` : ""}</section>`
        : `<section class="deconstruction-working-panel"><div class="deconstruction-empty-mark">⌁</div><h2>服务端还没有返回可引用内容</h2><p>当前响应没有正式结果，页面保留空白，不将不完整响应冒充分析完成。</p></section>`);
    } else if (data.effectiveStatus === "stale") {
      content.push(`<section class="deconstruction-working-panel is-stale"><div class="deconstruction-empty-mark">↻</div><h2>当前稿本已经超过这版结果</h2><p>旧结果不会沿同编号章节跳转。确认当前正文没有待处理修改后，可以从这里重建一版。</p></section>`);
    } else if (data.effectiveStatus === "rebuild_required") {
      content.push(data.actions.rebuild
        ? `<section class="deconstruction-working-panel is-upgrade-required"><div class="deconstruction-empty-mark">↗</div><h2>基础拆解已就绪，等待生成深度报告</h2><p>这版 1.0 基础结果仍是历史参考。生成 2.0 深度报告后，人物、剧情、伏笔、节奏、读者体验和文笔才会进入完成态。</p><button class="button button-primary" type="button" data-action="deconstruction-rebuild">生成深度拆解 <span aria-hidden="true">→</span></button></section>`
        : `<section class="deconstruction-working-panel is-stale"><div class="deconstruction-empty-mark">⌁</div><h2>先回正文处理待确认修改</h2><p>作品拆解不会越过作者确认直接读取这批旧章修改。处理完成后，再回到这里查看服务端状态。</p></section>`);
    } else {
      content.push(`<section class="deconstruction-working-panel"><div class="deconstruction-empty-mark">⌁</div><h2>结果会在这里出现</h2><p>任务在服务端继续运行；离开页面或刷新后，重新读取即可恢复。</p></section>`);
    }
    if (data.effectiveStatus !== "empty") content.push(`<p class="deconstruction-source-note"><span>分析来源</span>${escapeHtml(data.analysisLabel)}${data.source.versionId ? ` · 当前稿本 ${escapeHtml(data.source.versionId.slice(0, 12))}` : ""}${data.source.revision === null ? "" : ` · REV / ${data.source.revision}`}</p>`);
    content.push(renderDeconstructionHistory(data));
    elements.deconstructionPageContent.innerHTML = content.join("");
    scheduleDeconstructionPoll(data);
  }

  function renderDeconstructionLoading() {
    elements.deconstructionProjectTitle.textContent = "正在读取…";
    elements.deconstructionStatusPill.textContent = "读取中";
    elements.deconstructionStatusPill.className = "deconstruction-status-pill is-loading";
    elements.deconstructionRefreshButton.disabled = true;
    elements.deconstructionPageContent.setAttribute("aria-busy", "true");
    elements.deconstructionPageContent.innerHTML = `<section class="deconstruction-loading-panel" aria-label="正在读取作品拆解"><div class="deconstruction-loading-line"></div><div class="deconstruction-loading-line is-short"></div><div class="deconstruction-loading-grid"><span></span><span></span><span></span></div><p>正在读取这本作品的服务端拆解状态…</p></section>`;
  }

  function renderDeconstructionReadError(message) {
    elements.deconstructionStatusPill.textContent = "读取失败";
    elements.deconstructionStatusPill.className = "deconstruction-status-pill is-error";
    elements.deconstructionRefreshButton.disabled = false;
    elements.deconstructionPageContent.setAttribute("aria-busy", "false");
    elements.deconstructionPageContent.innerHTML = `<section class="deconstruction-error-panel"><div class="deconstruction-error-mark">!</div><h2>作品拆解暂时读不到</h2><p>${escapeHtml(message || "请稍后重试；当前没有展示任何本地或静态结果。")} </p><button class="button button-primary" type="button" data-action="deconstruction-refresh">重新读取 <span aria-hidden="true">→</span></button></section>`;
  }

  function scheduleDeconstructionPoll(data) {
    window.clearTimeout(state.deconstructionPollTimer);
    state.deconstructionPollTimer = null;
    if (!data || !["queued", "running"].includes(data.runStatus)) return;
    state.deconstructionPollTimer = window.setTimeout(() => {
      state.deconstructionPollTimer = null;
      if (state.screen === "deconstruction" && state.deconstructionProjectId === data.projectId) loadDeconstructionWorkspace(data.projectId, { silent: true });
    }, 1300);
  }

  function renderArchivePage(data) {
    state.archiveWorkspace = data;
    state.archiveProjectId = data.project_id;
    state.archiveMode = data.mode || "independent";
    elements.archivePageProjectTitle.textContent = data.title || "—";
    elements.archiveModeLabel.textContent = archiveModeLabel(data.mode);
    const archive = data.archive || { characters: [], storylines: [], foreshadowing: [], questions: [], snapshots: [] };
    const snapshots = data.available_snapshots || archive.snapshots || [];
    const latestNumber = archive.latest_chapter_number || data.selected_chapter_number || 0;
    if (data.mode === "ai_assisted") state.aiProjectId = data.project_id;
    elements.archivePageStatus.textContent = data.read_only
      ? `第 ${data.selected_chapter_number} 章快照 · 只读`
      : `当前状态 · 截至第 ${latestNumber || "—"} 章`;
    elements.archiveAiLink.classList.toggle("is-hidden", data.mode !== "ai_assisted");
    elements.archivePageSnapshotSelect.innerHTML = `<option value="">最新状态</option>${snapshots.map((snapshot) => `<option value="${snapshot.chapter_number}" ${data.read_only && String(data.selected_chapter_number) === String(snapshot.chapter_number) ? "selected" : ""}>第 ${snapshot.chapter_number} 章快照</option>`).join("")}`;
    if (!data.initialized) {
      elements.archivePageContent.innerHTML = `<div class="archive-empty-page"><div><div class="empty-mark">⌁</div><h2>档案还在等第一条确定信息</h2><p>完成一个章节，或在 AI 导演台完成一轮正文后，人物、剧情线、伏笔和疑问点会按来源章节出现在这里。</p></div></div>`;
      return;
    }
    const characters = archive.characters || [];
    const storylines = archive.storylines || [];
    const foreshadowing = archive.foreshadowing || [];
    const questions = archive.questions || [];
    const timelineNodes = snapshots.length ? snapshots.map((snapshot) => `
      <div class="archive-timeline-node ${String(data.selected_chapter_number || "") === String(snapshot.chapter_number) || (!data.read_only && snapshot.chapter_number === latestNumber) ? "is-current" : ""}">
        <button type="button" aria-label="查看第 ${snapshot.chapter_number} 章快照" data-action="archive-snapshot" data-chapter-number="${snapshot.chapter_number}"></button>
        <strong>第 ${snapshot.chapter_number} 章</strong><small>${escapeHtml(archiveAnalysisLabel(snapshot.analysis_label))}</small>
      </div>`).join("") : `<p class="archive-note">完成本章后，这里会出现可回看的时间节点。</p>`;
    const empty = (label) => `<p class="archive-note">${label}还没有记录；完成后会在来源章节留下它。</p>`;
    elements.archivePageContent.innerHTML = `
      <section class="archive-timeline-card" aria-label="章节快照时间线">
        <div class="archive-timeline-intro"><span class="eyebrow">故事脉络 / ${data.read_only ? "历史" : "最新"}</span><strong>${data.read_only ? `第 ${data.selected_chapter_number} 章` : "最新状态"}</strong><p>${data.read_only ? "历史快照不会改变当前档案。" : "默认显示当前稿本的最新分析。"}</p></div>
        <div class="archive-timeline-track">${timelineNodes}</div>
      </section>
      <nav class="archive-section-nav" aria-label="档案分类"><a class="archive-section-link is-selected" href="#archive-characters" data-archive-anchor="archive-characters"><span>01</span>人物</a><a class="archive-section-link" href="#archive-storylines" data-archive-anchor="archive-storylines"><span>02</span>剧情线</a><a class="archive-section-link" href="#archive-foreshadowing" data-archive-anchor="archive-foreshadowing"><span>03</span>伏笔</a><a class="archive-section-link" href="#archive-questions" data-archive-anchor="archive-questions"><span>04</span>疑问点</a></nav>
      <div class="archive-detail-grid">
        <section id="archive-characters" class="archive-detail-panel" data-archive-section="archive-characters"><header><h2>人物</h2><span class="archive-count">${characters.length}</span></header><div class="archive-card-list">${characters.length ? characters.map((character) => `<article class="archive-full-character"><div class="character-glyph" aria-hidden="true"><span></span></div><div><strong>${escapeHtml(character.name)}</strong><small>${escapeHtml(character.role)} · 来源第 ${character.source_chapter_number} 章</small><p>${escapeHtml(character.profile)} ${escapeHtml(character.current_state || "")}</p><span class="archive-source">来源 / 第 ${character.source_chapter_number} 章</span></div></article>`).join("") : empty("人物")}</div></section>
        <section id="archive-storylines" class="archive-detail-panel" data-archive-section="archive-storylines"><header><h2>剧情线</h2><span class="archive-count">${storylines.length}</span></header><div class="archive-card-list">${storylines.length ? storylines.map((item) => `<article class="archive-thread-item"><div class="archive-thread-line"><span></span></div><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.summary)}</p><span class="archive-source">来源 / 第 ${item.source_chapter_number} 章</span></article>`).join("") : empty("剧情线")}</div></section>
        <section id="archive-foreshadowing" class="archive-detail-panel" data-archive-section="archive-foreshadowing"><header><h2>伏笔</h2><span class="archive-count">${foreshadowing.length}</span></header><div class="archive-card-list">${foreshadowing.length ? foreshadowing.map((item) => `<article class="archive-thread-item"><strong>${escapeHtml(item.status === "open" ? "未解 · " : "已回收 · ")}${escapeHtml(item.text)}</strong><p>状态来自本次档案分析，作者可以继续观察它如何变化。</p><span class="archive-source">来源 / 第 ${item.source_chapter_number} 章</span></article>`).join("") : empty("伏笔")}</div></section>
        <section id="archive-questions" class="archive-detail-panel questions-panel" data-archive-section="archive-questions"><header><h2>疑问点</h2><span class="archive-count">${questions.length}</span></header><div class="archive-card-list">${questions.length ? questions.map((item) => `<article class="archive-question"><strong>${escapeHtml(item.text)}</strong><small>来源 / 第 ${item.source_chapter_number} 章 · 这是需要回看的线索，不是阻断写作的错误。</small></article>`).join("") : empty("疑问点")}</div></section>
      </div>
      <div class="archive-footer-legend"><span><i></i>已按来源章节记录</span><span><i class="red"></i>温和疑问，保持可回看</span><span class="mono">${escapeHtml(archiveAnalysisLabel(archive.analysis_label))}</span></div>`;
    bindArchiveAnchors();
  }

  function bindArchiveAnchors() {
    const links = $$("[data-archive-anchor]", elements.archivePageContent);
    const sections = $$("[data-archive-section]", elements.archivePageContent);
    if (!links.length || !sections.length) return;
    state.archiveScrollSpyCleanup?.();
    state.archiveAnchorObserver?.disconnect?.();
    state.archiveAnchorObserver = null;
    state.archiveAnchorIntent = null;
    window.clearTimeout(state.archiveAnchorUnlockTimer);
    state.archiveAnchorUnlockTimer = null;
    const activate = (id) => {
      links.forEach((link) => {
        const active = link.dataset.archiveAnchor === id;
        link.classList.toggle("is-selected", active);
        if (active) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      });
    };
    const scheduleArchiveAnchorStability = () => {
      window.clearTimeout(state.archiveAnchorUnlockTimer);
      state.archiveAnchorUnlockTimer = window.setTimeout(() => {
        state.archiveAnchorUnlockTimer = null;
        if (state.archiveAnchorIntent) state.archiveAnchorIntent.programmatic = false;
      }, 450);
    };
    const cancelArchiveAnchorIntent = () => {
      if (!state.archiveAnchorIntent) return;
      state.archiveAnchorIntent = null;
      window.clearTimeout(state.archiveAnchorUnlockTimer);
      state.archiveAnchorUnlockTimer = null;
      update();
    };
    const update = () => {
      if (state.archiveAnchorIntent) {
        activate(state.archiveAnchorIntent.id);
        if (state.archiveAnchorIntent.programmatic) scheduleArchiveAnchorStability();
        return;
      }
      const scrollY = window.scrollY || window.pageYOffset || 0;
      const maxScroll = Math.max(
        0,
        document.documentElement.scrollHeight - window.innerHeight,
      );
      let activeSection = sections[0];
      const atDocumentBottom = maxScroll <= 0 || scrollY >= maxScroll - 4;
      if (atDocumentBottom) {
        activeSection = sections[sections.length - 1];
      } else {
        const focusLine = scrollY + Math.max(120, Math.min(window.innerHeight * 0.55, window.innerHeight - 160));
        sections.forEach((section) => {
          const rect = section.getBoundingClientRect();
          if (rect.top <= focusLine - scrollY && rect.bottom >= 0) activeSection = section;
        });
      }
      activate(activeSection.id);
    };
    const handleArchiveScrollEnd = () => {
      if (state.archiveAnchorIntent) {
        scheduleArchiveAnchorStability();
        return;
      }
      update();
    };
    links.forEach((link) => link.addEventListener("click", (event) => {
      const id = link.dataset.archiveAnchor;
      const target = document.getElementById(id);
      event.preventDefault();
      if (target) {
        state.archiveAnchorIntent = { id, programmatic: true };
        activate(target.id);
        scheduleArchiveAnchorStability();
        target.scrollIntoView({
          behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
          block: "center",
        });
      }
      window.history.replaceState(null, "", `#${id}`);
    }));
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    window.addEventListener("scrollend", handleArchiveScrollEnd);
    window.addEventListener("wheel", cancelArchiveAnchorIntent, { capture: true, passive: true });
    window.addEventListener("touchstart", cancelArchiveAnchorIntent, { capture: true, passive: true });
    window.addEventListener("touchmove", cancelArchiveAnchorIntent, { capture: true, passive: true });
    window.addEventListener("pointerdown", cancelArchiveAnchorIntent, { capture: true, passive: true });
    window.addEventListener("pointermove", cancelArchiveAnchorIntent, { capture: true, passive: true });
    const handleArchiveAnchorKeydown = (event) => {
      const scrollKeys = ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "PageUp", "PageDown", "Home", "End", " ", "Spacebar"];
      const target = event.target;
      const isEditable = target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
      if (!isEditable && scrollKeys.includes(event.key)) cancelArchiveAnchorIntent();
    };
    window.addEventListener("keydown", handleArchiveAnchorKeydown, { capture: true });
    const cleanup = () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
      window.removeEventListener("scrollend", handleArchiveScrollEnd);
      window.removeEventListener("wheel", cancelArchiveAnchorIntent, true);
      window.removeEventListener("touchstart", cancelArchiveAnchorIntent, true);
      window.removeEventListener("touchmove", cancelArchiveAnchorIntent, true);
      window.removeEventListener("pointerdown", cancelArchiveAnchorIntent, true);
      window.removeEventListener("pointermove", cancelArchiveAnchorIntent, true);
      window.removeEventListener("keydown", handleArchiveAnchorKeydown, true);
      window.clearTimeout(state.archiveAnchorUnlockTimer);
      state.archiveAnchorUnlockTimer = null;
      state.archiveAnchorIntent = null;
      if (state.archiveScrollSpyCleanup === cleanup) state.archiveScrollSpyCleanup = null;
    };
    state.archiveScrollSpyCleanup = cleanup;
    update();
  }

  async function resolveChapterForProject(projectId) {
    let workspace = state.editorProjectId === projectId ? state.workspace : null;
    if (!workspace?.active_version) {
      workspace = await requestJson(`/api/independent/projects/${encodeURIComponent(projectId)}`);
    }
    const chapter = chooseActiveChapter(workspace?.active_version);
    if (chapter) syncActiveChapterUrl(chapter.chapter_id);
    return chapter;
  }

  async function loadArchiveWorkspace(projectId, chapterNumber = null) {
    if (!projectId) return;
    state.archiveProjectId = projectId;
    setActiveScreen("archive");
    try {
      if (chapterNumber === null) await resolveChapterForProject(projectId);
      const selectedChapterNumber = chapterNumber;
      const query = selectedChapterNumber ? `?chapter_number=${encodeURIComponent(selectedChapterNumber)}` : "";
      const payload = await requestJson(`/api/archive/projects/${encodeURIComponent(projectId)}${query}`);
      renderArchivePage(payload);
      setWorkspaceNotice(elements.archivePageNotice, "");
      void loadNotifications();
    } catch (error) {
      if (error.status === 401) {
        state.account = null;
        state.sessionExpired = error.code === "session_expired";
        navigate("/login", { replace: true });
        return;
      }
      setWorkspaceNotice(elements.archivePageNotice, error.message || "故事档案读取失败，请稍后重试。", "red");
    }
  }

  async function loadDeconstructionWorkspace(projectId, { silent = false } = {}) {
    if (!projectId) return;
    const loadToken = ++state.deconstructionLoadToken;
    state.deconstructionProjectId = projectId;
    window.clearTimeout(state.deconstructionPollTimer);
    state.deconstructionPollTimer = null;
    setActiveScreen("deconstruction");
    if (!silent) {
      renderDeconstructionLoading();
      setWorkspaceNotice(elements.deconstructionNotice, "");
    }
    try {
      await resolveChapterForProject(projectId);
      if (loadToken !== state.deconstructionLoadToken || state.deconstructionProjectId !== projectId) return;
      const data = await deconstructionApi.read(projectId);
      if (loadToken !== state.deconstructionLoadToken || state.deconstructionProjectId !== projectId) return;
      renderDeconstructionPage(data);
      setWorkspaceNotice(elements.deconstructionNotice, "");
      void loadNotifications();
    } catch (error) {
      if (loadToken !== state.deconstructionLoadToken || state.deconstructionProjectId !== projectId) return;
      if (error.status === 401) {
        state.account = null;
        state.sessionExpired = error.code === "session_expired";
        navigate("/login", { replace: true });
        return;
      }
      setWorkspaceNotice(elements.deconstructionNotice, error.message || "作品拆解读取失败，请稍后重试。", "red");
      renderDeconstructionReadError(error.message);
    }
  }

  async function runDeconstructionAction(action) {
    const projectId = state.deconstructionProjectId;
    if (!projectId) return;
    const current = state.deconstructionWorkspace;
    const allowed = action === "retry"
      ? current?.effectiveStatus === "failed_retryable" && current.actions.retry
      : (current?.effectiveStatus === "stale" || current?.effectiveStatus === "rebuild_required") && current.actions.rebuild;
    if (!allowed) return;
    const buttons = $$(`[data-action="deconstruction-${action}"]`, elements.deconstructionPageContent);
    buttons.forEach((button) => { button.disabled = true; });
    setWorkspaceNotice(elements.deconstructionNotice, action === "rebuild" ? "正在为当前稿本排队重建…" : "正在提交拆解任务…", "blue");
    try {
      const source = current.source || {};
      const actionPayload = {
        idempotency_key: `browser-deconstruction-${projectId}-${action}-${source.versionId || "none"}-${source.revision ?? "none"}`,
      };
      if (source.versionId) actionPayload.expected_source_version_id = source.versionId;
      if (source.revision !== null) actionPayload.expected_source_revision = source.revision;
      if (source.contentHash) actionPayload.expected_source_hash = source.contentHash;
      const next = await deconstructionApi.mutate(projectId, action, actionPayload);
      renderDeconstructionPage(next);
      setWorkspaceNotice(elements.deconstructionNotice, "", "blue");
      showToast(action === "rebuild" ? "当前稿本已开始重建。" : "拆解任务已重新排队。", "blue");
    } catch (error) {
      buttons.forEach((button) => { button.disabled = false; });
      if (error.status === 409) {
        await loadDeconstructionWorkspace(projectId);
        setWorkspaceNotice(elements.deconstructionNotice, "正文来源已经变化，已重新读取最新拆解状态。", "red");
      } else {
        setWorkspaceNotice(elements.deconstructionNotice, error.message || "拆解任务没有提交成功，请稍后重试。", "red");
      }
    }
  }

  function deconstructionEvidenceFromNode(actionNode) {
    return {
      id: actionNode.dataset.evidenceId || "",
      documentId: actionNode.dataset.documentId || "",
      sourceVersionId: actionNode.dataset.sourceVersionId || "",
      sourceRevision: deconstructionNumber(actionNode.dataset.sourceRevision),
      sourceHash: actionNode.dataset.sourceHash || "",
      chapterId: actionNode.dataset.chapterId || "",
      chapterNumber: deconstructionNumber(actionNode.dataset.chapterNumber),
      granularity: actionNode.dataset.granularity === "chapter" ? "chapter" : "span",
      charStart: deconstructionNumber(actionNode.dataset.charStart),
      charEnd: deconstructionNumber(actionNode.dataset.charEnd),
      offsetUnit: actionNode.dataset.offsetUnit || "",
      excerpt: actionNode.dataset.excerpt || "",
      label: "正文证据",
    };
  }

  function deconstructionEvidenceIdentityMatches(left, right) {
    if (!left || !right) return false;
    return ["id", "documentId", "sourceVersionId", "sourceRevision", "sourceHash", "chapterId", "chapterNumber", "granularity", "charStart", "charEnd", "offsetUnit"]
      .every((key) => left[key] === right[key]);
  }

  function deconstructionEvidenceMatchesSource(data, evidence, result) {
    const source = data?.source;
    return Boolean(
      data?.effectiveStatus === "completed"
      && data.runStatus === "completed"
      && data.sourceMatch
      && source?.match
      && result?.documentId
      && evidence?.documentId
      && evidence.documentId === result.documentId
      && evidence.sourceVersionId
      && evidence.sourceVersionId === source.versionId
      && evidence.sourceRevision !== null
      && evidence.sourceRevision === source.revision
      && evidence.sourceHash
      && evidence.sourceHash === source.contentHash
      && evidence.chapterId
      && evidence.chapterNumber !== null
    );
  }

  function openDeconstructionEvidenceDialog() {
    const dialog = elements.deconstructionEvidenceDialog;
    if (!dialog) return;
    rememberDialogFocus(dialog);
    if (typeof dialog.showModal === "function" && !dialog.open) dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  function closeDeconstructionEvidenceDialog({ clear = true } = {}) {
    const dialog = elements.deconstructionEvidenceDialog;
    if (dialog?.open && typeof dialog.close === "function") dialog.close();
    else dialog?.removeAttribute("open");
    if (clear) {
      state.deconstructionEvidenceRequestToken += 1;
      state.pendingEvidence = null;
    }
  }

  function renderDeconstructionEvidenceLoading() {
    elements.deconstructionEvidenceTitle.textContent = "正在读取证据";
    elements.deconstructionEvidenceContent.innerHTML = `<div class="deconstruction-evidence-dialog-loading" role="status">正在从服务端读取这条证据……</div>`;
    elements.locateDeconstructionEvidenceButton.disabled = true;
    elements.locateDeconstructionEvidenceButton.textContent = "等待证据校验";
  }

  function renderDeconstructionEvidenceDialog(payload, fallbackEvidence = null, current = false, reason = "") {
    const rawEvidence = payload?.evidence || fallbackEvidence || {};
    const evidence = normalizeEvidenceRef(rawEvidence) || fallbackEvidence;
    const chapter = payload?.chapter || {};
    const chapterNumber = evidence?.chapterNumber ?? deconstructionNumber(chapter.chapter_number);
    const chapterTitle = deconstructionText(chapter.title, "来源章节");
    const sourceIsCurrent = current
      && payload?.source_matches_current === true
      && payload?.historical === false
      && chapter.source_available !== false;
    const precise = Boolean(
      sourceIsCurrent
      && evidence
      && evidence.granularity === "span"
      && evidence.offsetUnit === DECONSTRUCTION_OFFSET_UNIT
      && evidence.charStart !== null
      && evidence.charStart >= 0
      && evidence.charEnd !== null
      && evidence.charEnd >= evidence.charStart,
    );
    elements.deconstructionEvidenceTitle.textContent = sourceIsCurrent ? "证据回链" : "历史证据回链";
    elements.deconstructionEvidenceContent.innerHTML = `<article class="deconstruction-evidence-dialog-card ${sourceIsCurrent ? "is-current" : "is-historical"}"><div class="depth-card-topline"><span class="depth-card-label">${sourceIsCurrent ? "当前稿本 · 只读" : "历史稿本 · 只读"}</span><span class="mono">${chapterNumber === null ? "章节待定位" : `第 ${escapeHtml(chapterNumber)} 章`}</span></div><h3>${escapeHtml(evidence?.label || "正文证据")}</h3><p class="deconstruction-evidence-dialog-chapter">${escapeHtml(chapterTitle)}</p>${evidence?.excerpt ? `<blockquote>“${escapeHtml(evidence.excerpt)}”</blockquote>` : `<p class="depth-empty-note">这条证据只提供章节级定位，没有保留正文片段。</p>`}<dl class="depth-fact-list"><div><dt>定位精度</dt><dd>${precise ? "UTF-16 字符位移已校验" : "章节级回看"}</dd></div>${precise ? `<div><dt>字符范围</dt><dd>${escapeHtml(`${evidence.charStart}–${evidence.charEnd}`)} · UTF-16 code unit</dd></div>` : ""}<div><dt>回看边界</dt><dd>${sourceIsCurrent ? "仅可定位到当前稿本，不会改写正文" : "历史来源只读，不跳转当前同编号章节"}</dd></div></dl>${reason ? `<p class="depth-evidence-reason">${escapeHtml(reason)}</p>` : ""}</article>`;
    elements.locateDeconstructionEvidenceButton.disabled = !precise;
    elements.locateDeconstructionEvidenceButton.textContent = precise ? "在当前正文中定位" : "当前仅可章节级回看";
    elements.locateDeconstructionEvidenceButton.title = precise ? "按 UTF-16 字符位移在当前稿本定位" : "历史或章节级证据不能定位当前正文";
    state.pendingEvidence = sourceIsCurrent && evidence ? { ...evidence, projectId: state.deconstructionProjectId } : null;
  }

  function showHistoricalDeconstructionEvidence(payload, reason) {
    renderDeconstructionEvidenceDialog(payload, null, false, reason || "来源版本、修订号或哈希未通过校验；当前页面只保留章节级回看。");
    openDeconstructionEvidenceDialog();
  }

  async function openDeconstructionEvidence(actionNode) {
    const projectId = state.deconstructionProjectId;
    if (!projectId) return;
    const clickedEvidence = deconstructionEvidenceFromNode(actionNode);
    if (!clickedEvidence.id) return;
    state.pendingEvidence = clickedEvidence;
    const requestToken = ++state.deconstructionEvidenceRequestToken;
    openDeconstructionEvidenceDialog();
    renderDeconstructionEvidenceLoading();
    let current;
    let endpoint;
    try {
      // 点击后只把 evidence id 发给真实端点；先重读 canonical source，避免用旧页面快照定位正文。
      current = await deconstructionApi.read(projectId);
      endpoint = await deconstructionApi.readEvidence(projectId, clickedEvidence.id);
    } catch (error) {
      if (requestToken !== state.deconstructionEvidenceRequestToken) return;
      state.pendingEvidence = null;
      elements.deconstructionEvidenceTitle.textContent = "证据暂时读不到";
      elements.deconstructionEvidenceContent.innerHTML = `<p class="depth-evidence-reason">${escapeHtml(error.message || "证据回链读取失败，请稍后重试。")} </p>`;
      elements.locateDeconstructionEvidenceButton.disabled = true;
      return;
    }
    if (requestToken !== state.deconstructionEvidenceRequestToken) return;
    const currentEvidence = current.result?.depthReport?.evidence?.find((item) => item.id === clickedEvidence.id)
      || current.result?.evidenceRefs?.find((item) => item.id === clickedEvidence.id)
      || null;
    const endpointEvidence = normalizeEvidenceRef(endpoint?.evidence);
    const endpointIsCurrent = endpoint?.source_matches_current === true
      && endpoint?.historical === false
      && endpoint?.chapter?.source_available === true;
    const precondition = deconstructionEvidenceMatchesSource(current, currentEvidence, current.result)
      && deconstructionEvidenceIdentityMatches(clickedEvidence, currentEvidence)
      && deconstructionEvidenceIdentityMatches(currentEvidence, endpointEvidence)
      && endpointIsCurrent;
    if (!precondition) {
      state.pendingEvidence = null;
      showHistoricalDeconstructionEvidence(endpoint, current.sourceMatch ? "这条证据的文档、来源版本、修订号或哈希未通过校验。" : "当前正文已经变化，这条证据属于历史稿本。");
      return;
    }
    renderDeconstructionEvidenceDialog(endpoint, currentEvidence, true);
  }

  async function locateDeconstructionEvidence() {
    const projectId = state.deconstructionProjectId;
    const evidence = state.pendingEvidence;
    if (!projectId || !evidence) return;
    const current = state.deconstructionWorkspace;
    if (!deconstructionEvidenceMatchesSource(current, evidence, current?.result)) {
      closeDeconstructionEvidenceDialog();
      setWorkspaceNotice(elements.deconstructionNotice, "当前正文已经变化，这条证据只保留章节级回看。", "red");
      return;
    }
    closeDeconstructionEvidenceDialog({ clear: false });
    // Evidence still returns through navigate(`/independent/${encodeURIComponent(projectId)}`) semantics;
    // editorPath adds the verified chapter query so the return target is exact.
    const navigated = await navigate(editorPath(projectId, evidence.chapterId || chapterIdFromLocation()));
    if (!navigated) {
      state.pendingEvidence = null;
      return;
    }
    state.editorMode = "independent";
    await loadIndependentWorkspace(projectId);
    const version = activeEditorVersion();
    let afterNavigation = null;
    try {
      afterNavigation = await deconstructionApi.read(projectId);
    } catch (error) {
      // 编辑器已经打开，但没有新的来源快照时，仍禁止精确定位。
      afterNavigation = null;
    }
    const sourceStillMatches = deconstructionEvidenceMatchesSource(afterNavigation, evidence, afterNavigation?.result)
      && version?.version_id === afterNavigation?.source?.versionId;
    const chapter = sourceStillMatches
      ? version?.chapters?.find((item) => evidence.chapterId && item.chapter_id === evidence.chapterId)
      : null;
    if (!chapter) {
      state.pendingEvidence = null;
      setEditorNotice("已回到正文，但来源稿本已经变化；当前只保留章节级回看。", "red");
      return;
    }
    state.activeChapterId = chapter.chapter_id;
    state.editorDirty = false;
    state.editorConflict = null;
    renderEditorWorkspace();
    const content = elements.chapterEditor.value || "";
    const validStart = sourceStillMatches
      && evidence.offsetUnit === DECONSTRUCTION_OFFSET_UNIT
      && evidence.charStart !== null
      && evidence.charStart >= 0
      && evidence.charStart <= content.length;
    const validEnd = validStart && evidence.charEnd !== null && evidence.charEnd >= evidence.charStart && evidence.charEnd <= content.length;
    const excerptMatches = validEnd && deconstructionEvidenceExcerptMatches(evidence, content);
    if (excerptMatches) {
      elements.chapterEditor.focus({ preventScroll: true });
      elements.chapterEditor.setSelectionRange(evidence.charStart, evidence.charEnd);
    } else {
      elements.chapterEditor.focus({ preventScroll: true });
    }
    const anchorText = excerptMatches
      ? `已按 UTF-16 字符位移选择正文中的第 ${evidence.charStart}–${evidence.charEnd} 位。`
      : sourceStillMatches
        ? evidence.excerpt
          ? "正文片段与证据摘录不一致，已降级为章节级回看。"
          : "当前证据未提供正文片段，已降级为章节级回看。"
        : "证据来自另一稿本，当前只保留章节级回看。";
    setEditorNoticeHtml(`<strong>已回到来源证据。</strong> 第 ${chapter.chapter_number} 章 · ${escapeHtml(anchorText)}${evidence.excerpt ? `<span class="editor-evidence-excerpt">“${escapeHtml(evidence.excerpt)}”</span>` : ""}`, "blue");
    state.pendingEvidence = null;
  }

  function renderAIConversation(messages) {
    const items = messages || [];
    elements.aiConversationCount.textContent = `${items.filter((item) => item.role === "author").length} 轮`;
    elements.aiConversation.innerHTML = items.length ? items.map((message) => `
      <article class="ai-message ${message.role === "editor" ? "is-editor" : ""}"><div class="ai-message-mark" aria-hidden="true">${message.role === "editor" ? "编" : "你"}</div><div class="ai-message-content"><div class="ai-message-meta"><strong>${message.role === "editor" ? "主编" : "你"}</strong><span>${escapeHtml(formatDate(message.created_at))}</span></div><p>${escapeHtml(message.content)}</p></div></article>`).join("") : `<div class="ai-conversation-empty">把一条想法交给主编。<br />他会先整理方向，再把需要你决定的地方留下来。</div>`;
    elements.aiConversation.scrollTop = elements.aiConversation.scrollHeight;
  }

  function blueprintFieldValue(blueprint, key) {
    if (key === "volume_outline") return (blueprint?.[key] || []).join("\n");
    return blueprint?.[key] || "";
  }

  function modelRuntimeLabel(workspace) {
    if (workspace?.mode === "live" && workspace?.model_runtime?.status === "connected") {
      return "模型已连接·开发测试，不结算创作积分";
    }
    if (workspace?.mode === "live" && workspace?.model_runtime?.status === "failed") {
      return "模型调用失败，可重试；不消耗创作积分";
    }
    return "演示推演 · 未配置模型 Key · 不消耗创作积分";
  }

  function renderAIStudio(workspace) {
    state.aiWorkspace = workspace;
    state.aiProjectId = workspace.project_id;
    state.aiRunId = workspace.active_run?.run_id || null;
    elements.aiStudioProjectTitle.textContent = workspace.title || "—";
    elements.aiStudioModelLabel.textContent = modelRuntimeLabel(workspace);
    elements.aiStudioBlueprintState.textContent = workspace.blueprint_status === "ready_to_confirm" ? "字段已齐，待确认" : workspace.blueprint_status === "director_ready" ? "当前蓝图已确认" : "蓝图草稿";
    elements.blueprintRevision.textContent = `V / ${workspace.blueprint_revision || 0}`;
    renderAIConversation(workspace.messages);
    const fields = ["core_premise", "core_conflict", "protagonist", "target_length", "protagonist_motivation", "key_relationships", "world_rules", "ending_direction", "volume_outline"];
    fields.forEach((key) => {
      const input = $(`[data-blueprint-field="${key}"]`);
      if (input && document.activeElement !== input) input.value = blueprintFieldValue(workspace.blueprint, key);
    });
    const missingLabels = (workspace.missing_fields || []).map((item) => item.label);
    elements.blueprintMissing.innerHTML = missingLabels.length ? `还需要决定：${missingLabels.map(escapeHtml).join("、")}` : "蓝图字段已齐，待作者确认。";
    elements.blueprintMissing.classList.toggle("is-ready", !missingLabels.length);
    elements.blueprintHint.textContent = missingLabels.length ? "字段未齐前，导演台不会开始生成正文；你可以继续对话，也可以直接编辑右侧字段。" : "字段已经齐全。确认后才会创建导演台任务，重复确认不会重复扣积分。";
    elements.confirmBlueprintButton.disabled = !workspace.can_confirm || workspace.blueprint_status === "director_ready";
    elements.confirmBlueprintButton.textContent = "确认蓝图并开始创作 →";
    elements.professionalRoleStatus.innerHTML = (workspace.role_statuses || []).map((role) => `<article class="professional-role"><strong>${escapeHtml(role.label)}</strong><span>${escapeHtml(role.state)}</span><small>${escapeHtml(role.output || "等待主编整理")}</small></article>`).join("");
  }

  async function loadAIWorkspace(projectId, director = false) {
    if (!projectId) return;
    const loadToken = ++state.aiLoadToken;
    state.aiProjectId = projectId;
    setActiveScreen(director ? "aiDirector" : "aiStudio");
    try {
      const workspace = await requestJson(`/api/ai/projects/${encodeURIComponent(projectId)}`);
      if (loadToken !== state.aiLoadToken || state.aiProjectId !== projectId) return;
      state.aiWorkspace = workspace;
      if (director) await renderAIDirector(workspace);
      else renderAIStudio(workspace);
      void loadNotifications();
    } catch (error) {
      if (loadToken !== state.aiLoadToken || state.aiProjectId !== projectId) return;
      if (error.status === 401) {
        state.account = null;
        state.sessionExpired = error.code === "session_expired";
        navigate("/login", { replace: true });
        return;
      }
      setWorkspaceNotice(director ? elements.aiDirectorNotice : elements.aiStudioNotice, error.message || "AI 工作区读取失败，请稍后重试。", "red");
    }
  }

  async function submitAIMessage(event) {
    event.preventDefault();
    const content = elements.aiMessageInput.value.trim();
    if (!content || !state.aiProjectId) return;
    elements.aiMessageButton.disabled = true;
    elements.aiMessageButton.textContent = "主编整理中…";
    try {
      const workspace = await requestJson(`/api/ai/projects/${encodeURIComponent(state.aiProjectId)}/messages`, { method: "POST", body: JSON.stringify({ content }) });
      elements.aiMessageInput.value = "";
      renderAIStudio(workspace);
      setWorkspaceNotice(elements.aiStudioNotice, "主编已把这轮讨论写入服务端蓝图。", "blue");
    } catch (error) {
      setWorkspaceNotice(elements.aiStudioNotice, error.message || "主编暂时没有回应，请稍后重试。", "red");
    } finally {
      elements.aiMessageButton.disabled = false;
      elements.aiMessageButton.innerHTML = '发送给主编 <span aria-hidden="true">→</span>';
    }
  }

  function blueprintPayload() {
    const payload = { expected_revision: state.aiWorkspace?.blueprint_revision || 0 };
    document.querySelectorAll("[data-blueprint-field]").forEach((input) => {
      const key = input.dataset.blueprintField;
      payload[key] = key === "volume_outline" ? input.value.split("\n").map((item) => item.trim()).filter(Boolean) : input.value.trim();
    });
    return payload;
  }

  async function saveAIBlueprint(event) {
    event.preventDefault();
    if (!state.aiProjectId || !state.aiWorkspace) return;
    elements.saveBlueprintButton.disabled = true;
    try {
      const workspace = await requestJson(`/api/ai/projects/${encodeURIComponent(state.aiProjectId)}/blueprint`, { method: "PUT", body: JSON.stringify(blueprintPayload()) });
      renderAIStudio(workspace);
      setWorkspaceNotice(elements.aiStudioNotice, "蓝图字段已保存到服务端。", "blue");
    } catch (error) {
      setWorkspaceNotice(elements.aiStudioNotice, error.message || "蓝图保存失败，请重新载入后再试。", "red");
    } finally {
      elements.saveBlueprintButton.disabled = false;
    }
  }

  async function confirmAIBlueprint() {
    if (!state.aiProjectId || !state.aiWorkspace || !state.aiWorkspace.can_confirm) return;
    elements.confirmBlueprintButton.disabled = true;
    try {
      const workspace = await requestJson(`/api/ai/projects/${encodeURIComponent(state.aiProjectId)}/blueprint/confirm`, { method: "POST", body: JSON.stringify({ expected_revision: state.aiWorkspace.blueprint_revision, idempotency_key: `blueprint-${state.aiProjectId}-${state.aiWorkspace.blueprint_revision}` }) });
      state.aiWorkspace = workspace;
      showToast("蓝图已确认，导演台准备就绪。");
      navigate(`/ai/${encodeURIComponent(state.aiProjectId)}/director`);
      await loadAIWorkspace(state.aiProjectId, true);
    } catch (error) {
      setWorkspaceNotice(elements.aiStudioNotice, error.message || "蓝图还不能确认。", "red");
      elements.confirmBlueprintButton.disabled = false;
    }
  }

  const directorStages = ["排队", "角色推演", "等待关键节点选择", "正文生成", "审校", "更新档案", "完成"];

  function renderDirectorStageTrack(run) {
    const history = run?.stage_history || [];
    const current = run?.current_stage || "排队";
    const stages = run?.current_stage === "失败，可重试" && !directorStages.includes("失败，可重试") ? [...directorStages, "失败，可重试"] : directorStages;
    elements.directorStageTrack.innerHTML = stages.map((stage, index) => {
      const done = history.includes(stage) && stage !== current;
      const currentClass = stage === current || (current === "完成" && stage === "更新档案") ? "is-current" : done ? "is-done" : "";
      return `<div class="director-stage-node ${currentClass}"><b>${index + 1}</b><strong>${stage}</strong></div>`;
    }).join("");
  }

  function renderDirectorRoles(workspace) {
    const roles = workspace.role_statuses || [];
    const characters = workspace.story_characters || [];
    const professionalMarkup = `<section class="director-professional-block"><div class="director-layer-heading"><span class="eyebrow">专业角色层</span><small>读取职责所需的全局材料</small></div><div class="director-professional-grid">${roles.map((role) => {
      return `<article class="director-professional-status"><strong>${escapeHtml(role.label)}</strong><span>${escapeHtml(role.state)}</span><small>${escapeHtml(role.output || "等待后台轮转")}</small></article>`;
    }).join("")}</div></section>`;
    const storyMarkup = `<section class="director-story-layer"><div class="director-layer-heading"><span class="eyebrow">故事人物层</span><small>只展示各自可知的目标、事实与情绪</small></div><div class="director-character-grid">${characters.map((character) => {
      return `<article class="director-story-character"><div class="director-character-head"><span class="director-role-mark" aria-hidden="true">${escapeHtml(character.name.slice(0, 1))}</span><div><strong>${escapeHtml(character.name)}</strong><small>${escapeHtml(character.role || "故事人物")} · ${escapeHtml(character.current_scene || "当前场景")}</small></div></div><p><b>当前目标</b>${escapeHtml(character.goal || "待角色推演")}</p><p><b>角色可知</b>${escapeHtml((character.known_facts || []).join("；") || "暂无公开事实")}</p><p><b>情绪</b>${escapeHtml(character.emotional_state || "未定")}</p></article>`;
    }).join("")}</div></section>`;
    const shared = workspace.blueprint?.world_rules;
    return `${professionalMarkup}${storyMarkup}${shared ? `<div class="director-shared-memory"><strong>共享世界规则 / 两层都可读取</strong><p>${escapeHtml(shared)}</p></div>` : ""}`;
  }

  function renderDirectorStart(workspace) {
    return `<div class="director-workspace-grid"><section class="director-main-column"><div class="director-section-heading"><h2>后台轮转已经准备好</h2><span>确认后只维护一条正式正文</span></div><div class="director-preview"><div class="director-chapter-mark">第一章</div><div class="director-preview-copy"><strong>${escapeHtml(workspace.blueprint?.core_premise || "故事蓝图")}</strong><p>选择一种创作策略。全自动继续会自动走完安全节点；关键节点暂停会在三选一处等待作者决定。</p><small>排队 → 角色推演 → 正文生成 → 审校 → 更新档案</small></div></div><div class="director-completed-actions"><button class="button button-primary" type="button" data-action="start-ai-director" data-strategy="pause_at_key_nodes">关键节点暂停</button><button class="button button-outline" type="button" data-action="start-ai-director" data-strategy="full_auto">全自动继续</button></div></section><aside class="director-choice-panel"><span class="eyebrow">创作策略</span><h2>由谁在关键处做决定？</h2><p>后台专业角色会各自推演，但不会变成四个并列聊天窗口。</p><p class="director-selected-strategy">当前设置：${workspace.settings?.strategy === "full_auto" ? "全自动继续" : "关键节点暂停"}</p><div class="director-settings"><label for="directorRevealConsequences">提前展示选择后果 <input id="directorRevealConsequences" type="checkbox" ${workspace.settings?.reveal_consequences ? "checked" : ""} /></label><small class="archive-note">默认关闭；开启只显示不确定的“可能后果”。</small></div></aside></div>`;
  }

  async function renderAIDirector(workspace) {
    if (state.directorPollTimer) {
      window.clearTimeout(state.directorPollTimer);
      state.directorPollTimer = null;
    }
    state.aiWorkspace = workspace;
    state.aiProjectId = workspace.project_id;
    const run = workspace.active_run;
    state.aiRunId = run?.run_id || null;
    elements.directorProjectTitle.textContent = workspace.title || "—";
    elements.aiDirectorModelLabel.textContent = modelRuntimeLabel(workspace);
    elements.directorCreditsUsedNote.textContent = workspace.mode === "live" ? "开发测试不结算" : "演示不消耗";
    elements.directorCreditsEstimateNote.textContent = workspace.mode === "live" ? "仅供开发观察" : "演示免费";
    elements.directorCreditsUsed.textContent = Number(workspace.credits_used || 0).toLocaleString("zh-CN");
    elements.directorCreditsEstimate.textContent = Number(run?.estimated_credits || 0).toLocaleString("zh-CN");
    renderDirectorStageTrack(run);
    if (!run) {
      elements.directorPageContent.innerHTML = renderDirectorStart(workspace);
      elements.directorPauseButton.classList.add("is-hidden");
      bindDirectorSettings();
      return;
    }
    const terminal = run.status === "completed" || run.status === "failed";
    elements.directorPauseButton.classList.toggle("is-hidden", terminal);
    elements.directorPauseButton.textContent = run.status === "paused" ? "继续创作" : run.status === "waiting_for_choice" ? "暂停等待" : "暂停创作";
    const roleMarkup = renderDirectorRoles(workspace);
    let rightPanel = "";
    if (run.status === "waiting_for_choice") {
      const leadName = escapeHtml(workspace.story_characters?.[0]?.name || "故事人物");
      rightPanel = `<aside class="director-choice-panel"><span class="eyebrow">关键节点 / 只选一个</span><h2>${leadName}准备进入旧档案</h2><p>三个方向都只会留下一个继续结果。未选方案不会成为可切换正文。</p><div class="director-choice-list">${(run.choices || []).map((choice, index) => `<button class="director-choice" type="button" data-action="choose-ai-choice" data-choice-id="${escapeHtml(choice.choice_id)}"><span class="director-choice-number">${index + 1}</span><span><strong>${escapeHtml(choice.label)}</strong><small>${escapeHtml(choice.description)}${choice.possible_consequence ? `<br />${escapeHtml(choice.possible_consequence)}` : ""}</small></span><span>→</span></button>`).join("")}</div><div class="director-hidden-note">⌑ 可能后果默认隐藏</div><div class="director-settings"><label for="directorRevealConsequences">提前展示选择后果 <input id="directorRevealConsequences" type="checkbox" ${workspace.settings?.reveal_consequences ? "checked" : ""} /></label></div></aside>`;
    } else if (run.status === "completed") {
      rightPanel = `<aside class="director-choice-panel"><span class="eyebrow">关键节点 / 已定稿</span><h2>唯一正文已经接上</h2><p>作者的选择已成为当前正式路线；未选方向没有被保存为分支。</p><div class="director-completed-actions"><button class="button button-primary" type="button" data-action="start-next-ai" data-strategy="pause_at_key_nodes">开始第 ${Number(workspace.next_chapter_number || run.chapter_number + 1)} 章 →</button><button class="button button-outline" type="button" data-action="ai-open-editor">进入正文编辑器</button><button class="button button-outline" type="button" data-action="ai-open-archive">查看故事档案</button></div><div class="director-settings"><label>提前展示选择后果 <input id="directorRevealConsequences" type="checkbox" ${workspace.settings?.reveal_consequences ? "checked" : ""} /></label></div></aside>`;
    } else if (run.status === "failed") {
      rightPanel = `<aside class="director-choice-panel"><div class="director-failure"><strong>导演台没有完成这一轮</strong><p>${escapeHtml(run.error_message || "可以修正蓝图后重试；失败不会重复扣除演示积分。")}</p><button class="button button-outline" type="button" data-action="retry-ai-director">重试这一轮</button></div></aside>`;
    } else if (run.status === "paused") {
      rightPanel = `<aside class="director-choice-panel"><span class="eyebrow">后台轮转</span><h2>创作已暂停</h2><p>暂停发生在安全节点，当前正文没有被伪装成完成。</p><button class="button button-primary button-wide" type="button" data-action="resume-ai-director">继续创作</button></aside>`;
    } else if (run.status === "character_simulation") {
      rightPanel = `<aside class="director-choice-panel"><span class="eyebrow">后台轮转 / 运行中</span><h2>角色正在推演</h2><p>专业角色正在读取全局材料，故事人物只读取自己的经历与角色可知事实。你可以离开页面，服务端会自动推进。</p></aside>`;
    } else {
      rightPanel = `<aside class="director-choice-panel"><span class="eyebrow">后台轮转</span><h2>${escapeHtml(run.current_stage || "正在创作")}</h2><p>关闭页面也不会丢失任务。导演台会从服务端状态继续。</p><div class="director-hidden-note">${workspace.mode === "live" ? "模型正在开发测试中，暂不展示未确认的选择后果。" : "演示推演正在进行，暂不展示未确认的选择后果。"}</div></aside>`;
    }
    elements.directorPageContent.innerHTML = `<div class="director-workspace-grid"><section class="director-main-column"><div class="director-section-heading"><h2>第 ${run.chapter_number} 章 · ${escapeHtml(run.current_stage || "后台轮转")}</h2><span>${escapeHtml(run.status === "completed" ? "已完成" : run.status === "waiting_for_choice" ? "等待作者选择" : run.status === "failed" ? "需要处理" : "可离页恢复")}</span></div><div class="director-preview"><div class="director-chapter-mark">第 ${run.chapter_number} 章</div><div class="director-preview-copy"><strong>${escapeHtml(workspace.blueprint?.core_premise || "创作蓝图")}</strong><p>${escapeHtml(run.preview_content || "角色推演会把共享世界规则和角色可知事实带到同一条故事脉络上。")}</p><small>阶段记录：${escapeHtml((run.stage_history || []).join(" → ") || "排队")}</small></div></div>${roleMarkup}</section>${rightPanel}</div>`;
    bindDirectorSettings();
    if (["queued", "character_simulation", "writing", "reviewing", "updating_archive"].includes(run.status)) {
      state.directorPollTimer = window.setTimeout(() => {
        state.directorPollTimer = null;
        if (state.screen === "aiDirector" && state.aiProjectId === workspace.project_id) {
          loadAIWorkspace(workspace.project_id, true);
        }
      }, 650);
    }
  }

  function bindDirectorSettings() {
    const toggle = $("#directorRevealConsequences");
    if (toggle && !toggle.dataset.bound) {
      toggle.dataset.bound = "true";
      toggle.addEventListener("change", async () => {
        try {
          const workspace = await requestJson(`/api/ai/projects/${encodeURIComponent(state.aiProjectId)}/settings`, { method: "PUT", body: JSON.stringify({ reveal_consequences: toggle.checked }) });
          await renderAIDirector(workspace);
        } catch (error) {
          setWorkspaceNotice(elements.aiDirectorNotice, error.message || "设置保存失败。", "red");
        }
      });
    }
  }

  async function startAIDirector(strategy) {
    try {
      const chapterNumber = Number(state.aiWorkspace?.next_chapter_number || 1);
      const workspace = await requestJson(`/api/ai/projects/${encodeURIComponent(state.aiProjectId)}/director/start`, { method: "POST", body: JSON.stringify({ strategy, defer: true, idempotency_key: `director-${state.aiProjectId}-${state.aiWorkspace.blueprint_revision}-${chapterNumber}-${strategy}` }) });
      navigate(`/ai/${encodeURIComponent(state.aiProjectId)}/director`);
      await renderAIDirector(workspace);
      showToast(strategy === "full_auto" ? "全自动继续已开始。" : "导演台会在关键节点停下来等你选择。", "blue");
    } catch (error) {
      setWorkspaceNotice(elements.aiDirectorNotice, error.message || "导演台没有开始。", "red");
    }
  }

  async function chooseAIDirector(choiceId) {
    if (!state.aiRunId) return;
    $(`[data-action="choose-ai-choice"][data-choice-id="${CSS.escape(choiceId)}"]`)?.setAttribute("disabled", "disabled");
    try {
      const workspace = await requestJson(`/api/ai/projects/${encodeURIComponent(state.aiProjectId)}/director/runs/${encodeURIComponent(state.aiRunId)}/choice`, { method: "POST", body: JSON.stringify({ choice_id: choiceId }) });
      await renderAIDirector(workspace);
      showToast("选择已成为唯一正式路线，正文和档案正在接续。", "blue");
    } catch (error) {
      setWorkspaceNotice(elements.aiDirectorNotice, error.message || "这个选择没有提交成功。", "red");
    }
  }

  async function toggleAIDirectorPause() {
    if (!state.aiRunId || !state.aiWorkspace?.active_run) return;
    const action = state.aiWorkspace.active_run.status === "paused" ? "resume" : "pause";
    try {
      const workspace = await requestJson(`/api/ai/projects/${encodeURIComponent(state.aiProjectId)}/director/runs/${encodeURIComponent(state.aiRunId)}/${action}`, { method: "POST" });
      await renderAIDirector(workspace);
    } catch (error) {
      setWorkspaceNotice(elements.aiDirectorNotice, error.message || "导演台状态没有更新。", "red");
    }
  }

  async function retryAIDirector() {
    if (!state.aiRunId) return;
    try {
      const workspace = await requestJson(`/api/ai/projects/${encodeURIComponent(state.aiProjectId)}/director/runs/${encodeURIComponent(state.aiRunId)}/retry`, { method: "POST" });
      await renderAIDirector(workspace);
    } catch (error) {
      setWorkspaceNotice(elements.aiDirectorNotice, error.message || "导演台重试失败。", "red");
    }
  }

  function openAIStudio() {
    if (!state.aiProjectId) return;
    navigate(`/ai/${encodeURIComponent(state.aiProjectId)}`);
    loadAIWorkspace(state.aiProjectId, false);
  }

  async function openDeconstruction(projectId = state.editorProjectId || state.archiveProjectId) {
    if (!projectId) return;
    const path = deconstructionPath(projectId, chapterIdFromLocation() || state.activeChapterId);
    if (await navigate(path)) await loadDeconstructionWorkspace(projectId);
  }

  async function openDeconstructionVersions(projectId = state.deconstructionProjectId || state.archiveProjectId || state.editorProjectId) {
    if (!projectId) return;
    const path = editorPath(projectId, chapterIdFromLocation() || state.activeChapterId);
    if (!(await navigate(path))) return;
    state.editorMode = "independent";
    await loadIndependentWorkspace(projectId);
    openVersionHistoryDialog();
  }

  function openAIDirector() {
    if (!state.aiProjectId) return;
    navigate(`/ai/${encodeURIComponent(state.aiProjectId)}/director`);
    loadAIWorkspace(state.aiProjectId, true);
  }

  function openAIEditor() {
    if (!state.aiProjectId) return;
    state.editorMode = "ai_assisted";
    navigate(`/independent/${encodeURIComponent(state.aiProjectId)}`);
    loadIndependentWorkspace(state.aiProjectId);
  }

  function openAIArchive() {
    if (!state.aiProjectId) return;
    navigate(`/archive/${encodeURIComponent(state.aiProjectId)}`);
    loadArchiveWorkspace(state.aiProjectId);
  }

  function rerenderDeconstructionDepth(focusId = "") {
    const data = state.deconstructionWorkspace;
    if (!data || !hasDeconstructionResults(data)) return;
    renderDeconstructionPage(data);
    if (focusId) document.getElementById(focusId)?.focus();
  }

  function handleDeconstructionDepthInput(event) {
    const actionNode = event.target.closest?.("[data-action]");
    if (!actionNode) return;
    if (actionNode.dataset.action === "deconstruction-depth-progress") {
      state.deconstructionChapterId = "";
      const progress = depthClamp(actionNode.value, 100);
      state.deconstructionProgress = progress;
      const output = document.getElementById("depthProgressOutput");
      if (output) output.textContent = `${Math.round(progress)}%`;
    }
  }

  function handleDeconstructionDepthChange(event) {
    const actionNode = event.target.closest?.("[data-action]");
    if (!actionNode) return;
    if (actionNode.dataset.action === "deconstruction-depth-progress") {
      state.deconstructionChapterId = "";
      state.deconstructionProgress = depthClamp(actionNode.value, 100);
      rerenderDeconstructionDepth("depthProgressFilter");
      return;
    }
    if (actionNode.dataset.action !== "deconstruction-depth-chapter") return;
    state.deconstructionChapterId = actionNode.value || "";
    const report = state.deconstructionWorkspace?.result?.depthReport;
    const chapter = report?.chapters?.find((item) => item.id === state.deconstructionChapterId);
    state.deconstructionProgress = chapter ? chapter.end : 100;
    rerenderDeconstructionDepth("depthChapterFilter");
  }

  function handleDeconstructionTabKeydown(event) {
    const tab = event.target.closest?.('[role="tab"][data-depth-tab]');
    if (!tab) return;
    const tabs = $$('[role="tab"][data-depth-tab]', elements.deconstructionPageContent);
    const index = tabs.indexOf(tab);
    if (index < 0) return;
    let nextIndex = index;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") nextIndex = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") nextIndex = (index - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    if (nextIndex === index) return;
    event.preventDefault();
    const next = tabs[nextIndex];
    state.deconstructionView = next.dataset.depthTab;
    rerenderDeconstructionDepth(next.id);
  }

  async function handleAction(event) {
    const actionNode = event.target.closest("[data-action]");
    if (!actionNode) return;
    const action = actionNode.dataset.action;
    if (action === "open-new-project") openNewProject();
    if (action === "open-notifications") openNotifications();
    if (action === "open-notification-target") await openNotificationTarget(actionNode);
    if (action === "retry-library") loadLibrary();
    if (action === "back-library") {
      if (await navigate("/library", { replace: true })) await loadLibrary();
    }
    if (action === "open-project") {
      const card = actionNode.closest("[data-project-id]");
      const project = state.projects.find((item) => item.project_id === card?.dataset.projectId);
      if (project) {
        if (project.mode === "independent") {
          const url = `/independent/${encodeURIComponent(project.project_id)}`;
          if (await navigate(url, { replace: true })) await loadIndependentWorkspace(project.project_id);
        } else {
          const url = `/ai/${encodeURIComponent(project.project_id)}`;
          if (await navigate(url, { replace: true })) await loadAIWorkspace(project.project_id, false);
        }
      }
    }
    if (action === "start-blank") startBlankWorkspace();
    if (action === "start-next-ai") startAIDirector(actionNode.dataset.strategy || "pause_at_key_nodes");
    if (action === "open-import") elements.importFileInput?.click();
    if (action === "confirm-import") confirmImport(actionNode.dataset.previewId);
    if (action === "select-chapter") selectEditorChapter(actionNode.dataset.chapterId);
    if (action === "show-editor") {
      elements.archiveDrawer.classList.remove("is-collapsed");
      elements.archiveDrawer.querySelector(".archive-drawer-body")?.removeAttribute("hidden");
    }
    if (action === "show-deconstruction") openDeconstruction(state.editorProjectId);
    if (action === "show-archive") {
      if (await navigate(archivePath(state.editorProjectId, state.activeChapterId))) await loadArchiveWorkspace(state.editorProjectId);
    }
    if (action === "open-version-history") openVersionHistoryDialog();
    if (action === "toggle-archive") {
      const collapsed = elements.archiveDrawer.classList.toggle("is-collapsed");
      actionNode.setAttribute("aria-expanded", String(!collapsed));
      actionNode.textContent = collapsed ? "展开" : "收起";
    }
    if (action === "review-changes") openPendingChangesDialog();
    if (action === "reload-server") {
      if (state.editorConflict) {
        const serverChapter = state.editorConflict;
        replaceActiveVersionChapter(serverChapter);
        state.editorBuffer = serverChapter.content || "";
        state.editorTitleBuffer = serverChapter.title || "";
        state.editorRevision = serverChapter.server_revision || 0;
        state.editorSavedRevision = serverChapter.server_revision || 0;
        state.editorDirty = false;
        state.editorSaveFailed = false;
        state.editorConflict = null;
        renderEditorWorkspace();
        setEditorSaveState("已载入服务器版本", "saved");
      }
    }
    if (action === "keep-local") {
      if (state.editorConflict) {
        state.editorRevision = state.editorConflict.server_revision || state.editorRevision;
        state.editorConflict = null;
        flushPendingSave();
      }
    }
    if (action === "retry-task") retryIndependentTask(actionNode.dataset.taskId);
    if (action === "preview-version") previewVersion(actionNode.dataset.versionId);
    if (action === "restore-version") restoreVersion(actionNode.dataset.versionId);
    if (action === "open-restore-confirm") openRestoreVersionConfirm(actionNode.dataset.versionId);
    if (action === "cancel-restore-version") elements.restoreVersionDialog?.close();
    if (action === "confirm-restore-version") confirmRestoreVersion();
    if (action === "open-trial") openTrialDialog(actionNode.dataset.characterId);
    if (action === "archive-snapshot") loadArchiveWorkspace(state.archiveProjectId, actionNode.dataset.chapterNumber);
    if (action === "archive-open-editor") {
      if (state.archiveMode === "ai_assisted") openAIEditor();
      else {
        await navigate(editorPath(state.archiveProjectId, chapterIdFromLocation() || state.activeChapterId));
        state.editorMode = "independent";
        await loadIndependentWorkspace(state.archiveProjectId);
      }
    }
    if (action === "archive-open-deconstruction") openDeconstruction(state.archiveProjectId);
    if (action === "archive-open-versions") openDeconstructionVersions(state.archiveProjectId);
    if (action === "archive-open-ai") openAIStudio();
    if (action === "archive-open-self") loadArchiveWorkspace(state.archiveProjectId);
    if (action === "deconstruction-open-editor") {
      const projectId = state.deconstructionProjectId;
      if (projectId && await navigate(editorPath(projectId, chapterIdFromLocation() || state.activeChapterId))) await loadIndependentWorkspace(projectId);
    }
    if (action === "deconstruction-open-self") loadDeconstructionWorkspace(state.deconstructionProjectId);
    if (action === "deconstruction-open-archive") {
      const projectId = state.deconstructionProjectId;
      if (projectId && await navigate(archivePath(projectId, chapterIdFromLocation() || state.activeChapterId))) await loadArchiveWorkspace(projectId);
    }
    if (action === "deconstruction-open-versions") openDeconstructionVersions(state.deconstructionProjectId);
    if (action === "deconstruction-refresh") loadDeconstructionWorkspace(state.deconstructionProjectId);
    if (action === "deconstruction-retry") runDeconstructionAction("retry");
    if (action === "deconstruction-rebuild") runDeconstructionAction("rebuild");
    if (action === "deconstruction-depth-tab") {
      const view = actionNode.dataset.depthTab;
      if (depthPerspectiveMeta[view]) {
        state.deconstructionView = view;
        rerenderDeconstructionDepth(`deconstructionTab-${view}`);
      }
    }
    if (action === "open-deconstruction-evidence") await openDeconstructionEvidence(actionNode);
    if (action === "close-deconstruction-evidence") closeDeconstructionEvidenceDialog();
    if (action === "locate-deconstruction-evidence") await locateDeconstructionEvidence();
    if (action === "ai-open-studio") openAIStudio();
    if (action === "ai-open-director") openAIDirector();
    if (action === "ai-open-editor") openAIEditor();
    if (action === "ai-open-archive") openAIArchive();
    if (action === "start-ai-director") startAIDirector(actionNode.dataset.strategy);
    if (action === "choose-ai-choice") chooseAIDirector(actionNode.dataset.choiceId);
    if (action === "resume-ai-director") toggleAIDirectorPause();
    if (action === "retry-ai-director") retryAIDirector();
  }

  function bindEvents() {
    // 深链接与浏览器缓存下重新确认动态壳节点，避免旧页面状态阻断整套事件绑定。
    elements.startWorkspaceContent = $("#startWorkspaceContent");
    elements.editorWorkspaceContent = $("#editorWorkspaceContent");
    elements.independentScreen = $("#independentScreen");
    document.addEventListener("click", async (event) => {
      const routeLink = event.target.closest("[data-route]");
      if (routeLink) {
        event.preventDefault();
        const path = routeLink.getAttribute("href") || "/";
        if (path.startsWith("#")) return;
        await navigate(path);
      }
      const comingSoon = event.target.closest("[data-coming-soon]");
      if (comingSoon) showToast(`${comingSoon.dataset.comingSoon}即将开放。`);
    });
    elements.emailForm.addEventListener("submit", submitEmail);
    elements.libraryContent.addEventListener("click", handleAction);
    elements.readyContent.addEventListener("click", handleAction);
    $('#libraryScreen [data-action="open-notifications"]')?.addEventListener("click", handleAction);
    elements.startWorkspaceContent?.addEventListener("click", handleAction);
    elements.editorWorkspaceContent?.addEventListener("click", handleAction);
    elements.editorNotice?.addEventListener("click", handleAction);
    elements.versionHistoryContent?.addEventListener("click", handleAction);
    elements.versionPreviewContent?.addEventListener("click", handleAction);
    elements.archivePageContent?.addEventListener("click", handleAction);
    elements.deconstructionScreen?.addEventListener("click", handleAction);
    elements.deconstructionPageContent?.addEventListener("input", handleDeconstructionDepthInput);
    elements.deconstructionPageContent?.addEventListener("change", handleDeconstructionDepthChange);
    elements.deconstructionPageContent?.addEventListener("keydown", handleDeconstructionTabKeydown);
    elements.deconstructionEvidenceDialog?.addEventListener("click", handleAction);
    elements.deconstructionEvidenceDialog?.addEventListener("close", () => restoreDialogFocus(elements.deconstructionEvidenceDialog));
    elements.deconstructionEvidenceDialog?.addEventListener("cancel", () => {
      state.deconstructionEvidenceRequestToken += 1;
      state.pendingEvidence = null;
    });
    elements.directorPageContent?.addEventListener("click", handleAction);
    elements.notificationsList.addEventListener("click", handleAction);
    elements.notificationsList.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      const actionNode = event.target.closest('[data-action="open-notification-target"]');
      if (!actionNode) return;
      event.preventDefault();
      actionNode.click();
    });
    document.querySelectorAll(".editor-spine [data-action], .archive-spine [data-action], .ai-spine [data-action]").forEach((node) => node.addEventListener("click", handleAction));
    elements.editorLogoutButton = $("#editorLogoutButton");
    elements.editorLogoutButton.addEventListener("click", logout);
    $("#archiveLogoutButton")?.addEventListener("click", logout);
    $("#deconstructionLogoutButton")?.addEventListener("click", logout);
    $("#aiStudioLogoutButton")?.addEventListener("click", logout);
    $("#aiDirectorLogoutButton")?.addEventListener("click", logout);
    $("#newProjectButton").addEventListener("click", openNewProject);
    $("#logoutButton").addEventListener("click", logout);
    elements.modeOptions.forEach((option) => option.addEventListener("click", () => chooseMode(option.dataset.mode)));
    $("#changeModeButton").addEventListener("click", () => {
      state.selectedMode = null;
      elements.projectDetails.classList.add("is-hidden");
      elements.modeOptions.forEach((option) => option.classList.remove("is-selected"));
    });
    elements.newProjectForm.addEventListener("submit", submitProject);
    [
      elements.dialog,
      elements.notificationsDialog,
      elements.pendingChangesDialog,
      elements.versionHistoryDialog,
      elements.trialDialog,
      elements.deconstructionEvidenceDialog,
      elements.restoreVersionDialog,
    ].forEach(bindDialogFocus);
    elements.dialog.addEventListener("close", resetProjectDialog);
    elements.librarySearch.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        if (state.account) loadLibrary(elements.librarySearch.value.trim());
      }
    });
    let searchTimer;
    elements.librarySearch.addEventListener("input", () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => {
        if (state.account) loadLibrary(elements.librarySearch.value.trim());
      }, 280);
    });
    elements.chapterEditor.addEventListener("input", handleEditorInput);
    elements.chapterTitleInput.addEventListener("input", handleEditorInput);
    elements.completeChapterButton.addEventListener("click", handleCompleteButtonClick);
    $("#addChapterButton").addEventListener("click", addIndependentChapter);
    $("#openVersionButton").addEventListener("click", openVersionHistoryDialog);
    elements.archiveSnapshotSelect.addEventListener("change", (event) => selectArchiveSnapshot(event.target.value));
    elements.archivePageSnapshotSelect?.addEventListener("change", (event) => loadArchiveWorkspace(state.archiveProjectId, event.target.value || null));
    elements.closePendingChangesButton = $("#closePendingChangesButton");
    elements.closePendingChangesButton.addEventListener("click", () => elements.pendingChangesDialog.close());
    elements.pendingChangesDialog.addEventListener("close", () => restoreDialogFocus(elements.pendingChangesDialog));
    elements.ignoreChangesButton.addEventListener("click", () => resolvePendingChanges("ignore"));
    elements.rebuildChangesButton.addEventListener("click", () => resolvePendingChanges("rebuild"));
    elements.closeVersionHistoryButton = $("#closeVersionHistoryButton");
    elements.closeVersionHistoryButton.addEventListener("click", () => elements.versionHistoryDialog.close());
    elements.versionHistoryDialog.addEventListener("close", () => restoreDialogFocus(elements.versionHistoryDialog));
    elements.restoreVersionDialog?.addEventListener("click", handleAction);
    elements.restoreVersionDialog?.addEventListener("close", () => {
      state.restoreConfirmVersionId = null;
      restoreDialogFocus(elements.restoreVersionDialog);
    });
    elements.closeTrialButton = $("#closeTrialButton");
    elements.closeTrialButton.addEventListener("click", () => elements.trialDialog.close());
    elements.trialDialog.addEventListener("close", () => restoreDialogFocus(elements.trialDialog));
    elements.confirmTrialButton.addEventListener("click", confirmTrialSketch);
    elements.aiMessageForm?.addEventListener("submit", submitAIMessage);
    elements.blueprintForm?.addEventListener("submit", saveAIBlueprint);
    elements.confirmBlueprintButton?.addEventListener("click", confirmAIBlueprint);
    elements.directorPauseButton?.addEventListener("click", toggleAIDirectorPause);
    elements.dialog.addEventListener("close", () => restoreDialogFocus(elements.dialog));
    elements.closeNotificationsButton = $("#closeNotificationsButton");
    elements.closeNotificationsButton.addEventListener("click", () => elements.notificationsDialog.close());
    elements.notificationsDialog.addEventListener("close", () => restoreDialogFocus(elements.notificationsDialog));
    $("#mobileMenuButton").addEventListener("click", (event) => {
      const button = event.currentTarget;
      const nav = $(".public-nav");
      const open = nav.classList.toggle("is-open");
      button.setAttribute("aria-expanded", String(open));
    });
    window.addEventListener("popstate", async () => {
      if (state.editorSaveFailed || state.editorConflict || !(await flushPendingSave())) {
        if (state.editorProjectId) {
          window.history.pushState({}, "", editorPath(state.editorProjectId, state.activeChapterId));
          setActiveScreen("independent");
        }
        return;
      }
      await restoreSession(routeFromLocation());
    });
    window.addEventListener("beforeunload", (event) => {
      if (!state.editorSaveFailed && !state.editorConflict && (state.editorDirty || state.editorSaving)) {
        event.preventDefault();
        event.returnValue = "当前正文尚未保存。";
      }
    });
    window.addEventListener("pagehide", () => {
      if (!state.editorSaveFailed && !state.editorConflict && (state.editorDirty || state.editorSaving)) void flushPendingSave({ keepalive: true });
    });
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden" && !state.editorSaveFailed && !state.editorConflict && (state.editorDirty || state.editorSaving)) {
        void flushPendingSave({ keepalive: true });
      }
    });
    document.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        if (state.screen === "library") {
          event.preventDefault();
          elements.librarySearch.focus();
        }
      }
    });
  }

  function start() {
    bindEvents();
    const initialRoute = routeFromLocation();
    if (initialRoute === "landing") {
      setActiveScreen("landing");
      restoreSession("landing");
    } else {
      restoreSession(initialRoute);
    }
  }

  start();
})();
