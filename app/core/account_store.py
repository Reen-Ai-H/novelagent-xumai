"""本地开发账户与会话持久化。

账户文件只保存邮箱、账户元数据、作品归属和会话 token 的哈希，不把会话放进
浏览器本地存储。生产环境可在不改变路由合同的情况下替换为数据库实现。
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from schemas.entry import AccountPublic


ACCOUNT_DATA_DIR = Path(__file__).resolve().parents[2] / ".novel_accounts"
ACCOUNT_DATA_PATH = ACCOUNT_DATA_DIR / "accounts.json"
SESSION_COOKIE_NAME = "xumai_session"
SESSION_TTL = timedelta(days=30)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ProjectLinkMode = Literal["independent", "ai_assisted", "legacy"]


class ProjectLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    mode: ProjectLinkMode
    created_at: datetime


class AccountRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    email: str
    credit_balance: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
    project_links: list[ProjectLink] = Field(default_factory=list)

    def public(self) -> AccountPublic:
        return AccountPublic(
            account_id=self.account_id,
            email=self.email,
            credit_balance=self.credit_balance,
            created_at=self.created_at,
        )


class SessionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime


class AccountStore:
    """账户和会话的原子 JSON 存储。"""

    def __init__(self, path: Path = ACCOUNT_DATA_PATH) -> None:
        self.path = path
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def normalize_email(email: str) -> str:
        normalized = email.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("请输入有效的邮箱地址")
        return normalized

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _empty_payload(self) -> dict[str, dict[str, dict]]:
        return {"accounts": {}, "sessions": {}}

    def _read(self) -> dict[str, dict[str, dict]]:
        if not self.path.exists():
            return self._empty_payload()

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return {
            "accounts": dict(raw.get("accounts", {})),
            "sessions": dict(raw.get("sessions", {})),
        }

    def _write(self, payload: dict[str, dict[str, dict]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.path.parent,
            delete=False,
        ) as tmp:
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
            temp_path = Path(tmp.name)
        temp_path.replace(self.path)

    def _load_account(self, payload: dict[str, dict[str, dict]], account_id: str) -> AccountRecord:
        raw = payload["accounts"].get(account_id)
        if raw is None:
            raise KeyError(f"未找到账户: {account_id}")
        return AccountRecord.model_validate(raw)

    def login(self, email: str) -> tuple[AccountRecord, str, datetime]:
        """创建或恢复账户，并返回一次性明文会话 token。"""

        normalized_email = self.normalize_email(email)
        now = self._now()
        expires_at = now + SESSION_TTL
        token = secrets.token_urlsafe(32)

        with self._lock:
            payload = self._read()
            account = next(
                (
                    AccountRecord.model_validate(raw)
                    for raw in payload["accounts"].values()
                    if str(raw.get("email", "")).lower() == normalized_email
                ),
                None,
            )
            if account is None:
                account = AccountRecord(
                    account_id=uuid4().hex,
                    email=normalized_email,
                    created_at=now,
                    updated_at=now,
                )
            else:
                account.updated_at = now

            payload["accounts"][account.account_id] = account.model_dump(mode="json")
            payload["sessions"][self._hash_token(token)] = SessionRecord(
                account_id=account.account_id,
                created_at=now,
                expires_at=expires_at,
                last_seen_at=now,
            ).model_dump(mode="json")
            self._write(payload)

        return account, token, expires_at

    def account_for_token(self, token: str | None) -> AccountRecord | None:
        if not token:
            return None

        now = self._now()
        token_hash = self._hash_token(token)
        with self._lock:
            payload = self._read()
            raw_session = payload["sessions"].get(token_hash)
            if raw_session is None:
                return None

            session = SessionRecord.model_validate(raw_session)
            if session.expires_at <= now:
                payload["sessions"].pop(token_hash, None)
                self._write(payload)
                return None

            session.last_seen_at = now
            payload["sessions"][token_hash] = session.model_dump(mode="json")
            self._write(payload)
            return self._load_account(payload, session.account_id)

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            payload = self._read()
            payload["sessions"].pop(self._hash_token(token), None)
            self._write(payload)

    def link_project(self, account_id: str, project_id: str, mode: ProjectLinkMode) -> ProjectLink:
        now = self._now()
        with self._lock:
            payload = self._read()
            account = self._load_account(payload, account_id)
            existing = next(
                (link for link in account.project_links if link.project_id == project_id),
                None,
            )
            if existing is not None:
                if existing.mode != mode:
                    raise ValueError("作品创作模式创建后不可暗中切换")
                return existing

            link = ProjectLink(project_id=project_id, mode=mode, created_at=now)
            account.project_links.append(link)
            account.updated_at = now
            payload["accounts"][account_id] = account.model_dump(mode="json")
            self._write(payload)
            return link

    def account(self, account_id: str) -> AccountRecord:
        with self._lock:
            return self._load_account(self._read(), account_id)
