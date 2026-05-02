from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 声明必须存在的环境变量，如果 .env 里没有这个键，程序启动时会直接报错阻止运行
    openai_api_key: str

    openai_base_url: str 

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# 实例化配置对象，全局只需实例化一次
settings = Settings()

if __name__ == "__main__":
    # 调用时直接像访问类属性一样访问，IDE 会有完美的自动补全
    print(f"✅ 成功读取 Pydantic 配置 Key: {settings.openai_api_key[:6]}...")