"""Reviewer Agent 的 LangChain 结构化输出链。"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from app.agents.llm_runtime import build_chat_model
from app.core.retriever import format_retrieved_context
from app.models import CharacterCard, ChapterDraft, RetrievalContext, ReviewerOutput

reviewer_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是严格的中文网文审稿编辑，负责检查章节草稿是否存在角色 OOC、逻辑漏洞、设定冲突、节奏问题和伏笔断裂。"
            "必须基于已给出的世界观、人物卡、剧情节点和章节正文审查，不要虚构正文之外的问题。"
            "输出必须是符合 JSON schema 的结构化 JSON 数据，只返回 JSON，不要 Markdown。",
        ),
        (
            "user",
            "请审查第 {chapter_number} 章草稿。\n\n"
            "【世界观】\n{worldview}\n\n"
            "【设定库】\n{global_lore}\n\n"
            "【相关长期记忆】\n{retrieved_context}\n\n"
            "【人物卡片】\n{characters}\n\n"
            "【已确认剧情节点】\n{plot_beats}\n\n"
            "【章节草稿】\n{draft}\n\n"
            "必须返回如下顶层 JSON 结构：\n"
            "{{\"passed\":true,\"quality_score\":8.0,"
            "\"reviewer_comments\":[\"...\"],\"revision_suggestions\":[\"...\"]}}\n\n"
            "审查要求：\n"
            "1. reviewer_comments 只写真实存在的问题；没有明显问题时返回空数组。\n"
            "2. revision_suggestions 要具体到可修改的段落、人物行为、冲突推进或设定补强。\n"
            "3. 检查草稿是否违背相关长期记忆中的稳定事实、人物状态、地点道具和伏笔。\n"
            "4. 若存在严重 OOC、关键逻辑断裂、伏笔断裂或设定冲突，passed 必须为 false。\n"
            "5. 第一稿必须严格审查，节奏重复、章节相似、人物动机弱、承接不足、伏笔无推进都要扣分。\n"
            "6. 多章节批量生成的第一稿，除非承接、人物动机、冲突升级和伏笔推进都非常扎实，否则建议修订。\n"
            "7. quality_score 使用 0-10 分，低于 8.5 默认不通过；8.5 以上也必须没有关键问题才可 passed=true。",
        ),
    ]
)

reviewer_llm = build_chat_model(temperature=0.2)
reviewer_chain = (
    reviewer_prompt | reviewer_llm.with_structured_output(ReviewerOutput)
    if reviewer_llm
    else None
)


def review_chapter_with_llm(
    *,
    worldview: str,
    global_lore: dict[str, str],
    characters: list[CharacterCard],
    draft: ChapterDraft,
    retrieved_context: list[RetrievalContext] | None = None,
) -> ReviewerOutput:
    """调用 LLM 审查章节草稿。"""

    if reviewer_chain is None:
        raise RuntimeError("未配置模型密钥，无法执行 Reviewer；当前请求可使用确定性降级路径。")

    return reviewer_chain.invoke(
        {
            "chapter_number": draft.chapter_number,
            "worldview": worldview or "暂无世界观，请只基于章节内部自洽性审查。",
            "global_lore": global_lore or {},
            "retrieved_context": format_retrieved_context(retrieved_context or []),
            "characters": "\n".join(
                character.model_dump_json(indent=2, exclude_none=True)
                for character in characters
            )
            or "暂无人物卡片。",
            "plot_beats": "\n".join(
                beat.model_dump_json(indent=2, exclude_none=True)
                for beat in draft.plot_beats
            ),
            "draft": draft.model_dump_json(indent=2, exclude_none=True),
        }
    )
