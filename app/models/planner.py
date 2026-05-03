"""Planner Agent 的结构化输出模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.chapter import PlotBeat


class PlannerOutput(BaseModel):
    """LLM 生成的章节规划结果。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    plot_beats: list[PlotBeat] = Field(
        ...,
        min_length=3,
        max_length=8,
        description="本章剧情节点，建议 3-6 个，按 order 升序排列",
    )
    planner_notes: list[str] = Field(
        default_factory=list,
        description="对本章节奏、伏笔、人物关系的规划说明",
    )

    @model_validator(mode="before")
    @classmethod
    def adapt_common_llm_shapes(cls, data: Any) -> Any:
        """兼容模型常见返回形态，避免字段名轻微漂移导致整次规划失败。"""

        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        if "plot_beats" not in normalized and "nodes" in normalized:
            normalized["plot_beats"] = normalized.pop("nodes")

        # 模型偶尔会额外返回章节号；章节号由状态机维护，不进入 PlannerOutput。
        normalized.pop("chapter", None)
        normalized.pop("chapter_number", None)

        beats = normalized.get("plot_beats")
        if isinstance(beats, list):
            normalized["plot_beats"] = [
                cls._normalize_raw_beat(raw_beat, index)
                for index, raw_beat in enumerate(beats, start=1)
            ]

        return normalized

    @staticmethod
    def _normalize_raw_beat(raw_beat: Any, index: int) -> Any:
        if isinstance(raw_beat, str):
            return {
                "order": index,
                "summary": raw_beat,
            }

        if not isinstance(raw_beat, dict):
            return raw_beat

        beat = dict(raw_beat)
        beat.setdefault("order", index)

        if "summary" not in beat:
            for alias in ("title", "event", "description", "content"):
                if alias in beat:
                    beat["summary"] = beat.pop(alias)
                    break

        return beat

    @field_validator("plot_beats")
    @classmethod
    def normalize_beat_order(cls, value: list[PlotBeat]) -> list[PlotBeat]:
        """保证剧情节点顺序连续，降低前端编辑和后续 Writer 消费成本。"""

        sorted_beats = sorted(value, key=lambda beat: beat.order)
        for index, beat in enumerate(sorted_beats, start=1):
            beat.order = index
        return sorted_beats
