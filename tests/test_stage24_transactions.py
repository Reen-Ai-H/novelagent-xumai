from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.core.account_store import AccountRecord, AccountStore, ProjectLink
from app.core.ai_service import AIStudioService
from app.core.ai_store import AIStore
from app.core.entry_service import EntryService
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore
from app.models import NovelProject

from tests.test_stage18_ai_text_pipeline import Stage18PipelineRuntime


class Stage24TransactionFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="stage24-")
        self.root = Path(self.tmp.name)
        self.project_id = "stage24-project"
        self.account_id = "stage24-account"
        self.ai, self.manuscript = self._service(self.root)
        asyncio.run(self.ai.send_message(self.project_id, self.account_id, "主角是林舟，顾遥守住一封回信。"))
        workspace = self.ai.workspace(self.project_id, self.account_id)
        self.ai.confirm_blueprint(
            self.project_id,
            self.account_id,
            workspace["blueprint_revision"],
            "stage24-confirm",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _service(self, root: Path, *, project_id: str | None = None) -> tuple[AIStudioService, IndependentWorkspaceService]:
        projects = JsonProjectStore(root / "projects")
        manuscript = IndependentWorkspaceService(
            store=IndependentStore(root / "independent"),
            projects=projects,
        )
        ai = AIStudioService(
            store=AIStore(root / "ai"),
            projects=projects,
            manuscript=manuscript,
            runtime=Stage18PipelineRuntime(),
        )
        return ai, manuscript

    def _waiting(self, ai: AIStudioService | None = None, *, key: str = "stage24-run") -> dict:
        service = ai or self.ai
        return asyncio.run(
            service.start_director(
                self.project_id,
                self.account_id,
                strategy="pause_at_key_nodes",
                idempotency_key=key,
                defer=False,
            )
        )

    def _public_and_raw(self, ai: AIStudioService, manuscript: IndependentWorkspaceService, run_id: str) -> tuple[dict, object, object]:
        public = ai.workspace(self.project_id, self.account_id)
        record = ai.store.load(self.project_id)
        manuscript_record = manuscript.store.load(self.project_id)
        assert record is not None and manuscript_record is not None
        active = next(item for item in manuscript_record.versions if item.version_id == manuscript_record.active_version_id)
        run = next(item for item in record.runs if item.run_id == run_id)
        return public, run, active

    def test_crash_matrix_before_and_after_marker_never_leaks_public_half_product(self) -> None:
        before_marker = (
            "journal_prepare_before",
            "journal_prepared",
            "manuscript_staged",
            "archive_staged",
            "ai_staged",
            "notification_staged",
            "commit_marker_before",
        )
        after_marker = ("commit_marker_after", "projection_partial")
        for index, label in enumerate((*before_marker, *after_marker)):
            with self.subTest(label=label):
                root = self.root / f"matrix-{index}-{label}"
                root.mkdir(parents=True)
                ai, manuscript = self._service(root)
                pid = f"p{index:02d}"
                aid = f"a{index:02d}"
                asyncio.run(ai.send_message(pid, aid, "主角是林舟，顾遥守住一封回信。"))
                draft = ai.workspace(pid, aid)
                ai.confirm_blueprint(pid, aid, draft["blueprint_revision"], f"confirm-{index}")
                waiting = asyncio.run(
                    ai.start_director(
                        pid,
                        aid,
                        strategy="pause_at_key_nodes",
                        idempotency_key=f"run-{index}",
                        defer=False,
                    )
                )
                run_id = waiting["active_run"]["run_id"]
                tripped = {"value": False}

                def fault(phase: str) -> None:
                    if phase == label and not tripped["value"]:
                        tripped["value"] = True
                        raise OSError(f"stage24 fault at {phase}")

                ai.transactions.failure_hook = fault
                result = asyncio.run(ai.choose(pid, aid, run_id, "role"))
                persisted = ai.store.load(pid)
                manuscript_record = manuscript.store.load(pid)
                assert persisted is not None and manuscript_record is not None
                active = next(item for item in manuscript_record.versions if item.version_id == manuscript_record.active_version_id)
                run = next(item for item in persisted.runs if item.run_id == run_id)
                self.assertTrue(tripped["value"])
                if label in before_marker:
                    self.assertEqual(result["active_run"]["status"], "failed")
                    self.assertEqual(run.status, "failed")
                    self.assertFalse(any(chapter.formal_content for chapter in active.chapters))
                    self.assertEqual(active.archive.snapshots, [])
                    self.assertFalse(any(item.kind == "director_completed" for item in persisted.notifications))
                else:
                    # marker 后即使本次投影触发 OSError，API 读路径也只能看到
                    # overlay 后的完整新状态；持久恢复随后会把两边补齐。
                    self.assertEqual(result["active_run"]["status"], "completed")
                    self.assertEqual(run.status, "completed")
                    self.assertTrue(any(chapter.formal_content for chapter in active.chapters))
                    self.assertEqual(len(active.archive.snapshots), 1)
                    self.assertEqual(sum(item.kind == "director_completed" for item in persisted.notifications), 1)

    def test_process_restart_after_marker_and_recovery_again_is_idempotent(self) -> None:
        run = self._waiting(key="stage24-crash-restart")
        run_id = run["active_run"]["run_id"]
        stopped = {"value": False}

        def terminate(phase: str) -> None:
            if phase == "projection_partial" and not stopped["value"]:
                stopped["value"] = True
                raise SystemExit("stage24 simulated process stop")

        self.ai.transactions.failure_hook = terminate
        with self.assertRaises(SystemExit):
            asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))

        restarted, manuscript = self._service(self.root)
        def recovery_stop(phase: str) -> None:
            if phase == "recovery_again":
                raise SystemExit("stage24 recovery interrupted")

        restarted.transactions.failure_hook = recovery_stop
        with self.assertRaises(SystemExit):
            restarted.workspace(self.project_id, self.account_id)
        restarted.transactions.failure_hook = None
        recovered = restarted.workspace(self.project_id, self.account_id)
        self.assertEqual(recovered["active_run"]["status"], "completed")
        self.assertEqual(recovered["active_run"]["choice_source"], "character")
        for _ in range(3):
            restarted.transactions.reconcile_all()
            restarted.workspace(self.project_id, self.account_id)
        record = restarted.store.load(self.project_id)
        independent = manuscript.store.load(self.project_id)
        assert record is not None and independent is not None
        active = next(item for item in independent.versions if item.version_id == independent.active_version_id)
        self.assertEqual(sum(item.selected_choice_id is not None for item in record.runs), 1)
        self.assertEqual(len(active.chapters), 1)
        self.assertEqual(len(active.archive.snapshots), 1)
        self.assertEqual(sum(item.kind == "director_completed" for item in record.notifications), 1)
        self.assertEqual(len(independent.versions), 1)

    def test_marker_visibility_gate_is_required_for_public_consistency(self) -> None:
        run = self._waiting(key="stage24-marker-gate")
        run_id = run["active_run"]["run_id"]
        tripped = {"value": False}

        def fault(phase: str) -> None:
            if phase == "projection_partial":
                tripped["value"] = True
                raise OSError("keep marker projection pending")

        self.ai.transactions.failure_hook = fault
        with patch.object(self.ai.transactions, "apply_ai", side_effect=OSError("AI projection unavailable")):
            with patch.object(self.ai.transactions, "overlay_record", side_effect=lambda record, **_: record):
                public = asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))
                raw_manuscript = self.manuscript.store.load(self.project_id)
                assert raw_manuscript is not None
                active = next(item for item in raw_manuscript.versions if item.version_id == raw_manuscript.active_version_id)
                # 故意移除门禁时能复现旧 P1：稿本已有正式正文而 AI 公共状态仍未完成。
                self.assertNotEqual(public["active_run"]["status"], "completed")
                self.assertTrue(active.chapters[0].formal_content)
        self.assertTrue(tripped["value"])
        self.ai.transactions.failure_hook = None
        repaired = self.ai.workspace(self.project_id, self.account_id)
        self.assertEqual(repaired["active_run"]["status"], "completed")

    def test_library_and_notification_readers_use_the_same_marker_overlay(self) -> None:
        """旁路入口不能在 AI projection 暂时失败时观察另一侧的半状态。"""

        now = datetime.now(timezone.utc)
        self.ai.projects.save_project(
            NovelProject(
                project_id=self.project_id,
                title="阶段24入口一致性",
                created_at=now,
                updated_at=now,
            )
        )
        accounts = AccountStore(self.root / "accounts.json")
        account = AccountRecord(
            account_id=self.account_id,
            email="stage24-entry@example.test",
            created_at=now,
            updated_at=now,
            project_links=[
                ProjectLink(
                    project_id=self.project_id,
                    mode="ai_assisted",
                    created_at=now,
                )
            ],
        )
        entry = EntryService(
            accounts=accounts,
            projects=self.ai.projects,
            independent=IndependentStore(self.root / "independent"),
            ai=AIStore(self.root / "ai"),
        )
        entry.transaction_coordinator = self.ai.transactions
        waiting = self._waiting(key="stage24-entry-overlay")
        run_id = waiting["active_run"]["run_id"]

        def keep_marker_pending(phase: str) -> None:
            if phase == "projection_partial":
                raise OSError("stage24 entry overlay fault")

        self.ai.transactions.failure_hook = keep_marker_pending
        with patch.object(self.ai.transactions, "apply_ai", side_effect=OSError("stage24 AI projection fault")):
            asyncio.run(self.ai.choose(self.project_id, self.account_id, run_id, "role"))
            summaries = entry.library(account)
            sidecar = entry.sidecar_for_link(
                account.project_links[0],
                account.account_id,
            )
        self.assertEqual([(item.chapter_count, item.status) for item in summaries], [(1, "已保存")])
        assert sidecar is not None
        self.assertEqual(sum(item.kind == "director_completed" for item in sidecar.notifications), 1)

    def test_choice_source_distinguishes_author_character_and_worker_recovery(self) -> None:
        ordinary = self._waiting(key="stage24-author-choice")
        ordinary_done = asyncio.run(self.ai.choose(self.project_id, self.account_id, ordinary["active_run"]["run_id"], "trust"))
        self.assertEqual(ordinary_done["active_run"]["choice_source"], "author")

        delegated = self._waiting(key="stage24-character-choice")
        delegated_done = asyncio.run(self.ai.choose(self.project_id, self.account_id, delegated["active_run"]["run_id"], "role"))
        self.assertEqual(delegated_done["active_run"]["choice_source"], "character")
        waiting = self._waiting(key="stage24-worker-choice")
        before = self.ai.store.load(self.project_id)
        assert before is not None
        worker_run = next(item for item in before.runs if item.run_id == waiting["active_run"]["run_id"])
        worker_run.pending_choice_id = "role"
        self.ai.store.save(before)
        asyncio.run(self.ai.process_background_runs_async())
        after = self.ai.workspace(self.project_id, self.account_id)
        self.assertEqual(after["active_run"]["choice_source"], "character")
        persisted = self.ai.store.load(self.project_id)
        assert persisted is not None
        self.assertEqual(next(item for item in persisted.runs if item.run_id == worker_run.run_id).choice_source, "character")
        self.assertEqual(sum(item.kind == "director_completed" for item in persisted.notifications), 3)

    def test_three_fake_runs_have_one_formal_route_each(self) -> None:
        for number in range(1, 4):
            waiting = self._waiting(key=f"stage24-three-{number}")
            completed = asyncio.run(self.ai.choose(self.project_id, self.account_id, waiting["active_run"]["run_id"], "role"))
            self.assertEqual(completed["active_run"]["status"], "completed")
            self.assertEqual(completed["active_run"]["chapter_number"], number)
            self.assertEqual(completed["active_run"]["choice_source"], "character")
        record = self.ai.store.load(self.project_id)
        manuscript = self.manuscript.store.load(self.project_id)
        assert record is not None and manuscript is not None
        active = next(item for item in manuscript.versions if item.version_id == manuscript.active_version_id)
        self.assertEqual([item.chapter_number for item in active.chapters], [1, 2, 3])
        self.assertEqual([item.chapter_number for item in active.archive.snapshots], [1, 2, 3])
        self.assertEqual(sum(item.kind == "director_completed" for item in record.notifications), 3)
        self.assertEqual(sum(item.status == "completed" for item in record.runs), 3)
        self.assertIsNone(manuscript.pending_changes)

    def test_author_revision_change_aborts_system_transaction_without_overwrite(self) -> None:
        waiting = self._waiting(key="stage24-author-revision")
        chapter = self.manuscript.workspace(self.project_id, self.account_id)["active_version"].chapters[0]
        self.manuscript.save_draft(
            self.project_id,
            self.account_id,
            chapter.chapter_id,
            content="作者在事务前留下的正式边界。",
            title=chapter.title,
            expected_revision=chapter.server_revision,
        )
        failed = asyncio.run(self.ai.choose(self.project_id, self.account_id, waiting["active_run"]["run_id"], "role"))
        self.assertEqual(failed["active_run"]["status"], "failed")
        manuscript = self.manuscript.store.load(self.project_id)
        assert manuscript is not None
        active = next(item for item in manuscript.versions if item.version_id == manuscript.active_version_id)
        self.assertEqual(active.chapters[0].formal_content, "")
        self.assertTrue(active.chapters[0].content.startswith("作者在事务前"))
        self.assertEqual(active.archive.snapshots, [])

    def test_transaction_payload_has_no_private_or_raw_provider_fields(self) -> None:
        record = self.ai.store.load(self.project_id)
        assert record is not None
        agents = {agent.name: agent for agent in record.story_characters}
        agents["林舟"].private_memory = ["林舟阶段24私有哨兵"]
        agents["顾遥"].private_memory = ["顾遥阶段24私有哨兵"]
        self.ai.store.save(record)
        waiting = self._waiting(key="stage24-safe-payload")
        asyncio.run(self.ai.choose(self.project_id, self.account_id, waiting["active_run"]["run_id"], "role"))
        journals = self.ai.transactions.store.list_journals()
        self.assertEqual(len(journals), 1)
        payload = self.ai.transactions.store.load_payload(journals[0].transaction_id)
        assert payload is not None
        serialized = json.dumps(payload.model_dump(mode="json"), ensure_ascii=False)
        forbidden_keys = {"private_memory", "own_experiences", "internal_prompt", "authorization", "api_key", "prompt", "completion"}

        def keys(value: object) -> list[str]:
            if isinstance(value, dict):
                return [str(key).lower() for key in value] + [item for child in value.values() for item in keys(child)]
            if isinstance(value, list):
                return [item for child in value for item in keys(child)]
            return []

        self.assertFalse(forbidden_keys.intersection(keys(payload.model_dump(mode="json"))))
        self.assertNotIn("林舟阶段24私有哨兵", serialized)
        self.assertNotIn("顾遥阶段24私有哨兵", serialized)


if __name__ == "__main__":
    unittest.main()
