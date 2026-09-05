from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class Stage33FrontendContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index_source = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        cls.app_source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        cls.css_source = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
        cls.browser_source = (ROOT / "tests" / "browser_stage33.cjs").read_text(encoding="utf-8")

    def test_chapter_query_is_canonical_and_safe(self) -> None:
        for marker in (
            "function chapterIdFromLocation",
            "function editorPath",
            "function chooseActiveChapter",
            "new URLSearchParams(window.location.search)",
            'params.set("chapter", chapterId)',
            'window.history.replaceState({}, "", path)',
            "最大的未完成章节",
            "最后一章",
        ):
            self.assertIn(marker, self.app_source)
        selection_start = self.app_source.index("function chooseActiveChapter")
        selection_end = self.app_source.index("\n  function renderChapterList", selection_start)
        selection_source = self.app_source[selection_start:selection_end]
        self.assertIn("version.chapters", selection_source)
        self.assertIn("requestedChapterId", selection_source)
        self.assertIn("status !== \"ready\"", selection_source)
        self.assertNotIn("localStorage", self.app_source)
        self.assertNotIn("sessionStorage", self.app_source)

    def test_chapter_switch_and_new_chapter_replace_url_and_focus_title(self) -> None:
        self.assertIn("updateChapterUrl(chapterId", self.app_source)
        self.assertIn("updateChapterUrl(newChapterId", self.app_source)
        self.assertIn("focusChapterTitle", self.app_source)
        self.assertIn('elements.chapterTitleInput.focus()', self.app_source)
        self.assertIn('state.activeChapterId = newChapterId', self.app_source)
        add_start = self.app_source.index("async function addIndependentChapter")
        add_end = self.app_source.index("\n  function openPendingChangesDialog", add_start)
        add_source = self.app_source[add_start:add_end]
        self.assertIn("const newChapterId = payload.chapter.chapter_id", add_source)
        self.assertIn("await loadIndependentWorkspace", add_source)
        self.assertIn("focusChapterTitle", add_source)

    def test_save_state_is_separate_from_analysis_state_and_blocks_failed_navigation(self) -> None:
        self.assertIn('id="editorAnalysisState"', self.index_source)
        for label in ("本地待保存", "保存中", "已保存", "保存失败", "保存冲突"):
            self.assertIn(label, self.app_source)
        self.assertIn("function setEditorAnalysisState", self.app_source)
        render_start = self.app_source.index("function renderEditorWorkspace")
        render_end = self.app_source.index("\n  function handleEditorInput", render_start)
        render_source = self.app_source[render_start:render_end]
        self.assertIn("setEditorAnalysisState", render_source)
        self.assertIn("setEditorSaveState", render_source)
        self.assertNotIn('setEditorSaveState("后台分析中', render_source)
        self.assertIn("state.editorConflict", self.app_source)
        self.assertIn("replaceActiveVersionChapter", self.app_source)
        self.assertIn("state.editorSavedRevision = serverChapter.server_revision", self.app_source)
        self.assertIn("if (leavingEditor", self.app_source)
        self.assertIn("flushPendingSave", self.app_source)

    def test_complete_flow_is_single_flight_and_completed_chapter_moves_to_next_action(self) -> None:
        self.assertIn("state.completeInFlight", self.app_source)
        self.assertIn("if (state.completeInFlight)", self.app_source)
        self.assertIn("state.addChapterInFlight", self.app_source)
        self.assertIn("新建下一章", self.app_source)
        self.assertIn("handleCompleteButtonClick", self.app_source)
        input_start = self.app_source.index("function handleEditorInput")
        input_end = self.app_source.index("\n  function renderSaveConflict", input_start)
        input_source = self.app_source[input_start:input_end]
        self.assertIn('elements.completeChapterButton.dataset.nextChapter = "false"', input_source)
        self.assertIn('elements.completeChapterButton.textContent = "完成本章 →"', input_source)
        complete_start = self.app_source.index("async function completeCurrentChapter")
        complete_end = self.app_source.index("\n  function wait", complete_start)
        complete_source = self.app_source[complete_start:complete_end]
        self.assertIn("await flushPendingSave", complete_source)
        self.assertIn("expected_revision", complete_source)
        self.assertIn("idempotency_key", complete_source)
        self.assertIn("finally", complete_source)

    def test_version_preview_is_complete_and_restore_requires_confirmation(self) -> None:
        for marker in (
            'id="restoreVersionDialog"',
            'id="restoreVersionTitle"',
            'id="confirmRestoreVersionButton"',
            'data-action="open-restore-confirm"',
            "创建新的当前稿本",
            "state.versionPreviewId",
            "state.restoreInFlight",
            "function openRestoreVersionConfirm",
            "function confirmRestoreVersion",
        ):
            self.assertIn(marker, self.index_source + self.app_source)
        preview_start = self.app_source.index("async function previewVersion")
        preview_end = self.app_source.index("\n  async function restoreVersion", preview_start)
        preview_source = self.app_source[preview_start:preview_end]
        self.assertIn("version.chapters.map", preview_source)
        self.assertIn("version-preview-chapter", preview_source)
        self.assertNotIn("slice(0, 260)", preview_source)
        self.assertNotIn("firstChapter", preview_source)
        restore_start = self.app_source.index("async function restoreVersion")
        restore_end = self.app_source.index("\n  async function selectArchiveSnapshot", restore_start)
        restore_source = self.app_source[restore_start:restore_end]
        self.assertIn("state.versionPreviewId", restore_source)
        self.assertIn("restoreInFlight", restore_source)
        self.assertIn("confirmRestoreVersion", self.app_source)
        self.assertIn("method: \"POST\"", restore_source)

    def test_dialog_focus_escape_tab_reduced_motion_and_responsive_contract(self) -> None:
        self.assertIn("function trapDialogFocus", self.app_source)
        self.assertIn('event.key === "Tab"', self.app_source)
        self.assertIn('event.key === "Escape"', self.app_source)
        self.assertIn("restoreDialogFocus", self.app_source)
        self.assertIn('aria-live="polite"', self.index_source)
        self.assertIn("prefers-reduced-motion: reduce", self.css_source)
        self.assertRegex(self.css_source, r"@media \(max-width: 1024px\)|@media \(max-width: 1120px\)")
        self.assertIn("overflow-x: hidden", self.css_source)
        self.assertIn("overflow-y: auto", self.css_source)

    def test_stage33_browser_script_exercises_real_state_boundaries(self) -> None:
        for marker in (
            "browser_stage33",
            "reducedMotion: 'reduce'",
            "stage33-browser",
            "chapter=",
            "新建下一章",
            "保存失败",
            "恢复确认",
            "版本预览",
            "consoleErrorsAndWarnings",
            "const failureContext = await browser.newContext",
            "fetch('/api/auth/logout'",
            "expectHttpFailure",
            "status: 401",
            "status: 409",
            "const restoreRequestListener",
            "dispatchEvent(new MouseEvent('click'",
            "assert.equal(restoreRequests, 1",
            "expectedHttpFailures",
        ):
            self.assertIn(marker, self.browser_source)
        failure_start = self.browser_source.index("const unsavedAfterExpiry")
        failure_end = self.browser_source.index("await failureContext.close()", failure_start)
        failure_source = self.browser_source[failure_start:failure_end]
        self.assertIn("expectHttpFailure", failure_source)
        self.assertIn("status: 401", failure_source)
        self.assertIn("inputValue(), unsavedAfterExpiry", failure_source)
        self.assertIn("failureEmail", self.browser_source)
        gate_start = self.browser_source.index("const chapterCountBeforeEditGate")
        gate_end = self.browser_source.index("const chapterTwoId", gate_start)
        gate_source = self.browser_source[gate_start:gate_end]
        self.assertIn("data-next-chapter", gate_source)
        self.assertIn("status: 409", gate_source)
        self.assertIn("pendingChangesDialog", gate_source)
        restore_start = self.browser_source.index("let restoreRequests")
        restore_end = self.browser_source.index("await layout(page, width, 'restored')", restore_start)
        restore_source = self.browser_source[restore_start:restore_end]
        self.assertIn("restoreRequestListener", restore_source)
        self.assertIn("dispatchEvent(new MouseEvent('click'", restore_source)
        self.assertIn("assert.equal(restoreRequests, 1", restore_source)
        self.assertNotRegex(self.browser_source, re.compile(r"page\.route|route\.fulfill|mock|skip", re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
