from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class Stage31CDeconstructionFrontendContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index_source = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        cls.app_source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        cls.css_source = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    def test_deconstruction_is_an_independent_workspace_view(self) -> None:
        self.assertIn('id="deconstructionScreen"', self.index_source)
        for label in ("正文", "作品拆解", "故事档案", "版本记录"):
            self.assertIn(f">{label}</strong>", self.index_source)
        self.assertIn('data-action="show-deconstruction"', self.index_source)
        self.assertIn('data-action="deconstruction-open-self"', self.index_source)
        self.assertNotIn('data-action="deconstruction-open-archive"', self.index_source)
        self.assertIn('id="deconstructionSubnav"', self.index_source)
        for section in ("plot", "characters", "time"):
            self.assertIn(f'data-section="{section}"', self.index_source)

    def test_adapter_uses_the_real_stage31_read_and_action_contract(self) -> None:
        self.assertIn("const deconstructionApi = Object.freeze({", self.app_source)
        self.assertIn("/api/independent/projects/${encodeURIComponent(projectId)}/deconstruction", self.app_source)
        self.assertIn("this.action(projectId, action)", self.app_source)
        self.assertIn("this.evidence(projectId, evidenceId)", self.app_source)
        self.assertIn('method: "POST"', self.app_source)
        for field in ("effective_status", "run_status", "source_match", "active_run", "payload.result", "payload.actions", "payload.history"):
            self.assertIn(field, self.app_source)
        self.assertIn("expected_source_version_id", self.app_source)
        self.assertIn("expected_source_revision", self.app_source)
        self.assertIn("expected_source_hash", self.app_source)
        self.assertIn("idempotency_key", self.app_source)
        self.assertNotIn("/api/deconstruction/projects/", self.app_source)

        canonical_slice = self.app_source[self.app_source.index("const deconstructionStatusText"):self.app_source.index("function renderArchivePage")]
        for forbidden in ("payload?.deconstruction", "payload?.document", "root.status", "payload?.status", "root.document"):
            self.assertNotIn(forbidden, canonical_slice)

    def test_all_server_states_are_rendered_without_promoting_unknown_to_completed(self) -> None:
        for status in (
            "empty",
            "queued",
            "running",
            "completed",
            "failed_retryable",
            "stale",
            "rebuild_required",
        ):
            self.assertIn(f"{status}:", self.app_source)
        self.assertIn("className = `deconstruction-status-pill is-${data.effectiveStatus}`", self.app_source)
        self.assertIn(".deconstruction-status-pill", self.css_source)
        self.assertIn('if (!deconstructionStatusSet.has(status) || !deconstructionRunStatusSet.has(runStatus))', self.app_source)
        self.assertIn('if (result && (status !== "completed" || runStatus !== "completed" || !sourceMatch))', self.app_source)
        self.assertIn('includes(data.runStatus)', self.app_source)

    def test_canonical_result_and_absolute_anchors_are_normalized(self) -> None:
        for field in (
            "value.overview",
            "value.timeline",
            "value.chapter_breakdowns",
            "value.evidence",
            "value.source_version_id",
            "value.source_revision",
            "value.source_hash",
            "ref.document_id",
            "ref.source_version_id",
            "ref.source_revision",
            "ref.source_hash",
            "ref.offset_unit",
            "normalized_start",
            "normalized_end",
            "word_start",
            "word_end",
            "narrative_function",
            "core_events",
            "scenes",
            "uncertainty",
        ):
            self.assertIn(field, self.app_source)
        self.assertIn("0% 起于正文开头，100% 落在正文结尾", self.app_source)
        self.assertIn("章节待定位", self.app_source)
        self.assertIn("暂未绑定来源证据", self.app_source)

    def test_evidence_links_return_to_editor_and_only_select_valid_offsets(self) -> None:
        self.assertIn('data-action="open-deconstruction-evidence"', self.app_source)
        for attribute in ("data-document-id", "data-source-version-id", "data-source-revision", "data-source-hash", "data-offset-unit"):
            self.assertIn(attribute, self.app_source)
        self.assertIn("navigate(`/independent/${encodeURIComponent(projectId)}`)", self.app_source)
        self.assertIn("setSelectionRange(evidence.charStart, evidence.charEnd)", self.app_source)
        self.assertIn("deconstructionEvidenceIdentityMatches", self.app_source)
        self.assertIn("deconstructionEvidenceMatchesSource", self.app_source)
        self.assertIn("source_matches_current", self.app_source)
        self.assertIn('evidence.offsetUnit === DECONSTRUCTION_OFFSET_UNIT', self.app_source)
        self.assertIn("evidence.charStart >= 0", self.app_source)
        self.assertIn("evidence.charEnd <= content.length", self.app_source)
        self.assertIn("章节级回看", self.app_source)
        self.assertNotIn("|| version?.chapters?.find((item) => evidence.chapterNumber", self.app_source)

    def test_status_actions_follow_server_capabilities(self) -> None:
        action_slice = self.app_source[self.app_source.index("function deconstructionStatusAction"):self.app_source.index("function renderDeconstructionStatus")]
        self.assertIn('data.effectiveStatus === "failed_retryable" && data.actions.retry', action_slice)
        self.assertIn('data.effectiveStatus === "stale" && data.actions.rebuild', action_slice)
        self.assertIn('data.effectiveStatus === "rebuild_required"', action_slice)
        self.assertIn('data-action="deconstruction-open-editor"', action_slice)
        self.assertNotIn('data.effectiveStatus === "rebuild_required" && data.actions.rebuild', action_slice)
        self.assertIn('current?.effectiveStatus === "failed_retryable"', self.app_source)
        self.assertIn('current?.effectiveStatus === "stale"', self.app_source)

    def test_page_uses_a_scroll_container_for_wide_breakdown_table(self) -> None:
        self.assertIn("overflow-x: auto", self.css_source)
        self.assertIn(".deconstruction-table-wrap", self.css_source)
        self.assertIn("min-width: 1080px", self.css_source)
        self.assertIn("min-width: 0", self.css_source)
        self.assertRegex(self.css_source, r"@media \(max-width: 1020px\)|@media \(max-width: 900px\)")

    def test_keyboard_focus_and_reduced_motion_contracts_remain_present(self) -> None:
        self.assertIn(":focus-visible", self.css_source)
        self.assertIn("prefers-reduced-motion: reduce", self.css_source)
        self.assertIn("animation: none !important", self.css_source)
        self.assertIn('aria-live="polite"', self.index_source)
        self.assertIn('aria-busy="false"', self.index_source)
        self.assertNotIn("localStorage", self.app_source)
        self.assertNotIn("sessionStorage", self.app_source)

    def test_no_static_result_fixture_is_embedded_in_the_deconstruction_view(self) -> None:
        render_start = self.app_source.index("function renderDeconstructionPage")
        render_end = self.app_source.index("function renderDeconstructionLoading")
        render_source = self.app_source[render_start:render_end]
        self.assertIn("renderDeconstructionResult(data)", render_source)
        self.assertIn("hasDeconstructionResults(data)", render_source)
        self.assertIn("data.effectiveStatus === \"completed\"", render_source)
        self.assertNotRegex(render_source, re.compile(r"雾港|陆沉|第一章"))


if __name__ == "__main__":
    unittest.main()
