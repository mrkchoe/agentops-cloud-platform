from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyUrl


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_env: str = "development"
    api_auth_token: str = "dev-demo-token"

    database_url: AnyUrl = "postgresql+psycopg2://postgres:postgres@localhost:5432/agentops_cloud"
    redis_url: AnyUrl = "redis://localhost:6379/0"

    celery_broker_url: AnyUrl = "redis://localhost:6379/0"
    celery_result_backend: AnyUrl = "redis://localhost:6379/0"
    celery_task_always_eager: bool = False

    llm_provider: str = "mock"  # mock | openai
    openai_api_key: str | None = None

    seed_demo: bool = False


settings = Settings()

