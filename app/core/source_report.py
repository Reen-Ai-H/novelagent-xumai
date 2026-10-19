"""Private source-only report wire; the legacy final validator stays authoritative.

Short selectors are local to one frozen job. They are never inferred from a
failed old report, fuzzy-matched, or used as proof of literary entailment.
"""
from __future__ import annotations

from copy import deepcopy

from pydantic import create_model, model_validator

from app.core.analysis_grounding import source_bank
from app.core.report_pipeline import (
    AliasBasis, DraftCharacter, DraftCharacterRelation, DraftClaim, DraftDetail,
    DraftEvent, DraftFinding, DraftRelation, ID_GROUPS, INDEX_GROUPS,
    MAX_REVISION_BYTES, NON_PEOPLE, Participant, QuestionSource, ReportDraft,
    ReportReview, ReportVerification, ReviewAccept, ReviewBlocked, ReviewRevise,
    TimeConstraint, _claims, canonical, object_hash, validate_draft,
)
from schemas.analysis_report import Claim, StrictModel


SOURCE_REPORT_WIRE = "source-report-v1"
LEGACY_REPORT_WIRE = "report-draft-v1"
REF_NAMES = {"evidence_ids": "source_ids", "name_evidence_ids": "name_source_ids",
             "time_evidence_ids": "time_source_ids"}
SOURCE_REF_NAMES = frozenset(REF_NAMES.values())
SOURCE_ID_GROUPS = tuple(g for g in ID_GROUPS if g != "evidence")
SOURCE_SCALARS = ("story_order", "time_note", "time_source_ids", "title", "scope")
MAX_DIAGNOSTICS = 12
MAX_DIAGNOSTIC_BYTES = 8192


def _source_model(name, base, **overrides):
    # Copy constraints/defaults, not AnalysisReport validators: the latter must
    # run on the final server-bound report, never on an incomplete draft.
    fields = {REF_NAMES.get(key, key): (field.annotation, deepcopy(field))
              for key, field in base.model_fields.items() if key != "evidence"}
    for key, annotation in overrides.items():
        fields[key] = (annotation, fields[key][1])
    if "id" in fields:
        # Code-owned schema guidance survives the common runtime's deliberate
        # removal of candidate values/messages from repair error summaries.
        fields["id"][1].description = (
            "内部稳定编号；须与本报告characters、events、findings、participants全部对象的id全局唯一。"
            "不同对象即使用名或拼音近似也不得共用id；不能通过合并或删除对象解决编号冲突。")
    return create_model(name, __base__=StrictModel, **fields)


SourceClaim = _source_model("SourceClaim", Claim)
SourceDraftClaim = _source_model("SourceDraftClaim", DraftClaim)
SourceFinding = _source_model("SourceFinding", DraftFinding)
SourceDetail = _source_model("SourceDetail", DraftDetail)
SourceAliasBasis = _source_model("SourceAliasBasis", AliasBasis)
SourceParticipant = _source_model("SourceParticipant", Participant)
SourceCharacter = _source_model("SourceCharacter", DraftCharacter,
    identity=SourceDraftClaim, motivation=SourceDraftClaim, change=SourceDraftClaim,
    portrait=SourceDraftClaim | None, insights=list[SourceDetail],
    alias_basis=list[SourceAliasBasis], importance_basis=SourceClaim)
SourceEvent = _source_model("SourceEvent", DraftEvent,
    action=SourceDraftClaim, consequence=SourceDraftClaim, sub_events=list[SourceDetail])
SourceRelation = _source_model("SourceRelation", DraftRelation)
SourceCharacterRelation = _source_model("SourceCharacterRelation", DraftCharacterRelation)
SourceTimeConstraint = _source_model("SourceTimeConstraint", TimeConstraint)
SourceQuestion = _source_model("SourceQuestion", QuestionSource)
_SourceReportShape = _source_model("SourceReportShape", ReportDraft,
    findings=list[SourceFinding], characters=list[SourceCharacter], events=list[SourceEvent],
    relations=list[SourceRelation], character_relations=list[SourceCharacterRelation],
    contradictions=list[SourceDetail], participants=list[SourceParticipant],
    order_constraints=list[SourceTimeConstraint], question_sources=list[SourceQuestion])


class SourceReportDraft(_SourceReportShape):
    """characters、events、findings、participants中全部对象的id必须全局唯一。

    编号只作内部引用，不是姓名或文学事实。格式修复须保留全部人物/事件/对象、
    事实文字、判断状态与来源编号选择；只可重分配可无歧义的内部ID，并同步对应的
    subject_id/object_id、actor_ids、from_id/to_id、story_order及动作定位引用
    from_action/to_action/action_ref。不得合并、去重、删对象或猜测身份/端点。
    无法明确归属的引用不能靠改编号掩盖；仍有歧义或重复时必须拒绝，不另增修复循环。
    """

    @model_validator(mode="after")
    def unique_object_ids(self):
        ids = [item.id for group in SOURCE_ID_GROUPS for item in getattr(self, group)]
        if len(ids) != len(set(ids)):
            # No ID/name/source values are put into trusted error prose.
            raise ValueError("报告对象的内部ID必须全局唯一")
        return self


def report_wire(job):
    version = job.get("report_wire_version")
    if version in (None, LEGACY_REPORT_WIRE):
        return LEGACY_REPORT_WIRE
    if version != SOURCE_REPORT_WIRE:
        raise ValueError("未知的私有报告合同版本")
    return version


def _binding(job):
    if (any(not isinstance(job[key], str) or not job[key] for key in
            ("account_id", "project_id", "source_version", "source_hash"))
            or type(job["source_revision"]) is not int or job["source_revision"] < 0):
        raise ValueError("来源目录绑定格式无效")
    return {key: job[key] for key in ("account_id", "project_id", "source_version",
                                     "source_revision", "source_hash")}


def _directory_material(bank, read_text):
    if not bank or bank != source_bank(read_text):
        raise ValueError("来源目录必须对应完整当前来源库")
    ordered = sorted(bank.values(), key=lambda p: (p.chapter_number, p.start, p.end, p.id))
    entries, counts = {}, {}
    for passage in ordered:
        if any(type(getattr(passage, key)) is not int for key in ("chapter_number", "start", "end")):
            raise ValueError("来源目录位置类型无效")
        number = passage.chapter_number
        counts[number] = counts.get(number, 0) + 1
        entries[f"C{number}P{counts[number]:03d}"] = passage.id
    return entries, ordered


def check_source_entries(entries, bank, read_text):
    if entries != _directory_material(bank, read_text)[0]:
        raise ValueError("短来源目录与完整来源库不一致")


def freeze_source_directory(job, bank, read_text):
    """Validate the COMPLETE bank before any runtime/budget/HTTP boundary."""
    entries, ordered = _directory_material(bank, read_text)
    value = {**_binding(job), "entries": entries,
             "bank_hash": object_hash([dict(source_id=p.id, chapter_number=p.chapter_number,
                                           start=p.start, end=p.end, quote=p.quote) for p in ordered])}
    return {**value, "directory_hash": object_hash(value)}


def check_source_directory(job, bank, read_text):
    # Recomputing an expectation is a check, NOT a replacement directory. All
    # resolution below uses the persisted map after this equality check.
    expected = freeze_source_directory(job, bank, read_text)
    directory = job.get("source_directory")
    if (not isinstance(directory, dict) or directory != expected
            or directory["directory_hash"] != object_hash({k: v for k, v in directory.items() if k != "directory_hash"})):
        raise ValueError("冻结来源目录、账户或稿本绑定不一致")
    return job["source_directory"]["entries"]


def source_target_index(draft):
    result = {key: value for key, value in draft.items() if key in SOURCE_SCALARS}
    for group in SOURCE_ID_GROUPS:
        result.update({f"{group}/{item['id']}": item for item in draft[group]})
    for group in INDEX_GROUPS:
        result.update({f"{group}/{i}": item for i, item in enumerate(draft[group])})
    return result


def source_target_hashes(draft):
    return {key: object_hash(value) for key, value in source_target_index(draft).items()}


def _references(value, path="", target=None):
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}" if path else key
            if key in SOURCE_REF_NAMES:
                yield child, target or key, item
            elif not path and key in SOURCE_ID_GROUPS:
                for index, obj in enumerate(item):
                    yield from _references(obj, f"{key}[{index}]", f"{key}/{obj['id']}")
            elif not path and key in INDEX_GROUPS:
                for index, obj in enumerate(item):
                    yield from _references(obj, f"{key}[{index}]", f"{key}/{index}")
            else:
                yield from _references(item, child, target)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _references(item, f"{path}[{index}]", target)


def _shape(data, entries, read_text):
    draft = SourceReportDraft.model_validate(data, strict=True)
    if (set(draft.chapter_numbers) != set(read_text)
            or len(draft.chapter_numbers) != len(read_text)):
        raise ValueError("报告必须覆盖全部当前正文")
    ids = [item.id for group in SOURCE_ID_GROUPS for item in getattr(draft, group)]
    # A duplicate cannot be safely addressed by a whole-object correction.
    if len(ids) != len(set(ids)) or set(ids).intersection(entries.values()):
        raise ValueError("草稿对象ID不唯一或占用服务器证据ID")
    return draft


def _legacy_projection(data, entries):
    """Only rename/resolve refs and assemble declarations; no fact edits."""
    used = set()
    def visit(value):
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if key in SOURCE_REF_NAMES:
                    if len(item) != len(set(item)) or any(ref not in entries for ref in item):
                        raise ValueError("来源引用不存在或重复")
                    used.update(item)
                    result[next(k for k, v in REF_NAMES.items() if v == key)] = [entries[ref] for ref in item]
                else:
                    result[key] = visit(item)
            return result
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value
    projected = visit(data)
    if len(used) > 500:
        raise ValueError("派生证据超过原报告容量")
    ordered = sorted(entries, key=lambda short: tuple(map(int, short[1:].split("P"))))
    projected["evidence"] = [dict(id=entries[short], source_id=entries[short]) for short in ordered if short in used]
    return projected


def validate_source_candidate(data, entries, bank, read_text, *, producer):
    check_source_entries(entries, bank, read_text)
    draft = _shape(data, entries, read_text).model_dump(mode="json")
    _, report = validate_draft(_legacy_projection(draft, entries), bank, read_text, producer=producer)
    return draft, report


def _cycle_targets(nodes, edges):
    """Return one exact cycle witness, not all edges or an invented ordering."""
    outgoing = {node: [] for node in sorted(nodes)}
    for start, end, target in edges:
        outgoing[start].append((end, target))
    done = set()
    for start in outgoing:
        if start in done:
            continue
        active, path, stack = {start: 0}, [], [(start, iter(outgoing[start]))]
        while stack:
            node, iterator = stack[-1]
            edge = next(iterator, None)
            if edge is None:
                done.add(node)
                del active[node]
                stack.pop()
                if path:
                    path.pop()
                continue
            end, target = edge
            if end in active:
                return list(dict.fromkeys([*path[active[end]:], target]))
            if end not in done:
                active[end] = len(stack)
                path.append(target)
                stack.append((end, iter(outgoing[end])))
    return []


def prepare_source_draft(data, entries, bank, read_text, *, producer):
    """Strict shape/boundary first; only enumerated, addressable defects review.

    No exception from the final validator is converted into a diagnostic.
    Unexpected errors still fail the job. Diagnostics never make a draft valid.
    """
    check_source_entries(entries, bank, read_text)
    draft = _shape(data, entries, read_text)
    value = draft.model_dump(mode="json")
    diagnostics = []
    def emit(code, targets, field, **details):
        issue = dict(code=code, targets=list(dict.fromkeys(targets)), field=field, **details)
        if issue not in diagnostics:
            diagnostics.append(issue)
        if (len(diagnostics) > MAX_DIAGNOSTICS
                or len(canonical(diagnostics).encode("utf-8")) > MAX_DIAGNOSTIC_BYTES):
            raise ValueError("草稿问题超过安全诊断边界")

    for path, target, refs in _references(value):
        unknown = list(dict.fromkeys(ref for ref in refs if ref not in entries))
        if unknown:
            emit("unknown_source", [target], path, source_ids=unknown)
        if len(refs) != len(set(refs)):
            emit("duplicate_source", [target], path)
    people = {p.id: p for p in [*draft.characters, *draft.participants]}
    visible, event_ids = {p.id for p in draft.characters}, {e.id for e in draft.events}
    claims = {key: (claim, owner) for key, claim, owner in _claims(draft)}
    claim_targets = {}
    for key, _, owner in _claims(draft):
        if owner in visible:
            target = "characters/" + owner
        elif owner in event_ids:
            target = "events/" + owner
        elif key.startswith("contradictions."):
            target = "contradictions/" + key.split(".")[1]
        else:
            target = "findings/" + key
        claim_targets[key] = target
    for group in ("characters", "participants"):
        for person in getattr(draft, group):
            target = f"{group}/{person.id}"
            refs = person.name_source_ids
            if person.name in NON_PEOPLE or (all(ref in entries for ref in refs)
                    and not any(person.name in bank[entries[ref]].quote for ref in refs)):
                emit("person_name", [target], "name")
            if group == "characters":
                if (len(person.aliases) != len(set(person.aliases))
                        or len(person.alias_basis) != len(person.aliases)
                        or {a.name for a in person.alias_basis} != set(person.aliases)):
                    emit("alias_basis", [target], "alias_basis")
                for alias in person.alias_basis:
                    if alias.name in NON_PEOPLE or (all(ref in entries for ref in alias.source_ids)
                            and not any(alias.name in bank[entries[ref]].quote for ref in alias.source_ids)):
                        emit("alias_name", [target], "alias_basis")
    for key, (claim, owner) in claims.items():
        if any(endpoint is not None and endpoint not in people for endpoint in (claim.subject_id, claim.object_id)):
            emit("claim_endpoint", [claim_targets[key]], key)
        if ((claim.kind in {"knowledge", "feeling"} and claim.subject_id is None)
                or (owner in visible and (owner not in (claim.subject_id, claim.object_id)
                    or (claim.kind in {"knowledge", "feeling"} and claim.subject_id != owner)))):
            emit("claim_holder", [claim_targets[key]], key)
    for event in draft.events:
        event_claims = [event.action, event.consequence, *event.sub_events]
        participants = {key for c in event_claims for key in (c.subject_id, c.object_id) if key is not None}
        subjects = {c.subject_id for c in event_claims if c.subject_id is not None}
        if (not set(event.actor_ids) <= participants & visible or not subjects & visible <= set(event.actor_ids)
                or len(event.actor_ids) != len(set(event.actor_ids))):
            emit("event_actors", ["events/" + event.id], "actor_ids")

    def action(key, target, event=None):
        if key not in claims or claims[key][1] not in event_ids or (event and claims[key][1] != event):
            emit("action_endpoint", [target], key)
            return None
        return claims[key]

    dependencies, action_edges, relation_keys, person_keys = [], [], set(), set()
    kinds = {"cause": "causes", "purpose": "enables", "before": "follows", "reveal": "reveals", "echo": "foreshadow_payoff"}
    for i, edge in enumerate(draft.relations):
        target = f"relations/{i}"
        key = edge.from_id, edge.to_id, edge.kind
        if key in relation_keys:
            emit("duplicate_relation", [target], target)
        relation_keys.add(key)
        first, second = action(edge.from_action, target, edge.from_id), action(edge.to_action, target, edge.to_id)
        if edge.from_id not in event_ids or edge.to_id not in event_ids or edge.from_id == edge.to_id:
            emit("relation_endpoint", [target], target)
        if not first or not second:
            continue
        if edge.from_action == edge.to_action or kinds[edge.basis] != edge.kind:
            emit("relation_kind", [target], target)
        if edge.status == "fact" and any(c.status != "fact" for c in (first[0], second[0])):
            emit("relation_status", [target], target)
        if edge.basis in {"cause", "purpose"} and any(c.phase != "actual" for c in (first[0], second[0])):
            emit("relation_phase", [target, claim_targets[edge.from_action], claim_targets[edge.to_action]], target)
        if edge.basis in {"cause", "purpose", "before"} and edge.status in {"fact", "reported"}:
            dependencies.append((first[1], second[1], target))
            action_edges.append((edge.from_action, edge.to_action, target))
    for i, edge in enumerate(draft.character_relations):
        target = f"character_relations/{i}"
        key = edge.from_id, edge.to_id, edge.label
        if key in person_keys:
            emit("duplicate_character_relation", [target], target)
        person_keys.add(key)
        if edge.from_id not in visible or edge.to_id not in visible or edge.from_id == edge.to_id:
            emit("character_endpoint", [target], target)
        if edge.action_ref not in claims:
            emit("character_action", [target], "action_ref")
            continue
        claim = claims[edge.action_ref][0]
        if ((claim.subject_id, claim.object_id) != (edge.from_id, edge.to_id)
                or not set(edge.source_ids).intersection(claim.source_ids)
                or (edge.status == "fact" and claim.status != "fact")):
            emit("character_direction", [target, claim_targets[edge.action_ref]], "action_ref")
    for i, edge in enumerate(draft.order_constraints):
        target = f"order_constraints/{i}"
        first, second = action(edge.from_action, target), action(edge.to_action, target)
        if first and second:
            action_edges.append((edge.from_action, edge.to_action, target))
            if first[1] != second[1]:
                dependencies.append((first[1], second[1], target))
    for label, nodes, edges in (("action_cycle", claims, action_edges), ("event_cycle", event_ids, dependencies)):
        cycle = _cycle_targets(nodes, edges)
        if cycle:
            emit(label, cycle, "order_constraints/relations")
    positions = {key: i for i, key in enumerate(draft.story_order)}
    if len(draft.story_order) != len(event_ids) or set(draft.story_order) != event_ids:
        emit("story_order_coverage", ["story_order"], "story_order")
    else:
        inverted = [target for first, second, target in dependencies if positions[first] >= positions[second]]
        if inverted:
            emit("story_order_dependency", ["story_order", *inverted], "story_order")
    if sorted(q.index for q in draft.question_sources) != list(range(len(draft.open_questions))):
        emit("question_sources", [f"question_sources/{i}" for i in range(len(draft.question_sources))]
             + [f"open_questions/{i}" for i in range(len(draft.open_questions))], "question_sources")
    if not diagnostics:
        # A backstop here is also intentional. Unexpected validator failures
        # must stop, not be silently relabelled as a reviewable content issue.
        validate_source_candidate(value, entries, bank, read_text, producer=producer)
    return value, diagnostics


def _review_sources(refs, entries, bank, read_text):
    if len(refs) != len(set(refs)) or any(ref not in entries for ref in refs):
        raise ValueError("审查引用了未知或重复短来源")
    # Keep the exact unique quotation checks on correction reasons too.
    from app.core.preview_analysis import _source_check
    _source_check([entries[ref] for ref in refs], bank, read_text)


def validate_source_review(data, draft, entries, bank, read_text, *, final=False):
    check_source_entries(entries, bank, read_text)
    review = (ReportVerification if final else ReportReview).model_validate(data, strict=True).root
    if review.draft_hash != object_hash(draft):
        raise ValueError("审查绑定了其他草稿")
    if isinstance(review, ReviewAccept):
        if sorted(review.checked_chapters) != sorted(read_text):
            raise ValueError("审查没有覆盖全部当前章节")
    elif isinstance(review, ReviewBlocked):
        for issue in review.issues:
            _review_sources(issue.source_ids, entries, bank, read_text)
    else:
        if len(canonical(review.model_dump(mode="json")).encode("utf-8")) > MAX_REVISION_BYTES:
            raise ValueError("修订总量超过12KiB")
        targets = [c.target for c in review.changes]
        if len(targets) != len(set(targets)):
            raise ValueError("修订对象重复")
        for change in review.changes:
            _review_sources(change.source_ids, entries, bank, read_text)
    return review


def apply_source_revision(review, draft, entries, bank, read_text, *, producer):
    if not isinstance(review, ReviewRevise):
        raise ValueError("只允许一次有源修订")
    validate_source_review(review.model_dump(mode="json"), draft, entries, bank, read_text)
    original, revised, removals = source_target_index(draft), deepcopy(draft), {}
    for change in review.changes:
        exists = change.target in original
        if change.before_hash != (object_hash(original[change.target]) if exists else None):
            raise ValueError("修订对象原值哈希不一致")
        replacement = change.replacement
        if change.target in SOURCE_SCALARS:
            if replacement is None or set(replacement) != {"value"}:
                raise ValueError("报告元信息须完整替换")
            revised[change.target] = replacement["value"]
            continue
        parts = change.target.split("/")
        if len(parts) != 2 or parts[0] not in (*SOURCE_ID_GROUPS, *INDEX_GROUPS):
            raise ValueError("修订目标不在白名单")
        group, key = parts
        if group in SOURCE_ID_GROUPS:
            index = next((i for i, item in enumerate(draft[group]) if item["id"] == key), None)
            if replacement is not None and replacement.get("id") != key:
                raise ValueError("修订不能更换稳定ID")
            if index is None:
                if replacement is None:
                    raise ValueError("不能撤回不存在的对象")
                revised[group].append(replacement)
                continue
        else:
            if not key.isdigit() or str(int(key)) != key or int(key) > len(draft[group]):
                raise ValueError("修订索引无效")
            index = int(key)
        if replacement is None:
            if index == len(draft[group]):
                raise ValueError("不能撤回不存在的对象")
            removals.setdefault(group, []).append(index)
        else:
            if group == "open_questions":
                if set(replacement) != {"value"}:
                    raise ValueError("未解项格式无效")
                replacement = replacement["value"]
            if index == len(draft[group]):
                revised[group].append(replacement)
            else:
                revised[group][index] = replacement
    for group, indices in removals.items():
        for index in sorted(indices, reverse=True):
            del revised[group][index]
    # A revision is only applied once and must immediately pass the ORIGINAL
    # full validator. No second diagnostic/revision round is opened here.
    return validate_source_candidate(revised, entries, bank, read_text, producer=producer)[0]
