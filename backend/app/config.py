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

    # Only the DB URL is mandatory. The Supabase *client* (the three keys
    # above it) is used by exactly one module — app/storage.py — so a local
    # `docker compose up` runs against plain Postgres with no Supabase
    # project at all. get_supabase() raises a clear error if something asks
    # for the client while these are empty.
    supabase_url: str = Field(default="")
    supabase_anon_key: str = Field(default="")
    supabase_service_role_key: str = Field(default="")
    supabase_db_url: str = Field(...)

    # "auto" picks supabase when a project is configured and local otherwise.
    # Set explicitly to make a deployment fail loudly on a missing variable
    # rather than quietly writing citizens' PDFs to a container filesystem.
    storage_backend: str = Field(default="auto")
    # Where the local backend keeps PDFs. Mount a volume here in compose.
    pdf_storage_dir: str = Field(default="./.data/pdfs")

    twilio_account_sid: str = Field(default="")
    twilio_auth_token: str = Field(default="")
    twilio_verify_service_sid: str = Field(default="")
    twilio_phone_number: str = Field(default="")
    # Fails closed. With mock_otp on, /auth/login-roeid hands a challenge to
    # anyone naming a persona and /auth/otp accepts the literal code 123456
    # (auth.py:142-148) — i.e. anyone can log in as anyone. Defaulting this to
    # True meant any deploy that forgot the env var was wide open. Same
    # posture as DEMO_RESET_TOKEN in demo.py:48-51, which already refuses to
    # work unless explicitly enabled. Set MOCK_OTP=1 for local dev and demos;
    # tests set it in conftest.py:15.
    mock_otp: bool = Field(default=False)

    # Which agent answers /agent/chat: "azure" (the LLM), "offline" (the
    # deterministic scripted agent in app/offline_agent.py — no API key, no
    # cost) or "auto" (azure when AZURE_OPENAI_API_KEY is set, else offline).
    agent_backend: str = Field(default="auto")
    # Same choice for procedure-search embeddings: "azure" (text-embedding
    # deployment), "local" (app/local_embeddings.py) or "auto".
    embeddings_backend: str = Field(default="auto")

    # Azure OpenAI — used for text chat (session_engine) + embeddings.
    # No default: a personal resource name here leaked a tenant and silently
    # misrouted a stranger's requests to somebody else's endpoint. Empty means
    # the SDK raises at startup, which is the loud failure we want.
    azure_openai_endpoint: str = Field(default="")
    azure_openai_api_key: str = Field(default="")
    azure_openai_chat_deployment: str = Field(default="gpt-5-mini")
    azure_openai_embed_deployment: str = Field(default="text-embedding-3-large")
    azure_openai_api_version: str = Field(default="2024-10-21")

    # Azure VoiceLive — used for browser voice WS + Twilio phone bridge.
    # Direct model mode: we own system_instruction + tool declarations
    # client-side.
    # Empty for the same reason as azure_openai_endpoint above.
    azure_voicelive_endpoint: str = Field(default="")
    azure_voicelive_api_key: str = Field(default="")
    azure_voicelive_model: str = Field(default="gpt-realtime")
    azure_voicelive_voice: str = Field(default="en-US-Ava:DragonHDLatestNeural")
    azure_voicelive_api_version: str = Field(default="2026-04-10")
    # Transcription back-channel for VoiceLive's input_audio_transcription.
    # This is NOT a deployment name — it's a fixed enum the realtime API
    # accepts: one of "whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe",
    # "gpt-4o-transcribe-diarize", "azure-fast-transcription", "azure-speech",
    # "mai-transcribe-1". VoiceLive maps the chosen value to whatever STT
    # backend Azure has wired up on the resource.
    #
    # We default to gpt-4o-mini-transcribe (not whisper-1) because whisper-1
    # only emits one final COMPLETED event with the full transcript — the
    # user's bubble pops in fully-formed at end-of-utterance. The gpt-4o
    # transcribe models stream partials via
    # CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_DELTA, which we forward as
    # `user_delta` frames so the bubble fills word-by-word while they speak.
    azure_voicelive_transcription_model: str = Field(default="gpt-4o-mini-transcribe")
    azure_voicelive_transcription_language: str = Field(default="ro")

    # Azure Speech Service — used in PARALLEL to VoiceLive for true
    # streaming user transcripts. VoiceLive's input_audio_transcription
    # only emits a COMPLETED event (no DELTA partials) under all currently
    # supported API versions / models, so the user bubble pops in
    # fully-formed at end-of-utterance instead of filling word-by-word.
    # The classic Speech SDK opens its own WebSocket and fires a
    # `recognizing` event for every partial token, which we forward to
    # the browser as user_delta frames. The same Foundry key works for
    # both VoiceLive and Speech; only the region differs.
    azure_speech_key: str = Field(default="")
    azure_speech_region: str = Field(default="swedencentral")
    azure_speech_language: str = Field(default="ro-RO")

    embedding_dim: int = Field(default=768)

    jwt_signing_secret: str = Field(...)
    jwt_algorithm: str = Field(default="HS256")
    jwt_expires_seconds: int = Field(default=86400)
    jwt_audience: str = Field(default="egata-tools")
    jwt_issuer: str = Field(default="egata-voice")

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
    # The exact URL Twilio POSTs the voice webhook to (as configured in the
    # Twilio console). Needed behind a proxy/tunnel, where the URL the app
    # sees differs from the one Twilio signed. Empty = use the request URL.
    twilio_webhook_public_url: str = Field(default="")



@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def _resolve(configured: str, *, name: str, keyed: str, keyless: str, has_key: bool) -> str:
    value = (configured or "auto").strip().lower()
    if value == "auto":
        return keyed if has_key else keyless
    if value not in {keyed, keyless}:
        raise RuntimeError(f"{name}={configured!r} is not one of auto|{keyed}|{keyless}")
    return value


def resolved_agent_backend(settings: Settings | None = None) -> str:
    """'azure' or 'offline'."""
    s = settings or get_settings()
    return _resolve(
        s.agent_backend,
        name="AGENT_BACKEND",
        keyed="azure",
        keyless="offline",
        has_key=bool(s.azure_openai_api_key),
    )


def resolved_embeddings_backend(settings: Settings | None = None) -> str:
    """'azure' or 'local'."""
    s = settings or get_settings()
    return _resolve(
        s.embeddings_backend,
        name="EMBEDDINGS_BACKEND",
        keyed="azure",
        keyless="local",
        has_key=bool(s.azure_openai_api_key),
    )
