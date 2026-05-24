"""可替换的长期记忆存储接口与本地 JSON 实现。"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable

from app.models import MemoryItem, RetrievalContext


MEMORY_DIR = Path(__file__).resolve().parents[2] / ".novel_memory"


class MemoryStore(ABC):
    """长期记忆存储抽象，后续可替换为向量库实现。"""

    @abstractmethod
    def add_items(self, project_id: str, items: Iterable[MemoryItem]) -> list[MemoryItem]:
        """写入记忆条目，并返回实际新增的条目。"""

    @abstractmethod
    def list_items(self, project_id: str) -> list[MemoryItem]:
        """列出项目下全部记忆。"""

    @abstractmethod
    def search(
        self,
        *,
        project_id: str,
        query: str,
        chapter_number: int | None = None,
        limit: int = 8,
    ) -> list[RetrievalContext]:
        """检索与 query 最相关的记忆条目。"""


class JsonMemoryStore(MemoryStore):
    """本地 JSON 记忆库，适合原型阶段和离线演示。"""

    def __init__(self, base_dir: Path = MEMORY_DIR) -> None:
        self.base_dir = base_dir

    def add_items(self, project_id: str, items: Iterable[MemoryItem]) -> list[MemoryItem]:
        normalized_items = [
            item.model_copy(update={"project_id": project_id})
            for item in items
            if item.content.strip()
        ]
        if not normalized_items:
            return []

        existing = self.list_items(project_id)
        existing_keys = {_dedupe_key(item) for item in existing}
        added: list[MemoryItem] = []
        for item in normalized_items:
            key = _dedupe_key(item)
            if key in existing_keys:
                continue
            existing.append(item)
            existing_keys.add(key)
            added.append(item)

        if added:
            self._write_items(project_id, existing)
        return added

    def list_items(self, project_id: str) -> list[MemoryItem]:
        path = self._project_path(project_id)
        if not path.exists():
            return []

        try:
            raw_items = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        return [
            MemoryItem.model_validate(raw_item)
            for raw_item in raw_items
            if isinstance(raw_item, dict)
        ]

    def search(
        self,
        *,
        project_id: str,
        query: str,
        chapter_number: int | None = None,
        limit: int = 8,
    ) -> list[RetrievalContext]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        contexts: list[RetrievalContext] = []
        for item in self.list_items(project_id):
            item_text = " ".join([item.title, item.content, " ".join(item.tags)])
            item_tokens = _tokenize(item_text)
            overlap = query_tokens & item_tokens
            if not overlap:
                continue

            score = _score_item(
                item=item,
                overlap_count=len(overlap),
                query_size=len(query_tokens),
                chapter_number=chapter_number,
            )
            contexts.append(
                RetrievalContext(
                    item=item,
                    score=score,
                    reason=f"命中关键词：{', '.join(sorted(overlap)[:6])}",
                    formatted_text=_format_item(item),
                )
            )

        return sorted(contexts, key=lambda context: context.score, reverse=True)[:limit]

    def _project_path(self, project_id: str) -> Path:
        safe_project_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", project_id or "default")
        return self.base_dir / f"{safe_project_id}.json"

    def _write_items(self, project_id: str, items: list[MemoryItem]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self._project_path(project_id)
        payload = [
            item.model_dump(mode="json", exclude_none=True)
            for item in sorted(
                items,
                key=lambda memory: (
                    memory.chapter_number or 0,
                    memory.category,
                    memory.title,
                ),
            )
        ]
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.base_dir,
            delete=False,
        ) as tmp:
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp_path = Path(tmp.name)
        tmp_path.replace(path)


def _tokenize(text: str) -> set[str]:
    """兼容中文与英文的轻量分词，避免引入额外依赖。"""

    lowered = (text or "").lower()
    latin_tokens = set(re.findall(r"[a-z0-9_]{2,}", lowered))
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", lowered)
    cjk_bigrams = {
        "".join(cjk_chars[index : index + 2])
        for index in range(max(len(cjk_chars) - 1, 0))
    }
    return latin_tokens | cjk_bigrams


def _score_item(
    *,
    item: MemoryItem,
    overlap_count: int,
    query_size: int,
    chapter_number: int | None,
) -> float:
    base_score = overlap_count / max(query_size, 1)
    importance_bonus = item.importance * 0.25
    category_bonus = 0.1 if item.category in {"chapter_summary", "foreshadowing"} else 0.0
    recency_bonus = 0.0
    if chapter_number and item.chapter_number:
        distance = abs(chapter_number - item.chapter_number)
        recency_bonus = max(0.0, 0.2 - distance * 0.03)
    return round(base_score + importance_bonus + category_bonus + recency_bonus, 4)


def _format_item(item: MemoryItem) -> str:
    chapter = f"第 {item.chapter_number} 章" if item.chapter_number else "全局"
    tags = f"；标签：{', '.join(item.tags)}" if item.tags else ""
    return f"[{chapter}｜{item.category}｜{item.title}] {item.content}{tags}"


def _dedupe_key(item: MemoryItem) -> tuple[str, str, int | None, str, str]:
    return (
        item.project_id,
        item.category,
        item.chapter_number,
        item.title.strip().lower(),
        item.content.strip(),
    )


memory_store = JsonMemoryStore()
