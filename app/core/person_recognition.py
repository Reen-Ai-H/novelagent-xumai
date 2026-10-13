"""Conservative Chinese person candidates, with auditable source positions.

This is a small lexical/context heuristic, not general NER. A nearby verb alone
does not establish identity: grammatical fragments, scenery and collectives are
negative evidence, including when repeated or present in a 人物 label.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
from typing import Iterable, Protocol


class TextSource(Protocol):
    chapter_id: str
    content: str


@dataclass(frozen=True)
class PersonMention:
    name: str
    chapter_id: str
    start: int
    origin: str  # archive / label / subject / object / weak_subject / weak_object


# Lexical categories, never a list of approved personal names or a person cap.
_NON_PERSON = {
    "雨水", "天色", "夜色", "石阶", "歌声", "钟声", "河岸", "街巷", "旧站",
    "钟楼", "钥匙", "铜钥匙", "脚印", "真相", "地图", "船票", "绳索",
    "书店", "院子", "屋内", "墙壁", "门后", "天空", "雨落", "空庭", "缺角",
    "路标", "驿站", "树林", "森林", "石门", "木门", "山林", "山峰", "风声",
    "月光", "阳光", "灯光", "灯火", "海面", "湖水", "河水", "寒意", "雾气", "大雨",
    "山道", "走廊", "街道", "屋顶", "回声", "影子", "雷声", "寒风", "阵雨",
    "蓝色", "红色", "绿色", "白色", "黑色", "金色", "灰色", "颜色",
    "方向", "声音", "答案", "消息", "东西", "事情", "理由", "机会", "结果", "道路",
    "众人", "众生", "群众", "人群", "大家", "百姓", "村民", "士兵", "围观者",
    "两人", "二人", "三人", "一个人", "所有人", "有人", "无人", "老人", "男子",
    "女子", "少年", "少女", "姑娘", "孩子", "姐姐", "妹妹", "哥哥", "母亲", "父亲",
}
_FUNCTIONS = (
    "与此同时", "三年前", "两人一起", "因为", "然后", "接着", "随后", "终于",
    "此时", "同时", "于是", "因此", "所以", "后来", "现在", "只是", "已经",
    "正在", "忽然", "突然", "先前", "以前", "当时", "渐渐", "慢慢", "立刻",
    "我们", "你们", "他们", "她们", "自己", "雨后", "风中", "夜里", "门外",
    "急忙", "连忙", "轻轻", "缓缓", "悄悄", "匆匆", "默默", "渐渐", "慢慢",
    "转身", "回头", "点头", "摇头", "低声", "轻声", "开口", "抬头", "低头",
    "站起", "坐下", "犹豫", "忍不住", "沉默",
)
_ACTIONS = (
    "想", "要", "在", "把", "将", "用", "拿", "带", "给", "对", "问", "说",
    "看", "听", "站", "走", "来", "去", "找到", "寻找", "害怕", "决定",
    "答应", "赶来", "帮助", "递", "交给", "打开", "推开", "点亮", "继续",
    "沿", "记录", "抛", "拖", "离开", "回家", "解释", "公开", "发现",
    "进入", "遇见", "收到", "保护", "守住", "合作", "回答", "询问", "喊", "笑",
    "抬", "点头", "摇头", "转身", "握", "接过", "收好", "低声", "轻声",
    "没有", "没", "未", "并没有", "并未", "并不", "并非", "从未", "未曾",
    "不", "拒绝", "拒不", "不能", "不会", "不肯", "不愿", "不再", "终于",
)
_OBJECT_VERBS = (
    "交给", "递给", "帮助", "保护", "找到", "寻找", "遇见", "看见",
    "提到", "等着", "跟着", "带着", "告诉", "询问", "问", "叫作", "名叫", "叫做", "替", "给", "对",
)
_WEAK_ACTIONS = ("在", "对", "看", "听", "要")
_COMPOUND_SURNAMES = {
    "欧阳", "司马", "上官", "诸葛", "东方", "皇甫", "尉迟", "公孙", "慕容",
    "令狐", "宇文", "司徒", "司空", "独孤", "南宫", "夏侯", "长孙", "闻人",
    "端木", "轩辕", "百里", "西门", "东郭", "南郭", "呼延", "公羊", "澹台",
}
_BOUNDARY = set("，,。！？!?；;：: \t\r\n\"“”「」‘’（）()、")
_OBJECT_PATTERN = re.compile("(?:" + "|".join(map(re.escape, sorted(_OBJECT_VERBS, key=len, reverse=True))) + r")\s*")
_PREDICATE_PREFIX = re.compile(r"^(?:(?:正在|已经|曾经|仍然|从来|终于|曾|又|也|仍|还|都|并|就|才)\s*)+")
_LEADING_ADVERBS = ("与此同时", "后来", "随后", "于是", "突然", "忽然", "接着", "终于", "此时", "同时")


def _action_after(tail: str) -> str:
    tail = _PREDICATE_PREFIX.sub("", tail.lstrip(" \t"))
    return next((action for action in _ACTIONS if tail.startswith(action)), "")


def plausible_person(value: str, *, explicit: bool = False) -> bool:
    if not 2 <= len(value) <= (20 if explicit else 4):
        return False
    if value in _NON_PERSON or value.startswith(_FUNCTIONS):
        return False
    if any(value.startswith(term) for term in _NON_PERSON):
        return False
    if not explicit and (not re.fullmatch(r"[\u4e00-\u9fff]+", value)
                         or value[0] in "我你他她它这那其此每各两一因所"
                         or any(char in value for char in "的了着地得")):
        return False
    return bool(re.fullmatch(r"[\u4e00-\u9fffA-Za-z·・\- ]+", value))


def discover_person_mentions(chapters: Iterable[TextSource], archive_names: Iterable[str] = ()) -> list[PersonMention]:
    chapters = tuple(chapters)
    archive_names = tuple(archive_names)
    mentions: dict[str, list[PersonMention]] = defaultdict(list)
    explicit_names: list[str] = []

    def add(name, chapter, position, origin):
        if plausible_person(name, explicit=origin in {"label", "archive"}):
            mentions[name].append(PersonMention(name, chapter.chapter_id, position, origin))
            if origin in {"label", "archive"} and name not in explicit_names:
                explicit_names.append(name)

    for chapter in chapters:
        text = chapter.content
        for name in archive_names:
            position = text.find(name)
            if position >= 0:
                add(name, chapter, position, "archive")
        for match in re.finditer(r"人物\s*[:：]\s*([^\n。；;]+)", text):
            for candidate in re.finditer(r"[^、，,；;]+", match.group(1)):
                value = candidate.group().strip(" ：:，,、；;")
                position = match.start(1) + candidate.start() + candidate.group().find(value)
                # Conjunctions may occur in a given name (沈与安). Split an
                # unpunctuated list only when both sides have name-sized spans.
                combined = re.fullmatch(r"([\u4e00-\u9fff]{2,4})\s*[和与及]\s*([\u4e00-\u9fff]{2,4})", value)
                if combined:
                    for group in (1, 2):
                        add(combined.group(group), chapter, position + combined.start(group), "label")
                else:
                    add(value, chapter, position, "label")
        # Scan Chinese runs only at a clause boundary. Testing a bounded prefix
        # avoids both greedy action adhesion and repeated scans of the full tail.
        for match in re.finditer(r"[\u4e00-\u9fff]+", text):
            start = match.start()
            for adverb in _LEADING_ADVERBS:
                if match.group().startswith(adverb):
                    start += len(adverb)
                    break
            for length in (2, 3, 4):
                name = text[start:start + length]
                if length == 2 and name in _COMPOUND_SURNAMES:
                    continue
                if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
                    continue
                action = _action_after(text[start + length:start + length + 16])
                if action:
                    add(name, chapter, start, "weak_subject" if action in _WEAK_ACTIONS else "subject")
                    break
        protected_spans = [(m.start, m.start + len(m.name)) for values in mentions.values()
                           for m in values if m.chapter_id == chapter.chapter_id]
        for match in _OBJECT_PATTERN.finditer(text):
            # A character such as 问 can be part of a complete name (苏问溪).
            # Do not reinterpret a verb match inside an already bounded name.
            if any(left <= match.start() < right for left, right in protected_spans):
                continue
            start = match.end()
            for length in (2, 3, 4):
                name = text[start:start + length]
                if length == 2 and name in _COMPOUND_SURNAMES:
                    continue
                if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
                    continue
                after = text[start + length: start + length + 16]
                if not after or after[0] in _BOUNDARY or _action_after(after):
                    add(name, chapter, start, "weak_object" if match.group().strip() in {"替", "给", "对"} else "object")
                    break

    # Source order breaks ties and does not impose a maximum number of people.
    source_order = {chapter.chapter_id: i for i, chapter in enumerate(chapters)}
    inferred = sorted((name for name in mentions if name not in explicit_names
                       and (any(m.origin in {"subject", "object"} for m in mentions[name])
                            or len({(m.chapter_id, m.start) for m in mentions[name]}) >= 2)),
                      key=lambda name: min((source_order[m.chapter_id], m.start) for m in mentions[name]))
    return [mention for name in explicit_names + inferred for mention in mentions[name]]


def discover_person_names(chapters: Iterable[TextSource], archive_names: Iterable[str] = ()) -> list[str]:
    return list(dict.fromkeys(m.name for m in discover_person_mentions(chapters, archive_names)))
