"""阶段 32 的确定性深度作品拆解引擎。

这个模块只接收一个已经冻结的正式正文快照，输出严格的六视角
DeconstructionDepthReport。它不持有作者 store 的锁，也不保存正文
副本；发布方负责在分析前后重新校验 source token。

这里的规则是保守的证据驱动启发式。不能从正文确认的关系、伏笔或人物
身份不会因为章节相邻、词语重复或分析模板而被补出来。
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
from typing import Iterable

from schemas.deconstruction import (
    DeconstructionDepthReport,
    DepthAnalysisItem,
    DepthChapter,
    DepthCharacter,
    DepthCharacterState,
    DepthEndpoint,
    DepthEvent,
    DepthEvidence,
    DepthForeshadowing,
    DepthForeshadowingState,
    DepthPlotline,
    DepthReaderExperience,
    DepthRelation,
    DepthRhythm,
    DepthSource,
    DepthTechnique,
    depth_stable_id,
)


MAX_EVIDENCE_EXCERPT = 180
MAX_NAMES = 80


@dataclass(frozen=True)
class ChapterInput:
    chapter_id: str
    chapter_number: int
    title: str
    content: str


@dataclass(frozen=True)
class DepthSnapshot:
    project_id: str
    document_id: str
    source_version_id: str
    source_revision: int
    source_hash: str
    chapters: tuple[ChapterInput, ...]
    character_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Segment:
    chapter: ChapterInput
    start: int
    end: int
    text: str
    index: int

    @property
    def clean(self) -> str:
        return self.text.strip()


@dataclass
class _EventMeta:
    event_id: str
    chapter: ChapterInput
    segment: _Segment
    start: int
    end: int
    action: str
    names: list[str]
    terms: list[str]
    temporal_mode: str
    story_order: int | None
    narrative_order: int
    consequence: str
    status: str
    negative: bool
    evidence_id: str = ""


def _utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _clip(text: str, limit: int = 480) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:limit]


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _progress_intervals(chapters: tuple[ChapterInput, ...]) -> dict[str, tuple[float, float]]:
    """Return contiguous chapter intervals on a UTF-16 reading axis."""

    total = sum(_utf16_length(chapter.content) for chapter in chapters)
    if total <= 0:
        return {chapter.chapter_id: (0.0, 0.0) for chapter in chapters}
    intervals: dict[str, tuple[float, float]] = {}
    consumed = 0
    for index, chapter in enumerate(chapters):
        start = 0.0 if index == 0 else round(consumed / total * 100.0, 6)
        consumed += _utf16_length(chapter.content)
        end = 100.0 if index == len(chapters) - 1 else round(consumed / total * 100.0, 6)
        intervals[chapter.chapter_id] = (start, end)
    return intervals


def _segments(chapter: ChapterInput) -> list[_Segment]:
    """Split prose while retaining exact code-point boundaries for evidence."""

    result: list[_Segment] = []
    pattern = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
    for index, match in enumerate(pattern.finditer(chapter.content)):
        raw = match.group(0)
        left = len(raw) - len(raw.lstrip())
        right = len(raw.rstrip())
        start = match.start() + left
        end = match.start() + right
        if end <= start:
            continue
        result.append(_Segment(chapter, start, end, chapter.content[start:end], index))
    return result


class _EvidenceBuilder:
    """Create exact UTF-16 evidence without storing a second body copy."""

    def __init__(self, source: DepthSource, chapters: tuple[ChapterInput, ...]) -> None:
        self.source = source
        self.chapters = {chapter.chapter_id: chapter for chapter in chapters}
        self.items: dict[str, DepthEvidence] = {}

    def span(self, chapter: ChapterInput, start: int, end: int, label: str) -> str:
        start = max(0, min(len(chapter.content), start))
        end = max(start, min(len(chapter.content), end))
        if end <= start:
            raise ValueError("evidence span must be nonempty")
        end = min(end, start + MAX_EVIDENCE_EXCERPT)
        excerpt = chapter.content[start:end]
        evidence_id = depth_stable_id(
            self.source, "evidence", f"{chapter.chapter_id}:{start}:{end}:{label}",
        )
        if evidence_id not in self.items:
            self.items[evidence_id] = DepthEvidence(
                project_id=self.source.project_id,
                document_id=self.source.document_id,
                source_version_id=self.source.source_version_id,
                source_revision=self.source.source_revision,
                source_hash=self.source.source_hash,
                evidence_id=evidence_id,
                chapter_id=chapter.chapter_id,
                chapter_number=chapter.chapter_number,
                granularity="span",
                start_offset=_utf16_length(chapter.content[:start]),
                end_offset=_utf16_length(chapter.content[:end]),
                offset_unit="utf16_code_unit",
                excerpt=excerpt,
                label=label[:120] or "正文片段",
            )
        return evidence_id

    def chapter(self, chapter: ChapterInput, label: str) -> str:
        evidence_id = depth_stable_id(
            self.source, "chapter-evidence", f"{chapter.chapter_id}:{label}",
        )
        if evidence_id not in self.items:
            self.items[evidence_id] = DepthEvidence(
                project_id=self.source.project_id,
                document_id=self.source.document_id,
                source_version_id=self.source.source_version_id,
                source_revision=self.source.source_revision,
                source_hash=self.source.source_hash,
                evidence_id=evidence_id,
                chapter_id=chapter.chapter_id,
                chapter_number=chapter.chapter_number,
                granularity="chapter",
                start_offset=None,
                end_offset=None,
                offset_unit="utf16_code_unit",
                excerpt="",
                label=label[:120] or "章节定位",
            )
        return evidence_id


class DepthAnalysisEngine:
    """Build one complete, source-bound depth report from a frozen snapshot."""

    _name_stopwords = {
        "三年前", "与此同时", "因为雨水", "一条长线", "两人一起", "一个人",
        "雨水", "天色", "石阶", "歌声", "钟声", "河岸", "街巷", "旧站",
        "钟楼", "钥匙", "铜钥匙", "脚印", "真相", "地图", "船票", "绳索",
        "书店", "院子", "屋内", "墙壁", "墙", "海", "花", "门后", "天空",
        "雨落", "空庭", "缺角", "姐姐", "妹妹", "哥哥", "母亲", "父亲",
        "信", "路标", "驿站", "然后", "接着", "随后", "终于", "此时", "同时",
        "于是", "因此", "所以", "后来", "现在", "只是", "已经", "正在",
        "忽然", "突然", "先前", "以前", "当时", "两人", "我们", "你们",
        "他们", "她们", "自己",
    }
    _name_context = (
        "想", "要", "在", "把", "将", "用", "拿", "带", "给", "对", "问", "说",
        "看", "听", "站", "走", "来", "去", "找到", "寻找", "害怕", "决定",
        "答应", "赶来", "帮助", "递", "交给", "打开", "推开", "点亮", "继续",
        "沿", "记录", "抛", "拖", "离开", "回家", "解释", "公开", "不再",
        "终于", "发现", "进入", "遇见", "收到", "保护", "守住", "合作",
        "没有", "没", "未", "并未", "拒绝", "拒不", "不肯", "不愿",
    )
    _artifact_suffixes = (
        "钥匙", "地图", "船票", "信", "门", "脚印", "真相", "秘密", "线索",
        "照片", "戒指", "印记", "名单", "日记", "礼物", "约定", "口信",
        "名字", "地址", "路标", "绳索", "钟楼", "旧站",
    )
    _non_story_terms = {
        "蓝色", "红色", "绿色", "白色", "黑色", "金色", "灰色", "颜色",
        "雨水", "天色", "石阶", "歌声", "钟声", "街巷", "天空", "海面",
    }

    def __init__(self, snapshot: DepthSnapshot) -> None:
        if not snapshot.chapters:
            raise ValueError("depth analysis requires chapters")
        self.snapshot = snapshot
        self.source = DepthSource(
            project_id=snapshot.project_id,
            document_id=snapshot.document_id,
            source_version_id=snapshot.source_version_id,
            source_revision=snapshot.source_revision,
            source_hash=snapshot.source_hash,
        )
        self.chapters = tuple(sorted(snapshot.chapters, key=lambda item: item.chapter_number))
        self.intervals = _progress_intervals(self.chapters)
        self.evidence = _EvidenceBuilder(self.source, self.chapters)
        self.names = self._discover_names()
        self.segments_by_chapter = {
            chapter.chapter_id: _segments(chapter)
            for chapter in self.chapters
        }
        self.events: list[_EventMeta] = []
        self.causal_pairs: list[tuple[str, str, str, str]] = []
        self.transfer_pairs: list[tuple[str, str, str]] = []
        self.foreshadow_candidates: list[tuple[str, _EventMeta, _EventMeta, str]] = []

    def _discover_names(self) -> list[str]:
        positions: dict[str, set[tuple[str, int]]] = defaultdict(set)
        explicit: list[str] = []
        clear_two_character_subjects: set[str] = set()
        subject_context = self._name_context
        strong_subject_context = {
            "把", "将", "用", "拿", "带", "给", "找到", "寻找", "决定",
            "答应", "赶来", "帮助", "递", "交给", "打开", "推开", "点亮",
            "继续", "沿", "记录", "抛", "拖", "离开", "回家", "解释",
            "公开", "保护", "守住", "合作", "走", "来", "去", "想",
            "没有", "没", "未", "并未", "拒绝", "拒不", "不肯", "不愿",
        }
        suffix_verbs = (
            "交给", "递给", "帮助", "保护", "找到", "寻找", "遇见", "看见",
            "提到", "等着", "跟着", "带着", "替", "给", "对",
        )
        boundary_after = set("，,。！？!?；;：: \t\n\"“”「」")
        pronoun_or_function_starts = set("我你他她它这那其此每各两一三因所先后")

        def record(value: str, chapter_id: str, position: int) -> None:
            if (
                len(value) < 2
                or value in self._name_stopwords
                or value[0] in pronoun_or_function_starts
            ):
                return
            positions[value].add((chapter_id, position))

        for chapter in self.chapters:
            for name in self.snapshot.character_names:
                if name and name not in self._name_stopwords:
                    explicit.append(name)
            for group in re.findall(r"人物\s*[:：]\s*([^\n。；;]+)", chapter.content):
                for candidate in re.split(r"[、，,；;和与及]\s*", group):
                    value = candidate.strip(" ：:，,、；;")
                    if 1 < len(value) <= 20:
                        explicit.append(value)
            text = chapter.content
            # Scan from a real clause boundary and choose the shortest
            # candidate whose next characters are an action verb.  Choosing
            # shortest-first is important for Chinese prose such as
            # “顾遥把一把钥匙...” where a greedy 2..4 span would absorb
            # “把一” and invent a four-character person.
            for position in range(len(text)):
                if position > 0 and "\u4e00" <= text[position - 1] <= "\u9fff":
                    continue
                for length in (2, 3, 4):
                    value = text[position:position + length]
                    if len(value) != length or not all("\u4e00" <= char <= "\u9fff" for char in value):
                        continue
                    after = text[position + length:]
                    if any(after.startswith(context) for context in subject_context):
                        record(value, chapter.chapter_id, position)
                        if length == 2 and any(
                            after.startswith(context) for context in strong_subject_context
                        ):
                            # A two-character candidate at a real clause
                            # boundary followed by an action context is a
                            # sufficiently strong local subject signal.  Keep
                            # the recurrence gate for longer or ambiguous
                            # spans, which is what filters phrase fragments.
                            clear_two_character_subjects.add(value)
                        break
            for verb in suffix_verbs:
                offset = 0
                while True:
                    found = text.find(verb, offset)
                    if found < 0:
                        break
                    position = found + len(verb)
                    for length in (2, 3, 4):
                        value = text[position:position + length]
                        after = text[position + length:position + length + 1]
                        if (
                            len(value) == length
                            and all("\u4e00" <= char <= "\u9fff" for char in value)
                            and (not after or after in boundary_after)
                        ):
                            record(value, chapter.chapter_id, position)
                            break
                    offset = position
        values = _unique(explicit)
        ranked = sorted(
            positions.items(),
            key=lambda item: (-len(item[1]), min(item[1])),
        )
        for value, occurrence_positions in ranked:
            if value in self._name_stopwords:
                continue
            # Require two distinct source positions for unlabelled natural
            # prose.  This prevents one-off pronoun/object phrases from
            # becoming people while retaining names that recur across clauses
            # or chapters. Explicit archive/人物 candidates bypass this gate.
            if len(occurrence_positions) >= 2 or value in clear_two_character_subjects:
                values.append(value)
        return _unique(values)[:MAX_NAMES]

    _negation_markers = (
        "并没有", "没有", "未曾", "未能", "并未", "从未", "不曾", "并不", "并非",
        "不是", "拒绝", "拒不", "反对", "不肯", "不愿", "不想", "不敢", "不去", "不让", "不许",
        "不准", "不必", "不应", "不该", "不得", "不要", "不再", "无法", "无从",
        "无力", "无须", "不能", "不会", "不太", "没能", "别", "没", "未",
    )
    _negation_pattern = re.compile(
        "|".join(re.escape(item) for item in sorted(_negation_markers, key=len, reverse=True))
    )
    _scope_predicate_pattern = re.compile(
        r"交给|递给|给了|转交|交予|帮助|合作|守住|保护|打开|找到|解释|公开|"
        r"进入|离开|寻找|收到|遇见|拿出|决定|追赶|阻止|阻拦|制止|避免|防止|"
        r"等待|发现|解决|兑现|回答|回应|说明|记录|带走|抛给|拖动|推开|拿起|放回|"
        r"留下|提到|说|答应|回收|揭示|揭开|确认|得到|获得|完成|实现|达成"
    )
    _negative_event_pattern = re.compile(
        r"拒绝|拒不|不肯|不愿|反对|失败|落空|未能|没能|未果|落败|无效"
    )
    _clause_boundaries = "，,；;。！？!?：:\n"
    _predicate_transition_pattern = re.compile(
        r"又|还|也|且|并且|并|然后|后来|随后|接着|但是|但|却|而|不过|反而|"
        r"同时|之后|以后|后|再|就|才|便|于是|因此|所以|从而|导致|使得|让"
    )
    _prevention_pattern = (
        r"阻止|阻拦|制止|避免|防止|阻挡|拦住|拦下|拦截|禁止|不让|不许|不准"
    )
    _completion_pattern = (
        r"找到|打开|解释|公开|兑现|解决|回应|说明|回收|揭示|揭开|确认|得到|"
        r"获得|完成|实现|达成"
    )
    _progress_pattern = (
        r"决定|找到|打开|解释|公开|帮助|合作|进入|离开|赶来|兑现|解决|回应|说明|"
        r"回收|揭示|揭开|确认|得到|获得|完成|实现|达成"
    )
    _reader_payoff_pattern = (
        r"找到|打开|解决|回应|说明|帮助|合作|完成|实现|达成|确认|得到|获得"
    )

    @classmethod
    def _is_negated_at(cls, text: str, start: int) -> bool:
        """Return whether a predicate is locally negated in its clause.

        The nearest clause boundary and predicate are used as a small scope,
        so a negated predicate does not poison a later positive action in the
        same sentence (for example ``没有找到，后来打开``).  Double negation
        without an intervening predicate is treated as positive.
        """

        boundary = max((text.rfind(mark, 0, start) for mark in cls._clause_boundaries), default=-1)
        prefix = text[boundary + 1:start]
        negation_positions = [match.start() for match in cls._negation_pattern.finditer(prefix)]
        # Bare 不 is only a negator when it is immediately adjacent to the
        # predicate.  This avoids treating lexical words such as 不久、不但、
        # 无意间 and 无论 as clause-level negation.
        if prefix.endswith("不"):
            negation_positions.append(len(prefix) - 1)
        if not negation_positions:
            return False
        predicates = list(cls._scope_predicate_pattern.finditer(prefix))
        last_negation = max(negation_positions)
        if predicates and predicates[-1].start() > last_negation:
            # A predicate after the negation can start a new action, but a
            # following noun is often just its object.  For example, in
            # “没有找到答案”, 找到 is the negated predicate and 答案 must
            # remain inside that scope.  Only an explicit conjunction or
            # temporal transition ends the preceding predicate's scope.
            previous = predicates[-1]
            previous_start = boundary + 1 + previous.start()
            if cls._is_negated_at(text, previous_start) and not cls._predicate_transition_pattern.search(
                prefix[previous.end():]
            ):
                return True
            return False
        if not predicates and len(negation_positions) % 2 == 0:
            return False
        return True

    @classmethod
    def _has_positive(cls, text: str, pattern: str) -> bool:
        """Match a marker only when its local predicate is affirmative."""

        return any(
            not cls._is_negated_at(text, match.start())
            for match in re.finditer(pattern, text)
        )

    @classmethod
    def _has_negated(cls, text: str, pattern: str) -> bool:
        return any(
            cls._is_negated_at(text, match.start())
            for match in re.finditer(pattern, text)
        )

    @classmethod
    def _has_refusal(cls, text: str) -> bool:
        return any(
            not cls._is_negated_at(text, match.start())
            for match in re.finditer(cls._negative_event_pattern, text)
        )

    @classmethod
    def _has_prevention(cls, text: str) -> bool:
        """Return whether a positive blocking action controls a later verb."""

        return cls._has_positive(text, cls._prevention_pattern)

    @classmethod
    def _is_prevented_at(cls, text: str, start: int) -> bool:
        """Return whether a positive prevention verb scopes the marker at ``start``."""

        boundary = max((text.rfind(mark, 0, start) for mark in cls._clause_boundaries), default=-1)
        prefix = text[boundary + 1:start]
        preventions = [
            match for match in re.finditer(cls._prevention_pattern, prefix)
            if not cls._is_negated_at(text, boundary + 1 + match.start())
        ]
        if not preventions:
            return False
        last_prevention = preventions[-1]
        # “阻止打开门，后来打开门” has an independent later action.  Without
        # a transition, the verb belongs to the blocked action's local scope.
        return not cls._predicate_transition_pattern.search(prefix[last_prevention.end():])

    @classmethod
    def _has_effective_positive(cls, text: str, pattern: str) -> bool:
        return any(
            not cls._is_negated_at(text, match.start())
            and not cls._is_prevented_at(text, match.start())
            for match in re.finditer(pattern, text)
        )

    @classmethod
    def _has_completion(cls, text: str) -> bool:
        """Return whether an affirmative, unblocked completion action is present."""

        return cls._has_effective_positive(text, cls._completion_pattern)

    @classmethod
    def _has_reader_payoff(cls, text: str) -> bool:
        return cls._has_effective_positive(text, cls._reader_payoff_pattern)

    @classmethod
    def _event_is_negative(cls, text: str) -> bool:
        """Detect failed, refused, or explicitly negated action predicates."""

        return (
            cls._has_prevention(text)
            or cls._has_refusal(text)
            or cls._has_negated(text, cls._scope_predicate_pattern.pattern)
        )

    def _chapter_progress(self, chapter: ChapterInput) -> tuple[float, float]:
        return self.intervals[chapter.chapter_id]

    def _event_progress(self, event: _EventMeta) -> tuple[float, float]:
        start, end = self._chapter_progress(event.chapter)
        length = max(1, _utf16_length(event.chapter.content))
        local_start = _utf16_length(event.chapter.content[:event.start])
        local_end = _utf16_length(event.chapter.content[:event.end])
        return (
            round(start + (end - start) * local_start / length, 6),
            round(start + (end - start) * local_end / length, 6),
        )

    def _event_mode(self, text: str) -> tuple[str, int | None, list[str]]:
        if self._has_positive(text, r"三年前|多年前|从前|过去|曾经|回忆|记得|那年|当时"):
            return "flashback", None, ["正文标记了回溯时间，但未提供完整全局故事顺序。"]
        if self._has_positive(text, r"与此同时|同时|此时|另一边|并行|一旁"):
            return "parallel", None, ["正文显示并行发生，但两条行动线的全部先后关系未知。"]
        if self._has_positive(text, r"将来|未来|后来会|以后"):
            return "flashforward", None, ["正文提及未来时间，具体故事顺序仍需更多上下文。"]
        return "linear", 0, []

    def _extract_terms(self, text: str) -> list[str]:
        values: list[str] = []
        for match in re.finditer(
            r"(?:一|这|那|另)[把张封枚件条面]([\u4e00-\u9fff]{1,14})",
            text,
        ):
            phrase = re.split(r"(?:交给|递给|拿给|放在|放进|打开|带着|用来|说)", match.group(1))[0]
            phrase = phrase.strip("，。！？；：:、 ")
            if phrase:
                values.append(phrase)
        for suffix in self._artifact_suffixes:
            for match in re.finditer(rf"[\u4e00-\u9fff]{{0,10}}{re.escape(suffix)}", text):
                phrase = match.group(0)
                if phrase in self._non_story_terms:
                    continue
                values.append(phrase)
                values.append(suffix)
        for match in re.finditer(
            r"(?:寻找|找到|解释|公开|守住|打开|记录|沿着|追赶|等待)([\u4e00-\u9fff]{1,10})",
            text,
        ):
            value = match.group(1).strip("，。！？；：:、 ")
            if value and value not in self._non_story_terms:
                values.append(value)
        return [
            value
            for value in _unique(values)
            if value not in self._non_story_terms and len(value) >= 1
        ]

    def _event_clauses(self, segment: _Segment) -> list[tuple[int, int, str]]:
        text = segment.clean
        if not text:
            return []
        # A causal connective at the beginning normally has the form
        # “因为 A，B”; split at that comma so A and B can receive separate
        # event nodes and a supported causal edge.
        if re.match(r"^(因为|由于)", text):
            comma = re.search(r"[，,]", text)
            if comma is not None and comma.start() > 1 and comma.end() < len(text):
                left = text[:comma.start()].strip()
                right = text[comma.end():].strip()
                left_start = text.find(left)
                right_start = text.find(right, comma.end())
                return [
                    (segment.start + left_start, segment.start + left_start + len(left), left),
                    (segment.start + right_start, segment.start + right_start + len(right), right),
                ]
        for connector in ("所以", "因此", "于是", "从而", "导致", "使得", "让"):
            match = re.search(connector, text)
            if match is None or match.start() <= 1 or match.start() >= len(text) - 2:
                continue
            if connector == "让" and self._is_negated_at(text, match.start()):
                # “不让顾遥打开门” is one blocked action, not a split at
                # the character 让.
                continue
            left = text[:match.start()].strip("，, ")
            right = text[match.end():].strip("，, ")
            if left and right:
                left_start = text.find(left)
                right_start = text.find(right, match.end())
                return [
                    (segment.start + left_start, segment.start + left_start + len(left), left),
                    (segment.start + right_start, segment.start + right_start + len(right), right),
                ]
        return [(segment.start, segment.end, text)]

    def _event_status(self, text: str) -> str:
        # Completion is established by an affirmative action/state.  Nouns
        # such as “答案” and adverbs such as “终于” are not enough on their
        # own: in “没有找到答案” the object follows a negated predicate and
        # must not turn the event into a resolved one.
        if self._has_completion(text):
            return "resolved"
        if self._has_prevention(text):
            return "turning"
        if self._event_is_negative(text):
            if self._has_refusal(text) or self._has_positive(text, r"失败|落空|未能|没能|未果|落败|无效"):
                return "turning"
            return "open"
        if self._has_positive(text, r"决定|却|但是|然而|危险|危机|对抗|追赶|阻止"):
            return "turning"
        if self._has_positive(text, r"想|寻找|收到|遇见|进入|拿出|交给|递给"):
            return "introduced"
        return "developing"

    def _event_consequence(self, text: str) -> str:
        if self._has_effective_positive(text, self._progress_pattern):
            return "正文明确展示了该行动带来的下一步推进。"
        if self._has_prevention(text):
            return "正文明确写出相关动作被阻止、避免或未完成，后果方向仍需结合上下文确认。"
        if self._event_is_negative(text):
            return "正文明确写出相关动作未发生或未完成，后果方向仍需结合上下文确认。"
        return "当前片段没有明确交代后果，后续影响仍需更多正文确认。"

    def _build_events(self) -> None:
        narrative_order = 0
        story_order = 0
        for chapter in self.chapters:
            for segment in self.segments_by_chapter[chapter.chapter_id]:
                clauses = self._event_clauses(segment)
                clause_ids: list[str] = []
                for start, end, raw in clauses:
                    action = _clip(raw, 1100)
                    if not action:
                        continue
                    temporal_mode, _, mode_uncertainty = self._event_mode(raw)
                    event_id = depth_stable_id(
                        self.source,
                        "event",
                        f"{chapter.chapter_id}:{start}:{end}",
                    )
                    evidence_id = self.evidence.span(chapter, start, end, "事件片段")
                    names = [name for name in self.names if name in raw]
                    terms = self._extract_terms(raw)
                    negative = self._event_is_negative(raw)
                    if temporal_mode == "linear":
                        current_story_order: int | None = story_order
                        story_order += 1
                    else:
                        current_story_order = None
                    event = _EventMeta(
                        event_id=event_id,
                        chapter=chapter,
                        segment=segment,
                        start=start,
                        end=end,
                        action=action,
                        names=names,
                        terms=terms,
                        temporal_mode=temporal_mode,
                        story_order=current_story_order,
                        narrative_order=narrative_order,
                        consequence=self._event_consequence(raw),
                        status=self._event_status(raw),
                        negative=negative,
                        evidence_id=evidence_id,
                    )
                    self.events.append(event)
                    clause_ids.append(event_id)
                    narrative_order += 1
                # The split itself is evidence of causation only for an
                # explicit causal connective; a normal sentence remains one
                # event and does not acquire a causal edge by adjacency.
                if len(clause_ids) >= 2 and re.search(
                    r"^(因为|由于)|所以|因此|于是|从而|导致|使得|让",
                    segment.clean,
                ):
                    events_by_id = {event.event_id: event for event in self.events}
                    left_event = events_by_id[clause_ids[0]]
                    right_event = events_by_id[clause_ids[1]]
                    if left_event.negative and right_event.negative:
                        causal_explanation = (
                            "正文使用明确因果连接词关联两个事件；前后两侧动作均被否定或未完成，"
                            "这里只保留负向因果，不推断正向推进。"
                        )
                    elif left_event.negative:
                        causal_explanation = (
                            "正文使用明确因果连接词关联两个事件；前一侧动作被否定或未完成，"
                            "这里只保留负向因果，后一侧仍按正文呈现，不把两侧都改写为负向状态。"
                        )
                    else:
                        causal_explanation = (
                            "正文使用明确因果连接词关联两个事件；后一侧动作被否定或未完成，"
                            "这里只保留负向因果，不推断正向回收。"
                        )
                    self.causal_pairs.append(
                        (
                            clause_ids[0],
                            clause_ids[1],
                            "causes",
                            causal_explanation
                            if left_event.negative or right_event.negative
                            else "正文使用了明确的因果连接词。",
                        )
                    )

        # A concrete object transfer followed by a later use can establish an
        # enabling relation. Shared names or neighboring chapters are not
        # enough; both events must mention the same non-visual term.
        for index, earlier in enumerate(self.events):
            if earlier.negative or not self._has_positive(earlier.action, r"交给|递给|给了|转交|交予"):
                continue
            earlier_terms = set(earlier.terms)
            if not earlier_terms:
                continue
            for later in self.events[index + 1:]:
                shared = [
                    term for term in later.terms
                    if term in earlier_terms and term not in self._non_story_terms
                ]
                if (
                    not later.negative
                    and shared
                    and self._has_positive(later.action, r"用|打开|找到|解释|拿|带")
                ):
                    self.transfer_pairs.append(
                        (earlier.event_id, later.event_id, shared[0])
                    )
                    break

    def _item_progress(
        self,
        chapter_ids: list[str],
        *,
        start: float | None = None,
        end: float | None = None,
    ) -> tuple[float, float]:
        ordered = [self.intervals[chapter_id] for chapter_id in chapter_ids]
        return (
            min(interval[0] for interval in ordered) if start is None else start,
            max(interval[1] for interval in ordered) if end is None else end,
        )

    def _common(
        self,
        *,
        item_id: str,
        kind: str,
        category: str,
        conclusion: str,
        epistemic_status: str,
        chapter_ids: list[str],
        evidence_ids: list[str],
        confidence: float,
        uncertainty: list[str],
        start: float | None = None,
        end: float | None = None,
    ) -> dict[str, object]:
        progress_start, progress_end = self._item_progress(
            chapter_ids, start=start, end=end,
        )
        if epistemic_status == "unknown":
            confidence = 0.0
            uncertainty = uncertainty or ["当前正文没有提供足够的直接证据。"]
            evidence_ids = []
        elif epistemic_status == "inferred" and not uncertainty:
            uncertainty = ["这是基于正文证据的推断，不能替代作者确认。"]
        return {
            "item_id": item_id,
            "kind": kind,
            "category": category,
            "conclusion": conclusion[:1200] or "当前正文未提供可用结论。",
            "epistemic_status": epistemic_status,
            "chapter_ids": _unique(chapter_ids),
            "normalized_start": float(progress_start),
            "normalized_end": float(progress_end),
            "evidence_ids": _unique(evidence_ids),
            "related_item_ids": [],
            "confidence": float(max(0.0, min(1.0, confidence))),
            "uncertainty": [item[:1200] for item in _unique(uncertainty)[:16]],
        }

    def _character_view(self) -> tuple[list[DepthCharacter], list[DepthCharacterState], list[DepthRelation], str, list[str]]:
        characters: list[DepthCharacter] = []
        states: list[DepthCharacterState] = []
        relations: list[DepthRelation] = []
        if not self.names:
            return (
                characters,
                states,
                relations,
                "当前正文未提供可可靠识别的人物候选。",
                ["当前正文没有足够的人物称谓或行动主体证据。"],
            )

        character_ids = {
            name: depth_stable_id(self.source, "character", f"name:{name}")
            for name in self.names
        }
        for name in self.names:
            related_events = [event for event in self.events if name in event.names]
            chapter_ids = _unique([event.chapter.chapter_id for event in related_events])
            if not chapter_ids:
                continue
            evidence_ids: list[str] = []
            for chapter_id in chapter_ids:
                chapter = next(item for item in self.chapters if item.chapter_id == chapter_id)
                position = chapter.content.find(name)
                if position >= 0:
                    evidence_ids.append(
                        self.evidence.span(chapter, position, position + len(name), "人物称谓")
                    )
            first_action = related_events[0].action if related_events else ""
            motivation = (
                f"正文显示{name}在行动上关注{_clip(first_action, 80)}。"
                if first_action
                else f"正文尚未明确{name}的长期动机。"
            )
            inner_conflict = (
                f"正文在{name}相关片段中出现了犹豫、害怕或转变信号。"
                if any(self._has_positive(event.action, r"害怕|犹豫|却|但是|不再") for event in related_events)
                else f"当前片段没有充分揭示{name}的内在冲突。"
            )
            role = (
                f"{name}是正文中反复出现的行动参与者。"
                if len(related_events) > 1 and any(not event.negative for event in related_events)
                else (
                    f"{name}在当前正文中以拒绝、未完成或待确认状态相关者身份出现。"
                    if all(event.negative for event in related_events)
                    else f"{name}在当前正文中以行动参与者身份出现。"
                )
            )
            common = self._common(
                item_id=character_ids[name],
                kind="character",
                category="人物候选",
                conclusion=(
                    f"正文直接呈现{name}参与了至少一项行动，具体主导地位仍需更长文本确认。"
                    if any(not event.negative for event in related_events)
                    else f"正文直接呈现{name}涉及一项拒绝、未发生或未完成状态，具体主导地位仍需更长文本确认。"
                ),
                epistemic_status="inferred",
                chapter_ids=chapter_ids,
                evidence_ids=evidence_ids,
                confidence=0.78,
                uncertainty=["人物角色和长期弧线依据当前正文推断，不能替代作者设定。"],
            )
            characters.append(
                DepthCharacter.model_validate({
                    **common,
                    "name": name,
                    "aliases": [],
                    "role": role,
                    "motivation": motivation,
                    "inner_conflict": inner_conflict,
                    "arc_summary": (
                        f"从第{chapter_ids[0]}相关片段到末次出现，"
                        f"可观察到{name}持续参与正文推进；完整人物弧尚未完全展开。"
                    ),
                })
            )

            grouped: list[tuple[str, list[_EventMeta]]] = []
            for chapter_id in chapter_ids:
                grouped.append((
                    chapter_id,
                    [event for event in related_events if event.chapter.chapter_id == chapter_id],
                ))
            for state_index, (chapter_id, chapter_events) in enumerate(grouped):
                chapter = next(item for item in self.chapters if item.chapter_id == chapter_id)
                chapter_evidence = [
                    event.evidence_id for event in chapter_events[:4] if event.evidence_id
                ]
                if not chapter_evidence:
                    position = chapter.content.find(name)
                    if position >= 0:
                        chapter_evidence = [
                            self.evidence.span(chapter, position, position + len(name), "人物状态")
                        ]
                state_id = depth_stable_id(
                    self.source, "character-state", f"{name}:{chapter_id}",
                )
                event_ids = [event.event_id for event in chapter_events[:100]]
                action = _clip(chapter_events[0].action, 110) if chapter_events else "正文没有明确行动。"
                emotion = (
                    "片段中出现担忧、犹豫或情绪变化。"
                    if self._has_positive(chapter.content, r"害怕|犹豫|紧张|愤怒|悲伤|不再")
                    else "当前片段未明确标注情绪状态。"
                )
                change = (
                    "这是当前可见的起始状态，前史变化暂未知。"
                    if state_index == 0
                    else "相较前一状态，正文出现了新的行动或关系推进。"
                )
                state_common = self._common(
                    item_id=state_id,
                    kind="character_state",
                    category="人物状态",
                    conclusion=f"第{chapter.chapter_number}章显示{name}的阶段状态与行动：{action}。",
                    epistemic_status="inferred",
                    chapter_ids=[chapter_id],
                    evidence_ids=chapter_evidence,
                    confidence=0.68,
                    uncertainty=["状态变化依据局部章节推断，未覆盖正文之外的动机。"],
                )
                states.append(
                    DepthCharacterState.model_validate({
                        **state_common,
                        "character_id": character_ids[name],
                        "goal": f"当前阶段的可见目标是继续处理：{action}。",
                        "belief": "正文没有完整说明其信念；这里只记录当前行动所支持的有限推断。",
                        "emotion": emotion,
                        "agency": "该人物在片段中有可观察的行动或回应。" if chapter_events else "行动能动性未知。",
                        "change": change,
                        "trigger_event_ids": event_ids,
                    })
                )

        # Only make a social relation when both names co-occur with a
        # cooperation/opposition cue in one bounded source segment.
        seen_relations: set[tuple[str, str, str]] = set()
        for event in self.events:
            if len(event.names) < 2:
                continue
            relation_type: str | None = None
            # A positive relationship requires the whole bounded event to be
            # affirmative.  Otherwise “拒绝把钥匙交给” could still match
            # the inner transfer word and create an allies edge.
            if event.negative:
                if self._has_positive(event.action, r"对抗|阻止|阻拦|制止|避免|防止|争吵|敌对|不信|冲突") or self._has_refusal(event.action):
                    relation_type = "opposes"
            elif self._has_positive(event.action, r"合作|帮助|守住|赶来|一起|保护|答应|交给|递给"):
                relation_type = "allies"
            if relation_type is None:
                continue
            for left_index, left in enumerate(event.names):
                for right in event.names[left_index + 1:]:
                    key = tuple(sorted((left, right))) + (relation_type,)
                    if key in seen_relations:
                        continue
                    seen_relations.add(key)
                    left_id, right_id = character_ids[left], character_ids[right]
                    relation_id = depth_stable_id(
                        self.source, "relation", f"character:{left}:{right}:{relation_type}",
                    )
                    start, end = self._event_progress(event)
                    relation_common = self._common(
                        item_id=relation_id,
                        kind="relation",
                        category="人物关系",
                        conclusion=(
                            f"{left}与{right}在同一片段中呈现出"
                            f"{'合作或相互支持' if relation_type == 'allies' else '对立或阻碍'}。"
                        ),
                        epistemic_status="observed",
                        chapter_ids=[event.chapter.chapter_id],
                        evidence_ids=[event.evidence_id],
                        confidence=0.82,
                        uncertainty=[],
                        start=start,
                        end=end,
                    )
                    relations.append(
                        DepthRelation.model_validate({
                            **relation_common,
                            "start": DepthEndpoint(item_id=left_id, kind="character"),
                            "end": DepthEndpoint(item_id=right_id, kind="character"),
                            "relation_type": relation_type,
                            "explanation": "关系类型来自同一正文片段中的明确行动或态度词。",
                        })
                    )
        if characters:
            summary = f"正文中识别到{len(characters)}个有行动证据的人物候选，并按章节建立状态快照。"
            uncertainty = [] if states else ["人物称谓存在，但没有足够行动片段建立状态。"]
        else:
            summary = "当前正文没有足够的人物行动证据。"
            uncertainty = ["当前正文未提供可可靠识别的人物候选。"]
        return characters, states, relations, summary, uncertainty

    def _plot_view(self) -> tuple[list[DepthPlotline], list[DepthEvent], list[DepthRelation], str, list[str]]:
        if not self.events:
            return (
                [],
                [],
                [],
                "当前正文没有可分割的事件片段。",
                ["当前正文未提供可可靠识别的剧情事件。"],
            )
        plotline_id = depth_stable_id(self.source, "plotline", "main-event-progression")
        event_models: list[DepthEvent] = []
        event_by_id: dict[str, DepthEvent] = {}
        event_meta_by_id = {event.event_id: event for event in self.events}
        for index, event in enumerate(self.events):
            start, end = self._event_progress(event)
            mode_uncertainty: list[str] = []
            if event.temporal_mode == "flashback":
                mode_uncertainty.append("回溯片段的世界时间早于当前叙述位置，但全局顺序未知。")
            elif event.temporal_mode == "parallel":
                mode_uncertainty.append("并行片段只确认同时发生，不推断两条线的因果。")
            elif event.temporal_mode == "flashforward":
                mode_uncertainty.append("未来片段的具体世界时间仍不确定。")
            effective_progress = self._has_effective_positive(event.action, self._progress_pattern)
            event_conclusion = (
                f"第{event.chapter.chapter_number}章同时呈现了未完成或受阻尝试，以及后续肯定行动：{event.action}。"
                if event.negative and effective_progress
                else (
                    f"第{event.chapter.chapter_number}章呈现了一个明确的未发生、未完成或拒绝状态：{event.action}。"
                    if event.negative
                    else f"第{event.chapter.chapter_number}章呈现了一个可观察行动：{event.action}。"
                )
            )
            common = self._common(
                item_id=event.event_id,
                kind="event",
                category="正文事件",
                conclusion=event_conclusion,
                epistemic_status="observed",
                chapter_ids=[event.chapter.chapter_id],
                evidence_ids=[event.evidence_id],
                confidence=0.8,
                uncertainty=mode_uncertainty,
                start=start,
                end=end,
            )
            model = DepthEvent.model_validate({
                **common,
                "plotline_ids": [plotline_id],
                "character_ids": [
                    depth_stable_id(self.source, "character", f"name:{name}")
                    for name in event.names
                    if name in self.names
                ],
                "story_order": event.story_order,
                "narrative_order": event.narrative_order,
                "temporal_mode": event.temporal_mode,
                "action": event.action,
                "consequence": event.consequence,
                "plotline_status": event.status,
            })
            event_models.append(model)
            event_by_id[event.event_id] = model

        plot_chapter_ids = _unique([event.chapter.chapter_id for event in self.events])
        plot_evidence_ids = _unique([event.evidence_id for event in self.events[:8]])
        plot_start, plot_end = self._item_progress(plot_chapter_ids)
        plot_common = self._common(
            item_id=plotline_id,
            kind="plotline",
            category="剧情线",
            conclusion="正文事件围绕行动、信息和后果逐步展开；具体主线权重仍需更长篇幅确认。",
            epistemic_status="inferred",
            chapter_ids=plot_chapter_ids,
            evidence_ids=plot_evidence_ids,
            confidence=0.62,
            uncertainty=["剧情线是基于当前正文事件归并的结构观察，不等同于作者完整大纲。"],
            start=plot_start,
            end=plot_end,
        )
        plotline = DepthPlotline.model_validate({
            **plot_common,
            "title": "正文事件推进线",
            "central_question": "当前行动会如何改变人物处境或信息状态？",
            "stakes": "事件后果和未解决问题构成的风险仍在正文中展开。",
            "resolution": (
                "正文已经出现阶段性解决或信息回收。"
                if any(event.status == "resolved" for event in self.events)
                else "当前正文尚未提供足够证据确认剧情线的最终解决。"
            ),
            "character_ids": _unique([
                depth_stable_id(self.source, "character", f"name:{name}")
                for event in self.events
                for name in event.names
                if name in self.names
            ]),
        })

        relations: list[DepthRelation] = []
        relation_keys: set[tuple[str, str, str]] = set()

        def add_event_relation(
            left_id: str,
            right_id: str,
            relation_type: str,
            explanation: str,
            category: str,
            conclusion: str,
        ) -> None:
            if left_id == right_id or left_id not in event_by_id or right_id not in event_by_id:
                return
            key = (left_id, right_id, relation_type)
            if key in relation_keys:
                return
            relation_keys.add(key)
            left = event_by_id[left_id]
            right = event_by_id[right_id]
            negative_cause = (
                relation_type == "causes"
                and (
                    event_meta_by_id[left_id].negative
                    or event_meta_by_id[right_id].negative
                )
            )
            if negative_cause:
                left_negative = event_meta_by_id[left_id].negative
                right_negative = event_meta_by_id[right_id].negative
                if left_negative and right_negative:
                    conclusion = "正文明确的因果连接表明前一状态和后一状态均未发生或未完成。"
                elif left_negative:
                    conclusion = "正文明确的因果连接表明前一状态未发生或未完成，后一事件仍按正文呈现。"
                else:
                    conclusion = "正文明确的因果连接表明前一事件已被呈现，但后一状态未发生或未完成。"
            chapter_ids = _unique([*left.chapter_ids, *right.chapter_ids])
            evidence_ids = _unique([*left.evidence_ids, *right.evidence_ids])
            start = min(left.normalized_start, right.normalized_start)
            end = max(left.normalized_end, right.normalized_end)
            common = self._common(
                item_id=depth_stable_id(
                    self.source,
                    "relation",
                    f"event:{left_id}:{right_id}:{relation_type}",
                ),
                kind="relation",
                category=category,
                conclusion=conclusion,
                epistemic_status="inferred" if relation_type != "precedes" else "observed",
                chapter_ids=chapter_ids,
                evidence_ids=evidence_ids,
                confidence=0.72 if negative_cause else 0.78 if relation_type in {"causes", "enables"} else 0.86,
                uncertainty=(
                    [
                        (
                            "这里只保留正文明确的负向因果，不据此推断正向推进或完成。"
                            if negative_cause
                            else "因果关系只依据明确连接词或同一具体物件的行动链推断。"
                        )
                    ]
                    if relation_type in {"causes", "enables"}
                    else []
                ),
                start=start,
                end=end,
            )
            relations.append(
                DepthRelation.model_validate({
                    **common,
                    "start": DepthEndpoint(item_id=left_id, kind="event"),
                    "end": DepthEndpoint(item_id=right_id, kind="event"),
                    "relation_type": relation_type,
                    "explanation": explanation,
                })
            )

        for earlier, later in zip(event_models, event_models[1:]):
            add_event_relation(
                earlier.item_id,
                later.item_id,
                "precedes",
                "两项事件在正文中的叙述顺序相邻；这不等同于因果关系。",
                "叙述顺序",
                "前一事件在正文呈现上先于后一事件。",
            )
        for left_id, right_id, _, explanation in self.causal_pairs:
            add_event_relation(
                left_id,
                right_id,
                "causes",
                explanation,
                "事件因果",
                "正文的明确因果连接支持前一事件导致后一行动或后果。",
            )
        for left_id, right_id, term in self.transfer_pairs:
            add_event_relation(
                left_id,
                right_id,
                "enables",
                f"同一具体对象“{term}”先被交付或保留，后在行动中被使用，因此只推断为行动条件。",
                "行动条件",
                f"前一事件提供的具体对象“{term}”支撑了后一事件的行动。",
            )
        for index, event in enumerate(self.events):
            if event.temporal_mode != "parallel":
                continue
            previous = next(
                (candidate for candidate in reversed(self.events[:index])
                 if candidate.chapter.chapter_id == event.chapter.chapter_id),
                None,
            )
            if previous is not None:
                add_event_relation(
                    previous.event_id,
                    event.event_id,
                    "parallel_to",
                    "正文使用并行时间标记，关系只表示同时展开。",
                    "并行叙事",
                    "两项事件在正文中被标记为并行呈现。",
                )

        return (
            [plotline],
            event_models,
            relations,
            f"正文中识别到{len(event_models)}个按叙述顺序排列的事件节点。",
            [],
        )

    def _foreshadowing_view(
        self,
        event_models: list[DepthEvent],
    ) -> tuple[list[DepthForeshadowing], list[DepthForeshadowingState], list[DepthRelation], str, list[str]]:
        if not self.events:
            return (
                [],
                [],
                [],
                "当前正文没有可用于识别铺垫和回收的事件链。",
                ["当前正文未提供可可靠识别的伏笔证据。"],
            )
        event_model_by_id = {event.item_id: event for event in event_models}
        candidates: list[tuple[str, _EventMeta, _EventMeta]] = []
        term_events: dict[str, list[_EventMeta]] = defaultdict(list)
        for event in self.events:
            for term in event.terms:
                if term not in self._non_story_terms:
                    term_events[term].append(event)
        selected_pairs: list[tuple[str, _EventMeta, _EventMeta]] = []
        for term in sorted(term_events, key=lambda value: (-len(value), value)):
            events = _unique([event.event_id for event in term_events[term]])
            ordered = [next(item for item in self.events if item.event_id == event_id) for event_id in events]
            if len(ordered) < 2 or len(term) < 2:
                continue
            first = ordered[0]
            later = next((item for item in ordered[1:] if item.narrative_order > first.narrative_order), None)
            if later is None:
                continue
            if first.negative or later.negative:
                continue
            if not self._has_positive(first.action, r"交给|递给|提到|说|留下|记|疑问|缺|秘密|线索|约定"):
                continue
            if not self._has_effective_positive(
                later.action,
                r"打开|用|解释|找到|公开|兑现|回收|解决|回应|说明|揭示|揭开|确认|得到|"
                r"获得|完成|实现|达成|拿|带",
            ):
                continue
            # Avoid emitting separate threads for a phrase and its head noun
            # when both describe the exact same source chain.
            if any(
                (term in existing_term or existing_term in term)
                and first.event_id == old_first.event_id
                and later.event_id == old_later.event_id
                for existing_term, old_first, old_later in selected_pairs
            ):
                continue
            selected_pairs.append((term, first, later))
        candidates = selected_pairs[:80]
        if not candidates:
            return (
                [],
                [],
                [],
                "当前正文没有足够证据确认铺垫与回收关系。",
                ["当前正文未提供可可靠识别的伏笔证据，重复出现的视觉词不会单独构成伏笔。"],
            )

        threads: list[DepthForeshadowing] = []
        states: list[DepthForeshadowingState] = []
        relations: list[DepthRelation] = []
        for term, first, later in candidates:
            thread_id = depth_stable_id(self.source, "foreshadowing", f"term:{term}")
            first_model = event_model_by_id[first.event_id]
            later_model = event_model_by_id[later.event_id]
            chapter_ids = _unique([first.chapter.chapter_id, later.chapter.chapter_id])
            evidence_ids = _unique([first.evidence_id, later.evidence_id])
            start = min(first_model.normalized_start, later_model.normalized_start)
            end = max(first_model.normalized_end, later_model.normalized_end)
            common = self._common(
                item_id=thread_id,
                kind="foreshadowing",
                category="铺垫线索",
                conclusion=f"正文先呈现具体对象或信息“{term}”，后续片段对其用途或含义作出回应。",
                epistemic_status="inferred",
                chapter_ids=chapter_ids,
                evidence_ids=evidence_ids,
                confidence=0.82,
                uncertainty=["这是基于前后两个具体行动片段的伏笔推断，其他含义仍可能存在。"],
                start=start,
                end=end,
            )
            threads.append(
                DepthForeshadowing.model_validate({
                    **common,
                    "label": f"{term}的前后回应",
                    "planted_detail": f"前段正文明确呈现了与“{term}”有关的交付、提及或疑问。",
                    "expected_payoff": f"后段正文把“{term}”连接到新的行动、解释或答案。",
                    "interpretation": "前后片段共享具体对象和行动链，因此比单纯词语重复更支持伏笔判断。",
                })
            )
            planted_common = self._common(
                item_id=depth_stable_id(self.source, "foreshadowing-state", f"{term}:planted"),
                kind="foreshadowing_state",
                category="伏笔状态",
                conclusion=f"“{term}”在前段被种下或被提出。",
                epistemic_status="observed",
                chapter_ids=[first.chapter.chapter_id],
                evidence_ids=[first.evidence_id],
                confidence=0.83,
                uncertainty=[],
                start=first_model.normalized_start,
                end=first_model.normalized_end,
            )
            states.append(
                DepthForeshadowingState.model_validate({
                    **planted_common,
                    "foreshadowing_id": thread_id,
                    "status": "planted",
                    "payoff": "后续回应尚未在该状态节点发生。",
                    "event_ids": [first.event_id],
                })
            )
            payoff_common = self._common(
                item_id=depth_stable_id(self.source, "foreshadowing-state", f"{term}:paid-off"),
                kind="foreshadowing_state",
                category="伏笔状态",
                conclusion=f"后段正文回应了“{term}”的用途、含义或此前疑问。",
                epistemic_status="inferred",
                chapter_ids=[later.chapter.chapter_id],
                evidence_ids=[later.evidence_id],
                confidence=0.84,
                uncertainty=["回收判断依赖后段的具体行动或解释，完整主题意义仍未必确定。"],
                start=later_model.normalized_start,
                end=later_model.normalized_end,
            )
            states.append(
                DepthForeshadowingState.model_validate({
                    **payoff_common,
                    "foreshadowing_id": thread_id,
                    "status": "paid_off",
                    "payoff": f"正文后段通过“{later.action}”回应了前段线索。",
                    "event_ids": [later.event_id],
                })
            )

            for event_model, relation_type, explanation, label in (
                (
                    first_model,
                    "plants",
                    "前段事件直接呈现了该具体对象或信息，形成线索起点。",
                    "铺垫关系",
                ),
                (
                    later_model,
                    "pays_off",
                    "后段事件对前段具体对象或信息作出行动性回应。",
                    "回收关系",
                ),
            ):
                relation_common = self._common(
                    item_id=depth_stable_id(
                        self.source,
                        "relation",
                        f"foreshadowing:{event_model.item_id}:{thread_id}:{relation_type}",
                    ),
                    kind="relation",
                    category=label,
                    conclusion=explanation,
                    epistemic_status="inferred",
                    chapter_ids=[event_model.chapter_ids[0]],
                    evidence_ids=list(event_model.evidence_ids),
                    confidence=0.8,
                    uncertainty=["关系来自具体对象在前后行动中的重复与变化。"],
                    start=event_model.normalized_start,
                    end=event_model.normalized_end,
                )
                relations.append(
                    DepthRelation.model_validate({
                        **relation_common,
                        "start": DepthEndpoint(item_id=event_model.item_id, kind="event"),
                        "end": DepthEndpoint(item_id=thread_id, kind="foreshadowing"),
                        "relation_type": relation_type,
                        "explanation": explanation,
                    })
                )
        return (
            threads,
            states,
            relations,
            f"正文中识别到{len(threads)}条有前后具体证据的铺垫线索。",
            [],
        )

    def _chapter_evidence(self, chapter: ChapterInput, label: str) -> str:
        segments = self.segments_by_chapter[chapter.chapter_id]
        if segments:
            segment = segments[0]
            return self.evidence.span(chapter, segment.start, segment.end, label)
        raise ValueError("blank chapter has no span evidence")

    def _rhythm_view(self) -> tuple[list[DepthRhythm], str]:
        items: list[DepthRhythm] = []
        for index, chapter in enumerate(self.chapters):
            start, end = self._chapter_progress(chapter)
            segments = self.segments_by_chapter[chapter.chapter_id]
            if not segments:
                common = self._common(
                    item_id=depth_stable_id(self.source, "rhythm", f"chapter:{chapter.chapter_id}"),
                    kind="rhythm",
                    category="章节节奏",
                    conclusion=f"第{chapter.chapter_number}章没有正式正文，当前节奏未知。",
                    epistemic_status="unknown",
                    chapter_ids=[chapter.chapter_id],
                    evidence_ids=[],
                    confidence=0.0,
                    uncertainty=["该章节为空，无法判断节奏、张力和信息密度。"],
                    start=start,
                    end=end,
                )
                items.append(DepthRhythm.model_validate({
                    **common,
                    "narrative_function": "不确定",
                    "scene_summary": "当前章节没有可分析的正式正文。",
                    "pace": None,
                    "tension": None,
                    "information_density": None,
                    "transition": "章节转场未知。",
                }))
                continue
            first = segments[0]
            evidence_id = self.evidence.span(chapter, first.start, first.end, "章节节奏片段")
            text = chapter.content
            pace = 0.72 if len(segments) >= 3 or self._has_effective_positive(
                text, r"决定|追赶|打开|找到|进入|离开"
            ) else 0.48
            tension = 0.76 if self._has_positive(text, r"危险|害怕|追赶|冲突|危机|却|但是") else 0.38
            density = min(0.95, 0.34 + len(segments) * 0.12 + (0.12 if self.names else 0.0))
            function = (
                "开端观察" if index == 0 else
                "收束观察" if index == len(self.chapters) - 1 else
                "推进与转折观察" if self._has_effective_positive(
                    text, r"决定|却|但是|危机|转折|打开|找到|进入|离开"
                )
                else "发展观察"
            )
            common = self._common(
                item_id=depth_stable_id(self.source, "rhythm", f"chapter:{chapter.chapter_id}"),
                kind="rhythm",
                category="章节节奏",
                conclusion=f"第{chapter.chapter_number}章的推进速度、张力和信息释放可由正文片段观察。",
                epistemic_status="observed",
                chapter_ids=[chapter.chapter_id],
                evidence_ids=[evidence_id],
                confidence=0.72,
                uncertainty=[],
                start=start,
                end=end,
            )
            items.append(DepthRhythm.model_validate({
                **common,
                "narrative_function": function,
                "scene_summary": _clip(first.clean, 300),
                "pace": float(pace),
                "tension": float(tension),
                "information_density": float(density),
                "transition": "本章与前后章节的转接细节仍需完整场景上下文确认。",
            }))
        return items, "节奏曲线按章节共享同一条阅读轴，指标只表示当前正文的观察值。"

    def _reader_view(self) -> tuple[list[DepthReaderExperience], str]:
        items: list[DepthReaderExperience] = []
        for index, chapter in enumerate(self.chapters):
            start, end = self._chapter_progress(chapter)
            segments = self.segments_by_chapter[chapter.chapter_id]
            if not segments:
                common = self._common(
                    item_id=depth_stable_id(self.source, "reader", f"chapter:{chapter.chapter_id}"),
                    kind="reader_experience",
                    category="读者体验",
                    conclusion=f"第{chapter.chapter_number}章为空，读者期待和情绪影响未知。",
                    epistemic_status="unknown",
                    chapter_ids=[chapter.chapter_id],
                    evidence_ids=[],
                    confidence=0.0,
                    uncertainty=["该章节没有正文证据，无法判断读者体验。"],
                    start=start,
                    end=end,
                )
                items.append(DepthReaderExperience.model_validate({
                    **common,
                    "expectation": "当前没有足够文本形成可验证的期待。",
                    "information_gap": "当前没有正文信息差证据。",
                    "emotional_effect": "情绪效果未知。",
                    "curiosity": None,
                    "suspense": None,
                    "emotional_valence": None,
                    "payoff": "当前没有可判断的回收。",
                }))
                continue
            first = segments[0]
            evidence_id = self.evidence.span(chapter, first.start, first.end, "读者体验片段")
            text = chapter.content
            expectation = (
                "行动目标或待解决问题会推动读者继续期待结果。"
                if self._has_positive(text, r"想|寻找|疑问|秘密|决定|等待|为什么")
                else "当前片段主要提供场景或行动，后续期待尚不明确。"
            )
            gap = (
                "片段保留了未解释的信息或具体线索，形成可观察的信息差。"
                if self._has_positive(text, r"秘密|疑问|线索|为什么|失踪|未知")
                else "当前片段没有明确的未解信息差。"
            )
            emotion = (
                "危险、害怕、追赶或解决信号会改变读者的情绪预期。"
                if self._has_positive(text, r"危险|害怕|紧张|追赶|雨") or self._has_completion(text)
                else "情绪影响主要来自当前行动和场景细节，强度仍需上下文确认。"
            )
            valence = 0.24 if self._has_reader_payoff(text) else -0.18 if self._has_positive(text, r"害怕|危险|失踪|冲突") else 0.0
            common = self._common(
                item_id=depth_stable_id(self.source, "reader", f"chapter:{chapter.chapter_id}"),
                kind="reader_experience",
                category="读者体验",
                conclusion=f"第{chapter.chapter_number}章的期待、信息差和情绪影响可由局部正文观察。",
                epistemic_status="observed",
                chapter_ids=[chapter.chapter_id],
                evidence_ids=[evidence_id],
                confidence=0.66,
                uncertainty=[],
                start=start,
                end=end,
            )
            items.append(DepthReaderExperience.model_validate({
                **common,
                "expectation": expectation,
                "information_gap": gap,
                "emotional_effect": emotion,
                "curiosity": float(0.74 if self._has_positive(text, r"秘密|疑问|为什么|失踪|寻找") else 0.42),
                "suspense": float(0.72 if self._has_positive(text, r"危险|害怕|追赶|失踪") else 0.34),
                "emotional_valence": float(valence),
                "payoff": (
                    "本章出现了阶段性回应或情绪缓解。"
                    if self._has_reader_payoff(text)
                    else "当前章节的主要问题尚未显示完整回收。"
                ),
            }))
        return items, "读者体验曲线与节奏曲线共享章节阅读轴，但分别观察期待、信息差和情绪影响。"

    def _technique_view(self) -> tuple[list[DepthTechnique], str]:
        candidates: list[tuple[str, str, str]] = []
        rules = (
            (
                "对话承载信息",
                r"[“「『\"]|[”」』\"]",
                "正文使用人物对话或引语承载信息。",
                "把信息放进说话动作，使线索或关系变化以场景形式出现。",
            ),
            (
                "时间跳接与并行叙事",
                r"三年前|多年前|与此同时|同时|回忆|曾经",
                "正文显式切换到回溯或并行时间。",
                "时间标记把背景信息或另一条行动线插入当前叙述。",
            ),
            (
                "意象与感官细节",
                r"雨|风|光|影|声音|钟声|歌声|像|仿佛|色",
                "正文用可感知的环境或比喻细节呈现场景。",
                "感官细节为行动或情绪提供可回到的具体载体。",
            ),
            (
                "动作推进",
                r"决定|寻找|进入|离开|拿出|交给|打开|赶来|继续|走向",
                "正文用连续动作推动场景状态变化。",
                "动词把人物目标、阻碍和下一步后果连成可读的行动链。",
            ),
        )
        for label, pattern, observation, mechanism in rules:
            for chapter in self.chapters:
                for segment in self.segments_by_chapter[chapter.chapter_id]:
                    has_marker = (
                        self._has_effective_positive(segment.clean, pattern)
                        if label == "动作推进"
                        else self._has_positive(segment.clean, pattern)
                    )
                    if has_marker:
                        candidates.append((label, observation, mechanism + f"例证来自第{chapter.chapter_number}章。"))
                        # Store the evidence on the candidate through a
                        # deterministic side lookup below.
                        break
                if candidates and candidates[-1][0] == label:
                    break
        if not candidates:
            chapter = next(
                chapter for chapter in self.chapters
                if self.segments_by_chapter[chapter.chapter_id]
            )
            segment = self.segments_by_chapter[chapter.chapter_id][0]
            evidence_id = self.evidence.span(chapter, segment.start, segment.end, "叙事技法例证")
            candidates.append((
                "场景并置与动作描写",
                "正文呈现了一个可定位的场景或动作片段。",
                "句子把可观察的场景状态或动作放在正文中，作用边界以该局部片段为准。",
            ))

        items: list[DepthTechnique] = []
        # Re-find the first matching span by label so evidence IDs remain
        # explicit and each example is a real bounded source excerpt.
        for label, observation, mechanism in candidates[:8]:
            evidence_id = ""
            selected_chapter: ChapterInput | None = None
            selected_segment: _Segment | None = None
            patterns = {
                "对话承载信息": r"[“「『\"]|[”」』\"]",
                "时间跳接与并行叙事": r"三年前|多年前|与此同时|同时|回忆|曾经",
                "意象与感官细节": r"雨|风|光|影|声音|钟声|歌声|像|仿佛|色",
                "动作推进": r"决定|寻找|进入|离开|拿出|交给|打开|赶来|继续|走向",
            }
            for chapter in self.chapters:
                for segment in self.segments_by_chapter[chapter.chapter_id]:
                    has_marker = (
                        self._has_effective_positive(segment.clean, patterns.get(label, r"."))
                        if label == "动作推进"
                        else self._has_positive(segment.clean, patterns.get(label, r"."))
                    )
                    if has_marker:
                        selected_chapter, selected_segment = chapter, segment
                        break
                if selected_chapter is not None:
                    break
            if selected_chapter is None or selected_segment is None:
                continue
            evidence_id = self.evidence.span(
                selected_chapter, selected_segment.start, selected_segment.end, "叙事技法例证",
            )
            start, end = self._chapter_progress(selected_chapter)
            common = self._common(
                item_id=depth_stable_id(self.source, "technique", f"technique:{label}"),
                kind="technique",
                category="叙事技法",
                conclusion=f"正文在局部片段中观察到“{label}”，其普适边界仍需作者结合全篇判断。",
                epistemic_status="inferred",
                chapter_ids=[selected_chapter.chapter_id],
                evidence_ids=[evidence_id],
                confidence=0.74,
                uncertainty=["这是局部技法观察，不应直接套用到所有场景或题材。"],
                start=start,
                end=end,
            )
            items.append(DepthTechnique.model_validate({
                **common,
                "technique": label,
                "observation": observation,
                "mechanism": mechanism,
                "effect": "该做法可能让信息、节奏或情绪变化更容易被读者感知。",
                "learning_note": f"可在需要呈现同类变化时尝试“{label}”，并以场景目标和人物反应检验是否有效。",
                "applicability": "适用于有明确行动或信息目的的局部场景；不适合脱离上下文机械复制。",
                "example_evidence_ids": [evidence_id],
            }))
        return items, "技法项只引用正文中可定位的局部例证，并保留适用边界。"

    def build(self) -> DeconstructionDepthReport:
        self._build_events()
        characters, character_states, character_relations, character_summary, character_uncertainty = (
            self._character_view()
        )
        plotlines, event_models, plot_relations, plot_summary, plot_uncertainty = self._plot_view()
        (
            foreshadowing,
            foreshadowing_states,
            foreshadowing_relations,
            foreshadowing_summary,
            foreshadowing_uncertainty,
        ) = self._foreshadowing_view(event_models)
        rhythm_items, rhythm_summary = self._rhythm_view()
        reader_items, reader_summary = self._reader_view()
        technique_items, technique_summary = self._technique_view()

        chapters = [
            DepthChapter(
                chapter_id=chapter.chapter_id,
                chapter_number=chapter.chapter_number,
                title=chapter.title,
                utf16_length=_utf16_length(chapter.content),
                normalized_start=self._chapter_progress(chapter)[0],
                normalized_end=self._chapter_progress(chapter)[1],
            )
            for chapter in self.chapters
        ]
        # Every completed report contains at least one exact span because the
        # service only starts this engine for a source with nonblank content.
        if not self.evidence.items:
            raise ValueError("depth report requires source evidence")
        report = DeconstructionDepthReport.model_validate({
            "report_version": "2.0",
            "source": self.source,
            "chapters": chapters,
            "evidence": list(self.evidence.items.values()),
            "characters": {
                "summary": character_summary,
                "uncertainty": character_uncertainty,
                "characters": characters,
                "states": character_states,
                "relations": character_relations,
            },
            "plot": {
                "summary": plot_summary,
                "uncertainty": plot_uncertainty,
                "plotlines": plotlines,
                "events": event_models,
                "relations": plot_relations,
            },
            "foreshadowing": {
                "summary": foreshadowing_summary,
                "uncertainty": foreshadowing_uncertainty,
                "threads": foreshadowing,
                "states": foreshadowing_states,
                "relations": foreshadowing_relations,
            },
            "rhythm": {
                "summary": rhythm_summary,
                "uncertainty": [],
                "items": rhythm_items,
            },
            "reader_experience": {
                "summary": reader_summary,
                "uncertainty": [],
                "items": reader_items,
            },
            "technique": {
                "summary": technique_summary,
                "uncertainty": [],
                "items": technique_items,
            },
        })
        return report


__all__ = ["ChapterInput", "DepthAnalysisEngine", "DepthSnapshot"]
