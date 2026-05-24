"""Writer Agent 的 LangChain 结构化输出链。"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.models import ChapterDraft, CharacterCard, PlotBeat, RetrievalContext, WriterOutput
from app.core.retriever import format_retrieved_context
from core.config import settings


writer_llm = ChatOpenAI(
    model=settings.llm_model,
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
    temperature=settings.llm_temperature,
    streaming=False,
)

writer_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是成熟的中文网文主笔，擅长把剧情节点扩写成可读性强的章节正文。"
            "必须遵守人物设定、世界观和用户审核后的剧情节点，不要擅自改变主线结果。"
            "输出必须是符合 JSON schema 的结构化 JSON 数据，只返回 JSON，不要 Markdown。",
        ),
        (
            "user",
            "请根据以下信息撰写第 {chapter_number} 章正文。\n\n"
            "【世界观】\n{worldview}\n\n"
            "【前文摘要】\n{previous_summary}\n\n"
            "【长期记忆检索结果】\n{retrieved_context}\n\n"
            "【人物卡片】\n{characters}\n\n"
            "【用户审核意见】\n{human_feedback}\n\n"
            "【已确认剧情节点】\n{plot_beats}\n\n"
            "【上一版草稿】\n{previous_draft}\n\n"
            "必须返回如下顶层 JSON 结构：\n"
            "{{\"title\":\"章节标题\",\"content\":\"章节正文\",\"writing_notes\":[\"...\"]}}\n\n"
            "写作要求：\n"
            "1. 正文应有网文阅读感，使用自然段，不要只复述剧情节点。\n"
            "2. 长期记忆中的稳定事实优先级高于自由发挥，必须保持人物状态、地点、道具和伏笔连续。\n"
            "3. 保留 Planner 安排的冲突和章节钩子。\n"
            "4. 如长期记忆和本章剧情节点冲突，以已确认剧情节点为本章目标，但在 writing_notes 中说明需要用户确认。\n"
            "5. 当前阶段可生成中短篇幅草稿，约 1200-2000 字。",
        ),
    ]
)

writer_chain = writer_prompt | writer_llm.with_structured_output(WriterOutput)


def generate_chapter_with_llm(
    *,
    chapter_number: int,
    worldview: str,
    previous_summary: str,
    characters: list[CharacterCard],
    plot_beats: list[PlotBeat],
    human_feedback: str | None,
    previous_draft: ChapterDraft | None = None,
    retrieved_context: list[RetrievalContext] | None = None,
) -> WriterOutput:
    """调用 LLM 生成章节正文。"""

    return writer_chain.invoke(
        {
            "chapter_number": chapter_number,
            "worldview": worldview or "暂无世界观，请保持剧情自洽。",
            "previous_summary": previous_summary or "暂无前文摘要。",
            "retrieved_context": format_retrieved_context(retrieved_context or []),
            "characters": "\n".join(
                character.model_dump_json(indent=2, exclude_none=True)
                for character in characters
            )
            or "暂无人物卡片。",
            "human_feedback": human_feedback or "用户已同意当前剧情节点。",
            "plot_beats": "\n".join(
                beat.model_dump_json(indent=2, exclude_none=True)
                for beat in plot_beats
            ),
            "previous_draft": previous_draft.model_dump_json(indent=2, exclude_none=True)
            if previous_draft
            else "暂无上一版草稿，本次为首次生成。",
        }
    )
