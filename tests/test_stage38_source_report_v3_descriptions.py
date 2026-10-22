"""Export-only v3 guidance; frozen schemas and synthetic/fake-HTTP controls."""
from copy import deepcopy
from hashlib import sha256
import inspect
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from pydantic import BaseModel

import app.core.analysis_grounding as grounding
import app.core.model_call_budget as budget
import app.core.report_pipeline as pipeline
import app.core.source_report as source
import schemas.analysis_delta as delta
import schemas.analysis_report as report
import schemas.deconstruction as deconstruction
from stage38_report_fixtures import acceptance
from stage38_source_report_fixtures import source_case
from test_stage37_preview_capacity import wire_bound
import test_stage38_source_report_api as api
import test_stage38_source_report_v3 as v3


def without_descriptions(value):
    if isinstance(value, dict):
        return {key: without_descriptions(item) for key, item in value.items() if key != "description"}
    if isinstance(value, list):
        return [without_descriptions(item) for item in value]
    return value


class SourceV3DescriptionTest(unittest.TestCase):
    def test_all_108_old_schema_values_keep_the_b604_fingerprint(self):
        excluded = {"SourceReportDraftV3", "SourceCharacterV3", "SourceInsightV3",
                    "ReportDraftV3", "DraftCharacterV3", "AnalysisReportV2", "CharacterV2", "PreviewGroundedReportV2"}
        source.SourceReportDraftV3.model_json_schema()
        schemas = {module.__name__ + "." + name: model.model_json_schema()
                   for module in (source, pipeline, grounding, report, delta, deconstruction)
                   for name, model in vars(module).items()
                   if inspect.isclass(model) and issubclass(model, BaseModel) and model is not BaseModel
                   and model.__module__ == module.__name__ and name not in excluded}
        self.assertEqual(len(schemas), 108)
        self.assertEqual(pipeline.object_hash(schemas),
                         "3ae224e76ef26cd7e8ee715961ff63ba3fec502ba153aae22d7250a7512ad0c8")

    def test_old_rules_reviews_and_v3_review_keep_their_byte_fingerprints(self):
        expected = {
            "deconstruction_report_rules.md": "1c2a9e223935b65c04322879117bc86d44e6d0e41e6d722b90ed4233324ac7a6",
            "deconstruction_report_review.md": "8226e3968f2d24d03bb4846f857e920cdf7d96a0ad98b1cafe4079771fa287ac",
            "deconstruction_source_report_rules.md": "8856b22666bbef402d436344f9cb3759180911e6e0f3ec30767a7ceaac350228",
            "deconstruction_source_report_review.md": "466e2a1d08e0602651bc7ec899899b4b2457e203e197ddf8322209d88e2ad956",
            "deconstruction_source_report_v3_review.md": "fbf5669f8eaa4d056888077ab4f07210b6802381577b753100377293043b9c09",
        }
        for name, fingerprint in expected.items():
            with self.subTest(prompt=name):
                self.assertEqual(sha256((Path("app/agents") / name).read_bytes()).hexdigest(), fingerprint)

    def test_v3_non_description_values_and_dynamic_repair_schema_are_unchanged(self):
        for options in ({}, {"mode": "serialization", "by_alias": False, "ref_template": "#/definitions/{model}"}):
            with self.subTest(options=options):
                # Bypass only the new exporter: original fields/validators stay
                # authoritative, including when the runtime makes a subclass.
                original = BaseModel.model_json_schema.__func__(source.SourceReportDraftV3, **options)
                exported = source.SourceReportDraftV3.model_json_schema(**options)
                self.assertEqual(without_descriptions(exported), without_descriptions(original))
                self.assertEqual(source.source_response_model(source.SOURCE_REPORT_V3_WIRE).model_json_schema(**options), exported)
        self.assertEqual(pipeline.object_hash(without_descriptions(source.SourceReportDraftV3.model_json_schema())),
                         "d1e99e2fcaefff601f2be3b7e98368a510a9b7fa48c46a50a10632acd92ae982")

    def test_exporter_deep_copies_even_a_shared_parent_schema(self):
        original = BaseModel.model_json_schema.__func__(source.SourceReportDraftV3)
        before = deepcopy(original)
        with patch.object(source.SourceReportDraftV2, "model_json_schema", return_value=original):
            exported = source.SourceReportDraftV3.model_json_schema()
            self.assertEqual(original, before)
            exported["$defs"]["SourceEvent"]["properties"]["actor_ids"]["items"]["type"] = "invalid"
            self.assertEqual(original, before)
            self.assertEqual(source.SourceReportDraftV3.model_json_schema()["$defs"]["SourceEvent"]
                             ["properties"]["actor_ids"]["items"]["type"], "string")

    def test_four_rules_are_beside_fields_and_self_check_is_ordered(self):
        definitions = source.SourceReportDraftV3.model_json_schema()["$defs"]
        for model in ("SourceCharacterV3", "SourceParticipant", "SourceAliasBasis"):
            field = "source_ids" if model == "SourceAliasBasis" else "name_source_ids"
            text = definitions[model]["properties"][field]["description"]
            self.assertIn("至少一段字面包含", text)
            self.assertIn("字面命中本身也不证明同一性", text)
        for model in ("SourceDraftClaim", "SourceFinding", "SourceDetail", "SourceInsightV3"):
            text = definitions[model]["properties"]["subject_id"]["description"]
            self.assertIn("kind为knowledge/feeling时subject_id不可为null", text)
            self.assertIn("在characters的人物分析字段中", text)
        formula = "S∩P ⊆ actor_ids ⊆ (S∪O)∩P且不得重复"
        self.assertIn(formula, definitions["SourceEvent"]["properties"]["actor_ids"]["description"])
        for model, fields in (("SourceRelation", ("from_action", "to_action", "status", "basis")),
                              ("SourceCharacterRelation", ("from_id", "to_id", "action_ref", "source_ids", "status"))):
            for field in fields:
                self.assertTrue(definitions[model]["properties"][field]["description"])
        rules = Path("app/agents/deconstruction_source_report_v3_rules.md").read_text()
        self.assertIn("称谓来源及真实主体→事件名单→边的方向/来源/状态", rules)
        self.assertIn(formula, rules)
        self.assertIn("不机械清名单、错绑主体或把主角藏到背景凑过关", rules)

    def check_candidate(self, draft, bank, texts, entries, accepted):
        before = deepcopy(draft)
        if accepted:
            normalized, _ = source.validate_source_candidate(draft, entries, bank, texts,
                producer="synthetic", wire=source.SOURCE_REPORT_V3_WIRE)
            self.assertEqual(normalized, before)
        else:
            with self.assertRaises(ValueError):
                source.validate_source_candidate(draft, entries, bank, texts,
                    producer="synthetic", wire=source.SOURCE_REPORT_V3_WIRE)
        self.assertEqual(draft, before)

    def test_name_alias_and_role_legal_counterexamples_and_illegal_values(self):
        _, _, texts, _ = source_case()
        draft, bank, texts, binding = source_case(texts={**texts, 1: texts[1] + "林客又称林舟。"})
        entries = binding["source_directory"]["entries"]
        draft["schema_version"] = "2"
        alias_source = next(key for key, ref in entries.items() if "林舟" in bank[ref].quote)
        draft["characters"][0].update(aliases=["林舟"], alias_basis=[dict(name="林舟", source_ids=[alias_source])])
        cases = [("valid alias", {}, True), ("valid role boundary", {"role": "身" * 80}, True),
                 ("empty role", {"role": ""}, False), ("long role", {"role": "身" * 81}, False),
                 ("typed role", {"role": False}, False), ("unsupported name", {"name": "未见称谓"}, False),
                 ("known but nonliteral alias source", {"alias_basis": [dict(name="林舟", source_ids=["C1P001"])]}, False),
                 ("alias mismatch", {"aliases": []}, False)]
        for label, changes, accepted in cases:
            with self.subTest(case=label):
                value = deepcopy(draft)
                value["characters"][0].update(changes)
                self.check_candidate(value, bank, texts, entries, accepted)
        value = deepcopy(draft)
        value["characters"][1]["name_source_ids"] = [alias_source]
        self.check_candidate(value, bank, texts, entries, False)

    def test_actual_holders_and_optional_object_actors_keep_original_acceptance(self):
        draft, bank, texts, entries = v3.sparse_case()
        for actors, accepted in ((["Lin"], True), (["Lin", "Xu"], True), (["Xu"], False), (["Lin", "Lin"], False)):
            with self.subTest(actors=actors):
                value = deepcopy(draft)
                value["events"][0]["actor_ids"] = actors
                self.check_candidate(value, bank, texts, entries, accepted)
        value = deepcopy(draft)
        event = value["events"][0]
        for claim in (event["action"], event["consequence"], *event["sub_events"]):
            claim["object_id"] = None
        event["actor_ids"] = ["Lin", "Xu"]  # Xu remains in text, not structural endpoints.
        self.check_candidate(value, bank, texts, entries, False)
        for kind in ("knowledge", "feeling"):
            for subject, accepted in ((None, False), ("Lin", True)):
                with self.subTest(kind=kind, subject=subject):
                    value = deepcopy(draft)
                    value["findings"][0].update(kind=kind, subject_id=subject)
                    self.check_candidate(value, bank, texts, entries, accepted)
        for kind, subject, obj, accepted in (("action", "Xu", "Lin", True), ("action", "Xu", None, False),
                                              ("knowledge", "Xu", "Lin", False), ("feeling", "Lin", None, True)):
            with self.subTest(kind=kind, subject=subject, obj=obj):
                value = deepcopy(draft)
                value["characters"][0]["identity"].update(kind=kind, subject_id=subject, object_id=obj)
                self.check_candidate(value, bank, texts, entries, accepted)

    def test_event_and_character_edges_keep_direction_source_status_and_phase_gates(self):
        draft, bank, texts, entries = v3.sparse_case()
        for changes, claim_changes, accepted in (
            ({}, {}, True), ({"from_action": "E1b.action"}, {}, False),
            ({}, {"status": "inferred"}, False), ({"status": "inferred"}, {"status": "inferred"}, True),
            ({"kind": "causes", "basis": "cause"}, {"phase": "planned"}, False),
            ({"kind": "enables", "basis": "purpose"}, {"phase": "requested"}, False),
        ):
            with self.subTest(edge=changes, claim=claim_changes):
                value = deepcopy(draft)
                value["relations"][0].update(changes)
                value["events"][0]["action"].update(claim_changes)
                self.check_candidate(value, bank, texts, entries, accepted)
        for changes, claim_changes, accepted in (
            ({}, {}, True), ({"from_id": "Xu", "to_id": "Lin"}, {}, False),
            ({"source_ids": ["C1P002"]}, {}, False), ({"action_ref": None}, {}, False),
            ({"action_ref": "Lin.motivation"}, {}, False), ({}, {"status": "reported"}, False),
            ({"status": "reported"}, {"status": "reported"}, True), ({}, {"phase": "planned"}, True),
        ):
            with self.subTest(edge=changes, claim=claim_changes):
                value = deepcopy(draft)
                value["characters"][0]["identity"].update(object_id="Xu", **claim_changes)
                value["character_relations"] = [dict(from_id="Lin", to_id="Xu", label="共同核对", text="共同核对记录。", status="fact",
                    source_ids=["C1P001"], action_ref="Lin.identity")]
                value["character_relations"][0].update(changes)
                self.check_candidate(value, bank, texts, entries, accepted)

    def test_actual_draft_repair_and_preflight_schemas_match_with_two_ledgers(self):
        case = api.SourceReportApiTest("runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.prepare()
        case.scripted([{"unexpected": "草稿"}, lambda: case.draft,
                       {"unexpected": "审查"}, case.revised_reply,
                       {"unexpected": "终审"}, lambda: acceptance(case.job()["revised"])])
        with patch.object(budget, "_reserve_all", wraps=budget._reserve_all) as reservations:
            self.assertEqual(case.start().status_code, 200)
            final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual([c["max_completion_tokens"] for c in case.calls], [24576, 24576, 8192, 8192, 4096, 4096])
        self.assertEqual(reservations.call_count, 6)
        schemas = [source.SourceReportDraftV3, pipeline.ReportReview, pipeline.ReportVerification]
        records = json.loads(case.deconstruction.model_budget.path.read_text())["records"]
        for i, (call, held, record, reserved) in enumerate(zip(case.calls, case.holds, records, reservations.call_args_list, strict=True)):
            expected = schemas[i // 2].model_json_schema()
            sent = json.loads(call["messages"][0]["content"].rsplit("只返回一个 JSON 对象，严格符合以下 schema，不要 Markdown 或解释：", 1)[1])
            self.assertEqual(sent, expected)
            self.assertEqual(json.loads(reserved.args[2][-1]["content"]), expected)
            for ledger in held:
                self.assertAlmostEqual(ledger["reserved_cny"], wire_bound(call), places=12)
            self.assertAlmostEqual(record["reserved_cny"], wire_bound(call), places=12)
        repair = case.calls[1]["messages"][-2]["content"]
        self.assertEqual(json.loads(repair.split("必须严格符合以下 schema：", 1)[1]), schemas[0].model_json_schema())
        self.assertEqual(case.independent.store.load(case.project).model_dump(mode="json"), case.old_author)


if __name__ == "__main__":
    unittest.main()
