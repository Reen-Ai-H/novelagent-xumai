from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 声明必须存在的环境变量，如果 .env 里没有这个键，程序启动时会直接报错阻止运行
    openai_api_key: str
    openai_base_url: str

    # LLM 相关配置，集中收口便于后续替换模型或调参
    llm_model: str = "qwen3.6-plus"
    llm_temperature: float = 0.7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# 全局唯一的配置实例
settings = Settings()


if __name__ == "__main__":
    print(f"✅ 成功读取 Pydantic 配置 Key: {settings.openai_api_key[:6]}...")
