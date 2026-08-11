"""独立创作侧车数据存储。

阶段 1 的旧作品目录继续由 ``JsonProjectStore`` 管理。本存储只承载阶段 2
新增的正文、档案、任务和稿本版本，避免为了新增能力重写既有用户数据。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from schemas.independent import IndependentProjectRecord


INDEPENDENT_DATA_DIR = Path(__file__).resolve().parents[2] / ".novel_independent"
PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class IndependentStore:
    """以作品为粒度原子写入的本地 JSON 存储。"""

    def __init__(self, base_dir: Path = INDEPENDENT_DATA_DIR) -> None:
        self.base_dir = base_dir
        self._lock = RLock()

    def _path(self, project_id: str) -> Path:
        normalized = project_id.strip()
        if not normalized or not PROJECT_ID_PATTERN.fullmatch(normalized):
            raise ValueError("project_id 只允许字母、数字、下划线和连字符")
        return self.base_dir / f"{normalized}.json"

    def load(self, project_id: str) -> IndependentProjectRecord | None:
        path = self._path(project_id)
        with self._lock:
            if not path.exists():
                return None
            raw = json.loads(path.read_text(encoding="utf-8"))
            return IndependentProjectRecord.model_validate(raw)

    def save(self, project: IndependentProjectRecord) -> IndependentProjectRecord:
        path = self._path(project.project_id)
        with self._lock:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.base_dir,
                delete=False,
            ) as temp:
                json.dump(project.model_dump(mode="json"), temp, ensure_ascii=False, indent=2)
                temp.write("\n")
                temp_path = Path(temp.name)
            temp_path.replace(path)
            return project
