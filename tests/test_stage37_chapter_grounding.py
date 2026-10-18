"""Chapter identity/coverage protocol invariants; not an NLP entailment oracle."""
from copy import deepcopy
import json
import unittest

from app.agents.deconstruction_model import chapter_fact_messages, chapter_checked_messages
from app.core.chapter_preview import (ChapterFacts, ChapterOutcome, ChapterBlocked, freeze_chapter, chapter_index,
    bind_chapter_outcome, namespace_id, split_namespaced_id)
from chapter_preview_fixtures import chapter_case, add_before


class ChapterGroundingTest(unittest.TestCase):
    def setUp(self):
        self.packets, self.outcome, self.bank, self.texts = chapter_case()

    def frozen(self):
        return tuple(freeze_chapter(p, {k: v for k, v in self.bank.items() if v.chapter_number == p["chapter_number"]},
                                   {p["chapter_number"]: self.texts[p["chapter_number"]]}) for p in self.packets)

    def bind(self):
        return bind_chapter_outcome(self.outcome, self.frozen(), self.bank, self.texts, producer="synthetic")

    def support(self, key):
        return next(s for s in self.outcome["supports"] if s["key"] == key)

    def test_chapter_has_no_cues_can_have_zero_people_but_not_zero_atoms(self):
        packet = deepcopy(self.packets[0])
        packet["characters"] = []
        packet["atoms"][0]["subject_id"] = None
        frozen = freeze_chapter(packet, self.bank, {1: self.texts[1]})
        self.assertEqual(json.loads(frozen)["characters"], [])
        for bad in ({**packet, "cues": []}, {**packet, "atoms": []}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ChapterFacts.model_validate(bad, strict=True)

    def test_chapter_sources_cannot_borrow_another_chapter(self):
        self.packets[0]["atoms"][0]["source_ids"] = self.packets[1]["atoms"][0]["source_ids"]
        with self.assertRaises(ValueError):
            self.frozen()

    def test_namespace_is_reversible_bounded_and_collision_free(self):
        key = namespace_id(999999999, "A" + "_" * 47)
        self.assertLessEqual(len(key), 64)
        self.assertEqual(split_namespaced_id(key), (999999999, "A" + "_" * 47))
        _, people, atoms = chapter_index(self.frozen())
        self.assertEqual(set(people), {"H1_P", "H2_P"})
        self.assertEqual(set(atoms), {"H1_A", "H2_A"})
        for number, local in ((1, "A" * 49), (1000000000, "A"), (0, "A"), (True, "A")):
            with self.subTest(number=number), self.assertRaises(ValueError):
                namespace_id(number, local)

    def test_namespace_changes_only_id_fields_not_text_null_status_or_phase(self):
        before = deepcopy(self.packets)
        frozen = [json.loads(x) for x in self.frozen()]
        for original, packet in zip(before, frozen, strict=True):
            for first, second in zip(original["atoms"], packet["atoms"], strict=True):
                for key in first.keys() - {"id", "subject_id", "object_id"}:
                    self.assertEqual(first[key], second[key])
                self.assertIsNone(second["object_id"])
        self.assertEqual(self.packets, before)

    def test_local_id_reuse_does_not_auto_merge_same_names(self):
        report = self.bind()
        self.assertEqual([p.name for p in report.characters], ["林客", "林客"])
        self.assertEqual([p.id for p in report.characters], ["C1", "C2"])

    def test_explicit_sourced_merge_is_allowed_without_editing_facts(self):
        self.packets, self.outcome, self.bank, self.texts = chapter_case(merged=True)
        before = self.frozen()
        self.assertEqual(len(self.bind().characters), 1)
        self.assertEqual(before, self.frozen())

    def test_twenty_chapter_identity_sources_can_cover_all_members_without_clipping(self):
        self.packets, self.outcome, self.bank, self.texts = chapter_case(20, merged=True)
        self.assertEqual(len(self.outcome["entities"][0]["source_ids"]), 20)
        self.assertEqual(len(self.bind().characters), 1)

    def test_identity_mapping_rejects_omission_duplicate_and_foreign_member(self):
        original = deepcopy(self.outcome)
        for members in ([], ["H1_P", "H2_P"], ["Missing"]):
            self.outcome = deepcopy(original)
            self.outcome["entities"][0]["members"] = members
            with self.subTest(members=members), self.assertRaises(ValueError):
                self.bind()

    def test_merge_requires_sources_for_every_member(self):
        self.packets, self.outcome, self.bank, self.texts = chapter_case(merged=True)
        self.outcome["entities"][0]["source_ids"].pop()
        with self.assertRaisesRegex(ValueError, "覆盖每个成员"):
            self.bind()

    def test_unknown_name_or_alias_is_not_invented_by_unification(self):
        for field, value in (("name", "新人物"), ("aliases", ["新别名"])):
            original = deepcopy(self.outcome)
            self.outcome["entities"][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "姓名或别名无来源"):
                self.bind()
            self.outcome = original

    def test_hidden_participant_is_not_forced_into_card_or_borrowed_as_visible(self):
        self.packets, self.outcome, self.bank, self.texts = chapter_case(internal=True)
        self.assertEqual([p.id for p in self.bind().characters], ["C1"])
        self.outcome["report"]["events"][1]["actor_ids"] = ["C1"]
        with self.assertRaisesRegex(ValueError, "人物不在映射动作"):
            self.bind()

    def test_internal_entity_cannot_appear_as_a_report_card(self):
        self.outcome["entities"][1]["role"] = "internal"
        with self.assertRaisesRegex(ValueError, "人物偏离"):
            self.bind()

    def test_shown_actor_cannot_be_silently_omitted(self):
        self.outcome["report"]["events"][0]["actor_ids"] = []
        with self.assertRaisesRegex(ValueError, "行动主体缺漏"):
            self.bind()

    def test_null_endpoint_cannot_become_an_actor_by_name_matching(self):
        self.packets[0]["atoms"][0]["subject_id"] = None
        with self.assertRaisesRegex(ValueError, "人物不在映射动作"):
            self.bind()

    def test_null_endpoint_cannot_support_another_person_claim_even_with_unknown_status(self):
        self.packets[0]["atoms"][0]["subject_id"] = None
        self.outcome["report"]["events"][0]["actor_ids"] = []
        self.outcome["report"]["characters"][0]["identity"]["status"] = "unknown"
        with self.assertRaisesRegex(ValueError, "主体与映射"):
            self.bind()

    def test_null_object_cannot_become_character_edge(self):
        self.outcome["cues"] = [{"id": "Rel", "kind": "character", "from_atom_id": "H1_A", "to_atom_id": None,
            "text": "不能把未定对象认定为另一人。", "status": "unknown", "source_ids": self.packets[0]["atoms"][0]["source_ids"]}]
        with self.assertRaisesRegex(ValueError, "明确有向人物"):
            self.bind()

    def test_report_actual_quote_cannot_be_swapped_for_other_chapter(self):
        self.outcome["report"]["events"][0]["action"]["evidence_ids"] = ["Q2"]
        with self.assertRaisesRegex(ValueError, "实际引文"):
            self.bind()

    def test_phase_metadata_cannot_change_even_when_status_is_lowered(self):
        self.support("E1.action")["phases"] = ["planned"]
        self.outcome["report"]["events"][0]["action"]["status"] = "unknown"
        with self.assertRaisesRegex(ValueError, "阶段偏离"):
            self.bind()

    def test_fact_purpose_with_planned_target_can_remain_sourced_unresolved(self):
        self.packets, self.outcome, self.bank, self.texts = chapter_case(merged=True, planned=True, texts={
            1: "第1日，林客出门，拟在第2日到第二处渡口等候。",
            2: "第2日，前章同一位林客计划在第二处渡口等候，但尚未等到人。"})
        reason = "出门的目的确实被说出，但等候仍是计划，不断言目标已完成。"
        self.outcome["cues"] = [{"id": "Plan", "kind": "purpose", "from_atom_id": "H1_A", "to_atom_id": "H2_A",
            "text": reason, "status": "fact", "source_ids": self.packets[0]["atoms"][0]["source_ids"]}]
        self.outcome["cue_resolutions"] = [{"cue_id": "Plan", "target": None, "reason": reason}]
        self.outcome["report"]["open_questions"] = [reason]
        self.outcome["questions"] = [{"index": 0, "fact_ids": ["H2_A"], "evidence_ids": ["Q2"], "phases": ["planned"]}]
        self.outcome["report"]["story_order"] = ["E2", "E1"]
        report = self.bind()
        self.assertEqual(report.relations, [])
        self.assertEqual(self.outcome["cues"][0]["status"], "fact")
        self.assertEqual(json.loads(self.frozen()[1])["atoms"][0]["phase"], "planned")
        self.support("E2.action")["phases"] = ["actual"]
        with self.assertRaisesRegex(ValueError, "阶段偏离"):
            self.bind()

    def object_identity_case(self):
        self.packets, self.outcome, self.bank, self.texts = chapter_case(texts={
            1: "第1日，林客收许守为徒，并在第一处渡口等候。", 2: "第2日，林客在第二处渡口等候。"})
        source_ids = self.packets[0]["atoms"][0]["source_ids"]
        self.packets[0]["characters"].append({"id": "Student", "name": "许守", "aliases": [], "source_ids": source_ids})
        self.packets[0]["atoms"][0]["object_id"] = "Student"
        self.outcome["entities"].append({"id": "Student", "members": ["H1_Student"], "name": "许守", "aliases": [],
            "role": "support", "basis": "本章明确收徒关系中的宾语。", "source_ids": source_ids})
        card = deepcopy(self.outcome["report"]["characters"][0])
        card.update(id="Student", name="许守", role="配角")
        for field in ("identity", "motivation", "change"):
            self.outcome["supports"].append({"key": f"Student.{field}", "fact_ids": ["H1_A"], "phases": ["actual"]})
        self.outcome["report"]["characters"].append(card)

    def test_object_view_identity_needs_no_duplicate_inverse_atom_in_chapter_flow(self):
        self.object_identity_case()
        self.assertEqual(self.bind().characters[-1].name, "许守")

    def test_mental_holder_cannot_be_transferred_to_known_object_in_chapter_flow(self):
        self.object_identity_case()
        self.packets[0]["atoms"][0]["kind"] = "knowledge"
        with self.assertRaisesRegex(ValueError, "知情或情感只能属于冻结持有者"):
            self.bind()

    def test_cross_chapter_before_and_reverse_order(self):
        add_before(self.outcome)
        self.bind()
        self.outcome["report"]["story_order"] = ["E2", "E1"]
        with self.assertRaisesRegex(ValueError, "顺序倒置"):
            self.bind()

    def test_cross_chapter_edge_cannot_reverse_atom_endpoints(self):
        add_before(self.outcome)
        self.outcome["report"]["relations"][0].update(from_id="E2", to_id="E1")
        with self.assertRaisesRegex(ValueError, "动作端点或方向"):
            self.bind()

    def test_atomic_dependency_cycle_is_rejected_before_report_binding(self):
        add_before(self.outcome)
        self.outcome["cues"].append({**self.outcome["cues"][0], "id": "T21", "from_atom_id": "H2_A", "to_atom_id": "H1_A"})
        with self.assertRaisesRegex(ValueError, "循环"):
            self.bind()

    def test_important_atom_needs_actual_claim_not_only_event_binding(self):
        self.packets[1]["atoms"].append({**self.packets[1]["atoms"][0], "id": "Uncovered"})
        self.outcome["event_bindings"][1]["atom_ids"].append("H2_Uncovered")
        with self.assertRaisesRegex(ValueError, "实际报告或未解项落点"):
            self.bind()

    def question_case(self):
        self.outcome["report"]["events"].pop()
        self.outcome["report"]["story_order"].pop()
        self.outcome["event_bindings"].pop()
        self.outcome["supports"] = [s for s in self.outcome["supports"] if not s["key"].startswith("E2.")]
        for support in self.outcome["supports"]:
            if support["key"].startswith("C2."):
                support.update(fact_ids=["H2_P"], phases=[])
        self.outcome["report"]["open_questions"] = ["第二章等候的后续尚未交代，保留本章原事实。"]
        self.outcome["questions"] = [{"index": 0, "fact_ids": ["H2_A"], "evidence_ids": ["Q2"], "phases": ["actual"]}]

    def test_sourced_actual_question_is_a_real_atom_landing(self):
        self.question_case()
        self.assertEqual(len(self.bind().open_questions), 1)

    def test_questions_require_actual_index_quote_and_phase(self):
        self.question_case()
        original = deepcopy(self.outcome)
        for field, value in (("index", 1), ("evidence_ids", ["Q1"]), ("phases", ["planned"]), ("fact_ids", ["Missing"])):
            self.outcome = deepcopy(original)
            self.outcome["questions"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.bind()

    def test_cannot_claim_all_questions_without_any_real_event_fact(self):
        for support in self.outcome["supports"]:
            if support["key"].startswith("E"):
                support.update(fact_ids=["H1_P"], phases=[])
        with self.assertRaisesRegex(ValueError, "事件字段"):
            self.bind()

    def test_blocked_is_strictly_exclusive_with_success_and_needs_nonempty_issues(self):
        blocked = {"outcome": "blocked", "issues": [{"text": "本章缺少主体依据。", "source_ids": self.packets[0]["atoms"][0]["source_ids"]}]}
        self.outcome = blocked
        self.assertIsInstance(self.bind(), ChapterBlocked)
        for bad in ({**blocked, "report": {}}, {"outcome": "blocked", "issues": []},
                    {"outcome": "blocked", "issues": blocked["issues"], "entities": []}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ChapterOutcome.model_validate(bad, strict=True)

    def test_blocked_bad_sources_and_unknown_fact_ids_are_rejected(self):
        for source, fact in (("S99_" + "0" * 20, []), (next(iter(self.bank)), ["Missing"])):
            self.outcome = {"outcome": "blocked", "issues": [{"text": "具体主体错归。", "source_ids": [source], "fact_ids": fact}]}
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.bind()

    def test_global_supported_id_collisions_are_rejected(self):
        self.outcome["entities"][0]["id"] = "H1_A"
        with self.assertRaisesRegex(ValueError, "全局支持ID冲突"):
            self.bind()

    def test_per_chapter_and_aggregate_limits_reject_without_clipping(self):
        packet = deepcopy(self.packets[0])
        packet["atoms"] = [{**packet["atoms"][0], "id": f"A{i}"} for i in range(151)]
        with self.assertRaises(ValueError):
            ChapterFacts.model_validate(packet, strict=True)
        large = []
        for n in range(1, 6):
            packet = deepcopy(self.packets[0])
            packet["chapter_number"] = n
            packet["atoms"] = [{**packet["atoms"][0], "id": f"A{i}"} for i in range(150)]
            text = {n: self.texts[1]}
            from app.core.analysis_grounding import source_bank
            bank = source_bank(text)
            for item in [*packet["characters"], *packet["atoms"]]:
                item["source_ids"] = [next(iter(bank))]
            large.append(freeze_chapter(packet, bank, text))
        with self.assertRaisesRegex(ValueError, "合计结构超界"):
            chapter_index(tuple(large))

    def test_actual_messages_keep_local_scope_and_global_same_complete_text(self):
        frozen = self.frozen()
        for packet in self.packets:
            n = packet["chapter_number"]
            chapter = {"chapter_number": n, "title": f"合成{n}", "content": self.texts[n]}
            messages = chapter_fact_messages(chapter, {k: p for k, p in self.bank.items() if p.chapter_number == n})
            material = json.loads(messages[1]["content"].split("\n", 1)[1])
            self.assertEqual([c["chapter_number"] for c in material["chapters"]], [n])
            self.assertEqual("".join(s["text"] for s in material["chapters"][0]["segments"]), self.texts[n])
            self.assertNotIn(self.texts[n], messages[0]["content"])
        messages = chapter_checked_messages([{"chapter_number": n, "content": text} for n, text in self.texts.items()], self.bank, frozen)
        material = json.loads(messages[1]["content"].split("\n", 1)[1])
        self.assertEqual(material["chapter_facts"], [json.loads(x) for x in frozen])
        self.assertEqual(["".join(s["text"] for s in c["segments"]) for c in material["chapters"]], list(self.texts.values()))

    def test_active_prompt_contracts_do_not_hide_null_omissions_or_core_people(self):
        facts = chapter_fact_messages({"chapter_number": 1, "content": self.texts[1]},
            {key: value for key, value in self.bank.items() if value.chapter_number == 1})[0]["content"]
        final = chapter_checked_messages([], {}, self.frozen())[0]["content"]
        for rule in ("不带引号的JSON null", "knowledge/feeling", "不沿用相邻章节", "不删掩护亲属", "最多48字符"):
            self.assertIn(rule, facts)
        for rule in ("反查原文", "不得同时返回report", "不能靠标internal隐藏", "整条atom有一个映射不证明关键分句全部保留",
                     "status/phase与null端点不可变", "两个不同有效原子事实", "不得以空cues/空边或统称未决回避"):
            self.assertIn(rule, final)
