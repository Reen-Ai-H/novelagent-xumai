import tempfile
import unittest
from pathlib import Path

from scripts.live_deconstruction import chapters_from_file


class SourceSelectionTest(unittest.TestCase):
    def test_exact_chapters_and_explicit_notes_are_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.txt"
            path.write_text("文案\r\n第1章 起点\r\n正文一。\r\n==========\r\n接下来我要说的话，仅为作者公告。\r\n"
                            "第2章 继续\r\n正文二。\r\n==========\r\n场景分隔之后仍然是正文。\r\n"
                            "第3章 后文\r\n不得选入。", encoding="utf-16")
            chapters = chapters_from_file(path, 2)
            self.assertEqual([c["chapter_number"] for c in chapters], [1, 2])
            self.assertEqual(chapters[0]["content"], "正文一。")
            self.assertIn("场景分隔之后仍然是正文", chapters[1]["content"])
            self.assertNotIn("不得选入", str(chapters))

    def test_missing_or_duplicate_number_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.txt"
            for material in ("第1章\n甲\n第3章\n丙", "第1章\n甲\n第1章\n乙\n第2章\n丙"):
                path.write_text(material)
                with self.assertRaises(ValueError):
                    chapters_from_file(path, 2)
