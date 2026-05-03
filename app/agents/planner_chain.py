"""Planner Agent 的 LangChain 结构化输出链。"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.models import CharacterCard, PlannerOutput
from core.config import settings


planner_llm = ChatOpenAI(
    model=settings.llm_model,
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
    temperature=settings.llm_temperature,
    streaming=False,
)

planner_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是资深网文责编与剧情架构师，负责为长篇网文生成单章剧情节点。"
            "必须严格遵守既有世界观、人物状态和前文摘要，避免角色 OOC、逻辑跳跃和过早揭露核心谜底。"
            "输出必须是符合 JSON schema 的结构化 JSON 数据，剧情节点要具体、可执行，并适合交给 Writer 扩写正文。"
            "不要输出 Markdown，不要输出解释性文字，只返回 JSON。",
        ),
        (
            "user",
            "请为第 {chapter_number} 章生成 3 到 6 个剧情节点。\n\n"
            "【世界观】\n{worldview}\n\n"
            "【前文摘要】\n{previous_summary}\n\n"
            "【人物卡片】\n{characters}\n\n"
            "【本章创作要求】\n{user_instruction}\n\n"
            "必须返回如下顶层 JSON 结构：\n"
            "{{\"plot_beats\":[{{\"order\":1,\"summary\":\"...\",\"purpose\":\"...\","
            "\"involved_characters\":[\"...\"],\"location\":\"...\",\"conflict\":\"...\","
            "\"expected_outcome\":\"...\",\"continuity_constraints\":[\"...\"]}}],"
            "\"planner_notes\":[\"...\"]}}\n\n"
            "要求：\n"
            "1. 每个节点都要有明确 summary、purpose、conflict、expected_outcome。\n"
            "2. 顶层字段必须使用 plot_beats，不要使用 nodes。\n"
            "3. involved_characters 只能填写已知人物名，除非剧情确实需要引入新角色。\n"
            "4. continuity_constraints 要写出本节点必须遵守的设定或伏笔。\n"
            "5. 结尾节点要形成可推动下一章的悬念。",
        ),
    ]
)

planner_chain = planner_prompt | planner_llm.with_structured_output(PlannerOutput)


def generate_plot_beats_with_llm(
    *,
    chapter_number: int,
    worldview: str,
    previous_summary: str,
    characters: list[CharacterCard],
    user_instruction: str,
) -> PlannerOutput:
    """调用 LLM 生成章节剧情节点。"""

    return planner_chain.invoke(
        {
            "chapter_number": chapter_number,
            "worldview": worldview or "暂无世界观，请根据用户要求生成，但要保持自洽。",
            "previous_summary": previous_summary or "暂无前文摘要，本章可作为开篇处理。",
            "characters": "\n".join(
                character.model_dump_json(indent=2, exclude_none=True)
                for character in characters
            )
            or "暂无人物卡片，可按需要引入主要人物。",
            "user_instruction": user_instruction or "保持主线推进，并制造清晰的章节钩子。",
        }
    )
