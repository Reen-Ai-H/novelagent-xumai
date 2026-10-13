"""Source reading units over unchanged detail events, never an inferred plot."""
from __future__ import annotations

import re
from schemas.deconstruction import DepthReadingSegment, depth_stable_id


_TIME = re.compile(r"(?:[零一二三四五六七八九十百\d]+(?:岁|年|月|天|日)(?:时|后|前|起)|"
                   r"翌日|次日|第二天|那天|那晚|当晚|前世|今生|与此同时|后来|转眼|几年后|几日后)")
_PLACE = re.compile(r"(?:回到|来到|赶到|离开|走进|进入)[^。！？\n]{1,24}(?:城|宫|院|港|楼|馆|山|镇|村|站|门)")


def reading_segments(source, chapters, events, identity_profiles, evidence_builder):
    selected = [p for p in identity_profiles if p.importance != "incidental"]
    result = []
    total = sum(len(c.content.encode("utf-16-le")) // 2 for c in chapters)
    consumed = 0
    for chapter in chapters:
        paragraphs = [p for p in re.finditer(r"[^\n]+", chapter.content) if p.group().strip()]
        if not paragraphs:
            consumed += len(chapter.content.encode("utf-16-le")) // 2
            continue
        boundaries = [(0, "chapter")]
        active_people: set[str] = set()
        for index, paragraph in enumerate(paragraphs):
            text = paragraph.group().strip()
            people = {p.name for p in selected if any(s in text for s in (p.name, *p.aliases))}
            dialogue = text.startswith(('“', '「', '"', '‘'))
            transition = not dialogue and bool(_TIME.search(text[:32]) or _PLACE.search(text[:48]))
            blank_break = index and bool(re.search(r"\n\s*\n", chapter.content[paragraphs[index-1].end():paragraph.start()]))
            changed_people = not dialogue and people and active_people and not people & active_people
            if index and (transition or blank_break or changed_people):
                boundaries.append((index, "transition" if transition else "paragraph"))
                active_people = set()
            active_people |= people
        for slot, (first, basis) in enumerate(boundaries):
            last = boundaries[slot + 1][0] if slot + 1 < len(boundaries) else len(paragraphs)
            start = 0 if first == 0 else paragraphs[first].start()
            end = paragraphs[last].start() if last < len(paragraphs) else len(chapter.content)
            included = [e for e in events if e.chapter.chapter_id == chapter.chapter_id and start <= e.start < end]
            raw = paragraphs[first].group()
            quote_start = paragraphs[first].start() + len(raw) - len(raw.lstrip())
            sentence = re.match(r"[^。！？!?\n]+[。！？!?]?", raw.lstrip())
            quote = (sentence.group() if sentence else raw.strip())[:150]
            evidence_id = evidence_builder.span(chapter, quote_start, quote_start + len(quote), "阅读段落摘要")
            offset_start = len(chapter.content[:start].encode("utf-16-le")) // 2
            offset_end = len(chapter.content[:end].encode("utf-16-le")) // 2
            names = list(dict.fromkeys(name for event in included for name in event.names))
            title = re.split(r"[，,。！？!?；;：:]", quote, maxsplit=1)[0][:36] or quote[:36]
            result.append(DepthReadingSegment(
                segment_id=depth_stable_id(source, "reading", f"{chapter.chapter_id}:{start}:{end}"),
                title=title, summary=quote, chapter_id=chapter.chapter_id, chapter_number=chapter.chapter_number,
                start_offset=offset_start, end_offset=offset_end,
                paragraph_start=first + 1, paragraph_end=last,
                normalized_start=round((consumed + offset_start) / total * 100, 6),
                normalized_end=round((consumed + offset_end) / total * 100, 6),
                character_ids=[depth_stable_id(source, "character", f"name:{name}") for name in names],
                event_ids=[e.event_id for e in included], evidence_ids=[evidence_id], grouping_basis=basis,
                uncertainty=["按来源段落和可见转场组织；摘要为原文摘取，尚未证明完整情境或语义主线。"],
            ))
        consumed += len(chapter.content.encode("utf-16-le")) // 2
    return result
