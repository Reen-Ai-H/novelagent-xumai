"""Small model-authored changes for a reading segment or final synthesis."""

from typing import Literal

from pydantic import Field

from schemas.analysis_report import (
    Character, CharacterInsight, CharacterRelation, Event, Finding, Relation, ReportEvidence, StrictModel,
)


class RelationKey(StrictModel):
    """Exact key of an existing relation; endpoints use canonical event IDs."""

    from_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    to_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    kind: Literal["causes", "enables", "reveals", "foreshadow_payoff", "follows"]


class AnalysisDelta(StrictModel):
    # New IDs are temporary references within this response. Revisions name a
    # canonical ID from the compact index supplied to the model.
    new_evidence: list[ReportEvidence] = Field(default_factory=list, max_length=60)
    revised_evidence: list[ReportEvidence] = Field(default_factory=list, max_length=60)
    new_findings: list[Finding] = Field(default_factory=list, max_length=20)
    revised_findings: list[Finding] = Field(default_factory=list, max_length=20)
    new_characters: list[Character] = Field(default_factory=list, max_length=30)
    revised_characters: list[Character] = Field(default_factory=list, max_length=30)
    new_events: list[Event] = Field(default_factory=list, max_length=50)
    revised_events: list[Event] = Field(default_factory=list, max_length=50)
    new_relations: list[Relation] = Field(default_factory=list, max_length=60)
    withdrawn_relations: list[RelationKey] = Field(default_factory=list, max_length=60)
    new_character_relations: list[CharacterRelation] = Field(default_factory=list, max_length=60)
    withdrawn_character_relations: list["CharacterRelationKey"] = Field(default_factory=list, max_length=60)
    withdrawn_ids: list[str] = Field(default_factory=list, max_length=60)
    # Optional means "no change". Empty lists can intentionally clear a set.
    story_order: list[str] | None = Field(default=None, max_length=300)
    open_questions: list[str] | None = Field(default=None, max_length=30)
    contradictions: list[CharacterInsight] | None = Field(default=None, max_length=30)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    time_note: str | None = Field(default=None, min_length=1, max_length=500)


class CharacterRelationKey(StrictModel):
    from_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    to_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    label: str = Field(min_length=1, max_length=40)


AnalysisDelta.model_rebuild()
