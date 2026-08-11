"""阶段 1 产品入口服务：账户关联作品、书架摘要和新建作品。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from app.core.account_store import AccountRecord, AccountStore, ProjectLink
from app.core.ai_store import AIStore
from app.core.independent_store import IndependentStore
from app.core.project_store import ProjectStore, project_store
from app.models import NovelProject
from schemas.ai import AIProjectRecord
from schemas.entry import ProjectMode, ProjectSummary
from schemas.independent import IndependentProjectRecord


class EntryService:
    _UTC = timezone.utc
    _FALLBACK_TIMESTAMP = datetime(1970, 1, 1, tzinfo=_UTC)

    def __init__(
        self,
        *,
        accounts: AccountStore,
        projects: ProjectStore = project_store,
        independent: IndependentStore | None = None,
        ai: AIStore | None = None,
    ) -> None:
        self.accounts = accounts
        self.projects = projects
        self.independent = independent or IndependentStore()
        self.ai = ai or AIStore()
        # AIService 注入 durable transaction coordinator 后，书架和通知这类
        # 旁路读也必须经过同一 marker/recovery 门禁，不能直接观察半投影。
        self.transaction_coordinator: Any | None = None

    def _load_sidecar_for_account(
        self,
        store: IndependentStore | AIStore,
        project_id: str,
        account_id: str | None,
        model_type: type[IndependentProjectRecord] | type[AIProjectRecord],
        *,
        kind: str,
    ) -> IndependentProjectRecord | AIProjectRecord | None:
        coordinator = self.transaction_coordinator
        if coordinator is not None and account_id:
            coordinator.reconcile_for_read(project_id, account_id)
        record = self._safe_load_sidecar(store, project_id, model_type)
        if coordinator is not None and account_id and record is not None:
            record = coordinator.overlay_record(
                record,
                project_id=project_id,
                account_id=account_id,
                kind=kind,
            )
        return record

    def sidecar_for_link(
        self,
        link: ProjectLink,
        account_id: str,
    ) -> AIProjectRecord | IndependentProjectRecord | None:
        if link.mode == "ai_assisted":
            return self._load_sidecar_for_account(
                self.ai,
                link.project_id,
                account_id,
                AIProjectRecord,
                kind="ai",
            )
        if link.mode == "independent":
            return self._load_sidecar_for_account(
                self.independent,
                link.project_id,
                account_id,
                IndependentProjectRecord,
                kind="manuscript",
            )
        return None

    @classmethod
    def _parse_timestamp(cls, value: object) -> datetime | None:
        if isinstance(value, datetime):
            candidate = value
        elif isinstance(value, str) and value.strip():
            try:
                candidate = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        try:
            if candidate.tzinfo is None:
                return candidate.replace(tzinfo=cls._UTC)
            return candidate.astimezone(cls._UTC)
        except (TypeError, ValueError, OverflowError):
            return None

    @classmethod
    def normalize_timestamp(
        cls,
        value: object,
        fallback: object | None = None,
    ) -> datetime:
        """将历史 naive/字符串时间仅在内存中解释为 aware UTC。"""

        return (
            cls._parse_timestamp(value)
            or cls._parse_timestamp(fallback)
            or cls._FALLBACK_TIMESTAMP
        )

    @classmethod
    def _normalize_raw_datetimes(cls, value: object) -> object:
        """为损坏时间做读取时兼容；不回写磁盘，其他数据保持原样。"""

        if isinstance(value, dict):
            normalized: dict[object, object] = {}
            for key, item in value.items():
                if isinstance(key, str) and (
                    key.endswith("_at") or key in {"recoverable_until"}
                ):
                    if item is None:
                        normalized[key] = None
                    else:
                        normalized[key] = cls.normalize_timestamp(item)
                else:
                    normalized[key] = cls._normalize_raw_datetimes(item)
            return normalized
        if isinstance(value, list):
            return [cls._normalize_raw_datetimes(item) for item in value]
        return value

    @classmethod
    def _recover_model_from_store(
        cls,
        store: object,
        project_id: str,
        model_type: type,
    ):
        path_builder = getattr(store, "_path", None) or getattr(store, "_project_path", None)
        if not callable(path_builder):
            return None
        try:
            raw_path = path_builder(project_id)
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None
            raw = cls._normalize_raw_datetimes(raw)
            created_at = cls.normalize_timestamp(raw.get("created_at"))
            raw["created_at"] = created_at
            raw["updated_at"] = cls.normalize_timestamp(raw.get("updated_at"), created_at)
            return model_type.model_validate(raw)
        except (OSError, TypeError, ValueError, KeyError):
            return None

    @classmethod
    def _safe_load_project(cls, store: ProjectStore, project_id: str) -> NovelProject | None:
        try:
            return store.load_project(project_id)
        except (TypeError, ValueError, KeyError):
            return cls._recover_model_from_store(store, project_id, NovelProject)

    @classmethod
    def _safe_load_sidecar(
        cls,
        store: IndependentStore | AIStore,
        project_id: str,
        model_type: type[IndependentProjectRecord] | type[AIProjectRecord],
    ) -> IndependentProjectRecord | AIProjectRecord | None:
        try:
            return store.load(project_id)
        except (TypeError, ValueError, KeyError):
            return cls._recover_model_from_store(store, project_id, model_type)

    @staticmethod
    def _target_chapter_count(project: NovelProject) -> int | None:
        if project.full_plan and project.full_plan.target_chapter_count:
            return project.full_plan.target_chapter_count
        if project.chapter_plans:
            return max(plan.chapter_number for plan in project.chapter_plans)
        return None

    @staticmethod
    def _status(project: NovelProject) -> str:
        if any(task.status == "failed" for task in project.batch_tasks):
            return "失败，可重试"
        if any(task.status in {"running", "pending"} for task in project.batch_tasks):
            return "处理中"
        return "已保存"

    def summary(
        self,
        project: NovelProject,
        link: ProjectLink,
        account_id: str | None = None,
    ) -> ProjectSummary:
        project_updated_at = self.normalize_timestamp(
            getattr(project, "updated_at", None),
            getattr(project, "created_at", None),
        )
        if link.mode == "independent":
            independent_record = self._load_sidecar_for_account(
                self.independent,
                project.project_id,
                account_id,
                IndependentProjectRecord,
                kind="manuscript",
            )
            if independent_record is not None and independent_record.active_version_id:
                active_version = next(
                    (
                        version
                        for version in independent_record.versions
                        if version.version_id == independent_record.active_version_id
                    ),
                    None,
                )
                if active_version is not None:
                    chapter_count = len(active_version.chapters)
                    completed_chapters = sum(
                        chapter.status == "ready" for chapter in active_version.chapters
                    )
                    progress = (
                        round(completed_chapters / chapter_count * 100)
                        if chapter_count
                        else 0
                    )
                    if any(task.status == "failed" for task in independent_record.tasks):
                        status = "失败，可重试"
                    elif any(task.status in {"queued", "running"} for task in independent_record.tasks):
                        status = "处理中"
                    else:
                        status = "已保存"
                    return ProjectSummary(
                        project_id=project.project_id,
                        title=independent_record.title or project.title,
                        mode=link.mode,
                        mode_label="独立创作",
                        chapter_count=chapter_count,
                        target_chapter_count=None,
                        total_word_count=sum(chapter.word_count for chapter in active_version.chapters),
                        progress_percent=min(100, max(0, progress)),
                        latest_edited_at=self.normalize_timestamp(
                            getattr(independent_record, "updated_at", None),
                            project_updated_at,
                        ),
                        status=status,
                        brief=project.project_brief,
                        credits_used=0,
                    )
        if link.mode == "ai_assisted":
            ai_record = self._load_sidecar_for_account(
                self.ai,
                project.project_id,
                account_id,
                AIProjectRecord,
                kind="ai",
            )
            independent_record = self._load_sidecar_for_account(
                self.independent,
                project.project_id,
                account_id,
                IndependentProjectRecord,
                kind="manuscript",
            )
            active_version = None
            if independent_record is not None and independent_record.active_version_id:
                active_version = next(
                    (version for version in independent_record.versions if version.version_id == independent_record.active_version_id),
                    None,
                )
            chapter_count = len(active_version.chapters) if active_version is not None else 0
            completed_chapters = sum(chapter.status == "ready" for chapter in active_version.chapters) if active_version is not None else 0
            if ai_record is None:
                status = "待进入创作室"
                updated_at = project_updated_at
                credits_used = 0
            else:
                latest_run = ai_record.runs[-1] if ai_record.runs else None
                if latest_run is not None and latest_run.status == "failed":
                    status = "失败，可重试"
                elif latest_run is not None and latest_run.status == "waiting_for_choice":
                    status = "等待关键选择"
                elif latest_run is not None and latest_run.status in {"queued", "character_simulation", "writing", "reviewing", "updating_archive", "paused"}:
                    status = "生成中"
                elif active_version is not None:
                    status = "已保存"
                else:
                    status = "蓝图待确认"
                updated_at = self.normalize_timestamp(
                    getattr(ai_record, "updated_at", None),
                    project_updated_at,
                )
                credits_used = ai_record.credits_used
            progress = round(completed_chapters / chapter_count * 100) if chapter_count else 0
            return ProjectSummary(
                project_id=project.project_id,
                title=project.title,
                mode=link.mode,
                mode_label="AI 辅助写作",
                chapter_count=chapter_count,
                target_chapter_count=None,
                total_word_count=sum(chapter.word_count for chapter in active_version.chapters) if active_version is not None else 0,
                progress_percent=min(100, max(0, progress)),
                latest_edited_at=updated_at,
                status=status,
                brief=project.project_brief,
                credits_used=credits_used,
            )
        target = self._target_chapter_count(project)
        completed_chapters = sum(
            chapter.status == "completed" for chapter in project.chapters
        )
        chapter_count = len(project.chapters)
        progress = round(completed_chapters / target * 100) if target else 0
        return ProjectSummary(
            project_id=project.project_id,
            title=project.title,
            mode=link.mode,
            mode_label="AI 辅助写作" if link.mode == "ai_assisted" else "独立创作",
            chapter_count=chapter_count,
            target_chapter_count=target,
            total_word_count=project.total_word_count,
            progress_percent=min(100, max(0, progress)),
            latest_edited_at=project_updated_at,
            status=self._status(project),
            brief=project.project_brief,
            credits_used=0,
        )

    def library(self, account: AccountRecord, query: str = "") -> list[ProjectSummary]:
        normalized_query = query.strip().lower()
        summaries: list[ProjectSummary] = []
        for link in account.project_links:
            # 旧 /novel 工作流的归属只供旧接口鉴权，不混入阶段 1+ 的书架合同。
            if link.mode == "legacy":
                continue
            project = self._safe_load_project(self.projects, link.project_id)
            if project is None:
                continue
            if normalized_query and not (
                normalized_query in project.title.lower()
                or normalized_query in (project.project_brief or "").lower()
            ):
                continue
            summaries.append(self.summary(project, link, account.account_id))
        return sorted(
            summaries,
            key=lambda item: (
                self.normalize_timestamp(item.latest_edited_at),
                item.project_id,
            ),
            reverse=True,
        )

    def create_project(
        self,
        *,
        account: AccountRecord,
        title: str,
        mode: ProjectMode,
        brief: str | None = None,
    ) -> ProjectSummary:
        now = datetime.now(timezone.utc)
        project = NovelProject(
            project_id=uuid4().hex,
            title=title,
            project_brief=brief,
            created_at=now,
            updated_at=now,
        )
        self.projects.save_project(project)
        link = self.accounts.link_project(account.account_id, project.project_id, mode)
        return self.summary(project, link, account.account_id)
