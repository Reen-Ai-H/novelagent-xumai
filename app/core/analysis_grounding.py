"""Source selectors for model calls; exact quotations are assembled by the server."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import re

from pydantic import Field, create_model

from schemas.analysis_delta import AnalysisDelta
from schemas.analysis_report import AnalysisReport, StrictModel


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


def validate_event_evidence(draft):
    evidence = {x["id"]: x["chapter_number"] for x in draft["evidence"]}
    for event in draft["events"]:
        claims = [event["action"], event["consequence"], *event.get("sub_events", [])]
        numbers = [evidence[key] for claim in claims for key in claim["evidence_ids"]]
        if min(numbers) != event["chapter_number"] or max(numbers) != (event.get("chapter_end") or event["chapter_number"]):
            raise ValueError("事件章节范围与所选原文依据不一致")
