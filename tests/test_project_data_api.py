from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from app import novel_routes
from app.agents import novel_nodes
from app.core import novel_graph
from app.core.project_store import JsonProjectStore
from app.models import (
    BatchTaskRecord,
    ChapterDraft,
    ChapterPlan,
    ChapterRecord,
    CharacterCard,
    FullNovelPlan,
    NovelState,
    PlotBeat,
    ReviewerOutput,
    VolumePlan,
    WriterOutput,
)


class ProjectDataApiTest(unittest.TestCase):
    def test_writer_receives_batch_temporary_context_in_previous_summary(self) -> None:
        captured: dict[str, str] = {}
        beat = PlotBeat(order=1, summary="主角转入城南档案馆。")
        state: NovelState = {
            "global_worldview": "旧城存在星门。",
            "global_lore": {"previous_summary": "上一章主角离开钟楼。"},
            "current_chapter_number": 3,
            "current_stage": "writing",
            "current_plot_beats": [beat],
            "current_draft": None,
            "character_graph": {},
            "retrieved_context": [],
            "temporary_context": {
                "previous_draft_summary": "第二章主角在钟楼暗室听到星门回声。",
                "previous_hook": "钟楼深处传来星门开启的回声。",
                "previous_character_state": "林澈；旧城钟楼；警觉；疲惫；查明星门来源",
                "recent_draft_summaries": "第 2 章：主角在钟楼暗室调查星门回声。",
                "batch_context_instruction": "避免重复近期章节的场景结构。",
            },
            "human_feedback": "继续推进档案馆线。",
            "human_approved": True,
            "extracted_lore_updates": {},
            "extracted_character_updates": {},
            "review_feedback": [],
            "session_id": "writer-temp-test",
            "project_id": "writer-temp-project",
            "error_message": None,
        }

        def fake_generate_chapter_with_llm(**kwargs: object) -> WriterOutput:
            captured["previous_summary"] = str(kwargs["previous_summary"])
            return WriterOutput(title="档案馆", content="草稿正文。", writing_notes=[])

        with patch.object(
            novel_nodes,
            "generate_chapter_with_llm",
            fake_generate_chapter_with_llm,
        ):
            novel_nodes.writer_agent(state)

        self.assertIn("第二章主角在钟楼暗室听到星门回声", captured["previous_summary"])
        self.assertIn("钟楼深处传来星门开启的回声", captured["previous_summary"])
        self.assertIn("林澈", captured["previous_summary"])
        self.assertIn("第 2 章", captured["previous_summary"])

    def test_reviewer_strictly_rejects_batch_first_draft_below_threshold(self) -> None:
        beat = PlotBeat(order=1, summary="主角继续调查线索。")
        state: NovelState = {
            "global_worldview": "旧城存在星门。",
            "global_lore": {"previous_summary": "上一章在钟楼听到星门回声。"},
            "current_chapter_number": 2,
            "current_stage": "reviewing",
            "current_plot_beats": [beat],
            "current_draft": ChapterDraft(
                chapter_number=2,
                title="回声",
                plot_beats=[beat],
                content="主角继续调查。主角继续调查。",
                status="drafted",
            ),
            "character_graph": {},
            "retrieved_context": [],
            "temporary_context": {
                "batch_generation": "true",
                "previous_hook": "钟楼深处传来星门开启的回声。",
            },
            "human_feedback": None,
            "human_approved": True,
            "extracted_lore_updates": {},
            "extracted_character_updates": {},
            "review_feedback": [],
            "session_id": "strict-review-test",
            "project_id": "strict-review-project",
            "error_message": None,
        }

        def fake_review_chapter_with_llm(**_: object) -> ReviewerOutput:
            return ReviewerOutput(
                passed=True,
                quality_score=8.4,
                reviewer_comments=[],
                revision_suggestions=[],
            )

        with patch.object(
            novel_nodes,
            "review_chapter_with_llm",
            fake_review_chapter_with_llm,
        ):
            update = novel_nodes.reviewer_agent(state)

        self.assertEqual(update["current_stage"], "awaiting_revision_decision")
        self.assertEqual(update["current_draft"].status, "needs_revision")
        self.assertLess(update["current_draft"].quality_score, 8.5)

    def test_reviewer_catches_non_adjacent_chapter_similarity_from_temp_context(self) -> None:
        beat = PlotBeat(
            order=1,
            summary="主角再次进入钟楼暗室调查星门回声。",
            conflict="调查方式与前文重复",
        )
        state: NovelState = {
            "global_worldview": "旧城存在星门。",
            "global_lore": {"previous_summary": "第三章主角离开钟楼。"},
            "current_chapter_number": 4,
            "current_stage": "reviewing",
            "current_plot_beats": [beat],
            "current_draft": ChapterDraft(
                chapter_number=4,
                title="重复的回声",
                plot_beats=[beat],
                content="主角再次进入钟楼暗室调查星门回声，沿着石阶寻找旧线索。",
                status="drafted",
            ),
            "character_graph": {},
            "retrieved_context": [],
            "temporary_context": {
                "batch_generation": "true",
                "recent_draft_summaries": "\n".join(
                    [
                        "第 2 章：主角进入钟楼暗室调查星门回声，沿着石阶寻找旧线索。",
                        "第 3 章：主角离开钟楼，转向城南档案馆。",
                    ]
                ),
            },
            "human_feedback": None,
            "human_approved": True,
            "extracted_lore_updates": {},
            "extracted_character_updates": {},
            "review_feedback": [],
            "session_id": "similar-review-test",
            "project_id": "similar-review-project",
            "error_message": None,
        }

        def fake_review_chapter_with_llm(**_: object) -> ReviewerOutput:
            return ReviewerOutput(
                passed=True,
                quality_score=9.1,
                reviewer_comments=[],
                revision_suggestions=[],
            )

        with patch.object(
            novel_nodes,
            "review_chapter_with_llm",
            fake_review_chapter_with_llm,
        ):
            update = novel_nodes.reviewer_agent(state)

        self.assertEqual(update["current_stage"], "awaiting_revision_decision")
        self.assertTrue(
            any("第 2 章" in comment and "相似" in comment for comment in update["review_feedback"])
        )

    def test_project_level_data_recovers_after_service_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_store = JsonProjectStore(Path(tmp_dir))
            first_service = novel_graph.NovelWorkflowService(store=project_store)

            first_service.create_project(
                project_id="project-data-recovery",
                title="星门旧城",
                global_worldview="旧城钟楼保存着失落星图。",
            )
            first_service.update_full_plan(
                project_id="project-data-recovery",
                full_plan=FullNovelPlan(
                    premise="少年追查钟楼星图。",
                    core_conflict="星门真相与旧城秩序相冲突。",
                    target_chapter_count=3,
                ),
                volumes=[
                    VolumePlan(
                        volume_number=1,
                        title="旧城卷",
                        summary="发现星图并进入主线。",
                        chapter_start=1,
                        chapter_end=3,
                    )
                ],
                chapter_plans=[
                    ChapterPlan(
                        chapter_number=1,
                        summary="发现钟楼星图。",
                    )
                ],
            )
            snapshot = first_service.prepare_next_chapter(
                project_id="project-data-recovery",
                user_instruction="承接星图线索。",
            )

            second_service = novel_graph.NovelWorkflowService(store=project_store)
            projects = second_service.list_projects()
            recovered = second_service.get_project("project-data-recovery")

            self.assertEqual([project.project_id for project in projects], ["project-data-recovery"])
            self.assertEqual(recovered.full_plan.premise, "少年追查钟楼星图。")
            self.assertEqual(recovered.volumes[0].title, "旧城卷")
            self.assertEqual(recovered.chapter_plans[0].summary, "发现钟楼星图。")
            self.assertEqual(recovered.next_chapter_input_snapshot.chapter_number, snapshot.chapter_number)
            self.assertEqual(recovered.next_chapter_input_snapshot.user_instruction, "承接星图线索。")

    def test_prepare_next_does_not_run_planner_until_formal_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_store = JsonProjectStore(Path(tmp_dir))

            def fake_planner_agent(_: NovelState) -> dict:
                return {
                    "current_plot_beats": [
                        PlotBeat(order=1, summary="主角确认下一章目标。")
                    ],
                    "current_stage": "awaiting_human_review",
                    "human_approved": False,
                    "error_message": None,
                }

            with patch.object(novel_graph, "planner_agent", fake_planner_agent):
                service = novel_graph.NovelWorkflowService(store=project_store)
                service.create_project(
                    project_id="prepare-vs-plan",
                    title="准备下一章",
                    global_worldview="世界观已经建立。",
                )

                snapshot = service.prepare_next_chapter(project_id="prepare-vs-plan")
                project_after_prepare = service.get_project("prepare-vs-plan")

                self.assertEqual(snapshot.chapter_number, 1)
                self.assertEqual(project_after_prepare.chapters, [])
                self.assertIsNotNone(project_after_prepare.next_chapter_input_snapshot)

                session_id, state = service.plan_next_chapter(project_id="prepare-vs-plan")

            project_after_plan = service.get_project("prepare-vs-plan")
            self.assertEqual(state["current_stage"], "awaiting_human_review")
            self.assertEqual(project_after_plan.chapters[0].session_id, session_id)
            self.assertIsNone(project_after_plan.next_chapter_input_snapshot)

    def test_project_routes_create_list_full_plan_and_prepare_next(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = novel_graph.NovelWorkflowService(
                store=JsonProjectStore(Path(tmp_dir))
            )
            client = TestClient(main.app)

            with patch.object(novel_routes, "novel_workflow_service", service):
                create_response = client.post(
                    "/novel/projects",
                    json={
                        "project_id": "route-project",
                        "title": "路由作品",
                        "project_brief": "首页摘要",
                        "global_worldview": "路由测试世界观。",
                    },
                )
                list_response = client.get("/novel/projects")
                full_plan_response = client.post(
                    "/novel/projects/route-project/full-plan",
                    json={
                        "target_chapter_count": 2,
                    },
                )
                prepare_response = client.get("/novel/projects/route-project/prepare-next")

            self.assertEqual(create_response.status_code, 200)
            self.assertEqual(list_response.status_code, 200)
            self.assertEqual(full_plan_response.status_code, 200)
            self.assertEqual(prepare_response.status_code, 200)
            self.assertEqual(
                list_response.json()["projects"][0]["project_id"],
                "route-project",
            )
            self.assertEqual(
                list_response.json()["projects"][0]["project_brief"],
                "首页摘要",
            )
            self.assertIn("completed_chapter_count", list_response.json()["projects"][0])
            self.assertIn("latest_chapter_status", list_response.json()["projects"][0])
            self.assertIn("suggested_next_chapter_number", list_response.json()["projects"][0])
            self.assertIn("suggested_batch_start_chapter", list_response.json()["projects"][0])
            self.assertEqual(
                full_plan_response.json()["project"]["full_plan"]["target_chapter_count"],
                2,
            )
            self.assertEqual(prepare_response.json()["snapshot"]["chapter_number"], 1)

    def test_project_codex_endpoint_aggregates_character_and_lore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = novel_graph.NovelWorkflowService(
                store=JsonProjectStore(Path(tmp_dir))
            )
            project = service.create_project(
                project_id="codex-project",
                title="设定集作品",
                global_worldview="旧城存在星门。",
                full_plan=FullNovelPlan(
                    premise="少年追查星门。",
                    core_conflict="星门真相与旧城秩序冲突。",
                ),
            )
            project.character_codex = [
                CharacterCard(
                    name="林澈",
                    role="protagonist",
                    profile="追查星门的少年。",
                )
            ]
            project.lore_codex = {
                "artifact.star_map": "钟楼星图可以定位星门。",
            }
            project.chapters.append(
                ChapterRecord(
                    chapter_number=1,
                    status="completed",
                    summary="林澈在钟楼发现星图。",
                )
            )
            service._save_project(project)  # noqa: SLF001 - 构造 codex 聚合数据。
            client = TestClient(main.app)

            with patch.object(novel_routes, "novel_workflow_service", service):
                response = client.get("/novel/projects/codex-project/codex")

            payload = response.json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload["project_id"], "codex-project")
            self.assertEqual(payload["character_count"], 1)
            self.assertEqual(payload["character_codex"][0]["name"], "林澈")
            self.assertEqual(payload["lore_codex"]["artifact.star_map"], "钟楼星图可以定位星门。")
            self.assertEqual(payload["lore_codex"]["full_plan.premise"], "少年追查星门。")
            self.assertEqual(payload["lore_codex"]["chapter_1_summary"], "林澈在钟楼发现星图。")

    def test_batch_task_response_infers_legacy_chapter_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = novel_graph.NovelWorkflowService(
                store=JsonProjectStore(Path(tmp_dir))
            )
            project = service.create_project(
                project_id="legacy-batch-project",
                title="旧批量任务作品",
                global_worldview="旧批量测试世界观。",
            )
            project.chapters.extend(
                [
                    ChapterRecord(
                        chapter_number=1,
                        status="drafted",
                        session_id="session-1",
                        draft=ChapterDraft(
                            chapter_number=1,
                            title="第一章",
                            content="第一章草稿。",
                            status="drafted",
                        ),
                    ),
                    ChapterRecord(
                        chapter_number=2,
                        status="needs_revision",
                        session_id="session-2",
                        draft=ChapterDraft(
                            chapter_number=2,
                            title="第二章",
                            content="第二章草稿。",
                            status="needs_revision",
                        ),
                    ),
                ]
            )
            project.batch_tasks.append(
                BatchTaskRecord(
                    kind="generate",
                    status="completed",
                    chapter_numbers=[1, 2, 3],
                    session_ids={1: "session-1", 2: "session-2"},
                    message="旧任务没有 chapter_results。",
                )
            )
            service._save_project(project)  # noqa: SLF001 - 构造旧 batch task。
            task = service.get_project("legacy-batch-project").batch_tasks[0]

            response = novel_routes.BatchTaskResponse.from_project(
                task=task,
                project=service.get_project("legacy-batch-project"),
            )

            self.assertEqual([result.chapter_number for result in response.chapter_results], [1, 2, 3])
            self.assertEqual(response.chapter_results[0].status, "generated")
            self.assertTrue(response.chapter_results[0].can_review)
            self.assertEqual(response.chapter_results[1].review_status, "needs_revision")
            self.assertTrue(response.chapter_results[1].can_revise)
            self.assertEqual(response.chapter_results[2].status, "pending")

    def test_batch_plan_and_generate_persist_task_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            writer_temporary_contexts: dict[int, dict[str, str]] = {}

            def fake_planner_agent(state: NovelState) -> dict:
                chapter_number = state["current_chapter_number"]
                return {
                    "current_plot_beats": [
                        PlotBeat(order=1, summary=f"第 {chapter_number} 章目标。")
                    ],
                    "current_stage": "awaiting_human_review",
                    "human_approved": False,
                    "error_message": None,
                }

            def fake_writer_agent(state: NovelState) -> dict:
                chapter_number = state["current_chapter_number"]
                writer_temporary_contexts[chapter_number] = state.get("temporary_context", {})
                return {
                    "current_draft": ChapterDraft(
                        chapter_number=chapter_number,
                        title=f"第 {chapter_number} 章",
                        plot_beats=state.get("current_plot_beats", []),
                        content=f"第 {chapter_number} 章草稿。章末钩子：继续追查第 {chapter_number + 1} 章线索。",
                        status="drafted",
                    ),
                    "current_stage": "awaiting_review",
                    "review_feedback": [],
                    "retrieved_context": [],
                    "error_message": None,
                }

            def fake_reviewer_agent(state: NovelState) -> dict:
                draft = state["current_draft"]
                passed = draft.chapter_number == 1
                reviewed_draft = draft.model_copy(
                    update={
                        "status": "reviewed" if passed else "needs_revision",
                        "reviewer_comments": []
                        if passed
                        else ["批量第一稿承接和伏笔推进不足，建议修订。"],
                        "revision_notes": [
                            *draft.revision_notes,
                            "Reviewer 建议：补强承接、人物动机和伏笔推进。",
                        ],
                        "quality_score": 8.7 if passed else 7.8,
                    }
                )
                return {
                    "current_draft": reviewed_draft,
                    "review_feedback": reviewed_draft.reviewer_comments,
                    "retrieved_context": [],
                    "current_stage": "awaiting_chapter_acceptance"
                    if passed
                    else "awaiting_revision_decision",
                    "error_message": None,
                }

            with (
                patch.object(novel_graph, "planner_agent", fake_planner_agent),
                patch.object(novel_graph, "writer_agent", fake_writer_agent),
                patch.object(novel_graph, "reviewer_agent", fake_reviewer_agent),
            ):
                service = novel_graph.NovelWorkflowService(
                    store=JsonProjectStore(Path(tmp_dir))
                )
                service.create_project(
                    project_id="batch-project",
                    title="批量作品",
                    global_worldview="批量测试世界观。",
                )
                plan_task = service.batch_plan_chapters(
                    project_id="batch-project",
                    start_chapter=1,
                    end_chapter=3,
                )
                generate_task = service.batch_generate_chapters(
                    project_id="batch-project",
                    start_chapter=1,
                    end_chapter=3,
                )

            recovered = novel_graph.NovelWorkflowService(
                store=JsonProjectStore(Path(tmp_dir))
            ).get_project("batch-project")

            self.assertEqual(plan_task.status, "completed")
            self.assertEqual(generate_task.status, "completed")
            self.assertEqual([task.kind for task in recovered.batch_tasks], ["plan", "generate"])
            self.assertEqual(
                [chapter.status for chapter in recovered.chapters],
                ["reviewed", "needs_revision", "needs_revision"],
            )
            self.assertEqual(
                [chapter.review_status for chapter in recovered.chapters],
                ["passed", "needs_revision", "needs_revision"],
            )
            self.assertTrue(recovered.chapters[0].can_accept)
            self.assertTrue(recovered.chapters[1].can_revise)
            self.assertEqual(generate_task.pending_acceptance_chapter_numbers, [1])
            self.assertEqual(generate_task.needs_revision_chapter_numbers, [2, 3])
            self.assertEqual(
                [result.chapter_number for result in generate_task.chapter_results],
                [1, 2, 3],
            )
            self.assertTrue(generate_task.chapter_results[0].can_accept)
            self.assertTrue(generate_task.chapter_results[1].can_revise)
            self.assertEqual(writer_temporary_contexts[1].get("batch_generation"), "true")
            self.assertIn("previous_draft_summary", writer_temporary_contexts[2])
            self.assertIn("previous_hook", writer_temporary_contexts[3])
            self.assertIn("recent_draft_summaries", writer_temporary_contexts[3])

    def test_batch_generate_blocks_or_compares_existing_chapters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            def fake_planner_agent(state: NovelState) -> dict:
                chapter_number = state["current_chapter_number"]
                return {
                    "current_plot_beats": [
                        PlotBeat(order=1, summary=f"第 {chapter_number} 章目标。")
                    ],
                    "current_stage": "awaiting_human_review",
                    "human_approved": False,
                    "error_message": None,
                }

            def fake_writer_agent(state: NovelState) -> dict:
                chapter_number = state["current_chapter_number"]
                return {
                    "current_draft": ChapterDraft(
                        chapter_number=chapter_number,
                        title=f"候选第 {chapter_number} 章",
                        plot_beats=state.get("current_plot_beats", []),
                        content=f"候选第 {chapter_number} 章正文。",
                        status="drafted",
                    ),
                    "current_stage": "awaiting_review",
                    "review_feedback": [],
                    "retrieved_context": [],
                    "error_message": None,
                }

            def fake_reviewer_agent(state: NovelState) -> dict:
                draft = state["current_draft"]
                return {
                    "current_draft": draft.model_copy(update={"status": "reviewed"}),
                    "review_feedback": [],
                    "retrieved_context": [],
                    "current_stage": "awaiting_chapter_acceptance",
                    "error_message": None,
                }

            with (
                patch.object(novel_graph, "planner_agent", fake_planner_agent),
                patch.object(novel_graph, "writer_agent", fake_writer_agent),
                patch.object(novel_graph, "reviewer_agent", fake_reviewer_agent),
            ):
                service = novel_graph.NovelWorkflowService(
                    store=JsonProjectStore(Path(tmp_dir))
                )
                service.create_project(
                    project_id="overwrite-project",
                    title="覆盖策略作品",
                    global_worldview="覆盖测试世界观。",
                )
                service.batch_plan_chapters(
                    project_id="overwrite-project",
                    start_chapter=1,
                    end_chapter=3,
                )
                service.batch_generate_chapters(
                    project_id="overwrite-project",
                    start_chapter=1,
                    end_chapter=3,
                )

                with self.assertRaises(ValueError):
                    service.batch_generate_chapters(
                        project_id="overwrite-project",
                        start_chapter=1,
                        end_chapter=3,
                    )

                compare_task = service.batch_generate_chapters(
                    project_id="overwrite-project",
                    start_chapter=1,
                    end_chapter=3,
                    overwrite_policy="compare",
                )

            recovered = service.get_project("overwrite-project")
            preview = next(chapter for chapter in recovered.chapters if chapter.chapter_number == 1)

            self.assertEqual(compare_task.status, "partial")
            self.assertTrue(all(result.status == "skipped" for result in compare_task.chapter_results))
            self.assertTrue(all(result.conflict_type for result in compare_task.chapter_results))
            self.assertIsNotNone(preview.draft)
            self.assertIsNotNone(preview.candidate_draft)
            self.assertIsNotNone(preview.draft_comparison_summary)

    def test_batch_generate_route_returns_conflict_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = novel_graph.NovelWorkflowService(
                store=JsonProjectStore(Path(tmp_dir))
            )
            project = service.create_project(
                project_id="route-conflict-project",
                title="路由冲突作品",
                global_worldview="路由冲突测试世界观。",
            )
            project.chapters.append(
                ChapterRecord(
                    chapter_number=1,
                    status="drafted",
                    session_id="existing-session",
                    draft=ChapterDraft(
                        chapter_number=1,
                        title="已有第一章",
                        content="已有正文。",
                        status="drafted",
                    ),
                    word_count=4,
                )
            )
            service._save_project(project)  # noqa: SLF001 - 构造已有章节冲突数据。
            client = TestClient(main.app)

            def fake_writer_agent(state: NovelState) -> dict:
                chapter_number = state["current_chapter_number"]
                return {
                    "current_draft": ChapterDraft(
                        chapter_number=chapter_number,
                        title=f"候选第 {chapter_number} 章",
                        content=f"候选第 {chapter_number} 章。",
                        status="drafted",
                    ),
                    "current_stage": "awaiting_review",
                    "review_feedback": [],
                    "retrieved_context": [],
                    "error_message": None,
                }

            with (
                patch.object(novel_routes, "novel_workflow_service", service),
                patch.object(novel_graph, "writer_agent", fake_writer_agent),
            ):
                blocked_response = client.post(
                    "/novel/projects/route-conflict-project/batch/generate",
                    json={
                        "start_chapter": 1,
                        "end_chapter": 3,
                    },
                )
                compare_response = client.post(
                    "/novel/projects/route-conflict-project/batch/generate",
                    json={
                        "start_chapter": 1,
                        "end_chapter": 3,
                        "overwrite_policy": "compare",
                    },
                )
                preview_response = client.get(
                    "/novel/projects/route-conflict-project/chapters/1"
                )

            self.assertEqual(blocked_response.status_code, 409)
            self.assertIn("existing_chapter_conflicts", blocked_response.json()["detail"])
            self.assertEqual(compare_response.status_code, 200)
            self.assertEqual(compare_response.json()["task"]["status"], "partial")
            self.assertEqual(
                compare_response.json()["chapter_results"][0]["conflict_type"],
                "existing_draft",
            )
            self.assertEqual(compare_response.json()["suggested_batch_start_chapter"], 2)
            self.assertIsNotNone(preview_response.json()["existing_draft"])
            self.assertIsNotNone(preview_response.json()["candidate_draft"])
            self.assertTrue(preview_response.json()["draft_comparison_summary"])

    def test_chapter_preview_returns_status_for_missing_or_empty_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = novel_graph.NovelWorkflowService(
                store=JsonProjectStore(Path(tmp_dir))
            )
            service.create_project(
                project_id="preview-project",
                title="预览作品",
                global_worldview="预览测试世界观。",
                chapter_plans=[
                    ChapterPlan(chapter_number=1, summary="第一章规划。"),
                    ChapterPlan(chapter_number=2, summary="第二章规划。"),
                ],
            )
            client = TestClient(main.app)

            def fake_planner_agent(_: NovelState) -> dict:
                return {
                    "current_plot_beats": [
                        PlotBeat(order=1, summary="第一章开场。")
                    ],
                    "current_stage": "awaiting_human_review",
                    "human_approved": False,
                    "error_message": None,
                }

            with patch.object(novel_routes, "novel_workflow_service", service):
                missing_response = client.get("/novel/projects/preview-project/chapters/1")
                with patch.object(novel_graph, "planner_agent", fake_planner_agent):
                    service.plan_chapter(
                        project_id="preview-project",
                        global_worldview="预览测试世界观。",
                        chapter_number=1,
                        characters=[],
                    )
                planned_response = client.get("/novel/projects/preview-project/chapters/1")

            self.assertEqual(missing_response.status_code, 200)
            self.assertEqual(missing_response.json()["status"], "missing")
            self.assertFalse(missing_response.json()["has_body"])
            self.assertEqual(missing_response.json()["next_chapter_number"], 2)
            self.assertEqual(planned_response.status_code, 200)
            self.assertEqual(planned_response.json()["status"], "planned")
            self.assertFalse(planned_response.json()["has_body"])
            self.assertTrue(planned_response.json()["can_continue"])
            self.assertTrue(planned_response.json()["message"])


if __name__ == "__main__":
    unittest.main()
