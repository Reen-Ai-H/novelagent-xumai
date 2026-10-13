from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class Stage32DeconstructionEvidenceFrontendTest(unittest.TestCase):
    """Keep evidence readable when imported reports are only partially bound."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report_source = (ROOT / "frontend" / "deconstruction-report.js").read_text(encoding="utf-8")
        cls.app_source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    def test_report_viewer_does_not_assume_optional_fields(self) -> None:
        for field in (
            "Array.isArray(report.events)",
            "Array.isArray(report.characters)",
            "Array.isArray(report.open_questions)",
            "Array.isArray(report.evidence)",
            "report.events[0]?.id || null",
        ):
            self.assertIn(field, self.report_source)
        self.assertIn("暂未绑定原文依据", self.report_source)

    def test_report_viewer_preserves_old_quotes_without_faking_a_link(self) -> None:
        self.assertIn("这条旧结果没有绑定当前正文回链", self.report_source)
        self.assertIn("reportEvidence.get(id)", self.report_source)
        self.assertIn("不能回到正文核对", self.report_source)

    def test_current_evidence_keeps_endpoint_and_legacy_evidence_is_static(self) -> None:
        self.assertIn('data-action="open-deconstruction-evidence"', self.app_source)
        self.assertIn("!evidence?.id || !evidence?.documentId", self.app_source)
        self.assertIn("来源稿本未绑定，暂不能回到正文", self.app_source)
        self.assertIn("source_matches_current", self.app_source)
        self.assertIn("setSelectionRange(evidence.charStart, evidence.charEnd)", self.app_source)


if __name__ == "__main__":
    unittest.main()
