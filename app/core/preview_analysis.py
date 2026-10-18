"""Private two-pass preview wire. Structural witnesses are not an entailment oracle."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.core.analysis_grounding import PreviewGroundedReport, bind_preview_selections, source_id
from schemas.analysis_report import StrictModel


class FactPerson(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=80)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    source_ids: list[str] = Field(min_length=1, max_length=12)


class FactAtom(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    subject_id: str | None
    object_id: str | None
    text: str = Field(min_length=1, max_length=300)
    kind: Literal["action", "state", "knowledge", "feeling"]
    status: Literal["fact", "reported", "inferred", "unknown"]
    phase: Literal["actual", "planned", "requested", "negated", "unknown"]
    time_anchor: str = Field(min_length=1, max_length=120)
    source_ids: list[str] = Field(min_length=1, max_length=12)


class FactCue(StrictModel):
    """A local textual cue, not a final report edge or a whole-scene dependency."""
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    kind: Literal["cause", "purpose", "before", "character", "reveal", "echo"]
    from_atom_id: str
    to_atom_id: str | None
    text: str = Field(min_length=1, max_length=240)
    status: Literal["fact", "reported", "inferred", "unknown"]
    source_ids: list[str] = Field(min_length=1, max_length=12)


class PreviewFacts(StrictModel):
    chapter_numbers: list[int] = Field(min_length=1, max_length=20)
    characters: list[FactPerson] = Field(min_length=1, max_length=100)
    atoms: list[FactAtom] = Field(min_length=1, max_length=300)
    cues: list[FactCue] = Field(max_length=300)


class FieldSupport(StrictModel):
    # Stable object IDs rather than repeated natural-language self-reviews.
    key: str = Field(min_length=1, max_length=120)
    fact_ids: list[str] = Field(min_length=1, max_length=20)
    # Orthogonal to epistemic status: a factual statement about a plan does
    # not turn its target action into a completed event.
    phases: list[Literal["actual", "planned", "requested", "negated", "unknown"]] = Field(default_factory=list, max_length=5)


class EventBinding(StrictModel):
    event_id: str
    atom_ids: list[str] = Field(min_length=1, max_length=60)


class EdgeBinding(StrictModel):
    # r0 / cr0 are zero-based report relation positions.
    key: str = Field(pattern=r"^(?:r|cr)[0-9]+$")
    cue_id: str


class CueResolution(StrictModel):
    cue_id: str
    # A relation key, a containing event ID, or null with a reason.
    target: str | None
    reason: str | None = Field(default=None, min_length=1, max_length=240)


class PreviewCheckedReport(StrictModel):
    report: PreviewGroundedReport
    supports: list[FieldSupport] = Field(min_length=1, max_length=3000)
    event_bindings: list[EventBinding] = Field(min_length=1, max_length=300)
    edge_bindings: list[EdgeBinding] = Field(max_length=1200)
    cue_resolutions: list[CueResolution] = Field(max_length=300)


def _unique(items, label):
    if len(items) != len(set(items)):
        raise ValueError(label)


def _source_check(keys, bank, read_text):
    for key in keys:
        passage = bank.get(key)
        if passage is None or passage.id != key:
            raise ValueError("事实引用了未提供的来源")
        body = read_text.get(passage.chapter_number, "")
        if (key != source_id(passage.chapter_number, passage.quote)
                or not 0 <= passage.start < passage.end <= len(body)
                or body[passage.start:passage.end] != passage.quote
                or body.find(passage.quote) != passage.start
                or body.find(passage.quote, passage.start + 1) >= 0):
            raise ValueError("事实来源不在同一原文中唯一匹配")


def _assert_dag(nodes, edges):
    outgoing = {node: set() for node in nodes}
    indegree = dict.fromkeys(nodes, 0)
    for start, end in edges:
        if start == end:
            raise ValueError("时间依赖自环")
        if end not in outgoing[start]:
            outgoing[start].add(end)
            indegree[end] += 1
    ready = [node for node in nodes if indegree[node] == 0]
    visited = 0
    while ready:
        node = ready.pop()
        visited += 1
        for end in outgoing[node]:
            indegree[end] -= 1
            if indegree[end] == 0:
                ready.append(end)
    if visited != len(nodes):
        raise ValueError("已知时间依赖循环")


def _actual_dependency(cue, atoms):
    if cue.status not in {"fact", "reported"} or cue.kind not in {"cause", "purpose", "before"}:
        return False
    # A textual before cue may order plans or requests as such, whereas
    # purpose/cause only constrains actual action chronology when both happen.
    return cue.kind == "before" or all(atoms[key].phase == "actual" for key in (cue.from_atom_id, cue.to_atom_id))


def freeze_preview_facts(data, bank, read_text):
    """Validate after structured(), so semantic/reference failures never trigger repair."""
    facts = PreviewFacts.model_validate(data, strict=True)
    if len(set(facts.chapter_numbers)) != len(facts.chapter_numbers) or set(facts.chapter_numbers) != set(read_text):
        raise ValueError("事实章节范围不一致")
    people = {person.id: person for person in facts.characters}
    atoms = {atom.id: atom for atom in facts.atoms}
    _unique([item.id for item in [*facts.characters, *facts.atoms, *facts.cues]], "事实ID重复")
    for item in [*facts.characters, *facts.atoms, *facts.cues]:
        _source_check(item.source_ids, bank, read_text)
    for person in facts.characters:
        _unique(person.aliases, "人物别名重复")
    for atom in facts.atoms:
        if any(key is not None and key not in people for key in (atom.subject_id, atom.object_id)):
            raise ValueError("事实人物端点不存在")
        if atom.kind in {"knowledge", "feeling"} and atom.subject_id is None:
            raise ValueError("知情和情感须明确持有者")
    for cue in facts.cues:
        if cue.from_atom_id not in atoms or (cue.to_atom_id is not None and cue.to_atom_id not in atoms):
            raise ValueError("线索动作端点不存在")
        if cue.kind == "character":
            atom = atoms[cue.from_atom_id]
            if cue.to_atom_id is not None or atom.subject_id is None or atom.object_id is None or atom.subject_id == atom.object_id:
                raise ValueError("人物线索须绑定单个有向事实")
        elif cue.to_atom_id is None or cue.to_atom_id == cue.from_atom_id:
            raise ValueError("线索须绑定两个不同原子动作")
    dependencies = [(cue.from_atom_id, cue.to_atom_id) for cue in facts.cues if _actual_dependency(cue, atoms)]
    _assert_dag(atoms, dependencies)
    # An immutable string is the stage boundary. Never hand a mutable model to
    # the runtime or let the second stage edit the first stage's dictionaries.
    return facts.model_dump_json()


def _claims(report):
    for item in report.findings:
        yield item.id, item, None
    for person in report.characters:
        for name in ("identity", "motivation", "change", "portrait"):
            claim = getattr(person, name)
            if claim is not None:
                yield f"{person.id}.{name}", claim, person.id
        for index, claim in enumerate(person.insights):
            yield f"{person.id}.insights.{index}", claim, person.id
    for event in report.events:
        yield f"{event.id}.action", event.action, event.id
        yield f"{event.id}.consequence", event.consequence, event.id
        for index, claim in enumerate(event.sub_events):
            yield f"{event.id}.sub_events.{index}", claim, event.id
    for prefix, group in (("r", report.relations), ("cr", report.character_relations), ("x", report.contradictions)):
        for index, claim in enumerate(group):
            yield f"{prefix}{index}", claim, None


def bind_checked_preview(data, frozen, bank, read_text, *, producer):
    checked = PreviewCheckedReport.model_validate(data, strict=True)
    facts = PreviewFacts.model_validate_json(frozen, strict=True)
    validate_checked_core(checked, {person.id: person for person in facts.characters},
                          {atom.id: atom for atom in facts.atoms}, {cue.id: cue for cue in facts.cues},
                          chapter_numbers=facts.chapter_numbers)
    return bind_preview_selections(checked.report.model_dump(mode="json"), bank, read_text, producer=producer)


def validate_checked_core(checked, people, atoms, cues, *, chapter_numbers,
                          entity_for=None, visible_ids=None, support_people=None):
    """Shared strict graph checks. Legacy callers retain identity/all-visible defaults.

    A chapter adapter must validate its complete mapping before supplying it;
    atoms themselves are never rewritten, including null endpoints or phases.
    """
    def resolve(key):
        return key if entity_for is None or key is None else entity_for[key]

    visible = set(people) if visible_ids is None else set(visible_ids)
    report = checked.report
    all_facts = {**(people if support_people is None else support_people), **atoms, **cues}
    if set(report.chapter_numbers) != set(chapter_numbers):
        raise ValueError("报告章节偏离事实包")
    if {person.id for person in report.characters} != visible:
        raise ValueError("报告人物偏离事实包")
    for person in report.characters:
        fact = people[person.id]
        if person.name != fact.name or person.aliases != fact.aliases:
            raise ValueError("人物姓名与ID或别名不一致")
    _unique([item.event_id for item in checked.event_bindings], "事件映射重复")
    event_atoms = {item.event_id: set(item.atom_ids) for item in checked.event_bindings}
    events = {event.id: event for event in report.events}
    if set(event_atoms) != set(events):
        raise ValueError("事件映射缺漏")
    for binding in checked.event_bindings:
        _unique(binding.atom_ids, "事件动作映射重复")
        if not event_atoms[binding.event_id] <= atoms.keys():
            raise ValueError("事件映射了不存在的动作")
        participants = {resolve(key) for atom_id in binding.atom_ids for key in
                        (atoms[atom_id].subject_id, atoms[atom_id].object_id) if key is not None}
        if not set(events[binding.event_id].actor_ids) <= participants & visible:
            raise ValueError("事件人物不在映射动作中")
        if visible_ids is not None:
            required = {resolve(atoms[key].subject_id) for key in binding.atom_ids
                        if atoms[key].kind == "action" and atoms[key].subject_id is not None} & visible
            if not required <= set(events[binding.event_id].actor_ids):
                raise ValueError("事件已显示行动主体缺漏")
    _unique([item.key for item in checked.supports], "字段映射重复")
    supports = {item.key: item.fact_ids for item in checked.supports}
    claims = list(_claims(report))
    _unique([key for key, _, _ in claims], "报告字段映射键冲突")
    if set(supports) != {key for key, _, _ in claims}:
        raise ValueError("字段映射缺漏或多余")
    evidence = {selection.id: selection.source_id for selection in report.evidence}
    phases = {item.key: item.phases for item in checked.supports}
    for key, claim, owner in claims:
        ids = supports[key]
        _unique(ids, "字段事实映射重复")
        if not set(ids) <= all_facts.keys():
            raise ValueError("字段映射了不存在的事实")
        allowed_sources = {source for fact_id in ids for source in all_facts[fact_id].source_ids}
        # Check the actual report citations, not merely a parallel attachment.
        if any(evidence.get(q) not in allowed_sources for q in claim.evidence_ids):
            raise ValueError("报告实际引文不在对应事实中")
        selected_sources = {evidence.get(q) for q in claim.evidence_ids}
        if any(not selected_sources.intersection(all_facts[fact_id].source_ids) for fact_id in ids):
            raise ValueError("报告实际引文未覆盖所映射事实")
        mapped_atoms = [atoms[fact_id] for fact_id in ids if fact_id in atoms]
        _unique(phases[key], "字段行动阶段重复")
        if set(phases[key]) != {atom.phase for atom in mapped_atoms}:
            raise ValueError("字段声明行动阶段偏离冻结事实")
        if owner in events:
            if not mapped_atoms or not {atom.id for atom in mapped_atoms} <= event_atoms[owner]:
                raise ValueError("事件字段映射超出本事件动作")
            for fact_id in ids:
                fact = all_facts[fact_id]
                if isinstance(fact, FactPerson) or (isinstance(fact, FactCue)
                        and not {fact.from_atom_id, fact.to_atom_id} <= event_atoms[owner]):
                    raise ValueError("事件字段借用了其他对象来源")
            subjects = {resolve(atom.subject_id) for atom in mapped_atoms if atom.subject_id is not None}
            if visible_ids is not None:
                subjects &= visible
            if key == f"{owner}.action" and not subjects <= set(events[owner].actor_ids):
                raise ValueError("事件行动主体缺漏")
        if owner in people:
            for fact_id in ids:
                fact = all_facts[fact_id]
                if isinstance(fact, FactPerson) and resolve(fact.id) != owner:
                    raise ValueError("人物字段串用其他身份")
                if isinstance(fact, FactAtom) and owner not in (resolve(fact.subject_id), resolve(fact.object_id)):
                    raise ValueError("人物判断的主体与映射不一致")
                if (entity_for is not None and isinstance(fact, FactAtom) and fact.kind in {"knowledge", "feeling"}
                        and resolve(fact.subject_id) != owner):
                    raise ValueError("知情或情感只能属于冻结持有者")
                if isinstance(fact, FactCue):
                    raise ValueError("人物判断须映射自身身份或主体事实")
        if claim.status == "fact" and any(getattr(all_facts[fact_id], "status", "fact") != "fact" for fact_id in ids):
            raise ValueError("报告将传闻推断或未知提升为事实")
    _unique([binding.key for binding in checked.edge_bindings], "关系映射重复")
    edges = {binding.key: binding.cue_id for binding in checked.edge_bindings}
    expected_edges = {f"r{i}" for i in range(len(report.relations))} | {f"cr{i}" for i in range(len(report.character_relations))}
    if set(edges) != expected_edges or any(cue_id not in cues for cue_id in edges.values()):
        raise ValueError("关系线索映射缺漏")
    kind_map = {"cause": "causes", "purpose": "enables", "before": "follows", "reveal": "reveals", "echo": "foreshadow_payoff"}
    for key, cue_id in edges.items():
        cue = cues[cue_id]
        if cue_id not in supports[key]:
            raise ValueError("关系判断未绑定连接依据")
        required = {cue.id, cue.from_atom_id}
        if cue.to_atom_id is not None:
            required.add(cue.to_atom_id)
        if set(supports[key]) != required:
            raise ValueError("关系须恰好映射连接依据与实际动作")
        if key.startswith("cr"):
            edge = report.character_relations[int(key[2:])]
            atom = atoms[cue.from_atom_id]
            if cue.kind != "character" or (edge.from_id, edge.to_id) != (resolve(atom.subject_id), resolve(atom.object_id)):
                raise ValueError("人物关系身份或方向与事实不一致")
        else:
            edge = report.relations[int(key[1:])]
            if (kind_map.get(cue.kind) != edge.kind or edge.from_id not in event_atoms or edge.to_id not in event_atoms
                    or cue.from_atom_id not in event_atoms[edge.from_id] or cue.to_atom_id not in event_atoms[edge.to_id]):
                raise ValueError("关系动作端点或方向与事实不一致")
        # The edge itself must cite the cue that establishes the connection,
        # rather than just valid quotations proving that its endpoints exist.
        if not {evidence.get(q) for q in edge.evidence_ids}.intersection(cue.source_ids):
            raise ValueError("关系实际引文未覆盖连接依据")
    _unique([item.cue_id for item in checked.cue_resolutions], "线索处理重复")
    if {item.cue_id for item in checked.cue_resolutions} != set(cues):
        raise ValueError("明确线索未逐项处理")
    for resolution in checked.cue_resolutions:
        cue = cues[resolution.cue_id]
        if resolution.target is None:
            planned_purpose = cue.kind == "purpose" and atoms[cue.to_atom_id].phase != "actual"
            if (not resolution.reason or (cue.status not in {"inferred", "unknown"} and not planned_purpose)
                    or resolution.cue_id in edges.values()):
                raise ValueError("明确线索不能以空关系回避")
            notes = report.time_note if cue.kind == "before" else "\n".join(report.open_questions)
            if resolution.reason not in notes:
                raise ValueError("未决线索须在报告中保留理由")
        elif resolution.reason is not None:
            raise ValueError("已覆盖线索不能同时声明未决")
        elif resolution.target in edges:
            if edges[resolution.target] != cue.id:
                raise ValueError("线索处理串绑其他关系")
        elif resolution.target in event_atoms and cue.kind != "character":
            if not {cue.from_atom_id, cue.to_atom_id} <= event_atoms[resolution.target]:
                raise ValueError("合并场景未包含线索实际动作")
            if not any(key.startswith(resolution.target + ".") and cue.id in ids for key, ids in supports.items()):
                raise ValueError("合并场景未引用内部连接依据")
        else:
            raise ValueError("线索处理目标无效")
    # Only known local dependencies constrain ordering. Unrelated atomic
    # actions need not become separate visible report events.
    positions = {event_id: index for index, event_id in enumerate(report.story_order)}
    dependencies = []
    for cue in cues.values():
        if not _actual_dependency(cue, atoms):
            continue
        for start, first in event_atoms.items():
            for end, second in event_atoms.items():
                if start != end and cue.from_atom_id in first and cue.to_atom_id in second:
                    dependencies.append((start, end))
    _assert_dag(events, dependencies)
    if any(positions.get(start, -1) >= positions.get(end, -1) for start, end in dependencies):
        raise ValueError("报告故事顺序倒置已知依赖")
