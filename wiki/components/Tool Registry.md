---
type: component
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Tool Registry

The `REGISTRY: dict[str, Tool]` in [[agent_tools]]. Populated at import time by side effect — each tool file calls `register(Tool(...))`.

## Tool shape

```python
@dataclass
class Tool:
    name: str
    description: str            # Romanian — shown to the model
    parameters: dict            # JSON-schema-ish for Gemini function_declarations
    valid_states: set[SessionState]
    execute: Callable[..., Awaitable[ToolResult]]
```

`function_declaration()` returns `{name, description, parameters}` — exactly the shape Gemini's `Tool(function_declarations=[...])` expects.

## Why import side-effects

`from app.agent_tools import lookup_procedure, ...` (at the bottom of `__init__.py`) triggers the registers. The top-level `dispatch / get_tool / permitted_tools` references the populated dict.

This pattern keeps each tool self-contained: file = name + params + executor + valid_states + register call. New tool = new file + add to the import list.

## Calling

- Text path: `_function_declarations_for_state(state)` filters the registry to the state-permitted set; `dispatch(session, name, args, ctx)` runs them.
- Voice path: all 7 declarations at connect; dispatcher refuses out-of-state. See [[ADR State-Gated Tool Surface]].

## Adding a new tool

1. Create `app/agent_tools/my_tool.py`.
2. Define `async def execute(session, ctx, **args) -> ToolResult`.
3. Call `register(Tool(name=..., description=..., parameters=..., valid_states={...}, execute=execute))`.
4. Add the module to the import list at the bottom of `app/agent_tools/__init__.py`.
5. Re-run the agent — that's it.

## See also

- [[agent_tools]]
- [[Flow Session State Machine]]
