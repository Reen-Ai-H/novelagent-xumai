"""独立创作工作区服务。

这里刻意不调用模型：无 Key 的本地开发环境使用可审计的确定性演示分析，
同时把分析任务和可替换边界持久化下来，后续可替换任务执行器而不改正文合同。
"""

from __future__ import annotations

import base64
import binascii
import difflib
import hashlib
import io
import logging
import re
import zipfile
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from threading import local
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree

from app.core.independent_store import IndependentStore
from app.core.project_lock import ProjectLockStore, ProjectLockError
from app.core.project_store import ProjectStore, project_store
from app.core.transaction_store import TransactionCommitted
from schemas.independent import (
    AnalysisTask,
    ArchiveSnapshot,
    ChapterDocument,
    ChangeDecision,
    ChangeSummary,
    DeconstructionOutboxItem,
    ForeshadowingItem,
    ImportChapterPreview,
    ImportPreview,
    ImportPreviewRecord,
    IndependentProjectRecord,
    ManuscriptVersion,
    NotificationRecord,
    PendingChangeBatch,
    QuestionItem,
    StoryArchive,
    StoryCharacter,
    StorylineItem,
)


ANALYSIS_LABEL = "确定性演示分析（未配置模型 Key）"
MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_PREVIEWS = 20
RECOVERY_DAYS = 30
logger = logging.getLogger("xumai.independent")


class IndependentServiceError(Exception):
    """可安全展示给前端的业务错误。"""

    def __init__(self, code: str, message: str, *, status_code: int = 400, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data


def _author_write_method(method):
    """给所有会写入独立整记录的入口加持久项目写锁。"""

    @wraps(method)
    def wrapped(self, project_id: str, account_id: str, *args: Any, **kwargs: Any):
        with self._author_write_guard(project_id, account_id):
            return method(self, project_id, account_id, *args, **kwargs)

    return wrapped


class IndependentWorkspaceService:
    """独立作品的正文、分析和版本持久化服务。"""

    def __init__(
        self,
        *,
        store: IndependentStore | None = None,
        projects: ProjectStore = project_store,
    ) -> None:
        self.store = store or IndependentStore()
        self.projects = projects
        # 由 AIStudioService 注入；独立作品自身没有跨 store 导演事务，但其
        # 公开读取必须先尊重已写入的 durable commit marker。
        self.transaction_coordinator: Any | None = None
        self._write_lock_state = local()
        # Independent-only instances do not have the AI transaction
        # coordinator injected, but they still need the same durable project
        # gate as the deconstruction worker.  Both sidecars derive this path
        # from the isolated data root, so tests and restarted processes share
        # one lock without sharing data.
        self.project_locks = ProjectLockStore(self.store.base_dir.parent / ".novel_transactions")
        # 由拆解路由装配；保持可选，便于旧调用方和阶段 2 测试继续独立运行。
        self.deconstruction_service: Any | None = None

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _in_author_write(self) -> bool:
        """Return recursion state for this thread only.

        A process-wide integer would let a second writer mistake another
        thread's active transaction for its own and bypass the project lock.
        """

        return bool(getattr(self._write_lock_state, "depth", 0))

    def _request_deconstruction(self, project_id: str, account_id: str, *, reason: str) -> None:
        """尽力派发同文件 outbox；正文写入成功不受拆解侧车故障反向影响。"""

        service = self.deconstruction_service
        if service is None:
            return
        try:
            service.reconcile_outbox(project_id, account_id, reason=reason)
        except (OSError, ValueError, KeyError):
            self._mark_deconstruction_event_retry(project_id, account_id, error_code="dispatch_unavailable")
        except Exception:  # post-commit outbox dispatch must not turn a saved manuscript into HTTP 500
            self._mark_deconstruction_event_retry(project_id, account_id, error_code="dispatch_failed")
            logger.warning("作品拆解 outbox 暂不可派发，将由后台恢复")

    @staticmethod
    def _deconstruction_event_id(record: IndependentProjectRecord) -> str:
        """按正式稿本内容生成稳定事件键，不把正文放进 outbox。"""

        version = next(
            (item for item in record.versions if item.version_id == record.active_version_id),
            None,
        )
        parts = [record.project_id, record.active_version_id or ""]
        if version is not None:
            for chapter in sorted(version.chapters, key=lambda item: item.chapter_number):
                parts.extend(
                    [
                        chapter.chapter_id,
                        str(chapter.chapter_number),
                        str(chapter.server_revision),
                        IndependentWorkspaceService._hash_text(chapter.formal_content or chapter.content),
                        chapter.formal_title or chapter.title,
                    ]
                )
        return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]

    def _queue_deconstruction_event(self, record: IndependentProjectRecord, *, reason: str) -> str:
        event_id = self._deconstruction_event_id(record)
        if not any(item.event_id == event_id for item in record.deconstruction_outbox):
            record.deconstruction_outbox.append(
                DeconstructionOutboxItem(
                    event_id=event_id,
                    reason=reason,
                    created_at=self._now(),
                )
            )
            record.deconstruction_outbox = record.deconstruction_outbox[-50:]
        return event_id

    def _mark_deconstruction_event_retry(self, project_id: str, account_id: str, *, error_code: str) -> None:
        """只更新安全 outbox 元数据；失败时保留原正文事实和待派发事件。"""

        try:
            record = self.store.load(project_id)
            if record is None or record.account_id != account_id:
                return
            for item in record.deconstruction_outbox:
                item.attempts += 1
                item.last_error_code = error_code
            self.store.save(record)
        except (OSError, ValueError, TypeError):
            return

    def mark_deconstruction_event_retry(self, project_id: str, account_id: str, *, error_code: str) -> None:
        """供拆解 worker 记录派发失败；只写安全 outbox 元数据。"""

        try:
            if self._in_author_write():
                self._mark_deconstruction_event_retry(project_id, account_id, error_code=error_code)
                return
            with self._author_write_guard(project_id, account_id):
                self._mark_deconstruction_event_retry(project_id, account_id, error_code=error_code)
        except (IndependentServiceError, OSError, ValueError, TypeError):
            # 事件本身仍保留，下一轮扫描会再次尝试；元数据失败不能把正文/API
            # 已经完成的事实转成异常响应。
            return

    def _remove_deconstruction_event(self, project_id: str, account_id: str, event_id: str) -> None:
        record = self.store.load(project_id)
        if record is None or record.account_id != account_id:
            return
        remaining = [item for item in record.deconstruction_outbox if item.event_id != event_id]
        if len(remaining) == len(record.deconstruction_outbox):
            return
        record.deconstruction_outbox = remaining
        self.store.save(record)

    def ack_deconstruction_event(self, project_id: str, account_id: str, event_id: str) -> None:
        """确认一个已进入拆解侧车的事件；不在拆解锁内反向拿作者锁。"""

        if self._in_author_write():
            self._remove_deconstruction_event(project_id, account_id, event_id)
            return
        with self._author_write_guard(project_id, account_id):
            self._remove_deconstruction_event(project_id, account_id, event_id)

    @staticmethod
    def _word_count(text: str) -> int:
        return len(re.sub(r"\s+", "", text))

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _slug(value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]

    def _title_from_legacy(self, project_id: str) -> str:
        project = self.projects.load_project(project_id)
        return project.title if project is not None else "未命名独立作品"

    def _load(self, project_id: str, account_id: str) -> IndependentProjectRecord:
        if self.transaction_coordinator is not None and not self._in_author_write():
            self.transaction_coordinator.reconcile_for_read(project_id, account_id)
        record = self.store.load(project_id)
        if record is None:
            raise IndependentServiceError("workspace_not_started", "这部独立作品还没有开始建书。", status_code=404)
        if record.account_id != account_id:
            raise IndependentServiceError("project_forbidden", "无权访问这部作品。", status_code=403)
        if self.transaction_coordinator is not None:
            record = self.transaction_coordinator.overlay_record(
                record,
                project_id=project_id,
                account_id=account_id,
                kind="manuscript",
            )
        return record

    @staticmethod
    def _active(record: IndependentProjectRecord) -> ManuscriptVersion:
        if not record.active_version_id:
            raise IndependentServiceError("workspace_not_started", "请先从空白开始或确认导入预览。", status_code=409)
        version = next(
            (item for item in record.versions if item.version_id == record.active_version_id),
            None,
        )
        if version is None:
            raise IndependentServiceError("version_missing", "当前稿本不存在，无法继续编辑。", status_code=500)
        if version.status != "active":
            raise IndependentServiceError("active_version_missing", "当前没有可编辑的当前稿本。", status_code=409)
        return version

    def _ensure_record(self, project_id: str, account_id: str) -> IndependentProjectRecord:
        if self.transaction_coordinator is not None and not self._in_author_write():
            self.transaction_coordinator.reconcile_for_read(project_id, account_id)
        record = self.store.load(project_id)
        if record is not None:
            if record.account_id != account_id:
                raise IndependentServiceError("project_forbidden", "无权访问这部作品。", status_code=403)
            if self.transaction_coordinator is not None:
                record = self.transaction_coordinator.overlay_record(
                    record,
                    project_id=project_id,
                    account_id=account_id,
                    kind="manuscript",
                )
            return record
        now = self._now()
        return IndependentProjectRecord(
            project_id=project_id,
            account_id=account_id,
            title=self._title_from_legacy(project_id),
            created_at=now,
            updated_at=now,
        )

    @contextmanager
    def _author_write_guard(self, project_id: str, account_id: str):
        """作者写入口的跨进程门禁；未注入 AI 时也拒绝绕过中的旧 writer。"""

        depth = getattr(self._write_lock_state, "depth", 0)
        self._write_lock_state.depth = depth + 1
        try:
            coordinator = self.transaction_coordinator
            # Every entry takes the common hashed project lock.  It is
            # reentrant for recursive calls on this thread, while a second
            # thread must still wait even when this instance is already writing.
            try:
                with self.project_locks.project_lock(project_id):
                    if coordinator is not None:
                        try:
                            # Keep the coordinator's legacy lock nested after
                            # the common lock for journal ordering compatibility.
                            with coordinator.author_write_lock(project_id, account_id):
                                yield
                        except TransactionCommitted as exc:
                            raise IndependentServiceError(
                                "author_revision_conflict",
                                "后台导演事务正在收敛，作者正文没有被覆盖；请稍后重试保存。",
                                status_code=409,
                                data={"retryable": True, "transaction_id": exc.transaction_id},
                            ) from None
                    else:
                        yield
            except ProjectLockError as exc:
                raise IndependentServiceError(
                    "project_lock_unavailable",
                    "作品暂时被另一项操作占用，请稍后重试。",
                    status_code=503,
                    data={"retryable": True},
                ) from exc
        finally:
            if depth:
                self._write_lock_state.depth = depth
            else:
                try:
                    del self._write_lock_state.depth
                except AttributeError:
                    pass

    @_author_write_method
    def start_blank(self, project_id: str, account_id: str) -> IndependentProjectRecord:
        record = self._ensure_record(project_id, account_id)
        if record.active_version_id:
            return record
        now = self._now()
        chapter = ChapterDocument(
            chapter_id=uuid4().hex,
            chapter_number=1,
            title="第一章",
            formal_title="第一章",
            updated_at=now,
        )
        version = ManuscriptVersion(
            version_id=uuid4().hex,
            label="稿本 1 · 初稿",
            created_at=now,
            updated_at=now,
            chapters=[chapter],
            archive=StoryArchive(analysis_label=ANALYSIS_LABEL),
        )
        record.active_version_id = version.version_id
        record.versions.append(version)
        record.updated_at = now
        self.store.save(record)
        return record

    def workspace(self, project_id: str, account_id: str) -> dict[str, Any]:
        record = self._ensure_record(project_id, account_id)
        self.recover_pending_tasks(project_id, account_id)
        record = self._ensure_record(project_id, account_id)
        active = next(
            (version for version in record.versions if version.version_id == record.active_version_id),
            None,
        )
        return {
            "initialized": active is not None,
            "project_id": record.project_id,
            "title": record.title,
            "active_version_id": record.active_version_id,
            "active_version": active,
            "versions": [self._version_summary(version) for version in record.versions],
            "pending_imports": [self._public_import(item) for item in record.pending_imports[-MAX_IMPORT_PREVIEWS:]],
            "pending_changes": record.pending_changes,
            "tasks": record.tasks[-30:],
            "notifications": list(reversed(record.notifications[-20:])),
            "archive": active.archive if active is not None else StoryArchive(analysis_label=ANALYSIS_LABEL),
            "analysis_label": ANALYSIS_LABEL,
        }

    def _version_summary(self, version: ManuscriptVersion) -> dict[str, Any]:
        return {
            "version_id": version.version_id,
            "label": version.label,
            "status": version.status,
            "created_at": version.created_at,
            "updated_at": version.updated_at,
            "recoverable_until": version.recoverable_until,
            "source_version_id": version.source_version_id,
            "chapter_count": len(version.chapters),
            "total_word_count": sum(chapter.word_count for chapter in version.chapters),
            "latest_chapter_number": version.archive.latest_chapter_number,
        }

    @staticmethod
    def _public_import(item: ImportPreviewRecord) -> ImportPreview:
        payload = item.model_dump(exclude={"raw_text"})
        return ImportPreview.model_validate(payload)

    def _set_failure(
        self,
        record: IndependentProjectRecord,
        *,
        filename: str,
        error_message: str,
        input_size_bytes: int = 0,
        raw_text: str = "",
        file_format: str | None = None,
    ) -> ImportPreviewRecord:
        preview = ImportPreviewRecord(
            preview_id=uuid4().hex,
            filename=filename,
            format=file_format if file_format in {"txt", "md", "docx"} else None,
            title=Path(filename).stem or "未命名导入",
            status="failed",
            error_message=error_message,
            input_size_bytes=input_size_bytes,
            raw_preserved=bool(raw_text),
            raw_text=raw_text,
            created_at=self._now(),
        )
        record.pending_imports.append(preview)
        record.updated_at = self._now()
        self.store.save(record)
        return preview

    @staticmethod
    def _decode_docx(content: bytes) -> str:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                xml = archive.read("word/document.xml")
        except (KeyError, zipfile.BadZipFile) as exc:
            raise ValueError("DOCX 文件结构无法读取，请确认文件没有损坏。") from exc

        try:
            root = ElementTree.fromstring(xml)
        except ElementTree.ParseError as exc:
            raise ValueError("DOCX 正文无法解析，请重新导出文件。") from exc

        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs: list[str] = []
        for paragraph in root.iter(f"{namespace}p"):
            parts = [node.text or "" for node in paragraph.iter(f"{namespace}t")]
            text = "".join(parts).strip()
            if text:
                paragraphs.append(text)
        return "\n".join(paragraphs)

    @staticmethod
    def _chinese_number(value: str) -> int | None:
        digits = {
            "一": 1,
            "二": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
        }
        if value.isdigit():
            return int(value)
        if value in digits:
            return digits[value]
        if len(value) == 2 and value[0] == "十" and value[1] in digits:
            return 10 + digits[value[1]]
        if len(value) == 2 and value[1] == "十" and value[0] in digits:
            return digits[value[0]] * 10
        if len(value) == 3 and value[1] == "十" and value[0] in digits and value[2] in digits:
            return digits[value[0]] * 10 + digits[value[2]]
        return None

    @classmethod
    def _heading_number(cls, line: str) -> int | None:
        cleaned = re.sub(r"^\s*#{1,6}\s*", "", line).strip()
        match = re.match(r"^第\s*([0-9一二三四五六七八九十百]+)\s*[章节回卷]", cleaned)
        if match:
            return cls._chinese_number(match.group(1))
        match = re.match(r"^(?:chapter\s+)?(\d+)[、.．:]?\s+", cleaned, re.IGNORECASE)
        return int(match.group(1)) if match else None

    @classmethod
    def _parse_text(cls, filename: str, text: str) -> tuple[str, list[ImportChapterPreview], list[str]]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")
        heading_indexes: list[tuple[int, int, str]] = []
        for index, line in enumerate(lines):
            number = cls._heading_number(line)
            if number is not None:
                title = re.sub(r"^\s*#{1,6}\s*", "", line).strip()
                heading_indexes.append((index, number, title or f"第{number}章"))

        fragments: list[str] = []
        chapters: list[ImportChapterPreview] = []
        if not heading_indexes:
            title = Path(filename).stem or "第一章"
            chapters.append(
                ImportChapterPreview(
                    chapter_number=1,
                    title=title,
                    content=normalized.strip(),
                    word_count=cls._word_count(normalized),
                )
            )
        else:
            preamble = "\n".join(lines[: heading_indexes[0][0]]).strip()
            if preamble:
                fragments.append(preamble)
            for position, (line_index, number, title) in enumerate(heading_indexes):
                end = heading_indexes[position + 1][0] if position + 1 < len(heading_indexes) else len(lines)
                content = "\n".join(lines[line_index + 1 : end]).strip()
                chapters.append(
                    ImportChapterPreview(
                        chapter_number=number,
                        title=title,
                        content=content,
                        word_count=cls._word_count(content),
                    )
                )

        title = Path(filename).stem or (chapters[0].title if chapters else "未命名导入")
        if chapters and len(chapters) == 1 and chapters[0].title != title:
            title = chapters[0].title
        return title, chapters, fragments

    @_author_write_method
    def preview_import(
        self,
        project_id: str,
        account_id: str,
        *,
        filename: str,
        content_base64: str,
    ) -> ImportPreviewRecord:
        record = self._ensure_record(project_id, account_id)
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix not in {"txt", "md", "docx"}:
            return self._set_failure(
                record,
                filename=filename,
                file_format=suffix or None,
                error_message="暂只支持 TXT、MD、DOCX 文件；原始输入已保留，可重新选择文件。",
            )
        try:
            content = base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            return self._set_failure(
                record,
                filename=filename,
                file_format=suffix,
                error_message="文件编码无法读取，请保留原文件后重新上传。",
            )
        raw_text = content.decode("utf-8-sig", errors="replace")
        if len(content) > MAX_IMPORT_BYTES:
            return self._set_failure(
                record,
                filename=filename,
                file_format=suffix,
                input_size_bytes=len(content),
                raw_text=raw_text,
                error_message="文件超过 5 MB 限制；原始输入已保留，请拆分后重新上传。",
            )

        try:
            text = (self._decode_docx(content) if suffix == "docx" else raw_text).strip()
            if not text:
                return self._set_failure(
                    record,
                    filename=filename,
                    file_format=suffix,
                    input_size_bytes=len(content),
                    raw_text=raw_text,
                    error_message="文件中没有可识别的正文或有效章节，原始输入已保留，请补充正文后重新上传。",
                )
            title, chapters, fragments = self._parse_text(filename, text)
            chapters = [chapter for chapter in chapters if chapter.content.strip()]
            if not chapters:
                return self._set_failure(
                    record,
                    filename=filename,
                    file_format=suffix,
                    input_size_bytes=len(content),
                    raw_text=raw_text,
                    error_message="文件中没有可识别的正文或有效章节，原始输入已保留，请补充正文后重新上传。",
                )
        except ValueError as exc:
            return self._set_failure(
                record,
                filename=filename,
                file_format=suffix,
                input_size_bytes=len(content),
                raw_text=raw_text,
                error_message=str(exc),
            )

        preview = ImportPreviewRecord(
            preview_id=uuid4().hex,
            filename=filename,
            format=suffix,  # type: ignore[arg-type]
            title=title,
            chapter_count=len(chapters),
            total_word_count=sum(chapter.word_count for chapter in chapters),
            chapters=chapters,
            unrecognized_fragments=fragments,
            status="pending",
            input_size_bytes=len(content),
            raw_preserved=True,
            raw_text=text,
            created_at=self._now(),
        )
        record.pending_imports.append(preview)
        record.pending_imports = record.pending_imports[-MAX_IMPORT_PREVIEWS:]
        record.updated_at = self._now()
        self.store.save(record)
        return preview

    @_author_write_method
    def confirm_import(self, project_id: str, account_id: str, preview_id: str) -> IndependentProjectRecord:
        record = self._load(project_id, account_id)
        if record.active_version_id:
            raise IndependentServiceError("import_already_confirmed", "这部作品已经有当前稿本，不能重复导入覆盖。", status_code=409)
        preview = next((item for item in record.pending_imports if item.preview_id == preview_id), None)
        if preview is None:
            raise IndependentServiceError("import_preview_missing", "导入预览不存在或已过期。", status_code=404)
        if preview.status == "failed":
            raise IndependentServiceError("import_preview_failed", preview.error_message or "导入预览失败。", status_code=422)
        if preview.status != "pending" or not preview.chapters or not any(item.content.strip() for item in preview.chapters):
            raise IndependentServiceError("import_empty", "预览没有识别到可写入的正文。", status_code=422)

        now = self._now()
        chapters = [
            ChapterDocument(
                chapter_id=uuid4().hex,
                chapter_number=item.chapter_number,
                title=item.title,
                formal_title=item.title,
                content=item.content,
                formal_content=item.content,
                server_revision=1,
                word_count=item.word_count,
                formal_word_count=item.word_count,
                status="ready",
                updated_at=now,
            )
            for item in preview.chapters
        ]
        version = ManuscriptVersion(
            version_id=uuid4().hex,
            label="稿本 1 · 导入初稿",
            created_at=now,
            updated_at=now,
            chapters=chapters,
            archive=StoryArchive(analysis_label=ANALYSIS_LABEL),
        )
        record.active_version_id = version.version_id
        record.versions.append(version)
        preview.status = "confirmed"
        record.updated_at = now
        self._queue_deconstruction_event(record, reason="首次导入确认")
        self.store.save(record)
        self._request_deconstruction(project_id, account_id, reason="首次导入确认")
        return record

    @_author_write_method
    def add_chapter(self, project_id: str, account_id: str, title: str | None = None) -> ChapterDocument:
        record = self._load(project_id, account_id)
        version = self._active(record)
        number = max((chapter.chapter_number for chapter in version.chapters), default=0) + 1
        chapter = ChapterDocument(
            chapter_id=uuid4().hex,
            chapter_number=number,
            title=title or f"第{number}章",
            formal_title=title or f"第{number}章",
            updated_at=self._now(),
        )
        version.chapters.append(chapter)
        version.updated_at = self._now()
        record.updated_at = version.updated_at
        self.store.save(record)
        return chapter

    @_author_write_method
    def commit_system_generated_chapter(
        self,
        project_id: str,
        account_id: str,
        *,
        chapter_number: int,
        content: str,
        title: str,
        archive: StoryArchive | None,
        idempotency_key: str | None,
    ) -> str:
        """兼容旧的独立调用；AI 导演使用 prepare/apply 事务投影。"""

        projection = self.prepare_system_generated_chapter(
            project_id,
            account_id,
            chapter_number=chapter_number,
            content=content,
            title=title,
            archive=archive,
            idempotency_key=idempotency_key,
        )
        return self.apply_system_generated_projection(projection, persist=True)

    def prepare_system_generated_chapter(
        self,
        project_id: str,
        account_id: str,
        *,
        chapter_number: int,
        content: str,
        title: str,
        archive: StoryArchive | None,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        """只在内存构造最终稿本投影，不写正式稿本。"""

        if not content.strip():
            raise IndependentServiceError("empty_chapter", "本章还没有正文，写入内容后再完成。", status_code=422)
        if idempotency_key is None:
            raise IndependentServiceError("idempotency_required", "系统正文提交缺少幂等键。", status_code=422)
        record = self._load(project_id, account_id)
        version = self._active(record)
        if record.pending_changes is not None:
            raise IndependentServiceError(
                "pending_changes_confirmation_required",
                "当前章节存在作者修改，请先确认修改后再继续导演台。",
                status_code=409,
            )
        chapter = next((item for item in version.chapters if item.chapter_number == chapter_number), None)
        content_hash = self._hash_text(content)
        existing_task = next(
            (
                task
                for task in record.tasks
                if task.kind == "chapter_analysis"
                and task.version_id == version.version_id
                and task.content_hash == content_hash
                and task.chapter_id
                and (chapter is None or task.chapter_id == chapter.chapter_id)
                and task.idempotency_key == idempotency_key
                and task.status != "cancelled"
            ),
            None,
        )
        if existing_task is not None and chapter is not None and chapter.formal_content == content:
            next_chapter = chapter.model_copy(deep=True)
            next_archive = archive.model_copy(deep=True) if archive is not None else version.archive.model_copy(deep=True)
            return self._system_projection(
                record,
                version_id=version.version_id,
                chapter=next_chapter,
                archive=next_archive,
                task=existing_task,
                content_hash=content_hash,
                expected_revision=chapter.server_revision,
                baseline_archive=version.archive,
            )

        if chapter is None:
            now = self._now()
            next_chapter = ChapterDocument(
                chapter_id=uuid4().hex,
                chapter_number=chapter_number,
                title=title,
                formal_title=title,
                content=content,
                formal_content=content,
                server_revision=1,
                word_count=self._word_count(content),
                formal_word_count=self._word_count(content),
                status="ready",
                last_completed_hash=content_hash,
                updated_at=now,
            )
            expected_revision = 0
        else:
            if chapter.formal_content and chapter.formal_content != content:
                raise IndependentServiceError(
                    "pending_changes_confirmation_required",
                    "当前章节已有正式正文或作者修改，导演任务没有覆盖它。",
                    status_code=409,
                )
            if chapter.content and chapter.content != content:
                raise IndependentServiceError(
                    "system_generation_conflict",
                    "当前章节已有未完成作者草稿，导演任务没有覆盖它。",
                    status_code=409,
                )
            expected_revision = chapter.server_revision
            next_chapter = chapter.model_copy(deep=True)
            now = self._now()
            next_chapter.content = content
            next_chapter.formal_content = content
            next_chapter.title = title or next_chapter.title
            next_chapter.formal_title = next_chapter.title
            next_chapter.word_count = self._word_count(content)
            next_chapter.formal_word_count = next_chapter.word_count
            next_chapter.server_revision += 1
            next_chapter.status = "ready"
            next_chapter.last_completed_hash = content_hash
            next_chapter.updated_at = now

        if archive is None:
            next_archive = self._analyze_content(version.archive, next_chapter)
            snapshot = self._snapshot(next_archive, chapter_number, version.version_id, content_hash)
            next_archive.snapshots = [
                item for item in next_archive.snapshots if item.chapter_number != chapter_number
            ] + [snapshot]
            next_archive.snapshots.sort(key=lambda item: item.chapter_number)
        else:
            next_archive = archive.model_copy(deep=True)
        now = next_chapter.updated_at
        task_id = self._slug(f"system-chapter:{project_id}:{version.version_id}:{chapter_number}:{content_hash}")
        task = AnalysisTask(
            task_id=task_id,
            kind="chapter_analysis",
            status="completed",
            project_id=project_id,
            version_id=version.version_id,
            chapter_id=next_chapter.chapter_id,
            content_hash=content_hash,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
        if existing_task is not None:
            task = existing_task
        return self._system_projection(
            record,
            version_id=version.version_id,
            chapter=next_chapter,
            archive=next_archive,
            task=task,
            content_hash=content_hash,
            expected_revision=expected_revision,
            baseline_archive=version.archive,
        )

    @staticmethod
    def _system_projection(
        record: IndependentProjectRecord,
        *,
        version_id: str,
        chapter: ChapterDocument,
        archive: StoryArchive,
        task: AnalysisTask,
        content_hash: str,
        expected_revision: int,
        baseline_archive: StoryArchive,
    ) -> dict[str, Any]:
        return {
            "project_id": record.project_id,
            "account_id": record.account_id,
            "version_id": version_id,
            "expected_chapter_revision": expected_revision,
            "chapter": chapter.model_dump(mode="json"),
            "archive": archive.model_dump(mode="json"),
            "task": task.model_dump(mode="json"),
            "content_hash": content_hash,
            "baseline_archive": baseline_archive.model_dump(mode="json"),
        }

    def apply_system_generated_projection_to_record(
        self,
        record: IndependentProjectRecord,
        projection: dict[str, Any],
    ) -> IndependentProjectRecord:
        """在内存应用系统投影；事务读 overlay 使用此路径，不写磁盘。"""

        version = next((item for item in record.versions if item.version_id == projection["version_id"]), None)
        if version is None or record.active_version_id != version.version_id or version.status != "active":
            raise IndependentServiceError("version_conflict", "当前稿本已变化，导演事务安全停止。", status_code=409)
        chapter_payload = ChapterDocument.model_validate(projection["chapter"])
        archive = StoryArchive.model_validate(projection["archive"])
        task = AnalysisTask.model_validate(projection["task"])
        existing = next((item for item in version.chapters if item.chapter_id == chapter_payload.chapter_id), None)
        same_number = next((item for item in version.chapters if item.chapter_number == chapter_payload.chapter_number), None)
        existing_task = next((item for item in record.tasks if item.task_id == task.task_id), None)
        if (
            existing is not None
            and existing.formal_content == chapter_payload.formal_content
            and existing.last_completed_hash == chapter_payload.last_completed_hash
            and existing_task is not None
            and version.archive.model_dump(mode="json") == archive.model_dump(mode="json")
        ):
            return record
        if record.pending_changes is not None:
            raise IndependentServiceError(
                "pending_changes_confirmation_required",
                "当前章节存在作者修改，事务没有覆盖它。",
                status_code=409,
            )
        expected_revision = int(projection["expected_chapter_revision"])
        if existing is not None and existing.server_revision != expected_revision:
            raise IndependentServiceError("revision_conflict", "作者正文版本已变化，事务没有覆盖它。", status_code=409)
        if existing is not None and existing.formal_content and existing.formal_content != chapter_payload.formal_content:
            raise IndependentServiceError("system_generation_conflict", "正式正文已变化，事务没有覆盖它。", status_code=409)
        if existing is None:
            if expected_revision != 0:
                raise IndependentServiceError("revision_conflict", "章节版本已变化，事务没有覆盖它。", status_code=409)
            if same_number is not None:
                raise IndependentServiceError("revision_conflict", "作者已经创建同编号章节，事务没有覆盖它。", status_code=409)
            version.chapters.append(chapter_payload)
        else:
            version.chapters[version.chapters.index(existing)] = chapter_payload
        version.archive = archive
        if existing_task is None:
            record.tasks.append(task)
        else:
            record.tasks[record.tasks.index(existing_task)] = task
        version.updated_at = chapter_payload.updated_at
        record.updated_at = version.updated_at
        self._sync_pending_changes(record, version)
        return record

    def inspect_system_generated_projection(self, projection: dict[str, Any]) -> str:
        """在每个跨 store 投影边界检查作者 revision 是否漂移。

        ``ok`` 表示仍可按 journal 预期投影，``applied`` 表示稿本侧已被同一
        系统 payload 幂等写入；其它结果都走作者优先补偿，不能把 revision
        漂移误当成普通投影异常而永久卡在 committed/projecting。
        """

        project_id = str(projection["project_id"])
        record = self.store.load(project_id)
        if record is None or record.account_id != str(projection["account_id"]):
            return "conflict"
        version = next((item for item in record.versions if item.version_id == projection["version_id"]), None)
        if version is None or record.active_version_id != version.version_id or version.status != "active":
            return "conflict"
        chapter_payload = ChapterDocument.model_validate(projection["chapter"])
        task_payload = AnalysisTask.model_validate(projection["task"])
        expected_revision = int(projection["expected_chapter_revision"])
        existing = next((item for item in version.chapters if item.chapter_id == chapter_payload.chapter_id), None)
        same_number = next((item for item in version.chapters if item.chapter_number == chapter_payload.chapter_number), None)
        existing_task = next((item for item in record.tasks if item.task_id == task_payload.task_id), None)
        if existing is not None and existing.server_revision == expected_revision:
            if record.pending_changes is not None:
                return f"conflict:{existing.server_revision}"
            return "ok"
        if (
            existing is not None
            and existing.model_dump(mode="json") == chapter_payload.model_dump(mode="json")
            and existing_task is not None
            and version.archive.model_dump(mode="json") == StoryArchive.model_validate(projection["archive"]).model_dump(mode="json")
        ):
            return "applied"
        if existing is None and expected_revision == 0 and record.pending_changes is None:
            if same_number is not None:
                return f"conflict:{same_number.server_revision}"
            return "ok"
        return f"conflict:{existing.server_revision if existing is not None else expected_revision + 1}"

    def compensate_author_revision(
        self,
        projection: dict[str, Any],
        *,
        persist: bool = True,
        record_override: IndependentProjectRecord | None = None,
    ) -> IndependentProjectRecord:
        """移除本事务对稿本/档案的公开投影，同时逐字保留作者 revision。"""

        # persist=True is an internal transaction callback. The
        # CrossStoreTransactionCoordinator invokes it while holding the same
        # common-project-lock -> legacy-transaction-lock section used by
        # apply_system_generated_projection; persist=False only mutates an
        # in-memory overlay and never calls IndependentStore.save.
        project_id = str(projection["project_id"])
        account_id = str(projection["account_id"])
        raw = record_override if record_override is not None else self.store.load(project_id)
        if raw is None or raw.account_id != account_id:
            raise IndependentServiceError("project_forbidden", "无权补偿这部作品。", status_code=404)
        record = raw.model_copy(deep=True)
        version = next((item for item in record.versions if item.version_id == projection["version_id"]), None)
        if version is None or record.active_version_id != version.version_id:
            raise IndependentServiceError("version_conflict", "当前稿本已变化，作者正文保留且事务停止。", status_code=409)
        chapter_payload = ChapterDocument.model_validate(projection["chapter"])
        task_payload = AnalysisTask.model_validate(projection["task"])
        expected_revision = int(projection["expected_chapter_revision"])
        chapter = next((item for item in version.chapters if item.chapter_id == chapter_payload.chapter_id), None)
        if chapter is not None:
            # 只有与系统 payload 完全一致且仍是 expected revision 的章节才是
            # 尚未发生作者写入的旧状态；其它情况一律保留当前 content/title，
            # 清掉 AI formal 字段，避免把系统正文伪装成作者正式稿。
            unchanged_before_projection = (
                chapter.server_revision == expected_revision
                and chapter.content == ""
                and not chapter.formal_content
            )
            if not unchanged_before_projection:
                chapter.formal_content = ""
                chapter.formal_title = None
                chapter.formal_word_count = 0
                chapter.last_completed_hash = None
                chapter.status = "drafting"
        version_archive = projection.get("baseline_archive")
        if version_archive:
            version.archive = StoryArchive.model_validate(version_archive)
        else:
            version.archive.snapshots = [
                item for item in version.archive.snapshots if item.chapter_number != chapter_payload.chapter_number
            ]
            if version.archive.latest_chapter_number == chapter_payload.chapter_number:
                version.archive.latest_chapter_number = max(
                    (item.chapter_number for item in version.archive.snapshots),
                    default=None,
                )
        record.tasks = [item for item in record.tasks if item.task_id != task_payload.task_id]
        self._sync_pending_changes(record, version)
        now = self._now()
        version.updated_at = max(version.updated_at, now)
        record.updated_at = now
        if persist:
            self.store.save(record)
        return record

    def apply_system_generated_projection(self, projection: dict[str, Any], *, persist: bool) -> str:
        """把已准备好的安全投影幂等应用到稿本 store。

        This method intentionally has no author-write decorator.  The durable
        transaction coordinator calls it from its common-project-lock -> legacy
        transaction-lock critical section; adding the coordinator lock here
        would make a committed apply callback try to reconcile its own marker.
        The compatibility entry point above is guarded before it reaches this
        method.
        """

        project_id = str(projection["project_id"])
        account_id = str(projection["account_id"])
        record = self.store.load(project_id)
        if record is None:
            raise IndependentServiceError("workspace_not_started", "独立稿本不存在。", status_code=404)
        if record.account_id != account_id:
            raise IndependentServiceError("project_forbidden", "无权访问这部作品。", status_code=403)
        self.apply_system_generated_projection_to_record(record, projection)
        if persist:
            self.store.save(record)
        return str(projection["task"]["task_id"])

    def recover_system_generated_chapter(
        self,
        project_id: str,
        account_id: str,
        *,
        chapter_number: int,
        idempotency_key: str,
    ) -> tuple[str, str] | None:
        """读取旧竞态留下的、可证明属于同一系统 run 的正式正文。

        这是内部恢复边界，不进入 API。必须同时满足稿本正文未被作者改动、分析
        任务属于当前 active version、幂等键精确相等且内容哈希一致；否则宁可让
        本轮失败，也不把任意正式正文当成模型缓存。
        """

        record = self._load(project_id, account_id)
        version = self._active(record)
        chapter = next((item for item in version.chapters if item.chapter_number == chapter_number), None)
        if chapter is None or not chapter.formal_content or chapter.content != chapter.formal_content:
            return None
        content_hash = self._hash_text(chapter.formal_content)
        task = next(
            (
                item
                for item in record.tasks
                if item.kind == "chapter_analysis"
                and item.status == "completed"
                and item.version_id == version.version_id
                and item.chapter_id == chapter.chapter_id
                and item.content_hash == content_hash
                and item.idempotency_key == idempotency_key
            ),
            None,
        )
        if task is None:
            return None
        return chapter.formal_content, task.task_id

    def _chapter(self, record: IndependentProjectRecord, chapter_id: str) -> tuple[ManuscriptVersion, ChapterDocument]:
        version = self._active(record)
        chapter = next((item for item in version.chapters if item.chapter_id == chapter_id), None)
        if chapter is None:
            raise IndependentServiceError("chapter_missing", "章节不存在。", status_code=404)
        return version, chapter

    @staticmethod
    def _change_ranges(before: str, after: str) -> list[str]:
        ranges: list[str] = []
        matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
        for tag, start, end, new_start, new_end in matcher.get_opcodes():
            if tag == "equal":
                continue
            old_end = max(start + 1, end)
            new_end_display = max(new_start + 1, new_end)
            ranges.append(f"原文第 {start + 1}—{old_end} 字 → 当前第 {new_start + 1}—{new_end_display} 字")
        return ranges[:8]

    def _change_summary(self, chapter: ChapterDocument) -> ChangeSummary:
        before_count = self._word_count(chapter.formal_content)
        after_count = chapter.word_count
        return ChangeSummary(
            chapter_id=chapter.chapter_id,
            chapter_number=chapter.chapter_number,
            title=chapter.title,
            before_word_count=before_count,
            after_word_count=after_count,
            delta_word_count=after_count - before_count,
            changed_ranges=self._change_ranges(chapter.formal_content, chapter.content),
            recommendation=(
                "轻微措辞变化，可忽略并继续"
                if abs(after_count - before_count) <= 20
                else "建议根据当前全文重建档案"
            ),
        )

    def _sync_pending_changes(self, record: IndependentProjectRecord, version: ManuscriptVersion) -> None:
        changes = [
            self._change_summary(chapter)
            for chapter in version.chapters
            if (chapter.formal_content or chapter.last_completed_hash)
            and (chapter.content != chapter.formal_content or chapter.title != (chapter.formal_title or chapter.title))
        ]
        now = self._now()
        if not changes:
            record.pending_changes = None
            return
        if record.pending_changes is None or record.pending_changes.version_id != version.version_id:
            record.pending_changes = PendingChangeBatch(
                batch_id=uuid4().hex,
                version_id=version.version_id,
                created_at=now,
                updated_at=now,
                changes=changes,
            )
        else:
            record.pending_changes.changes = changes
            record.pending_changes.updated_at = now

    @_author_write_method
    def save_draft(
        self,
        project_id: str,
        account_id: str,
        chapter_id: str,
        *,
        content: str,
        title: str | None,
        expected_revision: int,
    ) -> ChapterDocument:
        record = self._load(project_id, account_id)
        version, chapter = self._chapter(record, chapter_id)
        if expected_revision != chapter.server_revision:
            raise IndependentServiceError(
                "save_conflict",
                "服务器上的章节已被另一端更新，本次草稿没有覆盖它。",
                status_code=409,
                data={"chapter": chapter.model_dump(mode="json"), "server_revision": chapter.server_revision},
            )
        chapter.content = content
        if title is not None and title.strip():
            chapter.title = title.strip()
        chapter.word_count = self._word_count(content)
        chapter.server_revision += 1
        chapter.updated_at = self._now()
        if content != chapter.formal_content or chapter.title != (chapter.formal_title or chapter.title):
            chapter.status = "drafting"
        elif chapter.status != "analyzing":
            chapter.status = "ready" if chapter.formal_content else "drafting"
        version.updated_at = chapter.updated_at
        self._sync_pending_changes(record, version)
        record.updated_at = chapter.updated_at
        self.store.save(record)
        return chapter

    @_author_write_method
    def complete_chapter(
        self,
        project_id: str,
        account_id: str,
        chapter_id: str,
        *,
        content: str,
        expected_revision: int,
        idempotency_key: str | None,
    ) -> AnalysisTask:
        record = self._load(project_id, account_id)
        version, chapter = self._chapter(record, chapter_id)
        if expected_revision != chapter.server_revision or content != chapter.content:
            raise IndependentServiceError(
                "save_required",
                "请先保存当前正文，保存成功后才能完成本章。",
                status_code=409,
                data={"chapter": chapter.model_dump(mode="json"), "server_revision": chapter.server_revision},
            )
        if chapter.formal_content and (content != chapter.formal_content or chapter.title != (chapter.formal_title or chapter.title)):
            raise IndependentServiceError(
                "pending_changes_confirmation_required",
                "旧章修改已进入待确认批次，请先选择忽略轻微措辞或根据当前全文重建档案。",
                status_code=409,
                data={"pending_changes": record.pending_changes.model_dump(mode="json") if record.pending_changes else None},
            )
        content_hash = self._hash_text(content)
        existing = next(
            (
                task
                for task in record.tasks
                if task.kind == "chapter_analysis"
                and task.version_id == version.version_id
                and task.chapter_id == chapter.chapter_id
                and task.content_hash == content_hash
                and task.status != "cancelled"
            ),
            None,
        )
        if existing is not None:
            return existing
        if not content.strip():
            raise IndependentServiceError("empty_chapter", "本章还没有正文，写入内容后再完成。", status_code=422)
        now = self._now()
        chapter.formal_content = content
        chapter.formal_title = chapter.title
        chapter.formal_word_count = chapter.word_count
        chapter.last_completed_hash = content_hash
        chapter.status = "analyzing"
        task_id = self._slug(f"chapter:{project_id}:{version.version_id}:{chapter.chapter_id}:{content_hash}")
        task = AnalysisTask(
            task_id=task_id,
            kind="chapter_analysis",
            status="queued",
            project_id=project_id,
            version_id=version.version_id,
            chapter_id=chapter.chapter_id,
            content_hash=content_hash,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        record.tasks.append(task)
        version.updated_at = now
        record.updated_at = now
        self._sync_pending_changes(record, version)
        self._queue_deconstruction_event(record, reason="完成本章")
        self.store.save(record)
        self._request_deconstruction(project_id, account_id, reason="完成本章")
        return task

    def task(self, project_id: str, account_id: str, task_id: str) -> AnalysisTask:
        record = self._load(project_id, account_id)
        task = next((item for item in record.tasks if item.task_id == task_id), None)
        if task is None:
            raise IndependentServiceError("task_missing", "后台任务不存在。", status_code=404)
        return task

    def recover_pending_tasks(self, project_id: str, account_id: str) -> None:
        record = self.store.load(project_id)
        if record is None or record.account_id != account_id:
            return
        pending = [task.task_id for task in record.tasks if task.status in {"queued", "running"}]
        for task_id in pending:
            self.run_task(project_id, account_id, task_id)

    def _notify(self, record: IndependentProjectRecord, kind: str, message: str) -> None:
        record.notifications.append(
            NotificationRecord(
                notification_id=uuid4().hex,
                kind=kind,  # type: ignore[arg-type]
                message=message,
                created_at=self._now(),
            )
        )
        record.notifications = record.notifications[-50:]

    def _find_task(self, record: IndependentProjectRecord, task_id: str) -> AnalysisTask:
        task = next((item for item in record.tasks if item.task_id == task_id), None)
        if task is None:
            raise IndependentServiceError("task_missing", "后台任务不存在。", status_code=404)
        return task

    @staticmethod
    def _append_unique(items: list[Any], item: Any, key: str) -> None:
        if not any(getattr(existing, key) == getattr(item, key) for existing in items):
            items.append(item)

    def _analyze_content(self, archive: StoryArchive, chapter: ChapterDocument) -> StoryArchive:
        next_archive = archive.model_copy(deep=True)
        next_archive.analysis_label = ANALYSIS_LABEL
        next_archive.latest_chapter_number = max(
            chapter.chapter_number,
            next_archive.latest_chapter_number or chapter.chapter_number,
        )
        text = chapter.formal_content or chapter.content
        explicit_characters = re.findall(r"人物\s*[:：]\s*([^\n。；;]+)", text)
        character_names: list[str] = []
        for group in explicit_characters:
            for name in re.split(r"[、，,；;和与及]\s*", group):
                cleaned = name.strip(" ：:，,、；;")
                if 1 < len(cleaned) <= 12 and cleaned not in character_names:
                    character_names.append(cleaned)
        for name in character_names:
            character = StoryCharacter(
                character_id=self._slug(f"character:{name}"),
                name=name,
                role="主要人物" if not next_archive.characters else "相关人物",
                profile=f"由第 {chapter.chapter_number} 章的确定性演示分析识别。",
                current_state="本章已出现，后续状态待补充。",
                source_chapter_number=chapter.chapter_number,
            )
            existing = next((item for item in next_archive.characters if item.character_id == character.character_id), None)
            if existing is None:
                next_archive.characters.append(character)
            else:
                existing.current_state = character.current_state
                existing.source_chapter_number = chapter.chapter_number
                existing.profile = character.profile

        storyline_matches = re.findall(r"剧情线\s*[:：]\s*([^\n。；;]+)", text)
        for title in storyline_matches:
            cleaned = title.strip(" ：:，,、；;")
            if not cleaned:
                continue
            item = StorylineItem(
                storyline_id=self._slug(f"storyline:{cleaned}"),
                title=cleaned,
                summary=f"第 {chapter.chapter_number} 章继续推进：{cleaned}。",
                source_chapter_number=chapter.chapter_number,
            )
            existing = next((entry for entry in next_archive.storylines if entry.storyline_id == item.storyline_id), None)
            if existing is None:
                next_archive.storylines.append(item)
            else:
                existing.summary = item.summary
                existing.source_chapter_number = chapter.chapter_number

        for line in text.splitlines():
            cleaned = line.strip()
            if not cleaned or not re.search(r"伏笔|线索|秘密|约定", cleaned):
                continue
            item = ForeshadowingItem(
                foreshadowing_id=self._slug(f"foreshadowing:{cleaned}"),
                text=cleaned,
                source_chapter_number=chapter.chapter_number,
            )
            self._append_unique(next_archive.foreshadowing, item, "foreshadowing_id")

        question_candidates = re.findall(r"[^。！？!?\n]{2,80}[？?]", text)
        if not question_candidates and text.strip():
            question_candidates = ["本章留下的线索是否需要回看前文？"]
        for question in question_candidates[:5]:
            item = QuestionItem(
                question_id=self._slug(f"question:{question}"),
                text=question.strip(),
                source_chapter_number=chapter.chapter_number,
            )
            self._append_unique(next_archive.questions, item, "question_id")
        return next_archive

    def _snapshot(self, archive: StoryArchive, chapter_number: int, version_id: str, content_hash: str) -> ArchiveSnapshot:
        snapshot_id = self._slug(f"snapshot:{version_id}:{chapter_number}:{content_hash}")
        return ArchiveSnapshot(
            snapshot_id=snapshot_id,
            chapter_number=chapter_number,
            created_at=self._now(),
            analysis_label=ANALYSIS_LABEL,
            characters=deepcopy(archive.characters),
            storylines=deepcopy(archive.storylines),
            foreshadowing=deepcopy(archive.foreshadowing),
            questions=deepcopy(archive.questions),
        )

    def _run_chapter_analysis(self, record: IndependentProjectRecord, task: AnalysisTask) -> None:
        version = next((item for item in record.versions if item.version_id == task.version_id), None)
        chapter = next((item for item in version.chapters if item.chapter_id == task.chapter_id), None) if version else None
        if version is None or chapter is None:
            raise IndependentServiceError("analysis_context_missing", "分析所需的稿本或章节已不存在。", status_code=500)
        text = chapter.formal_content or chapter.content
        if "[[analysis-fail]]" in text:
            raise IndependentServiceError("analysis_demo_failed", "确定性演示分析遇到显式失败标记，可修改正文后重试。", status_code=500)
        next_archive = self._analyze_content(version.archive, chapter)
        snapshot = self._snapshot(next_archive, chapter.chapter_number, version.version_id, task.content_hash or self._hash_text(text))
        next_archive.snapshots = [
            item for item in next_archive.snapshots if item.chapter_number != chapter.chapter_number
        ] + [snapshot]
        next_archive.snapshots.sort(key=lambda item: item.chapter_number)
        version.archive = next_archive
        chapter.status = "ready"
        task.status = "completed"
        task.completed_at = self._now()
        task.updated_at = task.completed_at
        version.updated_at = task.completed_at
        self._notify(record, "analysis_completed", f"第 {chapter.chapter_number} 章分析完成，故事档案已更新。")

    def _new_rebuild_task(self, record: IndependentProjectRecord, version: ManuscriptVersion, *, kind: str) -> AnalysisTask:
        now = self._now()
        task_id = self._slug(f"{kind}:{record.project_id}:{version.version_id}")
        return AnalysisTask(
            task_id=task_id,
            kind=kind,  # type: ignore[arg-type]
            status="queued",
            project_id=record.project_id,
            version_id=version.version_id,
            created_at=now,
            updated_at=now,
        )

    def _prepare_full_rebuild(self, record: IndependentProjectRecord, version: ManuscriptVersion) -> None:
        archive = StoryArchive(analysis_label=ANALYSIS_LABEL)
        for chapter in version.chapters:
            chapter.formal_content = chapter.content
            chapter.formal_title = chapter.title
            chapter.formal_word_count = chapter.word_count
            chapter.last_completed_hash = self._hash_text(chapter.content)
            chapter.status = "analyzing"
            archive = self._analyze_content(archive, chapter)
            archive.snapshots.append(
                self._snapshot(archive, chapter.chapter_number, version.version_id, chapter.last_completed_hash)
            )
        archive.snapshots.sort(key=lambda item: item.chapter_number)
        version.archive = archive

    def _run_full_rebuild(self, record: IndependentProjectRecord, task: AnalysisTask) -> None:
        version = next((item for item in record.versions if item.version_id == task.version_id), None)
        if version is None:
            raise IndependentServiceError("version_missing", "重建稿本不存在。", status_code=500)
        if any("[[analysis-fail]]" in chapter.content for chapter in version.chapters):
            raise IndependentServiceError("analysis_demo_failed", "确定性演示分析遇到显式失败标记，可修改正文后重试。", status_code=500)
        self._prepare_full_rebuild(record, version)
        for chapter in version.chapters:
            chapter.status = "ready"
        task.status = "completed"
        task.completed_at = self._now()
        task.updated_at = task.completed_at
        version.updated_at = task.completed_at
        self._notify(record, "analysis_completed", "全文档案重建完成，当前稿本已成为唯一正式版本。")

    @_author_write_method
    def run_task(self, project_id: str, account_id: str, task_id: str) -> AnalysisTask:
        record = self._load(project_id, account_id)
        task = self._find_task(record, task_id)
        if task.status in {"completed", "cancelled"}:
            return task
        task.status = "running"
        task.updated_at = self._now()
        self.store.save(record)
        try:
            if task.kind == "chapter_analysis":
                self._run_chapter_analysis(record, task)
            else:
                self._run_full_rebuild(record, task)
        except IndependentServiceError as exc:
            task.status = "failed"
            task.error_message = exc.message
            task.updated_at = self._now()
            task.completed_at = None
            version = next((item for item in record.versions if item.version_id == task.version_id), None)
            if version is not None and task.chapter_id:
                chapter = next((item for item in version.chapters if item.chapter_id == task.chapter_id), None)
                if chapter is not None:
                    chapter.status = "failed"
            self._notify(record, "analysis_failed", exc.message)
        except Exception as exc:  # pragma: no cover - 兜底会被确定性错误测试覆盖
            task.status = "failed"
            task.error_message = f"后台分析异常：{exc}"
            task.updated_at = self._now()
            self._notify(record, "analysis_failed", task.error_message)
        self.store.save(record)
        return task

    @_author_write_method
    def retry_task(self, project_id: str, account_id: str, task_id: str) -> AnalysisTask:
        record = self._load(project_id, account_id)
        task = self._find_task(record, task_id)
        if task.status != "failed":
            raise IndependentServiceError("task_not_retryable", "只有失败任务可以重试。", status_code=409)
        version = next((item for item in record.versions if item.version_id == task.version_id), None)
        if version is None:
            raise IndependentServiceError("version_missing", "重试所需的稿本不存在。", status_code=500)
        if task.chapter_id:
            chapter = next((item for item in version.chapters if item.chapter_id == task.chapter_id), None)
            if chapter is None:
                raise IndependentServiceError("chapter_missing", "重试所需的章节不存在。", status_code=404)
            current_content = chapter.content
            if current_content != chapter.formal_content or chapter.title != (chapter.formal_title or chapter.title):
                chapter.formal_content = current_content
                chapter.formal_title = chapter.title
                chapter.formal_word_count = chapter.word_count
                chapter.last_completed_hash = self._hash_text(current_content)
                chapter.status = "analyzing"
            task.content_hash = self._hash_text(current_content)
        task.status = "queued"
        task.error_message = None
        task.updated_at = self._now()
        self.store.save(record)
        return self.run_task(project_id, account_id, task_id)

    def archive(self, project_id: str, account_id: str, chapter_number: int | None = None) -> dict[str, Any]:
        record = self._load(project_id, account_id)
        version = self._active(record)
        selected = version.archive
        selected_number = version.archive.latest_chapter_number
        if chapter_number is not None:
            snapshot = next((item for item in version.archive.snapshots if item.chapter_number == chapter_number), None)
            if snapshot is None:
                raise IndependentServiceError("snapshot_missing", "这个章节还没有可查看的档案快照。", status_code=404)
            selected = StoryArchive(
                analysis_label=snapshot.analysis_label,
                latest_chapter_number=snapshot.chapter_number,
                characters=deepcopy(snapshot.characters),
                storylines=deepcopy(snapshot.storylines),
                foreshadowing=deepcopy(snapshot.foreshadowing),
                questions=deepcopy(snapshot.questions),
                snapshots=[snapshot],
            )
            selected_number = chapter_number
        return {
            "read_only": chapter_number is not None,
            "selected_chapter_number": selected_number,
            "active_version_id": version.version_id,
            "available_snapshots": version.archive.snapshots,
            "archive": selected,
        }

    def version_preview(self, project_id: str, account_id: str, version_id: str) -> dict[str, Any]:
        record = self._load(project_id, account_id)
        version = next((item for item in record.versions if item.version_id == version_id), None)
        if version is None:
            raise IndependentServiceError("version_missing", "稿本版本不存在。", status_code=404)
        return {"read_only": version.version_id != record.active_version_id, "version": version, "archive": version.archive}

    @_author_write_method
    def resolve_changes(self, project_id: str, account_id: str, decision: ChangeDecision) -> dict[str, Any]:
        record = self._load(project_id, account_id)
        version = self._active(record)
        batch = record.pending_changes
        if batch is None or not batch.changes:
            raise IndependentServiceError("no_pending_changes", "当前没有待确认的旧章修改。", status_code=409)
        now = self._now()
        if decision == "ignore":
            for chapter in version.chapters:
                if chapter.content != chapter.formal_content or chapter.title != (chapter.formal_title or chapter.title):
                    chapter.formal_content = chapter.content
                    chapter.formal_title = chapter.title
                    chapter.formal_word_count = chapter.word_count
                    chapter.last_completed_hash = self._hash_text(chapter.content)
                    chapter.status = "ready"
            batch.last_decision = "ignore"
            batch.decision_note = "作者选择忽略轻微措辞并继续；本次未重建档案。"
            record.change_history.append(f"{now.isoformat()}：忽略轻微措辞并继续，保留现有档案。")
            self._notify(record, "change_decision", batch.decision_note)
            record.pending_changes = None
            version.updated_at = now
            record.updated_at = now
            self.store.save(record)
            return {"decision": decision, "task": None, "version": version}

        old_version_id = version.version_id
        version.status = "recoverable"
        version.recoverable_until = now + timedelta(days=RECOVERY_DAYS)
        for task in record.tasks:
            if task.version_id == old_version_id and task.status in {"queued", "running"}:
                task.status = "cancelled"
                task.error_message = "原稿本已进入历史恢复区，原分析任务失效。"
                task.updated_at = now
        # Clone the author-visible current text first, then freeze the old
        # version back to its last formal state.  Draft saves intentionally
        # update ``chapter.content`` in place while leaving ``formal_content``
        # untouched; retaining that draft on the recoverable version would let
        # a later restore resurrect text the author never confirmed.
        new_version = self._clone_as_active(version, label=f"稿本 {len(record.versions) + 1} · 全文重建", source_version_id=old_version_id)
        self._freeze_recoverable_version(version)
        record.versions.append(new_version)
        record.active_version_id = new_version.version_id
        record.pending_changes = None
        task = self._new_rebuild_task(record, new_version, kind="full_rebuild")
        record.tasks.append(task)
        record.change_history.append(f"{now.isoformat()}：根据当前全文重建档案，创建 {new_version.label}。")
        self._notify(record, "version_created", f"已创建 {new_version.label}；旧稿本保留至 {version.recoverable_until.date()}。")
        record.updated_at = now
        self._queue_deconstruction_event(record, reason="全文重建")
        self.store.save(record)
        self._request_deconstruction(project_id, account_id, reason="全文重建")
        return {"decision": decision, "task": task, "version": new_version, "old_version": version}

    def _freeze_recoverable_version(self, version: ManuscriptVersion) -> None:
        """Keep a recoverable version at its last confirmed author state."""

        for chapter in version.chapters:
            formal_content = chapter.formal_content
            chapter.content = formal_content
            chapter.word_count = chapter.formal_word_count or self._word_count(formal_content)
            if chapter.formal_title:
                chapter.title = chapter.formal_title
            chapter.status = "ready" if formal_content else "drafting"
            chapter.last_completed_hash = self._hash_text(formal_content) if formal_content else None

    def _clone_as_active(self, source: ManuscriptVersion, *, label: str, source_version_id: str) -> ManuscriptVersion:
        now = self._now()
        chapters: list[ChapterDocument] = []
        for item in source.chapters:
            chapter = item.model_copy(deep=True)
            chapter.chapter_id = uuid4().hex
            chapter.formal_content = chapter.content
            chapter.formal_title = chapter.title
            chapter.formal_word_count = chapter.word_count
            chapter.last_completed_hash = None
            chapter.status = "analyzing"
            chapter.updated_at = now
            chapters.append(chapter)
        return ManuscriptVersion(
            version_id=uuid4().hex,
            label=label,
            status="active",
            created_at=now,
            updated_at=now,
            source_version_id=source_version_id,
            chapters=chapters,
            archive=StoryArchive(analysis_label=ANALYSIS_LABEL),
        )

    @staticmethod
    def _restore_projection_matches_source(
        active: ManuscriptVersion,
        source: ManuscriptVersion,
    ) -> bool:
        """Check whether a restore result is still the same author state."""

        if active.source_version_id != source.version_id:
            return False
        current_chapters = sorted(active.chapters, key=lambda item: item.chapter_number)
        source_chapters = sorted(source.chapters, key=lambda item: item.chapter_number)
        if len(current_chapters) != len(source_chapters):
            return False
        for current, original in zip(current_chapters, source_chapters):
            if (
                current.chapter_number,
                current.title,
                current.content,
                current.formal_content,
                current.server_revision,
                current.word_count,
                current.formal_word_count,
            ) != (
                original.chapter_number,
                original.title,
                original.content,
                original.formal_content,
                original.server_revision,
                original.word_count,
                original.formal_word_count,
            ):
                return False
        return True

    @_author_write_method
    def restore_version(self, project_id: str, account_id: str, version_id: str) -> dict[str, Any]:
        record = self._load(project_id, account_id)
        selected = next((item for item in record.versions if item.version_id == version_id), None)
        if selected is None:
            raise IndependentServiceError("version_missing", "稿本版本不存在。", status_code=404)
        old_active = self._active(record)
        has_unconfirmed_changes = record.pending_changes is not None or any(
            chapter.content != chapter.formal_content
            or chapter.title != (chapter.formal_title or chapter.title)
            for chapter in old_active.chapters
        )
        if has_unconfirmed_changes:
            raise IndependentServiceError(
                "pending_changes_confirmation_required",
                "当前稿本存在未确认修改，请先选择忽略或根据当前全文重建后再恢复历史稿本。",
                status_code=409,
                data={
                    "pending_changes": (
                        record.pending_changes.model_dump(mode="json")
                        if record.pending_changes is not None
                        else None
                    )
                },
            )
        if selected.version_id == old_active.version_id:
            raise IndependentServiceError("version_already_active", "当前已经是当前稿本。", status_code=409)
        if selected.recoverable_until is not None and selected.recoverable_until <= self._now():
            raise IndependentServiceError("version_expired", "这个历史稿本已超过 30 天恢复期限，但仍保留为历史记录。", status_code=410)
        existing_restore = next(
            (
                task
                for task in record.tasks
                if task.kind == "restore"
                and task.version_id == old_active.version_id
                and task.status != "cancelled"
            ),
            None,
        )
        if (
            existing_restore is not None
            and self._restore_projection_matches_source(old_active, selected)
        ):
            # The restore endpoint has no request body/idempotency token.  A
            # repeated confirmation for the same just-created restore must
            # therefore return the existing projection instead of appending
            # another equivalent current version.
            return {"task": existing_restore, "version": old_active, "restored_from": selected}
        now = self._now()
        old_active.status = "recoverable"
        old_active.recoverable_until = now + timedelta(days=RECOVERY_DAYS)
        new_version = self._clone_as_active(selected, label=f"稿本 {len(record.versions) + 1} · 从历史恢复", source_version_id=selected.version_id)
        record.versions.append(new_version)
        record.active_version_id = new_version.version_id
        record.pending_changes = None
        for task in record.tasks:
            if task.version_id == old_active.version_id and task.status in {"queued", "running"}:
                task.status = "cancelled"
                task.error_message = "恢复历史稿本后，原稿本分析任务失效。"
                task.updated_at = now
        task = self._new_rebuild_task(record, new_version, kind="restore")
        record.tasks.append(task)
        record.change_history.append(f"{now.isoformat()}：从 {selected.label} 创建新的当前稿本。")
        self._notify(record, "version_created", f"已从 {selected.label} 创建新的当前稿本。")
        record.updated_at = now
        self._queue_deconstruction_event(record, reason="恢复历史稿本")
        self.store.save(record)
        self._request_deconstruction(project_id, account_id, reason="恢复历史稿本")
        return {"task": task, "version": new_version, "restored_from": selected}

    def trial_sketch(self, project_id: str, account_id: str, *, style: str, confirm: bool) -> dict[str, Any]:
        self._load(project_id, account_id)
        result = {
            "style": style,
            "estimated_credits": 12,
            "credits_charged": False,
            "image_status": "not_requested",
            "message": "选择画风并确认后才会触发试绘；不会自动为全员生成。",
        }
        if confirm:
            raise IndependentServiceError(
                "image_service_unconfigured",
                "未配置图片服务，试绘未触发，也未扣除积分。",
                status_code=503,
                data=result,
            )
        return result
