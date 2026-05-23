---
type: dependency
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Dep: FastAPI Stack

Python 3.12. Pinned in `backend/pyproject.toml`.

## Core

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | 0.115.4 | HTTP framework |
| `uvicorn[standard]` | 0.32.0 | ASGI server |
| `pydantic` | >=2.10, <2.12 | Models + validation |
| `pydantic-settings` | 2.6.1 | Env var loading |
| `python-jose[cryptography]` | 3.3.0 | JWT (used by [[security]]) |
| `pyjwt` | >=2.9.0 | Also installed; not directly used at runtime |
| `httpx` | >=0.28.1, <0.29 | Async HTTP client |
| `python-multipart` | 0.0.17 | Form data parsing |
| `websockets` | >=13.1 | WS client/server primitives |

## Domain libs

| Package | Purpose |
|---|---|
| `supabase` >=2.18 | Supabase client |
| `psycopg[binary,pool]` 3.2.3 | Postgres driver |
| `google-genai` >=2.0 | Gemini client |
| `aiohttp` >=3.11 | Floored explicitly — `google-genai` 2.x uses `StreamReader.readline(max_line_length=...)` only in aiohttp ≥3.11 |
| `twilio` 9.3.5 | Verify + Voice |
| `jinja2` 3.1.4 | Used by Twilio python lib internally |
| `apscheduler` >=3.10.4, <4 | Background worker |
| `sentry-sdk[fastapi]` >=2.18 | Error reporting (optional) |
| `pyyaml` 6.0.2 | OpenAPI export script |

## Dev

```
pytest 8.3.3
pytest-asyncio 0.24.0
ruff 0.7.2
mypy 1.13.0
types-pyyaml
```

## Pydantic v2 ↔ pydantic-ai

> [!gotcha] Pydantic pinned to `>=2.10` instead of `==2.9.2`
> Originally pinned to 2.9.2 by the spec; bumped because `pydantic-ai==0.0.13` (which Plan 3 was going to use) requires pydantic ≥2.10. No API-level impact. See [[CHECKPOINT_1]] (`backend/CHECKPOINT_1.md`).

## See also

- backend/pyproject.toml — source of truth
- [[Dockerfile]] — installs `pip install .`
