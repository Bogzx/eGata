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

    # Azure OpenAI — used for text chat (session_engine) + embeddings.
    azure_openai_endpoint: str = Field(
        default="https://mihaikun2501-5356-resource.openai.azure.com/"
    )
    azure_openai_api_key: str = Field(default="")
    azure_openai_chat_deployment: str = Field(default="gpt-5-mini")
    azure_openai_embed_deployment: str = Field(default="text-embedding-3-large")
    azure_openai_api_version: str = Field(default="2024-10-21")

    # Azure VoiceLive — used for browser voice WS + Twilio phone bridge.
    # Direct model mode: we own system_instruction + tool declarations
    # client-side.
    azure_voicelive_endpoint: str = Field(
        default="https://mihaikun2501-5356-resource.services.ai.azure.com/"
    )
    azure_voicelive_api_key: str = Field(default="")
    azure_voicelive_model: str = Field(default="gpt-realtime")
    azure_voicelive_voice: str = Field(default="en-US-Ava:DragonHDLatestNeural")
    azure_voicelive_api_version: str = Field(default="2026-04-10")
    # Whisper deployment used by VoiceLive's input_audio_transcription.
    # Defaults to the Foundry standard "whisper" deployment; override if
    # your Azure resource uses a different name.
    azure_voicelive_transcription_model: str = Field(default="whisper")
    azure_voicelive_transcription_language: str = Field(default="ro")

    embedding_dim: int = Field(default=768)

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
