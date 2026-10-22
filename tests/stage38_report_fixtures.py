"""Synthetic source at manuscript scale, with explicit independent wire authorship."""
from app.core.analysis_grounding import source_bank
from app.core.report_pipeline import ReportDraft, object_hash


def report_case(count=2, *, bulk=False, texts=None):
    if texts is None:
        texts = {n: "".join(f"第{n}日第{i}次验货时，林客与许守在第{n}号渡口核对第{i}份来船记录。"
                            for i in range(1, 113 if bulk else 9)) for n in range(1, count + 1)}
    bank = source_bank(texts)
    passages = {n: [p for p in bank.values() if p.chapter_number == n] for n in texts}
    evidence = []
    keys = {}
    for n, group in passages.items():
        for i, passage in enumerate(group[:8]):
            key = f"Q{n}_{i}"
            evidence.append(dict(id=key, source_id=passage.id))
            keys[n, i] = key
    def claim(n, i=0, *, subject="Lin", obj="Xu"):
        return dict(text="林客与许守核对来船记录。", status="fact", evidence_ids=[keys[n, i]],
                    subject_id=subject, object_id=obj, kind="action", phase="actual")
    first = min(texts)
    characters = []
    for key, name in (("Lin", "林客"), ("Xu", "许守")):
        c = claim(first, subject=key, obj=None)
        c["text"] = name + "参与核对来船记录。"
        characters.append(dict(id=key, name=name, aliases=[], role="主要人物" if key == "Lin" else "实质配角",
                               identity=c, motivation=c, change=c, name_evidence_ids=[keys[first, 0]], alias_basis=[],
                               importance="main" if key == "Lin" else "support",
                               importance_basis=dict(text="参与验货主干。", status="inferred", evidence_ids=[keys[first, 0]])))
    events = []
    for n in texts:
        for letter, offset in (("a", 0), ("b", 4)):
            events.append(dict(id=f"E{n}{letter}", title="核对来船记录", story_time=f"第{n}日", actor_ids=["Lin"],
                               action=claim(n, offset), consequence=claim(n, offset + 1),
                               sub_events=[dict(title="核对记录", **claim(n, i)) for i in range(offset, offset + 4)]))
    relations = []
    for i, (a, b) in enumerate(zip(events, events[1:])):
        n = list(texts)[i // 2]
        relations.append(dict(from_id=a["id"], to_id=b["id"], kind="follows", basis="before",
                              from_action=a["id"] + ".action", to_action=b["id"] + ".action",
                              text="验货记录依次核对。", status="fact", evidence_ids=[keys[n, 0]]))
    draft = dict(title="合成验货报告", scope="所提供的全部正文", chapter_numbers=sorted(texts),
                 findings=[dict(id="Finding", title="共同验货", **claim(first))], characters=characters,
                 events=events, relations=relations, character_relations=[], story_order=[e["id"] for e in events],
                 time_note="按明确日次及验货次序排列。", evidence=evidence, open_questions=[],
                 participants=[], order_constraints=[], question_sources=[], time_evidence_ids=[keys[first, 0]])
    return ReportDraft.model_validate(draft, strict=True).model_dump(mode="json"), bank, texts


def acceptance(draft):
    return dict(decision="accept", draft_hash=object_hash(draft), checked_chapters=draft["chapter_numbers"])
