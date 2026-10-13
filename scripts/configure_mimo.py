"""Install an explicitly supplied local MiMo credential without displaying it.

The input is data only. RTF conversion is delegated to macOS textutil; no
instructions or URLs from that document are executed or trusted.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile


def configure(source: Path, destination: Path) -> dict:
    if source.suffix.lower() == ".rtf":
        result = subprocess.run(["textutil", "-convert", "txt", "-stdout", str(source)],
                                capture_output=True, check=True)
        material = result.stdout.decode("utf-8")
    else:
        material = source.read_text(encoding="utf-8")
    keys = set(re.findall(r"(?:ttp-|tp-|sk-)[A-Za-z0-9_-]{16,}", material))
    if len(keys) != 1:
        raise ValueError("Expected exactly one credential; no configuration was changed")
    key = keys.pop()
    base = ("https://token-plan-cn.xiaomimimo.com/v1" if key.startswith(("tp-", "ttp-"))
            else "https://api.xiaomimimo.com/v1")
    values = {"LLM_PROVIDER": "mimo", "MIMO_API_KEY": key, "MIMO_BASE_URL": base,
              "MIMO_MODEL": "mimo-v2.6-pro", "DECONSTRUCTION_API_KEY": key,
              "DECONSTRUCTION_BASE_URL": base, "DECONSTRUCTION_MODEL": "mimo-v2.6-pro"}
    original = destination.read_text(encoding="utf-8") if destination.exists() else ""
    lines = [line for line in original.splitlines()
             if not re.match(r"^\s*(?:export\s+)?(" + "|".join(values) + r")\s*=", line)]
    lines.extend(f"{name}={value}" for name, value in values.items())
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as out:
        os.chmod(out.name, 0o600)
        out.write("\n".join(lines) + "\n")
        out.flush()
        os.fsync(out.fileno())
        temp = Path(out.name)
    temp.replace(destination)
    return {"configured": True, "provider": "mimo", "model": values["MIMO_MODEL"],
            "credential_displayed": False, "other_configuration_preserved": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(__file__).resolve().parents[1] / ".env")
    args = parser.parse_args()
    try:
        print(configure(args.source, args.env_file))
    except Exception:
        raise SystemExit("Credential configuration failed; credential contents were not displayed") from None
