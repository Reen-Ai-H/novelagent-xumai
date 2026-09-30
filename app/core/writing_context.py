"""Bounded, source-grounded professional context and explainable writing checks.

This module never reads character private memory or writes manuscript data.
Excerpts stay excerpts: compression is not presented as an inferred plot fact.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import re
from typing import Any

from schemas.ai import AIMessage, WritingCheck
from schemas.independent import ManuscriptVersion


CONTEXT_CHARACTER_BUDGET = 14000
CONVERSATION_CHARACTER_BUDGET = 8000


def recent_conversation(messages: list[AIMessage]) -> list[dict[str, str]]:
    """Newest turns receive capacity first; include only author/editor content."""
    remaining = CONVERSATION_CHARACTER_BUDGET
    selected = []
    for message in reversed(messages[-12:]):
        text = message.content.strip()
        if not remaining:
            break
        excerpt = _head_tail(text, min(2000, remaining))
        selected.append({"role": message.role, "content": excerpt})
        remaining -= len(excerpt)
    return list(reversed(selected))


def source_token(version: ManuscriptVersion | None) -> str:
    """All chapters and revisions participate, including uncompleted drafts."""
    data = {"version_id": version.version_id if version else None, "chapters": []}
    if version:
        data["chapters"] = [
            [chapter.chapter_id, chapter.chapter_number, chapter.server_revision,
             chapter.title, hashlib.sha256(chapter.content.encode()).hexdigest(),
             hashlib.sha256(chapter.formal_content.encode()).hexdigest()]
            for chapter in sorted(version.chapters, key=lambda item: item.chapter_number)
        ]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _head_tail(text: str, budget: int) -> str:
    if len(text) <= budget or budget < 40:
        return text[:budget]
    half = (budget - 14) // 2
    return text[:half] + "\n[…中间正文省略…]\n" + text[-half:]


def build_story_context(version: ManuscriptVersion | None, chapter_number: int, query: str = "") -> dict[str, Any]:
    """Select latest scene, bounded chapter excerpts and sourced archive entries.

    Only formal previous chapters enter model material. Drafts and future
    chapters participate in the source gate but are never fictional evidence.
    """
    chapters = sorted(
        (chapter for chapter in version.chapters
         if chapter.chapter_number < chapter_number and chapter.formal_content.strip()),
        key=lambda item: item.chapter_number,
    ) if version else []
    recent = chapters[-6:]
    older = chapters[:-6]
    # Lexical retrieval is deliberately labeled as such, not semantic truth.
    terms = set(re.findall(r"[A-Za-z0-9_]{3,}", query.lower()))
    for segment in re.findall(r"[\u4e00-\u9fff]+", query):
        terms.update(segment[i:i + 3] for i in range(max(0, len(segment) - 2)))
    terms = sorted(terms)[:80]
    ranked = sorted(older, key=lambda chapter: (
        sum(term in chapter.formal_content.lower() for term in terms), chapter.chapter_number,
    ), reverse=True)
    relevant = [chapter for chapter in ranked[:2] if any(term in chapter.formal_content.lower() for term in terms)]
    selected = {chapter.chapter_id: chapter for chapter in [*(chapters[:1] if older else []), *relevant, *recent]}
    excerpt_chapters = sorted(selected.values(), key=lambda chapter: chapter.chapter_number)
    context: dict[str, Any] = {
        "chapter_number": chapter_number,
        "source_version_id": version.version_id if version else None,
        "previous_chapter_count": len(chapters),
        "previous_scene": chapters[-1].formal_content[-2400:] if chapters else "",
        "chapter_excerpts": [
            {"chapter_number": chapter.chapter_number, "title": chapter.formal_title or chapter.title,
             "excerpt": _head_tail(chapter.formal_content, 700)}
            for chapter in excerpt_chapters
        ],
        "archive_entries": [],
        "omitted_chapter_count": max(0, len(chapters) - len(excerpt_chapters)),
        "limitations": "摘录有省略；档案是派生记录；疑问与伏笔不是已发生事实。正文是事实依据，缺少依据时保持未知。",
    }
    if version:
        archive = version.archive
        for category, entries, text_key in (
            ("character", archive.characters, "profile"),
            ("plotline", archive.storylines, "summary"),
            ("foreshadowing", archive.foreshadowing, "text"),
            ("question", archive.questions, "text"),
        ):
            for entry in sorted(entries, key=lambda item: item.source_chapter_number, reverse=True)[:8]:
                if entry.source_chapter_number >= chapter_number:
                    continue
                context["archive_entries"].append({
                    "category": category,
                    "source_chapter": entry.source_chapter_number,
                    "text": getattr(entry, text_key)[:180],
                })
    # Serialized size is the actual contract, rather than a sum that ignores
    # field names, escaped characters and arbitrary author titles.
    for excerpt in context["chapter_excerpts"]:
        excerpt["title"] = excerpt["title"][:100]
    while len(json.dumps(context, ensure_ascii=False)) > CONTEXT_CHARACTER_BUDGET:
        if context["archive_entries"]:
            context["archive_entries"].pop()
        elif context["chapter_excerpts"]:
            context["chapter_excerpts"].pop(0)
            context["omitted_chapter_count"] += 1
        else:
            context["previous_scene"] = context["previous_scene"][-1200:]
            break
    return context


def writing_checks(content: str, previous_content: str = "") -> list[WritingCheck]:
    """Flag exact sizable repetition. Intentional refrains remain author choices."""
    paragraphs = [re.sub(r"\s+", "", item) for item in content.splitlines() if item.strip()]
    counts = Counter(item for item in paragraphs if len(item) >= 40)
    checks = []
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    if repeated:
        checks.append(WritingCheck(
            kind="repeated_paragraph",
            message=f"本章有 {repeated} 处较长段落逐字重复。可以回看是否为有意复沓。",
        ))
    previous = re.sub(r"\s+", "", previous_content)
    overlap = sum(1 for paragraph in counts if paragraph in previous) if previous else 0
    if overlap:
        checks.append(WritingCheck(
            kind="previous_chapter_overlap",
            message=f"本章有 {overlap} 个较长段落与前章逐字相同。可以确认是必要回顾，还是需要推进新事件。",
        ))
    return checks
