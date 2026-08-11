"""AI 创作室与导演台的数据合同。

AI 专属状态和阶段 2 的正文/档案稿本分开存储：本文件只描述主编、蓝图、导演
轮转与角色上下文；正式正文仍由 ``schemas.independent`` 的唯一当前稿本承载。

专业角色和故事人物是两层不同实体：专业角色负责全局规划/审校，故事人物
只携带自己的经历与私有记忆。两者不能在接口或提示上下文中混用。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


BlueprintStage = Literal["drafting", "ready_to_confirm", "confirmed", "director_ready"]
DirectorStrategy = Literal["full_auto", "pause_at_key_nodes"]
DirectorStatus = Literal[
    "queued",
    "character_simulation",
    "writing",
    "reviewing",
    "updating_archive",
    "waiting_for_choice",
    "paused",
    "completed",
    "failed",
]
RoleState = Literal["等待", "分析中", "已建议", "需补充"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StoryBlueprint(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    core_premise: str = ""
    core_conflict: str = ""
    protagonist: str = ""
    protagonist_motivation: str = ""
    key_relationships: str = ""
    world_rules: str = ""
    target_length: str = ""
    ending_direction: str = ""
    volume_outline: list[str] = Field(default_factory=list)


class AIMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    role: Literal["author", "editor"]
    content: str
    created_at: datetime = Field(default_factory=utc_now)


class ProfessionalRoleStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_id: Literal["editor", "plot", "character", "world", "rhythm"]
    label: str
    state: RoleState = "等待"
    output: str = ""
    updated_at: datetime = Field(default_factory=utc_now)


class AISettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: DirectorStrategy = "pause_at_key_nodes"
    reveal_consequences: bool = False


class DirectorChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    choice_id: str
    label: str
    description: str
    consequence: str
    # 历史稿本可能没有该字段；真实协调输出使用下面的严格合同。
    character_id: str | None = None


class DirectorChoiceOutput(BaseModel):
    """模型协调阶段的严格选择合同；人物来源不可省略。"""

    model_config = ConfigDict(extra="forbid")

    choice_id: str
    label: str
    description: str
    consequence: str
    character_id: str = Field(..., min_length=1, max_length=120)


class BlueprintPatch(BaseModel):
    """主编本轮只允许返回九个蓝图字段的增量。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    core_premise: str | None = Field(default=None, max_length=1000)
    core_conflict: str | None = Field(default=None, max_length=1000)
    protagonist: str | None = Field(default=None, max_length=300)
    protagonist_motivation: str | None = Field(default=None, max_length=600)
    key_relationships: str | None = Field(default=None, max_length=1200)
    world_rules: str | None = Field(default=None, max_length=1600)
    target_length: str | None = Field(default=None, max_length=120)
    ending_direction: str | None = Field(default=None, max_length=800)
    volume_outline: list[str] | None = Field(default=None, max_length=20)


class BlueprintAssistantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reply: str = Field(..., min_length=1, max_length=4000)
    blueprint_patch: BlueprintPatch = Field(default_factory=BlueprintPatch)


class StoryCharacterSimulationResponse(BaseModel):
    """故事人物模型的公开产出；不得把私有记忆原文带入这些字段。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    character_id: str = Field(..., min_length=1, max_length=120)
    public_intent: str = Field(..., min_length=1, max_length=800)
    public_action: str = Field(..., min_length=1, max_length=800)
    emotional_state: str = Field(default="未定", min_length=1, max_length=120)
    current_goal: str = Field(default="", max_length=600)


class DirectorCoordinationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    choices: list[DirectorChoiceOutput] = Field(..., min_length=3, max_length=3)
    recommended_choice_id: str = Field(..., min_length=1, max_length=120)


class DirectorBodyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: str = Field(..., min_length=1, max_length=6000)
    review_summary: str = Field(default="", max_length=1200)
    public_character_updates: list[str] = Field(default_factory=list, max_length=20)
    plotline_updates: list[str] = Field(default_factory=list, max_length=20)
    foreshadowing_candidates: list[str] = Field(default_factory=list, max_length=20)
    question_points: list[str] = Field(default_factory=list, max_length=20)


class DirectorReviewResponse(BaseModel):
    """正文通过纯文本校验后的专业审校合同。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_chapter: int = Field(..., ge=1)
    summary: str = Field(..., min_length=1, max_length=1200)
    public_character_updates: list[str] = Field(default_factory=list, max_length=20)


class DirectorArchiveResponse(BaseModel):
    """只接收当前章节来源的档案增量；疑问内容保持为疑问点。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_chapter: int = Field(..., ge=1)
    plotline_updates: list[str] = Field(default_factory=list, max_length=20)
    foreshadowing_candidates: list[str] = Field(default_factory=list, max_length=20)
    question_points: list[str] = Field(default_factory=list, max_length=20)


class ModelUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class ModelCallMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str
    stage: str
    provider: str
    model: str
    status: Literal["completed", "failed"]
    usage: ModelUsage = Field(default_factory=ModelUsage)
    usage_known: bool = True
    latency_ms: int = Field(default=0, ge=0)
    attempts: int = Field(default=1, ge=1)


class ModelCallRecord(ModelCallMetadata):
    """服务端侧车中的安全调用记录。

    ``result`` 只为读取阶段 15 旧侧车保留兼容形状，并从所有新持久化 JSON
    排除；新完成结果统一进入已通过业务校验的 ``AIProjectRecord.model_cache``。
    """

    result: dict[str, Any] = Field(default_factory=dict, exclude=True)
    error_code: str | None = None
    error_message: str | None = None


class RoleContext(BaseModel):
    """后台专业角色上下文。

    这是专业角色层的兼容合同，不是故事人物上下文；``private_memory`` 仅是
    该专业角色的职责工作笔记，绝不包含任何故事人物私有事实。
    """

    model_config = ConfigDict(extra="forbid")

    role_id: str
    role_name: str
    entity_layer: Literal["professional"] = "professional"
    access_scope: Literal["global"] = "global"
    shared_worldview: str
    necessary_facts: list[str] = Field(default_factory=list)
    private_memory: list[str] = Field(default_factory=list)


class StoryCharacterAgent(BaseModel):
    """从蓝图/档案动态得到的故事人物实体。"""

    model_config = ConfigDict(extra="forbid")

    character_id: str
    name: str
    role: str = "故事人物"
    goal: str = ""
    known_facts: list[str] = Field(default_factory=list)
    emotional_state: str = "未定"
    current_scene: str = "第一章"
    public_facts: list[str] = Field(default_factory=list)
    experiences: list[str] = Field(default_factory=list)
    private_memory: list[str] = Field(default_factory=list)


class StoryCharacterContext(BaseModel):
    """单个故事人物能看到的上下文；不会携带其他人物的私有记忆。"""

    model_config = ConfigDict(extra="forbid")

    entity_layer: Literal["story_character"] = "story_character"
    character_id: str
    name: str
    shared_world_rules: str
    public_facts: list[str] = Field(default_factory=list)
    necessary_facts: list[str] = Field(default_factory=list)
    own_experiences: list[str] = Field(default_factory=list)
    private_memory: list[str] = Field(default_factory=list)
    current_scene: str = "第一章"
    current_goal: str = ""
    emotional_state: str = "未定"


class DirectorRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    project_id: str
    blueprint_revision: int = Field(..., ge=0)
    chapter_number: int = Field(default=1, ge=1)
    strategy: DirectorStrategy
    status: DirectorStatus = "queued"
    current_stage: str = "排队"
    stage_history: list[str] = Field(default_factory=list)
    choices: list[DirectorChoice] = Field(default_factory=list)
    simulated_character_id: str | None = None
    selected_choice_id: str | None = None
    # 服务端在选择提交前留下的恢复意图；公开运行合同会移除它。
    pending_choice_id: str | None = None
    # ``role`` 是阶段 3/旧 sidecar 的兼容值；新写入明确区分故事人物委托
    # ``character`` 与作者亲自选择 ``author``。
    choice_source: Literal["author", "character", "role", "none"] = "none"
    generated_content: str = ""
    preview_content: str = ""
    independent_task_id: str | None = None
    estimated_credits: int = Field(default=0, ge=0)
    used_credits: int = Field(default=0, ge=0)
    credits_charged: bool = False
    idempotency_key: str | None = None
    run_revision: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    error_message: str | None = None
    model_calls: list[ModelCallMetadata] = Field(default_factory=list)
    review_summary: str = ""
    archive_candidates: dict[str, list[str]] = Field(default_factory=dict)
    archive_source_chapter: int | None = Field(default=None, ge=1)


class CreditLedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ledger_id: str
    run_id: str
    label: str
    credits: int = Field(..., ge=0)
    created_at: datetime = Field(default_factory=utc_now)


class AINotification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notification_id: str
    kind: Literal["blueprint_confirmed", "director_waiting", "director_completed", "director_failed"]
    message: str
    created_at: datetime = Field(default_factory=utc_now)
    read: bool = False


class AIProjectRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    account_id: str
    title: str
    brief: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    stage: BlueprintStage = "drafting"
    blueprint: StoryBlueprint = Field(default_factory=StoryBlueprint)
    blueprint_revision: int = Field(default=0, ge=0)
    confirmed_blueprint_revision: int | None = None
    messages: list[AIMessage] = Field(default_factory=list)
    role_statuses: list[ProfessionalRoleStatus] = Field(default_factory=list)
    story_characters: list[StoryCharacterAgent] = Field(default_factory=list)
    settings: AISettings = Field(default_factory=AISettings)
    runs: list[DirectorRun] = Field(default_factory=list)
    active_run_id: str | None = None
    notifications: list[AINotification] = Field(default_factory=list)
    credits_used: int = Field(default=0, ge=0)
    credit_ledger: list[CreditLedgerEntry] = Field(default_factory=list)
    model_calls: list[ModelCallRecord] = Field(default_factory=list)
    model_cache: dict[str, dict[str, Any]] = Field(default_factory=dict)
    # 仅保存通过正文长度、格式和私密内容校验的服务端待用正文；绝不返回浏览器。
    text_cache: dict[str, str] = Field(default_factory=dict)
    last_model_error: ModelCallMetadata | None = None


class AIMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: str = Field(..., min_length=1, max_length=4000)


class BlueprintUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_revision: int = Field(..., ge=0)
    core_premise: str | None = Field(default=None, max_length=1000)
    core_conflict: str | None = Field(default=None, max_length=1000)
    protagonist: str | None = Field(default=None, max_length=300)
    protagonist_motivation: str | None = Field(default=None, max_length=600)
    key_relationships: str | None = Field(default=None, max_length=1200)
    world_rules: str | None = Field(default=None, max_length=1600)
    target_length: str | None = Field(default=None, max_length=120)
    ending_direction: str | None = Field(default=None, max_length=800)
    volume_outline: list[str] | None = Field(default=None, max_length=20)


class ConfirmBlueprintRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(..., ge=0)
    idempotency_key: str | None = Field(default=None, max_length=120)


class DirectorStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: DirectorStrategy = "pause_at_key_nodes"
    idempotency_key: str | None = Field(default=None, max_length=120)
    defer: bool = False


class DirectorChoiceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    choice_id: str = Field(..., min_length=1, max_length=120)


class DirectorSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: DirectorStrategy | None = None
    reveal_consequences: bool | None = None
