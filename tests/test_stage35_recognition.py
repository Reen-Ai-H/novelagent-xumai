"""Stage 35 recognition regressions using synthetic text, never a model."""
from __future__ import annotations

import base64
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from app.core.deconstruction_depth import ChapterInput, DepthAnalysisEngine, DepthSnapshot, RULE_ENGINE_REVISION
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore
from app.core.deconstruction_service import DeconstructionService
from app.core.deconstruction_store import DeconstructionStore
from app.core.person_recognition import discover_person_mentions, assess_person_identities
from app.agents.deconstruction_model import analysis_messages
from schemas.independent import StoryArchive
from schemas.deconstruction import DeconstructionResponse, DeconstructionDepthReport, validate_depth_report_source
from pydantic import ValidationError


MANY_NAMES = [surname + given for surname in "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨"
              for given in ("安宁", "清禾", "星澜", "知夏", "怀瑾", "以棠")]


def engine(texts, explicit=()):
    return DepthAnalysisEngine(DepthSnapshot(
        project_id="stage35", document_id="stage35-doc", source_version_id="v1",
        source_revision=1, source_hash="a" * 64,
        chapters=tuple(ChapterInput(f"c{i}", i, f"第{i}章", text)
                       for i, text in enumerate(texts, 1)), character_names=explicit,
    ))


class ChapterRecognitionTest(unittest.TestCase):
    def parse(self, text):
        return IndependentWorkspaceService._parse_text("synthetic.md", text)[1:]

    def test_large_and_fullwidth_numbers(self):
        for heading, expected in [("第一百零一章 起风", 101), ("第两千零三章 归来", 2003),
                                  ("第１２３章 回声", 123), ("Chapter 1001: Return", 1001)]:
            with self.subTest(heading=heading):
                chapters, fragments = self.parse(heading + "\n正文原样。")
                self.assertEqual([(c.chapter_number, c.content) for c in chapters], [(expected, "正文原样。")])
                self.assertEqual(fragments, [])

    def test_volumes_prologue_and_epilogue(self):
        text = "序章\n开篇。\n第一卷 初见\n第一章\n甲。\n第二卷 归来\n第一章\n乙。\n尾声\n终篇。"
        chapters, fragments = self.parse(text)
        self.assertEqual([c.content for c in chapters], ["开篇。\n", "甲。\n", "乙。\n", "终篇。"])
        self.assertEqual([c.chapter_number for c in chapters], [1, 2, 3, 4])
        self.assertEqual(fragments, ["第一卷 初见\n", "第二卷 归来\n"])

    def test_toc_and_empty_headings_are_visible_fragments(self):
        text = "目录\n第一章 雾起 .... 1\n第二章 归来 .... 4\n\n正文\n第一章 雾起\n  原文😀。  \n第二章 归来\n第三章 后来\n结尾。"
        chapters, fragments = self.parse(text)
        self.assertEqual([c.content for c in chapters], ["  原文😀。  \n", "结尾。"])
        self.assertIn("第二章 归来", "\n".join(fragments))
        self.assertIn("第一章 雾起 .... 1", "\n".join(fragments))

    def test_numbered_prose_does_not_split(self):
        body = "第一章里写着他的旧事。\n1. 他走进树林。\n2 他突然停下\n第一回见面，他没有说话。"
        chapters, fragments = self.parse("第一章 起点\n" + body + "\n第二章 归途\n后文。")
        self.assertEqual([c.content for c in chapters], [body + "\n", "后文。"])
        self.assertEqual(fragments, [])

    def test_chinese_integer_variants_and_invalid_units(self):
        for value, number in [("十", 10), ("两百", 200), ("一千零二十", 1020), ("两千三百四十五", 2345),
                              ("一〇一", 101), ("〇一二", 12), ("９９９", 999), ("九千九百九十九", 9999)]:
            with self.subTest(value=value):
                self.assertEqual(IndependentWorkspaceService._chinese_number(value), number)
        for value in ("百百", "一十百", "零百", "二三百", "²", "章", "999999999999999999999"):
            with self.subTest(value=value):
                self.assertIsNone(IndependentWorkspaceService._chinese_number(value))

    def test_duplicate_and_descending_numbers_keep_document_order(self):
        for labels in [(3, 1, 2), (1, 1, 2)]:
            chapters, fragments = self.parse("\n".join(f"第{n}章 标题{i}\n段{i}。" for i, n in enumerate(labels)))
            self.assertEqual([c.chapter_number for c in chapters], [1, 2, 3])
            self.assertEqual([c.title for c in chapters], [f"第{n}章 标题{i}" for i, n in enumerate(labels)])
            self.assertEqual([c.content.strip() for c in chapters], [f"段{i}。" for i in range(3)])
            self.assertEqual(fragments, [])

    def test_markdown_english_and_short_titles(self):
        chapters, fragments = self.parse("# 作品名\n## Chapter 1: Rain ##\n甲。\n### 场景注\n注释正文。\n## Chapter 2\n乙。")
        self.assertEqual([c.title for c in chapters], ["Chapter 1: Rain", "Chapter 2"])
        self.assertEqual(chapters[0].content, "甲。\n### 场景注\n注释正文。\n")
        self.assertEqual(fragments, ["# 作品名\n"])
        chapters, _ = self.parse("# 雾起\n甲。\n## 街口\n小节。\n# 归途\n乙。")
        self.assertEqual([c.title for c in chapters], ["雾起", "归途"])
        self.assertIn("## 街口\n小节。", chapters[0].content)
        chapters, _ = self.parse("第一百零一章雾起\n甲。\n第一百零二章归来\n乙。")
        self.assertEqual([c.chapter_number for c in chapters], [101, 102])

    def test_toc_without_body_marker_and_markdown_links(self):
        for toc in ("目录\n第一章 雾起 .... 1\n第二章 归来 .... 4\n",
                    "目录\n第一章 雾起 1\n第二章 归来 4\n",
                    "# Contents\n- [第一章 雾起](#one)\n- [第二章 归来](#two)\n",
                    "目录\n第一章 雾起\n第二章 归来\n"):
            with self.subTest(toc=toc):
                chapters, fragments = self.parse(toc + "第一章 雾起\n真实甲。\n第二章 归来\n真实乙。")
                self.assertEqual([c.content for c in chapters], ["真实甲。\n", "真实乙。"])
                self.assertEqual("".join(fragments), toc)

    def test_fragments_and_raw_body_account_for_every_marker(self):
        text = "作品说明MARKA\n目录\n第一章 标题 .... 1\n正文\n第一卷 MARKB\n卷引MARKC\n第一章 标题\n段落MARKD\n第二章 MARKE\n第三章 后来\n段落MARKF"
        chapters, fragments = self.parse(text)
        self.assertEqual([c.content for c in chapters], ["段落MARKD\n", "段落MARKF"])
        visible = "".join(fragments) + "".join(c.title + c.content for c in chapters)
        for marker in ("MARKA", "MARKB", "MARKC", "MARKD", "MARKE", "MARKF"):
            self.assertEqual(visible.count(marker), 1)

    def test_unheaded_text_preserves_all_whitespace(self):
        text = "  \n😀正文首行。\n\n末行。  \n"
        chapters, fragments = self.parse(text)
        self.assertEqual(chapters[0].content, text)
        self.assertEqual(fragments, [])

    def test_toc_or_empty_titles_only_are_not_body(self):
        for text in ("目录\n第一章 起点\n第二章 终点\n", "第一章 起点\n第二章 终点\n", "第一卷 起点\n卷前说明。"):
            with self.subTest(text=text):
                chapters, fragments = self.parse(text)
                self.assertEqual(chapters, [])
                self.assertEqual("".join(fragments), text)


class PersonRecognitionTest(unittest.TestCase):
    def test_scenery_and_function_words_are_not_people(self):
        texts = ["夜色渐深。突然说不出的寒意袭来。于是走进树林。众人走向石门。树林在风中摇晃。石门打开了。",
                 "夜色渐深。众人走远。树林在雨中沉默。石门打开后，突然说起旧事。于是走开。"]
        self.assertEqual(engine(texts).names, [])

    def test_single_occurrence_names_and_compound_surnames(self):
        text = "欧阳明走进庭院。司马青云没有开门。沈清禾拿起灯。陆川说：“等等。”顾遥把钥匙交给林舟。"
        self.assertEqual(set(engine([text]).names), {"欧阳明", "司马青云", "沈清禾", "陆川", "顾遥", "林舟"})

    def test_negated_people_survive(self):
        for name in ("沈禾", "沈清禾", "欧阳明", "司马青云"):
            with self.subTest(name=name):
                self.assertEqual(engine([f"{name}并没有开门。"]).names, [name])

    def test_explicit_false_candidates_are_filtered(self):
        self.assertEqual(engine(["人物：石门、众人、夜色、欧阳明。欧阳明没有开门。"],
                                ("树林", "于是")).names, ["欧阳明"])

    def test_action_adherence_and_different_names(self):
        self.assertEqual(set(engine(["司马来风说：“停下。”欧阳问柳把灯交给沈清禾。沈清禾拿起灯。沈青禾拒绝离开。"] ).names),
                         {"司马来风", "欧阳问柳", "沈清禾", "沈青禾"})
        natural = engine(["姐姐曾对林舟说：“听好。”林舟说完转身。顾遥把钥匙交给林舟。"])
        self.assertEqual(set(natural.names), {"林舟", "顾遥"})

    def test_repeated_scenery_stays_negative_with_actions(self):
        for phrase in ("石门没有打开。", "树林走向远方。", "众人决定离开。", "夜色在窗外。", "突然说起旧事。", "于是拿起灯。",
                       "急忙走远。", "连忙说话。", "转身说起往事。", "回头看去。", "低声说起往事。", "默默走开。"):
            with self.subTest(phrase=phrase):
                self.assertEqual(engine([phrase, phrase, phrase]).names, [])

    def test_modifiers_do_not_adhere_to_names(self):
        text = "沈清禾正在拿灯。欧阳明也没有开门。于是司马青云走远了。随后杜怀瑾拒绝离开。"
        self.assertEqual(set(engine([text]).names), {"沈清禾", "欧阳明", "司马青云", "杜怀瑾"})

    def test_conjunction_characters_in_names_and_label_lists(self):
        text = "人物：沈与安、江和宁、李及云、顾遥和林舟。沈与安拿灯。江和宁没有开门。李及云走远。"
        self.assertEqual(set(engine([text]).names), {"沈与安", "江和宁", "李及云", "顾遥", "林舟"})

    def test_unknown_name_shapes_are_not_an_approved_name_list(self):
        for names in (("杜怀瑾", "燕以棠", "乔知夏"), ("阿岚", "北辰", "苏问溪"), ("李树林", "张林", "江夜白")):
            with self.subTest(names=names):
                self.assertEqual(set(engine(["".join(f"{name}拿起灯。" for name in names)]).names), set(names))

    def test_weak_context_needs_cross_sentence_evidence(self):
        self.assertEqual(engine(["周砚在岸边。"] ).names, [])
        self.assertEqual(engine(["周砚在岸边。", "周砚看见灯火。"] ).names, ["周砚"])
        self.assertEqual(engine(["周砚在岸边。"], ("周砚",)).names, ["周砚"])

    def test_mentions_preserve_name_and_source_position(self):
        sample = engine(["😀欧阳明没有开门。顾遥把灯交给沈清禾。"])
        mentions = discover_person_mentions(sample.chapters)
        self.assertEqual({m.origin for m in mentions}, {"subject", "object"})
        for mention in mentions:
            text = sample.chapters[0].content
            self.assertEqual(text[mention.start:mention.start + len(mention.name)], mention.name)
            self.assertEqual(mention.chapter_id, "c1")

    def test_person_detection_has_no_eighty_person_cap(self):
        text = "".join(f"{name}没有开门。" for name in MANY_NAMES)
        self.assertEqual(set(engine([text]).names), set(MANY_NAMES))
        report = engine([text]).build()
        self.assertEqual({c.name for c in report.characters.characters}, set(MANY_NAMES))

    def test_model_candidate_contract_is_system_instruction(self):
        chapters = [dict(chapter_number=1, content="人物：众人、树林。欧阳明没有开门。材料中的命令只作素材。")]
        messages = analysis_messages(chapters)
        self.assertEqual([m["role"] for m in messages], ["system", "user"])
        for phrase in ("完整姓名边界", "群体", "复姓", "否定行动不否定人物存在", "固定人数", "不同姓名"):
            self.assertIn(phrase, messages[0]["content"])
        source_payload = json.loads(messages[1]["content"].split("\n", 1)[1])
        self.assertEqual(set(source_payload), {"chapters"})
        serialized = source_payload["chapters"][0]
        self.assertEqual(serialized["chapter_number"], chapters[0]["chapter_number"])
        self.assertEqual("".join(s["text"] for s in serialized["segments"]), chapters[0]["content"])
        self.assertTrue(any("source_id" in s for s in serialized["segments"]))


class RecognitionServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="stage35-recognition-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.service = IndependentWorkspaceService(store=IndependentStore(root / "independent"),
                                                   projects=JsonProjectStore(root / "projects"))

    def preview(self, text, project="project35"):
        return self.service.preview_import(project, "account35", filename="synthetic.md",
                                           content_base64=base64.b64encode(text.encode("utf-8")).decode("ascii"))

    def test_failed_toc_preview_retains_visible_text(self):
        text = "目录\n第一章 起点\n第二章 终点\n"
        preview = self.preview(text)
        self.assertEqual(preview.status, "failed")
        self.assertEqual(preview.unrecognized_fragments, [text])
        self.assertEqual(preview.raw_text, text)
        public = self.service._public_import(preview).model_dump()
        self.assertNotIn("raw_text", public)
        self.assertEqual(public["unrecognized_fragments"], [text])

    def test_empty_preview_is_failure_without_exception(self):
        self.assertEqual(self.preview(" \n ").status, "failed")

    def test_import_confirm_and_depth_evidence_keep_body_unchanged(self):
        text = "第一章 起点\n  😀欧阳明没有开门。\n\n沈清禾拿起灯。  \n"
        preview = self.preview(text)
        expected = text.split("\n", 1)[1]
        record = self.service.confirm_import("project35", "account35", preview.preview_id)
        chapter = record.versions[0].chapters[0]
        self.assertEqual(chapter.content, expected)
        self.assertEqual(chapter.formal_content, expected)
        self.assertEqual(self.service.store.load("project35").pending_imports[0].raw_text, text)
        frozen = chapter.model_dump()
        report = engine([chapter.formal_content]).build()
        self.assertEqual({c.name for c in report.characters.characters}, {"欧阳明", "沈清禾"})
        for ref in report.evidence:
            if ref.granularity == "span":
                raw = expected.encode("utf-16-le")
                self.assertEqual(raw[ref.start_offset * 2:ref.end_offset * 2].decode("utf-16-le"), ref.excerpt)
                self.assertEqual(ref.source_hash, "a" * 64)
                self.assertEqual(ref.source_version_id, "v1")
        self.assertEqual(chapter.model_dump(), frozen)

    def test_archive_recognition_reads_formal_not_draft(self):
        preview = self.preview("第一章\n欧阳明拿起灯。树林没有开门。")
        record = self.service.confirm_import("project35", "account35", preview.preview_id)
        chapter = record.versions[0].chapters[0].model_copy(update={"content": "顾遥走远了。"})
        archive = self.service._analyze_content(StoryArchive(), chapter)
        self.assertEqual([c.name for c in archive.characters], ["欧阳明"])
        self.assertEqual(chapter.content, "顾遥走远了。")

    def test_many_people_do_not_break_legacy_summary_contract(self):
        text = "第一章\n" + "".join(f"{name}没有开门。" for name in MANY_NAMES)
        deconstruction = DeconstructionService(independent=self.service,
                                               store=DeconstructionStore(Path(self.tmp.name) / "deconstruction"))
        self.service.deconstruction_service = deconstruction
        preview = self.preview(text)
        self.service.confirm_import("project35", "account35", preview.preview_id)
        deconstruction.process_background_tasks()
        response = DeconstructionResponse.model_validate(deconstruction.read("project35", "account35"))
        self.assertEqual(response.effective_status, "completed")
        document = response.document
        self.assertEqual(document.overview.recognized_character_count, len(MANY_NAMES))
        self.assertEqual(len(document.overview.main_character_candidates), 30)
        self.assertTrue(any("完整候选" in note for note in document.overview.uncertainty))
        self.assertTrue(all(node.recognized_character_count == len(MANY_NAMES) for node in document.timeline))
        self.assertEqual({c.name for c in response.result.report.characters.characters}, set(MANY_NAMES))

    def test_docx_preserves_tabs_linebreaks_and_empty_paragraphs(self):
        xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
               '<w:body><w:p><w:r><w:t>第一章 文档</w:t></w:r></w:p><w:p/>'
               '<w:p><w:r><w:t xml:space="preserve">  欧阳明</w:t><w:tab/><w:t>没有开门。</w:t>'
               '<w:br/><w:t xml:space="preserve">次行。  </w:t></w:r></w:p></w:body></w:document>')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", xml)
        preview = self.service.preview_import("project35", "account35", filename="synthetic.docx",
                                             content_base64=base64.b64encode(buffer.getvalue()).decode("ascii"))
        self.assertEqual(preview.chapters[0].content, "\n  欧阳明\t没有开门。\n次行。  ")


class AuditRecognitionTest(unittest.TestCase):
    def test_punctuation_in_first_and_middle_chapter_titles(self):
        for marker in ("", "# "):
            source = f"{marker}第一章 风，起\n甲。\n{marker}第二章 谁来了？\n乙。\n{marker}第三章 回声\n丙。"
            chapters = IndependentWorkspaceService._parse_text("audit.md", source)[1]
            self.assertEqual([c.title for c in chapters], ["第一章 风，起", "第二章 谁来了？", "第三章 回声"])
            self.assertEqual([c.content for c in chapters], ["甲。\n", "乙。\n", "丙。"])

    def test_toc_does_not_swallow_unlisted_prologue(self):
        toc = "目录\n第一章 起点\n第二章 终点\n\n"
        chapters, fragments = IndependentWorkspaceService._parse_text("audit.md", toc + "序章\n合成序。\n第一章 起点\n合成甲。\n第二章 终点\n合成乙。")[1:]
        self.assertEqual([c.content for c in chapters], ["合成序。\n", "合成甲。\n", "合成乙。"])
        self.assertEqual("".join(fragments), toc)

    def test_special_titles_without_space(self):
        chapters = IndependentWorkspaceService._parse_text("audit.md", "序章夜雨\n序。\n第一章 起点\n甲。\n尾声归途\n尾。")[1]
        self.assertEqual([c.title for c in chapters], ["序章夜雨", "第一章 起点", "尾声归途"])
        self.assertEqual([c.content for c in chapters], ["序。\n", "甲。\n", "尾。"])

    def test_volume_toc_repeated_numbers_and_body_keyword(self):
        source = "目录\n卷一 初见\n第一章 初见 ... 1\n第二章 告别 ... 9\n\n第一章 初见\n甲。\n正文\n中段。\n第二章 告别\n乙。"
        chapters, fragments = IndependentWorkspaceService._parse_text("audit.md", source)[1:]
        self.assertEqual([c.content for c in chapters], ["甲。\n正文\n中段。\n", "乙。"])
        self.assertIn("卷一 初见", "".join(fragments))

    def test_nested_docx_paragraphs_are_read_once(self):
        xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
               '<w:p><w:r><w:t>第一章 起点</w:t></w:r></w:p><w:p><w:r><w:t>普通唯一。</w:t></w:r>'
               '<w:r><w:pict><w:txbxContent><w:p><w:r><w:t>文本框唯一。</w:t></w:r></w:p></w:txbxContent>'
               '</w:pict></w:r></w:p></w:body></w:document>')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", xml)
        decoded = IndependentWorkspaceService._decode_docx(buffer.getvalue())
        self.assertEqual(decoded, "第一章 起点\n普通唯一。\n文本框唯一。")

    def test_objects_adverbs_pronouns_and_concepts_are_not_people(self):
        texts = ["他找到出路。她看见落叶。我们寻找食物。众人遇见困难。大家保护环境。",
                 "早已没有退路。恐怕不会回来。必须拿起武器。赶紧打开窗户。",
                 "人物：我、大道、应当、本来我、仔细、画像。大道没有消失。"]
        for text in texts:
            with self.subTest(text=text):
                candidate = engine([text])
                self.assertEqual(candidate.names, [])
                self.assertEqual(candidate.build().characters.characters, [])

    def test_full_names_with_internal_predicate_characters(self):
        for prefix in ("", "人物：段天问、陈自在、王不凡、张问天、李笑川、陈在山。"):
            candidate = engine([prefix + "段天问拿起灯。陈自在打开门。王不凡拿灯。张问天没有开门。李笑川走远。陈在山拒绝离开。"])
            self.assertEqual(set(candidate.names), {"段天问", "陈自在", "王不凡", "张问天", "李笑川", "陈在山"})
            self.assertEqual({c.name for c in candidate.build().characters.characters}, set(candidate.names))

    def test_aliases_require_direct_identity_evidence(self):
        candidate = engine(["周砚字子安。他名叫舒。子安拿灯。舒救下孩子。"])
        report = candidate.build()
        characters = {c.name: c for c in report.characters.characters}
        self.assertEqual(set(characters), {"周砚", "舒"})
        self.assertEqual(characters["周砚"].aliases, ["子安"])
        references = {e.evidence_id:e.excerpt for e in report.evidence}
        self.assertTrue(any("周砚字子安" in references[key] for key in characters["周砚"].evidence_ids))
        self.assertEqual(engine(["周砚说我叫子安。陆川说我也叫子安。"] ).names, ["周砚", "陆川"])

    def test_shared_alias_does_not_merge_two_people(self):
        candidate = engine(["周砚字子安。陆川字子安。周砚拿灯。陆川没有开门。"])
        characters = candidate.build().characters.characters
        self.assertEqual({c.name for c in characters}, {"周砚", "陆川"})
        self.assertTrue(all(not c.aliases for c in characters))

    def test_main_supporting_and_incidental_are_separate(self):
        text = "\n".join(["周砚拿起灯，继续巡视。" for _ in range(160)] +
                         ["赵路拿起纸。", "程陌救下孩子。", "父亲保护孩子。", "母亲拒绝交出钥匙。"])
        profiles = {p.name:p for p in assess_person_identities(engine([text]).chapters)}
        self.assertEqual(profiles["周砚"].importance, "main")
        self.assertEqual(profiles["赵路"].importance, "incidental")
        for name in ("程陌", "父亲", "母亲"):
            self.assertEqual(profiles[name].importance, "supporting")
        characters = engine([text]).build().characters.characters
        self.assertEqual({c.name for c in characters}, {"周砚", "程陌", "父亲", "母亲"})

    def test_short_source_keeps_ordinary_single_action_but_long_source_does_not(self):
        self.assertEqual(engine(["周砚拿灯。"]).build().characters.characters[0].importance, "supporting")
        long = "雨落在空庭。\n" * 500 + "周砚拿灯。"
        result = engine([long]).build()
        self.assertEqual(result.characters.characters, [])
        self.assertEqual(result.characters.identity_candidates[0].name, "周砚")

    def test_reading_units_group_continuation_and_split_explicit_transition(self):
        text = "😀周砚拿起灯。\n周砚站在旧站。\n“等我。”周砚说。\n第二天，周砚没有开门。\n周砚拿起钥匙。"
        candidate = engine([text])
        report = candidate.build()
        reading = report.plot.reading_segments
        self.assertEqual(len(reading), 2)
        self.assertEqual(reading[1].grouping_basis, "transition")
        self.assertEqual(reading[0].paragraph_end, 3)
        self.assertEqual(report.plot.overview.detail_event_count, len(report.plot.events))
        assigned = [key for unit in reading for key in unit.event_ids]
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(set(assigned), {e.item_id for e in report.plot.events})
        validate_depth_report_source(report, source=report.source, chapters={"c1":text})
        for unit in reading:
            raw = text.encode("utf-16-le")[unit.start_offset*2:unit.end_offset*2].decode("utf-16-le")
            self.assertIn(unit.title, raw)
            self.assertIn(unit.summary, raw)

    def test_reading_projection_does_not_use_a_fixed_sentence_count(self):
        for count in (2, 7, 25):
            text = "周砚拿起灯。\n" * count
            report = engine([text]).build()
            self.assertEqual(len(report.plot.reading_segments), 1)
            self.assertEqual(report.plot.reading_segments[0].paragraph_end, count)

    def test_projection_rejects_missing_event_and_fabricated_summary(self):
        text = "😀周砚没有开门。"
        report = engine([text]).build()
        data = report.model_dump()
        data["plot"]["reading_segments"][0]["event_ids"] = []
        with self.assertRaises(ValidationError):
            DeconstructionDepthReport.model_validate(data)
        altered = report.model_copy(deep=True)
        altered.plot.reading_segments[0].summary = "凭空获胜。"
        with self.assertRaises(ValueError):
            validate_depth_report_source(altered, source=altered.source, chapters={"c1":text})

    def test_arc_summary_uses_chapter_number_not_uuid(self):
        candidate = engine(["周砚拿灯。", "周砚没有开门。"])
        candidate.chapters = tuple(ChapterInput(f"opaque-{c.chapter_number}", c.chapter_number, c.title, c.content) for c in candidate.chapters)
        # Construct the actual snapshot again so evidence uses the same opaque IDs.
        report = DepthAnalysisEngine(DepthSnapshot("p", "d", "v", 1, "a"*64, candidate.chapters)).build()
        self.assertIn("第1章到第2章", report.characters.characters[0].arc_summary)
        self.assertNotIn("opaque-", report.characters.characters[0].arc_summary)

    def test_model_prompt_has_coverage_and_semantic_evidence_checks(self):
        prompt = analysis_messages([])[0]["content"]
        for text in ("不设固定人数目标", "关键前因", "不同段落可能切换第一人称", "称名矛盾", "事前已经知情", "引文逐字存在不保证"):
            self.assertIn(text, prompt)
        self.assertNotIn("2–5 位", prompt)


class RuleRevisionMigrationTest(unittest.TestCase):
    setUp = RecognitionServiceTest.setUp
    preview = RecognitionServiceTest.preview
    def test_explicit_upgrade_preserves_old_result_and_is_idempotent(self):
        deconstruction = DeconstructionService(independent=self.service,
                                               store=DeconstructionStore(Path(self.tmp.name) / "deconstruction"))
        self.service.deconstruction_service = deconstruction
        preview = self.preview("第一章\n😀周砚没有开门。")
        self.service.confirm_import("project35", "account35", preview.preview_id)
        deconstruction.process_background_tasks()
        source = deconstruction._source("project35", "account35")
        record = deconstruction.store.load("project35")
        current = record.documents[0]
        legacy = current.model_copy(deep=True, update={"document_id":"legacy35", "report":None,
                                                      "evidence":[], "engine_revision":None})
        deconstruction._build_document(source, legacy)
        legacy.engine_revision = None
        legacy.report.engine_revision = None
        legacy.report.plot.reading_segments = []
        legacy.report.plot.overview = None
        record.documents = [legacy]
        record.active_document_id = legacy.document_id
        deconstruction.store.save(record)
        frozen = legacy.model_dump(mode="json")
        author_path = Path(self.tmp.name) / "independent/project35.json"
        author_bytes = author_path.read_bytes()
        before = DeconstructionResponse.model_validate(deconstruction.read("project35", "account35"))
        self.assertTrue(before.update_available)
        self.assertTrue(before.actions.rebuild)
        self.assertEqual(before.effective_status, "rebuild_required")
        self.assertEqual(before.error.code, "engine_update_available")
        self.assertEqual(before.required_engine_revision, RULE_ENGINE_REVISION)
        self.assertIsNotNone(before.result)
        self.assertTrue(before.result.read_only)
        self.assertEqual(before.result.document_id, legacy.document_id)
        self.assertIsNone(before.document)
        pending = DeconstructionResponse.model_validate(deconstruction._response(replace(source, pending_changes=True), record))
        self.assertIsNone(pending.result)
        stale = DeconstructionResponse.model_validate(deconstruction._response(replace(source, source_hash="b"*64), record))
        self.assertEqual(stale.effective_status, "stale")
        self.assertIsNone(stale.result)
        unknown_revision = before.model_copy(deep=True)
        unknown_revision.required_engine_revision = None
        unknown_revision.deconstruction.required_engine_revision = None
        with self.assertRaises(ValidationError):
            DeconstructionResponse.model_validate(unknown_revision.model_dump())
        self.assertEqual(before.source.hash, source.source_hash)
        self.assertEqual(deconstruction.store.load("project35").documents[0].model_dump(mode="json"), frozen)
        first = deconstruction.enqueue_for_project("project35", "account35", idempotency_key="refresh-one")
        duplicate = deconstruction.enqueue_for_project("project35", "account35", idempotency_key="refresh-two")
        self.assertNotEqual(first.document_id, legacy.document_id)
        self.assertEqual(first.document_id, duplicate.document_id)
        deconstruction.process_background_tasks()
        completed = DeconstructionResponse.model_validate(deconstruction.read("project35", "account35"))
        self.assertEqual(completed.effective_status, "completed")
        self.assertFalse(completed.update_available)
        self.assertEqual(completed.result.engine_revision, RULE_ENGINE_REVISION)
        self.assertEqual(deconstruction.enqueue_for_project("project35", "account35").document_id, first.document_id)
        stored = deconstruction.store.load("project35")
        self.assertEqual(len(stored.documents), 2)
        self.assertEqual(stored.documents[0].model_dump(mode="json"), frozen)
        old_ref = legacy.evidence[0]
        evidence = deconstruction.evidence("project35", "account35", old_ref.evidence_id, document_id=legacy.document_id)
        self.assertTrue(evidence["historical"])
        self.assertTrue(evidence["chapter"]["read_only"])
        self.assertFalse(evidence["source_matches_current"])
        self.assertEqual(evidence["evidence"]["excerpt"], old_ref.excerpt)
        self.assertEqual(author_path.read_bytes(), author_bytes)


class FinalAuditRepairTest(unittest.TestCase):
    def test_object_names_preserve_internal_verb_letters(self):
        for declaration in ("", "人物：段天问、陈自在、张问天。"):
            with self.subTest(declaration=declaration):
                report = engine([declaration + "她找到段天问。她告诉陈自在。她保护张问天。"]).build()
                self.assertEqual({p.name for p in report.characters.identity_candidates}, {"段天问", "陈自在", "张问天"})
                self.assertEqual({p.name for p in report.characters.characters}, {"段天问", "陈自在", "张问天"})

    def test_material_abstract_words_and_modal_phrases_are_not_people(self):
        for text in ("金钱决定命运。白纸没有字。文明保护着古迹。",
                     "他找到方法。她看见白纸。大家保护文化。",
                     "仍然没有退路。果然不会回来。总算拿起武器。宁可走进雨里。",
                     "银币没有流通。木板保护着石碑。制度决定流程。",
                     "宁愿走开。总是拿起武器。"):
            with self.subTest(text=text):
                result = engine([text, text]).build()
                self.assertEqual(result.characters.identity_candidates, [])
                self.assertEqual(result.characters.characters, [])

    def test_coordinated_people_share_the_predicate(self):
        for text, names in (("温栩和贺岑走进院子。温栩与贺岑拿起灯。", {"温栩", "贺岑"}),
                            ("欧阳问柳、陈自在及段天问走进院子。", {"欧阳问柳", "陈自在", "段天问"}),
                            ("周砚和陆川一起拿起灯。", {"周砚", "陆川"})):
            with self.subTest(text=text):
                report = engine([text]).build()
                self.assertEqual({p.name for p in report.characters.identity_candidates}, names)
                self.assertEqual({p.name for p in report.characters.characters}, names)

    def test_declaration_and_personal_use_override_soft_noun_evidence(self):
        for text, names in (("人物：阳光、沈默、石阶明。阳光拿起灯。沈默打开门。石阶明没有离开。", {"阳光", "沈默", "石阶明"}),
                            ("她名叫阳光。阳光拿起灯。", {"阳光"}),
                            ("人物：银币、文明。银币问起往事。文明决定救下孩子。", {"银币", "文明"})):
            with self.subTest(text=text):
                report = engine([text]).build()
                self.assertEqual({p.name for p in report.characters.characters}, names)
        for text in ("人物：我、大道、众人、夜色、石门。欧阳明没有开门。",
                     "人物：白纸、阳光。白纸没有字。阳光没有消失。"):
            report = engine([text]).build()
            self.assertFalse({"我", "大道", "众人", "夜色", "石门", "白纸", "阳光"} & {p.name for p in report.characters.identity_candidates})

    def test_object_speech_boundary_does_not_extend_the_name(self):
        for text, names in (("陆川对林舟说：“等我。”林舟答应了。", {"陆川", "林舟"}),
                            ("她找到林舟走。她告诉周砚拿灯。", {"林舟", "周砚"})):
            with self.subTest(text=text):
                self.assertEqual(set(engine([text]).names), names)

    def test_title_punctuation_does_not_hide_first_or_middle_chapter(self):
        for title in ("第一章 再见。", "第一章 选择；等待", "第一章风，起", "第一章 你来了！"):
            with self.subTest(title=title):
                chapters = IndependentWorkspaceService._parse_text("synthetic.txt", f"{title}\n甲。\n第二章 终点\n乙。")[1]
                self.assertEqual([c.title for c in chapters], [title, "第二章 终点"])
                self.assertEqual([c.content for c in chapters], ["甲。\n", "乙。"])
                middle = IndependentWorkspaceService._parse_text("synthetic.txt", f"第九章\n前文。\n{title}\n甲。\n第十章\n后文。")[1]
                self.assertEqual(len(middle), 3)
                self.assertEqual(middle[1].title, title)

    def test_special_heading_in_a_sentence_stays_body(self):
        body = "甲。\n尾声还没有响起\n乙。\n"
        chapters = IndependentWorkspaceService._parse_text("synthetic.txt", "第一章 正文\n" + body + "第二章 归来\n丙。")[1]
        self.assertEqual([c.content for c in chapters], [body, "丙。"])

    def test_same_chapter_events_must_belong_to_the_referenced_segment(self):
        good = engine(["😀周砚拿灯。\n\n第二天，陆川救下孩子。"]).build()
        data = good.model_dump()
        first, second = data["plot"]["reading_segments"]
        first["event_ids"], second["event_ids"] = second["event_ids"], first["event_ids"]
        with self.assertRaises(ValidationError):
            DeconstructionDepthReport.model_validate(data)

    def test_current_engine_projection_cannot_be_removed(self):
        data = engine(["周砚拿灯。"]).build().model_dump()
        data["plot"]["reading_segments"] = []
        data["plot"]["overview"]["reading_segment_count"] = 0
        with self.assertRaises(ValidationError):
            DeconstructionDepthReport.model_validate(data)
        # The revision marker is absent in actual legacy 2.0 documents.
        data["engine_revision"] = None
        data["plot"]["overview"] = None
        DeconstructionDepthReport.model_validate(data)

    def test_paragraph_indices_and_progress_match_source_offsets(self):
        text = "\n\t😀周砚拿灯。\n\n第二天，陆川救下孩子。\n "
        report = engine([text]).build()
        validate_depth_report_source(report, source=report.source, chapters={"c1":text})
        for mutation in (dict(paragraph_start=900, paragraph_end=999),
                         dict(normalized_start=20, normalized_end=25),
                         dict(paragraph_end=1, end_offset=len(text.encode("utf-16-le"))//2)):
            with self.subTest(mutation=mutation):
                data = report.model_dump()
                data["plot"]["reading_segments"][0].update(mutation)
                with self.assertRaises(ValueError):
                    altered = DeconstructionDepthReport.model_validate(data)
                    validate_depth_report_source(altered, source=altered.source, chapters={"c1":text})


class FinalHistoryRetentionTest(unittest.TestCase):
    setUp = RecognitionServiceTest.setUp
    preview = RecognitionServiceTest.preview

    def test_model_import_and_reimport_do_not_remove_rule_history(self):
        from unittest.mock import patch
        from app.core import deconstruction_service as service_module
        from app.core import deconstruction_depth as depth_module
        from schemas.analysis_report import AnalysisImport
        service = DeconstructionService(independent=self.service,
                                       store=DeconstructionStore(Path(self.tmp.name) / "deconstruction"))
        self.service.deconstruction_service = service
        preview = self.preview("第一章\n😀周砚没有开门。")
        self.service.confirm_import("project35", "account35", preview.preview_id)
        service.process_background_tasks()
        first = service.store.load("project35").documents[0]
        frozen = first.model_dump(mode="json")
        author_path = Path(self.tmp.name) / "independent/project35.json"
        author_bytes = author_path.read_bytes()
        for revision in range(22):
            with patch.object(service_module, "RULE_ENGINE_REVISION", f"audit-revision-{revision}"), patch.object(depth_module, "RULE_ENGINE_REVISION", f"audit-revision-{revision}"):
                queued = service.enqueue_for_project("project35", "account35")
                self.assertEqual(service.enqueue_for_project("project35", "account35").document_id, queued.document_id)
                service.process_background_tasks()
        prior = service.store.load("project35")
        self.assertEqual(len(prior.documents), 23)
        source = service._source("project35", "account35")
        claim = dict(text="合成的不开门记录。", status="fact", evidence_ids=["Q1"])
        payload = AnalysisImport(expected_source_version_id=source.version_id,
                                expected_source_revision=source.source_revision, expected_source_hash=source.source_hash,
                                report=dict(producer="offline-audit-fake", title="合成报告", scope="合成第一章", chapter_numbers=[1],
                                            findings=[dict(id="F1", title="不开门", **claim)],
                                            characters=[dict(id="C1", name="周砚", role="合成人物", identity=claim, motivation=claim, change=claim)],
                                            events=[dict(id="E1", title="不开门", chapter_number=1, story_time="当下", actor_ids=["C1"], action=claim, consequence=claim)],
                                            relations=[], story_order=["E1"], time_note="无回忆",
                                            evidence=[dict(id="Q1", chapter_number=1, quote="周砚没有开门。")], open_questions=[]))
        for _ in range(2):
            service.import_report("project35", "account35", payload)
            stored = service.store.load("project35")
            self.assertEqual(len(stored.documents), 24)
            self.assertTrue({d.document_id for d in prior.documents} <= {d.document_id for d in stored.documents})
            oldest = next(d for d in stored.documents if d.document_id == first.document_id)
            self.assertEqual(oldest.model_dump(mode="json"), frozen)
            evidence = service.evidence("project35", "account35", first.evidence[0].evidence_id, document_id=first.document_id)
            self.assertTrue(evidence["historical"])
            self.assertTrue(evidence["chapter"]["read_only"])
            self.assertEqual(author_path.read_bytes(), author_bytes)


if __name__ == "__main__":
    unittest.main()
