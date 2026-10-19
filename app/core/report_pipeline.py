"""Private report-v2 wire and deterministic checks, never an entailment oracle.

The report's own claims are the fact units. Small inline annotations replace
the separate frozen extraction/support/binding tables. Source review remains
model work; this module never invents a sentence or repairs an identity.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Annotated, Any, Literal

from pydantic import Field, RootModel

from app.core.analysis_grounding import PreviewEvent, PreviewGroundedReport, bind_preview_selections
from app.core.preview_analysis import _assert_dag, _source_check, _unique
from schemas.analysis_report import Character, CharacterRelation, Claim, Relation, StrictModel


REPORT_KIND = "report-v2"
REPORT_LIMIT = 30000
REVIEW_MAX_TOKENS = 8192
VERIFY_MAX_TOKENS = 4096
MAX_REVISION_BYTES = 12 * 1024
ID = r"^[A-Za-z][A-Za-z0-9_-]{0,63}$"
HASH = r"^[a-f0-9]{64}$"
NON_PEOPLE = frozenset(("我", "我们", "咱", "咱们", "俺", "俺们", "你", "你们", "您", "您们",
                        "他", "她", "它", "其", "他们", "她们", "它们", "大家", "众人",
                        "群众", "人群", "大道", "某人", "某某", "自己"))


class DraftClaim(Claim):
    subject_id: str | None
    object_id: str | None
    kind: Literal["action", "state", "knowledge", "feeling"]
    phase: Literal["actual", "planned", "requested", "negated", "unknown"]


class DraftFinding(DraftClaim):
    id: str = Field(pattern=ID)
    title: str = Field(min_length=1, max_length=80)


class DraftDetail(DraftClaim):
    title: str = Field(min_length=1, max_length=80)


class AliasBasis(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)


class Participant(StrictModel):
    id: str = Field(pattern=ID)
    name: str = Field(min_length=1, max_length=80)
    name_evidence_ids: list[str] = Field(min_length=1, max_length=12)


class DraftCharacter(Character):
    identity: DraftClaim
    motivation: DraftClaim
    change: DraftClaim
    portrait: DraftClaim | None = None
    insights: list[DraftDetail] = Field(default_factory=list, max_length=8)
    name_evidence_ids: list[str] = Field(min_length=1, max_length=12)
    alias_basis: list[AliasBasis] = Field(max_length=20)
    importance: Literal["main", "support"] = Field(...)
    importance_basis: Claim


class DraftEvent(PreviewEvent):
    action: DraftClaim
    consequence: DraftClaim
    sub_events: list[DraftDetail] = Field(default_factory=list, max_length=30)


class DraftRelation(Relation):
    from_action: str = Field(min_length=1, max_length=120)
    to_action: str = Field(min_length=1, max_length=120)
    basis: Literal["cause", "purpose", "before", "reveal", "echo"]


class DraftCharacterRelation(CharacterRelation):
    action_ref: str = Field(min_length=1, max_length=120)


class TimeConstraint(StrictModel):
    from_action: str = Field(min_length=1, max_length=120)
    to_action: str = Field(min_length=1, max_length=120)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)


class QuestionSource(StrictModel):
    index: int = Field(ge=0, le=29)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)


class ReportDraft(PreviewGroundedReport):
    findings: list[DraftFinding] = Field(min_length=1, max_length=20)
    characters: list[DraftCharacter] = Field(min_length=1, max_length=100)
    events: list[DraftEvent] = Field(min_length=1, max_length=300)
    relations: list[DraftRelation] = Field(max_length=600)
    character_relations: list[DraftCharacterRelation] = Field(max_length=600)
    contradictions: list[DraftDetail] = Field(default_factory=list, max_length=30)
    participants: list[Participant] = Field(max_length=100)
    order_constraints: list[TimeConstraint] = Field(max_length=300)
    question_sources: list[QuestionSource] = Field(max_length=30)
    time_evidence_ids: list[str] = Field(min_length=1, max_length=12)


class SourceIssue(StrictModel):
    text: str = Field(min_length=1, max_length=500)
    source_ids: list[str] = Field(min_length=1, max_length=12)


class Correction(SourceIssue):
    # Whitelisted whole objects, not executable JSON paths. The corresponding
    # exact model is validated after application, including extra='forbid'.
    target: str = Field(min_length=1, max_length=140)
    before_hash: str | None = Field(pattern=HASH)
    replacement: dict[str, Any] | None


class ReviewAccept(StrictModel):
    decision: Literal["accept"]
    draft_hash: str = Field(pattern=HASH)
    checked_chapters: list[int] = Field(min_length=1, max_length=500)


class ReviewBlocked(StrictModel):
    decision: Literal["blocked"]
    draft_hash: str = Field(pattern=HASH)
    issues: list[SourceIssue] = Field(min_length=1, max_length=12)


class ReviewRevise(StrictModel):
    decision: Literal["revise"]
    draft_hash: str = Field(pattern=HASH)
    changes: list[Correction] = Field(min_length=1, max_length=8)


class ReportReview(RootModel[Annotated[ReviewAccept | ReviewBlocked | ReviewRevise,
                                       Field(discriminator="decision")]]):
    pass


class ReportVerification(RootModel[Annotated[ReviewAccept | ReviewBlocked,
                                             Field(discriminator="decision")]]):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def object_hash(value):
    return sha256(canonical(value).encode("utf-8")).hexdigest()


def _claims(draft):
    for finding in draft.findings:
        yield finding.id, finding, None
    for person in draft.characters:
        for field in ("identity", "motivation", "change", "portrait"):
            claim = getattr(person, field)
            if claim is not None:
                yield f"{person.id}.{field}", claim, person.id
        for i, claim in enumerate(person.insights):
            yield f"{person.id}.insights.{i}", claim, person.id
    for event in draft.events:
        for field in ("action", "consequence"):
            yield f"{event.id}.{field}", getattr(event, field), event.id
        for i, claim in enumerate(event.sub_events):
            yield f"{event.id}.sub_events.{i}", claim, event.id
    for i, claim in enumerate(draft.contradictions):
        yield f"contradictions.{i}", claim, None


def _public_claim(claim, *, title=False, finding=False):
    keys = ["text", "status", "evidence_ids"]
    if title or finding:
        keys.append("title")
    if finding:
        keys.append("id")
    return {key: getattr(claim, key) for key in keys}


def public_wire(draft):
    """An explicit projection after validation; never discard an unknown field."""
    data = {key: getattr(draft, key) for key in
            ("schema_version", "title", "scope", "chapter_numbers", "story_order", "time_note", "open_questions")}
    data["evidence"] = [e.model_dump(mode="json") for e in draft.evidence]
    data["findings"] = [_public_claim(c, finding=True) for c in draft.findings]
    data["characters"] = []
    for person in draft.characters:
        item = {key: getattr(person, key) for key in ("id", "entity_key", "name", "aliases", "role", "importance")}
        for field in ("identity", "motivation", "change", "portrait"):
            claim = getattr(person, field)
            item[field] = _public_claim(claim) if claim is not None else None
        item["insights"] = [_public_claim(c, title=True) for c in person.insights]
        data["characters"].append(item)
    data["events"] = []
    for event in draft.events:
        item = {key: getattr(event, key) for key in ("id", "title", "story_time", "actor_ids")}
        item.update(action=_public_claim(event.action), consequence=_public_claim(event.consequence),
                    sub_events=[_public_claim(c, title=True) for c in event.sub_events])
        data["events"].append(item)
    data["relations"] = [{**_public_claim(c), **{k: getattr(c, k) for k in ("from_id", "to_id", "kind")}}
                         for c in draft.relations]
    data["character_relations"] = [{**_public_claim(c), **{k: getattr(c, k) for k in ("from_id", "to_id", "label")}}
                                   for c in draft.character_relations]
    data["contradictions"] = [_public_claim(c, title=True) for c in draft.contradictions]
    return data


def validate_draft(data, bank, read_text, *, producer):
    draft = ReportDraft.model_validate(data, strict=True)
    if set(draft.chapter_numbers) != set(read_text) or len(draft.chapter_numbers) != len(read_text):
        raise ValueError("报告必须覆盖全部当前正文")
    report = bind_preview_selections(public_wire(draft), bank, read_text, producer=producer)
    evidence = {item.id: bank[item.source_id] for item in draft.evidence}

    def refs(ids):
        if not set(ids) <= evidence.keys() or len(ids) != len(set(ids)):
            raise ValueError("私有支持引用不存在或重复")

    people = {p.id: p for p in [*draft.characters, *draft.participants]}
    _unique([p.id for p in [*draft.characters, *draft.participants]], "人物与内部参与者ID重复")
    public_ids = {item.id for group in (draft.characters, draft.events, draft.findings, draft.evidence) for item in group}
    if any(p.id in public_ids for p in draft.participants):
        raise ValueError("内部参与者ID与公开对象冲突")
    for person in people.values():
        refs(person.name_evidence_ids)
        if person.name in NON_PEOPLE or not any(person.name in evidence[key].quote for key in person.name_evidence_ids):
            raise ValueError("人物用名必须是有据个体，不得是代词、概念或群众")
    for person in draft.characters:
        refs(person.importance_basis.evidence_ids)
        _unique(person.aliases, "别名重复")
        if len(person.alias_basis) != len(person.aliases) or {a.name for a in person.alias_basis} != set(person.aliases):
            raise ValueError("别名缺少逐项来源依据")
        for alias in person.alias_basis:
            refs(alias.evidence_ids)
            if alias.name in NON_PEOPLE or not any(alias.name in evidence[key].quote for key in alias.evidence_ids):
                raise ValueError("别名没有原文依据")
    claims = {key: (claim, owner) for key, claim, owner in _claims(draft)}
    for claim, owner in claims.values():
        if any(key is not None and key not in people for key in (claim.subject_id, claim.object_id)):
            raise ValueError("动作或身份端点不存在，不能以字符串null代替null")
        if claim.kind in {"knowledge", "feeling"} and claim.subject_id is None:
            raise ValueError("知情和情感必须有明确持有者")
        if owner in {p.id for p in draft.characters}:
            if owner not in (claim.subject_id, claim.object_id):
                raise ValueError("人物字段串用其他主体或不确定端点")
            if claim.kind in {"knowledge", "feeling"} and claim.subject_id != owner:
                raise ValueError("知情情感不能移给对象")
    event_ids = {e.id for e in draft.events}
    visible = {p.id for p in draft.characters}
    for event in draft.events:
        event_claims = [event.action, event.consequence, *event.sub_events]
        participants = {key for c in event_claims for key in (c.subject_id, c.object_id) if key is not None}
        subjects = {c.subject_id for c in event_claims if c.subject_id is not None}
        if (not set(event.actor_ids) <= participants & visible or not subjects & visible <= set(event.actor_ids)
                or len(event.actor_ids) != len(set(event.actor_ids))):
            raise ValueError("事件人物与实际动作主体不一致")

    def action(key, event=None):
        if key not in claims or claims[key][1] not in event_ids or (event and claims[key][1] != event):
            raise ValueError("关系必须定位其事件内的实际动作")
        return claims[key][0], claims[key][1]

    dependencies = []
    action_edges = []
    kind_map = {"cause": "causes", "purpose": "enables", "before": "follows", "reveal": "reveals", "echo": "foreshadow_payoff"}
    _unique([(e.from_id, e.to_id, e.kind) for e in draft.relations], "剧情关系重复")
    for edge in draft.relations:
        first, _ = action(edge.from_action, edge.from_id)
        second, _ = action(edge.to_action, edge.to_id)
        if edge.from_action == edge.to_action or kind_map[edge.basis] != edge.kind:
            raise ValueError("关系类型或实际动作方向不一致")
        if edge.status == "fact" and any(c.status != "fact" for c in (first, second)):
            raise ValueError("关系不能将推断或传闻升级为事实")
        if edge.basis in {"cause", "purpose"} and any(c.phase != "actual" for c in (first, second)):
            raise ValueError("计划、请求或否定动作不能作为已发生因果")
        if edge.basis in {"cause", "purpose", "before"} and edge.status in {"fact", "reported"}:
            dependencies.append((edge.from_id, edge.to_id))
            action_edges.append((edge.from_action, edge.to_action))
    for edge in draft.character_relations:
        if edge.action_ref not in claims:
            raise ValueError("人物关系缺少有向事实")
        claim = claims[edge.action_ref][0]
        if (claim.subject_id, claim.object_id) != (edge.from_id, edge.to_id):
            raise ValueError("人物关系方向与行动或情感持有者不一致")
        if not set(edge.evidence_ids).intersection(claim.evidence_ids):
            raise ValueError("人物关系与有向事实来源不对应")
        if edge.status == "fact" and claim.status != "fact":
            raise ValueError("人物关系不能升级事实状态")
    for constraint in draft.order_constraints:
        refs(constraint.evidence_ids)
        _, first = action(constraint.from_action)
        _, second = action(constraint.to_action)
        action_edges.append((constraint.from_action, constraint.to_action))
        if first != second:
            dependencies.append((first, second))
    _assert_dag(claims, action_edges)
    _assert_dag(event_ids, dependencies)
    positions = {key: i for i, key in enumerate(draft.story_order)}
    if any(positions[first] >= positions[second] for first, second in dependencies):
        raise ValueError("故事时间线倒置已知依赖")
    refs(draft.time_evidence_ids)
    if sorted(q.index for q in draft.question_sources) != list(range(len(draft.open_questions))):
        raise ValueError("未解项必须逐项保留来源")
    for question in draft.question_sources:
        refs(question.evidence_ids)
    return draft.model_dump(mode="json"), report


ID_GROUPS = ("characters", "events", "findings", "evidence", "participants")
INDEX_GROUPS = ("relations", "character_relations", "open_questions", "contradictions", "order_constraints", "question_sources")
SCALARS = ("story_order", "time_note", "time_evidence_ids", "title", "scope")


def target_index(draft):
    result = {key: value for key, value in draft.items() if key in SCALARS}
    for group in ID_GROUPS:
        result.update({f"{group}/{item['id']}": item for item in draft.get(group, [])})
    for group in INDEX_GROUPS:
        result.update({f"{group}/{i}": item for i, item in enumerate(draft.get(group, []))})
    return result


def target_hashes(draft):
    return {key: object_hash(value) for key, value in target_index(draft).items()}


def validate_review(data, draft, bank, read_text, *, final=False):
    schema = ReportVerification if final else ReportReview
    review = schema.model_validate(data, strict=True).root
    if review.draft_hash != object_hash(draft):
        raise ValueError("审查绑定了其他草稿")
    if isinstance(review, ReviewAccept):
        if sorted(review.checked_chapters) != sorted(read_text):
            raise ValueError("审查没有覆盖全部当前章节")
    elif isinstance(review, ReviewBlocked):
        for issue in review.issues:
            _source_check(issue.source_ids, bank, read_text)
    else:
        if len(canonical(review.model_dump(mode="json")).encode("utf-8")) > MAX_REVISION_BYTES:
            raise ValueError("修订总量超过12KiB")
        _unique([c.target for c in review.changes], "修订对象重复")
        for change in review.changes:
            _source_check(change.source_ids, bank, read_text)
    return review


def apply_revision(review, draft, bank, read_text, *, producer):
    if not isinstance(review, ReviewRevise):
        raise ValueError("只允许一次有源修订")
    # Recheck the complete envelope even for direct callers.
    validate_review(review.model_dump(mode="json"), draft, bank, read_text)
    original = target_index(draft)
    revised = deepcopy(draft)
    removals = {}
    for change in review.changes:
        exists = change.target in original
        if change.before_hash != (object_hash(original[change.target]) if exists else None):
            raise ValueError("修订对象原值哈希不一致")
        if change.target in SCALARS:
            if change.replacement is None or set(change.replacement) != {"value"}:
                raise ValueError("报告元信息须完整替换")
            revised[change.target] = change.replacement["value"]
            continue
        parts = change.target.split("/")
        if len(parts) != 2 or parts[0] not in (*ID_GROUPS, *INDEX_GROUPS):
            raise ValueError("修订目标不在白名单")
        group, key = parts
        if group in ID_GROUPS:
            index = next((i for i, item in enumerate(draft[group]) if item["id"] == key), None)
            if change.replacement is not None and change.replacement.get("id") != key:
                raise ValueError("修订不能更换稳定ID")
            if index is None:
                if change.replacement is None:
                    raise ValueError("不能撤回不存在的对象")
                revised[group].append(change.replacement)
                continue
        else:
            if not key.isdigit() or str(int(key)) != key:
                raise ValueError("修订索引无效")
            index = int(key)
            if index > len(draft[group]):
                raise ValueError("修订索引越界")
            if index == len(draft[group]):
                if change.replacement is None:
                    raise ValueError("不能撤回不存在的对象")
                value = change.replacement
                if group == "open_questions":
                    if set(value) != {"value"}:
                        raise ValueError("未解项格式无效")
                    value = value["value"]
                revised[group].append(value)
                continue
        if change.replacement is None:
            removals.setdefault(group, []).append(index)
        else:
            value = change.replacement
            if group == "open_questions":
                if set(value) != {"value"}:
                    raise ValueError("未解项格式无效")
                value = value["value"]
            revised[group][index] = value
    for group, indices in removals.items():
        for index in sorted(indices, reverse=True):
            del revised[group][index]
    # Deletions are explicit sourced retractions. All remaining references and
    # the complete revised report must pass; final full-source review is still
    # mandatory and may reject loss of a valid clause. Originals stay in job.
    return validate_draft(revised, bank, read_text, producer=producer)[0]
