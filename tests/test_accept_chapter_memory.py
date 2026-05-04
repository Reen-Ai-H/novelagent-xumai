from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core import novel_graph
from app.core.memory import JsonMemoryStore
from app.models import ChapterDraft, NovelState, PlotBeat


class AcceptChapterMemoryTest(unittest.TestCase):
    def test_accept_chapter_writes_librarian_memory_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_id = "accept-memory-test"
            session_id = "session-accept-memory-test"
            store = JsonMemoryStore(Path(tmp_dir))
            service = novel_graph.NovelWorkflowService()
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
                return {
                    "global_lore": {
                        "chapter_1_summary": "主角发现旧城钟楼藏有失落星图。"
                    },
                    "character_graph": {},
                    "extracted_lore_updates": {
                        "chapter_1_summary": "主角发现旧城钟楼藏有失落星图。"
                    },
                    "extracted_character_updates": {},
                    "current_stage": "extracting_lore",
                    "error_message": None,
                }

            with (
                patch.object(novel_graph, "memory_store", store),
                patch.object(novel_graph, "librarian_agent", fake_librarian_agent),
            ):
                accepted_state = service.accept_chapter(session_id=session_id)

            items = store.list_items(project_id)
            self.assertEqual(accepted_state["current_stage"], "completed")
            self.assertTrue((Path(tmp_dir) / f"{project_id}.json").exists())
            self.assertTrue(items)
            self.assertTrue(any(item.category == "chapter_summary" for item in items))
            self.assertTrue(
                any("旧城钟楼藏有失落星图" in item.content for item in items)
            )


if __name__ == "__main__":
    unittest.main()
