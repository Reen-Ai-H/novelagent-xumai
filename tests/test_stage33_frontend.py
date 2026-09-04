from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class Stage33FrontendContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index_source = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        cls.app_source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        cls.css_source = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    def _function_source(self, marker: str) -> str:
        start = self.app_source.index(marker)
        end = self.app_source.index("\n  }\n", start) + len("\n  }")
        return self.app_source[start:end]

    def test_chapter_query_selection_has_safe_fallback_priority(self) -> None:
        self.assertIn("function selectInitialChapter", self.app_source)
        self.assertIn("function chapterIdFromLocation", self.app_source)
        function_source = self._function_source("function selectInitialChapter")
        node_source = f"""
const assert = require("node:assert/strict");
const vm = require("node:vm");
const select = vm.runInNewContext("(" + {json.dumps(function_source)} + ")");
const chapters = [
  {{chapter_id: "one", chapter_number: 1, status: "ready", content: "one", formal_content: "one"}},
  {{chapter_id: "two", chapter_number: 2, status: "drafting", content: "two", formal_content: ""}},
  {{chapter_id: "three", chapter_number: 3, status: "drafting", content: "three", formal_content: ""}},
];
assert.equal(select(chapters, "one").chapter.chapter_id, "one");
assert.equal(select(chapters, "missing").chapter.chapter_id, "three");
assert.equal(select(chapters, "").chapter.chapter_id, "three");
assert.equal(select(chapters.map(ch => ({{...ch, status: "ready", formal_content: ch.content}})), "missing").chapter.chapter_id, "three");
"""
        completed = subprocess.run(
            ["node", "-e", node_source],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_notification_target_allowlist_rejects_unsafe_chapter_and_query_inputs(self) -> None:
        self.assertIn("function notificationTargetPath", self.app_source)
        function_source = self._function_source("function notificationTargetPath")
        node_source = f"""
const assert = require("node:assert/strict");
const vm = require("node:vm");
const targetPath = vm.runInNewContext("(" + {json.dumps(function_source)} + ")", {{
  URL,
  window: {{ location: {{ origin: "http://127.0.0.1:8000" }} }},
}});
assert.equal(targetPath("/independent/p1?chapter=chapter_2&view=deconstruction"), "/independent/p1?chapter=chapter_2&view=deconstruction");
assert.equal(targetPath("/independent/p1?view=deconstruction&chapter=chapter_2"), "/independent/p1?view=deconstruction&chapter=chapter_2");
assert.equal(targetPath("/independent/p1?chapter=chapter_2&view=independent"), null);
assert.equal(targetPath("/independent/p1?chapter=../../evil"), null);
assert.equal(targetPath("/independent/p1?chapter=chapter_2&redirect=https%3A%2F%2Fevil.example"), null);
assert.equal(targetPath("//evil.example/independent/p1"), null);
assert.equal(targetPath("javascript:alert(1)"), null);
"""
        completed = subprocess.run(
            ["node", "-e", node_source],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_save_and_analysis_states_are_separate_and_next_chapter_is_focusable(self) -> None:
        self.assertIn('id="editorAnalysisState"', self.index_source)
        for marker in (
            "function setEditorAnalysisState",
            'setEditorSaveState("已保存"',
            "chapter.server_revision",
            "function focusEditorTitle",
            '"add-next-chapter"',
            "state.activeChapterId = newChapterId || state.activeChapterId",
            "history.replaceState",
        ):
            self.assertIn(marker, self.app_source)
        self.assertNotIn('chapter.status === "ready" ? "已保存" : "等待保存"', self.app_source)
        self.assertIn("editorCompleting", self.app_source)
        self.assertIn("editorAddingChapter", self.app_source)

    def test_version_preview_is_full_chapter_read_only_and_restore_requires_confirmation(self) -> None:
        self.assertIn('id="versionPreviewTitle"', self.app_source)
        for marker in (
            'id="restoreVersionDialog"',
            'id="confirmRestoreVersionButton"',
            'id="cancelRestoreVersionButton"',
            'aria-labelledby="restoreVersionTitle"',
        ):
            self.assertIn(marker, self.index_source)
        for marker in (
            "function renderVersionPreview",
            "function previewVersionChapter",
            "function openRestoreConfirmation",
            "function confirmRestoreVersion",
            "state.versionPreview",
            'data-action="open-restore-confirmation"',
            "version.chapters.map",
            "restoreVersionDialog?.addEventListener(\"cancel\"",
        ):
            self.assertIn(marker, self.app_source)
        preview_render_start = self.app_source.index("function renderVersionPreview")
        preview_render_end = self.app_source.index("async function previewVersion", preview_render_start)
        self.assertNotIn("chapters[0]", self.app_source[preview_render_start:preview_render_end])
        preview_start = self.app_source.index("async function previewVersion")
        preview_end = self.app_source.index("function previewVersionChapter", preview_start)
        self.assertNotIn("slice(0, 260)", self.app_source[preview_start:preview_end])
        self.assertNotIn('action === "restore-version"', self.app_source)

    def test_responsive_and_reduced_motion_contract_is_present(self) -> None:
        self.assertIn("prefers-reduced-motion: reduce", self.css_source)
        self.assertIn("@media (max-width: 1024px)", self.css_source)
        self.assertIn("version-preview-body", self.css_source)
        self.assertIn("overflow-x: hidden", self.css_source)
        self.assertIn("handleVersionPreviewKeydown", self.app_source)


if __name__ == "__main__":
    unittest.main()
