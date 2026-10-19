"""Normal upload -> confirm regressions; synthetic sources only."""
from __future__ import annotations

import base64
import unittest

import test_independent_api as fixtures
from test_stage37_chapters import docx
from app.core.chapter_parser import parse_document, utf16_length
from app.core.independent_service import IndependentWorkspaceService


BODY = ("旅人把渡口收到的旧信逐一整理，记下不同船只到港的日期，"
        "等天明后带着册子去找守桥的人核对，又把未能确认的消息留给后来的人。") * 4
TITLES = ["第一章—离岸", "古驿来客", "旧城札记", "雨巷相逢", "归雁传书", "远山回音"]


def manuscript(titles=TITLES, newline="\r\n"):
    return newline.join(f"{title}{newline}{BODY}😀{newline}" for title in titles)


class NormalChapterImportTest(unittest.TestCase):
    setUp = fixtures.IndependentApiTest.setUp
    _cleanup = fixtures.IndependentApiTest._cleanup
    _project = fixtures.IndependentApiTest._project

    def upload(self, project, content, filename="合成稿.txt"):
        if isinstance(content, str):
            content = content.encode("utf-8")
        result = self.client.post(f"/api/independent/projects/{project}/imports/preview", json={
            "filename": filename, "content_base64": base64.b64encode(content).decode("ascii")})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["preview"]["status"], "pending")
        return result.json()["preview"]

    def confirm(self, project, preview):
        result = self.client.post(f"/api/independent/projects/{project}/imports/{preview['preview_id']}/confirm")
        self.assertEqual(result.status_code, 200)
        return result.json()

    def assert_chapters(self, chapters, text, titles):
        self.assertEqual([c["chapter_number"] for c in chapters], list(range(1, len(titles)+1)))
        self.assertEqual([c["title"] for c in chapters], titles)
        self.assertEqual("".join(c["content"] for c in chapters), text)
        self.assertEqual(sum(utf16_length(c["content"]) for c in chapters), utf16_length(text))

    def test_normal_txt_md_upload_confirm_and_read_six_lossless_chapters(self):
        for suffix, prefix in (("txt", ""), ("md", ""), ("md", "# 合成作品\n## ")):
            with self.subTest(suffix=suffix, declared=bool(prefix)):
                project = self._project()
                text = prefix + manuscript()
                self.assertEqual(len(parse_document(f"稿.{suffix}", text).chapters), 1)
                preview = self.upload(project, text, f"合成稿.{suffix}")
                self.assertEqual(preview["chapter_count"], 6)
                self.assert_chapters(preview["chapters"], text, TITLES)
                self.assertEqual(preview["unrecognized_fragments"], [])
                self.assertFalse(self.client.get(f"/api/independent/projects/{project}").json()["initialized"])
                workspace = self.confirm(project, preview)
                self.assert_chapters(workspace["active_version"]["chapters"], text, TITLES)
                self.assertTrue(all(c["formal_content"] == c["content"] for c in workspace["active_version"]["chapters"]))
                path = self.independent.store.base_dir / f"{project}.json"
                original = path.read_bytes()
                self.assertEqual(self.client.get(f"/api/independent/projects/{project}").json()["active_version"],
                                 workspace["active_version"])
                self.assertEqual(path.read_bytes(), original)

    def test_normal_docx_mixed_titles_preserve_declared_style_and_text(self):
        for styled in (False, True):
            with self.subTest(styled=styled):
                paragraphs = [("作品封面", 1)] if styled else []
                for i, title in enumerate(TITLES):
                    paragraphs.extend([(title, 2 if styled and i == 0 else None), (BODY+"😀", None)])
                content = docx(paragraphs)
                text, levels = IndependentWorkspaceService._decode_docx_structure(content)
                project = self._project()
                preview = self.upload(project, content, "合成稿.docx")
                self.assert_chapters(preview["chapters"], text, TITLES)
                chapters = self.confirm(project, preview)["active_version"]["chapters"]
                self.assert_chapters(chapters, text, TITLES)
                if styled:
                    self.assertEqual(chapters[0]["imported_heading_style"]["heading_levels"],
                                     {str(utf16_length(text[:p])): level for p, level in levels.items()})

    def test_missing_first_heading_uses_filename_without_recreating_source(self):
        text = BODY + "\n" + manuscript(TITLES[1:], "\n")
        project = self._project()
        preview = self.upload(project, text, "首章原题.txt")
        self.assert_chapters(preview["chapters"], text, ["首章原题", *TITLES[1:]])
        self.assertFalse(preview["chapters"][0]["content"].startswith("首章原题"))
        self.assert_chapters(self.confirm(project, preview)["active_version"]["chapters"],
                             text, ["首章原题", *TITLES[1:]])
        # An exported input may carry a missing title from stored metadata.
        # This is newly constructed input, not the original uploaded file.
        metadata_title = "第一章—原题"
        exported = metadata_title + "\n" + text
        project = self._project()
        preview = self.upload(project, exported, "导出稿.txt")
        self.assert_chapters(preview["chapters"], exported, [metadata_title, *TITLES[1:]])
        self.assert_chapters(self.confirm(project, preview)["active_version"]["chapters"],
                             exported, [metadata_title, *TITLES[1:]])

    def test_different_titles_and_encoding_are_not_a_sample_dictionary(self):
        titles = ["Chapter 7 Departure", "荒原手记", "新渡口", "异乡岁月", "春山行", "风中旧约"]
        text = manuscript(titles, "\n").replace("😀", "")
        for encoding in ("utf-16", "gb18030"):
            with self.subTest(encoding=encoding):
                project = self._project()
                preview = self.upload(project, text.encode(encoding))
                self.assert_chapters(preview["chapters"], text, titles)
                self.assert_chapters(self.confirm(project, preview)["active_version"]["chapters"], text, titles)

    def test_single_missing_number_uses_existing_supported_gap_inference(self):
        titles = ["第一章—启程", "离岸", "第三章—归来"]
        text = manuscript(titles)
        project = self._project()
        preview = self.upload(project, text)
        self.assert_chapters(preview["chapters"], text, titles)
        self.assert_chapters(self.confirm(project, preview)["active_version"]["chapters"], text, titles)

    def test_dialogue_action_short_paragraph_and_toc_do_not_add_chapters(self):
        cases = [
            BODY + "\n你是谁\n" + BODY + "\n我们走吧\n" + BODY,
            BODY + "\n转头望向窗外\n" + BODY + "\n慢慢走出房门\n" + BODY,
            BODY + "\n古驿来客\n仅有短段。\n旧城札记\n另一短段。",
            "古驿来客\n旧城札记\n归雁传书\n" + BODY,
            BODY + '\n“\n古驿来客\n' + BODY + '\n旧城札记\n' + BODY + '\n”',
            BODY + '\n```md\n古驿来客\n' + BODY + '\n旧城札记\n' + BODY + '\n```',
            "目录\n第一章 开篇 ... 1\n第二章 归来 ... 2\n正文\n第一章 开篇\n" + BODY,
        ]
        for text in cases:
            with self.subTest(case=cases.index(text)):
                preview = self.upload(self._project(), text)
                self.assertEqual(preview["chapter_count"], 1)

    def test_declared_nested_sections_keep_existing_hierarchy(self):
        text = "# 第一章 开篇\n" + BODY + "\n## 第一节 回忆\n甲。\n## 第二节 旧事\n乙。"
        preview = self.upload(self._project(), text, "层级.md")
        self.assertEqual(preview["chapter_count"], 1)
        self.assertEqual(preview["chapters"][0]["content"], parse_document("层级.md", text).chapters[0].content)

    def test_explicit_only_legacy_body_fragments_and_numbers_stay_compatible(self):
        text = "导入说明\n# 第七章 启程\n甲。\n# 第九章 归来\n乙。"
        preview = self.upload(self._project(), text, "旧格式.md")
        parsed = parse_document("旧格式.md", text)
        self.assertEqual([(c["chapter_number"], c["content"]) for c in preview["chapters"]],
                         [(c.chapter_number, c.content) for c in parsed.chapters])
        self.assertEqual(preview["unrecognized_fragments"], list(parsed.fragments))

    def test_existing_draft_and_formal_manuscript_cannot_be_overwritten(self):
        project = self._project()
        preview = self.upload(project, manuscript())
        self.client.post(f"/api/independent/projects/{project}/start", json={"source": "blank"})
        path = self.independent.store.base_dir / f"{project}.json"
        before = path.read_bytes()
        result = self.client.post(f"/api/independent/projects/{project}/imports/{preview['preview_id']}/confirm")
        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.json()["detail"]["code"], "import_already_confirmed")
        self.assertEqual(path.read_bytes(), before)

    def test_cross_account_upload_and_confirm_cannot_read_or_mutate_source(self):
        project = self._project()
        preview = self.upload(project, manuscript())
        path = self.independent.store.base_dir / f"{project}.json"
        before = path.read_bytes()
        self.client.post("/api/auth/email", json={"email": "other-stage38@example.com"})
        for suffix, payload in [("imports/preview", {"filename": "a.txt", "content_base64": "55Sy"}),
                                (f"imports/{preview['preview_id']}/confirm", None)]:
            result = self.client.post(f"/api/independent/projects/{project}/{suffix}", json=payload)
            self.assertEqual(result.status_code, 404)
        self.assertEqual(path.read_bytes(), before)

    def test_normal_upload_resegment_keeps_old_source_and_draft_conflict_guards(self):
        project = self._project()
        base = f"/api/independent/projects/{project}"
        text = manuscript()
        workspace = self.confirm(project, self.upload(project, text))
        old_version = workspace["active_version"]["version_id"]
        # Use the authenticated service for the exact historical source; its
        # source contract is independent of the import parser's output form.
        record = self.independent.store.load(project)
        old_source = self.independent.read_source_snapshot(project, record.account_id, old_version)
        source = workspace["chapter_source"]
        preview_response = self.client.post(base + "/chapter-previews/resegment", json={
            "expected_version_id": source["version_id"], "expected_source_hash": source["source_hash"]})
        self.assertEqual(preview_response.status_code, 200)
        partition = preview_response.json()["preview"]
        chapter = workspace["active_version"]["chapters"][0]
        saved = self.client.put(base + f"/chapters/{chapter['chapter_id']}/draft", json={
            "content": chapter["content"] + "未保存到正式稿的改动。", "expected_revision": chapter["server_revision"]})
        self.assertEqual(saved.status_code, 200)
        rejected = self.client.post(base + f"/chapter-previews/{partition['preview_id']}/confirm", json={
            "expected_revision": partition["revision"]})
        self.assertEqual(rejected.status_code, 409)
        current = saved.json()["workspace"]["active_version"]["chapters"][0]
        reset = self.client.put(base + f"/chapters/{chapter['chapter_id']}/draft", json={
            "content": chapter["content"], "expected_revision": current["server_revision"]})
        self.assertEqual(reset.status_code, 200)
        source = reset.json()["workspace"]["chapter_source"]
        old_source = self.independent.read_source_snapshot(project, record.account_id, old_version)
        partition = self.client.post(base + "/chapter-previews/resegment", json={
            "expected_version_id": source["version_id"], "expected_source_hash": source["source_hash"]}).json()["preview"]
        confirmed = self.client.post(base + f"/chapter-previews/{partition['preview_id']}/confirm", json={
            "expected_revision": partition["revision"]})
        self.assertEqual(confirmed.status_code, 200)
        self.assert_chapters(confirmed.json()["workspace"]["active_version"]["chapters"], text, TITLES)
        historical = self.independent.read_source_snapshot(project, record.account_id, old_version)
        self.assertTrue(historical["historical"])
        self.assertEqual(historical["source_hash"], old_source["source_hash"])
        self.assertEqual(historical["chapters"], old_source["chapters"])


if __name__ == "__main__":
    unittest.main()
