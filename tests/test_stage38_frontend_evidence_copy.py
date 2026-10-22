"""Offline source-review copy regression; no application or data-store imports."""
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class EvidenceCopyFrontendTest(unittest.TestCase):
    def test_evidence_copy_preserves_selection_and_source_guards(self):
        result = subprocess.run(
            ["node", "tests/test_stage38_frontend_evidence_copy.cjs"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
