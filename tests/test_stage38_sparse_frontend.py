"""Sparse public-report viewer contracts; no backend, stores or network."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Stage38SparseFrontendTest(unittest.TestCase):
    def test_explicit_versions_and_sparse_analysis(self):
        result = subprocess.run(
            ["node", "tests/test_stage38_sparse_frontend.cjs"], cwd=ROOT,
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
