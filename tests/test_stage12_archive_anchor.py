from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class Stage12ArchiveAnchorRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    def test_programmatic_anchor_scroll_keeps_clicked_intent(self) -> None:
        self.assertIn("state.archiveAnchorIntent", self.source)
        self.assertIn("if (state.archiveAnchorIntent)", self.source)
        self.assertIn('addEventListener("scrollend"', self.source)

    def test_user_scroll_gestures_cancel_anchor_intent(self) -> None:
        for event_name in ("wheel", "touchstart", "touchmove", "pointerdown", "pointermove", "keydown"):
            self.assertIn(f'addEventListener("{event_name}"', self.source)
        self.assertIn("cancelArchiveAnchorIntent", self.source)

    def test_click_records_intent_before_programmatic_scroll(self) -> None:
        click_start = self.source.index('link.addEventListener("click"')
        click_end = self.source.index("window.history.replaceState", click_start)
        click_body = self.source[click_start:click_end]
        self.assertLess(click_body.index("state.archiveAnchorIntent"), click_body.index("scrollIntoView"))
        self.assertIn("activate(target.id)", click_body)

    def test_archive_anchor_cleanup_removes_gesture_listeners_and_timer(self) -> None:
        cleanup_start = self.source.index("const cleanup = () =>")
        cleanup_end = self.source.index("state.archiveScrollSpyCleanup = cleanup", cleanup_start)
        cleanup_body = self.source[cleanup_start:cleanup_end]
        self.assertIn("clearTimeout(state.archiveAnchorUnlockTimer)", cleanup_body)
        self.assertIn('removeEventListener("wheel"', cleanup_body)
        self.assertIn('removeEventListener("keydown"', cleanup_body)
