"""跨卷人物聚合。

卷级报告是独立、可回溯的分析结果，不能在保存全书视图时用后卷人物卡
覆盖前卷。这个模块只做确定性的身份归并和阶段记录整理：它不替模型
判断人物关系，也不合并人物卡中的文学结论。

身份归并规则按安全程度排序：

* 相同 ``entity_key`` 明确表示同一人物；
* 没有 ``entity_key`` 时，相同规范化姓名可以合并；
* 一份卡片的规范化姓名与另一份卡片的别名完全相同，可以合并；
* 仅别名相同、模糊相似或只共享角色描述时不合并。

因此旧报告可以直接使用，误合并的风险也比模糊字符串匹配低。每个卷级
卡片都被保存为一个 ``CharacterStage``，聚合结果只增加稳定 ID 和索引，
不会丢掉任一阶段的动机、变化或证据引用。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from pydantic import BaseModel, ConfigDict, Field

from schemas.analysis_report import Character, CharacterInsight, Claim, AnalysisReport


def _normalize(value: str) -> str:
    """只消除展示层空白和常见标点，不做拼音或模糊匹配。"""

    return re.sub(r"[\s\u3000]+", "", value).strip("·•,，。；;、/／()（）[]【】\"'“”‘’")


class CharacterStage(BaseModel):
    """一张卷级人物卡在全书中的不可变快照。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_key: str = Field(min_length=1, max_length=160)
    scope_start: int = Field(ge=1)
    scope_end: int = Field(ge=1)
    character_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    entity_key: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=80)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    role: str = Field(min_length=1, max_length=80)
    identity: Claim
    motivation: Claim
    change: Claim
    portrait: Claim | None = None
    insights: list[CharacterInsight] = Field(default_factory=list, max_length=8)

    @classmethod
    def from_character(cls, source_key: str, scope_start: int, scope_end: int, character: Character) -> "CharacterStage":
        if scope_end < scope_start:
            raise ValueError("人物阶段章节范围无效")
        return cls(
            source_key=source_key,
            scope_start=scope_start,
            scope_end=scope_end,
            character_id=character.id,
            entity_key=character.entity_key,
            name=character.name,
            aliases=list(character.aliases),
            role=character.role,
            identity=character.identity,
            motivation=character.motivation,
            change=character.change,
            portrait=character.portrait,
            insights=list(character.insights),
        )


class AggregatedCharacter(BaseModel):
    """全书人物索引；``stages`` 是展示和核对的唯一完整来源。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=80)
    aliases: list[str] = Field(default_factory=list, max_length=100)
    stages: list[CharacterStage] = Field(min_length=1, max_length=500)


@dataclass(frozen=True)
class CharacterReportSlice:
    """将一份卷级报告放入聚合器所需的最小来源信息。"""

    source_key: str
    scope_start: int
    scope_end: int
    report: AnalysisReport

    def __post_init__(self) -> None:
        if not self.source_key.strip():
            raise ValueError("人物报告来源不能为空")
        if self.scope_start < 1 or self.scope_end < self.scope_start:
            raise ValueError("人物报告章节范围无效")


@dataclass(frozen=True)
class _Entry:
    stage: CharacterStage
    tokens: frozenset[str]
    explicit_key: str | None


def _stable_id(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return f"char-{digest}"


def _stage_sort_key(stage: CharacterStage) -> tuple[int, int, str, str]:
    return (stage.scope_start, stage.scope_end, stage.source_key, stage.character_id)


def _entry_tokens(character: Character) -> frozenset[str]:
    values = [character.name, *character.aliases]
    return frozenset(token for value in values if (token := _normalize(value)))


def _same_entity(left: _Entry, right: _Entry) -> bool:
    if left.explicit_key and right.explicit_key:
        return _normalize(left.explicit_key) == _normalize(right.explicit_key)
    if left.explicit_key or right.explicit_key:
        # 旧报告没有语义键时，仍允许它通过明确的姓名/别名连接；
        # 仅凭另一张卡的 entity_key 不能把两个不同姓名强行合并。
        shared_tokens = left.tokens & right.tokens
        return bool(shared_tokens) and (
            _normalize(left.stage.name) in right.tokens
            or _normalize(right.stage.name) in left.tokens
        )
    if _normalize(left.stage.name) == _normalize(right.stage.name):
        return True
    return (
        _normalize(left.stage.name) in right.tokens
        or _normalize(right.stage.name) in left.tokens
    )


def aggregate_character_slices(slices: Sequence[CharacterReportSlice] | Iterable[CharacterReportSlice]) -> list[AggregatedCharacter]:
    """按保守规则聚合卷级人物卡，返回稳定排序的全书人物索引。

    ``source_key`` 必须是持久的文档/卷标识，而不是列表下标。调用方可以
    把 ``document_id`` 作为它，这样同一份卷报告重跑不会改变阶段来源。
    报告输入会按章节范围和来源排序，因此结果与调用方传入顺序无关。
    """

    ordered_slices = sorted(
        list(slices), key=lambda item: (item.scope_start, item.scope_end, item.source_key)
    )
    entries: list[_Entry] = []
    seen_stages: set[tuple[str, str]] = set()
    for item in ordered_slices:
        for character in item.report.characters:
            stage_key = (item.source_key, character.id)
            # 同一文档重复进入全书索引时只保留一次；重新分析应使用新的
            # document/source_key，因此不会把真实的修订阶段误删。
            if stage_key in seen_stages:
                continue
            seen_stages.add(stage_key)
            stage = CharacterStage.from_character(
                item.source_key, item.scope_start, item.scope_end, character
            )
            entries.append(_Entry(stage, _entry_tokens(character), character.entity_key))

    # Union-find 只按明确规则连边。这样同一卷重复导入、输入顺序变化和后
    # 卷追加都不会靠“最后一张卡”覆盖旧阶段。
    parents = list(range(len(entries)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parents[root_right] = root_left

    for left_index, left in enumerate(entries):
        for right_index in range(left_index + 1, len(entries)):
            if _same_entity(left, entries[right_index]):
                union(left_index, right_index)

    groups: dict[int, list[CharacterStage]] = {}
    for index, entry in enumerate(entries):
        groups.setdefault(find(index), []).append(entry.stage)

    result: list[AggregatedCharacter] = []
    for stages in groups.values():
        stages.sort(key=_stage_sort_key)
        first = stages[0]
        # 明确 entity_key 优先；旧报告以最早出现的规范化姓名作为稳定回退键。
        stable_key = next(
            (_normalize(stage.entity_key) for stage in stages if stage.entity_key),
            f"name:{_normalize(first.name)}",
        )
        aliases: list[str] = []
        for stage in stages:
            for value in [stage.name, *stage.aliases]:
                if value and value != first.name and value not in aliases:
                    aliases.append(value)
        result.append(
            AggregatedCharacter(
                id=_stable_id(stable_key),
                name=first.name,
                aliases=aliases,
                stages=stages,
            )
        )
    return sorted(result, key=lambda item: (item.stages[0].scope_start, _normalize(item.name), item.id))


__all__ = [
    "AggregatedCharacter",
    "CharacterReportSlice",
    "CharacterStage",
    "aggregate_character_slices",
]
