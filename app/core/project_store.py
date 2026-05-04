"""作品目录本地持久化接口与 JSON 实现。"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
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

    def __init__(self, base_dir: Path = PROJECTS_DIR) -> None:
        self.base_dir = base_dir

    def save_project(self, project: NovelProject) -> NovelProject:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self._project_path(project.project_id)
        payload = project.model_dump(mode="json")

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

        raw_project = json.loads(path.read_text(encoding="utf-8"))
        return NovelProject.model_validate(raw_project)

    def list_projects(self) -> list[NovelProject]:
        if not self.base_dir.exists():
            return []

        projects: list[NovelProject] = []
        for path in sorted(self.base_dir.glob("*.json")):
            raw_project = json.loads(path.read_text(encoding="utf-8"))
            projects.append(NovelProject.model_validate(raw_project))
        return projects

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


project_store = JsonProjectStore()
