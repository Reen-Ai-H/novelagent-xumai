"""Description-only v2 guidance, real structured parsing with synthetic HTTP.

Frozen hashes are from dc10762 schemas, not manuscript answers. No private
failed response is loaded, corrected, or adopted by these tests.
"""
from copy import deepcopy
import json
import unittest

from pydantic import ValidationError

from app.core.report_pipeline import object_hash
from app.core.source_report import (
    SOURCE_REPORT_V2_WIRE, SourceReportDraft, SourceReportDraftV2,
    validate_source_candidate,
)
from stage38_report_fixtures import acceptance
from stage38_source_report_fixtures import source_case
import test_stage38_source_report_api as api
from test_stage37_preview_capacity import wire_bound


V1_SCHEMA_HASH = "bf4f806e8cca76c484c0b5c99c87680258d2c18b21ce325101cf473e2c9fe775"
V2_NON_DESCRIPTION_HASH = "83cdd912bbffca531eab28ca2a837a88c90d206c4170ed6f3462c4de24abb4ac"
CONTRACT_MARKER = "只返回一个 JSON 对象，严格符合以下 schema，不要 Markdown 或解释："
PROMPT_RULES = (
    "先建立characters、participants和events", "relations的from_id/to_id只选events.id",
    "character_relations的from_id/to_id只选characters.id", "人物之间的身份关系不能直接当事件边",
    "真实身份揭示事件仍可按合法事件端点、动作和来源表达",
    "两两枚举", "传递闭包", "同一合法关系键", "固定节点/边截断",
    "status仅fact/reported/inferred/unknown", "phase仅actual/planned/requested/negated/unknown",
    "planned绝不能填status", "不能由程序",
)


def without_descriptions(value):
    if isinstance(value, dict):
        return {key: without_descriptions(item) for key, item in value.items() if key != "description"}
    if isinstance(value, list):
        return [without_descriptions(item) for item in value]
    return value


class SourceV2ResponsibilitiesTest(unittest.TestCase):
    def case(self):
        case = api.SourceReportApiTest("runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.prepare(wire=SOURCE_REPORT_V2_WIRE)
        return case

    def test_v1_full_schema_and_v2_every_non_description_property_are_unchanged(self):
        self.assertEqual(object_hash(SourceReportDraft.model_json_schema()), V1_SCHEMA_HASH)
        self.assertEqual(object_hash(without_descriptions(SourceReportDraftV2.model_json_schema())), V2_NON_DESCRIPTION_HASH)
        self.assertEqual(set(SourceReportDraftV2.__pydantic_decorators__.model_validators), {"unique_object_ids"})
        self.assertIs(SourceReportDraftV2.unique_object_ids, SourceReportDraft.unique_object_ids)

    def test_v2_field_and_root_descriptions_separate_graphs_and_state_dimensions(self):
        schema = SourceReportDraftV2.model_json_schema()
        root = schema["description"]
        for rule in ("先建立characters、participants和events", "relations只连接events.id",
                     "character_relations只连接characters.id", "人物之间的身份关系不能直接当事件边",
                     "真实身份揭示事件仍可按合法事件端点、动作和来源表达",
                     "两两枚举", "传递闭包", "同键多机制合并保留事实", "不固定截断节点或边",
                     "status仅fact/reported/inferred/unknown", "phase仅actual/planned/requested/negated/unknown",
                     "planned绝不能填status", "不能由程序映射成fact"):
            self.assertIn(rule, root)
        event_edge = schema["properties"]["relations"]["description"]
        for rule in ("只选events.id", "不能选characters/participants", "各自事件", "EventId.action",
                     "EventId.consequence", "EventId.sub_events.索引", "(from_id,to_id,kind)"):
            self.assertIn(rule, event_edge)
        person_edge = schema["properties"]["character_relations"]["description"]
        for rule in ("只选characters.id", "不能选events/participants", "action_ref", "同向", "(from_id,to_id,label)"):
            self.assertIn(rule, person_edge)

    def test_real_four_http_carry_v2_schema_and_all_stage_prompts_with_actual_reserves(self):
        case = self.case()
        case.scripted([{}, lambda: case.draft, case.revised_reply, lambda: acceptance(case.job()["revised"])])
        case.start(); final = case.wait()
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(case.job()["report_wire_version"], SOURCE_REPORT_V2_WIRE)
        self.assertEqual(len(case.calls), 4)
        self.assertEqual([call["max_completion_tokens"] for call in case.calls], [24576, 24576, 8192, 4096])
        for index, call in enumerate(case.calls):
            self.assertEqual(call["response_format"], {"type": "json_object"})
            system = call["messages"][0]["content"]
            for rule in PROMPT_RULES:
                self.assertIn(rule, system)
            if index < 2:
                actual_schema = json.loads(system.rsplit(CONTRACT_MARKER, 1)[1])
                self.assertEqual(actual_schema, SourceReportDraftV2.model_json_schema())
            else:
                review = system.split("# 独立批评与唯一有界修订", 1)[1]
                for rule in ("先核对characters、participants、events", "relations只连接events.id",
                             "character_relations只连接characters.id", "合法动作路径", "传递闭包",
                             "人物之间的身份关系不能直接当事件边", "真实身份揭示事件仍可按合法事件端点、动作和来源表达",
                             "planned绝不能填status", "不能由程序映射成fact"):
                    self.assertIn(rule, review)
            for person in case.draft["characters"]:
                self.assertNotIn(person["name"], system)
        records = json.loads(case.deconstruction.model_budget.path.read_text())["records"]
        self.assertEqual(len(records), 4)
        for call, holds, record in zip(case.calls, case.holds, records, strict=True):
            for ledger in holds:
                self.assertAlmostEqual(ledger["reserved_cny"], wire_bound(call), places=12)
            self.assertAlmostEqual(record["reserved_cny"], wire_bound(call), places=12)
        self.assertEqual(case.independent.store.load(case.project).model_dump(mode="json"), case.old_author)

    def test_planned_is_still_illegal_status_and_no_server_mapping_occurs(self):
        case = self.case()
        claim = case.draft["events"][0]["sub_events"][0]
        claim.update(status="planned", phase="planned")
        before = deepcopy(case.draft)
        with self.assertRaises(ValidationError) as caught:
            SourceReportDraftV2.model_validate(case.draft, strict=True)
        errors = caught.exception.errors(include_input=False, include_context=False, include_url=False)
        self.assertEqual([(tuple(error["loc"]), error["type"]) for error in errors],
                         [(('events', 0, 'sub_events', 0, 'status'), 'literal_error')])
        case.scripted([lambda: case.draft, lambda: case.draft])
        case.start(); final = case.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "provider_bad_json"), final)
        self.assertEqual(len(case.calls), 2)
        self.assertNotIn("draft", case.job())
        self.assertNotIn("review_response", case.job())
        self.assertEqual(case.draft, before)
        case.unchanged()

    def test_event_edge_using_character_ids_reaches_review_but_cannot_be_accepted(self):
        case = self.case()
        case.draft["relations"][0].update(from_id="Lin", to_id="Xu", from_action="Lin.identity", to_action="Xu.identity")
        SourceReportDraftV2.model_validate(case.draft, strict=True)  # No new validator was added.
        before = deepcopy(case.draft)
        case.start(); final = case.wait()
        self.assertEqual((final["status"], final["error_code"]), ("failed", "report_evidence_invalid"), final)
        self.assertEqual(len(case.calls), 2)
        self.assertIn("review_response", case.job())
        self.assertNotIn("approved_hash", case.job())
        self.assertEqual(case.job()["draft"], before)
        codes = [issue["code"] for issue in case.job()["draft_diagnostics"]]
        self.assertIn("relation_endpoint", codes)
        self.assertEqual(codes.count("action_endpoint"), 2)
        case.unchanged()

    def test_character_edge_using_event_ids_cannot_be_accepted(self):
        case = self.case()
        event = case.draft["events"][0]
        case.draft["character_relations"] = [dict(from_id=event["id"], to_id=case.draft["events"][1]["id"],
            label="共同核对", text="共同核对来船记录。", status="fact", source_ids=["C1P001"], action_ref=event["id"]+".action")]
        SourceReportDraftV2.model_validate(case.draft, strict=True)
        case.start(); final = case.wait()
        self.assertEqual(final["error_code"], "report_evidence_invalid", final)
        self.assertEqual(len(case.calls), 2)
        self.assertIn("character_endpoint", [issue["code"] for issue in case.job()["draft_diagnostics"]])
        self.assertNotIn("approved_hash", case.job())
        case.unchanged()

    def test_event_action_must_belong_to_its_endpoint_and_duplicate_edges_still_reject(self):
        draft, bank, texts, binding = source_case()
        entries = binding["source_directory"]["entries"]
        for defect in ("character_action", "other_event_action", "duplicate_edge"):
            with self.subTest(defect=defect):
                bad = deepcopy(draft)
                if defect == "character_action": bad["relations"][0]["from_action"] = "Lin.identity"
                if defect == "other_event_action": bad["relations"][0]["from_action"] = bad["events"][1]["id"] + ".action"
                if defect == "duplicate_edge": bad["relations"].append(deepcopy(bad["relations"][0]))
                SourceReportDraftV2.model_validate(bad, strict=True)
                before = deepcopy(bad)
                with self.assertRaises(ValueError):
                    validate_source_candidate(bad, entries, bank, texts, producer="synthetic", wire=SOURCE_REPORT_V2_WIRE)
                self.assertEqual(bad, before)

    def test_actual_identity_revelation_between_sourced_events_still_passes(self):
        _, _, texts, _ = source_case(1)
        texts[1] = ("林客与许守核对来船记录，林客将旧名册递给许守，许守接过名册。"
                    "许守读名册，得知林客就是当年的记账人。" + texts[1])
        draft, bank, texts, binding = source_case(texts=texts)
        first, second = draft["events"]
        first.update(title="递交名册", actor_ids=["Lin", "Xu"], sub_events=[])
        first["action"].update(text="林客将旧名册递给许守。", source_ids=["C1P001"])
        first["consequence"].update(text="许守接过名册。", subject_id="Xu", object_id=None, source_ids=["C1P001"])
        second.update(title="名册揭示旧身份", actor_ids=["Xu"], sub_events=[])
        second["action"].update(text="许守读名册，得知林客就是当年的记账人。", subject_id="Xu", object_id="Lin",
                                kind="knowledge", source_ids=["C1P002"])
        second["consequence"] = deepcopy(second["action"])
        edge = draft["relations"][0]
        edge.update(kind="reveals", basis="reveal", text="递交的名册向许守揭示林客的旧身份。",
                    source_ids=["C1P001", "C1P002"])
        before = deepcopy(draft)
        normalized, report = validate_source_candidate(draft, binding["source_directory"]["entries"], bank, texts,
                                                       producer="synthetic", wire=SOURCE_REPORT_V2_WIRE)
        self.assertEqual(normalized, before)
        self.assertEqual(draft, before)
        self.assertEqual((report.relations[0].from_id, report.relations[0].to_id, report.relations[0].kind),
                         (first["id"], second["id"], "reveals"))
