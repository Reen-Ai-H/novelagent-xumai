"""跨服务、跨进程的独立作品事务锁。"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


if os.name == "nt":
    import msvcrt
else:  # pragma: no cover - exercised by the Linux CI job
    import fcntl


PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class ProjectLockError(OSError):
    """The shared lock could not be acquired safely."""


class _HeldLock:
    def __init__(self) -> None:
        self.mutex = threading.RLock()
        self.owner: int | None = None
        self.owner_pid: int | None = None
        self.depth = 0
        self.descriptor: int | None = None


class ProjectLockStore:
    """Advisory OS locks with same-process reentrancy and bounded waits."""

    _registry_guard = threading.Lock()
    _registry: dict[str, _HeldLock] = {}

    @classmethod
    def _after_fork_child(cls) -> None:
        """Drop inherited registry state without waiting on a copied mutex."""

        # A fork child may inherit a registry guard held by a thread that no
        # longer exists.  Do not acquire it here.  Closing the child's copies
        # of descriptors does not release the parent's open-file lock.
        inherited = list(cls._registry.values())
        for entry in inherited:
            descriptor = entry.descriptor
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        cls._registry_guard = threading.Lock()
        cls._registry = {}

    def __init__(self, base_dir: Path, *, legacy_names: bool = False) -> None:
        self.base_dir = Path(base_dir)
        self.legacy_names = legacy_names

    @staticmethod
    def _validate_id(project_id: str) -> str:
        normalized = project_id.strip()
        if not normalized or not PROJECT_ID_PATTERN.fullmatch(normalized):
            raise ValueError("project_id 只允许字母、数字、下划线和连字符")
        return normalized

    def _path(self, project_id: str) -> Path:
        normalized = self._validate_id(project_id)
        if self.legacy_names:
            filename = f".{normalized}.write.lock"
        else:
            filename = f".project-{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:32]}.lock"
        return self.base_dir / filename

    @classmethod
    def _entry(cls, path: Path) -> _HeldLock:
        key = str(path.resolve())
        with cls._registry_guard:
            entry = cls._registry.get(key)
            if entry is None:
                entry = _HeldLock()
                cls._registry[key] = entry
            return entry

    @staticmethod
    def _remaining(deadline: float | None) -> float | None:
        if deadline is None:
            return None
        return max(0.0, deadline - time.monotonic())

    def _acquire_os(self, descriptor: int, deadline: float | None) -> None:
        if os.name == "nt":
            os.ftruncate(descriptor, 1)
            while True:
                os.lseek(descriptor, 0, os.SEEK_SET)
                try:
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                    return
                except OSError:
                    remaining = self._remaining(deadline)
                    if remaining is not None and remaining <= 0:
                        raise ProjectLockError("项目事务锁暂时不可用，请稍后重试。") from None
                    time.sleep(min(0.02, remaining if remaining is not None else 0.02))
        else:
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return
                except OSError:
                    remaining = self._remaining(deadline)
                    if remaining is not None and remaining <= 0:
                        raise ProjectLockError("项目事务锁暂时不可用，请稍后重试。") from None
                    time.sleep(min(0.02, remaining if remaining is not None else 0.02))

    @staticmethod
    def _release_os(descriptor: int) -> None:
        if os.name == "nt":
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(descriptor, fcntl.LOCK_UN)

    @contextmanager
    def project_lock(self, project_id: str, *, timeout: float | None = 5.0) -> Iterator[None]:
        path = self._path(project_id)
        deadline = None if timeout is None else time.monotonic() + max(0.0, timeout)
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            entry = self._entry(path)
            if timeout is None:
                acquired_thread = entry.mutex.acquire()
            else:
                remaining = self._remaining(deadline)
                acquired_thread = entry.mutex.acquire(timeout=max(0.0, remaining or 0.0))
            if not acquired_thread:
                raise ProjectLockError("项目事务锁暂时不可用，请稍后重试。")
        except ProjectLockError:
            raise
        except (OSError, ValueError) as exc:
            raise ProjectLockError("项目事务锁暂时不可用，请稍后重试。") from exc

        current_thread = threading.get_ident()
        current_pid = os.getpid()
        try:
            if entry.owner == current_thread and entry.owner_pid == current_pid:
                entry.depth += 1
                yield
                return

            descriptor: int | None = None
            try:
                descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
                self._acquire_os(descriptor, deadline)
            except ProjectLockError:
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
                raise
            except (OSError, ValueError) as exc:
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
                raise ProjectLockError("项目事务锁暂时不可用，请稍后重试。") from exc
            entry.owner = current_thread
            entry.owner_pid = current_pid
            entry.depth = 1
            entry.descriptor = descriptor
            yield
        finally:
            release_error: ProjectLockError | None = None
            try:
                if entry.owner == current_thread and entry.owner_pid == current_pid:
                    entry.depth -= 1
                    if entry.depth == 0:
                        descriptor = entry.descriptor
                        entry.descriptor = None
                        entry.owner = None
                        entry.owner_pid = None
                        if descriptor is not None:
                            try:
                                self._release_os(descriptor)
                            except Exception as exc:
                                release_error = ProjectLockError("项目事务锁释放失败。")
                                release_error.__cause__ = exc
                            finally:
                                try:
                                    os.close(descriptor)
                                except Exception as exc:
                                    if release_error is None:
                                        release_error = ProjectLockError("项目事务锁文件关闭失败。")
                                        release_error.__cause__ = exc
            finally:
                # The in-process mutex must be released even when the OS unlock
                # or descriptor close fails; otherwise every later writer in
                # this process can deadlock forever.
                entry.mutex.release()
            if release_error is not None and sys.exc_info()[0] is None:
                raise release_error


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=ProjectLockStore._after_fork_child)


__all__ = ["ProjectLockError", "ProjectLockStore"]
