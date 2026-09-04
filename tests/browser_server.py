"""Run the real app against an isolated, reusable browser-test data directory.

No model transport, production data, fixture responses or extra HTTP routes.
Launch from a clean worktree with no .env. A fresh temporary directory is used
by default; --data-dir may reuse only a directory created by this helper.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8032)
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if (root / ".env").exists():
        parser.error("Use a clean worktree without .env; this helper does not read developer secrets.")
    for name in tuple(os.environ):
        if name.upper().startswith(("OPENAI_", "DASHSCOPE_", "LLM_")):
            del os.environ[name]
    sys.path.insert(0, str(root))
    marker_name = ".xumai-browser-fixture"
    if args.data_dir is None:
        data = Path(tempfile.mkdtemp(prefix="xumai-stage32-browser-"))
        (data / marker_name).write_text("synthetic browser test data only\n", encoding="utf-8")
    else:
        data = args.data_dir.resolve()
        if not (data / marker_name).is_file():
            parser.error("--data-dir must be an existing isolated directory created by this helper.")

    import main
    import uvicorn
    from app import ai_routes, deconstruction_routes, entry_routes, independent_routes
    from app.core.account_store import AccountStore
    from app.core.ai_service import AIStudioService
    from app.core.ai_store import AIStore
    from app.core.deconstruction_service import DeconstructionService
    from app.core.deconstruction_store import DeconstructionStore
    from app.core.entry_service import EntryService
    from app.core.independent_service import IndependentWorkspaceService
    from app.core.independent_store import IndependentStore
    from app.core.project_store import JsonProjectStore

    class NoPaidRuntime:
        available = False
        provider = "unavailable"
        model = "unavailable"

        async def complete(self, **kwargs):
            raise AssertionError("Paid model calls are forbidden in browser verification")

        async def structured(self, **kwargs):
            raise AssertionError("Paid model calls are forbidden in browser verification")

    accounts = AccountStore(data / "accounts" / "accounts.json")
    projects = JsonProjectStore(data / "projects")
    independent = IndependentWorkspaceService(
        projects=projects, store=IndependentStore(data / "independent")
    )
    ai = AIStudioService(
        projects=projects, manuscript=independent, store=AIStore(data / "ai"),
        runtime=NoPaidRuntime(),
    )
    entry = EntryService(accounts=accounts, projects=projects, independent=independent.store, ai=ai.store)
    entry.transaction_coordinator = ai.transactions
    deconstruction = DeconstructionService(
        independent=independent, store=DeconstructionStore(data / "deconstruction")
    )
    independent.deconstruction_service = deconstruction
    entry_routes.account_store = accounts
    entry_routes.entry_service = entry
    independent_routes.independent_service = independent
    ai_routes.ai_service = ai
    deconstruction_routes.deconstruction_service = deconstruction
    print(f"Isolated browser data: {data}", flush=True)
    uvicorn.run(main.app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    run()
