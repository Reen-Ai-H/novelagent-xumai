from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from app import ai_routes, entry_routes, independent_routes
from app.agents.llm_runtime import LLMRuntime, LLMRuntimeSettings
from app.core.account_store import AccountStore
from app.core.ai_service import AIStudioService
from app.core.ai_store import AIStore
from app.core.entry_service import EntryService
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore


class AIStudioApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        accounts = AccountStore(root / "accounts.json")
        projects = JsonProjectStore(root / "projects")
        independent = IndependentWorkspaceService(
            store=IndependentStore(root / "independent"),
            projects=projects,
        )
        service = EntryService(
            accounts=accounts,
            projects=projects,
            independent=independent.store,
            ai=AIStore(root / "ai"),
        )
        ai = AIStudioService(
            store=AIStore(root / "ai"),
            projects=projects,
            manuscript=independent,
            runtime=LLMRuntime(LLMRuntimeSettings()),
        )
        self.ai = ai
        self.patches = [
            patch.object(entry_routes, "account_store", accounts),
            patch.object(entry_routes, "entry_service", service),
            patch.object(independent_routes, "independent_service", independent),
            patch.object(ai_routes, "ai_service", ai),
        ]
        for patcher in self.patches:
            patcher.start()
        self.addCleanup(self._cleanup)
        self.client = TestClient(main.app)
        login = self.client.post("/api/auth/email", json={"email": "ai-stage3@example.com"})
        self.assertEqual(login.status_code, 200)

    def _cleanup(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def _project(self, title: str = "雾港档案") -> str:
        response = self.client.post(
            "/api/library/projects",
            json={"title": title, "mode": "ai_assisted", "brief": "一座被雾封存的城市。"},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["project"]["project_id"]

    def _ready_blueprint(self, project_id: str, content: str = "我想写一座被雾封存的城市，主角是林舟。") -> dict:
        response = self.client.post(
            f"/api/ai/projects/{project_id}/messages",
            json={"content": content},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _confirm(self, project_id: str, workspace: dict) -> dict:
        response = self.client.post(
            f"/api/ai/projects/{project_id}/blueprint/confirm",
            json={
                "expected_revision": workspace["blueprint_revision"],
                "idempotency_key": f"confirm-{project_id}",
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_blueprint_persists_direct_edit_and_confirmation_is_idempotent(self) -> None:
        project_id = self._project()
        empty = self.client.get(f"/api/ai/projects/{project_id}").json()
        self.assertFalse(empty["can_confirm"])
        workspace = self._ready_blueprint(project_id)
        self.assertTrue(workspace["can_confirm"])
        revision = workspace["blueprint_revision"]

        edited = self.client.put(
            f"/api/ai/projects/{project_id}/blueprint",
            json={"expected_revision": revision, "ending_direction": "公开真相，但保留一处余波。"},
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["blueprint"]["ending_direction"], "公开真相，但保留一处余波。")
        self.assertGreater(edited.json()["blueprint_revision"], revision)

        confirmed = self._confirm(project_id, edited.json())
        duplicate = self.client.post(
            f"/api/ai/projects/{project_id}/blueprint/confirm",
            json={
                "expected_revision": edited.json()["blueprint_revision"],
                "idempotency_key": f"confirm-{project_id}",
            },
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json()["confirmed_blueprint_revision"], confirmed["confirmed_blueprint_revision"])
        self.assertTrue(duplicate.json()["manuscript"]["initialized"])

        fresh = TestClient(main.app)
        fresh.post("/api/auth/email", json={"email": "ai-stage3@example.com"})
        recovered = fresh.get(f"/api/ai/projects/{project_id}")
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.json()["messages"][0]["content"], "我想写一座被雾封存的城市，主角是林舟。")
        self.assertEqual(recovered.json()["stage"], "director_ready")

    def test_director_choice_context_isolation_consequence_gate_and_credit_idempotency(self) -> None:
        project_id = self._project("导演台验收")
        workspace = self._ready_blueprint(project_id)
        workspace = self._confirm(project_id, workspace)
        started = self.client.post(
            f"/api/ai/projects/{project_id}/director/start",
            json={"strategy": "pause_at_key_nodes", "idempotency_key": "run-once"},
        )
        self.assertEqual(started.status_code, 200)
        waiting = started.json()["active_run"]
        self.assertEqual(waiting["status"], "waiting_for_choice")
        self.assertEqual(len(waiting["choices"]), 3)
        self.assertNotIn("possible_consequence", waiting["choices"][0])

        duplicate_start = self.client.post(
            f"/api/ai/projects/{project_id}/director/start",
            json={"strategy": "pause_at_key_nodes", "idempotency_key": "run-once"},
        )
        self.assertEqual(duplicate_start.status_code, 200)
        self.assertEqual(duplicate_start.json()["active_run"]["run_id"], waiting["run_id"])

        contexts = self.client.get(
            f"/api/ai/projects/{project_id}/director/runs/{waiting['run_id']}/contexts"
        )
        self.assertEqual(contexts.status_code, 200)
        context_items = contexts.json()["contexts"]
        self.assertEqual(len(context_items), 4)
        self.assertTrue(all("private_memory" not in item for item in context_items))
        self.assertNotIn("private_memory", contexts.text)

        revealed = self.client.put(
            f"/api/ai/projects/{project_id}/settings",
            json={"reveal_consequences": True},
        )
        self.assertEqual(revealed.status_code, 200)
        revealed_payload = revealed.json()
        self.assertIn("possible_consequence", revealed_payload["active_run"]["choices"][0])
        hidden_again = self.client.put(
            f"/api/ai/projects/{project_id}/settings",
            json={"reveal_consequences": False},
        )
        hidden_payload = hidden_again.json()
        self.assertNotIn("possible_consequence", hidden_payload["active_run"]["choices"][0])

        chosen = self.client.post(
            f"/api/ai/projects/{project_id}/director/runs/{waiting['run_id']}/choice",
            json={"choice_id": "hand-to-role"},
        )
        self.assertEqual(chosen.status_code, 200)
        self.assertEqual(chosen.json()["active_run"]["status"], "completed")
        self.assertEqual(chosen.json()["active_run"]["used_credits"], 0)
        self.assertEqual(len(self.ai.store.load(project_id).credit_ledger), 1)

        duplicate_choice = self.client.post(
            f"/api/ai/projects/{project_id}/director/runs/{waiting['run_id']}/choice",
            json={"choice_id": "hand-to-role"},
        )
        self.assertEqual(duplicate_choice.status_code, 200)
        self.assertEqual(duplicate_choice.json()["credits_used"], 0)
        self.assertEqual(len(self.ai.store.load(project_id).credit_ledger), 1)

    def test_director_failure_retry_and_ai_editor_reuses_pending_changes(self) -> None:
        project_id = self._project("导演台重试")
        workspace = self._ready_blueprint(project_id, "这轮演示需要先修正蓝图，主角是林舟。")
        marked = self.client.put(
            f"/api/ai/projects/{project_id}/blueprint",
            json={
                "expected_revision": workspace["blueprint_revision"],
                "core_premise": "[[ai-fail]] 这轮演示应该失败，主角是林舟。",
            },
        )
        self.assertEqual(marked.status_code, 200)
        workspace = marked.json()
        workspace = self._confirm(project_id, workspace)
        failed = self.client.post(
            f"/api/ai/projects/{project_id}/director/start",
            json={"strategy": "full_auto", "idempotency_key": "failure-once"},
        )
        self.assertEqual(failed.status_code, 200)
        run = failed.json()["active_run"]
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["used_credits"], 0)

        fixed = self.client.put(
            f"/api/ai/projects/{project_id}/blueprint",
            json={"expected_revision": workspace["blueprint_revision"], "core_premise": "一座被雾封存的城市，主角是林舟。"},
        )
        self.assertEqual(fixed.status_code, 200)
        retried = self.client.post(
            f"/api/ai/projects/{project_id}/director/runs/{run['run_id']}/retry"
        )
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(retried.json()["active_run"]["status"], "completed")
        self.assertEqual(retried.json()["credits_used"], 0)

        manuscript = self.client.get(f"/api/independent/projects/{project_id}")
        self.assertEqual(manuscript.status_code, 200)
        chapter = manuscript.json()["active_version"]["chapters"][0]
        edited = self.client.put(
            f"/api/independent/projects/{project_id}/chapters/{chapter['chapter_id']}/draft",
            json={
                "content": chapter["content"] + "\n作者补了一句。",
                "expected_revision": chapter["server_revision"],
            },
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(len(edited.json()["workspace"]["pending_changes"]["changes"]), 1)
        ignored = self.client.post(
            f"/api/independent/projects/{project_id}/pending-changes/resolve",
            json={"decision": "ignore"},
        )
        self.assertEqual(ignored.status_code, 200)
        self.assertIsNone(ignored.json()["workspace"]["pending_changes"])

        archive = self.client.get(f"/api/archive/projects/{project_id}")
        self.assertEqual(archive.status_code, 200)
        self.assertEqual(archive.json()["mode"], "ai_assisted")
        self.assertTrue(archive.json()["archive"]["characters"])

    def test_story_character_agents_are_dynamic_and_bidirectionally_private(self) -> None:
        project_id = self._project("双层角色隔离")
        workspace = self._confirm(project_id, self._ready_blueprint(project_id))
        started = self.client.post(
            f"/api/ai/projects/{project_id}/director/start",
            json={"strategy": "pause_at_key_nodes", "idempotency_key": "layers-once"},
        )
        self.assertEqual(started.status_code, 200)
        run = started.json()["active_run"]
        public_characters = started.json()["story_characters"]
        self.assertEqual({item["name"] for item in public_characters}, {"林舟", "顾遥"})
        self.assertTrue(all("private_memory" not in item for item in public_characters))
        self.assertIn("editor", {item["role_id"] for item in started.json()["role_statuses"]})

        record = self.ai.store.load(project_id)
        self.assertIsNotNone(record)
        assert record is not None
        by_name = {item.name: item for item in record.story_characters}
        by_name["林舟"].private_memory = ["林舟私有哨兵：潮汐钥匙"]
        by_name["顾遥"].private_memory = ["顾遥私有哨兵：白色回声"]
        self.ai.store.save(record)

        contexts = self.client.get(
            f"/api/ai/projects/{project_id}/director/runs/{run['run_id']}/character-contexts"
        )
        self.assertEqual(contexts.status_code, 200)
        items = contexts.json()["contexts"]
        self.assertEqual({item["name"] for item in items}, {"林舟", "顾遥"})
        by_context_name = {item["name"]: item for item in items}
        self.assertTrue(all("private_memory" not in item for item in items))
        self.assertNotIn("潮汐钥匙", contexts.text)
        self.assertNotIn("白色回声", contexts.text)
        self.assertTrue(all(item["entity_layer"] == "story_character" for item in items))
        self.assertEqual(by_context_name["林舟"]["shared_world_rules"], by_context_name["顾遥"]["shared_world_rules"])
        internal = self.ai.story_character_contexts(project_id, record.account_id, run["run_id"])
        internal_by_name = {item.name: item for item in internal}
        self.assertIn("林舟私有哨兵：潮汐钥匙", internal_by_name["林舟"].private_memory)
        self.assertNotIn("顾遥私有哨兵：白色回声", internal_by_name["林舟"].private_memory)
        self.assertIn("顾遥私有哨兵：白色回声", internal_by_name["顾遥"].private_memory)
        self.assertNotIn("林舟私有哨兵：潮汐钥匙", internal_by_name["顾遥"].private_memory)

        professional = self.client.get(
            f"/api/ai/projects/{project_id}/director/runs/{run['run_id']}/contexts"
        )
        self.assertEqual(professional.status_code, 200)
        self.assertTrue(all(item["entity_layer"] == "professional" for item in professional.json()["contexts"]))
        self.assertNotIn("潮汐钥匙", professional.text)
        self.assertNotIn("白色回声", professional.text)

    def test_deferred_director_state_machine_strategy_and_single_route(self) -> None:
        project_id = self._project("后台轮转状态")
        workspace = self._confirm(project_id, self._ready_blueprint(project_id))
        started = self.client.post(
            f"/api/ai/projects/{project_id}/director/start",
            json={"strategy": "pause_at_key_nodes", "defer": True, "idempotency_key": "deferred-once"},
        )
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["active_run"]["status"], "character_simulation")
        self.assertEqual(started.json()["settings"]["strategy"], "pause_at_key_nodes")
        self.assertTrue(all(item["state"] == "分析中" for item in started.json()["role_statuses"]))

        waiting = self.client.post(
            f"/api/ai/projects/{project_id}/director/runs/{started.json()['active_run']['run_id']}/advance"
        )
        self.assertEqual(waiting.status_code, 200)
        waiting_run = waiting.json()["active_run"]
        self.assertEqual(waiting_run["status"], "waiting_for_choice")
        self.assertEqual(len(waiting_run["choices"]), 3)
        self.assertTrue(all(choice.get("character_id") for choice in waiting_run["choices"]))

        chosen = self.client.post(
            f"/api/ai/projects/{project_id}/director/runs/{waiting_run['run_id']}/choice",
            json={"choice_id": "hand-to-role"},
        )
        self.assertEqual(chosen.status_code, 200)
        completed = chosen.json()["active_run"]
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["choice_source"], "character")
        self.assertEqual(
            completed["stage_history"],
            ["角色推演", "等待关键节点选择", "正文生成", "审校", "更新档案", "完成"],
        )
        self.assertEqual(chosen.json()["credits_used"], 0)
        duplicate = self.client.post(
            f"/api/ai/projects/{project_id}/director/runs/{waiting_run['run_id']}/choice",
            json={"choice_id": "hand-to-role"},
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(len(self.ai.store.load(project_id).credit_ledger), 1)

    def test_full_auto_deferred_run_completes_and_retry_credit_is_idempotent(self) -> None:
        project_id = self._project("全自动状态")
        workspace = self._confirm(project_id, self._ready_blueprint(project_id))
        started = self.client.post(
            f"/api/ai/projects/{project_id}/director/start",
            json={"strategy": "full_auto", "defer": True, "idempotency_key": "auto-once"},
        )
        self.assertEqual(started.status_code, 200)
        run_id = started.json()["active_run"]["run_id"]
        self.assertEqual(started.json()["settings"]["strategy"], "full_auto")
        completed = self.client.post(f"/api/ai/projects/{project_id}/director/runs/{run_id}/advance")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["active_run"]["status"], "completed")
        self.assertEqual(completed.json()["credits_used"], 0)
        repeated = self.client.post(f"/api/ai/projects/{project_id}/director/runs/{run_id}/advance")
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json()["credits_used"], 0)
        self.assertEqual(len(self.ai.store.load(project_id).credit_ledger), 1)

    def test_spoiler_is_absent_from_default_response_and_archive_is_latest_or_read_only(self) -> None:
        project_id = self._project("剧透门控")
        workspace = self._confirm(project_id, self._ready_blueprint(project_id))
        started = self.client.post(
            f"/api/ai/projects/{project_id}/director/start",
            json={"strategy": "pause_at_key_nodes", "idempotency_key": "spoiler-once"},
        )
        self.assertEqual(started.status_code, 200)
        payload_text = started.text
        self.assertNotIn("possible_consequence", payload_text)
        self.assertNotIn("节奏会更克制", payload_text)
        revealed = self.client.put(
            f"/api/ai/projects/{project_id}/settings",
            json={"reveal_consequences": True},
        )
        self.assertIn("possible_consequence", revealed.text)
        hidden = self.client.put(
            f"/api/ai/projects/{project_id}/settings",
            json={"reveal_consequences": False},
        )
        self.assertNotIn("possible_consequence", hidden.text)
        archive = self.client.get(f"/api/archive/projects/{project_id}")
        self.assertEqual(archive.status_code, 200)
        self.assertFalse(archive.json()["read_only"])
        self.assertIn("latest_chapter_number", archive.json()["archive"])


if __name__ == "__main__":
    unittest.main()
