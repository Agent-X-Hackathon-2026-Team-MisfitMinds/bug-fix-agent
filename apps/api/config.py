"""Server-side settings. Real values live in the ignored `.env` file."""
from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    environment: str = "development"
    session_secret: SecretStr = Field(
        default=SecretStr("dev-insecure-session-secret"),
        validation_alias=AliasChoices("SESSION_SECRET", "API_SECRET_KEY"),
    )
    github_client_id: str = Field(
        default="",
        validation_alias=AliasChoices("GITHUB_CLIENT_ID", "GITHUB_APP_CLIENT_ID"),
    )
    github_client_secret: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("GITHUB_APP_CLIENT_SECRET", "GITHUB_CLIENT_SECRET"),
    )
    github_webhook_secret: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("GITHUB_APP_WEBHOOK_SECRET", "GITHUB_WEBHOOK_SECRET"),
    )
    github_app_id: str = Field(
        default="",
        validation_alias=AliasChoices("GITHUB_APP_ID"),
    )
    github_app_private_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("GITHUB_APP_PRIVATE_KEY"),
    )
    github_installation_id: int = Field(
        default=0,
        validation_alias=AliasChoices("GITHUB_INSTALLATION_ID"),
    )
    github_repository: str = Field(
        default="",
        validation_alias=AliasChoices("GITHUB_DEMO_REPO"),
    )
    api_base_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("API_BASE_URL", "NEXT_PUBLIC_API_URL"),
    )
    web_origin: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("WEB_ORIGIN", "NEXT_PUBLIC_APP_URL", "NEXT_PUBLIC_SITE_URL"),
    )
    gemini_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("GEMINI_API_KEY", "LLM_API_KEY"),
    )
    gemini_model: str = Field(
        default="gemini-3.8-flash",
        validation_alias=AliasChoices("GEMINI_MODEL"),
    )
    gemini_fallback_models: str = Field(
        default="gemini-3.5-flash,gemini-2.5-flash",
        validation_alias=AliasChoices("GEMINI_FALLBACK_MODELS"),
    )
    cookie_secure: bool = True
    session_ttl_seconds: int = 86400
    oauth_state_ttl_seconds: int = 600


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
