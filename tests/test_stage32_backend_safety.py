"""阶段 32 后端专项：实体保守性、CAS 和共享持久锁。"""

from __future__ import annotations

import hashlib
import multiprocessing
from pathlib import Path
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.core.deconstruction_depth import (
    ChapterInput,
    DepthAnalysisEngine,
    DepthSnapshot,
)
from app.core.deconstruction_service import DeconstructionService
from app.core.deconstruction_store import (
    DeconstructionStore,
    DeconstructionStoreConflict,
)
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_lock import ProjectLockError, ProjectLockStore
from app.core.transaction_store import TransactionStore
from schemas.deconstruction import (
    DeconstructionProjectRecord,
    DepthAnalysisItem,
    DepthChapter,
    DepthCharacter,
    DepthEvidence,
    DepthForeshadowing,
    DepthPlotline,
    DepthTechnique,
    DepthView,
)
from schemas.independent import (
    ChapterDocument,
    IndependentProjectRecord,
    ManuscriptVersion,
    StoryArchive,
)


def _snapshot(texts: list[str], character_names: tuple[str, ...] = ()) -> DepthSnapshot:
    chapters = tuple(
        ChapterInput(f"c{index}", index, f"第{index}章", text)
        for index, text in enumerate(texts, 1)
    )
    return DepthSnapshot(
        project_id="backend-safety",
        document_id="backend-document",
        source_version_id="backend-version",
        source_revision=1,
        source_hash="a" * 64,
        chapters=chapters,
        character_names=character_names,
    )


def _hold_shared_project_lock(
    base_dir: str,
    role: str,
    entered: object,
    release: object,
    result_queue: object,
) -> None:
    """Spawn target that exercises the two independent lock entry points."""

    root = Path(base_dir)
    if role == "transaction":
        context = TransactionStore(root / "transactions").project_lock("shared-project")
    else:
        context = DeconstructionStore(root / "deconstruction").project_locks.project_lock("shared-project")
    try:
        with context:
            entered.set()  # type: ignore[attr-defined]
            result_queue.put(("entered", role))  # type: ignore[attr-defined]
            if not release.wait(8):  # type: ignore[attr-defined]
                result_queue.put(("timeout", role))  # type: ignore[attr-defined]
    except BaseException as exc:
        result_queue.put(("error", role, type(exc).__name__, str(exc)))  # type: ignore[attr-defined]
        raise


def _independent_record(project_id: str, account_id: str, content: str) -> IndependentProjectRecord:
    now = datetime.now(timezone.utc)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    chapter = ChapterDocument(
        chapter_id="chapter-1",
        chapter_number=1,
        title="第一章",
        formal_title="第一章",
        content=content,
        formal_content=content,
        server_revision=1,
        word_count=len(content),
        formal_word_count=len(content),
        status="ready",
        last_completed_hash=content_hash,
        updated_at=now,
    )
    version = ManuscriptVersion(
        version_id="version-1",
        label="稿本 1",
        status="active",
        created_at=now,
        updated_at=now,
        chapters=[chapter],
        archive=StoryArchive(),
    )
    return IndependentProjectRecord(
        project_id=project_id,
        account_id=account_id,
        title="并发安全测试",
        created_at=now,
        updated_at=now,
        active_version_id=version.version_id,
        versions=[version],
    )


class Stage32BackendSafetyTest(unittest.TestCase):
    def test_unlabelled_names_require_recurrence_and_exclude_phrase_fragments(self) -> None:
        natural = [
            "林舟想找到失踪的姐姐，却害怕再次走进旧站。顾遥把一把缺角的铜钥匙交给林舟，说：“我替你守住门，你去找她。”林舟答应与顾遥合作。",
            "三年前，姐姐曾对林舟说：“缺角的铜钥匙能打开钟楼的门。”与此同时，顾遥在河岸寻找脚印。",
            "林舟用那把缺角的铜钥匙打开钟楼，终于找到姐姐的信。顾遥赶来帮助林舟，两人决定一起公开真相。",
        ]
        engine = DepthAnalysisEngine(_snapshot(natural))
        self.assertEqual(set(engine.names), {"林舟", "顾遥"})
        self.assertFalse({"我替你", "他把疑问", "林舟说", "终于", "然后"} & set(engine.names))

    def test_second_unlabelled_natural_pair_is_recovered_without_fragments(self) -> None:
        engine = DepthAnalysisEngine(_snapshot([
            "周砚沿河走到码头，拿出一张船票。",
            "阿岚把绳索抛给周砚，两人一起把船拖到岸边。",
        ]))
        self.assertEqual(set(engine.names), {"周砚", "阿岚"})

    def test_negative_predicates_do_not_create_positive_relations_or_payoffs(self) -> None:
        negative = DepthAnalysisEngine(_snapshot([
            "林舟没有把钥匙交给顾遥，他只是拒绝了顾遥的请求。",
            "顾遥没有用钥匙打开门，她把钥匙放回桌上。",
            "因为门没有打开，所以林舟没有进入房间。",
        ])).build()
        self.assertFalse(any(event.plotline_status == "resolved" for event in negative.plot.events))
        self.assertTrue(all("明确展示了该行动带来的下一步推进" not in event.consequence for event in negative.plot.events))
        self.assertFalse(any(relation.relation_type == "enables" for relation in negative.plot.relations))
        self.assertFalse(any(relation.relation_type == "allies" for relation in negative.characters.relations))
        self.assertFalse(negative.foreshadowing.threads)
        self.assertFalse(any(state.status == "paid_off" for state in negative.foreshadowing.states))
        self.assertTrue(any(relation.relation_type == "causes" for relation in negative.plot.relations))
        negative_causes = [
            relation for relation in negative.plot.relations if relation.relation_type == "causes"
        ]
        self.assertTrue(all("负向因果" in relation.explanation for relation in negative_causes))
        self.assertTrue(all(item.emotional_valence is None or item.emotional_valence <= 0
                            for item in negative.reader_experience.items))
        self.assertTrue(all("尚未显示完整回收" in item.payoff for item in negative.reader_experience.items))

    def test_positive_controls_keep_affirmative_status_transfer_and_payoff(self) -> None:
        positive = DepthAnalysisEngine(_snapshot([
            "林舟把钥匙交给顾遥。",
            "顾遥用钥匙打开门。",
            "因为门打开了，所以林舟进入房间。",
        ])).build()
        self.assertTrue(any(event.plotline_status == "resolved" for event in positive.plot.events))
        self.assertTrue(any(relation.relation_type == "enables" for relation in positive.plot.relations))
        self.assertTrue(any(state.status == "paid_off" for state in positive.foreshadowing.states))
        self.assertTrue(any(relation.relation_type == "causes" for relation in positive.plot.relations))
        self.assertTrue(any("明确展示了该行动带来的下一步推进" in event.consequence
                            for event in positive.plot.events))

    def test_local_negation_variants_and_lexical_not_controls(self) -> None:
        negative_texts = [
            "林舟未找到钥匙。",
            "林舟并未打开门。",
            "林舟从未进入房间。",
            "林舟不曾帮助顾遥。",
            "林舟拒绝合作。",
        ]
        for text in negative_texts:
            with self.subTest(text=text):
                report = DepthAnalysisEngine(_snapshot([text])).build()
                event = report.plot.events[0]
                self.assertNotEqual(event.plotline_status, "resolved")
                self.assertNotIn("明确展示了该行动带来的下一步推进", event.consequence)

        affirmative_texts = [
            "无意间找到钥匙。",
            "不久后打开门。",
            "无论如何都要找到答案。",
            "不但帮助还公开真相。",
            "不是没有找到钥匙。",
        ]
        for text in affirmative_texts:
            with self.subTest(text=text):
                report = DepthAnalysisEngine(_snapshot([text])).build()
                event = report.plot.events[0]
                self.assertEqual(event.plotline_status, "resolved")
                self.assertIn("明确展示了该行动带来的下一步推进", event.consequence)

    def test_negated_object_does_not_bypass_affirmative_action_gate(self) -> None:
        cases = [
            "林舟没有找到答案。",
            "周砚没有找到答案。",
            "顾遥终于没有找到答案。",
            "阿岚并未打开门。",
            "林舟没有解释线索。",
        ]
        for text in cases:
            with self.subTest(text=text):
                report = DepthAnalysisEngine(_snapshot([text])).build()
                event = report.plot.events[0]
                reader = report.reader_experience.items[0]
                self.assertNotEqual(event.plotline_status, "resolved")
                self.assertNotIn("明确展示了该行动带来的下一步推进", event.consequence)
                self.assertLessEqual(reader.emotional_valence or 0.0, 0.0)
                self.assertNotIn("阶段性回应或情绪缓解", reader.payoff)

        mixed = DepthAnalysisEngine(_snapshot(["林舟没有找到答案，但后来打开了门。"])).build()
        self.assertEqual(mixed.plot.events[0].plotline_status, "resolved")
        self.assertIn("明确展示了该行动带来的下一步推进", mixed.plot.events[0].consequence)
        self.assertIn("同时呈现了未完成或受阻尝试，以及后续肯定行动", mixed.plot.events[0].conclusion)

    def test_refused_transfer_cannot_become_allies(self) -> None:
        report = DepthAnalysisEngine(_snapshot([
            "林舟拒绝把钥匙交给顾遥。",
        ], character_names=("林舟", "顾遥"))).build()
        self.assertFalse(any(relation.relation_type == "allies" for relation in report.characters.relations))
        self.assertTrue(any(relation.relation_type == "opposes" for relation in report.characters.relations))

    def test_blocking_verbs_do_not_count_as_completion_transfer_or_payoff(self) -> None:
        for blocker in ("阻止", "阻拦", "制止", "避免", "防止", "不让"):
            with self.subTest(blocker=blocker):
                report = DepthAnalysisEngine(_snapshot([
                    "顾遥把钥匙交给林舟。",
                    f"林舟{blocker}顾遥用钥匙打开门。",
                ])).build()
                event = report.plot.events[-1]
                self.assertEqual(event.plotline_status, "turning")
                self.assertNotIn("明确展示了该行动带来的下一步推进", event.consequence)
                self.assertFalse(any(relation.relation_type == "enables" for relation in report.plot.relations))
                self.assertFalse(any(state.status == "paid_off" for state in report.foreshadowing.states))
                reader = report.reader_experience.items[-1]
                self.assertLessEqual(reader.emotional_valence or 0.0, 0.0)
                self.assertNotIn("阶段性回应或情绪缓解", reader.payoff)

        independent = DepthAnalysisEngine(_snapshot([
            "林舟阻止顾遥打开门，后来自己打开了门。",
        ])).build()
        self.assertEqual(independent.plot.events[0].plotline_status, "resolved")
        self.assertIn("明确展示了该行动带来的下一步推进", independent.plot.events[0].consequence)

    def test_capability_and_permission_negation_blocks_all_positive_chains(self) -> None:
        denials = ("不可能", "不可以", "不可", "不能够", "没办法", "没有办法", "禁止", "不允许")
        for denial in denials:
            with self.subTest(denial=denial):
                relation_report = DepthAnalysisEngine(_snapshot([
                    f"林舟{denial}把钥匙交给顾遥。",
                ], character_names=("林舟", "顾遥"))).build()
                event = relation_report.plot.events[0]
                self.assertNotEqual(event.plotline_status, "resolved")
                self.assertFalse(any(
                    relation.relation_type == "allies"
                    for relation in relation_report.characters.relations
                ))

                chain_report = DepthAnalysisEngine(_snapshot([
                    "林舟把钥匙交给顾遥。",
                    f"顾遥{denial}用钥匙打开门。",
                ], character_names=("林舟", "顾遥"))).build()
                blocked = chain_report.plot.events[-1]
                self.assertNotEqual(blocked.plotline_status, "resolved")
                self.assertNotIn("明确展示了该行动带来的下一步推进", blocked.consequence)
                self.assertFalse(any(
                    relation.relation_type == "enables"
                    for relation in chain_report.plot.relations
                ))
                self.assertFalse(any(
                    state.status == "paid_off"
                    for state in chain_report.foreshadowing.states
                ))
                reader = chain_report.reader_experience.items[-1]
                self.assertLessEqual(reader.emotional_valence or 0.0, 0.0)
                self.assertNotIn("阶段性回应或情绪缓解", reader.payoff)

        for text in ("不久后打开门。", "不但帮助还公开真相。", "无意间找到钥匙。", "无论如何都要找到答案。"):
            with self.subTest(affirmative=text):
                report = DepthAnalysisEngine(_snapshot([text])).build()
                self.assertEqual(report.plot.events[0].plotline_status, "resolved")
        double_negative = DepthAnalysisEngine(_snapshot(["不是没有找到钥匙。"])).build()
        self.assertEqual(double_negative.plot.events[0].plotline_status, "resolved")

    def test_noun_and_waiting_sentences_do_not_create_completion_or_reader_payoff(self) -> None:
        for text in ("答案仍在桌上。", "林舟等待答案。"):
            with self.subTest(text=text):
                report = DepthAnalysisEngine(_snapshot([text])).build()
                event = report.plot.events[0]
                reader = report.reader_experience.items[0]
                self.assertNotEqual(event.plotline_status, "resolved")
                self.assertNotIn("明确展示了该行动带来的下一步推进", event.consequence)
                self.assertLessEqual(reader.emotional_valence or 0.0, 0.0)
                self.assertNotIn("阶段性回应或情绪缓解", reader.payoff)

    def test_mixed_polarity_cause_describes_each_side_without_inventing_negative_later_state(self) -> None:
        report = DepthAnalysisEngine(_snapshot([
            "因为门没有打开，所以林舟进入房间。",
        ])).build()
        causes = [relation for relation in report.plot.relations if relation.relation_type == "causes"]
        self.assertEqual(len(causes), 1)
        self.assertIn("前一状态未发生或未完成", causes[0].conclusion)
        self.assertIn("后一事件仍按正文呈现", causes[0].conclusion)
        self.assertNotIn("后一负向状态", causes[0].conclusion)
        self.assertIn("负向因果", causes[0].explanation)

    def test_required_depth_text_fields_reject_whitespace_but_empty_chapter_title_is_allowed(self) -> None:
        base = {
            "item_id": "item1",
            "kind": "character",
            "category": "人物",
            "conclusion": "有证据的结论",
            "epistemic_status": "unknown",
            "chapter_ids": ["c1"],
            "normalized_start": 0.0,
            "normalized_end": 100.0,
            "evidence_ids": [],
            "related_item_ids": [],
            "confidence": 0.0,
            "uncertainty": ["信息不足"],
        }
        for field, value in (
            ("category", " \t\n"),
            ("conclusion", " \t\n"),
        ):
            payload = {**base, field: value}
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    DepthAnalysisItem.model_validate(payload)
        with self.assertRaises(ValidationError):
            DepthView.model_validate({"summary": " \t\n", "uncertainty": []})
        with self.assertRaises(ValidationError):
            DepthView.model_validate({"summary": "总结", "uncertainty": [" \t\n"]})

        character = {
            **base,
            "name": "人物",
            "aliases": [],
            "role": "角色",
            "motivation": "动机",
            "inner_conflict": "冲突",
            "arc_summary": "弧线",
        }
        with self.assertRaises(ValidationError):
            DepthCharacter.model_validate({**character, "name": " \t\n"})

        plotline = {
            **{**base, "item_id": "line1", "kind": "plotline"},
            "title": "剧情",
            "central_question": "问题",
            "stakes": "代价",
            "resolution": "未定",
            "character_ids": [],
        }
        with self.assertRaises(ValidationError):
            DepthPlotline.model_validate({**plotline, "title": "\n\t"})

        foreshadowing = {
            **{**base, "item_id": "thread1", "kind": "foreshadowing"},
            "label": "线索",
            "planted_detail": "种下",
            "expected_payoff": "回收",
            "interpretation": "解释",
        }
        with self.assertRaises(ValidationError):
            DepthForeshadowing.model_validate({**foreshadowing, "label": " \n"})

        evidence = {
            "project_id": "project32",
            "document_id": "document32",
            "source_version_id": "version32",
            "source_revision": 1,
            "source_hash": "a" * 64,
            "evidence_id": "ev1",
            "chapter_id": "c1",
            "chapter_number": 1,
            "granularity": "span",
            "start_offset": 0,
            "end_offset": 1,
            "excerpt": "证",
            "label": "证据",
        }
        with self.assertRaises(ValidationError):
            DepthEvidence.model_validate({**evidence, "label": "\t\r\n"})

        technique = {
            **{**base, "item_id": "tech1", "kind": "technique", "evidence_ids": ["ev1"]},
            "technique": "动作",
            "observation": "观察",
            "mechanism": "机制",
            "effect": "效果",
            "learning_note": "学习",
            "applicability": "适用",
            "example_evidence_ids": ["ev1"],
        }
        with self.assertRaises(ValidationError):
            DepthTechnique.model_validate({**technique, "technique": " \n"})

        empty_title = DepthChapter.model_validate({
            "chapter_id": "c1",
            "chapter_number": 1,
            "title": "",
            "utf16_length": 0,
            "normalized_start": 0.0,
            "normalized_end": 0.0,
        })
        self.assertEqual(empty_title.title, "")

    def test_depth_ids_are_span_anchored_and_order_independent(self) -> None:
        snapshot = _snapshot([
            "林舟把钥匙交给顾遥。顾遥决定打开门。",
            "顾遥找到旧信。林舟公开真相。",
        ])
        first = DepthAnalysisEngine(snapshot)
        first._build_events()  # noqa: SLF001 - inspect deterministic event anchors.
        first_event_ids = {event.event_id for event in first.events}
        second = DepthAnalysisEngine(snapshot)
        second.segments_by_chapter = {
            chapter_id: list(reversed(segments))
            for chapter_id, segments in second.segments_by_chapter.items()
        }
        second._build_events()  # noqa: SLF001 - reorder only internal traversal.
        second_event_ids = {event.event_id for event in second.events}
        self.assertEqual(first_event_ids, second_event_ids)
        self.assertEqual(len(first_event_ids), len(first.events))

        first_report = DepthAnalysisEngine(snapshot).build()
        reversed_snapshot = DepthSnapshot(
            project_id=snapshot.project_id,
            document_id=snapshot.document_id,
            source_version_id=snapshot.source_version_id,
            source_revision=snapshot.source_revision,
            source_hash=snapshot.source_hash,
            chapters=tuple(reversed(snapshot.chapters)),
        )
        reversed_report = DepthAnalysisEngine(reversed_snapshot).build()
        self.assertEqual(
            {item.item_id for item in first_report.analysis_items()},
            {item.item_id for item in reversed_report.analysis_items()},
        )

        evidence_engine = DepthAnalysisEngine(_snapshot(["林舟打开门。"]))
        chapter = evidence_engine.chapters[0]
        left = evidence_engine.evidence.span(chapter, 0, 2, "片段")
        right = evidence_engine.evidence.span(chapter, 2, 5, "片段")
        self.assertNotEqual(left, right)

    def test_scene_and_colour_repetition_do_not_invent_people_or_paid_off_thread(self) -> None:
        scenery = DepthAnalysisEngine(_snapshot(["雨落在空庭。天色暗了。石阶上积起了水。"])).build()
        self.assertEqual(scenery.characters.characters, [])
        self.assertEqual(scenery.foreshadowing.threads, [])
        colours = DepthAnalysisEngine(_snapshot([
            "林舟看见墙是蓝色的，然后离开。",
            "顾遥看见海是蓝色的，然后回家。",
        ])).build()
        self.assertEqual(colours.characters.characters, [])
        self.assertFalse(any(item.status == "paid_off" for item in colours.foreshadowing.states))

    def test_empty_sidecar_uses_zero_as_cas_revision(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage32-cas-") as temporary:
            store = DeconstructionStore(Path(temporary) / "deconstruction")
            record = DeconstructionProjectRecord(
                project_id="cas-project",
                account_id="cas-account",
                record_revision=3,
            )
            with self.assertRaises(DeconstructionStoreConflict):
                store.save(record)

    def test_project_lock_release_failure_does_not_poison_in_process_mutex(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage32-lock-") as temporary:
            locks = ProjectLockStore(Path(temporary))
            original = locks._release_os
            locks._release_os = lambda descriptor: (_ for _ in ()).throw(OSError("injected"))
            with self.assertRaises(ProjectLockError):
                with locks.project_lock("release-project"):
                    pass
            locks._release_os = original
            with locks.project_lock("release-project"):
                pass

    def test_transaction_and_deconstruction_share_ordered_project_gate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage32-order-") as temporary:
            root = Path(temporary)
            transaction_store = TransactionStore(root / "transactions")
            deconstruction_store = DeconstructionStore(root / "deconstruction")
            barrier = threading.Barrier(2)
            entered: list[str] = []
            errors: list[BaseException] = []

            def transaction_worker() -> None:
                try:
                    barrier.wait(timeout=2)
                    with transaction_store.project_lock("ordered-project"):
                        entered.append("transaction")
                        time.sleep(0.04)
                except BaseException as exc:  # surfaced below, not swallowed
                    errors.append(exc)

            def deconstruction_worker() -> None:
                try:
                    barrier.wait(timeout=2)
                    with deconstruction_store.project_locks.project_lock("ordered-project"):
                        entered.append("deconstruction")
                        time.sleep(0.04)
                except BaseException as exc:
                    errors.append(exc)

            first = threading.Thread(target=transaction_worker)
            second = threading.Thread(target=deconstruction_worker)
            first.start()
            second.start()
            first.join(3)
            second.join(3)
            self.assertFalse(first.is_alive(), "transaction/deconstruction lock order deadlocked")
            self.assertFalse(second.is_alive(), "transaction/deconstruction lock order deadlocked")
            self.assertFalse(errors)
            self.assertEqual(set(entered), {"transaction", "deconstruction"})

    def test_spawned_transaction_and_deconstruction_locks_are_mutually_exclusive(self) -> None:
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory(prefix="stage32-spawn-lock-") as temporary:
            first_entered = context.Event()
            first_release = context.Event()
            second_entered = context.Event()
            second_release = context.Event()
            result_queue = context.Queue()
            first = context.Process(
                target=_hold_shared_project_lock,
                args=(temporary, "transaction", first_entered, first_release, result_queue),
            )
            second = context.Process(
                target=_hold_shared_project_lock,
                args=(temporary, "deconstruction", second_entered, second_release, result_queue),
            )
            processes = (first, second)
            try:
                first.start()
                self.assertTrue(first_entered.wait(5), "transaction child did not acquire the project lock")
                self.assertEqual(result_queue.get(timeout=5), ("entered", "transaction"))

                second.start()
                self.assertFalse(
                    second_entered.wait(0.35),
                    "deconstruction child entered while transaction child still held the shared lock",
                )
                first_release.set()
                first.join(8)
                self.assertFalse(first.is_alive(), "transaction child did not release the shared lock")
                self.assertEqual(first.exitcode, 0)

                self.assertTrue(second_entered.wait(5), "deconstruction child did not acquire after release")
                self.assertEqual(result_queue.get(timeout=5), ("entered", "deconstruction"))
                second_release.set()
                second.join(8)
                self.assertFalse(second.is_alive(), "deconstruction child did not release the shared lock")
                self.assertEqual(second.exitcode, 0)

                with TransactionStore(Path(temporary) / "transactions").project_lock("shared-project"):
                    pass
                with DeconstructionStore(Path(temporary) / "deconstruction").project_locks.project_lock("shared-project"):
                    pass
            finally:
                first_release.set()
                second_release.set()
                for process in processes:
                    process.join(2)
                    if process.is_alive():
                        process.terminate()
                        process.join(5)

    def test_retry_during_old_publish_cannot_overwrite_newer_queued_document(self) -> None:
        project_id = "interleave-project"
        account_id = "interleave-account"
        content = "林舟推开钟楼的门。顾遥在河岸等他。"
        with tempfile.TemporaryDirectory(prefix="stage32-retry-publish-") as temporary:
            root = Path(temporary)
            IndependentStore(root / "independent").save(
                _independent_record(project_id, account_id, content)
            )
            service_one = DeconstructionService(
                independent=IndependentWorkspaceService(store=IndependentStore(root / "independent")),
                store=DeconstructionStore(root / "deconstruction"),
            )
            service_two = DeconstructionService(
                independent=IndependentWorkspaceService(store=IndependentStore(root / "independent")),
                store=DeconstructionStore(root / "deconstruction"),
            )
            queued = service_one.enqueue_for_project(project_id, account_id)
            build_started = threading.Event()
            release_build = threading.Event()
            original_build = service_one._build_document

            def blocked_build(source, document):
                build_started.set()
                if not release_build.wait(5):
                    raise RuntimeError("test build gate timed out")
                return original_build(source, document)

            service_one._build_document = blocked_build  # type: ignore[method-assign]
            worker_result: list[object] = []
            worker_errors: list[BaseException] = []

            def old_worker() -> None:
                try:
                    worker_result.append(
                        service_one.run_document(project_id, account_id, queued.document_id)
                    )
                except BaseException as exc:
                    worker_errors.append(exc)

            worker = threading.Thread(target=old_worker)
            worker.start()
            try:
                self.assertTrue(build_started.wait(5), "old worker did not reach its unlocked analysis phase")
                service_two._mark_failed(  # noqa: SLF001 - exercise the durable retry transition.
                    project_id,
                    account_id,
                    queued.document_id,
                    "test failure before retry",
                )
                retried = service_two.retry(project_id, account_id, queued.document_id)
                self.assertEqual(retried.status, "queued")
                self.assertEqual(retried.retry_count, 1)
                release_build.set()
                worker.join(8)
                self.assertFalse(worker.is_alive(), "old worker did not finish after retry")
                self.assertFalse(worker_errors)
                self.assertEqual(worker_result[0].status, "queued")

                current = service_two.store.load(project_id)
                self.assertIsNotNone(current)
                current_document = next(item for item in current.documents if item.document_id == queued.document_id)
                self.assertEqual(current_document.status, "queued")
                self.assertIsNone(current_document.report)
                revision_after_retry = current.record_revision

                service_two.process_background_tasks()
                completed = service_two.store.load(project_id)
                self.assertIsNotNone(completed)
                completed_document = next(item for item in completed.documents if item.document_id == queued.document_id)
                self.assertEqual(completed_document.status, "completed")
                self.assertIsNotNone(completed_document.report)
                self.assertGreater(completed.record_revision, revision_after_retry)
            finally:
                release_build.set()
                worker.join(8)
                service_one._build_document = original_build  # type: ignore[method-assign]

    def test_author_save_waits_for_run_task_and_preserves_revision_and_outbox(self) -> None:
        project_id = "author-worker-project"
        account_id = "author-worker-account"
        with tempfile.TemporaryDirectory(prefix="stage32-author-worker-") as temporary:
            store = IndependentStore(Path(temporary) / "independent")
            service = IndependentWorkspaceService(store=store)
            service.start_blank(project_id, account_id)
            chapter = service.workspace(project_id, account_id)["active_version"].chapters[0]
            draft = service.save_draft(
                project_id,
                account_id,
                chapter.chapter_id,
                content="林舟推开钟楼的门。",
                title=None,
                expected_revision=chapter.server_revision,
            )
            task = service.complete_chapter(
                project_id,
                account_id,
                draft.chapter_id,
                content=draft.content,
                expected_revision=draft.server_revision,
                idempotency_key="author-worker-task",
            )
            analysis_started = threading.Event()
            release_analysis = threading.Event()
            original_analysis = service._run_chapter_analysis

            def blocked_analysis(record, pending_task):
                analysis_started.set()
                if not release_analysis.wait(5):
                    raise RuntimeError("test analysis gate timed out")
                return original_analysis(record, pending_task)

            service._run_chapter_analysis = blocked_analysis  # type: ignore[method-assign]
            run_errors: list[BaseException] = []
            author_errors: list[BaseException] = []
            author_done = threading.Event()
            author_result: list[object] = []

            def run_worker() -> None:
                try:
                    service.run_task(project_id, account_id, task.task_id)
                except BaseException as exc:
                    run_errors.append(exc)

            def author_worker() -> None:
                try:
                    author_result.append(
                        service.save_draft(
                            project_id,
                            account_id,
                            draft.chapter_id,
                            content="林舟决定把真相写进档案。",
                            title=None,
                            expected_revision=draft.server_revision,
                        )
                    )
                except BaseException as exc:
                    author_errors.append(exc)
                finally:
                    author_done.set()

            run_thread = threading.Thread(target=run_worker)
            run_thread.start()
            try:
                self.assertTrue(analysis_started.wait(5), "run_task did not reach its analysis phase")
                author_thread = threading.Thread(target=author_worker)
                author_thread.start()
                self.assertFalse(author_done.wait(0.35), "author write bypassed the running task project lock")
                release_analysis.set()
                run_thread.join(8)
                author_thread.join(8)
                self.assertFalse(run_thread.is_alive())
                self.assertFalse(author_thread.is_alive())
                self.assertFalse(run_errors)
                self.assertFalse(author_errors)
                self.assertEqual(len(author_result), 1)

                persisted = store.load(project_id)
                self.assertIsNotNone(persisted)
                persisted_chapter = persisted.versions[0].chapters[0]
                self.assertEqual(persisted_chapter.content, "林舟决定把真相写进档案。")
                self.assertEqual(persisted_chapter.server_revision, 2)
                self.assertTrue(persisted.deconstruction_outbox)
                self.assertEqual(persisted.tasks[0].status, "completed")
            finally:
                release_analysis.set()
                run_thread.join(8)
                service._run_chapter_analysis = original_analysis  # type: ignore[method-assign]


if __name__ == "__main__":
    unittest.main()
