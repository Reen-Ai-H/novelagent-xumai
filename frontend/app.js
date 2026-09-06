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
    editorMode: "independent",
    activeChapterId: null,
    editorBuffer: "",
    editorTitleBuffer: "",
    editorRevision: 0,
    editorDirty: false,
    editorSaving: false,
    editorConflict: null,
    editorChangeToken: 0,
    editorReadOnly: false,
    saveTimer: null,
    savePromise: null,
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
    pendingEvidence: null,
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
    if (state.screen === "deconstruction" && screen !== "deconstruction") {
      window.clearTimeout(state.deconstructionPollTimer);
      state.deconstructionPollTimer = null;
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
      && (state.editorDirty || state.editorSaving);
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
    window.scrollTo({ top: 0, behavior: "smooth" });
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

  function renderStartWorkspace(workspace) {
    elements.editorWorkspaceContent.classList.add("is-hidden");
    elements.startWorkspaceContent.classList.remove("is-hidden");
    elements.completeChapterButton.disabled = true;
    elements.editorProjectTitle.textContent = workspace.title || "—";
    elements.editorModeLabel.textContent = workspace.mode === "ai_assisted" ? "AI 辅助写作" : "独立创作";
    elements.writingModeNote.textContent = workspace.mode === "ai_assisted" ? "AI 辅助写作 · 唯一正式正文" : "独立创作 · 正式正文";
    elements.editorChapterHeading.textContent = "先把故事带回来";
    setEditorSaveState("等待开始");
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
    state.editorProjectId = projectId;
    setActiveScreen("independent");
    elements.editorProjectTitle.textContent = "正在读取…";
    try {
      const workspace = await requestJson(`/api/independent/projects/${encodeURIComponent(projectId)}`);
      state.workspace = workspace;
      state.editorMode = workspace.mode || state.editorMode || "independent";
      state.activeArchive = workspace.archive;
      state.editorConflict = null;
      if (!workspace.initialized) {
        renderStartWorkspace(workspace);
      } else {
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
    elements.startWorkspaceContent.classList.add("is-hidden");
    elements.editorWorkspaceContent.classList.remove("is-hidden");
    elements.editorProjectTitle.textContent = workspace.title || "—";
    const aiEditor = workspace.mode === "ai_assisted" || state.editorMode === "ai_assisted";
    elements.editorModeLabel.textContent = aiEditor ? "AI 辅助写作" : "独立创作";
    elements.writingModeNote.textContent = aiEditor ? "AI 辅助写作 · 唯一正式正文" : "独立创作 · 正式正文";
    if (!state.activeChapterId || !version.chapters.some((chapter) => chapter.chapter_id === state.activeChapterId)) {
      state.activeChapterId = version.chapters[0]?.chapter_id || null;
      state.editorDirty = false;
      state.editorConflict = null;
    }
    const chapter = version.chapters.find((item) => item.chapter_id === state.activeChapterId);
    if (!chapter) return;
    if (!state.editorDirty) {
      state.editorBuffer = chapter.content || "";
      state.editorTitleBuffer = chapter.title || "";
      state.editorRevision = chapter.server_revision || 0;
    }
    elements.editorChapterHeading.textContent = chapter.title || `第${chapter.chapter_number}章`;
    elements.chapterTitleInput.value = state.editorTitleBuffer;
    elements.chapterEditor.value = state.editorBuffer;
    elements.editorWordCount.textContent = `${countEditorWords(state.editorBuffer).toLocaleString("zh-CN")} 字`;
    elements.editorRevisionLabel.textContent = `REV / ${state.editorRevision}`;
    elements.completeChapterButton.disabled = !state.editorBuffer.trim() || state.editorReadOnly;
    renderChapterList(version);
    renderArchiveSummary(state.activeArchive || workspace.archive);
    if (workspace.pending_changes?.changes?.length) {
      setEditorNoticeHtml(`<strong>有 ${workspace.pending_changes.changes.length} 章旧稿修改等待确认。</strong><button class="notice-action" type="button" data-action="review-changes">确认全部修改 →</button>`);
    } else if (!state.editorConflict && !state.editorSaving) {
      elements.editorNotice.classList.add("is-hidden");
    }
    const latestTask = (workspace.tasks || []).find((task) => task.version_id === version.version_id && ["queued", "running", "failed"].includes(task.status));
    if (latestTask && latestTask.status === "failed") {
      setEditorNoticeHtml(`<strong>后台分析失败。</strong> ${escapeHtml(latestTask.error_message || "可以修改正文后重试。")} <button class="notice-action" type="button" data-action="retry-task" data-task-id="${escapeHtml(latestTask.task_id)}">重试 →</button>`, "red");
      setEditorSaveState("分析失败", "error");
    } else if (latestTask && ["queued", "running"].includes(latestTask.status)) {
      setEditorSaveState("后台分析中…", "saving");
    } else if (!state.editorDirty && !state.editorSaving && !state.editorConflict) {
      setEditorSaveState(chapter.status === "ready" ? "已保存" : "等待保存", chapter.status === "ready" ? "saved" : "");
    }
  }

  function handleEditorInput() {
    if (state.editorReadOnly) return;
    state.editorBuffer = elements.chapterEditor.value;
    state.editorTitleBuffer = elements.chapterTitleInput.value;
    state.editorDirty = true;
    state.editorChangeToken += 1;
    state.editorConflict = null;
    elements.editorWordCount.textContent = `${countEditorWords(state.editorBuffer).toLocaleString("zh-CN")} 字`;
    elements.completeChapterButton.disabled = !state.editorBuffer.trim();
    setEditorSaveState("本地缓冲");
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
        state.editorConflict = null;
        if (state.editorChangeToken === changeToken) {
          state.editorDirty = false;
          setEditorSaveState("已保存", "saved");
        } else {
          // 保存请求期间又有输入：只更新 revision，保留新缓冲并让 flush 再写一次。
          state.editorDirty = true;
          setEditorSaveState("本地缓冲", "");
        }
        renderEditorWorkspace();
        return true;
      } catch (error) {
        if (error.code === "save_conflict") renderSaveConflict(error);
        else setEditorNotice(error.message || "保存失败，可以稍后重试。", "red");
        setEditorSaveState("保存失败", "error");
        return false;
      } finally {
        state.editorSaving = false;
        state.savePromise = null;
      }
    })();
    state.savePromise = promise;
    return promise;
  }

  async function completeCurrentChapter() {
    if (state.editorReadOnly) return;
    const saved = await flushPendingSave();
    if (!saved || state.editorDirty) return;
    const button = elements.completeChapterButton;
    button.disabled = true;
    setEditorSaveState("已保存，分析中…", "saving");
    try {
      const payload = await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/chapters/${encodeURIComponent(state.activeChapterId)}/complete`, {
        method: "POST",
        body: JSON.stringify({ content: state.editorBuffer, expected_revision: state.editorRevision, idempotency_key: `browser-${state.activeChapterId}-${state.editorRevision}` }),
      });
      await pollIndependentTask(payload.task.task_id);
    } catch (error) {
      setEditorNotice(error.message || "完成本章没有提交成功，请确认正文已经保存。", "red");
      setEditorSaveState("完成失败", "error");
      button.disabled = !state.editorBuffer.trim();
    }
  }

  function wait(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  async function pollIndependentTask(taskId) {
    for (let attempt = 0; attempt < 50; attempt += 1) {
      const payload = await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/tasks/${encodeURIComponent(taskId)}`);
      if (payload.task.status === "completed") {
        await loadIndependentWorkspace(state.editorProjectId);
        setEditorNotice("本章完成，故事档案已更新；来源章节已记录。", "blue");
        showToast("本章已完成，档案快照已保存。");
        return;
      }
      if (payload.task.status === "failed") {
        await loadIndependentWorkspace(state.editorProjectId);
        setEditorNoticeHtml(`<strong>后台分析失败。</strong> ${escapeHtml(payload.task.error_message || "可以修改正文后重试。")} <button class="notice-action" type="button" data-action="retry-task" data-task-id="${escapeHtml(taskId)}">重试 →</button>`, "red");
        return;
      }
      await wait(260);
    }
    setEditorNotice("后台分析仍在运行，离开或刷新后会继续恢复。", "blue");
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
    renderEditorWorkspace();
  }

  async function addIndependentChapter() {
    if (state.editorDirty && !(await flushPendingSave())) return;
    try {
      await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/chapters`, { method: "POST" });
      await loadIndependentWorkspace(state.editorProjectId);
      showToast("新章节已加入目录。");
    } catch (error) {
      setEditorNotice(error.message || "新章节创建失败。", "red");
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
    elements.versionHistoryContent.innerHTML = versions.length ? versions.map((version) => `
      <article class="version-history-item ${version.status === "active" ? "is-active" : ""}">
        <div><span class="eyebrow">${escapeHtml(version.status === "active" ? "当前稿本" : "历史稿本")}</span><strong>${escapeHtml(version.label)}</strong><small>${version.chapter_count} 章 · ${Number(version.total_word_count || 0).toLocaleString("zh-CN")} 字 · ${escapeHtml(formatDate(version.created_at))}</small></div>
        <div class="version-actions"><button type="button" class="quiet-link" data-action="preview-version" data-version-id="${escapeHtml(version.version_id)}">只读预览</button>${version.status !== "active" ? `<button type="button" class="text-link" data-action="restore-version" data-version-id="${escapeHtml(version.version_id)}">恢复为当前稿本</button>` : ""}</div>
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
      const firstChapter = version.chapters?.[0];
      elements.versionPreviewContent.classList.remove("is-hidden");
      elements.versionPreviewContent.innerHTML = `<div class="version-preview-head"><span class="eyebrow">只读预览 / ${escapeHtml(version.label)}</span><strong>${version.chapters?.length || 0} 章 · ${Number(version.chapters?.reduce((sum, chapter) => sum + (chapter.word_count || 0), 0) || 0).toLocaleString("zh-CN")} 字</strong></div><p>${escapeHtml(firstChapter?.content?.slice(0, 260) || "这条历史稿本还没有正文片段。")} ${firstChapter?.content?.length > 260 ? "…" : ""}</p><small>历史正文不会被本次预览改写。恢复时会创建新的当前稿本。</small>`;
    } catch (error) {
      setEditorNotice(error.message || "历史稿本预览失败。", "red");
    }
  }

  async function restoreVersion(versionId) {
    const button = $(`[data-action="restore-version"][data-version-id="${CSS.escape(versionId)}"]`);
    if (button) button.disabled = true;
    try {
      await requestJson(`/api/independent/projects/${encodeURIComponent(state.editorProjectId)}/versions/${encodeURIComponent(versionId)}/restore`, { method: "POST" });
      elements.versionHistoryDialog.close();
      await loadIndependentWorkspace(state.editorProjectId);
      showToast("历史正文已恢复为新的当前稿本。");
    } catch (error) {
      if (button) button.disabled = false;
      setEditorNotice(error.message || "历史稿本恢复失败。", "red");
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
      charStart: deconstructionNumber(ref.start_offset),
      charEnd: deconstructionNumber(ref.end_offset),
      offsetUnit: String(ref.offset_unit || ""),
      excerpt: deconstructionText(ref.excerpt),
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

  function normalizeResult(value) {
    if (!value || typeof value !== "object" || value.status !== "completed") return null;
    return {
      documentId: String(value.document_id || ""),
      sourceVersionId: String(value.source_version_id || ""),
      sourceRevision: deconstructionNumber(value.source_revision),
      sourceHash: String(value.source_hash || ""),
      analysisLabel: deconstructionText(value.analysis_label, "服务端结构拆解"),
      overview: normalizeOverview(value.overview),
      report: value.report || null,
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
    return {
      documentId: String(value.document_id || ""),
      status: String(value.status || ""),
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
    return Boolean(data?.result?.overview);
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
    return `data-evidence-id="${escapeHtml(evidence.id)}" data-document-id="${escapeHtml(evidence.documentId)}" data-source-version-id="${escapeHtml(evidence.sourceVersionId)}" data-source-revision="${evidence.sourceRevision ?? ""}" data-source-hash="${escapeHtml(evidence.sourceHash)}" data-chapter-id="${escapeHtml(evidence.chapterId)}" data-chapter-number="${evidence.chapterNumber ?? ""}" data-char-start="${evidence.charStart ?? ""}" data-char-end="${evidence.charEnd ?? ""}" data-offset-unit="${escapeHtml(evidence.offsetUnit)}" data-excerpt="${escapeHtml(evidence.excerpt)}"`;
  }

  function renderDeconstructionEvidence(refs) {
    const references = Array.isArray(refs) ? refs : [];
    if (!references.length) return `<span class="deconstruction-no-evidence">暂未绑定来源证据</span>`;
    return `<div class="deconstruction-evidence-list">${references.slice(0, 6).map((evidence, index) => {
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
    if (data.effectiveStatus === "rebuild_required") return `<button class="button button-outline" type="button" data-action="deconstruction-open-editor">回到正文确认修改 <span aria-hidden="true">→</span></button>`;
    if (data.effectiveStatus === "empty") return `<button class="button button-outline" type="button" data-action="deconstruction-open-editor">回到正文 <span aria-hidden="true">→</span></button>`;
    return "";
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
      <div class="deconstruction-state-copy"><div class="deconstruction-state-kicker"><span class="eyebrow">拆解状态</span><span class="deconstruction-status-note">${escapeHtml(data.runStatus === "none" ? "服务端状态" : `运行 / ${data.runStatus}`)}</span></div><h2>${escapeHtml(deconstructionStatusHeading(data))}</h2><p>${escapeHtml(data.message)}</p><small class="deconstruction-source-line mono">${escapeHtml(sourceLine)}</small></div>
      <div class="deconstruction-state-side">${working ? `<div class="deconstruction-progress" role="progressbar" aria-label="拆解进度" aria-valuemin="0" aria-valuemax="100" ${data.progress.percent === null ? "" : `aria-valuenow="${Math.round(data.progress.percent)}"`}><span style="width: ${progress}%"></span></div><span class="deconstruction-progress-label">${escapeHtml(progressText)} · ${escapeHtml(data.progress.currentStage)}</span>` : `<span class="deconstruction-state-source">来源 / ${escapeHtml(sourceText)}</span>`}${deconstructionStatusAction(data)}</div>
    </section>`;
  }

  function renderDeconstructionOverview(data) {
    const overview = data.result.overview;
    const metrics = [
      ["正文规模", formatDeconstructionCount(overview.wordCount ?? data.source.wordCount, " 字"), "服务端统计"],
      ["章节数量", formatDeconstructionCount(overview.chapterCount ?? data.source.chapterCount, " 章"), "来源章节"],
      ["结构节点", formatDeconstructionCount(data.result.timeline.length, " 个"), "时间线记录"],
      ["稿本修订", data.source.revision === null ? "—" : `REV / ${data.source.revision}`, "当前来源"],
    ];
    const observations = overview.structure.map((item) => `<article class="deconstruction-observation"><div><strong>${escapeHtml(item.label)}</strong>${deconstructionConfidenceBadge(item.confidence, true)}</div><p>${escapeHtml(item.text)}</p>${item.uncertainty.length ? `<small class="deconstruction-uncertainty">不确定：${escapeHtml(item.uncertainty.join("；"))}</small>` : ""}${renderDeconstructionEvidence(item.evidenceRefs)}</article>`).join("");
    const structureUnits = overview.structureUnits.length ? `<div class="deconstruction-tag-row">${overview.structureUnits.slice(0, 8).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : `<p class="deconstruction-empty-note">服务端没有返回额外结构标签。</p>`;
    const characters = overview.mainCharacters.length ? overview.mainCharacters.slice(0, 5).map((item) => `<li><div><strong>${escapeHtml(item.value)}</strong><small>${escapeHtml(item.label)}</small></div>${deconstructionConfidenceBadge(item.confidence, true)}${item.uncertainty.length ? `<p>${escapeHtml(item.uncertainty.join("；"))}</p>` : ""}${renderDeconstructionEvidence(item.evidenceRefs)}</li>`).join("") : `<li class="deconstruction-empty-list">尚未形成主要人物候选。</li>`;
    const conflicts = overview.coreConflicts.length ? overview.coreConflicts.slice(0, 4).map((item) => `<article class="deconstruction-candidate-card is-conflict"><div><strong>${escapeHtml(item.value)}</strong><small>${escapeHtml(item.label)}</small></div>${deconstructionConfidenceBadge(item.confidence, true)}${item.uncertainty.length ? `<p>${escapeHtml(item.uncertainty.join("；"))}</p>` : ""}${renderDeconstructionEvidence(item.evidenceRefs)}</article>`).join("") : `<p class="deconstruction-empty-note">尚未形成核心冲突候选。</p>`;
    return `<section class="deconstruction-panel deconstruction-overview-panel" aria-labelledby="deconstructionOverviewTitle"><header class="deconstruction-panel-heading"><div><span class="eyebrow">从正文实际统计</span><h2 id="deconstructionOverviewTitle">作品概览</h2></div><span class="deconstruction-panel-note">当前稿本 · 已校验来源</span></header><div class="deconstruction-metric-row">${metrics.map(([label, value, note]) => `<div class="deconstruction-metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></div>`).join("")}</div><div class="deconstruction-overview-lower"><div class="deconstruction-observation-board"><div class="deconstruction-subheading"><h3>结构观察</h3><span>每条判断都应能回到证据</span></div><div class="deconstruction-observation-list">${observations}</div><div class="deconstruction-structure-units"><div class="deconstruction-subheading"><h3>结构标签</h3><span>服务端原样返回</span></div>${structureUnits}</div></div><aside class="deconstruction-candidate-board"><div class="deconstruction-subheading"><h3>主要人物候选</h3><span>尚未等于事实</span></div><ul class="deconstruction-candidate-list">${characters}</ul><div class="deconstruction-conflict-block"><div class="deconstruction-subheading"><h3>核心冲突候选</h3><span>${overview.coreConflicts.length} 条</span></div>${conflicts}</div></aside></div>${overview.uncertainties.length ? `<div class="deconstruction-uncertainty-strip"><strong>仍需保留的不确定项</strong><span>${escapeHtml(overview.uncertainties.join(" · "))}</span></div>` : ""}</section>`;
  }

  function renderDeconstructionTimeline(data) {
    const nodes = data.result.timeline || [];
    const nodeMarkup = nodes.length ? nodes.map((node) => {
      const start = node.normalizedStart;
      const end = node.normalizedEnd === null ? (start === null ? null : Math.min(100, start + 3)) : node.normalizedEnd;
      const width = start === null || end === null ? 0 : Math.max(3, end - start);
      const positioned = start !== null && end !== null;
      return `<article class="deconstruction-timeline-node ${positioned ? "is-positioned" : "is-unplaced"}" ${positioned ? `style="--node-start: ${start}%; --node-size: ${width}%"` : ""}><div class="deconstruction-timeline-marker" aria-hidden="true"><i></i></div><div class="deconstruction-timeline-copy"><div class="deconstruction-timeline-topline"><span class="mono">${positioned ? `${Math.round(start)}–${Math.round(end)}%` : "百分比待识别"}</span>${deconstructionConfidenceBadge(node.confidence, true)}</div><h3>${escapeHtml(node.title)}</h3><p>${escapeHtml(node.event)}</p><div class="deconstruction-timeline-meta"><span>${escapeHtml(deconstructionAnchorLabel(node))}</span>${node.narrativeFunction ? `<span>${escapeHtml(node.narrativeFunction)}</span>` : ""}</div>${node.characters.length ? `<div class="deconstruction-tag-row">${node.characters.slice(0, 4).map((character) => `<span>${escapeHtml(character)}</span>`).join("")}</div>` : ""}${node.uncertainty.length ? `<small class="deconstruction-uncertainty">不确定：${escapeHtml(node.uncertainty.join("；"))}</small>` : ""}${renderDeconstructionEvidence(node.evidenceRefs)}</div></article>`;
    }).join("") : `<p class="deconstruction-empty-note">服务端还没有返回可展示的时间线节点。</p>`;
    return `<section class="deconstruction-panel deconstruction-timeline-panel" aria-labelledby="deconstructionTimelineTitle"><header class="deconstruction-panel-heading"><div><span class="eyebrow">归一化进度 + 绝对锚点</span><h2 id="deconstructionTimelineTitle">节奏时间线</h2></div><span class="deconstruction-panel-note">0% 起于正文开头，100% 落在正文结尾</span></header><div class="deconstruction-timeline-scale" aria-hidden="true"><span>0%</span><span>50%</span><span>100%</span></div><div class="deconstruction-timeline-rail" aria-label="作品结构节奏节点">${nodes.length ? `<div class="deconstruction-timeline-axis"></div>` : ""}${nodeMarkup}</div><div class="deconstruction-timeline-legend"><span><i class="is-blue"></i>已定位的结构节点</span><span><i class="is-coral"></i>需要回看的不确定项</span><span class="mono">${nodes.length} 个服务端节点</span></div></section>`;
  }

  function deconstructionCell(label, value) {
    const text = Array.isArray(value) ? value.join("；") : deconstructionText(value, "暂无");
    return `<div class="deconstruction-table-detail"><span>${escapeHtml(label)}</span><strong>${escapeHtml(text)}</strong></div>`;
  }

  function renderDeconstructionChapterTable(data) {
    const chapters = data.result.chapters || [];
    const rows = chapters.length ? chapters.map((chapter) => `<tr><th scope="row"><span class="mono">${chapter.chapterNumber === null ? "—" : String(chapter.chapterNumber).padStart(2, "0")}</span><strong>${escapeHtml(chapter.title)}</strong><small>${escapeHtml(deconstructionAnchorLabel(chapter))}</small></th><td><p class="deconstruction-table-summary">${escapeHtml(chapter.summary)}</p>${chapter.coreEvents.length ? `<small>${escapeHtml(chapter.coreEvents.join("；"))}</small>` : ""}</td><td>${deconstructionCell("功能", chapter.narrativeFunction)}${deconstructionCell("场景", chapter.scenes)}${deconstructionCell("冲突", chapter.conflict)}</td><td>${deconstructionCell("信息释放", chapter.informationRelease)}${deconstructionCell("关系变化", chapter.relationshipChange)}${deconstructionCell("情绪变化", chapter.emotionalChange)}</td><td>${deconstructionCell("伏笔", chapter.foreshadowing)}${deconstructionCell("开头钩子", chapter.openingHook)}${deconstructionCell("结尾钩子", chapter.endingHook)}</td><td><div class="deconstruction-table-confidence">${deconstructionConfidenceBadge(chapter.confidence)}${chapter.uncertainty.length ? `<small class="deconstruction-uncertainty">不确定：${escapeHtml(chapter.uncertainty.join("；"))}</small>` : ""}</div>${renderDeconstructionEvidence(chapter.evidenceRefs)}</td></tr>`).join("") : `<tr><td colspan="6"><p class="deconstruction-empty-note">服务端尚未返回章节拆解。已有正文也不会被前端临时摘要替代。</p></td></tr>`;
    return `<section class="deconstruction-panel deconstruction-chapter-panel" aria-labelledby="deconstructionChapterTitle"><header class="deconstruction-panel-heading"><div><span class="eyebrow">逐章回看</span><h2 id="deconstructionChapterTitle">章节拆解</h2></div><span class="deconstruction-panel-note">${chapters.length ? `${chapters.length} 章已返回` : "等待服务端结果"}</span></header><div class="deconstruction-table-wrap"><table class="deconstruction-table"><caption class="visually-hidden">章节拆解表，包含摘要、结构功能、场景冲突、信息关系、伏笔钩子和证据回链</caption><thead><tr><th scope="col">章节</th><th scope="col">一句话摘要 / 核心事件</th><th scope="col">结构功能 / 场景 / 冲突</th><th scope="col">信息 / 关系 / 情绪</th><th scope="col">伏笔 / 开头 / 结尾</th><th scope="col">置信度 / 证据</th></tr></thead><tbody>${rows}</tbody></table></div><p class="deconstruction-table-footnote">点击证据前会再次校验文档、稿本、修订号和哈希；若只剩历史来源，页面只提供章节级只读提示。</p></section>`;
  }

  function renderDeconstructionHistory(data) {
    if (!data.history.length) return "";
    const items = data.history.slice().reverse().slice(0, 6).map((item) => `<li><div><strong>${escapeHtml(deconstructionStatusText[item.status] || item.status || "历史运行")}</strong><small>${escapeHtml(item.analysisLabel)} · REV / ${escapeHtml(item.sourceRevision ?? "—")}</small></div><span class="mono">${escapeHtml(item.sourceHash ? item.sourceHash.slice(0, 12) : "—")}</span></li>`).join("");
    return `<section class="deconstruction-history-panel" aria-labelledby="deconstructionHistoryTitle"><header class="deconstruction-panel-heading"><div><span class="eyebrow">运行历史 / 只读</span><h2 id="deconstructionHistoryTitle">旧稿记录仍然可辨认</h2></div><span class="deconstruction-panel-note">不回链当前正文</span></header><ul>${items}</ul><p>历史运行只用于说明来源，不会跳到当前同编号章节伪装成精确证据。</p></section>`;
  }

  function renderDeconstructionResult(data) {
    const result = data.result;
    if (!result) return "";
    if (result.report && window.XumaiAnalysis) return window.XumaiAnalysis.render(result.report);
    return `<div class="deconstruction-result">${renderDeconstructionOverview(data)}${renderDeconstructionTimeline(data)}${renderDeconstructionChapterTable(data)}<section class="deconstruction-panel deconstruction-evidence-card"><header class="deconstruction-panel-heading"><div><span class="eyebrow">证据回链 / 正文最小片段</span><h2>每个结论都能回到原文</h2></div><span class="deconstruction-panel-note">${result.evidenceRefs.length} 条</span></header>${result.evidenceRefs.length ? `<div class="deconstruction-evidence-grid">${result.evidenceRefs.map((ref) => `<article class="deconstruction-evidence-item"><div class="deconstruction-evidence-item-head"><span class="mono">第 ${Number(ref.chapterNumber || 0)} 章</span><span>${escapeHtml(ref.label)}</span></div><blockquote>${escapeHtml(ref.excerpt || "正文片段未保留，请回到章节查看。")}</blockquote><div class="deconstruction-evidence-item-foot"><span>位移 ${Number(ref.charStart || 0).toLocaleString("zh-CN")}–${Number(ref.charEnd || 0).toLocaleString("zh-CN")} · UTF-16</span>${renderDeconstructionEvidence([ref])}</div></article>`).join("")}</div>` : `<p class="deconstruction-muted">服务端没有返回可回链证据。</p>`}</section><footer class="deconstruction-result-footer"><span>${escapeHtml(result.analysisLabel)}</span><span class="mono">DOCUMENT / ${escapeHtml(result.documentId.slice(0, 16))} · SOURCE / ${escapeHtml(result.sourceVersionId.slice(0, 16))} · REV / ${escapeHtml(result.sourceRevision ?? "—")}</span></footer></div>`;
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
      content.push(`<section class="deconstruction-working-panel"><div class="deconstruction-empty-mark">⌁</div><h2>服务端还没有返回可引用内容</h2><p>当前响应没有正式结果，页面保留空白，不将不完整响应冒充分析完成。</p></section>`);
    } else if (data.effectiveStatus === "stale") {
      content.push(`<section class="deconstruction-working-panel is-stale"><div class="deconstruction-empty-mark">↻</div><h2>当前稿本已经超过这版结果</h2><p>旧结果不会沿同编号章节跳转。确认当前正文没有待处理修改后，可以从这里重建一版。</p></section>`);
    } else if (data.effectiveStatus === "rebuild_required") {
      content.push(`<section class="deconstruction-working-panel is-stale"><div class="deconstruction-empty-mark">⌁</div><h2>先回正文处理待确认修改</h2><p>作品拆解不会越过作者确认直接读取这批旧章修改。处理完成后，再回到这里查看服务端状态。</p></section>`);
    } else {
      content.push(`<section class="deconstruction-working-panel"><div class="deconstruction-empty-mark">⌁</div><h2>结果会在这里出现</h2><p>任务在服务端继续运行；离开页面或刷新后，重新读取即可恢复。</p></section>`);
    }
    if (data.effectiveStatus !== "empty") content.push(`<p class="deconstruction-source-note"><span>分析来源</span>${escapeHtml(data.analysisLabel)}${data.source.versionId ? ` · 当前稿本 ${escapeHtml(data.source.versionId.slice(0, 12))}` : ""}${data.source.revision === null ? "" : ` · REV / ${data.source.revision}`}</p>`);
    content.push(renderDeconstructionHistory(data));
    elements.deconstructionPageContent.innerHTML = content.join("");
    if (data.result?.report && window.XumaiAnalysis) window.XumaiAnalysis.mount(elements.deconstructionPageContent, data.result.report, data.result.evidenceRefs, renderDeconstructionEvidence);
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

  async function loadArchiveWorkspace(projectId, chapterNumber = null) {
    if (!projectId) return;
    state.archiveProjectId = projectId;
    setActiveScreen("archive");
    try {
      const query = chapterNumber ? `?chapter_number=${encodeURIComponent(chapterNumber)}` : "";
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
      : current?.effectiveStatus === "stale" && current.actions.rebuild;
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
      charStart: deconstructionNumber(actionNode.dataset.charStart),
      charEnd: deconstructionNumber(actionNode.dataset.charEnd),
      offsetUnit: actionNode.dataset.offsetUnit || "",
      excerpt: actionNode.dataset.excerpt || "",
      label: "正文证据",
    };
  }

  function deconstructionEvidenceIdentityMatches(left, right) {
    if (!left || !right) return false;
    return ["id", "documentId", "sourceVersionId", "sourceRevision", "sourceHash", "chapterId", "chapterNumber", "charStart", "charEnd", "offsetUnit"]
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

  function showHistoricalDeconstructionEvidence(payload, reason) {
    const evidence = payload?.evidence || {};
    const chapter = payload?.chapter || {};
    const chapterNumber = evidence.chapter_number || chapter.chapter_number || "—";
    const excerpt = evidence.excerpt || "正文片段未保留。";
    setWorkspaceNoticeHtml(elements.deconstructionNotice, `<strong>证据只读 / 未跳转当前正文</strong><span>第 ${escapeHtml(chapterNumber)} 章 · ${escapeHtml(chapter.title || "历史稿本章节")}</span><blockquote>“${escapeHtml(excerpt)}”</blockquote><small>${escapeHtml(reason || "来源版本、修订号或哈希未通过校验；当前页面只保留章节级回看。")}</small>`, "red");
  }

  async function openDeconstructionEvidence(actionNode) {
    const projectId = state.deconstructionProjectId;
    if (!projectId) return;
    const clickedEvidence = deconstructionEvidenceFromNode(actionNode);
    if (!clickedEvidence.id) return;
    state.pendingEvidence = clickedEvidence;
    let current;
    let endpoint;
    try {
      // 点击后先重新读取 canonical source，再读取证据端点，避免用页面旧快照直接定位正文。
      current = await deconstructionApi.read(projectId);
      endpoint = await deconstructionApi.readEvidence(projectId, clickedEvidence.id);
    } catch (error) {
      state.pendingEvidence = null;
      setWorkspaceNotice(elements.deconstructionNotice, error.message || "证据回链读取失败，请稍后重试。", "red");
      return;
    }
    const currentEvidence = current.result?.evidenceRefs?.find((item) => item.id === clickedEvidence.id) || null;
    const endpointEvidence = normalizeEvidenceRef(endpoint?.evidence);
    const endpointIsCurrent = endpoint?.source_matches_current === true && endpoint?.historical === false;
    const precondition = deconstructionEvidenceMatchesSource(current, currentEvidence, current.result)
      && deconstructionEvidenceIdentityMatches(clickedEvidence, currentEvidence)
      && deconstructionEvidenceIdentityMatches(currentEvidence, endpointEvidence)
      && endpointIsCurrent;
    if (!precondition) {
      state.pendingEvidence = null;
      showHistoricalDeconstructionEvidence(endpoint, current.sourceMatch ? "这条证据的文档、来源版本、修订号或哈希未通过校验。" : "当前正文已经变化，这条证据属于历史稿本。 ");
      return;
    }
    state.pendingEvidence = currentEvidence;
    const navigated = await navigate(`/independent/${encodeURIComponent(projectId)}`);
    if (!navigated) {
      state.pendingEvidence = null;
      return;
    }
    state.editorMode = "independent";
    await loadIndependentWorkspace(projectId);
    const version = activeEditorVersion();
    const evidence = state.pendingEvidence;
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
    if (validEnd) {
      elements.chapterEditor.focus({ preventScroll: true });
      elements.chapterEditor.setSelectionRange(evidence.charStart, evidence.charEnd);
    } else {
      elements.chapterEditor.focus({ preventScroll: true });
    }
    const anchorText = validEnd
      ? `已按 UTF-16 字符位移选择正文中的第 ${evidence.charStart}–${evidence.charEnd} 位。`
      : sourceStillMatches
        ? "当前证据只提供章节级定位，未伪装成精确字符高亮。"
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
    const path = `/independent/${encodeURIComponent(projectId)}?view=deconstruction`;
    if (await navigate(path)) await loadDeconstructionWorkspace(projectId);
  }

  async function openDeconstructionVersions(projectId = state.deconstructionProjectId || state.archiveProjectId || state.editorProjectId) {
    if (!projectId) return;
    const path = `/independent/${encodeURIComponent(projectId)}`;
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
      if (await navigate(`/archive/${encodeURIComponent(state.editorProjectId)}`)) await loadArchiveWorkspace(state.editorProjectId);
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
        state.editorBuffer = state.editorConflict.content || "";
        state.editorTitleBuffer = state.editorConflict.title || "";
        state.editorRevision = state.editorConflict.server_revision || 0;
        state.editorDirty = false;
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
    if (action === "open-trial") openTrialDialog(actionNode.dataset.characterId);
    if (action === "archive-snapshot") loadArchiveWorkspace(state.archiveProjectId, actionNode.dataset.chapterNumber);
    if (action === "archive-open-editor") {
      if (state.archiveMode === "ai_assisted") openAIEditor();
      else {
        await navigate(`/independent/${encodeURIComponent(state.archiveProjectId)}`);
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
      if (projectId && await navigate(`/independent/${encodeURIComponent(projectId)}`)) await loadIndependentWorkspace(projectId);
    }
    if (action === "deconstruction-open-self") loadDeconstructionWorkspace(state.deconstructionProjectId);
    if (action === "deconstruction-open-archive") {
      const projectId = state.deconstructionProjectId;
      if (projectId && await navigate(`/archive/${encodeURIComponent(projectId)}`)) await loadArchiveWorkspace(projectId);
    }
    if (action === "deconstruction-open-versions") openDeconstructionVersions(state.deconstructionProjectId);
    if (action === "deconstruction-refresh") loadDeconstructionWorkspace(state.deconstructionProjectId);
    if (action === "deconstruction-retry") runDeconstructionAction("retry");
    if (action === "deconstruction-rebuild") runDeconstructionAction("rebuild");
    if (action === "open-deconstruction-evidence") openDeconstructionEvidence(actionNode);
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
    elements.archivePageContent?.addEventListener("click", handleAction);
    elements.deconstructionScreen?.addEventListener("click", handleAction);
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
    elements.completeChapterButton.addEventListener("click", completeCurrentChapter);
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
      if (!(await flushPendingSave())) {
        if (state.editorProjectId) {
          window.history.pushState({}, "", `/independent/${encodeURIComponent(state.editorProjectId)}`);
          setActiveScreen("independent");
        }
        return;
      }
      await restoreSession(routeFromLocation());
    });
    window.addEventListener("beforeunload", (event) => {
      if (state.editorDirty || state.editorSaving) {
        event.preventDefault();
        event.returnValue = "当前正文尚未保存。";
      }
    });
    window.addEventListener("pagehide", () => {
      if (state.editorDirty || state.editorSaving) void flushPendingSave({ keepalive: true });
    });
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden" && (state.editorDirty || state.editorSaving)) {
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
