import asyncio
import copy
import json
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.agents.llm_runtime import LLMUsage
from app.core.analysis_delta import compact_index, merge_delta
from app.core.analysis_grounding import GroundedDelta, source_id
from app.core.book_analysis import BookAnalysis
from app.core.model_budget import BudgetLedger, pricing_for_model
from schemas.analysis_delta import AnalysisDelta, RelationKey
from test_stage32_analysis_import import AnalysisImportTest, selector_report


def first_delta(report):
    return {
        "new_evidence": selector_report(report)["evidence"], "new_findings": report["findings"],
        "new_characters": report["characters"], "new_events": report["events"],
        "story_order": report["story_order"], "time_note": report["time_note"],
    }


class Stage34DeltaTest(unittest.TestCase):
    def setUp(self):
        self.claim = {"text": "她暂时没有开门。", "status": "fact", "evidence_ids": ["q"]}
        self.seed = {
            "new_evidence": [{"id": "q", "chapter_number": 1, "quote": "沈禾没有开门。"}],
            "new_findings": [{"id": "f", "title": "未开门", **self.claim}],
            "new_characters": [{"id": "c", "name": "沈禾", "role": "主角",
                                "identity": self.claim, "motivation": self.claim, "change": self.claim}],
            "new_events": [{"id": "e", "title": "门前犹豫", "chapter_number": 1,
                            "story_time": "当下", "actor_ids": ["c"],
                            "action": self.claim, "consequence": self.claim}],
            "story_order": ["e"],
        }

    def test_new_and_revision_merge_to_stable_objects(self):
        draft, first = merge_delta(None, AnalysisDelta.model_validate(self.seed),
                                   chapters=[1], read_text={1: "沈禾没有开门。"},
                                   producer="fake", scope="已读一章")
        self.assertIsNotNone(first)
        self.assertEqual([x.id for x in first.characters], ["C1"])
        self.assertEqual(first.events[0].actor_ids, ["C1"])
        self.assertEqual(first.findings[0].evidence_ids, ["Q1"])
        self.assertEqual(compact_index(draft)["characters"][0]["id"], "C1")
        revised = first.characters[0].model_dump(mode="json")
        revised["change"] = {"text": "后来主动开门。", "status": "fact", "evidence_ids": ["later"]}
        change = AnalysisDelta.model_validate({
            "new_evidence": [{"id": "later", "chapter_number": 2, "quote": "沈禾终于开门。"}],
            "revised_characters": [revised],
        })
        merged, report = merge_delta(draft, change, chapters=[1, 2],
                                     read_text={1: "沈禾没有开门。", 2: "沈禾终于开门。"},
                                     producer="fake", scope="两章")
        self.assertEqual(len(report.characters), 1)
        self.assertEqual(report.characters[0].id, "C1")
        self.assertEqual(report.characters[0].change.evidence_ids, ["Q2"])
        self.assertEqual([x.id for x in report.evidence], ["Q1", "Q2"])
        self.assertEqual(merged["chapter_numbers"], [1, 2])

    def test_multiple_new_objects_per_group_have_complete_shapes(self):
        second_claim = {"text": "陆川接过钥匙。", "status": "fact", "evidence_ids": ["q2"]}
        change = copy.deepcopy(self.seed)
        change["new_evidence"].append({"id": "q2", "chapter_number": 1,
                                       "quote": "陆川接过钥匙。"})
        change["new_findings"].append({"id": "f2", "title": "钥匙交接", **second_claim})
        change["new_characters"].append({"id": "c2", "name": "陆川", "role": "接钥匙的人",
                                         "identity": second_claim, "motivation": second_claim,
                                         "change": second_claim})
        change["new_events"].append({"id": "e2", "title": "交接钥匙", "chapter_number": 1,
                                      "story_time": "稍后", "actor_ids": ["c2"],
                                      "action": second_claim, "consequence": second_claim})
        change["story_order"] = ["e", "e2"]
        draft, report = merge_delta(None, AnalysisDelta.model_validate(change), chapters=[1],
                                    read_text={1: "沈禾没有开门。陆川接过钥匙。"},
                                    producer="fake", scope="第一章")
        self.assertEqual([x.id for x in report.evidence], ["Q1", "Q2"])
        self.assertEqual([x.id for x in report.findings], ["F1", "F2"])
        self.assertEqual([x.id for x in report.characters], ["C1", "C2"])
        self.assertEqual([x.id for x in report.events], ["E1", "E2"])
        self.assertEqual(report.events[1].actor_ids, ["C2"])
        self.assertEqual(report.events[1].action.evidence_ids, ["Q2"])
        self.assertEqual(draft["story_order"], ["E1", "E2"])

    def test_unread_quote_and_dangling_revision_are_rejected(self):
        with self.assertRaises(ValueError):
            merge_delta(None, AnalysisDelta.model_validate(self.seed), chapters=[1],
                        read_text={1: "另一段正文。"}, producer="fake", scope="一章")
        draft, _ = merge_delta(None, AnalysisDelta.model_validate(self.seed), chapters=[1],
                               read_text={1: "沈禾没有开门。"}, producer="fake", scope="一章")
        bad = copy.deepcopy(draft["characters"][0])
        bad["id"] = "C999"
        with self.assertRaises(ValueError):
            merge_delta(draft, AnalysisDelta.model_validate({"revised_characters": [bad]}),
                        chapters=[1], read_text={1: "沈禾没有开门。"},
                        producer="fake", scope="一章")

    def test_incomplete_drafts_still_enforce_scope_and_references(self):
        for name, change, chapters, text in [
            ("future evidence", {"new_evidence": [{"id": "q", "chapter_number": 2,
                                                    "quote": "第二章证据。"}]}, [1],
             {1: "第一章正文。", 2: "第二章证据。"}),
            ("future event", {"new_events": [{**self.seed["new_events"][0],
                                               "chapter_number": 2, "actor_ids": []}]}, [1],
             {1: "沈禾没有开门。"}),
            ("unknown evidence", {"new_findings": self.seed["new_findings"]}, [1],
             {1: "沈禾没有开门。"}),
            ("unknown actor", {"new_evidence": self.seed["new_evidence"],
                                "new_events": self.seed["new_events"]}, [1],
             {1: "沈禾没有开门。"}),
            ("future end", {"new_evidence": self.seed["new_evidence"],
                              "new_events": [{**self.seed["new_events"][0], "actor_ids": [],
                                              "chapter_end": 2}]}, [1], {1: "沈禾没有开门。"}),
            ("huge future end", {"new_evidence": self.seed["new_evidence"],
                                   "new_events": [{**self.seed["new_events"][0], "actor_ids": [],
                                                   "chapter_end": 1_000_000_000}]}, [1],
             {1: "沈禾没有开门。"}),
            ("noncontiguous", {}, [1, 3], {1: "第一章。", 3: "第三章。"}),
            ("duplicate quote", {"new_evidence": self.seed["new_evidence"]}, [1],
             {1: "沈禾没有开门。沈禾没有开门。"}),
        ]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                merge_delta(None, AnalysisDelta.model_validate(change), chapters=chapters,
                            read_text=text, producer="fake", scope="未完成草稿")
        draft, report = merge_delta(None, AnalysisDelta.model_validate({
            "new_evidence": self.seed["new_evidence"]}), chapters=[1],
            read_text={1: "沈禾没有开门。"}, producer="fake", scope="未完成草稿")
        self.assertIsNone(report)
        self.assertEqual(draft["evidence"][0]["chapter_number"], 1)

    def test_existing_scope_cannot_shrink_and_failed_merge_is_atomic(self):
        draft, _ = merge_delta(None, AnalysisDelta.model_validate(self.seed), chapters=[1, 2],
                               read_text={1: "沈禾没有开门。", 2: "第二章正文。"},
                               producer="fake", scope="两章")
        before = copy.deepcopy(draft)
        with self.assertRaises(ValueError):
            merge_delta(draft, AnalysisDelta(), chapters=[1], read_text={1: "沈禾没有开门。"},
                        producer="fake", scope="一章")
        with self.assertRaises(ValueError):
            merge_delta(draft, AnalysisDelta(withdrawn_ids=["Q1"]), chapters=[1, 2],
                        read_text={1: "沈禾没有开门。", 2: "第二章正文。"},
                        producer="fake", scope="两章")
        self.assertEqual(draft, before)

    def _relation_draft(self):
        seed = copy.deepcopy(self.seed)
        seed["new_events"].extend([
            {**copy.deepcopy(seed["new_events"][0]), "id": "later", "title": "交接钥匙"},
            {**copy.deepcopy(seed["new_events"][0]), "id": "last", "title": "再次相遇"},
        ])
        seed["story_order"] = ["e", "later", "last"]
        seed["new_relations"] = [
            {**self.claim, "from_id": "later", "to_id": "e", "kind": "follows",
             "text": "交接钥匙跟随门前犹豫。"},
            {**self.claim, "from_id": "later", "to_id": "e", "kind": "enables"},
            {**self.claim, "from_id": "later", "to_id": "last", "kind": "follows"},
        ]
        draft, _ = merge_delta(None, AnalysisDelta.model_validate(seed), chapters=[1],
                               read_text={1: "沈禾没有开门。"}, producer="fake", scope="第一章")
        return draft

    def test_relation_direction_is_correctable_without_removing_unrelated_edges(self):
        draft = self._relation_draft()
        before = copy.deepcopy(draft)
        key = {"from_id": "E2", "to_id": "E1", "kind": "follows"}
        self.assertIn(key, compact_index(draft)["relations"])
        correction = AnalysisDelta.model_validate({
            "withdrawn_relations": [key],
            "new_relations": [{"from_id": "E1", "to_id": "E2", "kind": "follows",
                               "text": "交接钥匙跟随门前犹豫。", "status": "inferred",
                               "evidence_ids": ["Q1"]}],
        })
        merged, report = merge_delta(draft, correction, chapters=[1], read_text={1: "沈禾没有开门。"},
                                     producer="fake", scope="更正方向", final=True)
        self.assertEqual([(edge.from_id, edge.to_id, edge.kind) for edge in report.relations],
                         [("E2", "E1", "enables"), ("E2", "E3", "follows"), ("E1", "E2", "follows")])
        self.assertEqual(merged["relations"][:2], before["relations"][1:])
        for group in ("events", "characters", "evidence", "story_order"):
            self.assertEqual(merged[group], before[group])
        self.assertEqual(draft, before)

    def test_relation_withdrawals_are_exact_existing_unique_keys(self):
        draft = self._relation_draft()
        before = copy.deepcopy(draft)
        existing = {"from_id": "E2", "to_id": "E1", "kind": "follows"}
        absent = {"from_id": "E1", "to_id": "E2", "kind": "follows"}
        for keys in ([absent], [{**existing, "kind": "causes"}],
                     [{**existing, "from_id": "E999"}], [existing, existing]):
            with self.subTest(keys=keys), self.assertRaises(ValueError):
                merge_delta(draft, AnalysisDelta.model_validate({"withdrawn_relations": keys}),
                            chapters=[1], read_text={1: "沈禾没有开门。"}, producer="fake", scope="撤回")
        with self.assertRaises(ValueError):
            merge_delta(draft, AnalysisDelta.model_validate({
                "withdrawn_relations": [absent],
                "new_relations": [{**absent, "text": "新增不算已有撤回目标", "status": "inferred",
                                   "evidence_ids": ["Q1"]}],
            }), chapters=[1], read_text={1: "沈禾没有开门。"}, producer="fake", scope="撤回")
        merged, report = merge_delta(draft, AnalysisDelta.model_validate({"withdrawn_relations": [existing]}),
                                     chapters=[1], read_text={1: "沈禾没有开门。"}, producer="fake", scope="撤回")
        self.assertEqual(len(report.relations), 2)
        self.assertEqual(merged["relations"], before["relations"][1:])
        with self.assertRaises(ValueError):
            merge_delta(merged, AnalysisDelta.model_validate({"withdrawn_relations": [existing]}),
                        chapters=[1], read_text={1: "沈禾没有开门。"}, producer="fake", scope="重复撤回")
        self.assertEqual(draft, before)

    def test_relation_correction_still_validates_endpoints_and_evidence(self):
        draft = self._relation_draft()
        before = copy.deepcopy(draft)
        old = {"from_id": "E2", "to_id": "E1", "kind": "follows"}
        base = {"from_id": "E1", "to_id": "E2", "kind": "follows",
                "text": "交接钥匙跟随门前犹豫。", "status": "inferred", "evidence_ids": ["Q1"]}
        for edge in ({**base, "to_id": "E999"}, {**base, "evidence_ids": ["Q999"]}):
            with self.subTest(edge=edge), self.assertRaises(ValueError):
                merge_delta(draft, AnalysisDelta.model_validate({"withdrawn_relations": [old],
                                                                 "new_relations": [edge]}),
                            chapters=[1], read_text={1: "沈禾没有开门。"}, producer="fake", scope="更正")
            self.assertEqual(draft, before)

    def test_relation_key_contract_is_strict_and_old_deltas_remain_valid(self):
        self.assertEqual(AnalysisDelta().withdrawn_relations, [])
        key = {"from_id": "E2", "to_id": "E1", "kind": "follows"}
        self.assertEqual(RelationKey.model_validate(key).model_dump(), key)
        for invalid in ({**key, "kind": "unknown"}, {**key, "from_id": "中文ID"}, {**key, "id": "R1"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                RelationKey.model_validate(invalid)


class Stage34RunnerTest(unittest.IsolatedAsyncioTestCase):
    setUp = AnalysisImportTest.setUp
    _cleanup = AnalysisImportTest._cleanup
    _login = AnalysisImportTest._login
    _project = AnalysisImportTest._project
    _start_and_save = AnalysisImportTest._start_and_save
    _complete_and_process = AnalysisImportTest._complete_and_process
    prepare = AnalysisImportTest.prepare

    def _saved_job(self, runner, project, account, source, **updates):
        job = dict(project_id=project, account_id=account, source_hash=source.source_hash,
                   source_version=source.version_id, source_revision=source.source_revision,
                   status="running", cursor=0, total=1, memory="", draft=None, report=None,
                   run_id="prior", message="恢复中",
                   budget=BudgetLedger(pricing=pricing_for_model("mimo-v2.6-flash")).public())
        job.update(updates)
        runner.save(job)
        return job

    def _confirm_source_edit(self, project):
        chapter = self.client.get(f"/api/independent/projects/{project}").json()["active_version"]["chapters"][0]
        saved = self.client.put(f"/api/independent/projects/{project}/chapters/{chapter['chapter_id']}/draft",
                                json={"content": chapter["content"] + "窗外又下起雨。",
                                      "expected_revision": chapter["server_revision"]})
        self.assertEqual(saved.status_code, 200, saved.text)
        confirmed = self.client.post(f"/api/independent/projects/{project}/pending-changes/resolve",
                                     json={"decision": "ignore"})
        self.assertEqual(confirmed.status_code, 200, confirmed.text)

    async def test_incremental_segments_then_independent_synthesis(self):
        project, _ = self.prepare()
        account = self.independent.store.load(project).account_id
        first = first_delta(self.payload["report"])
        second = {"new_evidence": [{"id": "later", "source_id": source_id(1, "他把钥匙交给陆川。")}]}
        final = {"revised_findings": [{"id": "F1", "title": "行动中的否定",
                                        "text": "她保留选择，随后交出钥匙。", "status": "inferred",
                                        "evidence_ids": ["Q1", "Q2"]}]}
        responses = iter([first, second, final])

        async def respond(**kwargs):
            self.assertIs(kwargs["response_model"], GroundedDelta)
            return SimpleNamespace(data=next(responses), call_id=kwargs["call_id"],
                                   usage=LLMUsage(prompt_tokens=200, completion_tokens=100,
                                                  total_tokens=300))

        runtime = SimpleNamespace(available=True, model="mimo-v2.6-flash",
                                  structured=AsyncMock(side_effect=respond))
        runner = BookAnalysis(self.deconstruction, lambda: runtime)
        batches = [[dict(chapter_number=1, title="第一章", content="灯亮了。😀沈禾没有开门。")],
                   [dict(chapter_number=1, title="第一章", content="他把钥匙交给陆川。")]]
        with patch("app.core.book_analysis.reading_batches", return_value=batches):
            runner.start(project, account)
            await runner.tasks[project]
        job = runner.load(project, account)
        self.assertEqual((job["status"], job["cursor"], job["synthesized"]),
                         ("completed", 2, True), job["message"])
        self.assertEqual(runtime.structured.await_count, 3)
        self.assertEqual(job["budget"]["calls"], 3)
        self.assertEqual(job["budget"]["pending_attempts"], {})
        self.assertEqual(job["budget"]["pricing_version"], pricing_for_model(runtime.model).version)
        self.assertEqual(job["report"]["findings"][0]["evidence_ids"], ["Q1", "Q2"])
        calls = runtime.structured.await_args_list
        self.assertNotIn("accumulated_analysis", json.dumps(calls[1].kwargs["messages"], ensure_ascii=False))
        self.assertNotIn("沈禾保留了不开门的选择", json.dumps(calls[1].kwargs["messages"], ensure_ascii=False))
        self.assertIn("转生、附身区分意识与身体原主", calls[1].kwargs["messages"][0]["content"])
        for call in calls:
            rules = call.kwargs["messages"][0]["content"]
            self.assertIn("每段对白先核对说话者和被指对象", rules)
            self.assertIn("在场行动者与尸体", rules)
            self.assertIn("区分家族成员、仆人及其他在场者", rules)
            self.assertIn("复核事件内动作的前后顺序", rules)
            self.assertIn("follows 表示后件紧随前件", rules)
        self.assertIn("draft", calls[2].kwargs["messages"][1]["content"])
        self.assertEqual(self.client.get(self.url).json()["result"]["report"]["findings"][0]["text"],
                         "她保留选择，随后交出钥匙。")

    async def test_running_job_recovers_without_get_request(self):
        project, _ = self.prepare()
        account = self.independent.store.load(project).account_id
        source = self.deconstruction._source(project, account)
        runtime = SimpleNamespace(available=True, model="mimo-v2.6-flash",
                                  structured=AsyncMock(side_effect=[
                                      SimpleNamespace(data=first_delta(self.payload["report"]),
                                                      call_id="first", usage=LLMUsage(known=False)),
                                      SimpleNamespace(data={}, call_id="final", usage=LLMUsage(known=False)),
                                  ]))
        runner = BookAnalysis(self.deconstruction, lambda: runtime)
        runner.save(dict(project_id=project, account_id=account, source_hash=source.source_hash,
                         source_version=source.version_id, source_revision=source.source_revision,
                         status="running", cursor=0, total=1, memory="", draft=None, report=None,
                         message="恢复中", budget=BudgetLedger(pricing=pricing_for_model(runtime.model)).public()))
        with patch("app.core.book_analysis.reading_batches", return_value=[[
            dict(chapter_number=1, title="第一章", content="灯亮了。😀沈禾没有开门。他把钥匙交给陆川。")]]):
            self.assertEqual(runner.recover_pending(), {"scheduled": 1, "invalid": 0})
            await runner.tasks[project]
        job = runner.load(project, account)
        self.assertEqual(job["status"], "completed", job["message"])
        self.assertEqual(job["budget"]["unknown_usage_calls"], 2)
        self.assertGreater(job["budget"]["accounted_spent_cny"], 0)

    async def test_pause_during_model_call_keeps_existing_result(self):
        project, _ = self.prepare()
        account = self.independent.store.load(project).account_id
        before = self.client.get(self.url).json()["result"]["document_id"]

        async def respond(**kwargs):
            runner.pause(project, account)
            return SimpleNamespace(data=first_delta(self.payload["report"]),
                                   call_id=kwargs["call_id"], usage=LLMUsage(known=False))

        runtime = SimpleNamespace(available=True, model="mimo-v2.6-flash",
                                  structured=AsyncMock(side_effect=respond))
        runner = BookAnalysis(self.deconstruction, lambda: runtime)
        with patch("app.core.book_analysis.reading_batches", return_value=[[
            dict(chapter_number=1, title="第一章", content="灯亮了。😀沈禾没有开门。他把钥匙交给陆川。")]]):
            runner.start(project, account)
            await runner.tasks[project]
        job = runner.load(project, account)
        self.assertEqual((job["status"], job["cursor"]), ("paused", 0))
        self.assertEqual(job["budget"]["calls"], 1)
        self.assertEqual(job["budget"]["pending_attempts"], {})
        self.assertEqual(self.client.get(self.url).json()["result"]["document_id"], before)

    async def test_source_change_during_partial_result_prevents_cursor_advance(self):
        for mutation in ("version", "revision", "hash", "pending"):
            with self.subTest(mutation=mutation):
                project, _ = self.prepare()
                account = self.independent.store.load(project).account_id
                before = self.client.get(self.url).json()["result"]["document_id"]
                original = self.deconstruction._source(project, account)
                active = [original]

                async def respond(**kwargs):
                    changes = {"version": {"version_id": "new-version"},
                               "revision": {"source_revision": original.source_revision + 1},
                               "hash": {"source_hash": "f" * 64},
                               "pending": {"pending_changes": True}}
                    active[0] = replace(original, **changes[mutation])
                    return SimpleNamespace(data={}, call_id=kwargs["call_id"],
                                           usage=LLMUsage(known=False))

                runtime = SimpleNamespace(available=True, model="mimo-v2.6-flash",
                                          structured=AsyncMock(side_effect=respond))
                runner = BookAnalysis(self.deconstruction, lambda: runtime)
                with patch.object(self.deconstruction, "_source", side_effect=lambda *args: active[0]):
                    runner.start(project, account)
                    await runner.tasks[project]
                job = runner.load(project, account)
                self.assertEqual((job["status"], job["cursor"]), ("failed", 0))
                self.assertIsNone(job["draft"])
                self.assertEqual(job["budget"]["calls"], 1)
                self.assertEqual(runtime.structured.await_count, 1)
                self.assertEqual(self.client.get(self.url).json()["result"]["document_id"], before)

    async def test_restart_same_hash_new_source_identity_starts_fresh(self):
        project, _ = self.prepare()
        account = self.independent.store.load(project).account_id
        source = self.deconstruction._source(project, account)
        runtime = SimpleNamespace(available=True, model="mimo-v2.6-flash", structured=AsyncMock())
        runner = BookAnalysis(self.deconstruction, lambda: runtime)
        for changed in (replace(source, version_id="new-version"),
                        replace(source, source_revision=source.source_revision + 1)):
            with self.subTest(version=changed.version_id, revision=changed.source_revision):
                self._saved_job(runner, project, account, source, status="completed", cursor=1,
                                report=self.payload["report"])
                with patch.object(self.deconstruction, "_source", return_value=changed), \
                        patch.object(runner, "ensure_task"):
                    runner.start(project, account)
                job = runner.load(project, account)
                self.assertEqual((job["status"], job["cursor"]), ("running", 0))
                self.assertIsNone(job["report"])
                self.assertEqual(job["source_version"], changed.version_id)
                self.assertEqual(job["source_revision"], changed.source_revision)
                self.assertNotEqual(job["run_id"], "prior")
        runtime.structured.assert_not_called()

    async def test_stale_recovery_and_pending_changes_do_not_call_model(self):
        project, _ = self.prepare()
        account = self.independent.store.load(project).account_id
        source = self.deconstruction._source(project, account)
        runtime = SimpleNamespace(available=True, model="mimo-v2.6-flash", structured=AsyncMock())
        runner = BookAnalysis(self.deconstruction, lambda: runtime)
        for current in (replace(source, version_id="new-version"), replace(source, pending_changes=True)):
            with self.subTest(pending=current.pending_changes):
                self._saved_job(runner, project, account, source)
                with patch.object(self.deconstruction, "_source", return_value=current):
                    runner.recover_pending()
                    await runner.tasks[project]
                self.assertEqual(runner.load(project, account)["status"], "failed")
        runtime.structured.assert_not_called()

    async def test_later_half_chapter_quote_is_rejected_before_import(self):
        project, _ = self.prepare()
        account = self.independent.store.load(project).account_id
        before = self.client.get(self.url).json()["result"]["document_id"]
        runtime = SimpleNamespace(available=True, model="mimo-v2.6-flash",
                                  structured=AsyncMock(return_value=SimpleNamespace(
                                      data=first_delta(self.payload["report"]), call_id="unread",
                                      usage=LLMUsage(known=False))))
        runner = BookAnalysis(self.deconstruction, lambda: runtime)
        with patch("app.core.book_analysis.reading_batches", return_value=[
            [dict(chapter_number=1, title="第一章", content="灯亮了。😀")],
            [dict(chapter_number=1, title="第一章", content="沈禾没有开门。他把钥匙交给陆川。")]]):
            runner.start(project, account)
            await runner.tasks[project]
        job = runner.load(project, account)
        self.assertEqual((job["status"], job["cursor"]), ("failed", 0))
        self.assertEqual(self.client.get(self.url).json()["result"]["document_id"], before)

    async def test_pause_then_resume_in_flight_uses_new_run_and_accounts_old_call(self):
        project, _ = self.prepare()
        account = self.independent.store.load(project).account_id
        calls = []

        async def respond(**kwargs):
            calls.append(kwargs["call_id"])
            if len(calls) == 1:
                runner.pause(project, account)
                runner.start(project, account)
                data = {}
            elif len(calls) == 2:
                data = first_delta(self.payload["report"])
            else:
                data = {}
            return SimpleNamespace(data=data, call_id=kwargs["call_id"], usage=LLMUsage(known=False))

        runtime = SimpleNamespace(available=True, model="mimo-v2.6-flash",
                                  structured=AsyncMock(side_effect=respond))
        runner = BookAnalysis(self.deconstruction, lambda: runtime)
        runner.start(project, account)
        previous = runner.tasks[project]
        await previous
        await asyncio.sleep(0)
        self.assertIsNot(runner.tasks[project], previous)
        await runner.tasks[project]
        job = runner.load(project, account)
        self.assertEqual((job["status"], job["cursor"]), ("completed", 1))
        self.assertTrue(job["synthesized"])
        self.assertEqual(job["budget"]["calls"], 3)
        self.assertEqual(job["budget"]["pending_attempts"], {})

    async def test_source_invalidated_during_synthesis_keeps_segment_report(self):
        project, _ = self.prepare()
        account = self.independent.store.load(project).account_id
        original = self.deconstruction._source(project, account)
        active = [original]
        segment_document = []
        replies = 0

        async def respond(**kwargs):
            nonlocal replies
            replies += 1
            if replies == 1:
                data = first_delta(self.payload["report"])
            else:
                segment_document.append(self.client.get(self.url).json()["result"]["document_id"])
                active[0] = replace(original, source_revision=original.source_revision + 1)
                data = {"title": "这个综合不应发布"}
            return SimpleNamespace(data=data, call_id=kwargs["call_id"], usage=LLMUsage(known=False))

        runtime = SimpleNamespace(available=True, model="mimo-v2.6-flash",
                                  structured=AsyncMock(side_effect=respond))
        runner = BookAnalysis(self.deconstruction, lambda: runtime)
        with patch.object(self.deconstruction, "_source", side_effect=lambda *args: active[0]):
            runner.start(project, account)
            await runner.tasks[project]
        job = runner.load(project, account)
        self.assertEqual((job["status"], job["cursor"]), ("failed", 1))
        self.assertFalse(job["synthesized"])
        self.assertNotEqual(job["report"]["title"], "这个综合不应发布")
        self.assertEqual(job["budget"]["calls"], 2)
        self.assertEqual(self.client.get(self.url).json()["result"]["document_id"], segment_document[0])

    async def test_cancel_preserves_in_flight_budget_for_restart(self):
        project, _ = self.prepare()
        account = self.independent.store.load(project).account_id
        entered = asyncio.Event()
        wait = asyncio.Event()

        async def respond(**kwargs):
            entered.set()
            await wait.wait()

        runtime = SimpleNamespace(available=True, model="mimo-v2.6-flash",
                                  structured=AsyncMock(side_effect=respond))
        runner = BookAnalysis(self.deconstruction, lambda: runtime)
        runner.start(project, account)
        task = runner.tasks[project]
        await asyncio.wait_for(entered.wait(), timeout=2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
        self.assertIs(runner.tasks[project], task)
        job = runner.load(project, account)
        self.assertEqual((job["status"], job["cursor"]), ("running", 0))
        self.assertGreater(job["budget"]["reserved_cny"], 0)
        restored = BudgetLedger.from_public(job["budget"], pricing=pricing_for_model(runtime.model))
        self.assertEqual(restored.pending_attempts, job["budget"]["pending_attempts"])
        self.assertEqual(runtime.structured.await_count, 1)

    async def test_source_replacement_keeps_and_settles_old_request_budget(self):
        from app.agents.llm_runtime import LLMRuntimeError

        for old_outcome in ("unknown", "known", "failed"):
            with self.subTest(old_outcome=old_outcome):
                project, _ = self.prepare()
                account = self.independent.store.load(project).account_id
                entered = asyncio.Event()
                release = asyncio.Event()
                bounds = []
                old_usage = LLMUsage(prompt_tokens=100, completion_tokens=200, total_tokens=300)

                async def respond(**kwargs):
                    pending = runner.load(project, account)["budget"]["pending_attempts"]
                    self.assertEqual(len(pending), 1)
                    bounds.append(next(iter(pending.values())))
                    if len(bounds) == 1:
                        entered.set()
                        await release.wait()
                        if old_outcome == "failed":
                            raise LLMRuntimeError("provider_unavailable", "合成失败", retryable=True)
                        data = {}
                        usage = old_usage if old_outcome == "known" else LLMUsage(known=False)
                    else:
                        data = first_delta(self.payload["report"]) if len(bounds) == 2 else {}
                        usage = LLMUsage(known=False)
                    return SimpleNamespace(data=data, call_id=kwargs["call_id"], usage=usage)

                runtime = SimpleNamespace(available=True, model="mimo-v2.6-flash",
                                          structured=AsyncMock(side_effect=respond))
                runner = BookAnalysis(self.deconstruction, lambda: runtime)
                runner.start(project, account)
                old_task = runner.tasks[project]
                try:
                    await asyncio.wait_for(entered.wait(), timeout=2)
                    old_job = runner.load(project, account)
                    old_pending = copy.deepcopy(old_job["budget"]["pending_attempts"])
                    runner.pause(project, account)
                    self._confirm_source_edit(project)
                    self.assertFalse(self.deconstruction._source(project, account).pending_changes)
                    runner.start(project, account)
                    migrated = runner.load(project, account)
                    self.assertNotEqual(migrated["source_hash"], old_job["source_hash"])
                    self.assertEqual(migrated["budget"]["pending_attempts"], old_pending)
                    self.assertAlmostEqual(migrated["budget"]["reserved_cny"], bounds[0], places=6)
                    release.set()
                    await old_task
                    await asyncio.sleep(0)
                    await runner.tasks[project]
                    job = runner.load(project, account)
                    self.assertEqual((job["status"], job["cursor"]), ("completed", 1), job["message"])
                    self.assertEqual(runtime.structured.await_count, 3)
                    self.assertEqual(job["budget"]["calls"], 3)
                    old_cost = (pricing_for_model(runtime.model).cost(input_tokens=100, output_tokens=200)
                                if old_outcome == "known" else bounds[0])
                    self.assertAlmostEqual(job["budget"]["accounted_spent_cny"],
                                           old_cost + sum(bounds[1:]), places=6)
                    self.assertEqual(job["budget"]["pending_attempts"], {})
                    restored = BudgetLedger.from_public(job["budget"], pricing=pricing_for_model(runtime.model))
                    self.assertEqual(restored.calls, 3)
                    self.assertEqual(restored.spent_cny, job["budget"]["accounted_spent_cny"])
                finally:
                    release.set()
                    for task in set(runner.tasks.values()) | {old_task}:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*set(runner.tasks.values()), old_task, return_exceptions=True)

    async def test_source_replacement_cannot_reset_consumed_budget_cap(self):
        project, _ = self.prepare()
        account = self.independent.store.load(project).account_id
        source = self.deconstruction._source(project, account)
        before = self.client.get(self.url).json()["result"]["document_id"]
        runtime = SimpleNamespace(available=True, model="mimo-v2.6-flash", structured=AsyncMock())
        runner = BookAnalysis(self.deconstruction, lambda: runtime)
        budget = BudgetLedger(budget_cny=0.08, reserve_cny=0, pricing=pricing_for_model(runtime.model),
                              spent_cny=0.053848, calls=1, unknown_usage_calls=1).public()
        self._saved_job(runner, project, account, source, status="completed", cursor=1, budget=budget)
        self._confirm_source_edit(project)
        runner.start(project, account)
        await runner.tasks[project]
        job = runner.load(project, account)
        self.assertEqual((job["status"], job["cursor"]), ("paused", 0))
        self.assertEqual(job["budget"]["accounted_spent_cny"], 0.053848)
        self.assertEqual(job["budget"]["budget_cny"], 0.08)
        self.assertEqual(job["budget"]["calls"], 1)
        runtime.structured.assert_not_called()
        # The source is now stale, but no new model report has replaced the old document.
        self.assertEqual(self.deconstruction.store.load(project).active_document_id, before)

    async def test_late_settlement_preserves_more_recent_budget_entries(self):
        from app.agents.llm_runtime import LLMResult

        project, _ = self.prepare()
        account = self.independent.store.load(project).account_id
        source = self.deconstruction._source(project, account)
        pricing = pricing_for_model("mimo-v2.6-flash")
        runner = BookAnalysis(self.deconstruction, lambda: None)
        ledger = BudgetLedger(pricing=pricing)
        ledger.reserve_attempt("old", [{"content": "旧来源"}], 100)
        old_bound = ledger.pending_attempts["old"]
        self._saved_job(runner, project, account, source, budget=ledger.public())
        # Simulate a newer call having already written its settlement to disk.
        ledger.reserve_attempt("new", [{"content": "新来源"}], 100)
        new_bound = ledger.pending_attempts["new"]
        ledger.record(LLMResult(call_id="new", text="", usage=LLMUsage(known=False)),
                      stage="segment", attempt_id="new")
        latest = runner.load(project, account)
        latest.update(source_hash="f" * 64, budget=ledger.public())
        runner.save(latest)
        runner._settle_call(project, account, pricing,
                            LLMResult(call_id="old", text="", usage=LLMUsage(known=False)),
                            stage="segment", attempt_id="old")
        budget = runner.load(project, account)["budget"]
        self.assertEqual(budget["calls"], 2)
        self.assertEqual(budget["unknown_usage_calls"], 2)
        self.assertAlmostEqual(budget["accounted_spent_cny"], old_bound + new_bound, places=6)
        self.assertEqual(budget["pending_attempts"], {})

    async def test_synthesis_corrects_relation_through_real_delta_merge(self):
        project, _ = self.prepare()
        account = self.independent.store.load(project).account_id
        first = first_delta(copy.deepcopy(self.payload["report"]))
        event = {**copy.deepcopy(first["new_events"][0]), "id": "later", "title": "交接钥匙"}
        first["new_events"].append(event)
        first["story_order"].append("later")
        first["new_relations"] = [
            {**copy.deepcopy(event["action"]), "from_id": "later", "to_id": "E1", "kind": "follows",
             "text": "交接跟随未开门。"},
            {**copy.deepcopy(event["action"]), "from_id": "later", "to_id": "E1", "kind": "enables"},
        ]
        corrected = {
            "withdrawn_relations": [{"from_id": "E2", "to_id": "E1", "kind": "follows"}],
            "new_relations": [{"from_id": "E1", "to_id": "E2", "kind": "follows",
                               "text": "交接跟随未开门。", "status": "inferred", "evidence_ids": ["Q1"]}],
        }
        replies = iter([first, corrected])

        async def respond(**kwargs):
            self.assertIs(kwargs["response_model"], GroundedDelta)
            return SimpleNamespace(data=next(replies), call_id=kwargs["call_id"], usage=LLMUsage(known=False))

        runtime = SimpleNamespace(available=True, model="mimo-v2.6-flash",
                                  structured=AsyncMock(side_effect=respond))
        runner = BookAnalysis(self.deconstruction, lambda: runtime)
        with patch("app.core.book_analysis.asyncio.wait_for", wraps=asyncio.wait_for) as waits:
            runner.start(project, account)
            await runner.tasks[project]
        job = runner.load(project, account)
        self.assertEqual(job["status"], "completed", job["message"])
        self.assertEqual([(edge["from_id"], edge["to_id"], edge["kind"]) for edge in job["report"]["relations"]],
                         [("E2", "E1", "enables"), ("E1", "E2", "follows")])
        self.assertEqual(job["budget"]["calls"], 2)
        self.assertEqual(job["budget"]["pending_attempts"], {})
        self.assertEqual([call.kwargs["timeout"] for call in waits.call_args_list], [1220, 1220])
        for call in runtime.structured.await_args_list:
            self.assertIn("withdrawn_relations", call.kwargs["messages"][0]["content"])
        published = self.client.get(self.url).json()["result"]["report"]
        self.assertEqual(published["relations"], job["report"]["relations"])


del AnalysisImportTest
