"""Shared, cached Gemini client.

Before this module, three different files (session_engine, agent_voice,
twilio_bridge) each created their own genai.Client. agent_voice and
twilio_bridge created one PER WebSocket connect — wasteful and made test
monkey-patching inconsistent. embeddings had two redundant factories
side by side.

Callers now go through `get_genai_client()` everywhere. It's an
lru_cache singleton so the client is created at most once per worker
process.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from google import genai

from app.config import get_settings


@lru_cache(maxsize=1)
def get_genai_client() -> Any:
    """Return the process-wide cached genai.Client."""
    return genai.Client(api_key=get_settings().gemini_api_key)


def reset_genai_client_cache() -> None:
    """For tests: clear the cached client so a new api_key takes effect."""
    get_genai_client.cache_clear()
