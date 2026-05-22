"""Application configuration via Pydantic Settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    supabase_url: str = Field(...)
    supabase_anon_key: str = Field(...)
    supabase_service_role_key: str = Field(...)
    supabase_db_url: str = Field(...)

    twilio_account_sid: str = Field(default="")
    twilio_auth_token: str = Field(default="")
    twilio_verify_service_sid: str = Field(default="")
    twilio_phone_number: str = Field(default="")
    mock_otp: bool = Field(default=True)

    gemini_api_key: str = Field(...)
    openai_api_key: str = Field(default="")

    jwt_signing_secret: str = Field(...)
    jwt_algorithm: str = Field(default="HS256")
    jwt_expires_seconds: int = Field(default=86400)

    allow_origins: str = Field(default="*")

    ledger_genesis_hash: str = Field(default="0x" + "0" * 64)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
