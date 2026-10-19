"""Pure frontend contracts; no app import, author data, or network."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Stage38FrontendTest(unittest.TestCase):
    def test_async_safety_regressions(self):
        result = subprocess.run(
            ["node", "tests/test_stage38_frontend_safety.cjs"], cwd=ROOT,
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_display_and_graph_contracts(self):
        result = subprocess.run(
            ["node", "tests/test_stage38_frontend_unit.cjs"], cwd=ROOT,
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
