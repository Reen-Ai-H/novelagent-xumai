"""Librarian Agent 的 LangChain 结构化输出链。"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from app.agents.llm_runtime import build_chat_model
from app.models import CharacterCard, ChapterDraft, LibrarianOutput

librarian_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是小说设定库管理员，负责从章节正文中抽取稳定事实。"
            "只抽取正文已经明确发生或强确认的信息，不要把猜测当作设定。"
            "输出必须是符合 JSON schema 的结构化 JSON 数据，只返回 JSON，不要 Markdown。",
        ),
        (
            "user",
            "请从以下章节草稿中抽取世界观、人物状态、关系变化、道具、地点和伏笔信息。\n\n"
            "【现有世界观设定】\n{global_lore}\n\n"
            "【现有人物卡】\n{characters}\n\n"
            "【章节草稿】\n{draft}\n\n"
            "必须返回如下顶层 JSON 结构：\n"
            "{{\"global_lore_updates\":{{\"key\":\"value\"}},"
            "\"character_updates\":[{{\"name\":\"...\",\"profile\":\"...\"}}],"
            "\"extraction_notes\":[\"...\"]}}\n\n"
            "要求：\n"
            "1. global_lore_updates 的 key 使用英文或拼音风格短 key，例如 chapter_1_summary、item_bronze_key。\n"
            "2. character_updates 必须符合 CharacterCard 字段；若信息不足，至少提供 name 和 profile。\n"
            "3. 不要重复抽取已有且没有变化的设定。\n"
            "4. 对不确定信息放入 extraction_notes，而不是写入稳定设定。",
        ),
    ]
)

librarian_llm = build_chat_model(temperature=0.2)
librarian_chain = (
    librarian_prompt | librarian_llm.with_structured_output(LibrarianOutput)
    if librarian_llm
    else None
)


def extract_lore_with_llm(
    *,
    global_lore: dict[str, str],
    characters: list[CharacterCard],
    draft: ChapterDraft,
) -> LibrarianOutput:
    """调用 LLM 从章节草稿中抽取设定增量。"""

    if librarian_chain is None:
        raise RuntimeError("未配置模型密钥，无法执行 Librarian；当前请求可使用确定性降级路径。")

    return librarian_chain.invoke(
        {
            "global_lore": global_lore or {},
            "characters": "\n".join(
                character.model_dump_json(indent=2, exclude_none=True)
                for character in characters
            )
            or "暂无人物卡。",
            "draft": draft.model_dump_json(indent=2, exclude_none=True),
        }
    )
