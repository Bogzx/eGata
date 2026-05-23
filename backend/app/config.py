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
    # Delivery-SMS kill switch. Defaults to None so it tracks mock_otp
    # (the legacy behavior — `MOCK_OTP=1` doubled as the SMS kill). Set
    # MOCK_SMS=0 explicitly in production along with MOCK_OTP=0; or set
    # MOCK_SMS=1 alone to keep OTP-via-Twilio while skipping deliveries.
    mock_sms: bool | None = Field(default=None)

    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-2.5-flash")
    gemini_voice_model: str = Field(default="gemini-3.1-flash-live-preview")
    gemini_voice_name: str = Field(default="Aoede")
    openai_api_key: str = Field(default="")

    jwt_signing_secret: str = Field(...)
    jwt_algorithm: str = Field(default="HS256")
    jwt_expires_seconds: int = Field(default=86400)
    jwt_audience: str = Field(default="civicai-tools")
    jwt_issuer: str = Field(default="civicai-voice")

    # Default to local dev origins only. Wildcard + allow_credentials=True
    # is broken-by-browser anyway (Chrome refuses the combo) and would let
    # any origin in the wild send credentialed requests. Prod MUST set
    # ALLOW_ORIGINS to an explicit comma-separated allow list.
    #
    # Includes :3030 and :3001 alongside :3000 because the Next.js dev
    # server falls through to the next free port whenever 3000 is in use
    # (and the demo machine routinely has something on 3000). Before this,
    # every API call from a non-3000 dev server was blocked by the browser
    # at the preflight check and the chat just sat on "Se încarcă..."
    # forever — the same symptom as a broken auth token, which is what
    # the user noticed when voice messages "couldn't even send".
    allow_origins: str = Field(
        default=(
            "http://localhost:3000,http://127.0.0.1:3000,"
            "http://localhost:3001,http://127.0.0.1:3001,"
            "http://localhost:3030,http://127.0.0.1:3030"
        )
    )
    public_base_url: str = Field(default="http://localhost:8000")
    twilio_bridge_public_url: str = Field(default="")

    ledger_genesis_hash: str = Field(default="0x" + "0" * 64)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
