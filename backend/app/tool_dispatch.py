"""HTTP endpoints invoked by browser when Gemini Live emits a function-call.

Each endpoint requires a valid tool JWT (issued by /voice/session) and forwards
to the same Python tool function used by the server-side agent loop.

URL convention: POST /tools/{tool_name}
Body: tool arguments as JSON.
Response: tool return value as JSON.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.tools import REGISTRY, ToolContext
from app.voice import JwtClaims, require_tool_jwt

router = APIRouter(prefix="/tools", tags=["tool-dispatch"])


def _ctx(claims: JwtClaims) -> ToolContext:
    return ToolContext(citizen_id=claims.citizen_id, document_id=claims.document_id)


def _serialize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


@router.post("/{tool_name}")
async def dispatch_tool(
    tool_name: str,
    args: dict[str, Any] = Body(default_factory=dict),
    claims: JwtClaims = Depends(require_tool_jwt),
) -> Any:
    tool = REGISTRY.get(tool_name)
    if tool is None:
        raise HTTPException(404, f"Unknown tool '{tool_name}'")
    try:
        result = await tool(_ctx(claims), **args)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Tool {tool_name} failed: {e}")
    return _serialize(result)
