"""Pure contract tests: synthetic text, no services, stores, dotenv or model calls."""

from copy import deepcopy
import json
import unittest

from pydantic import ValidationError

from schemas.deconstruction import (
    DECONSTRUCTION_STATUS_TRANSITIONS,
    DeconstructionDepthReport, DeconstructionDocument, DeconstructionDocumentPublic,
    DeconstructionProjectRecord, DeconstructionResponse, DeconstructionResult,
    DeconstructionEvidenceResponse, DepthSource, depth_stable_id, validate_depth_report_source,
    is_valid_deconstruction_transition,
)


SOURCE = dict(project_id="project32", document_id="document32", source_version_id="version32",
              source_revision=3, source_hash="a" * 64)
TEXTS = {"c1": "  🧭阿岚把钥匙交给周砚。", "c2": "周砚用钥匙打开门，才认出旧信上的字。"}


def report_payload():
    """Executable complete six-perspective example for backend/frontend implementers."""
    def claim(item_id, kind, **details):
        return dict(item_id=item_id, kind=kind, category=kind, conclusion="钥匙的交接连接人物选择与开门事件。",
                    epistemic_status="inferred", chapter_ids=["c1", "c2"], normalized_start=0.0,
                    normalized_end=100.0, evidence_ids=["ev1", "ev2"], related_item_ids=[],
                    confidence=0.6, uncertainty=["两章材料不足以确定长程意义。"], **details)

    def view(**lists):
        return dict(summary="从正文交接与开门动作观察局部结构。", uncertainty=["仅限所提供两章。"], **lists)

    def relation(item_id, start_id, start_kind, end_id, end_kind, relation_type):
        return claim(item_id, "relation", start=dict(item_id=start_id, kind=start_kind),
                     end=dict(item_id=end_id, kind=end_kind), relation_type=relation_type,
                     explanation="前一行动为后一行动提供条件；不把叙述相邻当作确定因果。")

    payload = dict(
        report_version="2.0", source=SOURCE.copy(),
        chapters=[dict(chapter_id=key, chapter_number=index + 1, title=f"第{index + 1}章",
                       utf16_length=len(text.encode("utf-16-le")) // 2,
                       normalized_start=index * 50.0, normalized_end=(index + 1) * 50.0)
                  for index, (key, text) in enumerate(TEXTS.items())],
        evidence=[dict(**SOURCE, evidence_id="ev1", chapter_id="c1", chapter_number=1,
                       granularity="span", start_offset=4, end_offset=13,
                       excerpt="阿岚把钥匙交给周砚", label="交出钥匙者"),
                  dict(**SOURCE, evidence_id="ev2", chapter_id="c2", chapter_number=2,
                       granularity="span", start_offset=0, end_offset=8,
                       excerpt="周砚用钥匙打开门", label="开门者")],
        characters=view(
            characters=[claim(key, "character", name=name, aliases=[], role="行动参与者",
                              motivation="借助钥匙接近旧信", inner_conflict="正文尚未明示", arc_summary="交接后选择行动")
                        for key, name in (("person1", "阿岚"), ("person2", "周砚"))],
            states=[claim(key, "character_state", character_id=person, goal="打开门", belief="钥匙可用",
                          emotion="未明示", agency="主动选择", change="由持有转为行动", trigger_event_ids=["event1"])
                    for key, person in (("state1", "person1"), ("state2", "person2"))],
            relations=[relation("rel1", "person1", "character", "person2", "character", "allies")]),
        plot=view(
            plotlines=[claim("line1", "plotline", title="旧信之谜", central_question="旧信写了什么",
                             stakes="人物面临未知信息", resolution="只揭示局部线索", character_ids=["person1", "person2"])],
            events=[claim(f"event{i}", "event", plotline_ids=["line1"], character_ids=["person2"],
                          story_order=i, narrative_order=i, temporal_mode="linear", action=action,
                          consequence="获得进一步接近信息的条件", plotline_status="developing")
                    for i, action in ((1, "接过钥匙"), (2, "打开门"))],
            relations=[relation("rel2", "event1", "event", "event2", "event", "enables")]),
        foreshadowing=view(
            threads=[claim("thread1", "foreshadowing", label="钥匙", planted_detail="交出的钥匙",
                           expected_payoff="后来开门使用", interpretation="具体物件串起前后行动")],
            states=[claim("seed1", "foreshadowing_state", foreshadowing_id="thread1", status="planted",
                          payoff="尚待使用", event_ids=["event1"]),
                    claim("seed2", "foreshadowing_state", foreshadowing_id="thread1", status="paid_off",
                          payoff="用于开门", event_ids=["event2"])],
            relations=[relation("rel3", "event1", "event", "thread1", "foreshadowing", "plants"),
                       relation("rel4", "event2", "event", "thread1", "foreshadowing", "pays_off")]),
        rhythm=view(items=[claim("rhythm1", "rhythm", narrative_function="行动递进", scene_summary="交接后开门",
                                 pace=0.5, tension=None, information_density=0.4, transition="以物件延续动作")]),
        reader_experience=view(items=[claim("reader1", "reader_experience", expectation="钥匙将被使用",
                                            information_gap="旧信内容尚未展示", emotional_effect="局部好奇",
                                            curiosity=0.5, suspense=0.4, emotional_valence=None, payoff="开门兑现局部期待")]),
        technique=view(items=[claim("tech1", "technique", technique="物件衔接", observation="两章以钥匙连接",
                                     mechanism="先交出物件，再展示用途", effect="使动作之间可追踪",
                                      learning_note="检查前章物件是否在后续承担叙事功能",
                                      applicability="适合需要保持动作连续性的片段，不要求所有道具都回收",
                                      example_evidence_ids=["ev1", "ev2"])]),
    )
    payload["rhythm"]["items"][0]["related_item_ids"] = ["event1", "reader1"]
    # State snapshots use reading position, independent of story order.
    for item in (payload["characters"]["states"][0], payload["foreshadowing"]["states"][0]):
        item.update(chapter_ids=["c1"], normalized_start=0.0, normalized_end=50.0, evidence_ids=["ev1"])
    for item in (payload["characters"]["states"][1], payload["foreshadowing"]["states"][1]):
        item.update(chapter_ids=["c2"], normalized_start=50.0, normalized_end=100.0, evidence_ids=["ev2"])
    return payload


def document_payload(report=None):
    document = DeconstructionDocument(**SOURCE, account_id="private-account", status="completed",
                                       idempotency_key="key32", overview={}, report=report,
                                       analysis_contract_version="2.0" if report is not None else "1.0")
    return document.model_dump(mode="json")


def response_payload(report=None):
    document = document_payload(report)
    public = {key: value for key, value in document.items() if key != "account_id"}
    result = {key: value for key, value in public.items() if key in DeconstructionResult.model_fields}
    run = {key: public[key] for key in ("document_id", "source_version_id", "source_revision", "source_hash",
                                       "analysis_contract_version", "idempotency_key", "created_at", "updated_at")}
    run["run_status"] = "completed"
    return dict(schema_version="1.0", project_id=SOURCE["project_id"], title="合同示例",
                effective_status="completed", status="completed", run_status="completed", source_match=True,
                source=dict(version_id=SOURCE["source_version_id"], revision=SOURCE["source_revision"],
                            hash=SOURCE["source_hash"], match=True),
                source_version_id=SOURCE["source_version_id"], source_revision=SOURCE["source_revision"],
                source_hash=SOURCE["source_hash"], result=result, active_run=run, document=public)


class Stage32ContractTest(unittest.TestCase):
    def assert_invalid(self, mutate, message=None):
        payload = report_payload()
        mutate(payload)
        with self.assertRaises(ValidationError) as caught:
            DeconstructionDepthReport.model_validate(payload)
        if message:
            self.assertIn(message, str(caught.exception))

    def test_complete_six_view_report_and_json_roundtrip(self):
        payload = report_payload()
        report = DeconstructionDepthReport.model_validate(payload)
        self.assertEqual(report, DeconstructionDepthReport.model_validate_json(report.model_dump_json()))
        self.assertGreaterEqual(len(report.analysis_items()), 17)
        self.assertEqual(report.foreshadowing.states[-1].status, "paid_off")
        self.assertEqual(report.plot.relations[0].relation_type, "enables")
        self.assertEqual(validate_depth_report_source(report, source=DepthSource(**SOURCE), chapters=TEXTS), report)

    def test_stage31_payload_without_report_is_not_migrated_to_depth(self):
        payload = response_payload()
        del payload["result"]["report"]
        del payload["document"]["report"]
        parsed = DeconstructionResponse.model_validate(payload)
        self.assertEqual(parsed.schema_version, "1.0")
        self.assertIsNone(parsed.result.report)
        stored = document_payload()
        del stored["report"]
        record = DeconstructionProjectRecord.model_validate(dict(project_id=SOURCE["project_id"],
                    account_id="private-account", documents=[stored]))
        self.assertIsNone(record.documents[0].report)

    def test_new_report_roundtrips_internal_record_and_public_projection(self):
        report = DeconstructionDepthReport.model_validate(report_payload())
        internal = document_payload(report)
        with self.assertRaises(ValidationError):
            DeconstructionDocumentPublic.model_validate(internal)
        public = response_payload(report)
        result = DeconstructionResponse.model_validate(public)
        self.assertEqual(result.result.report, report)
        self.assertNotIn("account_id", result.model_dump_json())
        self.assertNotIn("private-account", result.model_dump_json())

    def test_schema_is_closed_recursive_and_never_exposes_account(self):
        schema = DeconstructionResponse.model_json_schema()
        for name, definition in schema["$defs"].items():
            if definition.get("type") == "object":
                self.assertIs(definition.get("additionalProperties"), False, name)
        serialized = json.dumps(schema)
        for key in ("account_id", "idempotency_key", "private_memory", "raw_completion", "prompt"):
            self.assertNotIn(f'"{key}"', serialized)
        required = schema["$defs"]["DeconstructionDepthReport"]["required"]
        self.assertTrue(set(("characters", "plot", "foreshadowing", "rhythm", "reader_experience", "technique")) <= set(required))

    def test_missing_perspective_unknown_version_and_extra_fields_fail(self):
        self.assert_invalid(lambda p: p.pop("technique"))
        self.assert_invalid(lambda p: p.update(report_version="1.0"))
        self.assert_invalid(lambda p: p["source"].update(account_id="private"))
        self.assert_invalid(lambda p: p["technique"]["items"][0].update(prompt="private"))
        self.assert_invalid(lambda p: p["characters"]["relations"][0]["start"].update(content="body"))

    def test_strict_numeric_types_and_nonfinite_scores(self):
        for value in (True, "0.6", float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(value=value):
                self.assert_invalid(lambda p: p["rhythm"]["items"][0].update(confidence=value))
        self.assert_invalid(lambda p: p["evidence"][0].update(start_offset="4"))
        self.assert_invalid(lambda p: p["chapters"][0].update(chapter_number=True))
        self.assert_invalid(lambda p: p["technique"]["items"][0].update(learning_note="  "))

    def test_dangling_wrong_chapter_and_duplicate_evidence_references(self):
        self.assert_invalid(lambda p: p["rhythm"]["items"][0].update(evidence_ids=["absent"]), "invalid evidence")
        self.assert_invalid(lambda p: p["characters"]["states"][0].update(evidence_ids=["ev2"]), "invalid evidence")
        self.assert_invalid(lambda p: p["rhythm"]["items"][0].update(evidence_ids=["ev1", "ev1"]))
        self.assert_invalid(lambda p: p["evidence"].append(deepcopy(p["evidence"][0])))

    def test_wrong_source_identity_hash_revision_and_chapter_number(self):
        for key, value in (("project_id", "other"), ("document_id", "other"), ("source_version_id", "old"),
                           ("source_revision", 4), ("source_hash", "b" * 64), ("chapter_number", 9)):
            with self.subTest(key=key):
                self.assert_invalid(lambda p: p["evidence"][0].update({key: value}))
        self.assert_invalid(lambda p: p["source"].update(source_hash="not-a-hash"))
        self.assert_invalid(lambda p: p["rhythm"]["items"][0].update(chapter_ids=["absent"]))

    def test_offsets_reversed_zero_negative_out_of_bounds_and_wrong_unit(self):
        for update in (dict(start_offset=6, end_offset=4), dict(start_offset=4, end_offset=4),
                       dict(start_offset=-1), dict(end_offset=999), dict(offset_unit="code_point"),
                       dict(start_offset=None), dict(excerpt="")):
            with self.subTest(update=update):
                self.assert_invalid(lambda p: p["evidence"][0].update(update))

    def test_actual_source_surrogate_boundaries_and_quote_validation(self):
        payload = report_payload()
        payload["evidence"][0].update(start_offset=2, end_offset=4, excerpt="🧭")
        report = DeconstructionDepthReport.model_validate(payload)
        validate_depth_report_source(report, source=DepthSource(**SOURCE), chapters=TEXTS)
        for update in (dict(start_offset=3), dict(end_offset=3), dict(excerpt="wrong")):
            broken = deepcopy(payload)
            broken["evidence"][0].update(update)
            structurally_valid = DeconstructionDepthReport.model_validate(broken)
            with self.assertRaises(ValueError):
                validate_depth_report_source(structurally_valid, source=DepthSource(**SOURCE), chapters=TEXTS)

    def test_chapter_evidence_explicitly_has_no_fake_offsets(self):
        payload = report_payload()
        payload["evidence"][0].update(granularity="chapter", start_offset=None, end_offset=None, excerpt="")
        report = DeconstructionDepthReport.model_validate(payload)
        validate_depth_report_source(report, source=DepthSource(**SOURCE), chapters=TEXTS)
        payload["evidence"][0]["start_offset"] = 0
        with self.assertRaises(ValidationError):
            DeconstructionDepthReport.model_validate(payload)

    def test_exact_source_gate_rejects_lengths_membership_and_binding(self):
        report = DeconstructionDepthReport.model_validate(report_payload())
        for texts in ({"c1": TEXTS["c1"]}, {**TEXTS, "c2": TEXTS["c2"] + "变"}):
            with self.assertRaises(ValueError):
                validate_depth_report_source(report, source=DepthSource(**SOURCE), chapters=texts)
        with self.assertRaises(ValueError):
            validate_depth_report_source(report, source=DepthSource(**{**SOURCE, "source_revision": 4}), chapters=TEXTS)

    def test_relation_endpoints_types_direction_and_self_links(self):
        self.assert_invalid(lambda p: p["plot"]["relations"][0]["end"].update(item_id="missing"))
        self.assert_invalid(lambda p: p["plot"]["relations"][0]["end"].update(kind="character"))
        self.assert_invalid(lambda p: p["plot"]["relations"][0].update(relation_type="allies"))
        self.assert_invalid(lambda p: p["plot"]["relations"][0]["end"].update(item_id="event1"))
        self.assert_invalid(lambda p: p["foreshadowing"]["relations"][0].update(relation_type="causes"))

    def test_precedes_is_not_cause_and_flashback_story_order_can_reverse(self):
        payload = report_payload()
        payload["plot"]["relations"][0]["relation_type"] = "precedes"
        payload["plot"]["events"][0]["story_order"] = 8
        payload["plot"]["events"][1].update(story_order=1, temporal_mode="flashback")
        DeconstructionDepthReport.model_validate(payload)
        payload["plot"]["relations"][0]["start"]["item_id"] = "event2"
        payload["plot"]["relations"][0]["end"]["item_id"] = "event1"
        with self.assertRaises(ValidationError):
            DeconstructionDepthReport.model_validate(payload)

    def test_duplicate_ids_wrong_parent_and_cross_view_claim_links(self):
        self.assert_invalid(lambda p: p["plot"]["events"][0].update(item_id="person1"))
        self.assert_invalid(lambda p: p["characters"]["states"][0].update(character_id="line1"))
        self.assert_invalid(lambda p: p["foreshadowing"]["states"][0].update(event_ids=["person1"]))
        self.assert_invalid(lambda p: p["rhythm"]["items"][0].update(related_item_ids=["missing"]))
        self.assert_invalid(lambda p: p["rhythm"]["items"][0].update(related_item_ids=["rhythm1"]))

    def test_evidence_free_claims_must_be_explicit_unknown_not_high_confidence(self):
        self.assert_invalid(lambda p: p["characters"]["characters"][0].update(evidence_ids=[]))
        self.assert_invalid(lambda p: p["characters"]["characters"][0].update(uncertainty=[]))
        payload = report_payload()
        item = payload["characters"]["characters"][0]
        item.update(epistemic_status="unknown", evidence_ids=[], confidence=0.0, uncertainty=["身份未明"])
        DeconstructionDepthReport.model_validate(payload)
        item["confidence"] = 0.8
        with self.assertRaises(ValidationError):
            DeconstructionDepthReport.model_validate(payload)

    def test_empty_placeholders_do_not_pass_for_completed_report(self):
        for view in ("rhythm", "reader_experience", "technique"):
            self.assert_invalid(lambda p: p[view].update(items=[]))
            self.assert_invalid(lambda p: p[view]["items"][0].update(epistemic_status="unknown", confidence=0.0))
        self.assert_invalid(lambda p: p["characters"].update(states=[]))
        self.assert_invalid(lambda p: p["foreshadowing"].update(states=[]))
        self.assert_invalid(lambda p: p["plot"].update(events=[], relations=[]))

    def test_timeline_bounds_chapter_order_and_state_order(self):
        self.assert_invalid(lambda p: p["chapters"][0].update(normalized_start=2.0))
        self.assert_invalid(lambda p: p["chapters"][1].update(normalized_end=99.0))
        self.assert_invalid(lambda p: p["chapters"][1].update(normalized_start=49.0))
        self.assert_invalid(lambda p: p["chapters"].reverse())
        self.assert_invalid(lambda p: p["foreshadowing"]["states"].reverse())
        self.assert_invalid(lambda p: p["characters"]["states"][0].update(normalized_end=51.0))
        self.assert_invalid(lambda p: p["rhythm"]["items"][0].update(normalized_end=99.0))

    def test_report_rejects_wrong_parent_document_and_canonical_source(self):
        report = DeconstructionDepthReport.model_validate(report_payload())
        stored = document_payload(report)
        stored["source_revision"] = 9
        with self.assertRaises(ValidationError):
            DeconstructionDocument.model_validate(stored)
        for mutate in (lambda p: p.update(project_id="other"),
                       lambda p: p["active_run"].update(document_id="other"),
                       lambda p: p["document"].update(report=None)):
            payload = response_payload(report)
            mutate(payload)
            with self.assertRaises(ValidationError):
                DeconstructionResponse.model_validate(payload)

    def test_report_cannot_publish_during_failed_stale_or_pending_state(self):
        report = DeconstructionDepthReport.model_validate(report_payload())
        for status in ("queued", "running", "failed_retryable", "stale", "rebuild_required"):
            stored = document_payload(report)
            stored["status"] = status
            with self.assertRaises(ValidationError):
                DeconstructionDocumentPublic.model_validate({k: v for k, v in stored.items() if k != "account_id"})
            payload = response_payload(report)
            payload.update(status=status, effective_status=status)
            with self.assertRaises(ValidationError):
                DeconstructionResponse.model_validate(payload)

    def test_revalidation_catches_mutated_model_instance(self):
        report = DeconstructionDepthReport.model_validate(report_payload())
        report.rhythm.items[0].evidence_ids = ["absent"]
        with self.assertRaises(ValidationError):
            DeconstructionDepthReport.model_validate(report)

    def test_stable_ids_depend_on_source_identity_and_anchor_not_worker_run(self):
        source = DepthSource(**SOURCE)
        first = depth_stable_id(source, "character", "canonical-person-阿岚")
        rerun = DepthSource(**{**SOURCE, "document_id": "another-worker-document"})
        self.assertEqual(first, depth_stable_id(rerun, "character", "canonical-person-阿岚"))
        changed = DepthSource(**{**SOURCE, "source_hash": "b" * 64})
        self.assertNotEqual(first, depth_stable_id(changed, "character", "canonical-person-阿岚"))
        self.assertNotEqual(first, depth_stable_id(source, "character", "canonical-person-周砚"))
        self.assertRegex(first, r"^d32_[a-f0-9]{40}$")
        with self.assertRaises(ValueError):
            depth_stable_id(source, "character", "")

    def test_new_evidence_response_preserves_read_only_history(self):
        payload = dict(project_id=SOURCE["project_id"], title="合同示例", evidence=report_payload()["evidence"][0],
                       chapter=dict(chapter_id="c1", chapter_number=1, title="历史章节", read_only=True,
                                    source_available=False), historical=True, source_matches_current=False)
        parsed = DeconstructionEvidenceResponse.model_validate(payload)
        self.assertEqual(parsed.evidence.source_version_id, "version32")
        self.assertIs(parsed.chapter.read_only, True)
        for update in (dict(historical=False), dict(source_matches_current=True), dict(project_id="other")):
            with self.assertRaises(ValidationError):
                DeconstructionEvidenceResponse.model_validate({**payload, **update})
        payload["chapter"]["read_only"] = False
        with self.assertRaises(ValidationError):
            DeconstructionEvidenceResponse.model_validate(payload)

    def test_single_chapter_and_hundred_chapter_contracts_have_no_small_book_cap(self):
        for count in (1, 100):
            payload = report_payload()
            texts = {f"c{i}": f"第{i}章。🧭" for i in range(1, count + 1)}
            payload["chapters"] = [dict(chapter_id=key, chapter_number=i, title=f"第{i}章",
                                        utf16_length=len(text.encode("utf-16-le")) // 2,
                                        normalized_start=(i - 1) * 100.0 / count,
                                        normalized_end=i * 100.0 / count)
                                   for i, (key, text) in enumerate(texts.items(), start=1)]
            for ref in payload["evidence"]:
                ref.update(chapter_id="c1", chapter_number=1, granularity="chapter",
                           start_offset=None, end_offset=None, excerpt="")
            for view in ("characters", "plot", "foreshadowing", "rhythm", "reader_experience", "technique"):
                for value in payload[view].values():
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict) and "item_id" in item:
                                item.update(chapter_ids=list(texts), normalized_start=0.0, normalized_end=100.0)
            report = DeconstructionDepthReport.model_validate(payload)
            validate_depth_report_source(report, source=DepthSource(**SOURCE), chapters=texts)
            self.assertEqual(len(report.chapters), count)

    def test_source_gate_rejects_span_beyond_actual_utf16_length(self):
        payload = report_payload()
        payload["evidence"][1].update(end_offset=999, excerpt=TEXTS["c2"])
        with self.assertRaises((ValidationError, ValueError)):
            report = DeconstructionDepthReport.model_validate(payload)
            validate_depth_report_source(report, source=DepthSource(**SOURCE), chapters=TEXTS)

    def test_each_completed_perspective_needs_supported_depth_not_only_unknown(self):
        primary_fields = {
            "rhythm": "items",
            "reader_experience": "items",
            "technique": "items",
        }
        for view, field in primary_fields.items():
            payload = report_payload()
            primary = payload[view][field]
            for item in primary:
                item.update(epistemic_status="unknown", evidence_ids=[], confidence=0.0,
                            uncertainty=["当前正文证据不足以支持该视角结论。"])
            with self.subTest(view=view):
                with self.assertRaises(ValidationError):
                    DeconstructionDepthReport.model_validate(payload)

    def test_technique_examples_must_be_bounded_evidence_ids(self):
        self.assert_invalid(lambda p: p["technique"]["items"][0].update(example_evidence_ids=["missing"]))

    def test_stage31_opaque_run_token_is_parse_only_and_never_serialized(self):
        parsed = DeconstructionResponse.model_validate(response_payload())
        serialized = parsed.model_dump_json()
        self.assertNotIn("idempotency_key", serialized)
        self.assertNotIn("private-account", serialized)
        active = parsed.active_run
        self.assertIsNotNone(active)
        self.assertEqual(active.idempotency_key, "key32")
        self.assertNotIn("idempotency_key", active.model_dump_json())

    def test_legacy_completed_result_and_new_depth_result_can_share_source_history(self):
        payload = report_payload()
        depth_document_id = "depth-document"
        payload["source"]["document_id"] = depth_document_id
        for evidence in payload["evidence"]:
            evidence["document_id"] = depth_document_id
        report = DeconstructionDepthReport.model_validate(payload)
        legacy = DeconstructionDocument(
            document_id="legacy-document", project_id=SOURCE["project_id"], account_id="private-account",
            source_version_id=SOURCE["source_version_id"], source_revision=SOURCE["source_revision"],
            source_hash=SOURCE["source_hash"], status="completed", idempotency_key="legacy-key",
            overview={}, analysis_contract_version="1.0",
        )
        depth = DeconstructionDocument(
            document_id=depth_document_id, project_id=SOURCE["project_id"], account_id="private-account",
            source_version_id=SOURCE["source_version_id"], source_revision=SOURCE["source_revision"],
            source_hash=SOURCE["source_hash"], status="completed", idempotency_key="depth-key",
            overview={}, report=report, analysis_contract_version="2.0",
        )
        record = DeconstructionProjectRecord(
            project_id=SOURCE["project_id"], account_id="private-account",
            active_document_id=depth_document_id, documents=[legacy, depth], record_revision=7,
        )
        self.assertEqual([item.analysis_contract_version for item in record.documents], ["1.0", "2.0"])
        self.assertEqual(record.record_revision, 7)

    def test_depth_report_cannot_be_attached_to_legacy_contract_document(self):
        report = DeconstructionDepthReport.model_validate(report_payload())
        with self.assertRaises(ValidationError):
            DeconstructionDocument(
                **SOURCE, account_id="private-account", status="completed", idempotency_key="key32",
                overview={}, report=report, analysis_contract_version="1.0",
            )

    def test_canonical_transition_table_is_explicit_and_idempotent(self):
        self.assertEqual(set(DECONSTRUCTION_STATUS_TRANSITIONS), {
            "empty", "queued", "running", "completed", "failed_retryable", "stale", "rebuild_required",
        })
        for status, transitions in DECONSTRUCTION_STATUS_TRANSITIONS.items():
            self.assertIn(status, transitions)
            self.assertTrue(is_valid_deconstruction_transition(status, status))
        self.assertFalse(is_valid_deconstruction_transition("completed", "running"))
        self.assertTrue(is_valid_deconstruction_transition("failed_retryable", "queued"))

    def test_event_story_order_is_separate_from_narrative_order(self):
        payload = report_payload()
        payload["plot"]["events"][0].update(story_order=None, uncertainty=[])
        with self.assertRaises(ValidationError):
            DeconstructionDepthReport.model_validate(payload)
        payload = report_payload()
        payload["plot"]["events"][0].update(temporal_mode="flashback", story_order=None)
        DeconstructionDepthReport.model_validate(payload)

    def test_absent_characters_and_foreshadowing_are_explicitly_unknown(self):
        payload = report_payload()
        payload["characters"].update(characters=[], states=[], relations=[],
                                      uncertainty=["当前正文未提供可可靠识别的人物证据。"])
        payload["foreshadowing"].update(threads=[], states=[], relations=[],
                                         uncertainty=["当前正文未提供可可靠识别的伏笔证据。"])
        for item in payload["plot"]["plotlines"]:
            item["character_ids"] = []
        for item in payload["plot"]["events"]:
            item["character_ids"] = []
        payload["plot"]["relations"] = []
        report = DeconstructionDepthReport.model_validate(payload)
        self.assertEqual(report.characters.characters, [])
        self.assertEqual(report.foreshadowing.threads, [])
        payload["characters"]["uncertainty"] = []
        with self.assertRaises(ValidationError):
            DeconstructionDepthReport.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
