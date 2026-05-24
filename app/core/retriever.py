"""RAG 检索入口：把工作流状态转换为长期记忆上下文。"""

from __future__ import annotations

from app.core.memory import MemoryStore, memory_store
from app.models import CharacterCard, MemoryItem, NovelState, RetrievalContext


def retrieve_context_for_state(
    state: NovelState,
    *,
    store: MemoryStore = memory_store,
    limit: int = 8,
) -> list[RetrievalContext]:
    """根据当前章节状态检索相关长期记忆。"""

    project_id = state.get("project_id") or "default"
    chapter_number = state.get("current_chapter_number")
    query = _build_query(state)
    return store.search(
        project_id=project_id,
        query=query,
        chapter_number=chapter_number,
        limit=limit,
    )


def format_retrieved_context(contexts: list[RetrievalContext]) -> str:
    """格式化检索结果，供 LLM prompt 注入。"""

    if not contexts:
        return "暂无检索到的长期记忆。"
    return "\n".join(
        f"{index}. {context.formatted_text}（相关度 {context.score:.2f}，{context.reason}）"
        for index, context in enumerate(contexts, start=1)
    )


def build_memory_items_from_state(state: NovelState) -> list[MemoryItem]:
    """把已接受章节的最终状态沉淀为长期记忆条目。"""

    project_id = state.get("project_id") or "default"
    session_id = state.get("session_id")
    chapter_number = state.get("current_chapter_number")
    draft = state.get("current_draft")
    items: list[MemoryItem] = []

    if draft and draft.content.strip():
        summary = _chapter_summary_from_state(state)
        items.append(
            MemoryItem(
                project_id=project_id,
                category="chapter_summary",
                title=draft.title or f"第 {draft.chapter_number} 章摘要",
                content=summary,
                chapter_number=draft.chapter_number,
                source="librarian",
                source_id=session_id,
                tags=_tags_from_state(state),
                importance=0.9,
            )
        )

    for key, value in state.get("extracted_lore_updates", {}).items():
        if not str(value).strip():
            continue
        items.append(
            MemoryItem(
                project_id=project_id,
                category=_category_from_lore_key(key),
                title=key,
                content=str(value),
                chapter_number=chapter_number,
                source="librarian",
                source_id=session_id,
                tags=_tags_from_text(key, str(value)),
                importance=0.75,
            )
        )

    for character in state.get("extracted_character_updates", {}).values():
        if not isinstance(character, CharacterCard):
            continue
        items.append(
            MemoryItem(
                project_id=project_id,
                category="character",
                title=character.name,
                content=character.model_dump_json(indent=2, exclude_none=True),
                chapter_number=chapter_number,
                source="librarian",
                source_id=character.name,
                tags=[character.name, *character.aliases, character.role],
                importance=0.85,
            )
        )

    return items


def _build_query(state: NovelState) -> str:
    parts: list[str] = [
        state.get("global_worldview", ""),
        state.get("human_feedback") or "",
    ]
    for beat in state.get("current_plot_beats", []):
        parts.extend(
            [
                beat.summary,
                beat.purpose or "",
                beat.location or "",
                beat.conflict or "",
                beat.expected_outcome or "",
                " ".join(beat.involved_characters),
                " ".join(beat.continuity_constraints),
            ]
        )
    for character in state.get("character_graph", {}).values():
        if isinstance(character, CharacterCard):
            parts.extend([character.name, *character.aliases, character.current_location or ""])
    draft = state.get("current_draft")
    if draft:
        parts.extend([draft.title or "", " ".join(draft.reviewer_comments)])
    return "\n".join(part for part in parts if part)


def _chapter_summary_from_state(state: NovelState) -> str:
    draft = state.get("current_draft")
    chapter_number = state.get("current_chapter_number")
    lore_updates = state.get("extracted_lore_updates", {})
    for key in (
        f"chapter_{chapter_number}_summary",
        f"chapter{chapter_number}_summary",
        "chapter_summary",
        "summary",
    ):
        value = lore_updates.get(key)
        if value:
            return value
    if not draft:
        return ""
    beat_summary = "；".join(beat.summary for beat in draft.plot_beats)
    compact_content = " ".join(draft.content.split())
    return beat_summary or compact_content[:320]


def _category_from_lore_key(key: str) -> str:
    lowered = key.lower()
    if "chapter" in lowered and "summary" in lowered:
        return "chapter_summary"
    if lowered.startswith(("character_", "role_", "person_")):
        return "character"
    if lowered.startswith(("location_", "place_", "city_", "room_")):
        return "location"
    if lowered.startswith(("item_", "prop_", "weapon_", "artifact_")):
        return "item"
    if lowered.startswith(("foreshadow", "clue_", "伏笔")):
        return "foreshadowing"
    if lowered.startswith(("plot_", "event_")):
        return "plot"
    return "world_lore"


def _tags_from_state(state: NovelState) -> list[str]:
    tags: list[str] = []
    for beat in state.get("current_plot_beats", []):
        tags.extend(beat.involved_characters)
        if beat.location:
            tags.append(beat.location)
    return list(dict.fromkeys(tag for tag in tags if tag))


def _tags_from_text(*values: str) -> list[str]:
    tags: list[str] = []
    for value in values:
        for token in value.replace("_", " ").replace("-", " ").split():
            cleaned = token.strip("：:，,。.；;[]()（）")
            if len(cleaned) >= 2:
                tags.append(cleaned[:24])
    return list(dict.fromkeys(tags))[:8]
