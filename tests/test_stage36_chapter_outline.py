"""Synthetic stage-36 navigation tests. No model or private manuscript fixtures."""
from __future__ import annotations

import base64
import io
import unittest
import zipfile

from app.core.chapter_outline import chapter_sections
from app.core.chapter_parser import parse_document, utf16_length
from app.core.independent_service import IndependentWorkspaceService
import test_independent_api as api_fixture


PARAGRAPH = "书院的长廊尽头有人等候，远行的人放下行囊，把一路所见仔细写进册子。他并不知道这一次重逢会改变什么，只是照旧整理桌上的信件。"


def bare_source(newline="\n"):
    return newline.join([PARAGRAPH, "  归航前  ", PARAGRAPH, PARAGRAPH,
                         "听雨轩", PARAGRAPH, PARAGRAPH, "秋社", PARAGRAPH])


def docx(paragraphs, styles=""):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                         + paragraphs + '</w:body></w:document>')
        if styles:
            archive.writestr("word/styles.xml", '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' + styles + '</w:styles>')
    return buffer.getvalue()


def p(text, properties=""):
    return f'<w:p><w:pPr>{properties}</w:pPr><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


class ChapterOutlineTest(unittest.TestCase):
    def test_empty_and_untitled_source(self):
        for text in ("", " \t\r\n"):
            self.assertEqual(chapter_sections("c1", text), [])
        text = "  😀正文没有小节标题。\r\n\r\n"
        sections = chapter_sections("c1", text)
        self.assertEqual(len(sections), 1)
        self.assertEqual((sections[0]["title"], sections[0]["kind"], sections[0]["start"], sections[0]["end"]),
                         ("本章开篇", "opening", 0, utf16_length(text)))

    def test_bare_headings_require_peer_context(self):
        text = bare_source()
        sections = chapter_sections("c1", text)
        self.assertEqual([s["title"] for s in sections], ["本章开篇", "归航前", "听雨轩", "秋社"])
        self.assertEqual([s["kind"] for s in sections], ["opening", "inferred", "inferred", "inferred"])
        for single in ("归航前", "听雨轩", "秋社"):
            self.assertEqual([s["kind"] for s in chapter_sections("c1", PARAGRAPH + "\n" + single + "\n" + PARAGRAPH)], ["opening"])

    def test_sentences_dialogue_and_scenery_are_not_titles(self):
        negatives = ["他转身离开", "天亮了", "我也想去", "终于回来了", "怎么办", "夜色渐深", "石门", "树林",
                     "真漂亮", "唉", "“听我说”", "太好了！", "（未完待续）", "* * *", "风声", "大家继续", "突然醒来"]
        text = "\n".join(PARAGRAPH + "\n" + value + "\n" + PARAGRAPH for value in negatives)
        self.assertEqual([s["kind"] for s in chapter_sections("c1", text)], ["opening"])

    def test_lists_verse_and_code_are_not_inferred(self):
        text = "青山\n绿水\n旧友\n归途\n\n> ## 引用中的标题\n```text\n## 代码\n```\n" + PARAGRAPH
        self.assertEqual([s["kind"] for s in chapter_sections("c1", text)], ["opening"])

    def test_multiline_dialogue_and_exclamations_are_not_titles(self):
        for start, end in (("“", "”"), ("「", "」"), ('"', '"')):
            text = start + bare_source() + end
            self.assertEqual([s["kind"] for s in chapter_sections("c1", text)], ["opening"])
        text = "\n".join(PARAGRAPH + "\n" + value + "\n" + PARAGRAPH for value in ("可恶", "糟糕", "救命", "天哪"))
        self.assertEqual([s["kind"] for s in chapter_sections("c1", text)], ["opening"])

    def test_explicit_single_heading_and_raw_whitespace(self):
        text = "\t开头正文。\n\n  ### 独立小节 ##  \n  后续正文。  \n"
        sections = chapter_sections("c1", text)
        self.assertEqual([s["title"] for s in sections], ["本章开篇", "独立小节"])
        self.assertEqual(sections[1]["kind"], "explicit")
        self.assertEqual(text[sections[1]["start"]:sections[1]["end"]], "  ### 独立小节 ##  \n  后续正文。  \n")

    def test_emoji_crlf_and_utf16_half_open_ranges(self):
        text = "😀开头\r\n## 中场😀\r\n后文🪶。\r\n## 结尾\r\n终。\r\n"
        sections = chapter_sections("c1", text)
        self.assertEqual([s["start"] for s in sections], [0, utf16_length("😀开头\r\n"), utf16_length(text[:text.index("## 结尾")])])
        raw = text.encode("utf-16-le")
        self.assertEqual("".join(raw[s["start"]*2:s["end"]*2].decode("utf-16-le") for s in sections), text)
        self.assertEqual(sections[-1]["end"], len(raw)//2)
        self.assertTrue(all(a["end"] == b["start"] for a, b in zip(sections, sections[1:])))

    def test_stable_ids_bind_chapter_position_and_text(self):
        text = "## 重逢\n甲。\n## 重逢\n甲。"
        first = chapter_sections("c1", text)
        self.assertEqual(first, chapter_sections("c1", text))
        self.assertNotEqual(first[0]["section_id"], first[1]["section_id"])
        self.assertNotEqual(first, chapter_sections("c2", text))
        self.assertNotEqual(first[0]["section_id"], chapter_sections("c1", text.replace("甲", "乙", 1))[0]["section_id"])
        self.assertNotEqual(first[0]["section_id"], chapter_sections("c1", "前文。\n" + text)[1]["section_id"])

    def test_plain_import_does_not_promote_inferred_headings_to_chapters(self):
        text = "第一章 源头\r\n" + bare_source("\r\n")
        parsed = parse_document("synthetic.txt", text)
        self.assertEqual(len(parsed.chapters), 1)
        self.assertEqual(parsed.chapters[0].content, text.split("\r\n", 1)[1])
        self.assertEqual(len(chapter_sections("c1", parsed.chapters[0].content)), 4)

    def test_txt_numbered_sections_stay_under_chapter(self):
        text = "第一章 起点\n开篇。\n第一节 暮归\n甲。\n第二节 新约\n乙。\n第二章 回望\n丙。"
        chapters = parse_document("synthetic.txt", text).chapters
        self.assertEqual([c.title for c in chapters], ["第一章 起点", "第二章 回望"])
        self.assertEqual([s["title"] for s in chapter_sections("c1", chapters[0].content)], ["本章开篇", "第一节 暮归", "第二节 新约"])
        self.assertEqual(parse_document("sections.txt", "第一节 暮归\n甲。\n第二节 新约\n乙。").chapters[1].title, "第二节 新约")

    def test_markdown_chapter_and_section_hierarchy(self):
        text = "# 卷名\n## 第一章 起点\n开篇。\n### 第一节 暮归\n甲。\n### 第二节 新约\n乙。\n## 第二章 回望\n丙。"
        parsed = parse_document("synthetic.md", text)
        self.assertEqual([c.title for c in parsed.chapters], ["第一章 起点", "第二章 回望"])
        self.assertEqual(parsed.fragments, ("# 卷名\n",))
        self.assertIn("### 第一节 暮归\n甲。\n", parsed.chapters[0].content)
        self.assertEqual(len(chapter_sections("c1", parsed.chapters[0].content)), 3)

    def test_markdown_code_does_not_create_a_chapter(self):
        body = "开篇。\n```text\n# 第九章 代码\n```\n后文。\n"
        parsed = parse_document("code.md", "## Chapter 1\n" + body + "## Chapter 2\n尾段。")
        self.assertEqual([c.title for c in parsed.chapters], ["Chapter 1", "Chapter 2"])
        self.assertEqual(parsed.chapters[0].content, body)

    def test_nested_markdown_numbered_chapter_is_still_a_section(self):
        body = "开篇。\n### Chapter 8: Quoted draft\n内文。\n"
        parsed = parse_document("nested.md", "## Chapter 1\n" + body + "## Chapter 2\n尾段。")
        self.assertEqual(len(parsed.chapters), 2)
        self.assertEqual(parsed.chapters[0].content, body)


class OutlineApiTest(unittest.TestCase):
    setUp = api_fixture.IndependentApiTest.setUp
    _cleanup = api_fixture.IndependentApiTest._cleanup
    _project = api_fixture.IndependentApiTest._project
    _encoded = staticmethod(api_fixture.IndependentApiTest._encoded)

    def preview(self, project, text, filename="synthetic.txt"):
        response = self.client.post(f"/api/independent/projects/{project}/imports/preview", json={
            "filename": filename, "content_base64": base64.b64encode(text if isinstance(text, bytes) else text.encode()).decode()})
        self.assertEqual(response.status_code, 200)
        return response.json()["preview"]

    def confirm(self, project, preview):
        response = self.client.post(f"/api/independent/projects/{project}/imports/{preview['preview_id']}/confirm")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_uninitialized_and_blank_workspace(self):
        project = self._project()
        self.assertEqual(self.client.get(f"/api/independent/projects/{project}").json()["chapter_sections"], {})
        workspace = self.client.post(f"/api/independent/projects/{project}/start", json={"source":"blank"}).json()
        chapter = workspace["active_version"]["chapters"][0]
        self.assertEqual(workspace["chapter_sections"], {chapter["chapter_id"]: []})

    def test_read_projection_does_not_persist_or_change_manuscript(self):
        project = self._project()
        preview = self.preview(project, "第一章\n" + bare_source())
        self.assertEqual(len(preview["chapter_sections"]["1"]), 4)
        workspace = self.confirm(project, preview)
        path = self.independent.store.base_dir / f"{project}.json"
        original = path.read_bytes()
        for _ in range(3):
            reread = self.client.get(f"/api/independent/projects/{project}").json()
            self.assertEqual(reread["chapter_sections"], workspace["chapter_sections"])
            self.assertEqual(reread["active_version"], workspace["active_version"])
        self.assertEqual(path.read_bytes(), original)
        self.assertNotIn('"chapter_sections"', original.decode())
        self.assertNotIn('"section_id"', original.decode())
        self.assertEqual(len(workspace["active_version"]["chapters"]), 1)

    def test_save_returns_fresh_projection_preserves_formal_source_and_conflicts(self):
        project = self._project()
        workspace = self.confirm(project, self.preview(project, "第一章\n" + bare_source()))
        chapter = workspace["active_version"]["chapters"][0]
        content = "😀草稿\r\n## 新标题\r\n  保存后的正文。  \r\n"
        response = self.client.put(f"/api/independent/projects/{project}/chapters/{chapter['chapter_id']}/draft", json={
            "content": content, "expected_revision": chapter["server_revision"]})
        self.assertEqual(response.status_code, 200)
        saved = response.json()
        current = saved["workspace"]["active_version"]["chapters"][0]
        self.assertEqual(current["chapter_id"], chapter["chapter_id"])
        self.assertEqual(current["formal_content"], chapter["formal_content"])
        self.assertEqual(current["content"], content)
        self.assertEqual(current["server_revision"], chapter["server_revision"] + 1)
        self.assertEqual(saved["workspace"]["chapter_sections"][chapter["chapter_id"]], chapter_sections(chapter["chapter_id"], content))
        self.assertEqual(saved["workspace"]["active_version_id"], workspace["active_version_id"])
        conflict = self.client.put(f"/api/independent/projects/{project}/chapters/{chapter['chapter_id']}/draft", json={
            "content": "不应写入", "expected_revision": chapter["server_revision"]})
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(self.client.get(f"/api/independent/projects/{project}").json()["chapter_sections"], saved["workspace"]["chapter_sections"])

    def test_account_and_chapter_isolation(self):
        project = self._project()
        workspace = self.confirm(project, self.preview(project, "第一章\n## 同题\n甲。\n第二章\n## 同题\n乙。"))
        first, second = workspace["active_version"]["chapters"]
        sections = workspace["chapter_sections"]
        self.assertEqual(set(sections), {first["chapter_id"], second["chapter_id"]})
        self.assertNotEqual(sections[first["chapter_id"]][0]["section_id"], sections[second["chapter_id"]][0]["section_id"])
        original = (self.independent.store.base_dir / f"{project}.json").read_bytes()
        self.client.post("/api/auth/email", json={"email": "other-outline@example.com"})
        self.assertEqual(self.client.get(f"/api/independent/projects/{project}").status_code, 404)
        self.assertEqual((self.independent.store.base_dir / f"{project}.json").read_bytes(), original)

    def test_docx_heading_styles_survive_preview_confirm_and_read(self):
        project = self._project()
        source = docx(p("  远航  ", '<w:pStyle w:val="Heading1"/>') + p("😀开篇。")
                      + p("  特殊小节  ", '<w:pStyle w:val="Child"/>') + p("  后文。  ")
                      + p("归家", '<w:outlineLvl w:val="0"/>') + p("末尾。"),
                      '<w:style w:styleId="Child"><w:basedOn w:val="Heading2"/></w:style>')
        preview = self.preview(project, source, "synthetic.docx")
        self.assertEqual([c["title"] for c in preview["chapters"]], ["  远航  ", "归家"])
        self.assertEqual(preview["chapters"][0]["content"], "😀开篇。\n  特殊小节  \n  后文。  \n")
        self.assertEqual([s["title"] for s in preview["chapter_sections"]["1"]], ["本章开篇", "特殊小节"])
        workspace = self.confirm(project, preview)
        chapter = workspace["active_version"]["chapters"][0]
        self.assertEqual([s["kind"] for s in workspace["chapter_sections"][chapter["chapter_id"]]], ["opening", "explicit"])
        self.assertEqual(chapter["content"], preview["chapters"][0]["content"])
        # Imported formatting may be reused only with the exact imported text.
        edited = self.client.put(f"/api/independent/projects/{project}/chapters/{chapter['chapter_id']}/draft", json={
            "content": "插入。\n" + chapter["content"], "expected_revision": chapter["server_revision"]}).json()
        self.assertEqual([s["kind"] for s in edited["workspace"]["chapter_sections"][chapter["chapter_id"]]], ["opening"])

    def test_docx_direct_body_style_overrides_inherited_heading(self):
        source = docx(p("起点", '<w:pStyle w:val="Heading1"/>')
                      + p("像标题的正文", '<w:pStyle w:val="Heading1"/><w:outlineLvl w:val="9"/>') + p("实际正文。"))
        preview = self.preview(self._project(), source, "synthetic.docx")
        self.assertEqual(len(preview["chapters"]), 1)
        self.assertEqual(preview["chapters"][0]["content"], "像标题的正文\n实际正文。")

    def test_docx_custom_style_outline_and_cycle_are_safe(self):
        source = docx(p("起点", '<w:pStyle w:val="CustomRoot"/>') + p("正文。")
                      + p("孤立词", '<w:pStyle w:val="LoopA"/>') + p("继续。"),
                      '<w:style w:styleId="CustomRoot"><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>'
                      '<w:style w:styleId="LoopA"><w:basedOn w:val="LoopB"/></w:style>'
                      '<w:style w:styleId="LoopB"><w:basedOn w:val="LoopA"/></w:style>')
        preview = self.preview(self._project(), source, "synthetic.docx")
        self.assertEqual(preview["status"], "pending")
        self.assertEqual(len(preview["chapters"]), 1)
        self.assertEqual([s["kind"] for s in preview["chapter_sections"]["1"]], ["opening"])

    def test_docx_textbox_not_duplicated_and_no_style_markers_in_body(self):
        source = docx(p("第一章 起点") + '<w:p><w:r><w:t>外文。</w:t><w:pict><w:txbxContent>'
                      + p("内文。") + '</w:txbxContent></w:pict></w:r></w:p>' + p("  末行。  "))
        preview = self.preview(self._project(), source, "synthetic.docx")
        body = preview["chapters"][0]["content"]
        self.assertEqual(body.count("内文。"), 1)
        self.assertEqual(body.count("外文。"), 1)
        self.assertTrue(body.endswith("  末行。  "))
        self.assertNotIn("#", body)


if __name__ == "__main__":
    unittest.main()
