from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core import novel_graph
from app.core.memory import JsonMemoryStore
from app.core.project_store import JsonProjectStore
from app.models import ChapterDraft, CharacterCard, NovelState, PlotBeat


class AcceptChapterMemoryTest(unittest.TestCase):
    def test_accept_chapter_writes_librarian_memory_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            project_id = "accept-memory-test"
            session_id = "session-accept-memory-test"
            memory_store = JsonMemoryStore(tmp_path / "memory")
            project_store = JsonProjectStore(tmp_path / "projects")
            service = novel_graph.NovelWorkflowService(store=project_store)
            beat = PlotBeat(order=1, summary="主角发现旧城钟楼藏有失落星图。")
            draft = ChapterDraft(
                chapter_number=1,
                title="钟楼星图",
                plot_beats=[beat],
                content="主角在旧城钟楼发现星图，并决定追查星门的来源。",
                status="reviewed",
            )
            state: NovelState = {
                "session_id": session_id,
                "project_id": project_id,
                "global_worldview": "星门散落在旧城各处。",
                "global_lore": {},
                "current_chapter_number": 1,
                "current_stage": "awaiting_chapter_acceptance",
                "current_plot_beats": [beat],
                "current_draft": draft,
                "character_graph": {},
                "retrieved_context": [],
                "human_feedback": None,
                "human_approved": True,
                "extracted_lore_updates": {},
                "extracted_character_updates": {},
                "review_feedback": [],
                "error_message": None,
            }
            service._graph.update_state(  # noqa: SLF001 - 最小闭环验证需要构造已审查状态。
                service._config(session_id),  # noqa: SLF001
                state,
                as_node="reviewer",
            )

            def fake_librarian_agent(_: NovelState) -> dict:
                character_update = CharacterCard(
                    name="林澈",
                    role="protagonist",
                    profile="追查星图的少年。",
                    current_location="旧城钟楼",
                    motivation="查明星门来源",
                )
                return {
                    "global_lore": {
                        "chapter_1_summary": "主角发现旧城钟楼藏有失落星图。",
                        "foreshadow_star_gate": "星门来源仍未揭开。",
                        "last_chapter_hook": "钟楼深处传来星门开启的回声。",
                    },
                    "character_graph": {"林澈": character_update},
                    "extracted_lore_updates": {
                        "chapter_1_summary": "主角发现旧城钟楼藏有失落星图。",
                        "foreshadow_star_gate": "星门来源仍未揭开。",
                        "last_chapter_hook": "钟楼深处传来星门开启的回声。",
                    },
                    "extracted_character_updates": {"林澈": character_update},
                    "current_stage": "extracting_lore",
                    "error_message": None,
                }

            with (
                patch.object(novel_graph, "memory_store", memory_store),
                patch.object(novel_graph, "librarian_agent", fake_librarian_agent),
            ):
                accepted_state = service.accept_chapter(session_id=session_id)

            items = memory_store.list_items(project_id)
            project = service.get_project(project_id)
            seed = project.next_chapter_input_snapshot
            self.assertEqual(accepted_state["current_stage"], "completed")
            self.assertTrue((tmp_path / "memory" / f"{project_id}.json").exists())
            self.assertTrue((tmp_path / "projects" / f"{project_id}.json").exists())
            self.assertTrue(items)
            self.assertTrue(any(item.category == "chapter_summary" for item in items))
            self.assertTrue(
                any("旧城钟楼藏有失落星图" in item.content for item in items)
            )
            self.assertIsNotNone(seed)
            self.assertEqual(seed.chapter_number, 2)
            self.assertIn("星门来源仍未揭开。", seed.unresolved_foreshadowing)
            self.assertEqual(seed.last_chapter_hook, "钟楼深处传来星门开启的回声。")
            self.assertTrue(seed.recommended_next_directions)
            self.assertEqual(project.lore_codex["foreshadow_star_gate"], "星门来源仍未揭开。")
            self.assertEqual(project.character_codex[0].name, "林澈")
            self.assertEqual(seed.current_character_state[0].name, "林澈")

    def test_project_catalog_recovers_from_json_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_store = JsonProjectStore(Path(tmp_dir))
            project_id = "project-recovery-test"
            first_service = novel_graph.NovelWorkflowService(store=project_store)

            def fake_planner_agent(_: NovelState) -> dict:
                return {
                    "current_plot_beats": [
                        PlotBeat(order=1, summary="主角发现钟楼星图的第一条线索。")
                    ],
                    "current_stage": "awaiting_human_review",
                    "human_approved": False,
                    "error_message": None,
                }

            with patch.object(novel_graph, "planner_agent", fake_planner_agent):
                session_id, state = first_service.plan_chapter(
                    project_id=project_id,
                    project_title="钟楼秘档",
                    global_worldview="旧城钟楼保存着失落星图。",
                    chapter_number=1,
                    characters=[],
                    user_instruction="生成一个稳定可保存的章节规划。",
                )

            self.assertEqual(state["current_stage"], "awaiting_human_review")
            self.assertTrue((Path(tmp_dir) / f"{project_id}.json").exists())

            second_service = novel_graph.NovelWorkflowService(store=project_store)
            recovered_project = second_service.get_project(project_id)

            self.assertEqual(recovered_project.project_id, project_id)
            self.assertEqual(recovered_project.title, "钟楼秘档")
            self.assertEqual(recovered_project.latest_session_id, session_id)
            self.assertEqual(len(recovered_project.chapters), 1)
            self.assertEqual(recovered_project.chapters[0].status, "planned")


if __name__ == "__main__":
    unittest.main()
