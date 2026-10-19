"""Explicit synthetic chapter and final-outcome authorship, without model calls."""
from app.core.analysis_grounding import source_bank


def chapter_case(count=2, *, texts=None, merged=False, internal=False, planned=False):
    if texts is None:
        texts = {n: f"第{n}日，{'前章同一位' if merged and n > 1 else ''}林客"
                    f"{'计划' if planned and n == 2 else ''}在第{n}处渡口等候。" for n in range(1, count + 1)}
    bank = source_bank(texts)
    packets, entities, events, evidence, supports, bindings, cards = [], [], [], [], [], [], []
    numbers = sorted(texts)
    keys = {n: next(p.id for p in bank.values() if p.chapter_number == n and "等候" in p.quote) for n in numbers}
    global_id = lambda n: "C1" if merged else f"C{n}"

    def claim(key, ids, number):
        phase = "planned" if planned and number == 2 else "actual"
        supports.append({"key": key, "fact_ids": ids, "phases": [phase]})
        return {"text": bank[keys[number]].quote, "status": "fact", "evidence_ids": [f"Q{number}"]}

    for n in numbers:
        quote = bank[keys[n]].quote
        packet = {"chapter_number": n, "characters": [{"id": "P", "name": "林客", "aliases": [], "source_ids": [keys[n]]}],
            "atoms": [{"id": "A", "subject_id": "P", "object_id": None, "text": quote, "kind": "action", "status": "fact",
                       "phase": "planned" if planned and n == 2 else "actual", "time_anchor": f"第{n}日", "source_ids": [keys[n]]}]}
        packets.append(packet)
        role = "internal" if internal and n == 2 else ("main" if n == numbers[0] else "support")
        if not merged or n == numbers[0]:
            members = [f"H{k}_P" for k in numbers] if merged else [f"H{n}_P"]
            sources = [keys[k] for k in numbers] if merged else [keys[n]]
            entities.append({"id": global_id(n), "members": members, "name": "林客", "aliases": [], "role": role,
                             "basis": "原文明确为前章同一个人。" if merged else "同名未证明同人，保留独立身份及角色。", "source_ids": sources})
            if role != "internal":
                cards.append({"id": global_id(n), "name": "林客", "aliases": [], "role": "主角" if role == "main" else "配角",
                    **{field: claim(f"{global_id(n)}.{field}", [f"H{n}_A"], n) for field in ("identity", "motivation", "change")}})
        actors = [] if role == "internal" else [global_id(n)]
        events.append({"id": f"E{n}", "title": f"渡口{n}", "story_time": f"第{n}日", "actor_ids": actors,
            "action": claim(f"E{n}.action", [f"H{n}_A"], n), "consequence": claim(f"E{n}.consequence", [f"H{n}_A"], n), "sub_events": []})
        evidence.append({"id": f"Q{n}", "source_id": keys[n]})
        bindings.append({"event_id": f"E{n}", "atom_ids": [f"H{n}_A"]})
    first = numbers[0]
    report = {"title": "合成多章报告", "scope": "本次完整选中章节", "chapter_numbers": numbers,
        "findings": [{"id": "F1", "title": "渡口等候", **claim("F1", [f"H{first}_A"], first)}], "characters": cards,
        "events": events, "relations": [], "character_relations": [], "story_order": [f"E{n}" for n in numbers],
        "time_note": "依照合成原文的日序。", "evidence": evidence, "open_questions": []}
    outcome = {"outcome": "success", "report": report, "entities": entities, "cues": [], "supports": supports,
               "event_bindings": bindings, "edge_bindings": [], "cue_resolutions": [], "questions": []}
    return packets, outcome, bank, texts


def add_before(outcome):
    sources = [e["source_id"] for e in outcome["report"]["evidence"][:2]]
    outcome["cues"].append({"id": "T12", "kind": "before", "from_atom_id": "H1_A", "to_atom_id": "H2_A",
                           "text": "第1日先于第2日。", "status": "fact", "source_ids": sources})
    outcome["report"]["relations"].append({"from_id": "E1", "to_id": "E2", "kind": "follows", "text": "先后有据。",
                                          "status": "fact", "evidence_ids": ["Q1", "Q2"]})
    outcome["supports"].append({"key": "r0", "fact_ids": ["T12", "H1_A", "H2_A"], "phases": ["actual"]})
    outcome["edge_bindings"].append({"key": "r0", "cue_id": "T12"})
    outcome["cue_resolutions"].append({"cue_id": "T12", "target": "r0", "reason": None})
