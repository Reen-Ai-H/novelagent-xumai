"""跨 AI sidecar 与独立稿本 sidecar 的持久协调器。

JSON 文件没有跨文件 ACID，因此导演提交先写 staging payload 和 journal，
再写 durable commit marker，最后幂等投影到两个 store。marker 前正式读路径
不会把 staging 当作正文；marker 后 journal payload 是一致性来源，读路径先
尝试补齐投影，失败时以内存 overlay 返回完整新状态，避免暴露半成品。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Any, Callable

from schemas.transaction import TransactionJournal, TransactionPayload


if os.name == "nt":
    import msvcrt
else:
    import fcntl


TRANSACTION_DATA_DIR = Path(__file__).resolve().parents[2] / ".novel_transactions"
PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class TransactionError(Exception):
    """协调失败；``committed`` 表示 marker 已经持久化。"""

    def __init__(self, transaction_id: str, message: str, *, committed: bool) -> None:
        super().__init__(message)
        self.transaction_id = transaction_id
        self.committed = committed


class TransactionNotCommitted(TransactionError):
    pass


class TransactionCommitted(TransactionError):
    pass


ApplyCallback = Callable[[TransactionPayload, bool], Any]
OverlayCallback = Callable[[Any, TransactionPayload], Any]
InspectCallback = Callable[[TransactionPayload, TransactionJournal], str]
CompensateCallback = Callable[[TransactionPayload, TransactionJournal], Any]
ConflictOverlayCallback = Callable[[Any, TransactionPayload, str], Any]


class TransactionStore:
    """journal 与 staging payload 的安全原子文件存储。"""

    def __init__(self, base_dir: Path = TRANSACTION_DATA_DIR) -> None:
        self.base_dir = base_dir
        self._lock = RLock()

    @staticmethod
    def _validate_id(value: str) -> str:
        normalized = value.strip()
        if not normalized or not PROJECT_ID_PATTERN.fullmatch(normalized):
            raise ValueError("transaction_id 只允许字母、数字、下划线和连字符")
        return normalized

    def _journal_path(self, transaction_id: str) -> Path:
        return self.base_dir / f"{self._validate_id(transaction_id)}.journal.json"

    def _payload_path(self, transaction_id: str) -> Path:
        return self.base_dir / f"{self._validate_id(transaction_id)}.payload.json"

    def _project_lock_path(self, project_id: str) -> Path:
        return self.base_dir / f".{self._validate_id(project_id)}.write.lock"

    @contextmanager
    def project_lock(self, project_id: str):
        """跨进程项目写锁；锁文件故障释放，不依赖进程内 asyncio/RLock。"""

        self.base_dir.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self._project_lock_path(project_id), os.O_CREAT | os.O_RDWR, 0o600)
        acquired = False
        try:
            if os.name == "nt":
                # msvcrt.locking 锁定当前文件指针起始的一个字节；固定文件长度
                # 后再加锁，避免空锁文件在 Windows 上无法建立区域锁。
                os.ftruncate(descriptor, 1)
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
            else:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            acquired = True
            yield
        finally:
            if acquired:
                if os.name == "nt":
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        try:
            descriptor = os.open(path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _atomic_write(self, path: Path, payload: dict[str, Any]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=self.base_dir, delete=False) as temp:
            json.dump(payload, temp, ensure_ascii=False, indent=2, sort_keys=True)
            temp.write("\n")
            temp.flush()
            os.fsync(temp.fileno())
            temporary = Path(temp.name)
        temporary.replace(path)
        self._fsync_directory(self.base_dir)

    def save_payload(self, payload: TransactionPayload) -> None:
        with self._lock:
            self._atomic_write(self._payload_path(payload.transaction_id), payload.model_dump(mode="json"))

    def save_journal(self, journal: TransactionJournal) -> None:
        with self._lock:
            self._atomic_write(self._journal_path(journal.transaction_id), journal.model_dump(mode="json"))

    def load_payload(self, transaction_id: str) -> TransactionPayload | None:
        path = self._payload_path(transaction_id)
        with self._lock:
            if not path.exists():
                return None
            return TransactionPayload.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def load_journal(self, transaction_id: str) -> TransactionJournal | None:
        path = self._journal_path(transaction_id)
        with self._lock:
            if not path.exists():
                return None
            return TransactionJournal.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def list_journals(self) -> list[TransactionJournal]:
        if not self.base_dir.exists():
            return []
        journals: list[TransactionJournal] = []
        with self._lock:
            for path in sorted(self.base_dir.glob("*.journal.json")):
                journals.append(TransactionJournal.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        return journals


class CrossStoreTransactionCoordinator:
    """两 store 的 durable 状态机与公开读 overlay。"""

    def __init__(
        self,
        *,
        store: TransactionStore | None = None,
        apply_ai: ApplyCallback,
        apply_manuscript: ApplyCallback,
        overlay_ai: OverlayCallback,
        overlay_manuscript: OverlayCallback,
        inspect_manuscript: InspectCallback | None = None,
        compensate_manuscript: CompensateCallback | None = None,
        compensate_ai: CompensateCallback | None = None,
        overlay_author_conflict: ConflictOverlayCallback | None = None,
    ) -> None:
        self.store = store or TransactionStore()
        self.apply_ai = apply_ai
        self.apply_manuscript = apply_manuscript
        self.overlay_ai = overlay_ai
        self.overlay_manuscript = overlay_manuscript
        self.inspect_manuscript = inspect_manuscript
        self.compensate_manuscript = compensate_manuscript
        self.compensate_ai = compensate_ai
        self.overlay_author_conflict = overlay_author_conflict
        # 只用于隔离测试和故障注入；正确性不依赖内存锁。
        self.failure_hook: Callable[[str], None] | None = None

    def _inject(self, label: str) -> None:
        hook = self.failure_hook
        if hook is not None:
            hook(label)

    @staticmethod
    def _ordered(journals: list[TransactionJournal]) -> list[TransactionJournal]:
        """按作品/章节/创建时间恢复，避免文件名哈希决定连续章节顺序。"""

        return sorted(
            journals,
            key=lambda item: (
                item.project_id,
                item.chapter_number,
                item.created_at,
                item.transaction_id,
            ),
        )

    @staticmethod
    def _payload_hash(payload: TransactionPayload) -> str:
        encoded = json.dumps(payload.model_dump(mode="json"), ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def find_for_run(
        self,
        *,
        project_id: str,
        run_id: str,
        content_hash: str,
    ) -> TransactionJournal | None:
        candidates = [
            item
            for item in self._ordered(self.store.list_journals())
            if item.project_id == project_id
            and item.run_id == run_id
            and item.content_hash == content_hash
            and item.state in {"prepared", "committed", "completed"}
        ]
        return max(candidates, key=lambda item: item.updated_at, default=None)

    def prepare(self, *, payload: TransactionPayload, expected_ai_run_revision: int, expected_manuscript_revision: int) -> TransactionJournal:
        existing = self.find_for_run(
            project_id=payload.project_id,
            run_id=payload.run_id,
            content_hash=payload.content_hash,
        )
        if existing is not None:
            return existing
        self._inject("journal_prepare_before")
        self.store.save_payload(payload)
        journal = TransactionJournal(
            transaction_id=payload.transaction_id,
            project_id=payload.project_id,
            account_id=payload.account_id,
            run_id=payload.run_id,
            version_id=payload.version_id,
            chapter_number=payload.chapter_number,
            idempotency_key=payload.idempotency_key,
            content_hash=payload.content_hash,
            expected_ai_run_revision=expected_ai_run_revision,
            expected_manuscript_revision=expected_manuscript_revision,
            payload_hash=self._payload_hash(payload),
        )
        self.store.save_journal(journal)
        self._inject("journal_prepared")
        return journal

    def _update(self, journal: TransactionJournal, **updates: Any) -> TransactionJournal:
        next_journal = journal.model_copy(update={**updates, "updated_at": datetime.now(timezone.utc)})
        self.store.save_journal(next_journal)
        return next_journal

    def abort(self, transaction_id: str, *, error_code: str = "not_committed") -> None:
        journal = self.store.load_journal(transaction_id)
        if journal is None or journal.state != "prepared":
            return
        try:
            self._update(journal, state="aborted", phase="aborted", error_code=error_code)
        except OSError:
            # 仅在原状态已经没有 marker 时尽力记录；公开读仍把 prepared 视为旧状态。
            return

    def _prepare_commit_marker(self, journal: TransactionJournal) -> TransactionJournal:
        phases = (
            "manuscript_staged",
            "archive_staged",
            "ai_staged",
            "notification_staged",
        )
        for phase in phases:
            self._inject(phase)
            journal = self._update(journal, phase=phase)  # type: ignore[arg-type]
        self._inject("commit_marker_before")
        journal = self._update(
            journal,
            state="committed",
            phase="commit_marker",
            commit_marker_at=datetime.now(timezone.utc),
        )
        self._inject("commit_marker_after")
        return journal

    def _inspect_author_revision(self, payload: TransactionPayload, journal: TransactionJournal) -> str:
        if self.inspect_manuscript is None:
            return "unknown"
        return self.inspect_manuscript(payload, journal)

    def _compensate_author_conflict(
        self,
        journal: TransactionJournal,
        payload: TransactionPayload,
        *,
        revision: int | None = None,
    ) -> TransactionJournal:
        """把 marker 后作者 revision 漂移收敛为持久作者优先终态。"""

        attempts = journal.compensation_attempts + 1
        try:
            journal = self._update(
                journal,
                state="committed",
                phase="author_compensating",
                error_code="author_revision_conflict",
                conflict_revision=revision,
                compensation_attempts=attempts,
            )
            if self.compensate_manuscript is None or self.compensate_ai is None:
                raise TransactionCommitted(
                    journal.transaction_id,
                    "作者 revision 冲突，等待安全补偿。",
                    committed=True,
                )
            # 先恢复稿本/档案，再收敛 AI run；每个 callback 必须以稳定业务键幂等。
            self.compensate_manuscript(payload, journal)
            self.compensate_ai(payload, journal)
            return self._update(
                journal,
                state="superseded",
                phase="author_conflict",
                error_code="author_revision_conflict",
                manuscript_projected=False,
                ai_projected=False,
            )
        except (KeyboardInterrupt, SystemExit):
            raise
        except TransactionCommitted:
            raise
        except Exception as exc:
            # 补偿本身可在任一 store 故障后重入；不要把作者状态回滚成旧值，保留
            # marker journal 供下一次启动/worker/读入口继续完成。
            try:
                latest = self.store.load_journal(journal.transaction_id) or journal
                self._update(
                    latest,
                    state="committed",
                    phase="author_compensating",
                    error_code="author_revision_conflict",
                    conflict_revision=revision,
                    compensation_attempts=max(attempts, latest.compensation_attempts),
                )
            except Exception:
                pass
            raise TransactionCommitted(
                journal.transaction_id,
                "作者 revision 冲突，后台将继续安全补偿。",
                committed=True,
            ) from exc

    def _reconcile_project_locked(self, project_id: str, account_id: str | None = None) -> int:
        count = 0
        for journal in self._ordered(self.store.list_journals()):
            if journal.project_id != project_id or (account_id is not None and journal.account_id != account_id):
                continue
            if journal.state != "committed":
                continue
            try:
                self._inject("recovery_again")
                self._commit_unlocked(journal.transaction_id)
                count += 1
            except (KeyboardInterrupt, SystemExit):
                raise
            except TransactionError:
                continue
        return count

    @contextmanager
    def author_write_lock(self, project_id: str, account_id: str):
        """作者写入前完成同作品未终结事务，或明确拒绝写入。"""

        with self.store.project_lock(project_id):
            self._reconcile_project_locked(project_id, account_id)
            unresolved = [
                item
                for item in self.store.list_journals()
                if item.project_id == project_id
                and item.account_id == account_id
                and item.state == "committed"
            ]
            if unresolved:
                raise TransactionCommitted(
                    unresolved[0].transaction_id,
                    "后台事务尚未安全收敛，请稍后重试作者修改。",
                    committed=True,
                )
            yield

    def commit(self, transaction_id: str) -> TransactionJournal:
        """对外提交入口；同作品作者写入不能穿过本次 marker/投影。"""

        journal = self.store.load_journal(transaction_id)
        if journal is None:
            return self._commit_unlocked(transaction_id)
        with self.store.project_lock(journal.project_id):
            return self._commit_unlocked(transaction_id)

    def _commit_unlocked(self, transaction_id: str) -> TransactionJournal:
        journal = self.store.load_journal(transaction_id)
        payload = self.store.load_payload(transaction_id)
        if journal is None or payload is None:
            raise TransactionNotCommitted(transaction_id, "事务材料缺失，正式稿本没有提交。", committed=False)
        if self._payload_hash(payload) != journal.payload_hash:
            raise TransactionNotCommitted(transaction_id, "事务材料校验失败，正式稿本没有提交。", committed=False)
        if journal.state == "aborted":
            raise TransactionNotCommitted(transaction_id, "事务已安全放弃，可重试。", committed=False)
        if journal.state == "superseded":
            return journal
        if journal.state == "completed":
            # completed 是 durable terminal marker，但旧版本/故障恢复可能只
            # 把 AI sidecar 标成完成而漏掉稿本投影。只有确认作者 revision
            # 没有漂移时才补齐这一类旧记录；一旦作者后来写过目标章节，重复
            # commit 只保留作者状态，绝不把旧 AI payload 写回正文。
            inspection = self._inspect_author_revision(payload, journal)
            if inspection.startswith("conflict"):
                return journal
            self.apply_manuscript(payload, True)
            self.apply_ai(payload, True)
            return journal
        if journal.state == "prepared":
            try:
                journal = self._prepare_commit_marker(journal)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as exc:
                self.abort(transaction_id, error_code="commit_marker_not_written")
                raise TransactionNotCommitted(transaction_id, "提交 marker 尚未写入，正式状态保持不变。", committed=False) from exc
        try:
            journal = self._update(journal, phase="projecting")
            inspection = self._inspect_author_revision(payload, journal)
            if inspection.startswith("conflict"):
                revision = None
                if ":" in inspection:
                    try:
                        revision = int(inspection.split(":", 1)[1])
                    except ValueError:
                        revision = None
                return self._compensate_author_conflict(journal, payload, revision=revision)
            if not journal.manuscript_projected:
                self.apply_manuscript(payload, True)
                journal = self._update(journal, manuscript_projected=True)
                self._inject("after_manuscript_projection")
                self._inject("after_archive_projection")
                inspection = self._inspect_author_revision(payload, journal)
                if inspection.startswith("conflict"):
                    return self._compensate_author_conflict(journal, payload)
                self._inject("projection_partial")
            if not journal.ai_projected:
                inspection = self._inspect_author_revision(payload, journal)
                if inspection.startswith("conflict"):
                    return self._compensate_author_conflict(journal, payload)
                self.apply_ai(payload, True)
                journal = self._update(journal, ai_projected=True)
                self._inject("after_ai_projection")
                inspection = self._inspect_author_revision(payload, journal)
                if inspection.startswith("conflict"):
                    return self._compensate_author_conflict(journal, payload)
                self._inject("after_notification_projection")
                inspection = self._inspect_author_revision(payload, journal)
                if inspection.startswith("conflict"):
                    return self._compensate_author_conflict(journal, payload)
            journal = self._update(journal, state="completed", phase="completed")
            return journal
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            # marker 已经持久化：后续读/worker 会从 payload 幂等补齐；不能把 run
            # 改写成 failed，也不能删除 payload 伪造回滚。
            raise TransactionCommitted(transaction_id, "提交 marker 已存在，后台将继续恢复完整状态。", committed=True) from exc

    def reconcile_for_read(self, project_id: str, account_id: str | None = None) -> None:
        with self.store.project_lock(project_id):
            self._reconcile_project_locked(project_id, account_id)

    def reconcile_all(self) -> int:
        count = 0
        project_ids = sorted({item.project_id for item in self.store.list_journals()})
        for project_id in project_ids:
            with self.store.project_lock(project_id):
                count += self._reconcile_project_locked(project_id)
        return count

    def overlay_record(self, record: Any, *, project_id: str, account_id: str, kind: str) -> Any:
        if record is None:
            return None
        current = record
        for journal in self._ordered(self.store.list_journals()):
            if (
                journal.project_id != project_id
                or journal.account_id != account_id
                or journal.state != "committed"
            ):
                continue
            payload = self.store.load_payload(journal.transaction_id)
            if payload is None:
                continue
            conflict = journal.error_code == "author_revision_conflict" or journal.phase == "author_compensating"
            if not conflict:
                try:
                    conflict = self._inspect_author_revision(payload, journal).startswith("conflict")
                except Exception:
                    # 公开读不能因恢复探测失败而暴露跨 store 异常；保守使用冲突视图。
                    conflict = True
            if conflict and self.overlay_author_conflict is not None:
                try:
                    current = self.overlay_author_conflict(current, payload, kind)
                except Exception:
                    # active version 已被作者切换或补偿材料暂时不可读时，保留
                    # 作者当前 store 作为公开旧状态；下一次 durable recovery
                    # 仍会重试，不能把内部 IndependentServiceError 传到页面。
                    current = current
            else:
                try:
                    current = self.overlay_ai(current, payload) if kind == "ai" else self.overlay_manuscript(current, payload)
                except Exception:
                    # 旧 payload/历史稿本不满足新投影前置条件时，reader 只返回
                    # 当前完整 store；不把跨 store 例外变成 500。
                    current = current
        return current
