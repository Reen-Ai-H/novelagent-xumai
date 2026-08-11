"""AI 创作室状态的本地持久化侧车。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from schemas.ai import AIProjectRecord


AI_DATA_DIR = Path(__file__).resolve().parents[2] / ".novel_ai"
PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class AIStore:
    """按作品原子写入 JSON，避免把 AI 状态塞进旧作品结构。"""

    def __init__(self, base_dir: Path = AI_DATA_DIR) -> None:
        self.base_dir = base_dir
        self._lock = RLock()

    def _path(self, project_id: str) -> Path:
        normalized = project_id.strip()
        if not normalized or not PROJECT_ID_PATTERN.fullmatch(normalized):
            raise ValueError("project_id 只允许字母、数字、下划线和连字符")
        return self.base_dir / f"{normalized}.json"

    def load(self, project_id: str) -> AIProjectRecord | None:
        path = self._path(project_id)
        with self._lock:
            if not path.exists():
                return None
            return AIProjectRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def save(self, record: AIProjectRecord) -> AIProjectRecord:
        path = self._path(record.project_id)
        with self._lock:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.base_dir,
                delete=False,
            ) as temp:
                json.dump(record.model_dump(mode="json"), temp, ensure_ascii=False, indent=2)
                temp.write("\n")
                temp_path = Path(temp.name)
            temp_path.replace(path)
            return record

    def list_records(self) -> list[AIProjectRecord]:
        """读取全部 AI 侧车记录，供服务端 worker 恢复未终态任务。"""

        if not self.base_dir.exists():
            return []
        records: list[AIProjectRecord] = []
        with self._lock:
            for path in sorted(self.base_dir.glob("*.json")):
                records.append(AIProjectRecord.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        return records
