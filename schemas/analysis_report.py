"""Model-authored analysis; code validates structure and evidence, never invents semantics."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Claim(StrictModel):
    text: str = Field(min_length=1, max_length=1200)
    status: Literal["fact", "reported", "inferred", "unknown"]
    evidence_ids: list[str] = Field(min_length=1, max_length=12)


class Finding(Claim):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    title: str = Field(min_length=1, max_length=80)


class CharacterInsight(Claim):
    title: str = Field(min_length=1, max_length=80)


class Character(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=80)
    identity: Claim
    motivation: Claim
    change: Claim
    portrait: Claim | None = None
    insights: list[CharacterInsight] = Field(default_factory=list, max_length=8)


class Event(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    title: str = Field(min_length=1, max_length=80)
    chapter_number: int = Field(ge=1)
    chapter_end: int | None = Field(default=None, ge=1)
    story_time: str = Field(min_length=1, max_length=160)
    actor_ids: list[str] = Field(max_length=20)
    action: Claim
    consequence: Claim


class Relation(Claim):
    from_id: str
    to_id: str
    kind: Literal["causes", "enables", "reveals", "foreshadow_payoff", "follows"]


class ReportEvidence(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    chapter_number: int = Field(ge=1)
    quote: str = Field(min_length=2, max_length=180)


class AnalysisReport(StrictModel):
    schema_version: Literal["1"] = "1"
    producer: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    scope: str = Field(min_length=1, max_length=500)
    chapter_numbers: list[int] = Field(min_length=1, max_length=500)
    findings: list[Finding] = Field(min_length=1, max_length=20)
    characters: list[Character] = Field(min_length=1, max_length=100)
    events: list[Event] = Field(min_length=1, max_length=300)
    relations: list[Relation] = Field(max_length=600)
    story_order: list[str] = Field(min_length=1, max_length=300)
    time_note: str = Field(min_length=1, max_length=500)
    evidence: list[ReportEvidence] = Field(min_length=1, max_length=500)
    open_questions: list[str] = Field(max_length=30)
    contradictions: list[CharacterInsight] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def valid_references(self):
        ids = [x.id for group in (self.findings, self.characters, self.events, self.evidence) for x in group]
        if len(ids) != len(set(ids)):
            raise ValueError("分析 ID 重复")
        chapters = set(self.chapter_numbers)
        if len(chapters) != len(self.chapter_numbers) or any(n < 1 for n in chapters):
            raise ValueError("阅读章节范围无效")
        evidence_ids = {x.id for x in self.evidence}
        character_ids = {x.id for x in self.characters}
        event_ids = {x.id for x in self.events}
        claims = [*self.findings, *self.relations, *self.contradictions]
        for person in self.characters:
            claims.extend((person.identity, person.motivation, person.change))
            claims.extend(person.insights)
            if person.portrait is not None:
                claims.append(person.portrait)
        for event in self.events:
            if event.chapter_end is not None and (event.chapter_end < event.chapter_number or not set(range(event.chapter_number, event.chapter_end + 1)) <= chapters):
                raise ValueError("剧情章节范围超出已读范围")
            if event.chapter_number not in chapters or not set(event.actor_ids) <= character_ids:
                raise ValueError("事件章节或人物引用无效")
            claims.extend((event.action, event.consequence))
        if any(not set(x.evidence_ids) <= evidence_ids for x in claims):
            raise ValueError("判断引用了不存在的证据")
        if any(x.chapter_number not in chapters for x in self.evidence):
            raise ValueError("证据超出已读范围")
        if any(x.from_id not in event_ids or x.to_id not in event_ids or x.from_id == x.to_id for x in self.relations):
            raise ValueError("剧情连线端点无效")
        if len(self.story_order) != len(event_ids) or set(self.story_order) != event_ids:
            raise ValueError("故事时间线必须覆盖每个事件一次")
        return self


class AnalysisImport(StrictModel):
    expected_source_version_id: str = Field(min_length=1, max_length=128)
    expected_source_revision: int = Field(ge=0)
    expected_source_hash: str = Field(min_length=16, max_length=128)
    report: AnalysisReport


class AnalysisRequest(StrictModel):
    expected_source_version_id: str = Field(min_length=1, max_length=128)
    expected_source_revision: int = Field(ge=0)
    expected_source_hash: str = Field(min_length=16, max_length=128)
    chapter_numbers: list[int] = Field(min_length=1, max_length=20)
