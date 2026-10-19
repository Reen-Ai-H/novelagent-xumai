"""Lossless formal-chapter proposals; every proposal remains author-reviewable.

Legacy imports keep their original contract. This module supplies the explicit
preview/correct/confirm workflow without discarding heading or wrapper text.
"""
from __future__ import annotations

from bisect import bisect_right
import re

from app.core.chapter_outline import _ACTION_CLAUSE, _SCENERY, _UTTERANCE
from app.core.chapter_parser import parse_document, recognize_heading, scan_code_fence, utf16_length


_ENUMERATED_LABEL = re.compile(r"^(?:[0-9０-９]{1,4}|[一二两三四五六七八九十百]{1,5})[、.．]\s*")


def partition_text(text: str, boundaries: list[dict]) -> tuple[list[dict], list[str]]:
    """Validate author metadata, then derive all content exclusively from text."""
    if not text.strip() or not boundaries or len(boundaries) > 5000:
        raise ValueError("原文和章节切点不能为空。")
    raw = text.encode("utf-16-le")
    total = len(raw) // 2
    starts = [b["start"] for b in boundaries]
    if (starts[0] != 0 or any(type(s) is not int or not 0 <= s < total for s in starts)
            or any(a >= b for a, b in zip(starts, starts[1:]))):
        raise ValueError("章节须从原文起点开始，切点严格递增且不越界。")
    chunks, items = [], []
    for index, (boundary, end) in enumerate(zip(boundaries, starts[1:] + [total]), 1):
        start, title = boundary["start"], boundary["title"]
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise ValueError("每章需要不超过200字的标题。")
        try:
            content = raw[start * 2:end * 2].decode("utf-16-le")
        except UnicodeDecodeError:
            raise ValueError("切点不能拆开Unicode字符。") from None
        if start and raw[start * 2 - 2:start * 2 + 2] == b"\r\x00\n\x00":
            raise ValueError("切点不能拆开CRLF换行。")
        if not content.strip():
            raise ValueError("章节不能只包含空白，请合并相邻片段。")
        chunks.append(content)
        items.append(dict(chapter_number=index, title=title, start=start, end=end,
                          char_count=end-start, word_count=len(re.sub(r"\s+", "", content)),
                          confidence=boundary.get("confidence", "manual"),
                          reason=boundary.get("reason", "作者确认的章节切点")))
    return items, chunks


def _bare_title(value: str) -> str | None:
    # Typography is evidence, not a title dictionary. Numbered short labels
    # still need the same narrative/peer checks as unnumbered short headings.
    label = _ENUMERATED_LABEL.sub("", value)
    if (not re.fullmatch(r"[\u4e00-\u9fff]{2,12}", label)
            or _UTTERANCE.search(label) or _SCENERY.search(label) or _ACTION_CLAUSE.search(label)):
        return None
    return value


def _number_gap_inferences(rows: list[dict], anchors: list[dict], candidates: list[dict],
                           heading_levels: dict[int, int]) -> list[dict]:
    """A single missing number can support one otherwise unpaired bare title.

    Only adjacent formal chapters at the same declared level qualify. Require
    exactly one candidate and 200 non-whitespace narrative characters on EACH
    side, excluding code/dialogue. Any intervening structural heading breaks
    the inference (volumes, TOCs and nested sections are not missing chapters).
    """
    starts = [c["start"] for c in candidates]
    row_starts = [r["start"] for r in rows]
    inferred = []
    for left, right in zip(anchors, anchors[1:]):
        before, after = recognize_heading(left["value"]), recognize_heading(right["value"])
        if (before is None or after is None or before.kind != "chapter" or after.kind != "chapter"
                or before.number is None or after.number != before.number + 2
                or heading_levels.get(left["position"], before.level)
                != heading_levels.get(right["position"], after.level)):
            continue
        choices = candidates[bisect_right(starts, left["start"]):bisect_right(starts, right["start"])]
        if len(choices) != 1:
            continue
        candidate = choices[0]
        between = rows[bisect_right(row_starts, left["start"]):bisect_right(row_starts, right["start"])-1]
        narrative = [r for r in between if r["value"] and not r["blocked"]]
        if any(recognize_heading(r["value"]) or r["position"] in heading_levels for r in narrative):
            continue
        counts = [sum(len(re.sub(r"\s+", "", r["value"])) for r in narrative if r["start"] < candidate["start"]),
                  sum(len(re.sub(r"\s+", "", r["value"])) for r in narrative if r["start"] > candidate["start"])]
        if min(counts) >= 200:
            inferred.append(dict(candidate, reason="相邻正式章编号恰缺一章，唯一短标题两侧均有充分正文；请核对"))
    return inferred


def suggest_boundaries(text: str, title: str, *, heading_levels: dict[int, int] | None = None,
                       preserve_opening: bool = False) -> list[dict]:
    """Use declared chapter hierarchy and repeated isolated narrative headings.

    heading_levels uses code-point offsets, as supplied by the DOCX decoder.
    Returned offsets use UTF-16. Bare singletons need a supported number gap;
    short dialogue, lists, TOCs and code are never enough to establish a layer.
    """
    parsed = parse_document(title, text, heading_levels=heading_levels)
    lines = text.splitlines(keepends=True)
    rows, position, units, fence, quotes = [], 0, 0, None, []
    pairs = {"“": "”", "「": "」", "『": "』", "‘": "’"}
    for line in lines:
        fence, code = scan_code_fence(line, fence)
        quoted = bool(quotes)
        if not code:
            for i, char in enumerate(line):
                if quotes and char == quotes[-1]:
                    quotes.pop()
                elif char in pairs:
                    quotes.append(pairs[char])
                elif char == '"' and (not i or line[i-1] != "\\"):
                    quotes.append(char)
        rows.append(dict(position=position, start=units, value=line.strip(), blocked=code or quoted))
        position += len(line)
        units += utf16_length(line)
    by_position = {row["position"]: row for row in rows}
    explicit, anchors = [], []
    for chapter in parsed.chapters:
        row = by_position.get(chapter.heading_start)
        if row is not None and not row["blocked"]:
            anchors.append(row)
            explicit.append(dict(start=row["start"], title=chapter.title,
                                 confidence="explicit", reason="原文编号或声明的章节标题层级"))
    occupied = [row for row in rows if row["value"]]
    # Only the narrative ranges recognized by the structural parser may
    # provide inferred peers. This excludes book/volume wrappers and TOCs.
    spans = [(c.source_start, c.source_end) for c in parsed.chapters]
    first_heading = next((c.heading_start for c in parsed.chapters if c.heading_start is not None), None)
    if first_heading:
        prefix = [r for r in rows if r["position"] < first_heading and r["value"]]
        # A plain-title chapter may precede the first numbered heading in a
        # mixed-format source. Do not extend across a declared wrapper/TOC.
        if prefix and not any(recognize_heading(r["value"]) for r in prefix):
            spans.insert(0, (0, first_heading))
    span_starts = [a for a, _ in spans]
    candidates = []
    for index, row in enumerate(occupied):
        value = row["value"]
        slot = bisect_right(span_starts, row["position"]) - 1
        in_narrative = slot >= 0 and row["position"] < spans[slot][1]
        if (not in_narrative or row["blocked"] or recognize_heading(value)
                or row["position"] in (heading_levels or {}) or not _bare_title(value)):
            continue
        # An enumerated body label below an established chapter is a lower
        # layer, not a peer merely because its explanation is long. Explicit
        # sibling headings above and root-level numbered bare titles remain
        # supported; do not let body lists supply peers or fill number gaps.
        if anchors and row["position"] > anchors[0]["position"] and _ENUMERATED_LABEL.match(value):
            continue
        following = occupied[index+1:index+4]
        previous = occupied[index-1] if index else None
        if (not following or following[0]["blocked"] or _bare_title(following[0]["value"])
                or recognize_heading(following[0]["value"])):
            continue
        if previous and (previous["blocked"] or len(previous["value"]) < 12):
            continue
        if not any(len(r["value"]) >= 24 for r in following) or sum(len(r["value"]) for r in following) < 48:
            continue
        candidates.append(dict(start=row["start"], title=value, confidence="inferred",
                               reason="独占行短标题，前后叙事及远处同型标题共同支持；请核对"))
    peers = []
    if candidates:
        first, last = candidates[0], candidates[-1]
        peers = [first, last,
                 next((c for c in candidates if c["title"] != first["title"]), first),
                 next((c for c in reversed(candidates) if c["title"] != last["title"]), last)]
    inferred = [c for c in candidates if any(p["title"] != c["title"] and abs(p["start"]-c["start"]) >= 80 for p in peers)]
    inferred_starts = {c["start"] for c in inferred}
    inferred.extend(c for c in _number_gap_inferences(rows, anchors, candidates, heading_levels or {})
                    if c["start"] not in inferred_starts)
    boundaries = sorted(explicit + inferred, key=lambda b: b["start"])
    if not boundaries:
        return [dict(start=0, title=title or "第一章", confidence="fallback", reason="未发现可靠分界，可在预览添加切点")]
    if boundaries[0]["start"]:
        # Declared first chapters retain their preceding book/TOC text. A bare
        # heading inside narrative leaves the opening under the existing title.
        first = boundaries[0]
        opening = [r for r in rows if r["start"] < first["start"] and r["value"]]
        existing_opening = (preserve_opening and first["title"] != title
                            and any(not recognize_heading(r["value"]) for r in opening))
        if first["confidence"] == "explicit" and not existing_opening:
            boundaries[0]["start"] = 0
        else:
            boundaries.insert(0, dict(start=0, title=title or "第一章", confidence="fallback",
                                      reason="首个候选标题之前的原文，沿用已有章名"))
    return boundaries
