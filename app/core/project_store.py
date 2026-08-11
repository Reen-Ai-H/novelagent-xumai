"""作品目录本地持久化接口与 JSON 实现。"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.models import NovelProject


PROJECTS_DIR = Path(__file__).resolve().parents[2] / ".novel_projects"
PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class ProjectStore(ABC):
    """作品目录存储抽象，后续可替换为数据库或云端实现。"""

    @abstractmethod
    def save_project(self, project: NovelProject) -> NovelProject:
        """保存作品目录，并返回已保存的项目。"""

    @abstractmethod
    def load_project(self, project_id: str) -> NovelProject | None:
        """按作品 ID 读取目录；不存在时返回 None。"""

    @abstractmethod
    def list_projects(self) -> list[NovelProject]:
        """列出本地已保存的全部作品目录。"""

    @abstractmethod
    def delete_project(self, project_id: str) -> bool:
        """删除作品目录；成功删除返回 True。"""


class JsonProjectStore(ProjectStore):
    """基于本地 JSON 文件的作品目录存储。"""

    _UTC = timezone.utc
    _FALLBACK_TIMESTAMP = datetime(1970, 1, 1, tzinfo=_UTC)

    def __init__(self, base_dir: Path = PROJECTS_DIR) -> None:
        self.base_dir = base_dir

    def save_project(self, project: NovelProject) -> NovelProject:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self._project_path(project.project_id)
        payload = project.model_dump(mode="json")
        payload["created_at"] = self._normalize_timestamp(
            project.created_at,
        ).isoformat()
        payload["updated_at"] = self._normalize_timestamp(
            project.updated_at,
            project.created_at,
        ).isoformat()

        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.base_dir,
            delete=False,
        ) as tmp:
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
            tmp_path = Path(tmp.name)
        tmp_path.replace(path)
        return project

    def load_project(self, project_id: str) -> NovelProject | None:
        path = self._project_path(project_id)
        if not path.exists():
            return None

        raw_project = self._read_raw_project(path)
        return NovelProject.model_validate(self._normalize_project_timestamps(raw_project))

    def list_projects(self) -> list[NovelProject]:
        if not self.base_dir.exists():
            return []

        projects: list[NovelProject] = []
        for path in sorted(self.base_dir.glob("*.json")):
            raw_project = self._read_raw_project(path)
            projects.append(
                NovelProject.model_validate(self._normalize_project_timestamps(raw_project))
            )
        return sorted(
            projects,
            key=lambda project: (
                self._normalize_timestamp(project.updated_at),
                project.project_id,
            ),
            reverse=True,
        )

    def delete_project(self, project_id: str) -> bool:
        path = self._project_path(project_id)
        if not path.exists():
            return False

        path.unlink()
        return True

    def _project_path(self, project_id: str) -> Path:
        normalized_project_id = project_id.strip()
        if not normalized_project_id:
            raise ValueError("project_id must not be empty")
        if not PROJECT_ID_PATTERN.fullmatch(normalized_project_id):
            raise ValueError("project_id may only contain letters, numbers, underscores, and hyphens")
        return self.base_dir / f"{normalized_project_id}.json"

    @staticmethod
    def _read_raw_project(path: Path) -> dict[str, object]:
        raw_project = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw_project, dict):
            raise ValueError(f"project JSON must be an object: {path.name}")
        return raw_project

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
    def _normalize_timestamp(
        cls,
        value: object,
        fallback: object | None = None,
    ) -> datetime:
        return (
            cls._parse_timestamp(value)
            or cls._parse_timestamp(fallback)
            or cls._FALLBACK_TIMESTAMP
        )

    @classmethod
    def _normalize_timestamp_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            normalized: dict[object, object] = {}
            for key, item in value.items():
                if isinstance(key, str) and key.endswith("_at"):
                    normalized[key] = cls._normalize_timestamp(item)
                else:
                    normalized[key] = cls._normalize_timestamp_fields(item)
            return normalized
        if isinstance(value, list):
            return [cls._normalize_timestamp_fields(item) for item in value]
        return value

    @classmethod
    def _normalize_project_timestamps(cls, raw_project: dict[str, object]) -> dict[str, object]:
        normalized = cls._normalize_timestamp_fields(raw_project)
        if not isinstance(normalized, dict):
            raise ValueError("project JSON must be an object")
        created_at = cls._normalize_timestamp(raw_project.get("created_at"))
        normalized["created_at"] = created_at
        normalized["updated_at"] = cls._normalize_timestamp(
            raw_project.get("updated_at"),
            created_at,
        )
        return normalized


project_store = JsonProjectStore()
