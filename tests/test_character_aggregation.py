import unittest

from app.core.character_aggregation import CharacterReportSlice, aggregate_character_slices
from schemas.analysis_report import AnalysisReport


def _report(chapter: int, character: dict) -> AnalysisReport:
    change_text = character.pop("_change", "本阶段变化")
    claim = {
        "text": character.pop("_text", "本阶段判断"),
        "status": "inferred",
        "evidence_ids": [f"Q{chapter}"],
    }
    return AnalysisReport.model_validate(
        {
            "producer": "fake",
            "title": "测试",
            "scope": f"第{chapter}章",
            "chapter_numbers": [chapter],
            "findings": [{"id": f"F{chapter}", "title": "发现", **claim}],
            "characters": [
                {
                    **character,
                    "identity": claim,
                    "motivation": claim,
                    "change": {**claim, "text": change_text},
                }
            ],
            "events": [
                {
                    "id": f"E{chapter}",
                    "title": "事件",
                    "chapter_number": chapter,
                    "story_time": "当下",
                    "actor_ids": [character["id"]],
                    "action": claim,
                    "consequence": claim,
                }
            ],
            "relations": [],
            "story_order": [f"E{chapter}"],
            "time_note": "测试",
            "evidence": [{"id": f"Q{chapter}", "chapter_number": chapter, "quote": f"证据{chapter}"}],
            "open_questions": [],
        }
    )


class CharacterAggregationTest(unittest.TestCase):
    def test_stable_entity_key_keeps_all_stage_snapshots(self):
        first = _report(
            1,
            {
                "id": "C1",
                "entity_key": "wei-ying",
                "name": "魏婴",
                "aliases": ["夷陵老祖"],
                "role": "行动者",
                "_text": "前卷仍把退让当成保护。",
                "_change": "前卷变化",
            },
        )
        later = _report(
            2,
            {
                "id": "C9",
                "entity_key": "wei-ying",
                "name": "魏无羡",
                "aliases": ["魏婴"],
                "role": "行动者",
                "_text": "后卷开始为自己作决定。",
                "_change": "后卷变化",
            },
        )
        slices = [
            CharacterReportSlice("vol-02", 2, 2, later),
            CharacterReportSlice("vol-01", 1, 1, first),
        ]
        result = aggregate_character_slices(slices)
        self.assertEqual(len(result), 1)
        person = result[0]
        self.assertEqual(person.id, aggregate_character_slices(list(reversed(slices)))[0].id)
        self.assertEqual([stage.character_id for stage in person.stages], ["C1", "C9"])
        self.assertEqual(person.stages[0].change.text, "前卷变化")
        self.assertEqual(person.stages[1].change.text, "后卷变化")
        self.assertIn("魏无羡", person.aliases)

    def test_legacy_reports_merge_exact_name_alias_without_overwriting(self):
        first = _report(
            3,
            {
                "id": "C1",
                "name": "蓝二公子",
                "aliases": ["含光君"],
                "role": "同行者",
                "_text": "前卷卡片",
                "_change": "前卷状态",
            },
        )
        later = _report(
            4,
            {
                "id": "C2",
                "name": "含光君",
                "aliases": ["蓝二公子"],
                "role": "同行者",
                "_text": "后卷卡片",
                "_change": "后卷状态",
            },
        )
        result = aggregate_character_slices(
            [CharacterReportSlice("a", 3, 3, first), CharacterReportSlice("b", 4, 4, later)]
        )
        self.assertEqual(len(result), 1)
        self.assertEqual([stage.identity.text for stage in result[0].stages], ["前卷卡片", "后卷卡片"])
        self.assertEqual(result[0].name, "蓝二公子")

    def test_shared_only_alias_does_not_merge_two_people(self):
        first = _report(5, {"id": "C1", "name": "甲", "aliases": ["公子"], "role": "甲方"})
        later = _report(6, {"id": "C2", "name": "乙", "aliases": ["公子"], "role": "乙方"})
        result = aggregate_character_slices(
            [CharacterReportSlice("a", 5, 5, first), CharacterReportSlice("b", 6, 6, later)]
        )
        self.assertEqual(len(result), 2)

    def test_duplicate_stage_source_is_idempotent(self):
        report = _report(7, {"id": "C1", "name": "丙", "aliases": [], "role": "旁观者"})
        source = CharacterReportSlice("same-document", 7, 7, report)
        result = aggregate_character_slices([source, source])
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0].stages), 1)


if __name__ == "__main__":
    unittest.main()
