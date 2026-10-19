"""Deterministic merge of model-authored deltas; no literary facts are invented here."""

from __future__ import annotations

from collections import defaultdict

from schemas.analysis_delta import AnalysisDelta
from schemas.analysis_report import AnalysisReport, CharacterRelation, validate_character_relations


GROUPS = {"evidence": "Q", "findings": "F", "characters": "C", "events": "E"}


def compact_index(draft: dict | None) -> dict:
    """Only identifiers and labels go into per-segment context, never the full report."""
    draft = draft or {}
    return {
        "characters": [{"id": x["id"], "name": x["name"], "entity_key": x.get("entity_key")}
                       for x in draft.get("characters", [])],
        "events": [{"id": x["id"], "title": x["title"], "chapter_number": x["chapter_number"]}
                   for x in draft.get("events", [])],
        "findings": [{"id": x["id"], "title": x["title"]} for x in draft.get("findings", [])],
        "relations": [{key: x[key] for key in ("from_id", "to_id", "kind")}
                      for x in draft.get("relations", [])],
        "character_relations": [{key: x[key] for key in ("from_id", "to_id", "label")}
                                for x in draft.get("character_relations", [])],
        "recent_evidence": [{"id": x["id"], "chapter_number": x["chapter_number"], "quote": x["quote"]}
                            for x in draft.get("evidence", [])[-30:]],
    }


def _identity(group: str, item: dict) -> tuple:
    if group == "evidence":
        return (item["chapter_number"], item["quote"])
    if group == "characters":
        return (item.get("entity_key") or item["name"],)
    if group == "events":
        return (item["chapter_number"], item["title"])
    return (item["title"],)


def _next_id(prefix: str, used: set[str]) -> str:
    number = 1
    while f"{prefix}{number}" in used:
        number += 1
    return f"{prefix}{number}"


def _remap_claim(claim: dict, ids: dict[str, str]) -> None:
    claim["evidence_ids"] = [ids.get(value, value) for value in claim["evidence_ids"]]


def _remap_object(group: str, item: dict, ids: dict[str, str]) -> None:
    if group == "findings":
        _remap_claim(item, ids)
    elif group == "characters":
        for key in ("identity", "motivation", "change", "portrait"):
            if item.get(key) is not None:
                _remap_claim(item[key], ids)
        for insight in item.get("insights", []):
            _remap_claim(insight, ids)
    elif group == "events":
        item["actor_ids"] = [ids.get(value, value) for value in item["actor_ids"]]
        for key in ("action", "consequence"):
            _remap_claim(item[key], ids)
        for sub in item.get("sub_events", []):
            _remap_claim(sub, ids)


def _validate_draft(draft: dict, read_text: dict[int, str]) -> None:
    """An incomplete draft must obey the same source/reference bounds as a report."""
    numbers = draft["chapter_numbers"]
    chapters = set(numbers)
    ordered = sorted(chapters)
    if (not numbers or len(numbers) > 500 or len(chapters) != len(numbers) or any(n < 1 for n in numbers)
            or any(right != left + 1 for left, right in zip(ordered, ordered[1:]))
            or chapters != set(read_text)):
        raise ValueError("已读章节与正文范围不一致")
    ids = [item["id"] for group in GROUPS for item in draft[group]]
    if len(ids) != len(set(ids)):
        raise ValueError("分析 ID 重复")
    evidence_ids = {item["id"] for item in draft["evidence"]}
    character_ids = {item["id"] for item in draft["characters"]}
    event_ids = {item["id"] for item in draft["events"]}
    claims = [*draft["findings"], *draft["relations"], *draft["character_relations"], *draft["contradictions"]]
    validate_character_relations([CharacterRelation.model_validate(x, strict=True)
                                  for x in draft["character_relations"]], character_ids)
    for character in draft["characters"]:
        claims.extend(character[key] for key in ("identity", "motivation", "change"))
        claims.extend(character.get("insights", []))
        if character.get("portrait") is not None:
            claims.append(character["portrait"])
    for event in draft["events"]:
        end = event.get("chapter_end") or event["chapter_number"]
        if (event["chapter_number"] not in chapters or end < event["chapter_number"]
                or end > ordered[-1]
                or not set(event["actor_ids"]) <= character_ids):
            raise ValueError("事件章节或人物超出已读范围")
        claims.extend((event["action"], event["consequence"]))
        claims.extend(event.get("sub_events", []))
    if any(not set(claim["evidence_ids"]) <= evidence_ids for claim in claims):
        raise ValueError("判断引用了不存在的证据")
    if any(edge["from_id"] not in event_ids or edge["to_id"] not in event_ids
           or edge["from_id"] == edge["to_id"] for edge in draft["relations"]):
        raise ValueError("剧情连线端点无效")
    order = draft["story_order"]
    if len(order) != len(set(order)) or not set(order) <= event_ids:
        raise ValueError("故事时间线引用无效")
    if any(item["chapter_number"] not in chapters or
           (read_text[item["chapter_number"]].find(item["quote"]) < 0 or
            read_text[item["chapter_number"]].find(item["quote"], read_text[item["chapter_number"]].find(item["quote"]) + 1) >= 0)
           for item in draft["evidence"]):
        raise ValueError("引文不在已读正文中唯一出现")


def merge_delta(previous: dict | None, change: AnalysisDelta, *, chapters: list[int],
                read_text: dict[int, str], producer: str, scope: str,
                final: bool = False) -> tuple[dict, AnalysisReport | None]:
    """Apply declarations atomically; validate all references and quotes before publication."""
    if not set((previous or {}).get("chapter_numbers", [])) <= set(chapters):
        raise ValueError("已读章节范围不能缩小")
    draft = {key: list((previous or {}).get(key, [])) for key in (*GROUPS, "relations", "character_relations", "story_order", "open_questions", "contradictions")}
    draft.update(schema_version="1", producer=producer, title=(previous or {}).get("title", "全书拆解"),
                 scope=scope, chapter_numbers=chapters, time_note=(previous or {}).get("time_note", "时间顺序待全书核对。"))
    withdrawn_keys = [(item.from_id, item.to_id, item.kind) for item in change.withdrawn_relations]
    withdrawn_key_set = set(withdrawn_keys)
    if len(withdrawn_keys) != len(withdrawn_key_set):
        raise ValueError("撤回连线键重复")
    existing_keys = {(edge["from_id"], edge["to_id"], edge["kind"]) for edge in draft["relations"]}
    if not withdrawn_key_set <= existing_keys:
        raise ValueError("撤回连线必须引用已有的 from_id/to_id/kind")
    draft["relations"] = [edge for edge in draft["relations"]
                          if (edge["from_id"], edge["to_id"], edge["kind"]) not in withdrawn_key_set]
    character_keys = [(x.from_id, x.to_id, x.label) for x in change.withdrawn_character_relations]
    existing_character_keys = {(x["from_id"], x["to_id"], x["label"]) for x in draft["character_relations"]}
    if len(character_keys) != len(set(character_keys)) or not set(character_keys) <= existing_character_keys:
        raise ValueError("撤回人物关系必须引用唯一的已有端点与标签")
    draft["character_relations"] = [x for x in draft["character_relations"]
                                    if (x["from_id"], x["to_id"], x["label"]) not in character_keys]
    ids: dict[str, str] = {}
    # Resolve all object IDs before resolving claims/edges between new objects.
    planned: dict[str, list[tuple[dict, str]]] = defaultdict(list)
    all_existing = {item["id"] for key in GROUPS for item in draft[key]}
    allocated = set(all_existing)
    local_ids: set[str] = set()
    for group, prefix in GROUPS.items():
        existing_by_id = {item["id"]: item for item in draft[group]}
        for item_model in getattr(change, f"new_{group}"):
            item = item_model.model_dump(mode="json")
            local = item["id"]
            if local in local_ids or local in all_existing:
                raise ValueError("新增声明 ID 与已有对象或本轮声明重复")
            local_ids.add(local)
            match = next((x for x in draft[group] if _identity(group, x) == _identity(group, item)), None)
            if any(_identity(group, existing) == _identity(group, item)
                   for existing, _ in planned[group]):
                raise ValueError("本轮重复声明同一对象")
            canonical = match["id"] if match else _next_id(prefix, allocated)
            allocated.add(canonical)
            ids[local] = canonical
            planned[group].append((item, canonical))
        for item_model in getattr(change, f"revised_{group}"):
            item = item_model.model_dump(mode="json")
            canonical = item["id"]
            if canonical not in existing_by_id or canonical in {target for _, target in planned[group]}:
                raise ValueError("修正声明必须引用唯一的已有 ID")
            planned[group].append((item, canonical))
    for group in GROUPS:
        by_id = {item["id"]: index for index, item in enumerate(draft[group])}
        for item, canonical in planned[group]:
            item["id"] = canonical
            _remap_object(group, item, ids)
            if canonical in by_id:
                draft[group][by_id[canonical]] = item
            else:
                by_id[canonical] = len(draft[group])
                draft[group].append(item)
    for item in change.new_relations:
        edge = item.model_dump(mode="json")
        edge["from_id"] = ids.get(edge["from_id"], edge["from_id"])
        edge["to_id"] = ids.get(edge["to_id"], edge["to_id"])
        _remap_claim(edge, ids)
        key = (edge["from_id"], edge["to_id"], edge["kind"])
        draft["relations"] = [x for x in draft["relations"]
                              if (x["from_id"], x["to_id"], x["kind"]) != key]
        draft["relations"].append(edge)
    new_character_keys = set()
    for item in change.new_character_relations:
        edge = item.model_dump(mode="json")
        edge["from_id"] = ids.get(edge["from_id"], edge["from_id"])
        edge["to_id"] = ids.get(edge["to_id"], edge["to_id"])
        _remap_claim(edge, ids)
        key = (edge["from_id"], edge["to_id"], edge["label"])
        if key in new_character_keys:
            raise ValueError("本轮人物关系键重复")
        new_character_keys.add(key)
        draft["character_relations"] = [x for x in draft["character_relations"]
                                        if (x["from_id"], x["to_id"], x["label"]) != key]
        draft["character_relations"].append(edge)
    withdrawn = set(change.withdrawn_ids)
    if withdrawn:
        known = {item["id"] for key in GROUPS for item in draft[key]}
        if not withdrawn <= known:
            raise ValueError("撤回声明引用了不存在的 ID")
        for group in GROUPS:
            draft[group] = [item for item in draft[group] if item["id"] not in withdrawn]
        draft["relations"] = [edge for edge in draft["relations"]
                              if edge["from_id"] not in withdrawn and edge["to_id"] not in withdrawn]
        draft["character_relations"] = [edge for edge in draft["character_relations"]
                                        if edge["from_id"] not in withdrawn and edge["to_id"] not in withdrawn]
    if change.story_order is not None:
        draft["story_order"] = [ids.get(value, value) for value in change.story_order]
    else:
        draft["story_order"] = [value for value in draft["story_order"] if value not in withdrawn]
    if change.open_questions is not None:
        draft["open_questions"] = change.open_questions
    if change.contradictions is not None:
        draft["contradictions"] = [item.model_dump(mode="json") for item in change.contradictions]
        for item in draft["contradictions"]:
            _remap_claim(item, ids)
    if change.title is not None:
        draft["title"] = change.title
    if change.time_note is not None:
        draft["time_note"] = change.time_note
    _validate_draft(draft, read_text)
    required = (all(draft[key] for key in ("findings", "characters", "events", "evidence", "story_order"))
                and len(draft["story_order"]) == len(draft["events"]))
    if not required and not final:
        return draft, None
    report = AnalysisReport.model_validate(draft)
    return draft, report
