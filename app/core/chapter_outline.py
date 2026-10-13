"""Read-only navigation over the exact current chapter, never manuscript edits.

Bare Chinese headings need repeated, separated typographic evidence and nearby
narrative paragraphs. This is a conservative layout heuristic, not a semantic
chapter splitter. Section IDs are content anchors, not edit/revision tokens.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping

from app.core.chapter_parser import recognize_heading, scan_code_fence, utf16_length


# Grammatical utterances and free-standing scenery are weak heading evidence.
# These exclusions are language categories, not approved titles for one work.
_UTTERANCE = re.compile(
    r"^(?:我|你|他|她|它|咱|您|这|那|谁|怎么|什么|为何|原来|于是|忽然|突然|"
    r"终于|其实|果然|仍然|已经|正在|只好|没想到|不料|看来|可是|但是|大家|自己|唉|哎|啊|哦|嗯|哈哈)"
    r"|(?:了|呢|吗|吧|呀|啊|哇|啦|哟)$"
    r"|(?:渐渐|越来越|说道|问道|回答|摇头|点头|叹气|赶紧|必须|恐怕)"
    r"|^(?:真|太|好|多么).*(?:漂亮|美|好|棒|冷|热|糟|坏|妙|讨厌|可怕|难)$"
    r"|^(?:可恶|糟糕|不妙|救命|天哪|天呐)$"
)
_SCENERY = re.compile(r"^(?:夜色|天色|月色|阳光|月光|灯光|风声|雨声|树林|森林|石门|木门|山风|寒风|落叶|天空|大雨|白雪|薄雾|暮色)$"
                      r"|^(?:夜色|天色|月色|山风|寒风|雨声|风声|阳光|月光)(?:渐|已|更|正|在|很|微|吹|落|照)")
_ACTION_CLAUSE = re.compile(
    # Body movement plus a following action, manner + movement, and ordinary
    # directional/result complements are prose even without punctuation.
    r"^(?:(?:抬|低|回|转|偏|侧)头|(?:转|侧|起|躬)身|(?:伸|抬|挥|收)手|弯腰|迈步|举步|蹲下|站起|坐下|推门|拉门|握紧|拿起|放下|睁眼|闭眼)"
    r"|^(?:大|小|快|慢|碎|疾|缓)步(?:向|朝|往|走|奔|跑|退|前|后)"
    r"|^(?:轻轻|慢慢|缓缓|悄悄|默默|急忙|连忙|迅速|立刻|猛然)(?:看|望|走|去|跑|退|伸|抬|低|转|推|拉|拿|放|说|问)"
    r"|^(?:望|看|走|跑|奔|退|冲|跳|爬|挪|移)(?:向|往|过|进|出|回|开|上|下|远|近)"
)


def content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="surrogatepass")).hexdigest()


def chapter_sections(chapter_id: str, content: str, *, heading_levels: Mapping[int, int] | None = None) -> list[dict]:
    """Return UTF-16 half-open ranges in *content*, without normalizing newlines.

    heading_levels contains original DOCX outline positions, only supplied by
    the service when its import content hash still matches the current draft.
    Callers must bind this projection to the response's version, revision and
    exact content; unsaved editor text must never navigate with older offsets.
    """
    if not content.strip():
        return []
    lines = content.splitlines(keepends=True)
    rows = []
    position = offset = 0
    fenced = None
    quote_stack: list[str] = []
    quote_pairs = {"“": "”", "「": "」", "『": "』", "‘": "’"}
    for line in lines:
        value = line.strip()
        fenced, in_code = scan_code_fence(line, fenced)
        quoted = bool(quote_stack)
        if not in_code:
            for index, char in enumerate(line):
                if quote_stack and char == quote_stack[-1]:
                    quote_stack.pop()
                elif char in quote_pairs:
                    quote_stack.append(quote_pairs[char])
                elif char == '"' and (index == 0 or line[index - 1] != "\\"):
                    quote_stack.append(char)
        rows.append((position, offset, value, in_code or quoted))
        position += len(line)
        offset += utf16_length(line)
    total_utf16 = offset
    occupied = [i for i, row in enumerate(rows) if row[2]]
    neighbors = {i: (occupied[n - 1] if n else None, occupied[n + 1] if n + 1 < len(occupied) else None)
                 for n, i in enumerate(occupied)}
    explicit, candidates = [], []
    for i in occupied:
        position, offset, value, in_code = rows[i]
        if in_code:
            continue
        heading = recognize_heading(value)
        if heading and heading.kind not in {"toc", "body", "volume"}:
            explicit.append((position, offset, heading.title, "explicit"))
            continue
        if heading_levels and offset in heading_levels:
            explicit.append((position, offset, value, "explicit"))
            continue
        if (not re.fullmatch(r"[\u4e00-\u9fff]{2,8}", value) or _UTTERANCE.search(value)
                or _SCENERY.search(value) or _ACTION_CLAUSE.search(value)):
            continue
        before, after = neighbors[i]
        # A title followed by another short line is usually a list, verse, or
        # dialogue. Do not turn it into a table of contents automatically.
        if after is None or rows[after][3] or len(rows[after][2]) < 24:
            continue
        if before is not None and (rows[before][3] or len(rows[before][2]) < 12):
            continue
        candidates.append((position, offset, value, "inferred"))
    # One ambiguous isolated word is not enough. Peer headings must also be
    # separated by narrative, not consecutive labels within a short passage.
    # The farthest distinct-title peers suffice for the distance check. Avoid
    # comparing every pair in a long file containing repeated short labels.
    peers = []
    if candidates:
        first, last = candidates[0], candidates[-1]
        peers = [first, last]
        peers.append(next((c for c in candidates if c[2] != first[2]), first))
        peers.append(next((c for c in reversed(candidates) if c[2] != last[2]), last))
    inferred = [candidate for candidate in candidates if any(
        other[2] != candidate[2] and abs(other[0] - candidate[0]) >= 80 for other in peers)]
    headings = sorted(explicit + inferred)
    if not headings or content[:headings[0][0]].strip():
        headings.insert(0, (0, 0, "本章开篇", "opening"))
    sections = []
    for index, (position, start, title, kind) in enumerate(headings):
        next_position, end = (headings[index + 1][:2] if index + 1 < len(headings) else (len(content), total_utf16))
        # Include exact text and position; identical repeated headings have
        # different IDs, and moving/editing an anchor cannot reuse an old ID.
        identity = f"{chapter_id}\0{start}\0{kind}\0{content[position:next_position]}"
        sections.append(dict(section_id="sec_" + content_digest(identity)[:32], title=title,
                             start=start, end=end, kind=kind))
    return sections
