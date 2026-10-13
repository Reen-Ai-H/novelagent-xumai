"""Local acceptance workspace isolated from the author's existing .novel_* data.

Use --authorized-live only for explicitly authorized provider evaluation.
Without that flag no model operation is available. Binds only to localhost.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def build_app(data: Path, *, live: bool):
    import main
    from app import ai_routes, deconstruction_routes, entry_routes, independent_routes
    from app.agents.deconstruction_model import create_runtime
    from app.agents.llm_runtime import LLMRuntime, LLMRuntimeSettings
    from app.core.account_store import AccountStore
    from app.core.ai_service import AIStudioService
    from app.core.ai_store import AIStore
    from app.core.book_analysis import BookAnalysis
    from app.core.deconstruction_service import DeconstructionService
    from app.core.deconstruction_store import DeconstructionStore
    from app.core.entry_service import EntryService
    from app.core.independent_service import IndependentWorkspaceService
    from app.core.independent_store import IndependentStore
    from app.core.project_store import JsonProjectStore

    accounts = AccountStore(data / "accounts.json")
    projects = JsonProjectStore(data / "projects")
    independent = IndependentWorkspaceService(projects=projects, store=IndependentStore(data / "independent"))
    factory = create_runtime if live else lambda: LLMRuntime(LLMRuntimeSettings())
    ai = AIStudioService(projects=projects, manuscript=independent, store=AIStore(data / "ai"), runtime=factory())
    entry = EntryService(accounts=accounts, projects=projects, independent=independent.store, ai=ai.store)
    entry.transaction_coordinator = ai.transactions
    deconstruction = DeconstructionService(independent=independent, store=DeconstructionStore(data / "deconstruction"))
    independent.deconstruction_service = deconstruction
    entry_routes.account_store, entry_routes.entry_service = accounts, entry
    independent_routes.independent_service = independent
    ai_routes.ai_service = ai
    deconstruction_routes.deconstruction_service = deconstruction
    deconstruction_routes.book_analysis = BookAnalysis(deconstruction, runtime_factory=factory)
    deconstruction_routes.create_runtime = factory
    return main.app, independent, deconstruction


def seed_reports(app, independent, deconstruction, data: Path, outputs: Path):
    """Import via real authenticated APIs, never by editing manuscript records."""
    from fastapi.testclient import TestClient
    from scripts.live_deconstruction import private_json
    marker = data / "review.json"
    if marker.exists():
        return json.loads(marker.read_text(encoding="utf-8"))
    chapters = json.loads((outputs / "chapters.json").read_text(encoding="utf-8"))
    reports = sorted(path for path in outputs.glob("report-*.json") if not path.name.endswith(".receipt.json"))
    if not reports:
        raise ValueError("No verified reports are available")
    # All verification must pass before creating an acceptance project.
    for path in reports:
        receipt = json.loads(path.with_name(path.stem + ".receipt.json").read_text(encoding="utf-8"))
        report = json.loads(path.read_text(encoding="utf-8"))
        batch = [c for c in chapters if c["chapter_number"] in report["chapter_numbers"]]
        source_hash = hashlib.sha256(json.dumps(batch, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if (receipt["invalid_evidence_ids"] or not receipt["scope_correct"]
                or receipt.get("source_hash") != source_hash
                or receipt.get("report_hash") != hashlib.sha256(path.read_bytes()).hexdigest()
                or receipt.get("quality_status") != "passed"):
            raise ValueError("A report has not passed evidence verification")
    client = TestClient(app)
    email = "mimo-review@xumai.local"
    def require(response):
        if response.status_code != 200:
            raise ValueError(f"Review API failed with HTTP {response.status_code}")
        return response.json()
    account = require(client.post("/api/auth/email", json={"email": email}))["account"]["account_id"]
    project = require(client.post("/api/library/projects", json={"title": "魔道祖师 · 前十章 MiMo 验收", "mode": "independent"}))["project"]["project_id"]
    manuscript = "\n\n".join(f"# {c['title']}\n{c['content']}" for c in chapters)
    preview = require(client.post(f"/api/independent/projects/{project}/imports/preview",
                                  json={"filename": "前十章.md", "content_base64": base64.b64encode(manuscript.encode()).decode()}))["preview"]
    require(client.post(f"/api/independent/projects/{project}/imports/{preview['preview_id']}/confirm"))
    deconstruction.process_background_tasks()
    source = deconstruction._source(project, account)
    if len(source.chapters) != len(chapters):
        raise ValueError("Imported chapter boundaries differ from the evaluated source")
    if any(actual.chapter_number != expected["chapter_number"] or actual.content != expected["content"]
           for actual, expected in zip(source.chapters, chapters)):
        raise ValueError("Imported narrative differs from the evaluated source")
    for path in reports:
        require(client.post(f"/api/independent/projects/{project}/deconstruction/import", json={"report": json.loads(path.read_text(encoding="utf-8"))}))
    info = dict(email=email, project_id=project, path=f"/independent/{project}?view=deconstruction", reports=len(reports))
    private_json(marker, info)
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".codex" / "stage34-review")
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--port", type=int, default=8034)
    parser.add_argument("--authorized-live", action="store_true")
    args = parser.parse_args()
    data = args.data_dir.resolve()
    if ROOT / ".codex" not in data.parents:
        parser.error("Review data must remain under the ignored .codex directory")
    data.mkdir(parents=True, exist_ok=True)
    os.chmod(data, 0o700)
    app, independent, deconstruction = build_app(data, live=args.authorized_live)
    if args.reports:
        print(json.dumps(seed_reports(app, independent, deconstruction, data, args.reports), ensure_ascii=False), flush=True)
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
