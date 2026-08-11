from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class Stage10ArchiveVisualContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app_source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        cls.css_source = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    def test_four_archive_sections_keep_ordered_anchor_contract(self) -> None:
        expected = [
            "archive-characters",
            "archive-storylines",
            "archive-foreshadowing",
            "archive-questions",
        ]
        section_ids = re.findall(r'<section id="(archive-[^"]+)"[^>]+data-archive-section=', self.app_source)
        self.assertEqual(section_ids[:4], expected)
        for section_id in expected:
            self.assertIn(f'data-archive-anchor="{section_id}"', self.app_source)

    def test_scrollspy_uses_visible_focus_line_and_explicit_document_bottom(self) -> None:
        self.assertIn("const atDocumentBottom = maxScroll <= 0 || scrollY >= maxScroll - 4;", self.app_source)
        self.assertIn("const focusLine = scrollY +", self.app_source)
        self.assertIn("section.getBoundingClientRect()", self.app_source)
        self.assertIn("rect.bottom >= 0", self.app_source)
        self.assertIn("activeSection = sections[sections.length - 1]", self.app_source)

    def test_anchor_clicks_center_content_and_reduced_motion_is_auto(self) -> None:
        self.assertIn('behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"', self.app_source)
        self.assertIn('block: "center"', self.app_source)
        self.assertNotIn('block: "start"', self.app_source)

    def test_archive_has_no_fixed_bottom_spacer_and_tail_contract_is_bounded(self) -> None:
        self.assertNotIn("archive-scroll-bottom-space", self.app_source)
        self.assertNotIn("archive-scroll-bottom-space", self.css_source)
        self.assertNotRegex(self.css_source, r"archive-detail-panel[^}]*padding-bottom:\s*(?:1[6-9][1-9]|[2-9][0-9]{2})px")

    def test_timeline_uses_short_complete_demo_label(self) -> None:
        self.assertIn("function archiveAnalysisLabel", self.app_source)
        self.assertIn('return "演示分析";', self.app_source)
        self.assertNotIn("snapshot.analysis_label || \"档案已更新\"", self.app_source)
        self.assertNotIn("未配...", self.app_source)

    def test_reduced_motion_keeps_scroll_behavior_auto(self) -> None:
        self.assertIn("scroll-behavior: auto !important", self.css_source)
