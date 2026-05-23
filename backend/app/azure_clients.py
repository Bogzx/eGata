"""Shared Azure SDK clients + format converters.

One module owns:
  * the lazy AsyncAzureOpenAI client for text chat + embeddings
  * the VoiceLive credential factory
  * tool-schema conversion to the two shapes the OpenAI APIs accept
    (Chat Completions wraps each tool in {type, function}; the Realtime
    API takes a flat {type, name, description, parameters})

Keeping these in one place is what lets agent_voice.py, twilio_bridge.py,
session_engine.py, and embeddings.py stay short.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI

from app.config import get_settings


# ---- AsyncAzureOpenAI (chat + embeddings) ----


@lru_cache(maxsize=1)
def get_openai_client() -> AsyncAzureOpenAI:
    s = get_settings()
    if not s.azure_openai_api_key:
        raise RuntimeError(
            "AZURE_OPENAI_API_KEY not set — text chat + embeddings require it."
        )
    return AsyncAzureOpenAI(
        api_key=s.azure_openai_api_key,
        azure_endpoint=s.azure_openai_endpoint,
        api_version=s.azure_openai_api_version,
    )


# ---- VoiceLive ----


def get_voicelive_credential() -> AzureKeyCredential:
    s = get_settings()
    if not s.azure_voicelive_api_key:
        raise RuntimeError(
            "AZURE_VOICELIVE_API_KEY not set — voice features require it."
        )
    return AzureKeyCredential(s.azure_voicelive_api_key)


# ---- Tool-schema conversion ----

_TYPE_MAP = {
    "OBJECT": "object",
    "STRING": "string",
    "NUMBER": "number",
    "INTEGER": "integer",
    "BOOLEAN": "boolean",
    "ARRAY": "array",
    "NULL": "null",
}


def _normalize_schema(node: Any) -> Any:
    """Recursively lowercase UPPERCASE schema types to JSON-schema.

    Tool registrations use the legacy uppercase ("OBJECT"/"STRING")
    convention; OpenAI Chat Completions and the Realtime API both want
    lowercase JSON-schema types. Walk the tree once at conversion time
    so the tool definitions themselves stay untouched.
    """
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k == "type" and isinstance(v, str) and v in _TYPE_MAP:
                out[k] = _TYPE_MAP[v]
            else:
                out[k] = _normalize_schema(v)
        return out
    if isinstance(node, list):
        return [_normalize_schema(x) for x in node]
    return node


def tools_for_chat_completions(
    function_declarations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Wrap each declaration in OpenAI ChatCompletions {type, function} shape."""
    out: list[dict[str, Any]] = []
    for d in function_declarations:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": d["name"],
                    "description": d.get("description", ""),
                    "parameters": _normalize_schema(d.get("parameters") or {}),
                },
            }
        )
    return out


def tools_for_realtime(
    function_declarations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Flat shape used by the Azure VoiceLive / OpenAI Realtime tools field."""
    out: list[dict[str, Any]] = []
    for d in function_declarations:
        out.append(
            {
                "type": "function",
                "name": d["name"],
                "description": d.get("description", ""),
                "parameters": _normalize_schema(d.get("parameters") or {}),
            }
        )
    return out


# ---- History conversion ----


def history_to_openai_messages(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter stored history to valid OpenAI Chat Completions messages.

    history is persisted as a list of OpenAI-shaped dicts (role/content,
    plus optional tool_calls/tool_call_id). Anything that doesn't conform
    is dropped — we don't carry forward unrecognized shapes.
    """
    out: list[dict[str, Any]] = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        if role not in {"system", "user", "assistant", "tool"}:
            continue
        out.append(entry)
    return out


def history_to_user_only_texts(history: list[dict[str, Any]]) -> list[str]:
    """Extract just the user-turn text content for replay into VoiceLive.

    VoiceLive's `conversation.item.create` accepts text per item, and we
    want to seed the model with prior user turns (model replies will be
    re-derived). Skips entries with no usable text.
    """
    msgs = history_to_openai_messages(history)
    out: list[str] = []
    for m in msgs:
        if m.get("role") != "user":
            continue
        content = m.get("content")
        if isinstance(content, str) and content.strip():
            out.append(content)
        elif isinstance(content, list):
            # OpenAI multimodal content — extract text parts.
            for c in content:
                if isinstance(c, dict) and c.get("type") == "input_text":
                    t = c.get("text")
                    if isinstance(t, str) and t.strip():
                        out.append(t)
    return out
