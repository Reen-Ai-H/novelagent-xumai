import copy
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from test_stage32_analysis_import import AnalysisImportTest
from app.core.book_analysis import BookAnalysis, reading_batches, ReadingMemory


class WholeBookTest(unittest.IsolatedAsyncioTestCase):
    setUp = AnalysisImportTest.setUp
    _cleanup = AnalysisImportTest._cleanup
    _login = AnalysisImportTest._login
    _project = AnalysisImportTest._project
    _start_and_save = AnalysisImportTest._start_and_save
    _complete_and_process = AnalysisImportTest._complete_and_process
    prepare = AnalysisImportTest.prepare

    async def test_cumulative_publish_memory_and_completed_restart(self):
        project, _ = self.prepare()
        account = self.independent.store.load(project).account_id
        report = copy.deepcopy(self.payload["report"])
        async def respond(**kwargs):
            return SimpleNamespace(data={"summary":"人物仍未开门。"} if kwargs["response_model"] is ReadingMemory else report)
        runtime = SimpleNamespace(available=True, model="fake", structured=AsyncMock(side_effect=respond))
        runner = BookAnalysis(self.deconstruction, lambda:runtime)
        batch = [[dict(chapter_number=1,title="片段",content="沈禾没有开门。")]] * 4
        with patch("app.core.book_analysis.reading_batches", return_value=batch):
            runner.start(project, account)
            await runner.tasks[project]
            job = runner.load(project, account)
            self.assertEqual((job["status"],job["cursor"]), ("completed",4))
            self.assertTrue(job["memory"])
            self.assertEqual(runtime.structured.await_count,5)
            self.assertEqual(self.client.get(self.url).json()["result"]["report"]["producer"],"fake")
            runner.start(project, account)
            self.assertEqual(runtime.structured.await_count,5)

    async def test_pause_before_call_and_invalid_quote_preserve_result(self):
        project,_ = self.prepare()
        account = self.independent.store.load(project).account_id
        before = self.client.get(self.url).json()["result"]["document_id"]
        bad = copy.deepcopy(self.payload["report"])
        bad["evidence"][0]["quote"] = "原文不存在的引文"
        runtime = SimpleNamespace(available=True, model="fake", structured=AsyncMock(return_value=SimpleNamespace(data=bad)))
        runner=BookAnalysis(self.deconstruction,lambda:runtime)
        runner.start(project,account)
        runner.pause(project,account)
        await runner.tasks[project]
        runtime.structured.assert_not_called()
        runner.start(project,account)
        await runner.tasks[project]
        self.assertEqual(runner.load(project,account)["status"],"failed")
        self.assertEqual(self.client.get(self.url).json()["result"]["document_id"],before)

    def test_long_chapter_is_split_without_dropping_text(self):
        text="中文测试"*15000
        batches=reading_batches([SimpleNamespace(chapter_number=1,title="第一章",content=text)])
        self.assertEqual(''.join(c['content'] for b in batches for c in b),text)
        self.assertTrue(all(sum(len(c['content']) for c in b)<=24000 for b in batches))

del AnalysisImportTest
