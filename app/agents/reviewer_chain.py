"""Reviewer Agent 的 LangChain 结构化输出链。"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.models import CharacterCard, ChapterDraft, ReviewerOutput
from core.config import settings


reviewer_llm = ChatOpenAI(
    model=settings.llm_model,
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
    temperature=0.2,
    streaming=False,
)

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
            "【人物卡片】\n{characters}\n\n"
            "【已确认剧情节点】\n{plot_beats}\n\n"
            "【章节草稿】\n{draft}\n\n"
            "必须返回如下顶层 JSON 结构：\n"
            "{{\"passed\":true,\"quality_score\":8.0,"
            "\"reviewer_comments\":[\"...\"],\"revision_suggestions\":[\"...\"]}}\n\n"
            "审查要求：\n"
            "1. reviewer_comments 只写真实存在的问题；没有明显问题时返回空数组。\n"
            "2. revision_suggestions 要具体到可修改的段落、人物行为、冲突推进或设定补强。\n"
            "3. 若存在严重 OOC、关键逻辑断裂或设定冲突，passed 必须为 false。\n"
            "4. quality_score 使用 0-10 分，7 分以上才建议通过。",
        ),
    ]
)

reviewer_chain = reviewer_prompt | reviewer_llm.with_structured_output(ReviewerOutput)


def review_chapter_with_llm(
    *,
    worldview: str,
    global_lore: dict[str, str],
    characters: list[CharacterCard],
    draft: ChapterDraft,
) -> ReviewerOutput:
    """调用 LLM 审查章节草稿。"""

    return reviewer_chain.invoke(
        {
            "chapter_number": draft.chapter_number,
            "worldview": worldview or "暂无世界观，请只基于章节内部自洽性审查。",
            "global_lore": global_lore or {},
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
