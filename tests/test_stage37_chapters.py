from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import timedelta
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest
import zipfile

import test_independent_api as fixtures
from app.core.chapter_parser import parse_document, utf16_length
from app.core.chapter_segmentation import partition_text, suggest_boundaries
from app.core.deconstruction_service import DeconstructionService
from app.core.deconstruction_store import DeconstructionStore
from app.core.independent_service import IndependentServiceError, IndependentWorkspaceService
from schemas.independent import AnalysisTask, PendingChangeBatch


NARRATIVE = "客栈门外的行人绕过长街来到渡口，船上的灯火一直亮到天明，留下的人收好旧信，等候远处归来的船队。" * 3


def docx(paragraphs):
    from xml.sax.saxutils import escape
    xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
    for text, level in paragraphs:
        style = f'<w:pPr><w:pStyle w:val="Heading{level}"/></w:pPr>' if level else ""
        xml += f'<w:p>{style}<w:r><w:t>{escape(text)}</w:t></w:r></w:p>'
    xml += '</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buf.getvalue()


class ChapterPartitionParserTest(unittest.TestCase):
    def assert_partition(self, text, expected, levels=None):
        boundaries = suggest_boundaries(text, "现有章题", heading_levels=levels)
        items, chunks = partition_text(text, boundaries)
        self.assertEqual([c["title"] for c in items], expected)
        self.assertEqual("".join(chunks), text)
        self.assertEqual([c["chapter_number"] for c in items], list(range(1, len(items)+1)))
        self.assertEqual(sum(c["char_count"] for c in items), utf16_length(text))
        return items

    def test_repeated_bare_titles_preserve_opening(self):
        text = NARRATIVE + "\r\n\r\n渡口旧事\r\n" + NARRATIVE + "\r\n\r\n雨巷重逢\r\n" + NARRATIVE
        self.assert_partition(text, ["现有章题", "渡口旧事", "雨巷重逢"])

    def test_bare_first_title_and_numbered_labels(self):
        self.assert_partition("渡口旧事\n" + NARRATIVE + "\n雨巷重逢\n" + NARRATIVE, ["渡口旧事", "雨巷重逢"])
        self.assert_partition("1、渡口旧事\n" + NARRATIVE + "\n二、雨巷重逢\n" + NARRATIVE,
                              ["1、渡口旧事", "二、雨巷重逢"])

    def test_markdown_root_descendant_and_book_wrapper(self):
        for level in (1, 2, 3):
            h = "#" * level
            self.assert_partition(f"{h} 远行\r\n甲。\r\n{h}# 第九章 引用草稿\r\n乙。\r\n{h} 归来\r\n丙。\r\n",
                                  ["远行", "归来"])
        self.assert_partition("# 书名\n## 第一章 远行\n甲。\n## 第二章 归来\n乙。\n",
                              ["第一章 远行", "第二章 归来"])

    def test_docx_roots_and_book_wrapper(self):
        for level in (1, 2, 3):
            paragraphs = [("远行", level), ("甲。", None), ("第九章 引用草稿", level+1),
                          ("乙。", None), ("归来", level), ("丙。", None)]
            text, levels = IndependentWorkspaceService._decode_docx_structure(docx(paragraphs))
            self.assert_partition(text, ["远行", "归来"], levels)
        text, levels = IndependentWorkspaceService._decode_docx_structure(docx([
            ("书名", 1), ("第一章 远行", 2), ("甲。", None), ("第二章 归来", 2), ("乙。", None)]))
        self.assert_partition(text, ["第一章 远行", "第二章 归来"], levels)

    def test_unnumbered_children_under_book_container(self):
        self.assert_partition("# 书名\n\n## 远行\n甲。\n## 归来\n乙。", ["远行", "归来"])
        text, levels = IndependentWorkspaceService._decode_docx_structure(docx([
            ("书名", 1), ("远行", 2), ("甲。", None), ("归来", 2), ("乙。", None)]))
        self.assert_partition(text, ["远行", "归来"], levels)
        self.assert_partition("# 开篇\n甲。\n## 密约\n乙。\n## 远行\n丙。", ["开篇"])

    def test_mixed_plain_titles_and_numbered_chapter(self):
        text = "渡口旧事\n" + NARRATIVE + "\n第二章 归来\n" + NARRATIVE + "\n雨巷重逢\n" + NARRATIVE
        self.assert_partition(text, ["渡口旧事", "第二章 归来", "雨巷重逢"])

    def test_same_level_numbered_and_unnumbered(self):
        for level in (1, 2, 3):
            h = "#" * level
            self.assert_partition(f"{h} 第一章 远行\n甲。\n{h} 归来\n乙。", ["第一章 远行", "归来"])

    def test_standard_sequence_restarts_and_specials(self):
        self.assert_partition("序章\n甲。\n第一卷\n第九章 远行\n乙。\n第二卷\n第一章 归来\n丙。\n尾声\n丁。",
                              ["序章", "第九章 远行", "第一章 归来", "尾声"])

    def test_code_and_multiline_dialogue_stay_in_body(self):
        for opener, closer in [('```md', '```'), ('~~~~', '~~~~'), ('“', '”'), ('「', '」'), ('"', '"')]:
            text = "# 第一章 开篇\n" + NARRATIVE + "\n" + opener + "\n第九章 引用\n" + NARRATIVE
            text += "\n渡口旧事\n" + NARRATIVE + "\n雨巷重逢\n" + NARRATIVE + "\n" + closer
            text += "\n# 第二章 终点\n" + NARRATIVE
            self.assert_partition(text, ["第一章 开篇", "第二章 终点"])

    def test_dialogue_actions_scenery_lists_are_not_chapters(self):
        for first, second in [("你是谁", "我们走吧"), ("转头望向窗外", "慢慢走出房门"),
                              ("夜色", "山风渐起"), ("他没有回答", "她点头了")]:
            text = NARRATIVE + "\n" + first + "\n" + NARRATIVE + "\n" + second + "\n" + NARRATIVE
            self.assert_partition(text, ["现有章题"])
        self.assert_partition("渡口旧事\n雨巷重逢\n归雁传书\n" + NARRATIVE, ["现有章题"])

    def test_single_uncertain_title_is_manual_only(self):
        self.assert_partition(NARRATIVE + "\n渡口旧事\n" + NARRATIVE, ["现有章题"])

    def test_toc_and_volume_not_official_chapters(self):
        text = "# 书名\n目录\n第一章 远行 ... 1\n第二章 归来 ... 2\n正文\n第一卷 春\n第一章 远行\n甲。\n第二章 归来\n乙。"
        self.assert_partition(text, ["第一章 远行", "第二章 归来"])

    def test_exact_utf16_and_whitespace(self):
        text = "  \r\n# 第一章 😀\r\n　甲。\t\r\n\r\n# 第二章 归来\r\n乙。  \r\n"
        items = self.assert_partition(text, ["第一章 😀", "第二章 归来"])
        self.assertEqual(items[1]["start"], utf16_length(text[:text.index("# 第二章")]))

    def test_invalid_utf16_crlf_and_blank_partitions(self):
        for text, cuts in [("😀甲乙", [0, 1]), ("甲\r\n乙", [0, 2]), ("甲乙", [1]),
                           ("甲乙", [0, 0]), ("甲乙", [0, 3]), ("甲乙", [0, True]),
                           ("甲\n  ", [0, 2]), ("甲乙", [0, 1.0])]:
            with self.subTest(text=text, cuts=cuts), self.assertRaises(ValueError):
                partition_text(text, [dict(start=s, title="标题") for s in cuts])

    def test_legacy_parser_contract_and_source_positions(self):
        text = "# 第一章 开篇\r\n　甲。\r\n# 第二章 终点\r\n乙。\r\n"
        parsed = parse_document("稿.md", text)
        self.assertEqual(parsed.chapters[0].content, "　甲。\r\n")
        for c in parsed.chapters:
            self.assertEqual(c.content, text[c.source_start:c.source_end])
            self.assertEqual(text[c.heading_start], "#")


class ChapterPartitionApiTest(unittest.TestCase):
    setUp = fixtures.IndependentApiTest.setUp
    _cleanup = fixtures.IndependentApiTest._cleanup
    _project = fixtures.IndependentApiTest._project
    _encoded = staticmethod(fixtures.IndependentApiTest._encoded)

    def init_project(self):
        self.pid = self._project()
        self.base = f"/api/independent/projects/{self.pid}"
        self.account = self.client.get(self.base).json()

    def preview(self, text, filename="稿.md"):
        result = self.client.post(self.base + "/chapter-previews/import",
                                  json=dict(filename=filename, content_base64=self._encoded(text)))
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()["preview"]

    def confirm(self, p, status=200):
        result = self.client.post(self.base + f"/chapter-previews/{p['preview_id']}/confirm",
                                  json=dict(expected_revision=p["revision"]))
        self.assertEqual(result.status_code, status, result.text)
        return result.json()

    def resegment(self):
        state = self.client.get(self.base).json()["chapter_source"]
        result = self.client.post(self.base + "/chapter-previews/resegment",
                                  json=dict(expected_version_id=state["version_id"], expected_source_hash=state["source_hash"]))
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()["preview"]

    def seed(self, text="甲。\r\n乙。", title="第一章 — 原题"):
        self.init_project()
        p = self.preview(text, "稿.txt")
        result = self.client.put(self.base + f"/chapter-previews/{p['preview_id']}",
                                 json=dict(expected_revision=1, boundaries=[dict(start=0, title=title)]))
        self.assertEqual(result.status_code, 200, result.text)
        return self.confirm(result.json()["preview"])["workspace"]

    def test_import_correct_confirm_exact_source_and_no_models(self):
        self.init_project()
        source = "  \r\n# 第一章 远行\r\n甲😀。\t\r\n\r\n# 第二章 归来\r\n乙。  \r\n"
        p = self.preview(source)
        self.assertEqual(p["source_text"], source)
        self.assertEqual(p["source_hash"], hashlib.sha256(source.encode()).hexdigest())
        self.assertNotIn("source_text_hash", p)
        self.assertNotIn("heading_levels", p)
        service = Mock()
        self.independent.deconstruction_service = service
        result = self.confirm(p)
        chapters = result["workspace"]["active_version"]["chapters"]
        self.assertEqual("".join(c["content"] for c in chapters), source)
        self.assertEqual("".join(c["formal_content"] for c in chapters), source)
        self.assertEqual([c["chapter_number"] for c in chapters], [1, 2])
        self.assertEqual([c["title"] for c in chapters], ["第一章 远行", "第二章 归来"])
        self.assertEqual(service.mock_calls, [])
        self.assertIsNone(result["previous_version_id"])
        self.assertEqual(self.confirm(p, 409)["detail"]["code"], "chapter_preview_confirmed")

    def test_import_txt_md_docx_utf16_and_gb18030(self):
        source = "第一章 远行\r\n甲。\r\n第二章 归来\r\n乙。\r\n"
        cases = [("稿.txt", source.encode("utf-16"), source), ("稿.md", source.encode("utf-8-sig"), source),
                 ("稿.txt", source.encode("gb18030"), source)]
        paragraphs = [("远行", 2), ("甲。", None), ("第九章 引用", 3), ("乙。", None), ("归来", 2), ("丙。", None)]
        cases.append(("稿.docx", docx(paragraphs), "\n".join(t for t, _ in paragraphs)))
        for filename, data, expected in cases:
            self.init_project()
            response = self.client.post(self.base + "/chapter-previews/import", json=dict(
                filename=filename, content_base64=base64.b64encode(data).decode()))
            self.assertEqual(response.status_code, 200, response.text)
            p = response.json()["preview"]
            self.assertEqual(len(p["chapters"]), 2)
            result = self.confirm(p)
            self.assertEqual("".join(c["content"] for c in result["workspace"]["active_version"]["chapters"]), expected)
            if filename.endswith("docx"):
                self.assertIsNotNone(result["workspace"]["active_version"]["chapters"][0]["imported_heading_style"])

    def test_invalid_import_and_toc_only(self):
        self.init_project()
        for filename, data in [("坏.pdf", b"body"), ("坏.docx", b"invalid"), ("坏.txt", b"\xff"),
                               ("空.txt", b" \r\n"), ("目录.md", "目录\n第一章\n第二章\n".encode())]:
            response = self.client.post(self.base + "/chapter-previews/import", json=dict(
                filename=filename, content_base64=base64.b64encode(data).decode()))
            self.assertEqual(response.status_code, 422, response.text)
        self.assertFalse(self.client.get(self.base).json()["initialized"])

    def test_manual_correction_merge_and_revision_cas(self):
        self.init_project()
        p = self.preview("甲😀。\r\n乙。")
        path = self.base + f"/chapter-previews/{p['preview_id']}"
        update = dict(expected_revision=1, boundaries=[dict(start=0, title="原题"), dict(start=6, title="后半")])
        result = self.client.put(path, json=update)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["preview"]["revision"], 2)
        self.assertEqual(self.client.put(path, json=update).json()["detail"]["code"], "chapter_preview_conflict")
        self.assertEqual(self.confirm(p, 409)["detail"]["code"], "chapter_preview_conflict")
        merged = self.client.put(path, json=dict(expected_revision=2, boundaries=[dict(start=0, title="合并")])).json()["preview"]
        result = self.confirm(merged)
        self.assertEqual(result["workspace"]["active_version"]["chapters"][0]["content"], p["source_text"])

    def test_reject_client_body_and_malformed_boundaries(self):
        self.init_project()
        p = self.preview("甲😀。\r\n乙。")
        path = self.base + f"/chapter-previews/{p['preview_id']}"
        for extra in [dict(content="恶意替换"), dict(end=1), dict(source_text="替换")]:
            response = self.client.put(path, json=dict(expected_revision=1, boundaries=[dict(start=0, title="原题", **extra)]))
            self.assertEqual(response.status_code, 422)
        for cuts in [[0, 2], [0, 5], [0, 0], [1], [0, 999], [0, True]]:
            response = self.client.put(path, json=dict(expected_revision=1, boundaries=[dict(start=s, title="原题") for s in cuts]))
            self.assertEqual(response.status_code, 422)
        response = self.client.post(path + "/confirm", json=dict(expected_revision=1, content="替换"))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get(path).json()["preview"], p)

    def test_resegment_inherits_title_no_recreated_heading_and_preserves_pending_import(self):
        text = NARRATIVE + "\n渡口旧事\n" + NARRATIVE + "\n雨巷重逢\n" + NARRATIVE
        old = self.seed(text, "第一章 — 原题")
        legacy = self.independent.preview_import(self.pid, self.independent.store.load(self.pid).account_id,
                                               filename="未确认.txt", content_base64=self._encoded(text + NARRATIVE))
        p = self.resegment()
        self.assertEqual(p["source_text"], text)
        self.assertEqual([c["title"] for c in p["chapters"]], ["第一章 — 原题", "渡口旧事", "雨巷重逢"])
        self.assertEqual(p["chapters"][0]["start"], 0)
        result = self.confirm(p)
        active = result["workspace"]["active_version"]
        self.assertEqual([c["chapter_number"] for c in active["chapters"]], [1, 2, 3])
        self.assertEqual("".join(c["content"] for c in active["chapters"]), text)
        self.assertEqual(active["source_version_id"], old["active_version_id"])
        self.assertEqual(self.independent.store.load(self.pid).pending_imports[0].model_dump(), legacy.model_dump())

    def test_existing_multiple_chapters_no_inserted_separator(self):
        self.init_project()
        p = self.preview("第一章 原题\n甲。\n第二章 原题\n乙。")
        old = self.confirm(p)["workspace"]
        preview = self.resegment()
        result = self.confirm(preview)["workspace"]
        self.assertEqual([c["content"] for c in result["active_version"]["chapters"]],
                         [c["content"] for c in old["active_version"]["chapters"]])

    def test_six_chapters_without_title_dictionary(self):
        names = ["青石渡", "雁归时", "客中书", "长桥夜", "故园梦"]
        text = NARRATIVE + "\r\n" + "\r\n".join(name + "\r\n" + NARRATIVE for name in names)
        self.seed(text, "第一章 原题")
        p = self.resegment()
        self.assertEqual([c["title"] for c in p["chapters"]], ["第一章 原题", *names])
        chapters = self.confirm(p)["workspace"]["active_version"]["chapters"]
        self.assertEqual([c["chapter_number"] for c in chapters], list(range(1, 7)))
        self.assertEqual("".join(c["content"] for c in chapters), text)

    def test_resegment_stripped_first_heading_keeps_opening_and_later_standard_heading(self):
        text = "甲。\r\n第二章 归来\r\n乙。"
        self.seed(text, "第一章 原题")
        p = self.resegment()
        self.assertEqual([c["title"] for c in p["chapters"]], ["第一章 原题", "第二章 归来"])
        self.assertEqual([c["start"] for c in p["chapters"]], [0, 4])
        self.assertEqual(p["source_text"], text)

    def test_resegment_new_import_does_not_promote_retained_book_wrapper(self):
        self.init_project()
        source = "# 书名\n## 第一章 原题\n甲。\n## 第二章 归来\n乙。"
        self.confirm(self.preview(source))
        p = self.resegment()
        self.assertEqual([c["title"] for c in p["chapters"]], ["第一章 原题", "第二章 归来"])
        self.assertEqual(p["source_text"], source)

    def test_source_hash_identical_to_deconstruction(self):
        self.seed("甲😀。\r\n乙。")
        record = self.independent.store.load(self.pid)
        account = record.account_id
        service = DeconstructionService(independent=self.independent, store=DeconstructionStore(Path(self.tmp.name)/"deconstruction"))
        for mutation in ("none", "draft", "empty_slot", "formal_title", "reorder"):
            record = self.independent.store.load(self.pid)
            version = self.independent._active(record)
            if mutation == "draft":
                version.chapters[0].content += "草稿不入hash"
                version.chapters[0].server_revision = 4
            elif mutation == "empty_slot":
                c = version.chapters[0].model_copy(deep=True)
                c.chapter_id = "empty"
                c.chapter_number = 2
                c.formal_content = c.content = ""
                c.server_revision = 999
                version.chapters.append(c)
            elif mutation == "formal_title":
                version.chapters[0].formal_title = "已确认😀标题"
            elif mutation == "reorder":
                version.chapters.reverse()
            self.independent.store.save(record)
            expected = service._source(self.pid, account)
            snapshot = self.independent.read_source_snapshot(self.pid, account, version.version_id)
            self.assertEqual(snapshot["source_hash"], expected.source_hash, mutation)
            self.assertEqual(snapshot["source_revision"], expected.source_revision, mutation)
            self.assertEqual(self.independent.workspace(self.pid, account)["chapter_source"]["source_hash"], expected.source_hash)

    def test_old_source_permanent_readonly_after_resegment_and_expiry(self):
        old = self.seed("甲😀。\r\n乙。")
        version = old["active_version_id"]
        chapter = old["active_version"]["chapters"][0]
        source_path = self.base + f"/versions/{version}/source"
        before = self.client.get(source_path).json()["snapshot"]
        result = self.confirm(self.resegment())
        record = self.independent.store.load(self.pid)
        frozen = next(v for v in record.versions if v.version_id == version)
        self.assertEqual(frozen.status, "archived")
        self.assertIsNone(frozen.recoverable_until)
        self.assertEqual([c.model_dump(mode="json") for c in frozen.chapters], old["active_version"]["chapters"])
        with patch.object(self.independent, "_now", return_value=self.independent._now()+timedelta(days=3650)):
            after = self.client.get(source_path).json()["snapshot"]
        self.assertTrue(after.pop("historical"))
        before.pop("historical")
        self.assertEqual(after, before)
        response = self.client.put(self.base + f"/chapters/{chapter['chapter_id']}/draft",
                                   json=dict(content="覆盖旧章", expected_revision=1))
        self.assertEqual(response.status_code, 404)
        new_chapter = result["workspace"]["active_version"]["chapters"][0]["chapter_id"]
        self.assertEqual(self.client.get(source_path + f"?chapter_id={new_chapter}").status_code, 404)

    def test_snapshot_filter_full_hash_and_formal_only(self):
        self.init_project()
        active = self.confirm(self.preview("第一章 起点\n甲。\n第二章 终点\n乙。"))["workspace"]["active_version"]
        base = self.base + f"/versions/{active['version_id']}/source"
        full = self.client.get(base).json()["snapshot"]
        cid = active["chapters"][0]["chapter_id"]
        self.client.put(self.base + f"/chapters/{cid}/draft", json=dict(content="未确认新正文", expected_revision=1))
        selected = self.client.get(base + f"?chapter_id={cid}").json()["snapshot"]
        self.assertEqual(selected["source_hash"], full["source_hash"])
        self.assertEqual(selected["chapters"][0]["content"], active["chapters"][0]["formal_content"])
        self.assertEqual(len(selected["chapters"]), 1)

    def test_archived_failed_tasks_cannot_mutate_historical_source(self):
        old = self.seed()
        record = self.independent.store.load(self.pid)
        now = self.independent._now()
        record.tasks.append(AnalysisTask(task_id="old-failure", kind="full_rebuild", status="failed",
            project_id=self.pid, version_id=record.active_version_id, created_at=now, updated_at=now))
        self.independent.store.save(record)
        self.confirm(self.resegment())
        before = self.independent.store._path(self.pid).read_bytes()
        for method in (self.independent.retry_task, self.independent.run_task):
            with self.assertRaises(IndependentServiceError) as caught:
                method(self.pid, record.account_id, "old-failure")
            self.assertEqual(caught.exception.code, "version_read_only")
        self.assertEqual(self.independent.store._path(self.pid).read_bytes(), before)
        source = self.independent.read_source_snapshot(self.pid, record.account_id, old["active_version_id"])
        self.assertEqual(source["chapters"][0]["content"], "甲。\r\n乙。")

    def test_source_cas_version_hash_and_revision(self):
        self.seed()
        p = self.resegment()
        record = self.independent.store.load(self.pid)
        record.versions[-1].chapters[0].server_revision += 1
        self.independent.store.save(record)
        self.assertEqual(self.confirm(p, 409)["detail"]["code"], "chapter_source_conflict")
        for version, digest in [("wrong", p["source_hash"]), (p["source_version_id"], "0"*64)]:
            response = self.client.post(self.base + "/chapter-previews/resegment", json=dict(
                expected_version_id=version, expected_source_hash=digest))
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["detail"]["code"], "chapter_source_conflict")

    def test_nonmax_revision_cas_and_new_empty_slot(self):
        self.init_project()
        self.confirm(self.preview("第一章 起点\n甲。\n第二章 终点\n乙。"))
        record = self.independent.store.load(self.pid)
        record.versions[-1].chapters[0].server_revision = 100
        self.independent.store.save(record)
        p = self.resegment()
        record = self.independent.store.load(self.pid)
        record.versions[-1].chapters[1].server_revision += 1
        self.independent.store.save(record)
        self.assertEqual(self.confirm(p, 409)["detail"]["code"], "chapter_source_conflict")
        p = self.resegment()
        self.client.post(self.base + "/chapters")
        self.assertEqual(self.confirm(p, 409)["detail"]["code"], "chapter_source_conflict")

    def test_pending_changes_and_drafts_rejected_without_mutation(self):
        for kind in ("draft", "title", "pending"):
            self.seed()
            p = self.resegment()
            record = self.independent.store.load(self.pid)
            version = record.versions[-1]
            if kind == "draft":
                version.chapters[0].content += "尚未确认"
            elif kind == "title":
                version.chapters[0].title = "尚未确认标题"
            else:
                record.pending_changes = PendingChangeBatch(batch_id="pending", version_id=version.version_id,
                    created_at=self.independent._now(), updated_at=self.independent._now())
            self.independent.store.save(record)
            before = self.independent.store._path(self.pid).read_bytes()
            response = self.confirm(p, 409)
            self.assertEqual(response["detail"]["code"], "pending_changes_confirmation_required" if kind == "pending" else "chapter_drafts_pending")
            self.assertEqual(self.independent.store._path(self.pid).read_bytes(), before)
            self.assertFalse(self.independent._chapter_source_state(record)["can_resegment"])

    def test_pending_task_prevents_confirm(self):
        self.seed()
        p = self.resegment()
        record = self.independent.store.load(self.pid)
        now = self.independent._now()
        record.tasks.append(AnalysisTask(task_id="busy", kind="chapter_analysis", status="running", project_id=self.pid, version_id=record.active_version_id,
                                        created_at=now, updated_at=now))
        self.independent.store.save(record)
        self.assertEqual(self.confirm(p, 409)["detail"]["code"], "chapter_transaction_pending")

    def test_prepared_transaction_preserved_and_other_projects_do_not_block(self):
        self.seed()
        p = self.resegment()
        record = self.independent.store.load(self.pid)
        journal = SimpleNamespace(project_id=self.pid, account_id=record.account_id, state="prepared")
        coordinator = SimpleNamespace(
            store=SimpleNamespace(list_journals=lambda: [journal]),
            author_write_lock=lambda *args: nullcontext(),
            reconcile_for_read=lambda *args: None,
            overlay_record=lambda record, **kwargs: record,
        )
        self.independent.transaction_coordinator = coordinator
        before = self.independent.store._path(self.pid).read_bytes()
        self.assertEqual(self.confirm(p, 409)["detail"]["code"], "chapter_transaction_pending")
        self.assertEqual(journal.state, "prepared")
        self.assertEqual(self.independent.store._path(self.pid).read_bytes(), before)
        journal.project_id = "different-project"
        self.confirm(p)

    def test_expired_preview_and_tampered_server_source_rejected(self):
        self.init_project()
        p = self.preview("原文不可替换")
        with patch.object(self.independent, "_now", return_value=self.independent._now()+timedelta(days=2)):
            self.assertEqual(self.confirm(p, 409)["detail"]["code"], "chapter_preview_expired")
        record = self.independent.store.load(self.pid)
        record.chapter_previews[0].source_text += "损坏"
        self.independent.store.save(record)
        self.assertEqual(self.confirm(p, 409)["detail"]["code"], "chapter_source_conflict")

    def test_preview_restart_persistence(self):
        self.init_project()
        p = self.preview("原文不可替换")
        record = self.independent.store.load(self.pid)
        restarted = IndependentWorkspaceService(store=self.independent.store, projects=self.independent.projects)
        self.assertEqual(restarted.read_chapter_preview(self.pid, record.account_id, p["preview_id"]).model_dump(mode="json"), p)
        result = restarted.confirm_chapter_preview(self.pid, record.account_id, p["preview_id"], expected_revision=1)
        self.assertEqual(result["workspace"]["active_version"].chapters[0].content, p["source_text"])

    def test_competing_confirm_only_one_version(self):
        self.init_project()
        p = self.preview("原文不可替换")
        account = self.independent.store.load(self.pid).account_id
        def confirm(_):
            service = IndependentWorkspaceService(store=self.independent.store, projects=self.independent.projects)
            try:
                service.confirm_chapter_preview(self.pid, account, p["preview_id"], expected_revision=1)
                return "ok"
            except IndependentServiceError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(confirm, range(2)))
        self.assertCountEqual(outcomes, ["ok", "chapter_preview_confirmed"])
        self.assertEqual(len(self.independent.store.load(self.pid).versions), 1)

    def test_import_cannot_replace_existing_and_sibling_preview_stale(self):
        self.init_project()
        first, second = self.preview("甲。"), self.preview("乙。")
        self.confirm(first)
        self.assertEqual(self.confirm(second, 409)["detail"]["code"], "import_already_confirmed")
        p, q = self.resegment(), self.resegment()
        self.confirm(p)
        self.assertEqual(self.confirm(q, 409)["detail"]["code"], "chapter_source_conflict")

    def test_cross_account_missing_ids_and_unauthenticated(self):
        old = self.seed()
        p = self.resegment()
        source_path = self.base + f"/versions/{old['active_version_id']}/source"
        self.assertEqual(self.client.get(self.base + "/chapter-previews/missing").status_code, 404)
        self.assertEqual(self.client.get(self.base + "/versions/missing/source").status_code, 404)
        with self.assertRaises(IndependentServiceError) as caught:
            self.independent.read_source_snapshot(self.pid, "other", old["active_version_id"])
        self.assertEqual(caught.exception.status_code, 403)
        self.client.cookies.clear()
        self.assertEqual(self.client.get(source_path).status_code, 401)
        self.client.post("/api/auth/email", json={"email": "other@example.com"})
        for path in (source_path, self.base + f"/chapter-previews/{p['preview_id']}"):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_openapi_contract_has_strict_boundaries(self):
        self.init_project()
        schema = self.client.get("/openapi.json").json()
        for suffix, method in [("import", "post"), ("resegment", "post"), ("{preview_id}", "get"),
                               ("{preview_id}", "put"), ("{preview_id}/confirm", "post")]:
            self.assertIn(method, schema["paths"]["/api/independent/projects/{project_id}/chapter-previews/" + suffix])
        boundary = schema["components"]["schemas"]["ChapterBoundary"]
        self.assertFalse(boundary["additionalProperties"])
        self.assertEqual(set(boundary["properties"]), {"start", "title"})
