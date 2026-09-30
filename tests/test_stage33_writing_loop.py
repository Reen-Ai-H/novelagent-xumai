"""Source-grounded creation contracts; all model calls use an isolated fake."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from app.agents.llm_runtime import LLMResult, LLMUsage
from app.core.ai_service import AIServiceError, AIStudioService
from app.core.ai_store import AIStore
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore
from app.core.writing_context import (
    build_story_context, CONTEXT_CHARACTER_BUDGET, recent_conversation,
    source_token, writing_checks, CONVERSATION_CHARACTER_BUDGET,
)
from schemas.ai import AIMessage, BlueprintAssistantResponse, WritingPreferences
from schemas.independent import ChapterDocument, ManuscriptVersion
from tests.test_stage18_ai_text_pipeline import Stage18PipelineRuntime, body_text


class ContextContractTest(unittest.TestCase):
    def version(self, count=1):
        now = datetime.now(timezone.utc)
        return ManuscriptVersion(version_id="v1", label="稿本", created_at=now, updated_at=now, chapters=[
            ChapterDocument(chapter_id=f"c{i}", chapter_number=i, title=f"第{i}章", formal_content=f"事实{i}。" * 200,
                            content=f"事实{i}。" * 200, updated_at=now) for i in range(1, count + 1)
        ])

    def test_formal_prior_text_only_and_latest_scene_present(self):
        version = self.version(3)
        version.chapters[1].content = "尚未确认的修改，不是事实"
        version.chapters[2].formal_content = "未来章节不能提前给模型"
        context = build_story_context(version, 3)
        text = json.dumps(context, ensure_ascii=False)
        self.assertIn("事实2", context["previous_scene"])
        self.assertNotIn("尚未确认", text)
        self.assertNotIn("未来章节", text)
        self.assertEqual(context["previous_chapter_count"], 2)

    def test_serialized_budget_and_omission_are_explicit_for_long_book(self):
        version = self.version(100)
        for chapter in version.chapters:
            chapter.formal_content = ('“\\特殊字符”\n' * 3000) + f"结尾{chapter.chapter_number}。"
            chapter.title = "长标题" * 500
        context = build_story_context(version, 101)
        self.assertLessEqual(len(json.dumps(context, ensure_ascii=False)), CONTEXT_CHARACTER_BUDGET)
        self.assertIn("结尾100", context["previous_scene"])
        self.assertGreater(context["omitted_chapter_count"], 0)
        self.assertEqual(context["previous_chapter_count"], 100)

    def test_source_gate_detects_draft_title_revision_and_version_changes(self):
        original = self.version(2)
        token = source_token(original)
        for field, value in [("content", "作者新内容"), ("server_revision", 3), ("title", "改标题")]:
            changed = original.model_copy(deep=True)
            setattr(changed.chapters[0], field, value)
            self.assertNotEqual(source_token(changed), token)
        changed = original.model_copy(deep=True)
        changed.version_id = "v2"
        self.assertNotEqual(source_token(changed), token)

    def test_bounded_conversation_keeps_latest_intent_in_order(self):
        messages = [AIMessage(message_id=str(i), role="author" if i % 2 == 0 else "editor", content=f"第{i}轮" + "补充" * 1500) for i in range(20)]
        history = recent_conversation(messages)
        self.assertLessEqual(sum(len(item["content"]) for item in history), CONVERSATION_CHARACTER_BUDGET)
        self.assertTrue(history[-1]["content"].startswith("第19轮"))
        self.assertTrue(all(item["role"] in {"author", "editor"} for item in history))

    def test_checks_are_exact_repeat_advice_without_score(self):
        paragraph = "林舟把信纸铺在桌面上，逐一核对印章，又将杯子移开，为顾遥留出一把椅子。" * 2
        checks = writing_checks(paragraph + "\n" + paragraph, paragraph)
        self.assertEqual({item.kind for item in checks}, {"repeated_paragraph", "previous_chapter_overlap"})
        self.assertNotIn("score", json.dumps([item.model_dump() for item in checks]))
        self.assertEqual(writing_checks("这是一个新的场景。", paragraph), [])

    def test_relevant_early_chapter_and_story_opening_survive_recent_window(self):
        version = self.version(20)
        version.chapters[3].formal_content = "她发现铜印章留在灯塔上，这件事只有顾遥知道。"
        context = build_story_context(version, 21, "追查铜印章")
        numbers = [item["chapter_number"] for item in context["chapter_excerpts"]]
        self.assertIn(1, numbers)
        self.assertIn(4, numbers)
        self.assertIn(20, numbers)


class LoopRuntime(Stage18PipelineRuntime):
    def __init__(self):
        super().__init__()
        self.blueprint_override = None
        self.on_text = None

    async def structured(self, **kwargs):
        if kwargs["response_model"] is BlueprintAssistantResponse and self.blueprint_override:
            self.calls.append({"stage": "BlueprintAssistantResponse", **kwargs})
            data = {"reply": "我提出一条变更，请作者决定。", "blueprint_patch": self.blueprint_override}
            return LLMResult(call_id=kwargs["call_id"], text=json.dumps(data, ensure_ascii=False), data=data,
                             provider=self.provider, model=self.model, usage=LLMUsage(total_tokens=3))
        return await super().structured(**kwargs)

    async def text(self, **kwargs):
        if self.on_text:
            action, self.on_text = self.on_text, None
            action()
        return await super().text(**kwargs)


class CreationLoopTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        projects = JsonProjectStore(root / "projects")
        manuscript = IndependentWorkspaceService(store=IndependentStore(root / "manuscript"), projects=projects)
        self.runtime = LoopRuntime()
        self.ai = AIStudioService(store=AIStore(root / "ai"), projects=projects, manuscript=manuscript, runtime=self.runtime)
        self.pid, self.owner = "creation-loop", "author"
        self.ws = asyncio.run(self.ai.send_message(self.pid, self.owner, "主角林舟追查一封信。"))

    def tearDown(self):
        self.tmp.cleanup()

    def confirm(self):
        self.ws = self.ai.confirm_blueprint(self.pid, self.owner, self.ws["blueprint_revision"], "confirm")

    def start(self, key, goal=""):
        return asyncio.run(self.ai.start_director(self.pid, self.owner, strategy="pause_at_key_nodes", idempotency_key=key, chapter_goal=goal))

    def choose(self, waiting):
        return asyncio.run(self.ai.choose(self.pid, self.owner, waiting["active_run"]["run_id"], "role"))

    def propose(self):
        self.runtime.blueprint_override = {"world_rules": "海水涨落改变通往山城的道路。"}
        self.ws = asyncio.run(self.ai.send_message(self.pid, self.owner, "改成山城，增加潮汐道路规则。"))
        return self.ws["blueprint_suggestions"][0]

    def test_nonempty_blueprint_update_is_reviewable_and_author_accepts(self):
        old = self.ws["blueprint"].world_rules
        suggestion = self.propose()
        self.assertEqual(self.ws["blueprint"].world_rules, old)
        self.assertEqual(suggestion.before, old)
        resolved = self.ai.resolve_blueprint_suggestion(self.pid, self.owner, suggestion.suggestion_id,
                                                      expected_revision=self.ws["blueprint_revision"], decision="accept")
        self.assertEqual(resolved["blueprint"].world_rules, suggestion.after)
        self.assertIsNone(resolved["confirmed_blueprint_revision"])
        duplicate = self.ai.resolve_blueprint_suggestion(self.pid, self.owner, suggestion.suggestion_id,
                                                       expected_revision=0, decision="accept")
        self.assertEqual(duplicate["blueprint_revision"], resolved["blueprint_revision"])

    def test_later_author_edit_blocks_old_suggestion_even_with_latest_revision(self):
        suggestion = self.propose()
        edited = self.ai.update_blueprint(self.pid, self.owner, {"expected_revision": self.ws["blueprint_revision"], "world_rules": "作者最终设定"})
        with self.assertRaises(AIServiceError) as ctx:
            self.ai.resolve_blueprint_suggestion(self.pid, self.owner, suggestion.suggestion_id,
                                                expected_revision=edited["blueprint_revision"], decision="accept")
        self.assertEqual(ctx.exception.code, "blueprint_conflict")
        self.assertEqual(self.ai.workspace(self.pid, self.owner)["blueprint"].world_rules, "作者最终设定")

    def test_dismiss_and_wrong_owner_do_not_change_blueprint(self):
        suggestion = self.propose()
        with self.assertRaises(AIServiceError):
            self.ai.resolve_blueprint_suggestion(self.pid, "other", suggestion.suggestion_id, expected_revision=0, decision="accept")
        resolved = self.ai.resolve_blueprint_suggestion(self.pid, self.owner, suggestion.suggestion_id, expected_revision=0, decision="dismiss")
        self.assertEqual(resolved["blueprint"].world_rules, suggestion.before)
        self.assertEqual(resolved["blueprint_suggestions"], [])

    def test_editor_second_turn_receives_prior_conversation(self):
        self.propose()
        payload = json.loads(self.runtime.calls[-1]["messages"][-1]["content"])
        self.assertEqual(payload["recent_conversation"][0]["content"], "主角林舟追查一封信。")
        self.assertEqual(payload["author_message"], "改成山城，增加潮汐道路规则。")

    def test_second_chapter_writer_coordinator_reviewer_share_actual_first_body(self):
        self.confirm()
        first = self.choose(self.start("first"))
        first_text = first["active_run"]["generated_content"]
        self.runtime.text_outputs = [body_text(1500).replace("林舟", "顾遥")]
        waiting = self.start("second", "顾遥尝试核对印章，承担一次失败的后果。")
        completed = self.choose(waiting)
        self.assertEqual(completed["active_run"]["chapter_number"], 2)
        body = json.loads(self.runtime.text_calls[-1]["messages"][-1]["content"])
        self.assertEqual(body["chapter_number"], 2)
        self.assertEqual(body["story_context"]["previous_scene"], first_text[-2400:])
        self.assertEqual(body["chapter_goal"], "顾遥尝试核对印章，承担一次失败的后果。")
        for stage in ["DirectorCoordinationResponse", "DirectorReviewResponse", "DirectorArchiveResponse"]:
            call = [item for item in self.runtime.calls if item["stage"] == stage][-1]
            payload = json.loads(call["messages"][-1]["content"])
            self.assertEqual(payload["story_context"], body["story_context"])
        self.assertNotIn("context_token", completed["active_run"])
        self.assertNotIn("generation_epoch", completed["active_run"])

    def test_preferences_are_persistent_and_snapshotted_for_each_run(self):
        self.confirm()
        preferences = WritingPreferences(genre="悬疑", point_of_view="第三人称有限视角", tone="克制", avoid="大段复述")
        self.ai.update_settings(self.pid, self.owner, writing_preferences=preferences)
        waiting = self.start("preferences", "让线索改变计划")
        self.ai.update_settings(self.pid, self.owner, writing_preferences=WritingPreferences(tone="轻快"))
        completed = self.choose(waiting)
        body = json.loads(self.runtime.text_calls[-1]["messages"][-1]["content"])
        self.assertEqual(body["writing_preferences"]["tone"], "克制")
        self.assertEqual(completed["active_run"]["writing_preferences"]["genre"], "悬疑")
        restarted = AIStudioService(store=self.ai.store, projects=self.ai.projects, manuscript=self.ai.manuscript, runtime=LoopRuntime())
        self.assertEqual(restarted.workspace(self.pid, self.owner)["settings"].writing_preferences.tone, "轻快")

    def test_pending_author_change_blocks_generation_and_keeps_text(self):
        self.confirm()
        completed = self.choose(self.start("before-edit"))
        chapter = self.ai.manuscript.workspace(self.pid, self.owner)["active_version"].chapters[0]
        edited = chapter.content + "作者选择了不同的结尾。"
        self.ai.manuscript.save_draft(self.pid, self.owner, chapter.chapter_id, content=edited, title=chapter.title, expected_revision=chapter.server_revision)
        with self.assertRaises(AIServiceError) as ctx:
            self.start("blocked")
        self.assertEqual(ctx.exception.code, "manuscript_change_pending")
        self.assertEqual(self.ai.manuscript.workspace(self.pid, self.owner)["active_version"].chapters[0].content, edited)

    def test_source_change_after_choice_preparation_invalidates_old_choices(self):
        self.confirm()
        waiting = self.start("source-change")
        self.ai.manuscript.add_chapter(self.pid, self.owner)
        failed = self.choose(waiting)
        self.assertEqual(failed["active_run"]["status"], "failed")
        self.assertIn("前文已经修改", failed["active_run"]["error_message"])
        self.assertEqual(len(self.runtime.text_calls), 0)
        retried = asyncio.run(self.ai.retry(self.pid, self.owner, waiting["active_run"]["run_id"]))
        self.assertEqual(retried["active_run"]["status"], "waiting_for_choice")
        coordinators = [item for item in self.runtime.calls if item["stage"] == "DirectorCoordinationResponse"]
        self.assertEqual(len(coordinators), 2)
        self.assertNotEqual(coordinators[0]["call_id"], coordinators[1]["call_id"])

    def test_source_change_during_body_never_commits_generated_text(self):
        self.confirm()
        waiting = self.start("mid-call")
        self.runtime.on_text = lambda: self.ai.manuscript.add_chapter(self.pid, self.owner)
        failed = self.choose(waiting)
        self.assertEqual(failed["active_run"]["status"], "failed")
        self.assertFalse(any(chapter.formal_content for chapter in self.ai.manuscript.workspace(self.pid, self.owner)["active_version"].chapters))

    def test_source_change_after_successful_body_invalidates_cached_text_on_retry(self):
        self.confirm()
        self.runtime.fail_review_once = True
        waiting = self.start("cached-source-change")
        failed = self.choose(waiting)
        self.assertEqual(failed["active_run"]["status"], "failed")
        self.assertEqual(len(self.runtime.text_calls), 1)
        self.ai.manuscript.add_chapter(self.pid, self.owner)
        retried = asyncio.run(self.ai.retry(self.pid, self.owner, waiting["active_run"]["run_id"]))
        completed = self.choose(retried)
        self.assertEqual(completed["active_run"]["status"], "completed")
        self.assertEqual(len(self.runtime.text_calls), 2)
        self.assertNotEqual(self.runtime.text_calls[0]["call_id"], self.runtime.text_calls[1]["call_id"])
        self.assertEqual(sum(bool(chapter.formal_content) for chapter in self.ai.manuscript.workspace(self.pid, self.owner)["active_version"].chapters), 1)

    def test_legacy_record_defaults_and_no_prompt_persistence(self):
        record = self.ai.store.load(self.pid)
        raw = record.model_dump(mode="json")
        raw.pop("blueprint_suggestions")
        raw["settings"].pop("writing_preferences")
        self.ai.store.save(type(record).model_validate(raw))
        self.confirm()
        completed = self.choose(self.start("legacy"))
        self.assertEqual(completed["active_run"]["status"], "completed")
        stored = self.ai.store.load(self.pid).model_dump(mode="json")
        self.assertNotIn('"story_context"', json.dumps(stored))
        self.assertNotIn('"recent_conversation"', json.dumps(stored))
        self.assertTrue(completed["active_run"]["writing_checks"])

    def test_preferences_updated_during_body_call_are_not_lost(self):
        self.confirm()
        waiting = self.start("concurrent-preference")
        self.runtime.on_text = lambda: self.ai.update_settings(self.pid, self.owner, writing_preferences=WritingPreferences(tone="作者的新语气"))
        completed = self.choose(waiting)
        self.assertEqual(completed["active_run"]["status"], "completed")
        self.assertEqual(completed["settings"].writing_preferences.tone, "作者的新语气")
        self.assertEqual(completed["active_run"]["writing_preferences"]["tone"], "")

    def test_blueprint_updated_during_body_call_is_preserved_and_task_stops(self):
        self.confirm()
        waiting = self.start("concurrent-blueprint")
        revision = self.ws["blueprint_revision"]
        self.runtime.on_text = lambda: self.ai.update_blueprint(self.pid, self.owner, {"expected_revision":revision, "world_rules":"作者刚刚修改的新规则"})
        failed = self.choose(waiting)
        self.assertEqual(failed["active_run"]["status"], "failed")
        self.assertEqual(failed["blueprint"].world_rules, "作者刚刚修改的新规则")
        self.assertFalse(any(chapter.formal_content for chapter in self.ai.manuscript.workspace(self.pid, self.owner)["active_version"].chapters))

    def test_unfinished_prior_draft_is_not_ignored_by_new_chapter(self):
        self.confirm()
        chapter = self.ai.manuscript.workspace(self.pid, self.owner)["active_version"].chapters[0]
        self.ai.manuscript.save_draft(self.pid, self.owner, chapter.chapter_id, content="还在写的第一章", title=chapter.title, expected_revision=chapter.server_revision)
        failed = self.start("unfinished")
        self.assertEqual(failed["active_run"]["status"], "failed")
        self.assertIn("未完成", failed["active_run"]["error_message"])
        self.assertEqual(len(self.runtime.text_calls), 0)

class CreationApiTest(unittest.TestCase):
    # Reuse isolated setup helpers without inheriting or duplicating old tests.
    from tests.test_ai_api import AIStudioApiTest as _Fixture
    setUp = _Fixture.setUp
    _cleanup = _Fixture._cleanup
    _project = _Fixture._project
    _ready_blueprint = _Fixture._ready_blueprint

    def suggestion(self):
        self.ai.runtime = LoopRuntime()
        pid = self._project("阶段33 API 合同")
        self._ready_blueprint(pid)
        self.ai.runtime.blueprint_override = {"world_rules": "潮水改变山路。"}
        ws = self._ready_blueprint(pid, "希望更新山路规则")
        return pid, ws, ws["blueprint_suggestions"][0]

    def test_suggestion_endpoint_enforces_owner_and_explicit_confirmation(self):
        from fastapi.testclient import TestClient
        import main
        pid, ws, suggestion = self.suggestion()
        url = f'/api/ai/projects/{pid}/blueprint/suggestions/{suggestion["suggestion_id"]}'
        request = {"expected_revision": ws["blueprint_revision"], "decision": "accept"}
        anonymous = TestClient(main.app)
        self.assertEqual(anonymous.post(url, json=request).status_code, 401)
        anonymous.post('/api/auth/email', json={"email": "another-stage33@example.test"})
        self.assertEqual(anonymous.post(url, json=request).status_code, 404)
        accepted = self.client.post(url, json=request)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["blueprint"]["world_rules"], "潮水改变山路。")
        self.assertIsNone(accepted.json()["confirmed_blueprint_revision"])

    def test_new_author_input_limits_and_mode_gate(self):
        pid = self._project()
        base = f'/api/ai/projects/{pid}'
        self.assertEqual(self.client.put(base + '/settings', json={"writing_preferences": {"tone": "字" * 601}}).status_code, 422)
        self.assertEqual(self.client.put(base + '/settings', json={"writing_preferences": {"private_memory": "no"}}).status_code, 422)
        self.assertEqual(self.client.post(base + '/director/start', json={"chapter_goal": "字" * 1201}).status_code, 422)
        independent = self.client.post('/api/library/projects', json={"title": "独立作品", "mode": "independent"}).json()["project"]["project_id"]
        self.assertEqual(self.client.put(f'/api/ai/projects/{independent}/settings', json={"writing_preferences": {"tone": "安静"}}).status_code, 409)

    def test_api_invalid_decision_and_revision_do_not_accept_suggestion(self):
        pid, ws, suggestion = self.suggestion()
        url = f'/api/ai/projects/{pid}/blueprint/suggestions/{suggestion["suggestion_id"]}'
        self.assertEqual(self.client.post(url, json={"expected_revision":ws["blueprint_revision"],"decision":"overwrite"}).status_code, 422)
        self.assertEqual(self.client.post(url, json={"expected_revision":0,"decision":"accept"}).status_code, 409)
        after = self.client.get(f'/api/ai/projects/{pid}').json()
        self.assertEqual(after["blueprint"]["world_rules"], suggestion["before"])


if __name__ == "__main__":
    unittest.main()
