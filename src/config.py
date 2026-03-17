from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "AgentBasePlatform"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+asyncpg://abp_user:abp_password@localhost:5432/agent_base_platform"
    DATABASE_URL_SYNC: str = "postgresql://abp_user:abp_password@localhost:5432/agent_base_platform"

    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM Model (Qwen via DashScope)
    DASHSCOPE_API_KEY: str = ""
    DEFAULT_MODEL_NAME: str = "qwen-max"
    DEFAULT_MODEL_STREAM: bool = True
    DEFAULT_MODEL_ENABLE_THINKING: bool = False
    DEFAULT_MODEL_MAX_TOKENS: int = 4096
    DEFAULT_MODEL_TEMPERATURE: float = 0.7

    # Agent Runtime
    AGENT_MAX_REACT_ITERATIONS: int = 10
    AGENT_EXECUTION_TIMEOUT: int = 120
    AGENT_FALLBACK_TO_MOCK: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
