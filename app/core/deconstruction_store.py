"""作品拆解侧车存储。

拆解是对独立稿本的可版本化派生数据，单独按作品原子写入，避免为了加入
拆解能力而重写已有 ``.novel_independent`` 用户数据。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from pydantic import ValidationError

from app.core.project_lock import ProjectLockError, ProjectLockStore
from schemas.deconstruction import DeconstructionProjectRecord


DECONSTRUCTION_DATA_DIR = Path(__file__).resolve().parents[2] / ".novel_deconstruction"
PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class DeconstructionStoreError(Exception):
    """单个拆解侧车不可读取/写入时的安全内部错误。"""


class DeconstructionStoreConflict(DeconstructionStoreError):
    """The sidecar changed after a caller took its CAS snapshot."""


class DeconstructionStore:
    """按作品保存拆解运行；写入使用临时文件替换，读取不回写正文数据。"""

    def __init__(self, base_dir: Path = DECONSTRUCTION_DATA_DIR) -> None:
        self.base_dir = base_dir
        self._lock = RLock()
        self.project_locks = ProjectLockStore(self.base_dir.parent / ".novel_transactions")

    def _path(self, project_id: str) -> Path:
        normalized = project_id.strip()
        if not normalized or not PROJECT_ID_PATTERN.fullmatch(normalized):
            raise ValueError("project_id 只允许字母、数字、下划线和连字符")
        return self.base_dir / f"{normalized}.json"

    def load(self, project_id: str) -> DeconstructionProjectRecord | None:
        path = self._path(project_id)
        with self._lock:
            return self._load_unlocked(path)

    @staticmethod
    def _load_unlocked(path: Path) -> DeconstructionProjectRecord | None:
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return DeconstructionProjectRecord.model_validate(raw)
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
            raise DeconstructionStoreError("拆解侧车暂时不可读取。") from exc

    def _atomic_write(self, path: Path, record: DeconstructionProjectRecord) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.base_dir,
                delete=False,
            ) as temp:
                json.dump(record.model_dump(mode="json"), temp, ensure_ascii=False, indent=2)
                temp.write("\n")
                temp.flush()
                os.fsync(temp.fileno())
                temporary = Path(temp.name)
            assert temporary is not None
            temporary.replace(path)
            try:
                directory = os.open(self.base_dir, os.O_RDONLY)
            except OSError:
                directory = None
            if directory is not None:
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            if temporary is not None and temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass

    def save(self, record: DeconstructionProjectRecord) -> DeconstructionProjectRecord:
        path = self._path(record.project_id)
        try:
            with self.project_locks.project_lock(record.project_id):
                with self._lock:
                    current = self._load_unlocked(path)
                    expected = record.record_revision
                    actual = 0 if current is None else current.record_revision
                    if actual != expected:
                        raise DeconstructionStoreConflict("拆解侧车已被另一项操作更新，请重试。")
                    return self._save_if_revision_unlocked(path, record, expected)
        except ProjectLockError as exc:
            raise DeconstructionStoreError("拆解侧车项目锁暂时不可用。") from exc

    def save_if_revision(
        self,
        record: DeconstructionProjectRecord,
        expected_revision: int,
    ) -> DeconstructionProjectRecord:
        """Atomically commit a sidecar mutation if its CAS revision is current."""

        if expected_revision < 0 or record.record_revision != expected_revision:
            raise DeconstructionStoreConflict("拆解侧车版本冲突，请重新读取后重试。")
        path = self._path(record.project_id)
        try:
            with self.project_locks.project_lock(record.project_id):
                with self._lock:
                    current = self._load_unlocked(path)
                    if current is None:
                        actual = 0
                    else:
                        actual = current.record_revision
                    if actual != expected_revision:
                        raise DeconstructionStoreConflict("拆解侧车版本冲突，请重新读取后重试。")
                    return self._save_if_revision_unlocked(path, record, expected_revision)
        except ProjectLockError as exc:
            raise DeconstructionStoreError("拆解侧车项目锁暂时不可用。") from exc

    def _save_if_revision_unlocked(
        self,
        path: Path,
        record: DeconstructionProjectRecord,
        expected_revision: int,
    ) -> DeconstructionProjectRecord:
        try:
            validated = DeconstructionProjectRecord.model_validate(record.model_dump(mode="json"))
        except (TypeError, ValueError, ValidationError) as exc:
            raise DeconstructionStoreError("拆解侧车数据校验失败。") from exc
        committed = validated.model_copy(update={"record_revision": expected_revision + 1})
        committed = DeconstructionProjectRecord.model_validate(committed.model_dump(mode="json"))
        self._atomic_write(path, committed)
        # Keep callers that hold a freshly loaded model in sync with the
        # durable CAS value.  This is internal metadata and is never projected.
        record.record_revision = committed.record_revision
        return committed

    def list_records(self) -> list[DeconstructionProjectRecord]:
        """返回全部侧车记录，供启动/后台 worker 找回未完成拆解。"""

        if not self.base_dir.exists():
            return []
        records: list[DeconstructionProjectRecord] = []
        with self._lock:
            for path in sorted(self.base_dir.glob("*.json")):
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    records.append(DeconstructionProjectRecord.model_validate(raw))
                except (OSError, UnicodeError, json.JSONDecodeError, ValidationError):
                    # 单个侧车损坏不能阻断其他作品；公开读取由 service 将该项目
                    # 视为暂不可用，避免把损坏文件静默当作新任务覆盖。
                    continue
        return records
