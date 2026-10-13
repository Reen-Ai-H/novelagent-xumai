"""Stage 35 recognition regressions using synthetic text, never a model."""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from app.core.deconstruction_depth import ChapterInput, DepthAnalysisEngine, DepthSnapshot
from app.core.independent_service import IndependentWorkspaceService
from app.core.independent_store import IndependentStore
from app.core.project_store import JsonProjectStore
from app.core.deconstruction_service import DeconstructionService
from app.core.deconstruction_store import DeconstructionStore
from app.core.person_recognition import discover_person_mentions
from app.agents.deconstruction_model import analysis_messages
from schemas.independent import StoryArchive
from schemas.deconstruction import DeconstructionResponse


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
        self.assertEqual(json.loads(messages[1]["content"].split("\n", 1)[1]), chapters)


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


if __name__ == "__main__":
    unittest.main()
