"""Conservative Chinese person candidates, with auditable source positions.

This is a small lexical/context heuristic, not general NER. A nearby verb alone
does not establish identity: grammatical fragments, scenery and collectives are
negative evidence, including when repeated or present in a 人物 label.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
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
    spelling: str = ""
    predicate: str = ""  # Shared predicate of a coordinated subject, if explicit.


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
    "女子", "少年", "少女", "姑娘", "孩子", "大道", "天道", "画像", "前世", "今生", "死婴",
    "出路", "落叶", "食物", "困难", "环境", "金吾卫", "万人", "西域", "烟花",
    "白雪", "薄雾", "暮色", "红叶", "金钱", "白纸", "文明", "文化", "方法",
    "制度", "命运", "古迹", "武器", "工具", "资源", "规则", "秩序",
}
_MATERIAL_NOUN = re.compile(r"(?:白|黄|红|黑|金|银|铜|铁|木|竹|石)(?:纸|布|钱|币|板|器|料|块|片)$")
_HARD_NON_PERSON = {"我", "你", "他", "她", "它", "我们", "你们", "他们", "她们", "自己",
                    "大道", "天道", "众人", "众生", "群众", "人群", "大家", "百姓", "所有人"}
_FUNCTIONS = (
    "与此同时", "三年前", "两人一起", "因为", "然后", "接着", "随后", "终于",
    "此时", "同时", "于是", "因此", "所以", "后来", "现在", "只是", "已经",
    "正在", "忽然", "突然", "先前", "以前", "当时", "渐渐", "慢慢", "立刻",
    "我们", "你们", "他们", "她们", "自己", "雨后", "风中", "夜里", "门外",
    "急忙", "连忙", "轻轻", "缓缓", "悄悄", "匆匆", "默默", "渐渐", "慢慢",
    "转身", "回头", "点头", "摇头", "低声", "轻声", "开口", "抬头", "低头",
    "站起", "坐下", "犹豫", "忍不住", "沉默",
    "别人", "人们", "应当", "本来", "怎么", "例如", "仔细", "不好", "结果",
    "同我", "跟我", "让我", "让人", "要我", "把头", "伸手", "爆炸", "人还", "且本",
    "出来", "过来", "不是", "不过", "不如", "只好", "也有", "说是", "要是", "好像",
    "都不", "不错", "全然", "总爱", "直接", "乖乖", "说完", "问题", "手上", "身子",
    "从我", "问你", "万一", "哪家", "倘若", "被抱", "很早", "快步", "头发", "可我",
    "反手", "晚上", "月末", "今天", "目前", "自然", "至于", "反正", "谁敢", "然而",
    "早已", "恐怕", "必须", "赶紧", "连人", "听", "从", "宁可", "宁愿", "总是", "总算", "果然", "仍然",
)
_ACTIONS = (
    "想", "要", "在", "把", "将", "用", "拿", "带", "给", "对", "问", "说",
    "看", "听", "站", "走", "来", "去", "找到", "寻找", "害怕", "决定",
    "答应", "赶来", "帮助", "递", "交给", "打开", "推开", "点亮", "继续",
    "沿", "记录", "抛", "拖", "离开", "回家", "解释", "公开", "发现",
    "进入", "遇见", "收到", "保护", "守住", "合作", "回答", "询问", "喊", "笑", "救", "杀", "死", "受伤", "叫",
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
# Surname morphology is a lexical prior, never a list of this work's names.
# Nicknames and single names still enter through explicit naming evidence.
_SURNAMES = set("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
                "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳丰鲍史唐"
                "费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于傅皮卞齐康伍余元卜顾孟平黄和"
                "穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴宋茅庞熊纪舒屈项祝董梁杜阮"
                "蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万"
                "支柯昝管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉龚程嵇邢裴"
                "陆荣翁荀羊甄曲封芮储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全"
                "郗班仰秋仲伊宫宁仇栾甘钭厉戎祖武符刘景詹束龙叶幸司黎韶郜郦薄印宿"
                "白怀蒲邰从鄂索咸赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵"
                "冉宰郏雍郤璩桑桂濮牛寿通边扈燕冀浦尚农温庄晏柴瞿阎充慕连茹习艾鱼"
                "容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东殴殳沃利蔚越夔"
                "隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾沙乜养鞠须巢关蒯相查后荆红游"
                "竺权逯盖益桓公北南西")
_RELATIVES = {"父亲", "母亲", "爹爹", "娘亲", "爸爸", "妈妈", "姐姐", "哥哥", "妹妹", "弟弟", "爷爷", "奶奶"}
_ROLE = re.compile(r"(?:皇帝爹爹|皇后[\u4e00-\u9fff]{0,3}|皇帝陛下|皇帝|太后|太子|先帝|陛下|大神官|"
                   r"[\u4e00-\u9fff]{1,3}(?:姨|叔|姐|哥|师父|老师|先生|将军|大人))$")
_GRAMMAR = set("的了着地得不也还把被让跟向且便本都正应能会是有进过时们并虽")
_BOUNDARY = set("，,。！？!?；;：: \t\r\n\"“”「」‘’（）()、")
_OBJECT_PATTERN = re.compile("(?:" + "|".join(map(re.escape, sorted(_OBJECT_VERBS, key=len, reverse=True))) + r")\s*")
_PREDICATE_PREFIX = re.compile(r"^(?:(?:正在|已经|曾经|仍然|从来|终于|曾|又|也|仍|还|都|并|就|才)\s*)+")
_LEADING_ADVERBS = ("与此同时", "后来", "随后", "于是", "突然", "忽然", "接着", "终于", "此时", "同时")


def _action_after(tail: str) -> str:
    tail = _PREDICATE_PREFIX.sub("", tail.lstrip(" \t"))
    return next((action for action in _ACTIONS if tail.startswith(action)), "")


def _personal_use(value: str, text: str) -> bool:
    """A declaration may override a lexical noun prior, not a hard identity ban.

    In particular '石门没有消失' is not human behavior; negation itself is
    not enough. This deliberately cannot decide every metaphor or namesake.
    """
    for match in re.finditer(re.escape(value), text):
        tail = _PREDICATE_PREFIX.sub("", text[match.end():match.end() + 24].lstrip())
        tail = re.sub(r"^(?:并没有|并未|从未|没有|不能|不会|不肯|不愿|不再|未曾|未|没|不)", "", tail)
        if re.match(r"(?:拿|把|问|说|回答|询问|救|拒绝|答应|决定|走|离开|回家|保护|帮助|接过|握|抬|点头|摇头|转身)", tail):
            return True
    return False


def plausible_person(value: str, *, explicit: bool = False, lexical_override: bool = False) -> bool:
    if not (1 if explicit else 2) <= len(value) <= (20 if explicit else 4):
        return False
    if value in _HARD_NON_PERSON or any(value.startswith(term) for term in _HARD_NON_PERSON if len(term) > 1):
        return False
    if value.startswith(_FUNCTIONS):
        return False
    if not lexical_override and (any(value.startswith(term) for term in _NON_PERSON) or _MATERIAL_NOUN.fullmatch(value)):
        return False
    if not explicit and (not re.fullmatch(r"[\u4e00-\u9fff]+", value)
                         or value[0] in "我你他她它这那其此每各两一因所"
                         or any(char in value for char in "的了着地得")):
        return False
    if not re.fullmatch(r"[\u4e00-\u9fffA-Za-z·・\- ]+", value):
        return False
    if value in _RELATIVES or _ROLE.fullmatch(value):
        return True
    if explicit:
        return not any(char in value for char in "把被让的了着们")
    if any(char in value for char in "把被让的了着们") or value[-1] in _GRAMMAR:
        return False
    if value[:2] in _COMPOUND_SURNAMES:
        return len(value) in {3, 4}
    return len(value) in {2, 3} and (value[0] in _SURNAMES or value[0] in "阿小老")


def discover_person_mentions(chapters: Iterable[TextSource], archive_names: Iterable[str] = ()) -> list[PersonMention]:
    chapters = tuple(chapters)
    archive_names = tuple(archive_names)
    mentions: dict[str, list[PersonMention]] = defaultdict(list)
    explicit_names: list[str] = []
    lexical_names: set[str] = set()

    def add(name, chapter, position, origin, predicate=""):
        explicit = origin in {"label", "archive"}
        override = name in lexical_names or (explicit and _personal_use(name, chapter.content))
        if plausible_person(name, explicit=explicit or name in explicit_names, lexical_override=override):
            if override:
                lexical_names.add(name)
            mentions[name].append(PersonMention(name, chapter.chapter_id, position, origin, predicate=predicate))
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
        defined_names = {m.name for values in mentions.values() for m in values if m.origin in {"label", "archive"}}
        # Scan Chinese runs only at a clause boundary. Testing a bounded prefix
        # avoids both greedy action adhesion and repeated scans of the full tail.
        for match in re.finditer(r"[\u4e00-\u9fff]+", text):
            start = match.start()
            for adverb in _LEADING_ADVERBS:
                if match.group().startswith(adverb):
                    start += len(adverb)
                    break
            # Resolve a whole coordinated subject before its shared verb. Each
            # component must pass identity checks; no fixed maximum person count.
            coordinated = []
            cursor = start
            while True:
                part = re.match(r"([\u4e00-\u9fff]{2,4}?)([和与及、])", text[cursor:cursor + 5])
                if not part or not plausible_person(part.group(1), explicit=part.group(1) in defined_names,
                                                     lexical_override=part.group(1) in lexical_names):
                    break
                coordinated.append((part.group(1), cursor))
                cursor += part.end()
            if coordinated:
                endings = []
                for length in (2, 3, 4):
                    name = text[cursor:cursor + length]
                    tail = text[cursor + length:cursor + length + 24]
                    predicate_tail = re.sub(r"^(?:一起|一同|共同)", "", tail)
                    action = _action_after(predicate_tail)
                    if action and plausible_person(name, explicit=name in defined_names, lexical_override=name in lexical_names):
                        endings.append((name, action))
                if endings:
                    name, action = (max(endings, key=lambda c: len(c[0])) if endings[0][1] in {"问", "在", "笑"} else endings[0])
                    for component, position in coordinated + [(name, cursor)]:
                        add(component, chapter, position, "weak_subject" if action in _WEAK_ACTIONS else "subject", action)
                    continue
            known_full_names = [name for name in defined_names if text.startswith(name, start)]
            if known_full_names:
                complete_name = max(known_full_names, key=len)
                complete_action = _action_after(text[start + len(complete_name):start + len(complete_name) + 16])
                if complete_action:
                    add(complete_name, chapter, start, "weak_subject" if complete_action in _WEAK_ACTIONS else "subject")
                continue
            choices = []
            for length in (2, 3, 4):
                name = text[start:start + length]
                if length == 2 and name in _COMPOUND_SURNAMES:
                    continue
                if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
                    continue
                action = _action_after(text[start + length:start + length + 16])
                if action == "对" and re.match(r"对[\u4e00-\u9fff]{2,4}(?:说|问|喊)", text[start + length:]):
                    action = "说"
                if action and plausible_person(name):
                    choices.append((name, action))
            if choices:
                explicit_choices = [choice for choice in choices if choice[0] in defined_names]
                # Longer is justified by an explicit complete name, or a
                # conventional given-name glyph that also acts as a verb.
                # Otherwise “林舟想找到” must remain 林舟, not 林舟想.
                if explicit_choices:
                    name, action = max(explicit_choices, key=lambda item: len(item[0]))
                elif choices[0][1] in {"问", "在", "笑"}:
                    name, action = max(choices, key=lambda item: len(item[0]))
                else:
                    name, action = choices[0]
                add(name, chapter, start, "weak_subject" if action in _WEAK_ACTIONS else "subject")
        protected_spans = [(m.start, m.start + len(m.name)) for values in mentions.values()
                           for m in values if m.chapter_id == chapter.chapter_id]
        for match in _OBJECT_PATTERN.finditer(text):
            # A character such as 问 can be part of a complete name (苏问溪).
            # Do not reinterpret a verb match inside an already bounded name.
            if any(left <= match.start() < right for left, right in protected_spans):
                continue
            start = match.end()
            choices = []
            for length in (2, 3, 4):
                name = text[start:start + length]
                if length == 2 and name in _COMPOUND_SURNAMES:
                    continue
                if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
                    continue
                after = text[start + length: start + length + 16]
                terminal = not after or after[0] in _BOUNDARY
                if (terminal or _action_after(after)) and plausible_person(name, explicit=name in defined_names,
                                                                           lexical_override=name in lexical_names):
                    # Speech verbs belong to the predicate, not the addressee.
                    if name.endswith(("说", "喊", "答应")) and match.group().strip() in {"对", "给", "问", "告诉"}:
                        continue
                    choices.append((name, terminal))
            if choices:
                declared = [c for c in choices if c[0] in defined_names]
                terminal = [c for c in choices if c[1]]
                shortest = choices[0][0]
                # A terminal span is stronger than a possible given-name verb
                # (段天问 / 陈自在), but not permission to absorb an action
                # such as 林舟走 / 林舟说 into a new three-character name.
                ambiguous = _action_after(text[start + len(shortest):start + len(shortest) + 16]) in {"问", "在", "笑"}
                preferred = declared or (terminal if ambiguous else [])
                name = max(preferred, key=lambda c: len(c[0]))[0] if preferred else shortest
                add(name, chapter, start, "weak_object" if match.group().strip() in {"替", "给", "对"} else "object")

    # Source order breaks ties and does not impose a maximum number of people.
    source_order = {chapter.chapter_id: i for i, chapter in enumerate(chapters)}
    inferred = sorted((name for name in mentions if name not in explicit_names
                       and (any(m.origin in {"subject", "object"} for m in mentions[name])
                            or len({(m.chapter_id, m.start) for m in mentions[name]}) >= 2)),
                      key=lambda name: min((source_order[m.chapter_id], m.start) for m in mentions[name]))
    return [mention for name in explicit_names + inferred for mention in mentions[name]]


def discover_person_names(chapters: Iterable[TextSource], archive_names: Iterable[str] = ()) -> list[str]:
    return list(dict.fromkeys(m.name for m in discover_person_mentions(chapters, archive_names)))


@dataclass(frozen=True)
class PersonIdentity:
    name: str
    aliases: tuple[str, ...]
    mentions: tuple[PersonMention, ...]
    mention_count: int
    paragraph_count: int
    action_count: int
    contribution_count: int
    identity_confidence: float
    importance: str  # main / supporting / incidental
    importance_reason: str
    definition_spans: tuple[tuple[str, int, int], ...] = ()


_ALIAS = re.compile(r"(?<![\u4e00-\u9fff])([\u4e00-\u9fff]{2,4})[，,]?\s*"
                    r"(?:闺字|字|又名|别名|小名|乳名|也叫)\s*([\u4e00-\u9fff]{1,4})(?=$|[^\u4e00-\u9fff])")
_FULL_NAME = re.compile(r"(?<![\u4e00-\u9fff])([\u4e00-\u9fff]{2,8})全名([\u4e00-\u9fff]{2,4})"
                        r"(?:[，,]\s*闺?字([\u4e00-\u9fff]{1,4}))?(?=$|[^\u4e00-\u9fff])")
_SINGLE_NAME = re.compile(r"(?:他|她|此人|这人)(?:的名字是|名叫|名为|叫做)([\u4e00-\u9fff]{1,4})(?=$|[^\u4e00-\u9fff])")
_CONTRIBUTION = re.compile(r"救|杀|牺牲|阻止|阻拦|守住|保护|帮助|决定|拒绝|揭露|揭示|导致|改变|答应|交给|递给|公开|发现")


def assess_person_identities(chapters: Iterable[TextSource], archive_names: Iterable[str] = ()) -> list[PersonIdentity]:
    """Separate identity evidence from sample-relative narrative prominence.

Frequency alone never establishes identity. Explicit alias statements bind only
their named sides; shared pronouns, surnames or actions do not merge identities.
"""
    chapters = tuple(chapters)
    mentions = discover_person_mentions(chapters, archive_names)
    names = list(dict.fromkeys(m.name for m in mentions))
    alias_owners: dict[str, set[str]] = defaultdict(set)
    definitions: dict[str, list[PersonMention]] = defaultdict(list)
    definition_spans: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for chapter in chapters:
        for match in _ALIAS.finditer(chapter.content):
            name, alias = match.group(1, 2)
            if plausible_person(name) and plausible_person(alias, explicit=True):
                names.append(name)
                alias_owners[alias].add(name)
                definitions[name].append(PersonMention(name, chapter.chapter_id, match.start(1), "definition"))
                definition_spans[name].append((chapter.chapter_id, match.start(), match.end()))
        for match in _FULL_NAME.finditer(chapter.content):
            label, name, alias = match.group(1, 2, 3)
            if plausible_person(label, explicit=True) and plausible_person(name):
                names.append(name)
                alias_owners[label].add(name)
                if alias and plausible_person(alias, explicit=True):
                    alias_owners[alias].add(name)
                definitions[name].append(PersonMention(name, chapter.chapter_id, match.start(2), "definition"))
                definition_spans[name].append((chapter.chapter_id, match.start(), match.end()))
        for match in _SINGLE_NAME.finditer(chapter.content):
            name = match.group(1)
            if plausible_person(name, explicit=True, lexical_override=_personal_use(name, chapter.content)):
                names.append(name)
                definitions[name].append(PersonMention(name, chapter.chapter_id, match.start(1), "definition"))
                definition_spans[name].append((chapter.chapter_id, match.start(), match.end()))
    aliases = {alias: next(iter(owners)) for alias, owners in alias_owners.items() if len(owners) == 1}
    names = list(dict.fromkeys(aliases.get(name, name) for name in names))
    spelling_to_name = {name: name for name in names}
    spelling_to_name.update({alias: name for alias, name in aliases.items() if name in names})
    if not names:
        return []
    occurrences: dict[str, list[PersonMention]] = defaultdict(list)
    paragraphs: dict[str, set[tuple[str, int]]] = defaultdict(set)
    actions: dict[str, set[tuple[str, int]]] = defaultdict(set)
    contributions: dict[str, set[tuple[str, int]]] = defaultdict(set)
    shared_predicates = {(aliases.get(m.name, m.name), m.chapter_id, m.start): m.predicate
                         for m in mentions if m.predicate}
    pattern = re.compile("|".join(map(re.escape, sorted(spelling_to_name, key=len, reverse=True))))
    for chapter in chapters:
        for paragraph_index, paragraph in enumerate(re.finditer(r"[^\n]+", chapter.content)):
            for match in pattern.finditer(paragraph.group()):
                spelling = match.group()
                name = spelling_to_name[spelling]
                position = paragraph.start() + match.start()
                tail = paragraph.group()[match.end():match.end() + 24]
                if len(spelling) == 1 and match.start() and "\u4e00" <= paragraph.group()[match.start()-1] <= "\u9fff":
                    if not any(m.chapter_id == chapter.chapter_id and m.start == position for m in definitions[name]):
                        continue
                occurrence = PersonMention(name, chapter.chapter_id, position, "source", spelling)
                occurrences[name].append(occurrence)
                paragraphs[name].add((chapter.chapter_id, paragraph_index))
                action = _action_after(tail)
                shared = shared_predicates.get((name, chapter.chapter_id, position), "")
                if shared:
                    action = shared
                if action == "对" and re.match(r"对[\u4e00-\u9fff]{2,4}(?:说|问|喊)", tail):
                    action = "说"
                if action and action not in _WEAK_ACTIONS:
                    actions[name].add((chapter.chapter_id, position))
                    if _CONTRIBUTION.match(_PREDICATE_PREFIX.sub("", tail)):
                        contributions[name].add((chapter.chapter_id, position))
    total_length = sum(len(re.sub(r"\s+", "", c.content)) for c in chapters)
    recurrence_gate = max(2, math.ceil(math.log1p(total_length / 700)))
    dominant_count = max((len(values) for values in occurrences.values()), default=0)
    main_gate = max(4, math.ceil(math.sqrt(total_length / 80)), math.ceil(dominant_count * .2))
    result = []
    for name in names:
        count, paragraph_count = len(occurrences[name]), len(paragraphs[name])
        action_count, contribution_count = len(actions[name]), len(contributions[name])
        declared = bool(definitions[name]) or any(m.name == name and m.origin in {"label", "archive"} for m in mentions)
        significant = (contribution_count > 0
                       or (count >= recurrence_gate and paragraph_count >= recurrence_gate and action_count >= 2)
                       or (count >= main_gate and action_count >= 2)
                       or (total_length <= 1500 and (action_count > 0 or declared
                           or any(m.name == name and m.origin == "object" for m in mentions))))
        importance = "main" if significant and count >= main_gate and action_count >= 2 else "supporting" if significant else "incidental"
        confidence = .95 if definitions[name] else .88 if declared else .8 if action_count else .65
        reason = (f"当前来源{paragraph_count}个段落中出现{count}次，有{action_count}处个人行动及{contribution_count}处作用线索。"
                  + ("短来源仅作局部配角观察。" if total_length <= 1500 else "按来源长度与作用证据判断重要性。")
                  + ("仅提及或作用证据不足，暂不单列人物卡。" if importance == "incidental" else ""))
        result.append(PersonIdentity(name, tuple(a for a, n in aliases.items() if n == name),
                                     tuple(occurrences[name]), count, paragraph_count, action_count,
                                     contribution_count, confidence, importance, reason, tuple(definition_spans[name])))
    return result
