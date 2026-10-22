"""Source selectors for model calls; exact quotations are assembled by the server."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import re

from pydantic import Field, create_model

from schemas.analysis_delta import AnalysisDelta
from schemas.analysis_report import AnalysisReport, AnalysisReportV2, Event, ReportEvidence, StrictModel, validate_character_relations


class SourceSelection(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    source_id: str = Field(pattern=r"^S[1-9][0-9]*_[a-f0-9]{20}$")


def _selector_model(name, base, overrides):
    fields = {key: (field.annotation, deepcopy(field)) for key, field in base.model_fields.items()
              if key not in overrides}
    fields.update(overrides)
    return create_model(name, __base__=StrictModel, **fields)


GroundedReport = _selector_model("GroundedReport", AnalysisReport, {
    "producer": (str, Field(default="server", exclude=True)),
    "evidence": (list[SourceSelection], Field(min_length=1, max_length=500)),
})
GroundedDelta = _selector_model("GroundedDelta", AnalysisDelta, {
    "new_evidence": (list[SourceSelection], Field(default_factory=list, max_length=60)),
    "revised_evidence": (list[SourceSelection], Field(default_factory=list, max_length=60)),
})

# Preview alone delegates source-position metadata to the server. Do not inherit
# Event: accepting then discarding its chapter fields would accept the old wire.
PreviewEvent = create_model("PreviewEvent", __base__=StrictModel, **{
    key: (field.annotation, deepcopy(field)) for key, field in Event.model_fields.items()
    if key not in {"chapter_number", "chapter_end"}
})
PreviewGroundedReport = _selector_model("PreviewGroundedReport", GroundedReport, {
    "events": (list[PreviewEvent], Field(min_length=1, max_length=300)),
})

# Separate final projection for the explicitly versioned source-v3 path. The
# old generation/preview selector schemas above remain byte-for-byte strict.
PreviewGroundedReportV2 = _selector_model("PreviewGroundedReportV2", AnalysisReportV2, {
    "producer": (str, Field(default="server", exclude=True)),
    "evidence": (list[SourceSelection], Field(min_length=1, max_length=500)),
    "events": (list[PreviewEvent], Field(min_length=1, max_length=300)),
})


@dataclass(frozen=True)
class SourcePassage:
    id: str
    chapter_number: int
    quote: str
    start: int
    end: int

    def public(self):
        return {"source_id": self.id, "chapter_number": self.chapter_number, "quote": self.quote}


def source_id(number: int, quote: str) -> str:
    return f"S{number}_{sha256(quote.encode('utf-8')).hexdigest()[:20]}"


def source_bank(chapters: dict[int, str]) -> dict[str, SourcePassage]:
    bank = {}
    for number, body in sorted(chapters.items()):
        # Complete contiguous sentence spans, with bounded contiguous pieces
        # for long unpunctuated prose. Never synthesize or fuzzy-match text.
        for match in re.finditer(r'[^。！？!?\n]+(?:[。！？!?]+[”’"\u0027]?|$)|[。！？!?]+', body, re.MULTILINE):
            span = match.group().strip()
            for offset in range(0, len(span), 180):
                quote = span[offset:offset + 180].strip()
                start = body.find(quote)
                if len(quote) < 2 or start < 0 or body.find(quote, start + 1) >= 0:
                    continue
                key = source_id(number, quote)
                passage = SourcePassage(key, number, quote, start, start + len(quote))
                if key in bank and bank[key] != passage:
                    raise ValueError("来源编号重复")
                bank[key] = passage
    return bank


def bind_selections(data, bank, read_text, *, delta=False, producer=None):
    """Validate the selector wire shape before resolving any server-owned text."""
    model = GroundedDelta if delta else GroundedReport
    payload = model.model_validate(data, strict=True).model_dump(mode="json")
    groups = ("new_evidence", "revised_evidence") if delta else ("evidence",)
    for group in groups:
        evidence = []
        for selection in payload[group]:
            passage = bank.get(selection["source_id"])
            if passage is None:
                raise ValueError("模型选择了未提供的原文来源编号")
            body = read_text.get(passage.chapter_number, "")
            if (body[passage.start:passage.end] != passage.quote or body.find(passage.quote) != passage.start
                    or body.find(passage.quote, passage.start + 1) >= 0):
                raise ValueError("来源片段不在已读正文中逐字唯一出现")
            evidence.append({"id": selection["id"], "chapter_number": passage.chapter_number,
                             "quote": passage.quote})
        payload[group] = evidence
    if not delta:
        payload["producer"] = producer
        report = AnalysisReport.model_validate(payload, strict=True)
        validate_event_evidence(report.model_dump(mode="json"))
        return report
    return AnalysisDelta.model_validate(payload, strict=True)


def _validate_preview_references(preview, evidence):
    """Check the whole reference graph before deriving any event metadata.

    Mirror AnalysisReport's non-range checks here; its final validation remains
    mandatory as a backstop. No placeholder chapters or filtered references.
    """
    ids = [x.id for group in (preview.findings, preview.characters, preview.events, evidence) for x in group]
    if len(ids) != len(set(ids)):
        raise ValueError("分析 ID 重复")
    chapters = set(preview.chapter_numbers)
    if len(chapters) != len(preview.chapter_numbers) or any(n < 1 for n in chapters):
        raise ValueError("阅读章节范围无效")
    evidence_ids = {x.id for x in evidence}
    character_ids = {x.id for x in preview.characters}
    event_ids = {x.id for x in preview.events}
    claims = [*preview.findings, *preview.relations, *preview.character_relations, *preview.contradictions]
    for person in preview.characters:
        claims.extend(c for c in (person.identity, person.motivation, person.change, *person.insights) if c is not None)
        if person.portrait is not None:
            claims.append(person.portrait)
    for event in preview.events:
        if not set(event.actor_ids) <= character_ids:
            raise ValueError("事件人物引用无效")
        claims.extend((event.action, event.consequence, *event.sub_events))
    for claim in claims:
        if not set(claim.evidence_ids) <= evidence_ids:
            raise ValueError("判断引用了不存在的证据")
    if any(x.chapter_number not in chapters for x in evidence):
        raise ValueError("证据超出已读范围")
    if any(x.from_id not in event_ids or x.to_id not in event_ids or x.from_id == x.to_id
           for x in preview.relations):
        raise ValueError("剧情连线端点无效")
    validate_character_relations(preview.character_relations, character_ids)
    if len(preview.story_order) != len(event_ids) or set(preview.story_order) != event_ids:
        raise ValueError("故事时间线必须覆盖每个事件一次")


def _derive_preview_event_ranges(payload):
    evidence = {x["id"]: x["chapter_number"] for x in payload["evidence"]}
    for event in payload["events"]:
        claims = [event["action"], event["consequence"], *event["sub_events"]]
        numbers = [evidence[key] for claim in claims for key in claim["evidence_ids"]]
        event["chapter_number"], event["chapter_end"] = min(numbers), max(numbers)


def bind_preview_selections(data, bank, read_text, *, producer, schema_version="1"):
    """Bind strict preview selectors, validate every reference, then derive ranges."""
    models = {"1": (PreviewGroundedReport, AnalysisReport), "2": (PreviewGroundedReportV2, AnalysisReportV2)}
    if schema_version not in models:
        raise ValueError("未知的公开分析报告版本")
    preview_model, report_model = models[schema_version]
    preview = preview_model.model_validate(data, strict=True)
    evidence = []
    for selection in preview.evidence:
        passage = bank.get(selection.source_id)
        if passage is None:
            raise ValueError("模型选择了未提供的原文来源编号")
        if (not isinstance(passage, SourcePassage) or passage.id != selection.source_id
                or type(passage.chapter_number) is not int or passage.chapter_number not in read_text
                or type(passage.start) is not int or type(passage.end) is not int
                or not isinstance(passage.quote, str)
                or passage.id != source_id(passage.chapter_number, passage.quote)):
            raise ValueError("来源编号或范围无效")
        body = read_text[passage.chapter_number]
        if (not 0 <= passage.start < passage.end <= len(body)
                or body[passage.start:passage.end] != passage.quote
                or body.find(passage.quote) != passage.start
                or body.find(passage.quote, passage.start + 1) >= 0):
            raise ValueError("来源片段不在已读正文中逐字唯一出现")
        evidence.append(ReportEvidence.model_validate({"id": selection.id,
            "chapter_number": passage.chapter_number, "quote": passage.quote}, strict=True))
    _validate_preview_references(preview, evidence)
    payload = preview.model_dump(mode="json")
    payload["evidence"] = [item.model_dump(mode="json") for item in evidence]
    payload["producer"] = producer
    _derive_preview_event_ranges(payload)
    report = report_model.model_validate(payload, strict=True)
    validate_event_evidence(report.model_dump(mode="json"))
    return report


def validate_event_evidence(draft):
    evidence = {x["id"]: x["chapter_number"] for x in draft["evidence"]}
    for event in draft["events"]:
        claims = [event["action"], event["consequence"], *event.get("sub_events", [])]
        numbers = [evidence[key] for claim in claims for key in claim["evidence_ids"]]
        if min(numbers) != event["chapter_number"] or max(numbers) != (event.get("chapter_end") or event["chapter_number"]):
            raise ValueError("事件章节范围与所选原文依据不一致")
