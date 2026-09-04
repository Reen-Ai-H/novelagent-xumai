"""作品拆解侧车存储。

拆解是对独立稿本的可版本化派生数据，单独按作品原子写入，避免为了加入
拆解能力而重写已有 ``.novel_independent`` 用户数据。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from schemas.deconstruction import DeconstructionProjectRecord


DECONSTRUCTION_DATA_DIR = Path(__file__).resolve().parents[2] / ".novel_deconstruction"
PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class DeconstructionStore:
    """按作品保存拆解运行；写入使用临时文件替换，读取不回写正文数据。"""

    def __init__(self, base_dir: Path = DECONSTRUCTION_DATA_DIR) -> None:
        self.base_dir = base_dir
        self._lock = RLock()

    def _path(self, project_id: str) -> Path:
        normalized = project_id.strip()
        if not normalized or not PROJECT_ID_PATTERN.fullmatch(normalized):
            raise ValueError("project_id 只允许字母、数字、下划线和连字符")
        return self.base_dir / f"{normalized}.json"

    def load(self, project_id: str) -> DeconstructionProjectRecord | None:
        path = self._path(project_id)
        with self._lock:
            if not path.exists():
                return None
            raw = json.loads(path.read_text(encoding="utf-8"))
            return DeconstructionProjectRecord.model_validate(raw)

    def save(self, record: DeconstructionProjectRecord) -> DeconstructionProjectRecord:
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

    def list_records(self) -> list[DeconstructionProjectRecord]:
        """返回全部侧车记录，供启动/后台 worker 找回未完成拆解。"""

        if not self.base_dir.exists():
            return []
        records: list[DeconstructionProjectRecord] = []
        with self._lock:
            for path in sorted(self.base_dir.glob("*.json")):
                raw = json.loads(path.read_text(encoding="utf-8"))
                records.append(DeconstructionProjectRecord.model_validate(raw))
        return records
