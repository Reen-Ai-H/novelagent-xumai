"""作品拆解 MVP 的持久化与 API 数据合同。

作品拆解是独立创作内部的一项可回溯分析，不是第三条顶层创作路径。
本文件只描述已经通过安全校验、可公开给当前账户的结构化结论；不保存
prompt、原始模型输出或整本正文。
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DeconstructionStatus = Literal[
    "empty",
    "queued",
    "running",
    "completed",
    "failed_retryable",
    "stale",
    "rebuild_required",
]
DeconstructionEffectiveStatus = DeconstructionStatus
DeconstructionRunStatus = Literal["none", "queued", "running", "completed", "failed_retryable"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceRef(BaseModel):
    """能回到同一稿本、同一章节和最小片段的证据定位。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    evidence_id: str
    document_id: str = ""
    source_version_id: str
    source_revision: int = Field(default=0, ge=0)
    source_hash: str = ""
    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    start_offset: int = Field(default=0, ge=0)
    end_offset: int = Field(default=0, ge=0)
    offset_unit: Literal["utf16_code_unit"] = "utf16_code_unit"
    excerpt: str = Field(default="", max_length=180)
    label: str = Field(default="正文证据", max_length=120)
    target_path: str | None = Field(default=None, max_length=500)


class DeconstructionObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(default="", max_length=500)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: list[str] = Field(default_factory=list, max_length=8)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=8)


class DeconstructionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label: str = Field(default="候选", max_length=80)
    value: str = Field(..., min_length=1, max_length=300)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: list[str] = Field(default_factory=list, max_length=8)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=8)


class DeconstructionOverview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(default="未命名作品", max_length=200)
    total_word_count: int = Field(default=0, ge=0)
    chapter_count: int = Field(default=0, ge=0)
    structure_units: list[str] = Field(default_factory=list, max_length=40)
    main_character_candidates: list[DeconstructionCandidate] = Field(default_factory=list, max_length=30)
    core_conflict_candidates: list[DeconstructionCandidate] = Field(default_factory=list, max_length=20)
    opening: DeconstructionObservation = Field(default_factory=DeconstructionObservation)
    development: DeconstructionObservation = Field(default_factory=DeconstructionObservation)
    climax: DeconstructionObservation = Field(default_factory=DeconstructionObservation)
    ending: DeconstructionObservation = Field(default_factory=DeconstructionObservation)
    uncertainty: list[str] = Field(default_factory=list, max_length=20)


class TimelineNode(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    node_id: str
    label: str = Field(..., max_length=160)
    normalized_start: float = Field(..., ge=0.0, le=100.0)
    normalized_end: float = Field(..., ge=0.0, le=100.0)
    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    chapter_title: str = Field(default="", max_length=200)
    word_start: int = Field(default=0, ge=0)
    word_end: int = Field(default=0, ge=0)
    event: str = Field(default="", max_length=600)
    narrative_function: str = Field(default="不确定", max_length=160)
    characters: list[str] = Field(default_factory=list, max_length=30)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: list[str] = Field(default_factory=list, max_length=8)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=8)


class ChapterBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    title: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=500)
    core_events: list[str] = Field(default_factory=list, max_length=12)
    narrative_function: str = Field(default="不确定", max_length=160)
    scenes: list[str] = Field(default_factory=list, max_length=12)
    conflict: str = Field(default="不确定", max_length=500)
    information_release: str = Field(default="不确定", max_length=500)
    relationship_change: str = Field(default="不确定", max_length=500)
    emotional_change: str = Field(default="不确定", max_length=500)
    foreshadowing: list[str] = Field(default_factory=list, max_length=12)
    opening_hook: str = Field(default="", max_length=300)
    ending_hook: str = Field(default="", max_length=300)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: list[str] = Field(default_factory=list, max_length=12)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=16)


# Stage 32 is opt-in through report, never an in-place migration of stage 31.
DepthID = Annotated[str, Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_-]+$")]
DepthText = Annotated[str, Field(min_length=1, max_length=1200, pattern=r"\S")]
DepthScore = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
DepthProgress = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
DepthKind = Literal[
    "character", "character_state", "plotline", "event", "foreshadowing",
    "foreshadowing_state", "rhythm", "reader_experience", "technique", "relation",
]


class DepthModel(BaseModel):
    """Strict JSON-shaped public data; no arbitrary dictionaries or coercion."""

    model_config = ConfigDict(extra="forbid", strict=True, revalidate_instances="always")


class DepthSource(DepthModel):
    project_id: DepthID
    document_id: DepthID
    source_version_id: DepthID
    source_revision: int = Field(ge=0)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def depth_stable_id(source: DepthSource, kind: str, anchor: str) -> str:
    """Source-scoped repeatable ID; anchor is semantic identity, never prose/order."""
    if not kind.strip() or not anchor.strip():
        raise ValueError("stable id requires kind and anchor")
    identity = ["2.0", source.project_id, source.source_version_id,
                source.source_revision, source.source_hash, kind, anchor]
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return "d32_" + digest.hexdigest()[:40]


class DepthChapter(DepthModel):
    chapter_id: DepthID
    chapter_number: int = Field(ge=1)
    title: str = Field(max_length=200)
    utf16_length: int = Field(ge=0)
    normalized_start: DepthProgress
    normalized_end: DepthProgress

    @model_validator(mode="after")
    def ordered(self) -> "DepthChapter":
        if self.normalized_start > self.normalized_end:
            raise ValueError("chapter progress is reversed")
        if self.utf16_length == 0 and self.normalized_start != self.normalized_end:
            raise ValueError("empty chapter cannot occupy progress")
        return self


class DepthEvidence(DepthSource):
    evidence_id: DepthID
    chapter_id: DepthID
    chapter_number: int = Field(ge=1)
    granularity: Literal["span", "chapter"]
    start_offset: int | None = Field(ge=0)
    end_offset: int | None = Field(ge=0)
    offset_unit: Literal["utf16_code_unit"] = "utf16_code_unit"
    excerpt: str = Field(max_length=180)
    label: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def offsets(self) -> "DepthEvidence":
        if self.granularity == "chapter":
            if self.start_offset is not None or self.end_offset is not None or self.excerpt:
                raise ValueError("chapter evidence has no offsets or excerpt")
        elif (self.start_offset is None or self.end_offset is None
              or self.start_offset >= self.end_offset or not self.excerpt.strip()):
            raise ValueError("span evidence requires a nonempty ordered span and excerpt")
        return self


class DepthAnalysisItem(DepthModel):
    item_id: DepthID
    kind: DepthKind
    category: str = Field(min_length=1, max_length=80)
    conclusion: DepthText
    epistemic_status: Literal["observed", "inferred", "unknown"]
    chapter_ids: list[DepthID] = Field(min_length=1)
    normalized_start: DepthProgress
    normalized_end: DepthProgress
    evidence_ids: list[DepthID]
    related_item_ids: list[DepthID]
    confidence: DepthScore
    uncertainty: list[DepthText]

    @model_validator(mode="after")
    def supported(self) -> "DepthAnalysisItem":
        if self.normalized_start > self.normalized_end:
            raise ValueError("item progress is reversed")
        if len(set(self.chapter_ids)) != len(self.chapter_ids) or len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("duplicate chapter or evidence reference")
        if self.epistemic_status == "unknown":
            if self.confidence != 0 or not self.uncertainty:
                raise ValueError("unknown requires zero confidence and explicit uncertainty")
        elif not self.evidence_ids:
            raise ValueError("observed/inferred conclusions require evidence")
        if self.epistemic_status == "inferred" and not self.uncertainty:
            raise ValueError("inference requires explicit uncertainty")
        return self


class DepthCharacter(DepthAnalysisItem):
    kind: Literal["character"] = "character"
    name: str = Field(min_length=1, max_length=80)
    aliases: list[str] = Field(max_length=40)
    role: DepthText
    motivation: DepthText
    inner_conflict: DepthText
    arc_summary: DepthText


class DepthCharacterState(DepthAnalysisItem):
    kind: Literal["character_state"] = "character_state"
    character_id: DepthID
    goal: DepthText
    belief: DepthText
    emotion: DepthText
    agency: DepthText
    change: DepthText
    trigger_event_ids: list[DepthID]


class DepthPlotline(DepthAnalysisItem):
    kind: Literal["plotline"] = "plotline"
    title: str = Field(min_length=1, max_length=160)
    central_question: DepthText
    stakes: DepthText
    resolution: DepthText
    character_ids: list[DepthID]


class DepthEvent(DepthAnalysisItem):
    kind: Literal["event"] = "event"
    plotline_ids: list[DepthID] = Field(min_length=1)
    character_ids: list[DepthID]
    story_order: int | None = Field(ge=0)
    narrative_order: int = Field(ge=0)
    temporal_mode: Literal["linear", "flashback", "flashforward", "parallel", "unknown"]
    action: DepthText
    consequence: DepthText
    plotline_status: Literal["introduced", "developing", "turning", "resolved", "open", "unknown"]


class DepthForeshadowing(DepthAnalysisItem):
    kind: Literal["foreshadowing"] = "foreshadowing"
    label: str = Field(min_length=1, max_length=160)
    planted_detail: DepthText
    expected_payoff: DepthText
    interpretation: DepthText


class DepthForeshadowingState(DepthAnalysisItem):
    kind: Literal["foreshadowing_state"] = "foreshadowing_state"
    foreshadowing_id: DepthID
    status: Literal["planted", "reinforced", "paid_off", "subverted", "unresolved", "unknown"]
    payoff: DepthText
    event_ids: list[DepthID]


class DepthRhythm(DepthAnalysisItem):
    kind: Literal["rhythm"] = "rhythm"
    narrative_function: DepthText
    scene_summary: DepthText
    pace: DepthScore | None
    tension: DepthScore | None
    information_density: DepthScore | None
    transition: DepthText


class DepthReaderExperience(DepthAnalysisItem):
    kind: Literal["reader_experience"] = "reader_experience"
    expectation: DepthText
    information_gap: DepthText
    emotional_effect: DepthText
    curiosity: DepthScore | None
    suspense: DepthScore | None
    emotional_valence: float | None = Field(ge=-1, le=1, allow_inf_nan=False)
    payoff: DepthText


class DepthTechnique(DepthAnalysisItem):
    kind: Literal["technique"] = "technique"
    technique: str = Field(min_length=1, max_length=160)
    observation: DepthText
    mechanism: DepthText
    effect: DepthText
    learning_note: DepthText
    applicability: DepthText


class DepthEndpoint(DepthModel):
    item_id: DepthID
    kind: Literal["character", "character_state", "plotline", "event", "foreshadowing", "foreshadowing_state"]


class DepthRelation(DepthAnalysisItem):
    kind: Literal["relation"] = "relation"
    start: DepthEndpoint
    end: DepthEndpoint
    relation_type: Literal[
        "allies", "opposes", "depends_on", "changes_to", "causes", "enables",
        "prevents", "precedes", "parallel_to", "intersects", "plants", "reinforces",
        "pays_off", "subverts",
    ]
    explanation: DepthText


# Pairs are directional; precedes is narrative order, never an implicit cause.
DEPTH_RELATION_ENDPOINTS = {
    **{key: ("character", "character") for key in ("allies", "opposes", "depends_on")},
    "changes_to": ("character_state", "character_state"),
    **{key: ("event", "event") for key in ("causes", "enables", "prevents", "precedes", "parallel_to")},
    "intersects": ("plotline", "plotline"),
    **{key: ("event", "foreshadowing") for key in ("plants", "reinforces", "pays_off", "subverts")},
}


class DepthView(DepthModel):
    summary: DepthText
    uncertainty: list[DepthText]


class DepthCharactersView(DepthView):
    characters: list[DepthCharacter]
    states: list[DepthCharacterState]
    relations: list[DepthRelation]


class DepthPlotView(DepthView):
    plotlines: list[DepthPlotline]
    events: list[DepthEvent]
    relations: list[DepthRelation]


class DepthForeshadowingView(DepthView):
    threads: list[DepthForeshadowing]
    states: list[DepthForeshadowingState]
    relations: list[DepthRelation]


class DepthRhythmView(DepthView):
    items: list[DepthRhythm] = Field(min_length=1)


class DepthReaderView(DepthView):
    items: list[DepthReaderExperience] = Field(min_length=1)


class DepthTechniqueView(DepthView):
    items: list[DepthTechnique] = Field(min_length=1)


class DeconstructionDepthReport(DepthModel):
    report_version: Literal["2.0"]
    source: DepthSource
    chapters: list[DepthChapter] = Field(min_length=1)
    evidence: list[DepthEvidence]
    characters: DepthCharactersView
    plot: DepthPlotView
    foreshadowing: DepthForeshadowingView
    rhythm: DepthRhythmView
    reader_experience: DepthReaderView
    technique: DepthTechniqueView

    def analysis_items(self) -> list[DepthAnalysisItem]:
        return [
            *self.characters.characters, *self.characters.states, *self.characters.relations,
            *self.plot.plotlines, *self.plot.events, *self.plot.relations,
            *self.foreshadowing.threads, *self.foreshadowing.states, *self.foreshadowing.relations,
            *self.rhythm.items, *self.reader_experience.items, *self.technique.items,
        ]

    @model_validator(mode="after")
    def validate_graph(self) -> "DeconstructionDepthReport":
        def unique(values, label):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label}")

        unique([c.chapter_id for c in self.chapters], "chapter id")
        numbers = [c.chapter_number for c in self.chapters]
        unique(numbers, "chapter number")
        if numbers != sorted(numbers):
            raise ValueError("chapters must follow reading order")
        if self.chapters[0].normalized_start != 0 or self.chapters[-1].normalized_end != 100:
            raise ValueError("chapter timeline must cover 0 to 100")
        for left, right in zip(self.chapters, self.chapters[1:]):
            if left.normalized_end != right.normalized_start:
                raise ValueError("chapter progress must be contiguous and monotonic")
        chapters = {c.chapter_id: c for c in self.chapters}
        unique([e.evidence_id for e in self.evidence], "evidence id")
        evidence = {e.evidence_id: e for e in self.evidence}
        for ref in self.evidence:
            if any(getattr(ref, key) != value for key, value in self.source.model_dump().items()):
                raise ValueError("evidence source mismatch")
            chapter = chapters.get(ref.chapter_id)
            if chapter is None or chapter.chapter_number != ref.chapter_number:
                raise ValueError("evidence chapter mismatch")
            if ref.end_offset is not None and ref.end_offset > chapter.utf16_length:
                raise ValueError("evidence offset outside chapter")
        items = self.analysis_items()
        unique([i.item_id for i in items], "analysis id")
        index = {i.item_id: i for i in items}

        def references(ids, kind):
            unique(ids, "typed reference")
            if any(key not in index or index[key].kind != kind for key in ids):
                raise ValueError(f"invalid {kind} reference")

        for item in items:
            unique(item.related_item_ids, "related item reference")
            if any(key not in index or key == item.item_id for key in item.related_item_ids):
                raise ValueError("invalid related item reference")
            if any(key not in chapters for key in item.chapter_ids):
                raise ValueError("unknown source chapter")
            selected = [chapters[key] for key in item.chapter_ids]
            if [c.chapter_number for c in selected] != sorted(c.chapter_number for c in selected):
                raise ValueError("item chapters must follow reading order")
            if (item.normalized_start < selected[0].normalized_start
                    or item.normalized_end > selected[-1].normalized_end):
                raise ValueError("item progress outside source chapters")
            for key in item.evidence_ids:
                if key not in evidence or evidence[key].chapter_id not in item.chapter_ids:
                    raise ValueError("invalid evidence reference")
            if isinstance(item, DepthCharacterState):
                references([item.character_id], "character")
                references(item.trigger_event_ids, "event")
            elif isinstance(item, DepthPlotline):
                references(item.character_ids, "character")
            elif isinstance(item, DepthEvent):
                references(item.plotline_ids, "plotline")
                references(item.character_ids, "character")
            elif isinstance(item, DepthForeshadowingState):
                references([item.foreshadowing_id], "foreshadowing")
                references(item.event_ids, "event")
            elif isinstance(item, DepthRelation):
                references([item.start.item_id], item.start.kind)
                references([item.end.item_id], item.end.kind)
                if item.start.item_id == item.end.item_id:
                    raise ValueError("self relation is invalid")
                if (item.start.kind, item.end.kind) != DEPTH_RELATION_ENDPOINTS[item.relation_type]:
                    raise ValueError("relation endpoint type mismatch")
                if item.relation_type == "precedes":
                    if index[item.start.item_id].narrative_order >= index[item.end.item_id].narrative_order:
                        raise ValueError("precedes must follow narrative order")
                if item.relation_type == "changes_to":
                    start, end = index[item.start.item_id], index[item.end.item_id]
                    if start.character_id != end.character_id or start.normalized_start > end.normalized_start:
                        raise ValueError("state change must follow the same character forward")
        groups = (
            (self.characters, self.characters.characters), (self.plot, self.plot.plotlines),
            (self.foreshadowing, self.foreshadowing.threads), (self.rhythm, self.rhythm.items),
            (self.reader_experience, self.reader_experience.items), (self.technique, self.technique.items),
        )
        for view, primary in groups:
            if not primary and not view.uncertainty:
                raise ValueError("empty perspective requires explicit uncertainty")
        for parents, states, parent_field in (
            (self.characters.characters, self.characters.states, "character_id"),
            (self.foreshadowing.threads, self.foreshadowing.states, "foreshadowing_id"),
        ):
            represented = {getattr(state, parent_field) for state in states}
            if any(parent.item_id not in represented for parent in parents):
                raise ValueError("each entity requires at least one retrospective state")
        represented_lines = {key for event in self.plot.events for key in event.plotline_ids}
        if any(line.item_id not in represented_lines for line in self.plot.plotlines):
            raise ValueError("each plotline requires at least one event")
        for view in (self.rhythm, self.reader_experience, self.technique):
            if not any(item.epistemic_status != "unknown" for item in view.items):
                raise ValueError("a completed view cannot contain only unknown placeholders")
        for relations, allowed in (
            (self.characters.relations, {"allies", "opposes", "depends_on", "changes_to"}),
            (self.plot.relations, {"causes", "enables", "prevents", "precedes", "parallel_to", "intersects"}),
            (self.foreshadowing.relations, {"plants", "reinforces", "pays_off", "subverts"}),
        ):
            if any(r.relation_type not in allowed for r in relations):
                raise ValueError("relation is in the wrong perspective")
        for sequence in (self.rhythm.items, self.reader_experience.items):
            if sequence:
                if sequence[0].normalized_start != 0 or sequence[-1].normalized_end != 100:
                    raise ValueError("curve must cover 0 to 100")
                if any(a.normalized_end > b.normalized_start for a, b in zip(sequence, sequence[1:])):
                    raise ValueError("curve must be monotonic")
        for states, parent_field in (
            (self.characters.states, "character_id"),
            (self.foreshadowing.states, "foreshadowing_id"),
        ):
            previous = {}
            for state in states:
                key = getattr(state, parent_field)
                if state.normalized_start < previous.get(key, -1):
                    raise ValueError("states must follow reading progress")
                previous[key] = state.normalized_start
        orders = [e.narrative_order for e in self.plot.events]
        unique(orders, "narrative order")
        if orders != sorted(orders):
            raise ValueError("events must follow narrative order")
        return self


def validate_depth_report_source(
    report: DeconstructionDepthReport, *, source: DepthSource, chapters: Mapping[str, str],
) -> DeconstructionDepthReport:
    """Publication gate using an authorized immutable source snapshot; never stores text.

    The caller computes/verifies source_hash from the canonical formal source. This
    pure validator checks the actual UTF-16 boundaries and exact (unstripped) quote.
    """
    report = DeconstructionDepthReport.model_validate(report.model_dump())
    if report.source != source or set(chapters) != {c.chapter_id for c in report.chapters}:
        raise ValueError("report source snapshot mismatch")
    encoded = {key: text.encode("utf-16-le") for key, text in chapters.items()}
    for chapter in report.chapters:
        if len(encoded[chapter.chapter_id]) // 2 != chapter.utf16_length:
            raise ValueError("chapter UTF-16 length mismatch")
    for ref in report.evidence:
        if ref.granularity == "chapter":
            continue
        raw = encoded[ref.chapter_id]
        start, end = ref.start_offset * 2, ref.end_offset * 2
        try:
            # Decoding all three parts rejects a cut through either surrogate pair.
            raw[:start].decode("utf-16-le")
            quote = raw[start:end].decode("utf-16-le")
            raw[end:].decode("utf-16-le")
        except UnicodeDecodeError:
            raise ValueError("evidence splits a UTF-16 surrogate pair") from None
        if quote != ref.excerpt:
            raise ValueError("evidence excerpt does not match source span")
    return report


def _validate_report_binding(container) -> None:
    report = container.report
    if report is None:
        return
    for key, value in report.source.model_dump().items():
        if hasattr(container, key) and getattr(container, key) != value:
            raise ValueError("report does not match enclosing document source")
    if container.status != "completed":
        raise ValueError("only a completed document may publish a report")


class DeconstructionDocument(BaseModel):
    """一次绑定到稿本来源的拆解运行和完成结果。"""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    project_id: str
    account_id: str
    source_version_id: str
    source_revision: int = Field(default=0, ge=0)
    source_hash: str = Field(..., min_length=16, max_length=128)
    status: DeconstructionStatus = "queued"
    progress_percent: int = Field(default=0, ge=0, le=100)
    current_stage: str = Field(default="等待拆解", max_length=120)
    idempotency_key: str
    retry_count: int = Field(default=0, ge=0)
    analysis_label: str = "确定性结构拆解（无模型）"
    overview: DeconstructionOverview | None = None
    report: DeconstructionDepthReport | None = None
    timeline: list[TimelineNode] = Field(default_factory=list)
    chapter_breakdowns: list[ChapterBreakdown] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list, max_length=40)
    error_message: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_report(self) -> "DeconstructionDocument":
        _validate_report_binding(self)
        return self


class DeconstructionProjectRecord(BaseModel):
    """按作品保存当前运行与历史拆解，不改写独立正文侧车。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    account_id: str
    active_document_id: str | None = None
    documents: list[DeconstructionDocument] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class DeconstructionActions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retry: bool = False
    rebuild: bool = False


class DeconstructionProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    percent: int = Field(default=0, ge=0, le=100)
    current_stage: str = Field(default="等待拆解", max_length=120)


class DeconstructionSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: str | None = None
    revision: int | None = Field(default=None, ge=0)
    hash: str | None = None
    match: bool = False
    chapter_count: int = Field(default=0, ge=0)
    total_word_count: int = Field(default=0, ge=0)


class DeconstructionError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    retryable: bool = False


class DeconstructionActiveRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    run_status: DeconstructionRunStatus
    source_version_id: str
    source_revision: int = Field(default=0, ge=0)
    source_hash: str
    retry_count: int = Field(default=0, ge=0)
    idempotency_key: str
    analysis_label: str = "确定性结构拆解（无模型）"
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class DeconstructionDocumentPublic(BaseModel):
    """阶段 31A 兼容投影；不含内部 account_id。"""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    project_id: str
    source_version_id: str
    source_revision: int = Field(default=0, ge=0)
    source_hash: str
    status: DeconstructionStatus
    progress_percent: int = Field(default=0, ge=0, le=100)
    current_stage: str = Field(default="等待拆解", max_length=120)
    idempotency_key: str
    retry_count: int = Field(default=0, ge=0)
    analysis_label: str = "确定性结构拆解（无模型）"
    overview: DeconstructionOverview | None = None
    report: DeconstructionDepthReport | None = None
    timeline: list[TimelineNode] = Field(default_factory=list)
    chapter_breakdowns: list[ChapterBreakdown] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list, max_length=40)
    error_message: str | None = Field(default=None, max_length=500)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_report(self) -> "DeconstructionDocumentPublic":
        _validate_report_binding(self)
        return self


class DeconstructionResult(BaseModel):
    """只承载与当前 source 匹配的已完成结果。"""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    status: Literal["completed"] = "completed"
    source_version_id: str
    source_revision: int = Field(default=0, ge=0)
    source_hash: str
    analysis_label: str = "确定性结构拆解（无模型）"
    overview: DeconstructionOverview
    report: DeconstructionDepthReport | None = None
    timeline: list[TimelineNode] = Field(default_factory=list)
    chapter_breakdowns: list[ChapterBreakdown] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def validate_report(self) -> "DeconstructionResult":
        _validate_report_binding(self)
        return self


class DeconstructionHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    status: DeconstructionStatus
    source_version_id: str
    source_revision: int = Field(default=0, ge=0)
    source_hash: str
    retry_count: int = Field(default=0, ge=0)
    analysis_label: str = "确定性结构拆解（无模型）"
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class DeconstructionEvidenceChapter(BaseModel):
    """证据回链公开的稳定章节定位，不包含正文或内部字段。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chapter_id: str
    chapter_number: int = Field(..., ge=1)
    title: str = Field(default="", max_length=200)
    read_only: Literal[True] = True
    source_available: bool = False


class DeconstructionState(BaseModel):
    """兼容旧客户端的嵌套投影；字段与顶层 canonical state 保持一致。"""

    model_config = ConfigDict(extra="forbid")

    effective_status: DeconstructionEffectiveStatus
    run_status: DeconstructionRunStatus
    source_match: bool
    progress: DeconstructionProgress
    current_stage: str = Field(default="等待拆解", max_length=120)
    source: DeconstructionSource
    active_run: DeconstructionActiveRun | None = None
    result: DeconstructionResult | None = None
    actions: DeconstructionActions
    error: DeconstructionError | None = None


class DeconstructionResponse(BaseModel):
    """浏览器/客户端合同，省略账户归属和内部协调字段。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    project_id: str
    title: str
    mode: Literal["independent"] = "independent"
    effective_status: DeconstructionEffectiveStatus
    run_status: DeconstructionRunStatus = "none"
    source_match: bool = False
    progress: DeconstructionProgress = Field(default_factory=DeconstructionProgress)
    source: DeconstructionSource = Field(default_factory=DeconstructionSource)
    active_run: DeconstructionActiveRun | None = None
    result: DeconstructionResult | None = None
    error: DeconstructionError | None = None
    actions: DeconstructionActions = Field(default_factory=DeconstructionActions)
    history: list[DeconstructionHistoryItem] = Field(default_factory=list)
    # 兼容阶段 31A 客户端；这些字段始终由 canonical state 同步生成。
    status: DeconstructionEffectiveStatus
    progress_percent: int = Field(default=0, ge=0, le=100)
    current_stage: str = "等待拆解"
    source_version_id: str | None = None
    source_revision: int | None = Field(default=None, ge=0)
    source_hash: str | None = None
    analysis_label: str = "确定性结构拆解（无模型）"
    empty_reason: str | None = None
    error_message: str | None = None
    retryable: bool = False
    initialized: bool = False
    deconstruction: DeconstructionState | None = None
    # 路由使用去除 account_id 的公开投影；内部文档模型不能直接作为浏览器合同。
    document: DeconstructionDocumentPublic | None = None

    @model_validator(mode="after")
    def validate_canonical_projection(self) -> "DeconstructionResponse":
        """拒绝顶层兼容字段与 canonical state 互相矛盾的公开响应。"""

        if self.status != self.effective_status:
            raise ValueError("status 必须与 effective_status 一致")
        if self.progress_percent != self.progress.percent or self.current_stage != self.progress.current_stage:
            raise ValueError("兼容进度字段必须与 progress 一致")
        if (
            self.source_version_id != self.source.version_id
            or self.source_revision != self.source.revision
            or self.source_hash != self.source.hash
            or self.source_match != self.source.match
        ):
            raise ValueError("兼容来源字段必须与 source 一致")
        if self.effective_status != "completed" and self.result is not None:
            raise ValueError("非 completed 状态不得返回正式 result")
        if self.result is not None and (not self.source_match or self.run_status != "completed"):
            raise ValueError("result 必须绑定当前来源且运行已完成")
        if self.deconstruction is not None:
            if (
                self.deconstruction.effective_status != self.effective_status
                or self.deconstruction.run_status != self.run_status
                or self.deconstruction.source_match != self.source_match
                or self.deconstruction.result != self.result
            ):
                raise ValueError("嵌套 deconstruction 必须与顶层 canonical state 一致")
        if self.active_run is not None and self.active_run.run_status != self.run_status:
            raise ValueError("active_run 必须与 run_status 一致")
        if self.effective_status in {"empty", "stale", "rebuild_required"} and self.document is not None:
            raise ValueError("空态或来源非当前状态不得返回当前 document")
        report = self.result.report if self.result is not None else None
        document_report = self.document.report if self.document is not None else None
        if document_report is not None and document_report != report:
            raise ValueError("document report must equal canonical result report")
        if report is not None:
            if (report.source.project_id != self.project_id
                    or report.source.source_version_id != self.source.version_id
                    or report.source.source_revision != self.source.revision
                    or report.source.source_hash != self.source.hash):
                raise ValueError("report must match canonical project and source")
            if self.active_run is None:
                raise ValueError("depth report requires its completed active run")
            for key in ("document_id", "source_version_id", "source_revision", "source_hash"):
                if getattr(self.active_run, key) != getattr(report.source, key):
                    raise ValueError("depth report active run mismatch")
            if self.document is not None and document_report != report:
                raise ValueError("legacy document projection cannot drop a depth report")
        return self


class DeconstructionEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    title: str
    evidence: EvidenceRef | DepthEvidence
    chapter: DeconstructionEvidenceChapter
    source_matches_current: bool = False
    historical: bool = True

    @model_validator(mode="after")
    def validate_depth_evidence(self) -> "DeconstructionEvidenceResponse":
        if isinstance(self.evidence, DepthEvidence):
            if (self.project_id != self.evidence.project_id
                    or self.chapter.chapter_id != self.evidence.chapter_id
                    or self.chapter.chapter_number != self.evidence.chapter_number):
                raise ValueError("depth evidence response source mismatch")
            if self.historical == self.source_matches_current:
                raise ValueError("historical evidence cannot match current source")
            if self.source_matches_current and not self.chapter.source_available:
                raise ValueError("current evidence requires an available source")
        return self


class DeconstructionActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    idempotency_key: str | None = Field(default=None, max_length=160)
    expected_source_version_id: str | None = Field(default=None, max_length=160)
    expected_source_revision: int | None = Field(default=None, ge=0)
    expected_source_hash: str | None = Field(default=None, min_length=16, max_length=128)
