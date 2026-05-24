"""小说共创工作流的 Agent 节点骨架。

当前阶段先用确定性逻辑打通状态流转；后续可将每个函数内部替换为
LangChain 结构化输出链，并继续复用这些 Pydantic 模型。
"""

from __future__ import annotations

from app.core.retriever import retrieve_context_for_state
from app.agents.librarian_chain import extract_lore_with_llm
from app.agents.planner_chain import generate_plot_beats_with_llm
from app.agents.reviewer_chain import review_chapter_with_llm
from app.agents.writer_chain import generate_chapter_with_llm
from app.models import ChapterDraft, CharacterCard, NovelState, PlotBeat, RetrievalContext


def _retrieve_context(state: NovelState) -> tuple[list[RetrievalContext], str | None]:
    """检索长期记忆；失败时降级为空上下文，避免阻断创作流程。"""

    try:
        return retrieve_context_for_state(state), None
    except Exception as exc:  # noqa: BLE001 - RAG 失败不能阻断章节生成。
        return [], f"RAG 检索失败，已跳过长期记忆：{exc}"


def _fallback_plot_beats(state: NovelState) -> list[PlotBeat]:
    """LLM 不可用时的降级剧情规划，保证工作流仍可演示。"""

    chapter_number = state.get("current_chapter_number", 1)
    worldview = state.get("global_worldview", "")
    user_instruction = state.get("human_feedback") or "保持主线推进，并制造清晰的章节钩子。"
    character_names = list(state.get("character_graph", {}).keys())
    main_characters = character_names[:3]

    return [
        PlotBeat(
            order=1,
            summary=f"第 {chapter_number} 章开场承接前文，展示主角面临的新局势。",
            purpose="承接上章并重新聚焦主线矛盾",
            involved_characters=main_characters,
            conflict="主角需要在有限信息下做出选择",
            continuity_constraints=[worldview[:120]] if worldview else [],
        ),
        PlotBeat(
            order=2,
            summary="关键人物带来新的线索或阻碍，迫使局势升级。",
            purpose="制造冲突升级和人物互动",
            involved_characters=main_characters,
            conflict="新线索与既有目标发生冲突",
            expected_outcome="主角意识到问题比预期更复杂",
        ),
        PlotBeat(
            order=3,
            summary="章节结尾留下一个可推动下一章的悬念。",
            purpose="形成章节钩子",
            involved_characters=main_characters[:1],
            expected_outcome=user_instruction,
        ),
    ]


def planner_agent(state: NovelState) -> dict:
    """根据全局设定和章节上下文生成本章剧情节点。"""

    chapter_number = state.get("current_chapter_number", 1)
    worldview = state.get("global_worldview", "")
    global_lore = state.get("global_lore", {})
    previous_summary = global_lore.get("previous_summary", "")
    user_instruction = state.get("human_feedback") or "保持主线推进，并制造清晰的章节钩子。"
    characters = [
        character
        for character in state.get("character_graph", {}).values()
        if isinstance(character, CharacterCard)
    ]

    try:
        planner_output = generate_plot_beats_with_llm(
            chapter_number=chapter_number,
            worldview=worldview,
            previous_summary=previous_summary,
            characters=characters,
            user_instruction=user_instruction,
        )
        beats = planner_output.plot_beats
        error_message = None
    except Exception as exc:  # noqa: BLE001 - 节点必须降级，避免单次 LLM 失败中断工作流。
        beats = _fallback_plot_beats(state)
        error_message = f"Planner LLM 调用失败，已使用降级剧情节点：{exc}"

    return {
        "current_plot_beats": beats,
        "current_stage": "awaiting_human_review",
        "human_approved": False,
        "error_message": error_message,
    }


def writer_agent(state: NovelState) -> dict:
    """根据人工确认后的剧情节点生成章节草稿。"""

    chapter_number = state.get("current_chapter_number", 1)
    worldview = state.get("global_worldview", "")
    global_lore = state.get("global_lore", {})
    previous_summary = global_lore.get("previous_summary", "")
    temporary_context = state.get("temporary_context", {})
    if temporary_context:
        temp_parts = [
            temporary_context.get("previous_draft_summary", ""),
            temporary_context.get("previous_hook", ""),
            temporary_context.get("previous_character_state", ""),
            temporary_context.get("recent_draft_summaries", ""),
            temporary_context.get("batch_context_instruction", ""),
        ]
        previous_summary = "\n\n".join(part for part in [previous_summary, *temp_parts] if part)
    human_feedback = state.get("human_feedback")
    previous_draft = state.get("current_draft")
    characters = [
        character
        for character in state.get("character_graph", {}).values()
        if isinstance(character, CharacterCard)
    ]
    plot_beats = sorted(state.get("current_plot_beats", []), key=lambda beat: beat.order)
    retrieved_context, retrieval_error = _retrieve_context(state)

    try:
        writer_output = generate_chapter_with_llm(
            chapter_number=chapter_number,
            worldview=worldview,
            previous_summary=previous_summary,
            characters=characters,
            plot_beats=plot_beats,
            human_feedback=human_feedback,
            previous_draft=previous_draft,
            retrieved_context=retrieved_context,
        )
        title = writer_output.title or f"第 {chapter_number} 章"
        content = writer_output.content
        revision_notes = writer_output.writing_notes
        error_message = retrieval_error
    except Exception as exc:  # noqa: BLE001 - Writer 失败时保留可演示的降级草稿。
        title = f"第 {chapter_number} 章"
        content = "\n\n".join(
            f"【剧情节点 {beat.order}】{beat.summary}"
            for beat in plot_beats
        )
        revision_notes = ["Writer LLM 调用失败，已使用剧情节点生成降级草稿。"]
        error_message = f"Writer LLM 调用失败，已使用降级草稿：{exc}"
        if retrieval_error:
            error_message = f"{retrieval_error}；{error_message}"

    draft = ChapterDraft(
        chapter_number=chapter_number,
        title=title,
        plot_beats=plot_beats,
        content=content,
        status="drafted",
        revision_notes=[
            *(previous_draft.revision_notes if previous_draft else []),
            *revision_notes,
        ],
    )

    return {
        "current_draft": draft,
        "current_stage": "awaiting_review",
        "review_feedback": [],
        "retrieved_context": retrieved_context,
        "error_message": error_message,
    }


def librarian_agent(state: NovelState) -> dict:
    """从草稿中抽取需要合并进设定库的信息。"""

    draft = state.get("current_draft")
    if draft is None:
        return {
            "current_stage": "failed",
            "error_message": "Librarian Agent 未收到章节草稿",
        }

    global_lore = state.get("global_lore", {})
    character_graph = state.get("character_graph", {})
    characters = [
        character
        for character in character_graph.values()
        if isinstance(character, CharacterCard)
    ]

    try:
        librarian_output = extract_lore_with_llm(
            global_lore=global_lore,
            characters=characters,
            draft=draft,
        )
        lore_updates = librarian_output.global_lore_updates
        character_updates = {
            character.name: character
            for character in librarian_output.character_updates
        }
        error_message = None
    except Exception as exc:  # noqa: BLE001 - 设定抽取失败时保留章节摘要作为降级记忆。
        lore_updates = {
            f"chapter_{draft.chapter_number}_summary": "；".join(
                beat.summary for beat in draft.plot_beats
            ),
        }
        character_updates = {}
        error_message = f"Librarian LLM 调用失败，已使用降级设定摘要：{exc}"

    merged_lore = {
        **global_lore,
        **lore_updates,
    }
    merged_characters = {
        **character_graph,
        **character_updates,
    }

    return {
        "global_lore": merged_lore,
        "character_graph": merged_characters,
        "extracted_lore_updates": lore_updates,
        "extracted_character_updates": character_updates,
        "current_stage": "extracting_lore",
        "error_message": error_message,
    }


def reviewer_agent(state: NovelState) -> dict:
    """审查章节草稿是否存在明显 OOC 或逻辑断裂。"""

    draft = state.get("current_draft")
    if draft is None:
        return {
            "current_stage": "failed",
            "error_message": "Reviewer Agent 未收到章节草稿",
        }

    comments: list[str]
    revision_notes = list(draft.revision_notes)
    retrieved_context, retrieval_error = _retrieve_context(state)
    error_message = retrieval_error

    try:
        character_graph = state.get("character_graph", {})
        characters = [
            character
            for character in character_graph.values()
            if isinstance(character, CharacterCard)
        ]
        reviewer_output = review_chapter_with_llm(
            worldview=state.get("global_worldview", ""),
            global_lore=state.get("global_lore", {}),
            characters=characters,
            draft=draft,
            retrieved_context=retrieved_context,
        )
        comments = reviewer_output.reviewer_comments
        if reviewer_output.revision_suggestions:
            revision_notes.extend(
                f"Reviewer 建议：{suggestion}"
                for suggestion in reviewer_output.revision_suggestions
            )
        strict_comments, quality_penalty = _strict_review_findings(state, comments)
        comments = [*comments, *strict_comments]
        quality_score = max(0.0, reviewer_output.quality_score - quality_penalty)
        passed = reviewer_output.passed and quality_score >= 8.5 and not strict_comments
    except Exception as exc:  # noqa: BLE001 - Reviewer 失败时回退到基础规则审查。
        comments = []
        if not draft.content.strip():
            comments.append("正文为空，需要重新生成。")
        if not draft.plot_beats:
            comments.append("缺少剧情节点，无法检查章节逻辑。")
        comments.extend(_strict_review_findings(state, comments)[0])
        passed = False
        quality_score = 6.5 if comments else 7.0
        fallback_note = "Reviewer LLM 调用失败，已使用基础规则审查。"
        revision_notes.append(fallback_note)
        error_message = f"{fallback_note}：{exc}"
        if retrieval_error:
            error_message = f"{retrieval_error}；{error_message}"

    reviewer_comments = comments or ["Reviewer 结构化审查通过，未发现明显 OOC、逻辑断裂或设定冲突。"]
    reviewed_draft = draft.model_copy(
        update={
            "status": "reviewed" if passed else "needs_revision",
            "reviewer_comments": reviewer_comments,
            "revision_notes": revision_notes,
            "quality_score": quality_score,
        }
    )

    return {
        "current_draft": reviewed_draft,
        "review_feedback": reviewed_draft.reviewer_comments,
        "retrieved_context": retrieved_context,
        "current_stage": "awaiting_chapter_acceptance"
        if passed
        else "awaiting_revision_decision",
        "error_message": error_message,
    }


def _strict_review_findings(state: NovelState, existing_comments: list[str]) -> tuple[list[str], float]:
    """生产模式审查补充：第一稿和批量稿默认更严格。"""

    draft = state.get("current_draft")
    if draft is None:
        return [], 0.0

    findings: list[str] = []
    content = draft.content or ""
    compact = "".join(content.split())
    temporary_context = state.get("temporary_context", {})
    global_lore = state.get("global_lore", {})
    previous_summary = global_lore.get("previous_summary", "")
    is_batch_first_draft = temporary_context.get("batch_generation") == "true"
    is_first_draft = not any("Reviewer 建议" in note for note in draft.revision_notes)

    if len(compact) < 800:
        findings.append("章节正文偏短，冲突、情绪转折或场景推进不足，建议扩写关键段落。")

    if previous_summary and not _has_meaningful_overlap(previous_summary, content):
        findings.append("与前文摘要承接不足，读者难以看出本章如何接住上一章局面。")

    if temporary_context.get("previous_hook") and not _has_meaningful_overlap(
        temporary_context["previous_hook"],
        content,
    ):
        findings.append("上一章结尾钩子没有被有效回应，连续阅读时悬念推进不足。")

    similar_chapter = _similar_recent_chapter(
        current_chapter=state.get("current_chapter_number", 0),
        recent_summaries=temporary_context.get("recent_draft_summaries", ""),
        content=content,
    )
    if similar_chapter:
        findings.append(
            f"本章与第 {similar_chapter} 章的场景结构或冲突推进过于相似，需要重做差异化设计。"
        )

    if draft.plot_beats and not any(
        beat.conflict or beat.expected_outcome or beat.purpose for beat in draft.plot_beats
    ):
        findings.append("剧情节点只描述事件，人物动机、冲突压力和结果变化偏弱。")

    if _has_repetitive_segments(content):
        findings.append("章节内部存在节奏或句式重复，场景推进显得相似，需要增加变化。")

    if is_batch_first_draft and is_first_draft and not existing_comments:
        findings.append("批量生成第一稿默认进入严格审查，请人工确认节奏、承接、人物动机和伏笔推进后再接受。")

    unique_findings = list(dict.fromkeys(findings))
    penalty = min(2.5, 0.35 * len(unique_findings))
    return unique_findings, penalty


def _has_meaningful_overlap(left: str, right: str) -> bool:
    left_tokens = _review_tokens(left)
    right_tokens = _review_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    return len(left_tokens & right_tokens) >= min(3, max(1, len(left_tokens) // 8))


def _review_tokens(text: str) -> set[str]:
    cleaned = "".join(char if char.isalnum() or "\u4e00" <= char <= "\u9fff" else " " for char in text)
    latin = {part.lower() for part in cleaned.split() if len(part) >= 3}
    cjk = [char for char in cleaned if "\u4e00" <= char <= "\u9fff"]
    cjk_bigrams = {"".join(cjk[index : index + 2]) for index in range(max(len(cjk) - 1, 0))}
    return latin | cjk_bigrams


def _has_repetitive_segments(content: str) -> bool:
    paragraphs = [paragraph.strip() for paragraph in content.splitlines() if paragraph.strip()]
    if len(paragraphs) < 4:
        return False
    prefixes = [paragraph[:18] for paragraph in paragraphs if len(paragraph) >= 18]
    return len(prefixes) != len(set(prefixes))


def _similar_recent_chapter(
    *,
    current_chapter: int,
    recent_summaries: str,
    content: str,
) -> int | None:
    content_tokens = _review_tokens(content)
    if not content_tokens:
        return None

    for line in recent_summaries.splitlines():
        line = line.strip()
        if not line.startswith("第 ") or "章：" not in line:
            continue
        prefix, summary = line.split("章：", 1)
        try:
            chapter_number = int(prefix.removeprefix("第 ").strip())
        except ValueError:
            continue
        if chapter_number == current_chapter:
            continue
        summary_tokens = _review_tokens(summary)
        if not summary_tokens:
            continue
        overlap = len(content_tokens & summary_tokens)
        similarity = overlap / max(min(len(content_tokens), len(summary_tokens)), 1)
        threshold = 0.38 if abs(current_chapter - chapter_number) > 1 else 0.48
        if similarity >= threshold:
            return chapter_number
    return None
