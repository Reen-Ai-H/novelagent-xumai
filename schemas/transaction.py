"""导演跨存储事务的内部持久合同。

这些模型只用于服务端恢复，不由任何 API 直接返回。payload 是通过正文、审校
和公开档案校验后的业务投影；它不承载 prompt、原始 completion、密钥或人物
私有记忆。模型调用账本仍由 AI sidecar 独立保存。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


TransactionState = Literal["prepared", "committed", "completed", "aborted", "superseded"]
TransactionPhase = Literal[
    "prepared",
    "manuscript_staged",
    "archive_staged",
    "ai_staged",
    "notification_staged",
    "commit_marker",
    "projecting",
    "author_compensating",
    "author_conflict",
    "completed",
    "aborted",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TransactionJournal(BaseModel):
    """不含业务正文的协调记录；payload 单独存放并只含最终业务投影。"""

    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    project_id: str
    account_id: str
    run_id: str
    version_id: str
    chapter_number: int = Field(..., ge=1)
    idempotency_key: str
    content_hash: str
    expected_ai_run_revision: int = Field(..., ge=0)
    expected_manuscript_revision: int = Field(..., ge=0)
    payload_hash: str
    state: TransactionState = "prepared"
    phase: TransactionPhase = "prepared"
    manuscript_projected: bool = False
    ai_projected: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    commit_marker_at: datetime | None = None
    error_code: str | None = None
    conflict_revision: int | None = Field(default=None, ge=0)
    compensation_attempts: int = Field(default=0, ge=0)


class TransactionPayload(BaseModel):
    """经安全校验后的单章投影。

    ``ai_run.generated_content`` 与 ``chapter.content`` 是正式稿本业务数据，
    不是原始供应商响应；这里绝不保存 prompt、HTTP header、私密记忆或内部
    提示。字段保持显式，避免把完整 AI sidecar 当作恢复快照复制出去。
    """

    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    project_id: str
    account_id: str
    run_id: str
    version_id: str
    chapter_number: int = Field(..., ge=1)
    idempotency_key: str
    content_hash: str
    ai_run: dict[str, Any]
    professional_roles: list[dict[str, Any]] = Field(default_factory=list)
    character_updates: list[dict[str, str]] = Field(default_factory=list)
    chapter: dict[str, Any]
    archive: dict[str, Any]
    task: dict[str, Any]
    notification: dict[str, Any]
    credit_entry: dict[str, Any] | None = None
    # 作者优先补偿所需的安全业务基线；不含 prompt、原始模型响应或人物私有记忆。
    baseline_archive: dict[str, Any] | None = None
    baseline_professional_roles: list[dict[str, Any]] = Field(default_factory=list)
    baseline_character_states: list[dict[str, str]] = Field(default_factory=list)
