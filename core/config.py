from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOTENV_PATH = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """只在进程内保存模型配置；任何诊断都只能读取安全派生属性。

    ``OPENAI_API_KEY`` 优先，``DASHSCOPE_API_KEY`` 是百炼兼容别名。字段可以
    缺失，这样无 Key 的本地演示和自动化测试不需要伪造密钥才能启动。
    """

    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY"),
    )
    dashscope_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DASHSCOPE_API_KEY"),
    )
    openai_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_BASE_URL", "DASHSCOPE_BASE_URL", "LLM_BASE_URL"),
    )

    # LLM 相关配置集中收口；未配置时由 effective_model 返回 unavailable。
    llm_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_MODEL", "OPENAI_MODEL", "DASHSCOPE_MODEL"),
    )
    llm_temperature: float = 0.7

    model_config = SettingsConfigDict(
        # 不依赖启动时 cwd；从任意工作目录启动都只加载项目根目录 .env。
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def effective_api_key(self) -> str:
        return (self.openai_api_key or self.dashscope_api_key or "").strip()

    @property
    def provider(self) -> str:
        if self.openai_api_key:
            return "openai"
        if self.dashscope_api_key:
            return "dashscope"
        return "unavailable"

    @property
    def effective_base_url(self) -> str | None:
        if self.openai_base_url:
            return self.openai_base_url.strip().rstrip("/") or None
        if self.provider == "dashscope":
            return "https://dashscope.aliyuncs.com/compatible-mode/v1"
        if self.provider == "openai":
            return "https://api.openai.com/v1"
        return None

    @property
    def effective_model(self) -> str:
        if self.llm_model and self.llm_model.strip():
            return self.llm_model.strip()
        if self.provider == "dashscope":
            return "qwen3.6-plus"
        if self.provider == "openai":
            return "gpt-4o-mini"
        return "unavailable"


# 全局唯一的配置实例
settings = Settings()
