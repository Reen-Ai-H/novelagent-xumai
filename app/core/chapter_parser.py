"""Pure, conservative import parsing. Every non-heading span stays visible.

Chapter numbers are source numbers when increasing and unique. Special chapters,
volumes or restarted numbering use document order; their original heading stays
in the title. Bare numbered prose is deliberately not a chapter signal.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from pathlib import Path
import re


_DIGITS = dict(zip("零〇一二两三四五六七八九", (0, 0, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9)))
_UNITS = {"十": 10, "百": 100, "千": 1000}
_NUM = r"[0-9０-９零〇一二两三四五六七八九十百千]+"


def utf16_length(text: str) -> int:
    return sum(2 if ord(char) > 0xffff else 1 for char in text)


def scan_code_fence(line: str, active: tuple[str, int] | None) -> tuple[tuple[str, int] | None, bool]:
    """Shared fence state for imports and navigation; bool includes delimiters.

    Opening info strings are allowed. Only a same-character marker at least
    as long as the opener, followed entirely by whitespace, closes the block.
    """
    marker = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
    if active is not None:
        if marker and marker[1][0] == active[0] and len(marker[1]) >= active[1] and not marker[2].strip():
            return None, True
        return active, True
    if marker and not (marker[1][0] == "`" and "`" in marker[2]):
        return (marker[1][0], len(marker[1])), True
    return None, False


def heading_number(value: str) -> int | None:
    """Parse decimal or Chinese integers without accepting malformed unit order."""
    value = value.strip().translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if re.fullmatch(r"[0-9]+", value):
        return int(value) if len(value) <= 9 else None
    if not value or any(c not in _DIGITS and c not in _UNITS for c in value):
        return None
    if all(c in _DIGITS for c in value):
        return int("".join(str(_DIGITS[c]) for c in value))
    total, digit, previous_unit = 0, None, 10000
    for char in value:
        if char in _DIGITS:
            current = _DIGITS[char]
            if digit not in (None, 0):
                return None
            digit = current
        else:
            unit = _UNITS[char]
            if unit >= previous_unit or digit == 0:
                return None
            if digit is None and (total or unit != 10):
                return None
            total += (digit if digit is not None else 1) * unit
            digit, previous_unit = None, unit
    return total + (digit or 0)


@dataclass(frozen=True)
class Heading:
    title: str
    kind: str
    number: int | None = None
    level: int = 0


@dataclass(frozen=True)
class ParsedChapter:
    chapter_number: int
    title: str
    content: str
    heading_levels: tuple[tuple[int, int], ...] = ()  # Imported style, UTF-16 position.


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    chapters: tuple[ParsedChapter, ...]
    fragments: tuple[str, ...]


def recognize_heading(line: str) -> Heading | None:
    cleaned = line.strip()
    markdown = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", cleaned)
    if markdown:
        cleaned = markdown.group(1).strip()
    level = len(line.strip().split()[0]) if markdown else 0
    if re.fullmatch(r"目录|目次|contents|table of contents|正文", cleaned, re.I):
        return Heading(cleaned, "body" if cleaned == "正文" else "toc")
    # A prose sentence mentioning 第X章/回 must not consume the whole line.
    if len(cleaned) > 80:
        return None
    match = re.match(rf"^第\s*({_NUM})\s*([章节回卷])(.*)$", cleaned)
    if match:
        number = heading_number(match.group(1))
        tail = match.group(3)
        # Concatenated short titles occur in TXT novels, but grammatical
        # continuations such as 第一章里 / 第一次见面 must stay in the body.
        prose_tail = re.match(r"^(?:里|中|内|的|时|讲述|写着|提到|见面|见到|遇见)", tail)
        # Punctuation belongs to the title; sentence continuation is decided
        # by grammar after the chapter marker, not by a punctuation blacklist.
        if number is not None and number > 0 and not prose_tail:
            kind = {"卷": "volume", "节": "section"}.get(match.group(2), "chapter")
            return Heading(cleaned, kind, number, level)
    match = re.match(rf"^(chapter|volume|book)\s+({_NUM})(?=$|[\s:：.\-])", cleaned, re.I)
    if match:
        number = heading_number(match.group(2))
        if number is not None and number > 0:
            return Heading(cleaned, "chapter" if match.group(1).lower() == "chapter" else "volume", number, level)
    match = re.match(rf"^卷\s*({_NUM})(.*)$", cleaned)
    if match and (number := heading_number(match.group(1))):
        return Heading(cleaned, "volume", number)
    special = re.match(r"^(序章|楔子|序幕|尾声|终章|后记)(.*)$", cleaned)
    if special:
        tail = special.group(2)
        continuation = re.match(r"^(?:还|已经|正在|没有|并未|尚未|不再|渐渐|传来|响起|里|中|的)", tail)
        if not continuation:
            return Heading(cleaned, "special", level=level)
    if re.match(r"^(prologue|epilogue)(?=$|[\s:：\-])", cleaned, re.I):
        return Heading(cleaned, "special", level=level)
    if markdown:
        match = re.match(rf"^({_NUM})[、.．:：]?\s+", cleaned)
        number = heading_number(match.group(1)) if match else None
        return Heading(cleaned, "chapter" if number and number > 0 else "markdown",
                       number if number and number > 0 else None, len(line.strip().split()[0]))
    return None


def parse_document(filename: str, text: str, *, heading_levels: Mapping[int, int] | None = None) -> ParsedDocument:
    # Newlines are source content, including CRLF. DOCX hints use code-point
    # positions in the decoded source and never insert Markdown into the text.
    normalized = text
    lines = normalized.splitlines(keepends=True)
    headings = [recognize_heading(line) for line in lines]
    positions = []
    offset = 0
    fence = None
    for i, line in enumerate(lines):
        positions.append(offset)
        fence, in_code = scan_code_fence(line, fence)
        if in_code:
            headings[i] = None
        if heading_levels and offset in heading_levels and line.strip():
            heading = headings[i]
            headings[i] = Heading(line.rstrip("\r\n"), heading.kind if heading else "markdown",
                                  heading.number if heading else None, heading_levels[offset])
        offset += len(line)
    next_nonblank_lines: list[int | None] = [None] * len(lines)
    following = None
    for i in range(len(lines) - 1, -1, -1):
        next_nonblank_lines[i] = following
        if lines[i].strip():
            following = i
    toc_lines: set[int] = set()
    in_toc, seen = False, set()
    toc_body_markers: set[int] = set()

    def entry_key(heading: Heading):
        # Page leaders and page numbers are TOC formatting, not identity.
        title = re.sub(r"(?:\.{2,}|…+|·{2,}|\s+)\s*[0-9０-９]+\s*$", "", heading.title).strip()
        return heading.kind, heading.number, title.casefold()

    for index, heading in enumerate(headings):
        if heading and heading.kind == "toc":
            in_toc, seen = True, set()
            toc_lines.add(index)
            continue
        if not in_toc:
            continue
        next_nonblank = next_nonblank_lines[index]
        followed_by_body = (heading and next_nonblank is not None and not headings[next_nonblank]
                            and not re.match(r"^[-*]\s*\[", lines[next_nonblank].strip()))
        if heading and (heading.kind == "body" or followed_by_body
                        or (heading.kind == "volume" and entry_key(heading) in seen)):
            if heading.kind == "body":
                toc_body_markers.add(index)
            in_toc = False
            continue
        # Page leaders / Markdown TOC links are not narrative headings.
        entry = heading or re.match(rf"^(?:第\s*{_NUM}\s*[章节回卷]|[-*]\s*\[)", lines[index].strip())
        if not lines[index].strip() or entry:
            toc_lines.add(index)
            if heading:
                seen.add(entry_key(heading))
            else:
                link = re.search(r"\[([^\]]+)\]\(", lines[index])
                linked_heading = recognize_heading(link.group(1)) if link else None
                if linked_heading:
                    seen.add(entry_key(linked_heading))
        else:
            in_toc = False

    first_chapter = next((i for i, h in enumerate(headings)
                          if h and h.kind in {"chapter", "section", "special", "markdown"} and i not in toc_lines), len(lines))
    narrative = [h for i, h in enumerate(headings)
                 if h and h.kind in {"chapter", "special", "section", "markdown"} and i not in toc_lines]
    numbered = [h for h in narrative if h.kind in {"chapter", "special"}]
    # Numbered chapters identify the chapter layer (e.g. H2 under a book H1).
    # At that layer, unnumbered peers are chapters too. Without such anchors,
    # use the outer declared layer across *all* heading kinds, including 节.
    root_level = min((h.level for h in numbered), default=min((h.level for h in narrative if h.level), default=0))

    def chapter_boundary(heading: Heading) -> bool:
        if heading.kind not in {"chapter", "special", "section", "markdown"}:
            return True
        if root_level:
            return heading.level == root_level
        if numbered:
            return heading.kind in {"chapter", "special"}
        return heading.level == 0

    boundaries = [(i, h) for i, h in enumerate(headings)
                  if h and (i not in toc_lines or h.kind == "toc")
                  and (h.kind != "body" or i < first_chapter or i in toc_body_markers)
                  and chapter_boundary(h)]
    fragments: list[str] = []
    parsed: list[tuple[Heading, str, int]] = []
    if not boundaries:
        if toc_lines:
            fragments.append(normalized)
        elif normalized.strip():
            parsed.append((Heading(Path(filename).stem or "第一章", "chapter", 1), normalized, 0))
    else:
        preamble = "".join(lines[:boundaries[0][0]])
        if preamble:
            fragments.append(preamble)
        for position, (start, heading) in enumerate(boundaries):
            end = boundaries[position + 1][0] if position + 1 < len(boundaries) else len(lines)
            body = "".join(lines[start + 1:end])
            if heading.kind in {"volume", "body", "toc"} or not body.strip():
                fragments.append("".join(lines[start:end]))
            else:
                parsed.append((heading, body, positions[start] + len(lines[start])))
    numbers = [heading.number for heading, _, _ in parsed]
    ordered = (all(n is not None and n > 0 for n in numbers)
               and all(a < b for a, b in zip(numbers, numbers[1:]))
               and not any(h.kind in {"volume", "special"} for _, h in boundaries))
    chapters = tuple(ParsedChapter(heading.number if ordered else index, heading.title, content,
                                   tuple((utf16_length(content[:position - start]), level)
                                         for position, level in (heading_levels or {}).items()
                                         if start <= position < start + len(content)))
                     for index, (heading, content, start) in enumerate(parsed, 1))
    title = Path(filename).stem or (chapters[0].title if chapters else "未命名导入")
    if len(chapters) == 1:
        title = chapters[0].title
    return ParsedDocument(title, chapters, tuple(fragments))
