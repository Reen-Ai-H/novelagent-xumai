from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class Stage32FrontendDepthContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index_source = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        cls.app_source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        cls.css_source = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    def test_depth_report_and_nullable_metrics_are_explicitly_server_backed(self) -> None:
        for field in (
            "analysis_contract_version",
            "report_version",
            "characters",
            "plot",
            "foreshadowing",
            "rhythm",
            "reader_experience",
            "technique",
        ):
            self.assertIn(field, self.app_source)
        self.assertIn("deconstructionNullableNumber", self.app_source)
        for field in (
            "story_order",
            "pace",
            "tension",
            "information_density",
            "curiosity",
            "suspense",
            "emotional_valence",
        ):
            self.assertIn(f"deconstructionNullableNumber(item.{field})", self.app_source)
        self.assertIn('return typeof value === "number" && Number.isFinite(value) ? value : null;', self.app_source)
        self.assertIn("未绘制数值曲线", self.app_source)
        self.assertIn("storyOrder === null", self.app_source)
        self.assertIn('epistemicStatus === "unknown" ? normalizedConfidence(null)', self.app_source)
        self.assertIn("基于证据推断", self.app_source)

        marker = "function deconstructionNullableNumber"
        start = self.app_source.index(marker)
        end = self.app_source.index("\n  }\n", start) + len("\n  }")
        function_source = self.app_source[start:end]
        node_source = f"""
const assert = require("node:assert/strict");
const vm = require("node:vm");
const nullableNumber = vm.runInNewContext("(" + {json.dumps(function_source)} + ")");
assert.equal(nullableNumber(null), null);
assert.equal(nullableNumber(false), null);
assert.equal(nullableNumber("0"), null);
assert.equal(nullableNumber(0), 0);
assert.equal(nullableNumber(0.5), 0.5);
assert.equal(nullableNumber(Number.NaN), null);
"""
        completed = subprocess.run(
            ["node", "-e", node_source],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_exact_excerpt_guard_has_deterministic_match_and_mismatch_cases(self) -> None:
        marker = "function deconstructionEvidenceExcerptMatches"
        start = self.app_source.index(marker)
        end = self.app_source.index("\n  }\n", start) + len("\n  }")
        function_source = self.app_source[start:end]
        node_source = f"""
const assert = require("node:assert/strict");
const vm = require("node:vm");
const functionSource = {json.dumps(function_source)};
const matches = vm.runInNewContext("(" + functionSource + ")", {{
  DECONSTRUCTION_OFFSET_UNIT: "utf16_code_unit",
}});
const emojiEvidence = {{
  offsetUnit: "utf16_code_unit",
  charStart: 1,
  charEnd: 3,
  excerpt: "😀",
}};
assert.equal(matches(emojiEvidence, "A😀B"), true);
assert.equal(matches({{ ...emojiEvidence, excerpt: "错" }}, "A😀B"), false);
assert.equal(matches({{ ...emojiEvidence, charStart: 0, charEnd: 2, excerpt: "A😀" }}, "A😀B"), false);
assert.equal(matches({{ offsetUnit: "utf16_code_unit", charStart: 0, charEnd: 0, excerpt: "" }}, ""), true);
assert.equal(matches({{ offsetUnit: "utf16_code_unit", charStart: 0, charEnd: 3, excerpt: " A " }}, " A"), false);
assert.equal(matches({{ offsetUnit: "utf16_code_unit", charStart: 0, charEnd: 3, excerpt: " A " }}, " A "), true);
"""
        completed = subprocess.run(
            ["node", "-e", node_source],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

        locate_start = self.app_source.index("async function locateDeconstructionEvidence")
        locate_end = self.app_source.index("\n  function renderAIConversation", locate_start)
        locate_source = self.app_source[locate_start:locate_end]
        self.assertIn("const excerptMatches = validEnd && deconstructionEvidenceExcerptMatches(evidence, content);", locate_source)
        self.assertIn('"正文片段与证据摘录不一致，已降级为章节级回看。"', locate_source)
        self.assertIn("if (excerptMatches)", locate_source)
        self.assertIn("setSelectionRange(evidence.charStart, evidence.charEnd)", locate_source)

    def test_depth_tabs_are_roving_and_evidence_is_read_only(self) -> None:
        for label in ("人物", "剧情", "伏笔", "节奏", "读者", "文笔"):
            self.assertIn(label, self.app_source)
        for key in ("ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"):
            self.assertIn(f'event.key === "{key}"', self.app_source)
        self.assertIn('role="tab"', self.app_source)
        self.assertIn('tabindex="${activeView === "overview" ? "0" : "-1"}"', self.app_source)
        self.assertIn("event.preventDefault()", self.app_source)
        self.assertIn("rerenderDeconstructionDepth(next.id)", self.app_source)
        self.assertIn('id="deconstructionEvidenceDialog"', self.index_source)
        self.assertIn('aria-labelledby="deconstructionEvidenceTitle"', self.index_source)
        self.assertIn("source_matches_current", self.app_source)
        self.assertIn("historical", self.app_source)
        self.assertIn("read_only", self.app_source)
        self.assertIn("function renderDeconstructionHistory", self.app_source)
        self.assertIn("analysisContractVersion", self.app_source)
        self.assertIn('"深度 2.0"', self.app_source)
        self.assertIn('"基础 1.0"', self.app_source)
        self.assertIn('"版本未知"', self.app_source)
        has_results_start = self.app_source.index("function hasDeconstructionResults")
        has_results_end = self.app_source.index("\n  function formatDeconstructionCount", has_results_start)
        self.assertNotIn("history", self.app_source[has_results_start:has_results_end])
        self.assertIn("正文片段与证据摘录不一致", self.app_source)
        self.assertNotIn("localStorage", self.app_source)
        self.assertNotIn("sessionStorage", self.app_source)
        self.assertIn("prefers-reduced-motion: reduce", self.css_source)

        close_start = self.app_source.index("function closeDeconstructionEvidenceDialog")
        close_end = self.app_source.index("\n  function renderDeconstructionEvidenceLoading", close_start)
        close_source = self.app_source[close_start:close_end]
        self.assertIn("state.deconstructionEvidenceRequestToken += 1", close_source)
        self.assertIn("state.pendingEvidence = null", close_source)
        self.assertIn("closeDeconstructionEvidenceDialog({ clear: false })", self.app_source)
        self.assertNotIn("references.slice(0, 6)", self.app_source)
        self.assertIn("references.map((evidence, index)", self.app_source)
        self.assertIn("deconstructionApi.readEvidence(projectId, clickedEvidence.id)", self.app_source)

        input_start = self.app_source.index("function handleDeconstructionDepthInput")
        input_end = self.app_source.index("\n  function handleDeconstructionDepthChange", input_start)
        input_source = self.app_source[input_start:input_end]
        self.assertIn("state.deconstructionProgress = progress", input_source)
        self.assertIn("output.textContent = `${Math.round(progress)}%`", input_source)
        self.assertNotIn("rerenderDeconstructionDepth", input_source)
        change_start = input_end + 1
        change_end = self.app_source.index("\n  function handleDeconstructionTabKeydown", change_start)
        change_source = self.app_source[change_start:change_end]
        self.assertIn('actionNode.dataset.action === "deconstruction-depth-progress"', change_source)
        self.assertIn('rerenderDeconstructionDepth("depthProgressFilter")', change_source)

        open_start = self.app_source.index("async function openDeconstructionEvidence")
        open_end = self.app_source.index("async function locateDeconstructionEvidence", open_start)
        open_source = self.app_source[open_start:open_end]
        guard = "if (requestToken !== state.deconstructionEvidenceRequestToken) return;"
        self.assertGreaterEqual(open_source.count(guard), 2)
        self.assertLess(open_source.index(guard), open_source.index("const currentEvidence"))
        catch_start = open_source.index("} catch (error) {")
        pending = "state.pendingEvidence = null"
        catch_end = open_source.index(pending, catch_start) + len(pending)
        catch_source = open_source[catch_start:catch_end]
        self.assertLess(catch_source.index(guard), catch_source.index("state.pendingEvidence = null"))
        bind_start = self.app_source.index("function bindEvents")
        self.assertIn("state.deconstructionEvidenceRequestToken += 1", self.app_source[bind_start:])


if __name__ == "__main__":
    unittest.main()
