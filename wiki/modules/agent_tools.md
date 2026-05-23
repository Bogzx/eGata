---
type: module
path: "backend/app/agent_tools/__init__.py"
status: active
language: python
purpose: "State-gated tool registry + dispatcher."
depends_on: [sessions]
used_by: [session_engine, agent, agent_voice, twilio_bridge]
created: 2026-05-23
updated: 2026-05-23
---

# agent_tools

The agent's tool surface. Each tool declares which `SessionState`s it's valid in; the dispatcher refuses out-of-state calls and returns an error.

## Inventory

```
                    EXPLORING  CONFIRMING_MATCH  FILLING  REVIEWING  DELIVERED  REDIRECTED
lookup_procedure       ●            ●                                   ●           ●
list_procedures        ●            ●                                   ●           ●
start_procedure                     ●                                   ●
propose_widget                      ●               ●
set_field                                           ●         ●
complete_document                                             ●
find_redirect          ●            ●                                   ●           ●
```

Why `find_redirect` and `lookup_procedure` are **OFF during FILLING / REVIEWING**: a mid-fill mention ("vreau și impozit cândva") must not flip state to REDIRECTED and abandon the draft. The agent can still reply with text about the right institution; it just can't fire the tool. See [[ADR State-Gated Tool Surface]].

Each tool lives in its own file under `backend/app/agent_tools/`:

- [[lookup_procedure]]
- [[list_procedures]]
- [[start_procedure]]
- [[set_field]]
- [[propose_widget]]
- [[complete_document]]
- [[find_redirect]]

## Data types

```python
@dataclass
class ToolContext:
    citizen_id: str
    citizen_attributes: dict[str, Any]

@dataclass
class ToolResult:
    output: dict[str, Any]
    error: str | None = None
    transition_to: SessionState | None = None     # dispatcher applies if legal
    frontend_event: dict[str, Any] | None = None  # pushed alongside snapshot

@dataclass
class Tool:
    name: str
    description: str
    parameters: dict          # JSON-schema-ish for Gemini function_declarations
    valid_states: set[SessionState]
    execute: Callable
```

## Dispatcher

```python
async def dispatch(session, name, args, ctx) -> ToolResult:
    tool = get_tool(name)
    if session.state not in tool.valid_states:
        return ToolResult(error=f"Tool {name!r} not permitted in {session.state.value!r}")
    result = await tool.execute(session, ctx, **args)
    if result.transition_to:
        transition(session, result.transition_to)  # may downgrade to warning
    return result
```

The transition is applied via `sessions.transition` which raises on illegal moves. Illegal transitions get caught and surface as a `warnings` entry inside the tool output — the tool itself succeeded, just the state move didn't.

## Registration

`REGISTRY: dict[str, Tool]`. Populated by **import side effects** at the bottom of `__init__.py`:

```python
from app.agent_tools import (
    complete_document, find_redirect, list_procedures,
    lookup_procedure, propose_widget, set_field, start_procedure,
)  # each module calls register(Tool(...)) at import time
```

## See also

- [[Flow Session State Machine]] — the transitions tools may request
- [[Tool Registry]] — component view
- [[ADR State-Gated Tool Surface]]
