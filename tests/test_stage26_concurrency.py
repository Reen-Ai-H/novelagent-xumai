from __future__ import annotations

import asyncio
import json
import multiprocessing as mp
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.core.account_store import AccountRecord, AccountStore, ProjectLink
from app.core.ai_service import AIStudioService
from app.core.ai_store import AIStore
from app.core.entry_service import EntryService
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore
from app.models import NovelProject
from app.core.transaction_store import TransactionStore
from schemas.independent import ChapterDocument
from schemas.transaction import TransactionJournal

from tests.test_stage18_ai_text_pipeline import Stage18PipelineRuntime


def _hold_transaction_lock(base_dir: str, ready: object) -> None:
    store = TransactionStore(Path(base_dir))
    with store.project_lock("stage26-lock-project"):
        ready.set()  # type: ignore[attr-defined]
        time.sleep(30)


class Stage26ConcurrencyRedTest(unittest.TestCase):
    """阶段 25 marker-after + 外部作者 revision 的最小红测。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="stage26-red-")
        self.root = Path(self.tmp.name)
        projects = JsonProjectStore(self.root / "projects")
        manuscript = IndependentWorkspaceService(
            store=IndependentStore(self.root / "independent"),
            projects=projects,
        )
        self.ai = AIStudioService(
            store=AIStore(self.root / "ai"),
            projects=projects,
            manuscript=manuscript,
            runtime=Stage18PipelineRuntime(),
        )
        self.manuscript = manuscript
        self.project_id = "stage26-red-project"
        self.account_id = "stage26-red-account"
        asyncio.run(self.ai.send_message(self.project_id, self.account_id, "主角是林舟，顾遥守住一封回信。"))
        draft = self.ai.workspace(self.project_id, self.account_id)
        self.ai.confirm_blueprint(
            self.project_id,
            self.account_id,
            draft["blueprint_revision"],
            "stage26-red-confirm",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _fresh(self, suffix: str) -> tuple[AIStudioService, IndependentWorkspaceService, Path, str, str]:
        root = self.root / suffix
        root.mkdir(parents=True, exist_ok=True)
        projects = JsonProjectStore(root / "projects")
        manuscript = IndependentWorkspaceService(store=IndependentStore(root / "independent"), projects=projects)
        ai = AIStudioService(
            store=AIStore(root / "ai"),
            projects=projects,
            manuscript=manuscript,
            runtime=Stage18PipelineRuntime(),
        )
        project_id = f"stage26-{suffix}-project"
        account_id = f"stage26-{suffix}-account"
        asyncio.run(ai.send_message(project_id, account_id, "主角是林舟，顾遥守住一封回信。"))
        draft = ai.workspace(project_id, account_id)
        ai.confirm_blueprint(project_id, account_id, draft["blueprint_revision"], f"confirm-{suffix}")
        return ai, manuscript, root, project_id, account_id

    def _inject_author_after(self, ai: AIStudioService, manuscript: IndependentWorkspaceService, root: Path, project_id: str, account_id: str, label: str) -> None:
        def hook(phase: str) -> None:
            if phase != label:
                return
            direct = IndependentWorkspaceService(store=IndependentStore(root / "independent"), projects=ai.projects)
            raw = direct.store.load(project_id)
            assert raw is not None and raw.active_version_id
            version = next(item for item in raw.versions if item.version_id == raw.active_version_id)
            chapter = version.chapters[0]
            direct.save_draft(
                project_id,
                account_id,
                chapter.chapter_id,
                content=f"作者在 {label} 后留下的正文。",
                title=chapter.title,
                expected_revision=chapter.server_revision,
            )
            raise SystemExit(f"stage26 crash at {label}")

        ai.transactions.failure_hook = hook

    def test_marker_after_external_author_revision_converges_without_public_error(self) -> None:
        waiting = asyncio.run(
            self.ai.start_director(
                self.project_id,
                self.account_id,
                strategy="pause_at_key_nodes",
                idempotency_key="stage26-red-run",
                defer=False,
            )
        )
        run_id = waiting["active_run"]["run_id"]

        def crash_after_marker(phase: str) -> None:
            if phase != "commit_marker_after":
                return
            # 模拟旧代码/进程外 writer 绕过 API，在 marker 后写出更高 revision。
            raw = self.manuscript.store.load(self.project_id)
            assert raw is not None and raw.active_version_id
            version = next(item for item in raw.versions if item.version_id == raw.active_version_id)
            chapter = version.chapters[0]
            chapter.content = "作者在 marker 后留下的正文，不能被 AI 覆盖。"
            chapter.word_count = len(chapter.content)
            chapter.server_revision += 1
            chapter.updated_at = self.manuscript._now()
            version.updated_at = chapter.updated_at
            raw.updated_at = chapter.updated_at
            self.manuscript.store.save(raw)
            raise SystemExit("stage26 marker-after process stop")

        self.ai.transactions.failure_hook = crash_after_marker
        with self.assertRaises(SystemExit):
            asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))
        self.ai.transactions.failure_hook = None

        restarted = AIStudioService(
            store=AIStore(self.root / "ai"),
            projects=self.ai.projects,
            manuscript=IndependentWorkspaceService(
                store=IndependentStore(self.root / "independent"),
                projects=self.ai.projects,
            ),
            runtime=Stage18PipelineRuntime(),
        )
        for _ in range(3):
            restarted.transactions.reconcile_all()

        # 修复前这里会在 reconcile/overlay 中抛 IndependentServiceError，且 journal
        # 永久停在 committed/projecting；修复后必须是完整成功或作者冲突终态。
        workspace = restarted.workspace(self.project_id, self.account_id)
        editor = restarted.manuscript.workspace(self.project_id, self.account_id)
        journal = restarted.transactions.store.list_journals()[0]
        self.assertIn(journal.state, {"completed", "superseded"})
        self.assertNotEqual(journal.phase, "projecting")
        self.assertIn(workspace["active_run"]["status"], {"completed", "failed"})
        chapter = editor["active_version"].chapters[0]
        self.assertIn("作者在 marker 后", chapter.content)
        self.assertEqual(chapter.formal_content, "")

    def test_author_revision_after_each_projection_boundary_converges(self) -> None:
        for index, label in enumerate(("after_manuscript_projection", "after_archive_projection", "after_ai_projection", "after_notification_projection")):
            with self.subTest(label=label):
                ai, manuscript, root, project_id, account_id = self._fresh(f"boundary-{index}")
                waiting = asyncio.run(ai.start_director(project_id, account_id, strategy="pause_at_key_nodes", idempotency_key=f"run-{index}", defer=False))
                run_id = waiting["active_run"]["run_id"]
                self._inject_author_after(ai, manuscript, root, project_id, account_id, label)
                with self.assertRaises(SystemExit):
                    asyncio.run(ai.choose(project_id, account_id, run_id, "role"))
                ai.transactions.failure_hook = None
                restarted = AIStudioService(
                    store=AIStore(root / "ai"),
                    projects=ai.projects,
                    manuscript=IndependentWorkspaceService(store=IndependentStore(root / "independent"), projects=ai.projects),
                    runtime=Stage18PipelineRuntime(),
                )
                for _ in range(3):
                    restarted.transactions.reconcile_all()
                workspace = restarted.workspace(project_id, account_id)
                editor = restarted.manuscript.workspace(project_id, account_id)
                journal = restarted.transactions.store.list_journals()[0]
                self.assertEqual(journal.state, "superseded")
                self.assertEqual(journal.error_code, "author_revision_conflict")
                self.assertEqual(workspace["active_run"]["status"], "failed")
                chapter = editor["active_version"].chapters[0]
                self.assertEqual(chapter.formal_content, "")
                self.assertIn("作者在", chapter.content)
                self.assertEqual(editor["archive"].snapshots, [])

    def test_conflict_retry_creates_new_transaction_and_preserves_author_revision(self) -> None:
        waiting = asyncio.run(self.ai.start_director(self.project_id, self.account_id, strategy="pause_at_key_nodes", idempotency_key="stage26-retry-run", defer=False))
        old_run_id = waiting["active_run"]["run_id"]

        def conflict(phase: str) -> None:
            if phase != "commit_marker_after":
                return
            direct = IndependentWorkspaceService(store=IndependentStore(self.root / "independent"), projects=self.ai.projects)
            raw = direct.store.load(self.project_id)
            assert raw is not None and raw.active_version_id
            version = next(item for item in raw.versions if item.version_id == raw.active_version_id)
            chapter = version.chapters[0]
            direct.save_draft(self.project_id, self.account_id, chapter.chapter_id, content="作者优先的第一章正文。", title=chapter.title, expected_revision=chapter.server_revision)

        self.ai.transactions.failure_hook = conflict
        failed = asyncio.run(self.ai.choose(self.project_id, self.account_id, old_run_id, "role"))
        self.ai.transactions.failure_hook = None
        self.assertEqual(failed["active_run"]["status"], "failed")
        old_journal = self.ai.transactions.store.list_journals()[0]
        self.assertEqual(old_journal.state, "superseded")
        retried = asyncio.run(self.ai.retry(self.project_id, self.account_id, old_run_id))
        new_run_id = retried["active_run"]["run_id"]
        self.assertNotEqual(new_run_id, old_run_id)
        self.assertEqual(retried["active_run"]["status"], "waiting_for_choice")
        completed = asyncio.run(self.ai.choose(self.project_id, self.account_id, new_run_id, "role"))
        self.assertEqual(completed["active_run"]["status"], "completed")
        record = self.ai.store.load(self.project_id)
        manuscript = self.manuscript.store.load(self.project_id)
        assert record is not None and manuscript is not None and manuscript.active_version_id
        active = next(item for item in manuscript.versions if item.version_id == manuscript.active_version_id)
        self.assertEqual([item.chapter_number for item in active.chapters if item.formal_content], [2])
        self.assertEqual(active.chapters[0].content, "作者优先的第一章正文。")
        self.assertEqual(sum(item.kind == "director_completed" for item in record.notifications), 1)
        self.assertEqual(len(manuscript.versions), 1)
        self.assertEqual(len(self.ai.transactions.store.list_journals()), 2)
        self.assertEqual(sum(item.state == "completed" for item in self.ai.transactions.store.list_journals()), 1)

    def test_marker_after_author_added_same_number_never_creates_parallel_chapter(self) -> None:
        ai, manuscript, root, project_id, account_id = self._fresh("same-number")
        for index in range(1, 4):
            waiting = asyncio.run(
                ai.start_director(
                    project_id,
                    account_id,
                    strategy="pause_at_key_nodes",
                    idempotency_key=f"same-number-run-{index}",
                    defer=False,
                )
            )
            asyncio.run(ai.choose(project_id, account_id, waiting["active_run"]["run_id"], "role"))

        waiting = asyncio.run(
            ai.start_director(
                project_id,
                account_id,
                strategy="pause_at_key_nodes",
                idempotency_key="same-number-conflict",
                defer=False,
            )
        )
        run_id = waiting["active_run"]["run_id"]
        injected = False

        def append_author_chapter_after_marker(phase: str) -> None:
            nonlocal injected
            if phase != "commit_marker_after" or injected:
                return
            injected = True
            raw = manuscript.store.load(project_id)
            assert raw is not None and raw.active_version_id
            version = next(item for item in raw.versions if item.version_id == raw.active_version_id)
            now = manuscript._now()
            version.chapters.append(
                ChapterDocument(
                    chapter_id="same-number-author-chapter",
                    chapter_number=4,
                    title="作者第4章",
                    formal_title="作者第4章",
                    content="作者在 marker 后新增的第4章。",
                    server_revision=1,
                    word_count=16,
                    status="drafting",
                    updated_at=now,
                )
            )
            version.updated_at = now
            raw.updated_at = now
            manuscript.store.save(raw)

        ai.transactions.failure_hook = append_author_chapter_after_marker
        result = asyncio.run(ai.choose(project_id, account_id, run_id, "role"))
        ai.transactions.failure_hook = None
        self.assertEqual(result["active_run"]["status"], "failed")
        record = manuscript.store.load(project_id)
        assert record is not None and record.active_version_id
        active = next(item for item in record.versions if item.version_id == record.active_version_id)
        self.assertEqual([item.chapter_number for item in active.chapters], [1, 2, 3, 4])
        self.assertEqual([item.chapter_number for item in active.chapters if item.formal_content], [1, 2, 3])
        self.assertEqual(active.chapters[-1].content, "作者在 marker 后新增的第4章。")

    def test_repeated_commit_after_completed_never_overwrites_later_author_revision(self) -> None:
        waiting = asyncio.run(
            self.ai.start_director(
                self.project_id,
                self.account_id,
                strategy="pause_at_key_nodes",
                idempotency_key="stage26-completed-repeat",
                defer=False,
            )
        )
        completed = asyncio.run(self.ai.choose(self.project_id, self.account_id, waiting["active_run"]["run_id"], "role"))
        self.assertEqual(completed["active_run"]["status"], "completed")
        journal = next(item for item in self.ai.transactions.store.list_journals() if item.state == "completed")
        chapter = self.manuscript.workspace(self.project_id, self.account_id)["active_version"].chapters[0]
        self.manuscript.save_draft(
            self.project_id,
            self.account_id,
            chapter.chapter_id,
            content="作者在 AI 完成后继续写下的正文。",
            title=chapter.title,
            expected_revision=chapter.server_revision,
        )
        self.ai.transactions.commit(journal.transaction_id)
        preserved = self.manuscript.workspace(self.project_id, self.account_id)["active_version"].chapters[0]
        self.assertEqual(preserved.content, "作者在 AI 完成后继续写下的正文。")
        self.assertTrue(preserved.formal_content)

    def test_attached_author_api_is_serialized_after_marker(self) -> None:
        waiting = asyncio.run(self.ai.start_director(self.project_id, self.account_id, strategy="pause_at_key_nodes", idempotency_key="stage26-serialized", defer=False))
        run_id = waiting["active_run"]["run_id"]
        chapter = self.manuscript.workspace(self.project_id, self.account_id)["active_version"].chapters[0]
        writer_result: dict[str, object] = {}
        started = threading.Event()

        def writer() -> None:
            started.set()
            try:
                self.manuscript.save_draft(self.project_id, self.account_id, chapter.chapter_id, content="并发作者写入", title=chapter.title, expected_revision=chapter.server_revision)
            except Exception as exc:  # expected stale revision after AI transaction wins
                writer_result["error"] = exc

        def after_marker(phase: str) -> None:
            if phase == "commit_marker_after":
                thread = threading.Thread(target=writer, daemon=True)
                thread.start()
                started.wait(1)
                time.sleep(0.03)
                writer_result["thread"] = thread

        self.ai.transactions.failure_hook = after_marker
        completed = asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))
        self.ai.transactions.failure_hook = None
        thread = writer_result.get("thread")
        assert isinstance(thread, threading.Thread)
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(completed["active_run"]["status"], "completed")
        self.assertEqual(getattr(writer_result.get("error"), "code", None), "save_conflict")
        active = self.manuscript.workspace(self.project_id, self.account_id)["active_version"].chapters[0]
        self.assertNotEqual(active.content, "并发作者写入")
        self.assertTrue(active.formal_content)

    def test_cross_process_project_lock_releases_after_process_exit(self) -> None:
        lock_dir = self.root / "lock-store"
        context = mp.get_context("spawn")
        ready = context.Event()
        process = context.Process(target=_hold_transaction_lock, args=(str(lock_dir), ready))
        process.start()
        self.assertTrue(ready.wait(5))
        process.terminate()
        process.join(5)
        store = TransactionStore(lock_dir)
        with store.project_lock("stage26-lock-project"):
            marker = lock_dir / "released.txt"
            marker.write_text("released", encoding="utf-8")
        self.assertEqual(marker.read_text(encoding="utf-8"), "released")

    def test_journal_atomic_fault_preserves_previous_parseable_record(self) -> None:
        store = TransactionStore(self.root / "journal-store")
        journal = TransactionJournal(
            transaction_id="stage26-journal",
            project_id="stage26-project",
            account_id="stage26-account",
            run_id="stage26-run",
            version_id="stage26-version",
            chapter_number=1,
            idempotency_key="stage26-key",
            content_hash="hash",
            expected_ai_run_revision=0,
            expected_manuscript_revision=0,
            payload_hash="payload",
        )
        store.save_journal(journal)
        path = store.base_dir / "stage26-journal.journal.json"
        before = json.loads(path.read_text(encoding="utf-8"))
        original = store._atomic_write

        def fail(*args: object, **kwargs: object) -> None:
            raise OSError("stage26 replace/fsync fault")

        store._atomic_write = fail  # type: ignore[method-assign]
        with self.assertRaises(OSError):
            store.save_journal(journal.model_copy(update={"phase": "projecting"}))
        store._atomic_write = original  # type: ignore[method-assign]
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), before)
        self.assertEqual(store.load_journal("stage26-journal").phase, "prepared")  # type: ignore[union-attr]

    def test_compensation_journal_fault_retries_to_terminal_state(self) -> None:
        waiting = asyncio.run(self.ai.start_director(self.project_id, self.account_id, strategy="pause_at_key_nodes", idempotency_key="stage26-journal-retry", defer=False))
        run_id = waiting["active_run"]["run_id"]

        def author_marker(phase: str) -> None:
            if phase != "commit_marker_after":
                return
            direct = IndependentWorkspaceService(store=IndependentStore(self.root / "independent"), projects=self.ai.projects)
            raw = direct.store.load(self.project_id)
            assert raw is not None and raw.active_version_id
            chapter = next(item for item in raw.versions if item.version_id == raw.active_version_id).chapters[0]
            direct.save_draft(self.project_id, self.account_id, chapter.chapter_id, content="作者优先且 journal 会重试。", title=chapter.title, expected_revision=chapter.server_revision)

        self.ai.transactions.failure_hook = author_marker
        original_save = self.ai.transactions.store.save_journal
        failed_once = {"value": False}

        def fault_once(journal: object) -> None:
            if getattr(journal, "phase", None) == "author_compensating" and not failed_once["value"]:
                failed_once["value"] = True
                raise OSError("stage26 compensation journal fault")
            original_save(journal)  # type: ignore[arg-type]

        self.ai.transactions.store.save_journal = fault_once  # type: ignore[method-assign]
        result = asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))
        self.ai.transactions.failure_hook = None
        self.ai.transactions.store.save_journal = original_save  # type: ignore[method-assign]
        self.assertEqual(result["active_run"]["status"], "failed")
        for _ in range(3):
            self.ai.transactions.reconcile_all()
        journal = self.ai.transactions.store.list_journals()[0]
        self.assertEqual(journal.state, "superseded")
        self.assertEqual(journal.compensation_attempts, 2)
        self.assertEqual(self.ai.workspace(self.project_id, self.account_id)["active_run"]["status"], "failed")

    def test_choose_and_worker_race_submits_once(self) -> None:
        waiting = asyncio.run(self.ai.start_director(self.project_id, self.account_id, strategy="pause_at_key_nodes", idempotency_key="stage26-race", defer=False))
        run_id = waiting["active_run"]["run_id"]
        results: list[object] = []

        def worker() -> None:
            try:
                results.append(asyncio.run(self.ai.process_background_runs_async()))
            except Exception as exc:
                results.append(exc)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        chosen = asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertIn(chosen["active_run"]["status"], {"completed", "failed"})
        self.ai.transactions.reconcile_all()
        record = self.ai.store.load(self.project_id)
        manuscript = self.manuscript.store.load(self.project_id)
        assert record is not None and manuscript is not None and manuscript.active_version_id
        active = next(item for item in manuscript.versions if item.version_id == manuscript.active_version_id)
        self.assertEqual(sum(item.status == "completed" for item in record.runs), 1)
        self.assertEqual(sum(bool(item.formal_content) for item in active.chapters), 1)
        self.assertEqual(sum(item.kind == "director_completed" for item in record.notifications), 1)

    def test_five_public_readers_share_author_conflict_state(self) -> None:
        self.ai.projects.save_project(
            NovelProject(
                project_id=self.project_id,
                title="阶段 26 旁路一致性",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        accounts = AccountStore(self.root / "accounts.json")
        account = AccountRecord(
            account_id=self.account_id,
            email="stage26-readers@example.test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            project_links=[ProjectLink(project_id=self.project_id, mode="ai_assisted", created_at=datetime.now(timezone.utc))],
        )
        entry = EntryService(accounts=accounts, projects=self.ai.projects, independent=self.manuscript.store, ai=self.ai.store)
        entry.transaction_coordinator = self.ai.transactions

        waiting = asyncio.run(self.ai.start_director(self.project_id, self.account_id, strategy="pause_at_key_nodes", idempotency_key="stage26-readers", defer=False))
        run_id = waiting["active_run"]["run_id"]

        def conflict(phase: str) -> None:
            if phase == "commit_marker_after":
                direct = IndependentWorkspaceService(store=IndependentStore(self.root / "independent"), projects=self.ai.projects)
                raw = direct.store.load(self.project_id)
                assert raw is not None and raw.active_version_id
                chapter = next(item for item in raw.versions if item.version_id == raw.active_version_id).chapters[0]
                direct.save_draft(self.project_id, self.account_id, chapter.chapter_id, content="五入口都要看到作者正文。", title=chapter.title, expected_revision=chapter.server_revision)

        self.ai.transactions.failure_hook = conflict
        asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))
        self.ai.transactions.failure_hook = None
        ai_view = self.ai.workspace(self.project_id, self.account_id)
        editor_view = self.manuscript.workspace(self.project_id, self.account_id)
        archive_view = self.manuscript.archive(self.project_id, self.account_id)
        library_view = entry.library(account)
        notification_view = entry.sidecar_for_link(account.project_links[0], self.account_id)
        self.assertEqual(ai_view["active_run"]["status"], "failed")
        self.assertEqual(editor_view["active_version"].chapters[0].formal_content, "")
        self.assertEqual(archive_view["archive"].snapshots, [])
        self.assertEqual(len(library_view), 1)
        assert notification_view is not None
        self.assertFalse(any(item.kind == "director_completed" for item in notification_view.notifications))

    def test_failed_store_projection_recovers_without_half_state(self) -> None:
        waiting = asyncio.run(self.ai.start_director(self.project_id, self.account_id, strategy="pause_at_key_nodes", idempotency_key="stage26-store-fault", defer=False))
        run_id = waiting["active_run"]["run_id"]
        original_save = self.manuscript.store.save
        raised = {"value": False}

        def fail_once(record: object) -> object:
            if not raised["value"]:
                raised["value"] = True
                raise OSError("stage26 manuscript store fault")
            return original_save(record)  # type: ignore[arg-type]

        self.manuscript.store.save = fail_once  # type: ignore[method-assign]
        chosen = asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))
        self.manuscript.store.save = original_save  # type: ignore[method-assign]
        self.assertIn(chosen["active_run"]["status"], {"completed", "failed"})
        for _ in range(3):
            self.ai.transactions.reconcile_all()
        workspace = self.ai.workspace(self.project_id, self.account_id)
        editor = self.manuscript.workspace(self.project_id, self.account_id)
        self.assertEqual(workspace["active_run"]["status"], "completed")
        self.assertTrue(editor["active_version"].chapters[0].formal_content)


if __name__ == "__main__":
    unittest.main()
