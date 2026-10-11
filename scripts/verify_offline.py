"""Run the existing tests in a source-only copy with credentials and network disabled."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import unittest


class CompactResult(unittest.TextTestResult):
    def _exc_info_to_string(self, err, test):
        message = super()._exc_info_to_string(err, test)
        if len(message) > 7000:
            return message[:6000] + "\n[oversized assertion rendering truncated; failure is preserved]\n" + message[-1000:]
        return message


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--pattern", default="test*.py")
    args = parser.parse_args()
    destination = args.destination or Path(tempfile.mkdtemp(prefix="xumai-offline-"))
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("app", "core", "schemas", "tests", "frontend", "docs", "scripts"):
        shutil.copytree(root / name, destination / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.local.md"))
    for name in ("main.py", "config.py", ".env.example", "requirements.txt"):
        shutil.copy2(root / name, destination / name)
    for key in tuple(os.environ):
        if any(part in key.upper() for part in ("API_KEY", "OPENAI", "DASHSCOPE", "DEEPSEEK", "MIMO", "LLM_", "DECONSTRUCTION_")):
            os.environ.pop(key, None)
    os.chdir(destination)
    sys.path.insert(0, str(destination))
    def blocked(*args, **kwargs):
        raise RuntimeError("Network disabled for offline verification")
    socket.socket.connect = blocked
    result = unittest.TextTestRunner(verbosity=1, resultclass=CompactResult).run(unittest.defaultTestLoader.discover("tests", pattern=args.pattern))
    print(json.dumps(dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                          skipped=len(result.skipped), isolated_source=str(destination))))
    return int(not result.wasSuccessful() or bool(result.skipped))


if __name__ == "__main__":
    raise SystemExit(main())
