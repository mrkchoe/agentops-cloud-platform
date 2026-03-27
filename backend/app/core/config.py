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

    # WhatsApp / messaging channels (TODO: set real values in production)
    whatsapp_provider: str = "twilio"  # twilio | meta
    whatsapp_webhook_verify_token: str = ""
    whatsapp_verify_signature: bool = False  # TODO: enable when credentials are configured

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""

    meta_whatsapp_access_token: str = ""
    meta_whatsapp_phone_number_id: str = ""
    meta_app_secret: str = ""
    meta_verify_token: str = ""

    default_whatsapp_workspace_id: int | None = None
    default_whatsapp_agent_id: int | None = None


settings = Settings()

