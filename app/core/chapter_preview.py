"""Bounded chapter extraction and one final outcome; no persistence or model runtime."""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import Field, RootModel

from app.core.analysis_grounding import bind_preview_selections
from app.core.preview_analysis import (
    FactPerson, FactAtom, FactCue, PreviewCheckedReport, _source_check, _unique,
    _assert_dag, _actual_dependency, validate_checked_core,
)
from schemas.analysis_report import StrictModel


CHAPTER_MAX_TOKENS = 12288
MAX_LOCAL_PEOPLE, MAX_LOCAL_ATOMS = 100, 150
MAX_TOTAL_PEOPLE, MAX_TOTAL_ATOMS = 300, 600
LOCAL_ID = r"^[A-Za-z][A-Za-z0-9_-]{0,47}$"


class LocalPerson(FactPerson):
    id: str = Field(pattern=LOCAL_ID)


class LocalAtom(FactAtom):
    id: str = Field(pattern=LOCAL_ID)


class ChapterFacts(StrictModel):
    chapter_number: int = Field(ge=1, le=999999999)
    characters: list[LocalPerson] = Field(max_length=MAX_LOCAL_PEOPLE)
    atoms: list[LocalAtom] = Field(min_length=1, max_length=MAX_LOCAL_ATOMS)


class FrozenChapter(StrictModel):
    chapter_number: int = Field(ge=1, le=999999999)
    characters: list[FactPerson] = Field(max_length=MAX_LOCAL_PEOPLE)
    atoms: list[FactAtom] = Field(min_length=1, max_length=MAX_LOCAL_ATOMS)


class UnifiedEntity(FactPerson):
    members: list[str] = Field(min_length=1, max_length=MAX_TOTAL_PEOPLE)
    # One source for each member may exceed the old single-packet limit of
    # twelve; this is private identity evidence, not public claim citations.
    source_ids: list[str] = Field(min_length=1, max_length=MAX_TOTAL_PEOPLE)
    role: Literal["main", "support", "internal"]
    basis: str = Field(min_length=1, max_length=300)


class QuestionBinding(StrictModel):
    index: int = Field(ge=0, le=29)
    fact_ids: list[str] = Field(min_length=1, max_length=20)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)
    phases: list[Literal["actual", "planned", "requested", "negated", "unknown"]] = Field(max_length=5)


class ChapterSuccess(PreviewCheckedReport):
    outcome: Literal["success"]
    entities: list[UnifiedEntity] = Field(min_length=1, max_length=MAX_TOTAL_PEOPLE)
    cues: list[FactCue] = Field(max_length=300)
    questions: list[QuestionBinding] = Field(max_length=30)


class BlockingIssue(StrictModel):
    text: str = Field(min_length=1, max_length=500)
    source_ids: list[str] = Field(min_length=1, max_length=12)
    fact_ids: list[str] = Field(default_factory=list, max_length=20)


class ChapterBlocked(StrictModel):
    outcome: Literal["blocked"]
    issues: list[BlockingIssue] = Field(min_length=1, max_length=12)


class ChapterOutcome(RootModel[Annotated[ChapterSuccess | ChapterBlocked, Field(discriminator="outcome")]]):
    pass


def namespace_id(chapter_number, local_id):
    if type(chapter_number) is not int or not 1 <= chapter_number <= 999999999 or not re.fullmatch(LOCAL_ID, local_id):
        raise ValueError("章级ID超界或无效")
    return f"H{chapter_number}_{local_id}"


def split_namespaced_id(key):
    match = re.fullmatch(r"H([1-9][0-9]{0,8})_([A-Za-z][A-Za-z0-9_-]{0,47})", key)
    if match is None:
        raise ValueError("命名空间ID无效")
    return int(match[1]), match[2]


def freeze_chapter(data, bank, read_text):
    packet = ChapterFacts.model_validate(data, strict=True)
    if set(read_text) != {packet.chapter_number}:
        raise ValueError("章包章节范围不一致")
    _unique([item.id for item in [*packet.characters, *packet.atoms]], "章包局部ID重复")
    people = {person.id for person in packet.characters}
    for item in [*packet.characters, *packet.atoms]:
        _source_check(item.source_ids, bank, read_text)
    for atom in packet.atoms:
        if any(key is not None and key not in people for key in (atom.subject_id, atom.object_id)):
            raise ValueError("事实人物端点不存在")
        if atom.kind in {"knowledge", "feeling"} and atom.subject_id is None:
            raise ValueError("知情和情感须明确持有者")
    for person in packet.characters:
        _unique(person.aliases, "人物别名重复")
    payload = packet.model_dump(mode="json")
    for person in payload["characters"]:
        person["id"] = namespace_id(packet.chapter_number, person["id"])
    for atom in payload["atoms"]:
        atom["id"] = namespace_id(packet.chapter_number, atom["id"])
        for field in ("subject_id", "object_id"):
            if atom[field] is not None:
                atom[field] = namespace_id(packet.chapter_number, atom[field])
    return FrozenChapter.model_validate(payload, strict=True).model_dump_json()


def chapter_index(frozen):
    if not 1 <= len(frozen) <= 20:
        raise ValueError("冻结章包数量超界")
    packets = [FrozenChapter.model_validate_json(item, strict=True) for item in frozen]
    _unique([p.chapter_number for p in packets], "冻结章包章节重复")
    people, atoms = {}, {}
    for packet in packets:
        packet_people = {p.id for p in packet.characters}
        for item in [*packet.characters, *packet.atoms]:
            if split_namespaced_id(item.id)[0] != packet.chapter_number:
                raise ValueError("冻结ID与章节不一致")
        for atom in packet.atoms:
            if any(key is not None and key not in packet_people for key in (atom.subject_id, atom.object_id)):
                raise ValueError("冻结原子事实人物引用无效")
            if atom.kind in {"knowledge", "feeling"} and atom.subject_id is None:
                raise ValueError("冻结知情或情感缺少持有者")
        _unique([item.id for item in [*packet.characters, *packet.atoms]], "冻结ID重复")
        people.update((p.id, p) for p in packet.characters)
        atoms.update((a.id, a) for a in packet.atoms)
    if len(people) > MAX_TOTAL_PEOPLE or len(atoms) > MAX_TOTAL_ATOMS:
        raise ValueError("章包合计结构超界")
    return packets, people, atoms


def _check_sources_for_support(ids, evidence_ids, all_facts, evidence):
    _unique(ids, "事实支持重复")
    if not ids or not set(ids) <= all_facts.keys():
        raise ValueError("未解项事实引用无效")
    allowed = {source for key in ids for source in all_facts[key].source_ids}
    selected = {evidence.get(key) for key in evidence_ids}
    if not selected or not selected <= allowed:
        raise ValueError("未解项实际证据不在对应事实中")
    if any(not selected.intersection(all_facts[key].source_ids) for key in ids):
        raise ValueError("未解项实际证据未覆盖对应事实")


def bind_chapter_outcome(data, frozen, bank, read_text, *, producer):
    outcome = ChapterOutcome.model_validate(data, strict=True).root
    packets, local_people, atoms = chapter_index(frozen)
    if {p.chapter_number for p in packets} != set(read_text):
        raise ValueError("冻结章包与完整来源不一致")
    for packet in packets:
        for fact in [*packet.characters, *packet.atoms]:
            _source_check(fact.source_ids, bank, {packet.chapter_number: read_text[packet.chapter_number]})
    if isinstance(outcome, ChapterBlocked):
        for issue in outcome.issues:
            _source_check(issue.source_ids, bank, read_text)
            if not set(issue.fact_ids) <= local_people.keys() | atoms.keys():
                raise ValueError("阻断问题引用不存在的事实")
        return outcome

    _unique([e.id for e in outcome.entities], "统一人物ID重复")
    members = [member for entity in outcome.entities for member in entity.members]
    _unique(members, "局部人物重复映射")
    if set(members) != set(local_people):
        raise ValueError("局部人物映射缺漏或多余")
    entities = {entity.id: entity for entity in outcome.entities}
    entity_for = {member: entity.id for entity in outcome.entities for member in entity.members}
    _unique([*local_people, *atoms, *entities, *[cue.id for cue in outcome.cues],
             *[item.id for group in (outcome.report.findings, outcome.report.events, outcome.report.evidence) for item in group]],
            "全局支持ID冲突")
    for entity in outcome.entities:
        _unique(entity.aliases, "统一别名重复")
        _source_check(entity.source_ids, bank, read_text)
        names = {name for member in entity.members for name in
                 (local_people[member].name, *local_people[member].aliases)}
        if entity.name not in names or not set(entity.aliases) <= names:
            raise ValueError("统一人物姓名或别名无来源")
        if any(not set(entity.source_ids).intersection(local_people[member].source_ids) for member in entity.members):
            raise ValueError("身份依据未覆盖每个成员")
    cues = {cue.id: cue for cue in outcome.cues}
    for cue in outcome.cues:
        _source_check(cue.source_ids, bank, read_text)
        if cue.from_atom_id not in atoms or (cue.to_atom_id is not None and cue.to_atom_id not in atoms):
            raise ValueError("全局线索动作端点不存在")
        if cue.kind == "character":
            atom = atoms[cue.from_atom_id]
            if (cue.to_atom_id is not None or atom.subject_id is None or atom.object_id is None
                    or entity_for[atom.subject_id] == entity_for[atom.object_id]):
                raise ValueError("人物线索须绑定明确有向人物事实")
        elif cue.to_atom_id is None or cue.to_atom_id == cue.from_atom_id:
            raise ValueError("线索须绑定两个不同原子动作")
    _assert_dag(atoms, [(c.from_atom_id, c.to_atom_id) for c in outcome.cues if _actual_dependency(c, atoms)])
    visible = {e.id for e in outcome.entities if e.role != "internal"}
    validate_checked_core(outcome, entities, atoms, cues, chapter_numbers=[p.chapter_number for p in packets],
                          entity_for=entity_for, visible_ids=visible, support_people=local_people)
    evidence = {e.id: e.source_id for e in outcome.report.evidence}
    all_facts = {**local_people, **atoms, **cues}
    _unique([q.index for q in outcome.questions], "未解项映射重复")
    if {q.index for q in outcome.questions} != set(range(len(outcome.report.open_questions))):
        raise ValueError("未解项映射缺漏或多余")
    for question in outcome.questions:
        if not outcome.report.open_questions[question.index].strip():
            raise ValueError("未解项实际文本为空")
        _check_sources_for_support(question.fact_ids, question.evidence_ids, all_facts, evidence)
        _unique(question.phases, "未解项阶段重复")
        mapped = set(question.fact_ids) & atoms.keys()
        if not mapped or set(question.phases) != {atoms[key].phase for key in mapped}:
            raise ValueError("未解项行动阶段与冻结事实不一致")
    report_atoms = {key for support in outcome.supports for key in support.fact_ids if key in atoms}
    question_atoms = {key for q in outcome.questions for key in q.fact_ids if key in atoms}
    if not report_atoms or report_atoms | question_atoms != set(atoms):
        raise ValueError("重要事实缺少实际报告或未解项落点")
    return bind_preview_selections(outcome.report.model_dump(mode="json"), bank, read_text, producer=producer)
