"""Author two-stage synthetic replies; production has no legacy-preview bypass."""
from copy import deepcopy


def preview_pair(wire):
    wire = deepcopy(wire)
    sources = {item["id"]: item["source_id"] for item in wire["evidence"]}
    facts = {"chapter_numbers": wire["chapter_numbers"], "characters": [], "atoms": [], "cues": []}
    checked = {"report": wire, "supports": [], "event_bindings": [], "edge_bindings": [], "cue_resolutions": []}

    def add_claim(key, claim, subject, *, object_id=None):
        atom_id = f"A{len(facts['atoms']) + 1}"
        facts["atoms"].append({"id": atom_id, "subject_id": subject, "object_id": object_id,
            "text": claim["text"], "kind": "action", "status": claim["status"], "phase": "actual",
            "time_anchor": "当下", "source_ids": [sources.get(q, "S1_" + "0" * 20) for q in claim["evidence_ids"]]})
        checked["supports"].append({"key": key, "fact_ids": [atom_id], "phases": ["actual"]})
        return atom_id

    for person in wire["characters"]:
        facts["characters"].append({"id": person["id"], "name": person["name"], "aliases": person.get("aliases", []),
            "source_ids": [sources.get(q, "S1_" + "0" * 20) for q in person["identity"]["evidence_ids"]]})
        for field in ("identity", "motivation", "change", "portrait"):
            if person.get(field) is not None:
                add_claim(f"{person['id']}.{field}", person[field], person["id"])
        for index, claim in enumerate(person.get("insights", [])):
            add_claim(f"{person['id']}.insights.{index}", claim, person["id"])
    for event in wire["events"]:
        subject = next(iter(event["actor_ids"]), None)
        ids = [add_claim(f"{event['id']}.{field}", event[field], subject) for field in ("action", "consequence")]
        for index, claim in enumerate(event.get("sub_events", [])):
            ids.append(add_claim(f"{event['id']}.sub_events.{index}", claim, subject))
        checked["event_bindings"].append({"event_id": event["id"], "atom_ids": ids})
    for item in wire["findings"]:
        add_claim(item["id"], item, None)
    for index, item in enumerate(wire.get("contradictions", [])):
        add_claim(f"x{index}", item, None)
    # Existing endpoint fixtures contain no relationships; relationship-specific
    # tests author their atomic witnesses explicitly instead of guessing here.
    if wire["relations"] or wire.get("character_relations"):
        raise AssertionError("Author relationship witnesses explicitly in this fixture")
    return facts, checked
