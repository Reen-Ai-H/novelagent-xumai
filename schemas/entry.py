"""阶段 1：产品入口、账户、书架和新建作品的数据合同。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ProjectMode = Literal["independent", "ai_assisted"]


class EmailLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(..., max_length=254, description="登录邮箱")


class AccountPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    email: str
    credit_balance: int = Field(default=0, ge=0)
    created_at: datetime


class AuthResponse(BaseModel):
    authenticated: bool = True
    account: AccountPublic
    next_path: str = "/library"
    session_expires_at: datetime


class SessionResponse(BaseModel):
    authenticated: bool = False
    account: AccountPublic | None = None
    reason: Literal["session_expired"] | None = None


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=120, description="作品标题")
    mode: ProjectMode = Field(..., description="独立创作或 AI 辅助写作")
    brief: str | None = Field(default=None, max_length=1000, description="作品简介")


class ProjectSummary(BaseModel):
    project_id: str
    title: str
    mode: ProjectMode
    mode_label: str
    chapter_count: int = Field(default=0, ge=0)
    target_chapter_count: int | None = Field(default=None, ge=1)
    total_word_count: int = Field(default=0, ge=0)
    progress_percent: int = Field(default=0, ge=0, le=100)
    latest_edited_at: datetime
    status: str
    brief: str | None = None
    credits_used: int = Field(default=0, ge=0)


class LibraryResponse(BaseModel):
    account: AccountPublic
    projects: list[ProjectSummary] = Field(default_factory=list)
    query: str = ""


class ProjectCreatedResponse(BaseModel):
    project: ProjectSummary
    next_path: str
    next_step_label: str
