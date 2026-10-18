"""Two real provider boundaries, compact witnesses and synthetic structural counterexamples.

No assertion treats matching words or an attachment as proof of entailment.
"""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from app import deconstruction_routes
from app.agents import deconstruction_model
from app.core.analysis_grounding import source_bank
from app.core.model_budget import estimate_structured_call_bound
from app.core.model_call_budget import DurableModelBudget
from app.core.preview_analysis import PreviewFacts, PreviewCheckedReport, freeze_preview_facts, bind_checked_preview
import test_stage32_analysis_import as fixtures


def structural_example(sentences=None):
    sentences = sentences or ["陈师收林生为徒。", "林生请命查仓。", "林生离营，为清点库房腾出地方。",
                             "清点者计划清点库房。", "林生归营，查仓仍未完成。", "林生暗恋卫宁，卫宁并不知情。"]
    texts = {1: "".join(sentences)}
    bank = source_bank(texts)
    keys = [next(p.id for p in bank.values() if p.quote == text) for text in sentences]
    people = [{"id": key, "name": name, "aliases": [], "source_ids": [keys[n]]}
              for key, name, n in (("Master", "陈师", 0), ("Student", "林生", 0), ("Friend", "卫宁", 5))]

    def atom(key, subject, obj, n, *, phase="actual", kind="action", status="fact"):
        return {"id": key, "subject_id": subject, "object_id": obj, "text": sentences[n], "kind": kind,
                "phase": phase, "status": status, "time_anchor": "当下", "source_ids": [keys[n]]}

    atoms = [atom("Teach", "Master", "Student", 0), atom("Ask", "Student", None, 1, phase="requested"),
             atom("Leave", "Student", None, 2), atom("Clear", None, None, 3, phase="planned"),
             atom("Return", "Student", None, 4), atom("Unfinished", "Student", None, 4, phase="negated"),
             atom("Love", "Student", "Friend", 5, kind="feeling"),
             atom("Unaware", "Friend", "Student", 5, kind="knowledge", phase="negated")]

    def cue(key, kind, first, second, n):
        return {"id": key, "kind": kind, "from_atom_id": first, "to_atom_id": second,
                "text": sentences[n], "status": "fact", "source_ids": [keys[n]]}

    cues = [cue("TAsk", "before", "Ask", "Leave", 2), cue("TBack", "before", "Leave", "Return", 4),
            cue("PClear", "purpose", "Leave", "Clear", 2), cue("CTeach", "character", "Teach", None, 0),
            cue("CLove", "character", "Love", None, 5)]
    facts = {"chapter_numbers": [1], "characters": people, "atoms": atoms, "cues": cues}
    evidence = [{"id": f"Q{n}", "source_id": key} for n, key in enumerate(keys)]
    supports = []
    atom_map = {a["id"]: a for a in atoms}
    all_facts = {a["id"]: a for a in [*people, *atoms, *cues]}

    def claim(key, ids, text=None):
        supports.append({"key": key, "fact_ids": ids, "phases": sorted({atom_map[i]["phase"] for i in ids if i in atom_map})})
        selected = {s for i in ids for s in all_facts[i]["source_ids"]}
        return {"text": text or all_facts[ids[0]].get("text", "身份有据。"), "status": "fact",
                "evidence_ids": [e["id"] for e in evidence if e["source_id"] in selected]}

    characters = []
    for person, fact in zip(people, ("Teach", "Teach", "Unaware"), strict=True):
        characters.append({"id": person["id"], "name": person["name"], "aliases": [], "role": "人物",
            **{field: claim(f"{person['id']}.{field}", [fact]) for field in ("identity", "motivation", "change")}})
    events = []
    bindings = []
    for key, ids in (("Request", ["Ask"]), ("Journey", ["Leave", "Clear"]), ("Home", ["Return", "Unfinished"])):
        events.append({"id": key, "title": key, "story_time": "当下", "actor_ids": ["Student"],
            "action": claim(key + ".action", [ids[0]]), "consequence": claim(key + ".consequence", [ids[-1]]), "sub_events": []})
        bindings.append({"event_id": key, "atom_ids": ids})
    relations = [{"from_id": start, "to_id": end, "kind": "follows", **claim(f"r{n}", ids)}
                 for n, (start, end, ids) in enumerate((
                     ("Request", "Journey", ["TAsk", "Ask", "Leave"]),
                     ("Journey", "Home", ["TBack", "Leave", "Return"])))]
    character_relations = [
        {"from_id": "Master", "to_id": "Student", "label": "师父", **claim("cr0", ["CTeach", "Teach"])},
        {"from_id": "Student", "to_id": "Friend", "label": "单方倾慕", **claim("cr1", ["CLove", "Love"])}]
    finding = {"id": "Finding", "title": "尚未完成", **claim("Finding", ["Unfinished"])}
    reason = "目标尚属计划，不能据此断言已经发生。"
    report = {"title": "合成核对", "scope": "一章", "chapter_numbers": [1], "findings": [finding],
        "characters": characters, "events": events, "relations": relations, "character_relations": character_relations,
        "story_order": ["Request", "Journey", "Home"], "time_note": "请命、离开、归返分开；任务完成未证实。",
        "evidence": evidence, "open_questions": [reason]}
    checked = {"report": report, "supports": supports, "event_bindings": bindings,
        "edge_bindings": [{"key": key, "cue_id": cue_id} for key, cue_id in
                          (("r0", "TAsk"), ("r1", "TBack"), ("cr0", "CTeach"), ("cr1", "CLove"))],
        "cue_resolutions": [{"cue_id": c["id"], "target": target, "reason": reason if target is None else None}
                            for c, target in zip(cues, ("r0", "r1", None, "cr0", "cr1"), strict=True)]}
    return facts, checked, bank, texts


class TwoPassWitnessTest(unittest.TestCase):
    def setUp(self):
        self.facts, self.checked, self.bank, self.texts = structural_example()

    def bind(self):
        frozen = freeze_preview_facts(self.facts, self.bank, self.texts)
        return bind_checked_preview(self.checked, frozen, self.bank, self.texts, producer="synthetic")

    def support(self, key):
        return next(s for s in self.checked["supports"] if s["key"] == key)

    def test_two_schemas_strict_and_public_report_unchanged(self):
        self.assertEqual(self.bind().producer, "synthetic")
        for model, data in ((PreviewFacts, self.facts), (PreviewCheckedReport, self.checked)):
            with self.subTest(model=model.__name__), self.assertRaises(ValueError):
                model.model_validate({**data, "untrusted_extra": True}, strict=True)
        bad = deepcopy(self.facts)
        bad["chapter_numbers"] = ["1"]
        with self.assertRaises(ValueError):
            freeze_preview_facts(bad, self.bank, self.texts)

    def test_actual_report_quote_cannot_borrow_another_valid_source(self):
        self.checked["report"]["events"][0]["action"]["evidence_ids"] = ["Q4"]
        with self.assertRaisesRegex(ValueError, "实际引文"):
            self.bind()

    def test_actual_report_must_cover_each_mapped_fact_not_just_union(self):
        self.checked["report"]["events"][2]["consequence"]["evidence_ids"] = ["Q4"]
        self.support("Home.consequence")["fact_ids"].append("Leave")
        self.support("Home.consequence")["phases"].append("actual")
        self.checked["event_bindings"][2]["atom_ids"].append("Leave")
        with self.assertRaisesRegex(ValueError, "实际引文未覆盖"):
            self.bind()

    def test_name_id_and_alias_each_remain_frozen(self):
        for field, value in (("name", "另一个名字"), ("aliases", ["新别名"]), ("id", "SomebodyElse")):
            with self.subTest(field=field):
                original = deepcopy(self.checked)
                self.checked["report"]["characters"][0][field] = value
                with self.assertRaises(ValueError):
                    self.bind()
                self.checked = original

    def test_object_view_of_student_identity_is_legal_without_duplicate_atom(self):
        self.assertEqual(self.support("Student.identity")["fact_ids"], ["Teach"])
        self.assertEqual(self.bind().characters[1].name, "林生")

    def test_unrelated_third_person_cannot_borrow_identity(self):
        self.support("Friend.identity").update(fact_ids=["Teach"], phases=["actual"])
        self.checked["report"]["characters"][2]["identity"]["evidence_ids"] = ["Q0"]
        with self.assertRaisesRegex(ValueError, "主体与映射"):
            self.bind()

    def test_reverse_character_endpoint_is_rejected(self):
        self.checked["report"]["character_relations"][0].update(from_id="Student", to_id="Master")
        with self.assertRaisesRegex(ValueError, "身份或方向"):
            self.bind()

    def test_single_feeling_is_not_structurally_shared_knowledge(self):
        self.checked["report"]["character_relations"][1].update(from_id="Friend", to_id="Student")
        with self.assertRaisesRegex(ValueError, "身份或方向"):
            self.bind()

    def test_knowledge_feeling_and_action_tags_survive_stage_boundary(self):
        frozen = freeze_preview_facts(self.facts, self.bank, self.texts)
        material = deconstruction_model.preview_checked_messages([], {}, frozen)[1]["content"]
        packet = json.loads(material.split("\n", 1)[1])["facts"]
        self.assertEqual(packet, self.facts)
        atoms = {a["id"]: a for a in packet["atoms"]}
        self.assertEqual((atoms["Love"]["kind"], atoms["Unaware"]["kind"]), ("feeling", "knowledge"))
        self.assertEqual((atoms["Ask"]["phase"], atoms["Unfinished"]["phase"]), ("requested", "negated"))

    def test_fact_status_does_not_turn_plan_into_actual_phase(self):
        self.assertEqual(self.facts["atoms"][3]["status"], "fact")
        self.assertEqual(self.facts["atoms"][3]["phase"], "planned")
        self.support("Journey.consequence")["phases"] = ["actual"]
        with self.assertRaisesRegex(ValueError, "阶段偏离"):
            self.bind()

    def test_lower_status_cannot_hide_changed_phase(self):
        self.checked["report"]["events"][1]["consequence"]["status"] = "inferred"
        self.support("Journey.consequence")["phases"] = ["actual"]
        with self.assertRaisesRegex(ValueError, "阶段偏离"):
            self.bind()

    def test_reported_cannot_be_elevated_to_fact(self):
        self.facts["atoms"][0]["status"] = "reported"
        with self.assertRaisesRegex(ValueError, "提升为事实"):
            self.bind()

    def test_known_dependency_cannot_be_reversed_or_lost(self):
        self.checked["report"]["story_order"] = ["Home", "Journey", "Request"]
        with self.assertRaisesRegex(ValueError, "顺序倒置"):
            self.bind()

    def test_return_cannot_replace_departure_as_the_link_action(self):
        self.checked["report"]["relations"][0]["to_id"] = "Home"
        with self.assertRaisesRegex(ValueError, "动作端点或方向"):
            self.bind()

    def test_cyclic_local_dependencies_fail_before_second_stage(self):
        self.facts["cues"].append({**self.facts["cues"][0], "id": "Cycle", "from_atom_id": "Return", "to_atom_id": "Ask"})
        with self.assertRaisesRegex(ValueError, "循环"):
            freeze_preview_facts(self.facts, self.bank, self.texts)

    def test_missing_or_foreign_support_is_rejected(self):
        self.checked["supports"].pop()
        with self.assertRaisesRegex(ValueError, "字段映射缺漏"):
            self.bind()

    def test_unknown_fact_source_fails_before_second_stage(self):
        self.facts["atoms"][0]["source_ids"] = ["S1_" + "0" * 20]
        with self.assertRaisesRegex(ValueError, "未提供的来源"):
            freeze_preview_facts(self.facts, self.bank, self.texts)

    def test_all_clear_relationships_cannot_be_deleted(self):
        self.checked["report"]["relations"] = []
        self.checked["edge_bindings"] = [b for b in self.checked["edge_bindings"] if b["key"].startswith("cr")]
        self.checked["supports"] = [s for s in self.checked["supports"] if not s["key"].startswith("r")]
        self.checked["cue_resolutions"][0].update(target=None, reason="没有关系")
        self.checked["cue_resolutions"][1].update(target=None, reason="没有关系")
        with self.assertRaisesRegex(ValueError, "空关系回避"):
            self.bind()

    def test_genuinely_unknown_order_allows_reason_and_preserves_known_dependency(self):
        self.facts["cues"][0]["status"] = "unknown"
        self.checked["report"]["relations"].pop(0)
        self.checked["edge_bindings"].pop(0)
        self.checked["edge_bindings"][0]["key"] = "r0"
        self.checked["supports"] = [s for s in self.checked["supports"] if s["key"] != "r0"]
        self.support("r1")["key"] = "r0"
        self.checked["cue_resolutions"][0].update(target=None, reason="Request与Journey先后未定")
        self.checked["cue_resolutions"][1]["target"] = "r0"
        self.checked["report"]["time_note"] += "Request与Journey先后未定"
        self.checked["report"]["story_order"] = ["Journey", "Request", "Home"]
        self.bind()
        self.checked["report"]["story_order"] = ["Home", "Request", "Journey"]
        with self.assertRaisesRegex(ValueError, "顺序倒置"):
            self.bind()

    def test_fact_purpose_with_unfinished_target_allows_reason_without_actual_edge(self):
        self.assertEqual(self.facts["cues"][2]["status"], "fact")
        self.bind()

    def test_borrow_departure_to_plan_rescue_but_not_yet_succeed_is_not_actual_causation(self):
        self.facts, self.checked, self.bank, self.texts = structural_example([
            "陈师收林生为徒。", "林生请命查仓。", "林生借出门拟救人。",
            "林生计划救人，但尚未救成。", "林生归营，查仓仍未完成。", "林生暗恋卫宁，卫宁并不知情。"])
        self.facts["atoms"][3]["subject_id"] = "Student"
        for phase in ("planned", "requested", "negated", "unknown"):
            with self.subTest(phase=phase):
                self.facts["atoms"][3]["phase"] = phase
                self.support("Journey.consequence")["phases"] = [phase]
                self.bind()
                self.checked["report"]["events"][1]["consequence"]["status"] = "inferred"
                self.support("Journey.consequence")["phases"] = ["actual"]
                with self.assertRaisesRegex(ValueError, "阶段偏离"):
                    self.bind()
                self.checked["report"]["events"][1]["consequence"]["status"] = "fact"

    def test_unknown_purpose_cannot_silently_disappear(self):
        self.checked["report"]["open_questions"] = []
        with self.assertRaisesRegex(ValueError, "保留理由"):
            self.bind()

    def test_grouped_scene_covers_internal_purpose_without_splitting_every_atom(self):
        self.checked["cue_resolutions"][2].update(target="Journey", reason=None)
        self.support("Journey.consequence").update(fact_ids=["Leave", "Clear", "PClear"], phases=["actual", "planned"])
        self.checked["report"]["events"][1]["consequence"]["evidence_ids"] = ["Q2", "Q3"]
        self.assertEqual(len(self.bind().events), 3)
        self.assertEqual(len(self.facts["atoms"]), 8)

    def test_plan_does_not_impose_actual_chronology_but_actual_purpose_does(self):
        # A separate planned target may be displayed ahead of the departure;
        # no completed-target chronology follows merely from stated purpose.
        journey = self.checked["report"]["events"][1]
        target = deepcopy(journey)
        target.update(id="Plan", actor_ids=[])
        target["action"] = deepcopy(journey["consequence"])
        self.checked["report"]["events"].append(target)
        self.checked["event_bindings"][1]["atom_ids"] = ["Leave"]
        self.checked["event_bindings"].append({"event_id": "Plan", "atom_ids": ["Clear"]})
        journey["consequence"] = deepcopy(journey["action"])
        self.support("Journey.consequence").update(fact_ids=["Leave"], phases=["actual"])
        self.checked["supports"].extend([{"key": "Plan.action", "fact_ids": ["Clear"], "phases": ["planned"]},
                                        {"key": "Plan.consequence", "fact_ids": ["Clear"], "phases": ["planned"]}])
        self.checked["report"]["story_order"] = ["Plan", "Request", "Journey", "Home"]
        self.bind()
        self.facts["atoms"][3]["phase"] = "actual"
        self.support("Plan.action")["phases"] = ["actual"]
        self.support("Plan.consequence")["phases"] = ["actual"]
        # Actual purposes must be covered, unlike a still-unfulfilled plan.
        self.checked["cue_resolutions"][2].update(target="r2", reason=None)
        self.checked["edge_bindings"].append({"key": "r2", "cue_id": "PClear"})
        self.checked["supports"].append({"key": "r2", "fact_ids": ["PClear", "Leave", "Clear"], "phases": ["actual"]})
        self.checked["report"]["relations"].append({"from_id": "Journey", "to_id": "Plan", "kind": "enables",
            "text": "实际调离促成实际清点。", "status": "fact", "evidence_ids": ["Q2", "Q3"]})
        with self.assertRaisesRegex(ValueError, "顺序倒置"):
            self.bind()

    def test_original_facts_and_checked_output_are_never_rewritten(self):
        before = deepcopy((self.facts, self.checked))
        self.bind()
        self.assertEqual((self.facts, self.checked), before)


class TwoPassApiTest(unittest.TestCase):
    setUp = fixtures.AnalysisImportTest.setUp
    _cleanup = fixtures.AnalysisImportTest._cleanup
    _login = fixtures.AnalysisImportTest._login
    _project = fixtures.AnalysisImportTest._project
    _start_and_save = fixtures.AnalysisImportTest._start_and_save
    _complete_and_process = fixtures.AnalysisImportTest._complete_and_process
    prepare = fixtures.AnalysisImportTest.prepare

    def run_preview(self, packets, *, hook=None, cap=2):
        self.project, _ = self.prepare()
        facts, checked = fixtures.preview_pair(fixtures.preview_selector_report(self.payload["report"]))
        replies = iter(packets(facts, checked))
        calls, reservations = [], []
        budget = DurableModelBudget(self.deconstruction.store.base_dir / "two-pass", budget_cny=cap)
        self.deconstruction.model_budget = budget
        runtime = deconstruction_model.create_runtime(deconstruction_model.DeconstructionModelSettings(
            _env_file=None, api_key="synthetic-only", base_url="https://offline.invalid/v1"))

        def transport(url, headers, body, timeout):
            call = json.loads(body)
            calls.append(call)
            reservations.append(budget.public(runtime.model))
            if hook:
                hook(len(calls), budget, runtime)
            return 200, json.dumps({"choices": [{"message": {"content": json.dumps(next(replies))}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}}).encode()

        runtime._transport = transport
        body = {k: v for k, v in self.payload.items() if k != "report"}
        body["chapter_numbers"] = [1]
        before = self.deconstruction.store.load(self.project).model_dump(mode="json")
        with patch.object(deconstruction_routes, "create_runtime", return_value=runtime):
            response = self.client.post(self.url + "/analyze-preview", json=body)
        self.assertEqual(self.deconstruction.store.load(self.project).model_dump(mode="json"), before)
        return response, calls, reservations, budget

    def test_normal_two_requests_and_maximum_four_including_both_repairs(self):
        response, calls, _, budget = self.run_preview(lambda facts, checked: [{}, facts, {}, checked])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(calls), 4)
        records = json.loads(budget.path.read_text())["records"]
        self.assertEqual([r["stage"].split(":")[-1] for r in records], ["facts", "format-repair", "checked", "format-repair"])
        self.assertEqual(budget.public("mimo-v2.6-pro")["calls"], 4)

    def test_second_stage_repair_reserves_its_entire_growing_input(self):
        def packets(facts, checked):
            invalid = {**deepcopy(checked), "extra": "较长但不可信的失败候选" * 400}
            return [facts, invalid, checked]
        response, calls, holds, budget = self.run_preview(packets)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(calls), 3)
        self.assertGreater(holds[2]["reserved_cny"], holds[1]["reserved_cny"])
        records = json.loads(budget.path.read_text())["records"]
        for call, record in zip(calls, records, strict=True):
            system = call["messages"][0]["content"]
            prefix, schema_text = system.rsplit("\n\n只返回一个 JSON 对象，严格符合以下 schema，不要 Markdown 或解释：", 1)
            schema = json.loads(schema_text)
            messages = deepcopy(call["messages"])
            messages[0]["content"] = prefix
            messages.append({"role": "system", "content": json.dumps(schema, ensure_ascii=False)})
            bound = estimate_structured_call_bound(messages, 12288, model="mimo-v2.6-pro", attempts=1)
            self.assertAlmostEqual(record["reserved_cny"], bound, places=12)

    def test_first_fact_reference_failure_stops_without_semantic_retry(self):
        def packets(facts, checked):
            facts["atoms"][0]["subject_id"] = "Unrelated"
            return [facts]
        response, calls, _, _ = self.run_preview(packets)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(len(calls), 1)

    def test_first_stage_two_format_failures_never_start_report_stage(self):
        response, calls, _, _ = self.run_preview(lambda facts, checked: [{}, {}])
        self.assertEqual(response.status_code, 502, response.text)
        self.assertEqual(len(calls), 2)

    def test_second_stage_budget_refusal_does_not_send_or_reset_first_call(self):
        def drain(n, budget, runtime):
            if n == 1:
                ledger = budget._load(runtime.model)
                ledger.spent_cny = ledger.budget_cny - sum(ledger.pending_attempts.values()) - 0.001
                budget._save(ledger, budget._records())
        response, calls, _, budget = self.run_preview(lambda facts, checked: [facts, checked], hook=drain)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(len(calls), 1)
        state = budget.public("mimo-v2.6-pro")
        self.assertEqual((state["calls"], state["reserved_cny"]), (1, 0))
        self.assertLess(state["remaining_cny"], 0.2)
        self.assertEqual(DurableModelBudget(budget.directory, budget_cny=10).public("mimo-v2.6-pro"), state)

    def test_second_mapping_failure_stops_without_semantic_retry(self):
        def packets(facts, checked):
            checked["supports"].pop()
            return [facts, checked]
        response, calls, _, _ = self.run_preview(packets)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(len(calls), 2)

    def test_source_change_between_stages_refuses_second_http(self):
        def change(n, budget, runtime):
            if n == 1:
                record = self.independent.store.load(self.project)
                version = next(v for v in record.versions if v.version_id == record.active_version_id)
                version.chapters[0].formal_content += "后来新增的合成正文。"
                version.chapters[0].server_revision += 1
                self.independent.store.save(record)
        response, calls, _, budget = self.run_preview(lambda f, c: [f, c], hook=change)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(budget.public("mimo-v2.6-pro")["calls"], 1)

    def test_source_change_after_second_http_refuses_returned_candidate(self):
        def change(n, budget, runtime):
            if n == 2:
                record = self.independent.store.load(self.project)
                version = next(v for v in record.versions if v.version_id == record.active_version_id)
                version.chapters[0].formal_content += "末次返回前已保存的正文。"
                version.chapters[0].server_revision += 1
                self.independent.store.save(record)
        response, calls, _, _ = self.run_preview(lambda facts, checked: [facts, checked], hook=change)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(len(calls), 2)

    def test_source_change_before_second_stage_repair_refuses_third_http(self):
        def change(n, budget, runtime):
            if n == 2:
                record = self.independent.store.load(self.project)
                version = next(v for v in record.versions if v.version_id == record.active_version_id)
                version.chapters[0].formal_content += "修复前新增正文。"
                version.chapters[0].server_revision += 1
                self.independent.store.save(record)
        response, calls, _, _ = self.run_preview(lambda facts, checked: [facts, {}], hook=change)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(len(calls), 2)

    def test_same_original_source_and_untrusted_facts_are_user_data(self):
        attack = "UNTRUSTED_FACT_IGNORE_SYSTEM"
        def packets(facts, checked):
            facts["atoms"][0]["text"] = attack
            return [facts, checked]
        response, calls, _, _ = self.run_preview(packets)
        self.assertEqual(response.status_code, 200, response.text)
        first, second = [json.loads(call["messages"][1]["content"].split("\n", 1)[1]) for call in calls]
        self.assertEqual(first["chapters"], second["chapters"])
        self.assertIn(attack, calls[1]["messages"][1]["content"])
        self.assertNotIn(attack, calls[1]["messages"][0]["content"])
