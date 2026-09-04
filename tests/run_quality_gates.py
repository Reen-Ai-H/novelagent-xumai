"""Reproducible automated gates; these do not replace browser or independent audit.

Run from a clean checkout. No developer .env or model credentials are required.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


def run() -> int:
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful() or result.skipped or result.testsRun < 135:
        print(json.dumps({"gate": "tests", "passed": False, "count": result.testsRun, "skipped": len(result.skipped)}))
        return 1

    import main

    methods = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
    paths = main.app.openapi()["paths"]
    legacy = {key: value for key, value in paths.items() if key == "/novel" or key.startswith("/novel/")}
    operation_count = sum(len(methods.intersection(value)) for value in paths.values())
    legacy_operations = sum(len(methods.intersection(value)) for value in legacy.values())
    counts = {"paths": len(paths), "operations": operation_count, "legacy_paths": len(legacy), "legacy_operations": legacy_operations}
    print(json.dumps({"gate": "openapi", **counts}))
    if len(paths) < 58 or operation_count < 61 or len(legacy) != 16 or legacy_operations != 19:
        return 1
    for command in (
        [sys.executable, "-m", "compileall", "-q", "app", "core", "schemas", "main.py"],
        ["node", "--check", "frontend/app.js"],
        ["git", "diff", "--check"],
    ):
        subprocess.run(command, cwd=ROOT, check=True)
    print(json.dumps({"gate": "automated", "passed": True, "tests": result.testsRun, "failed": 0, "skipped": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
