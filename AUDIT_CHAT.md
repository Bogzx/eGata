# eGata Chat Audit — 2026-05-23

Demo: **2026-05-24** (tomorrow). Auditor focus: chat capability (text + voice), tool loop, widget round-trip, persistence.
Stack: Next.js + Zustand frontend, FastAPI + Gemini backend, SSE-over-POST streaming, Gemini Live voice bridge.

Read all paths end-to-end. No code changed. Report below ranks bugs **P0** (demo-blocker), **P1** (must-fix), **P2** (polish). Each has a one-line repro, file:line, root cause, and a surgical fix sketch.

---

## Quick verdict on the 13 suspected bugs

| # | Suspected | Verdict | Notes |
|---|---|---|---|
| 1 | No "thinking" indicator | **REFUTED** | `ChatStream.tsx:126` already renders `showTyping` dots when `sending && !pendingAgent.text.trim()`. The original concern (`pendingAgent.text===""` hides the bubble) IS true, but the typing dots cover that exact state. Real edge case: voice path never sets `sending`, so no dots while voice WS is mid-turn — voice has audio feedback though, so non-issue. |
| 2 | Voice + text echo risk | **REFUTED (in practice)** | `clientContent.turns` via `sendText` (`gemini-live.ts:397-413`) does NOT trigger `inputTranscription` — Gemini Live only emits inputTranscription for audio STT. Risk only if Gemini changes that contract. |
| 3 | Tool-loop delta replacement | **CONFIRMED P0** | Backend resets `accumulated_text=""` each iteration (`agent.py:379`) and emits full text per delta. After tool round-trip, iteration-2 deltas replace iteration-1 text in `pendingAgent`. Final `done` message also contains only iteration-N text — earlier text vanishes. |
| 4 | No abort | **CONFIRMED P1** | `streamChat` accepts `signal` (`sseChat.ts:81`) but `sendText` never passes one. `Composer` disables the input while `sending` (`Composer.tsx:75`) so the user can't even type a follow-up. |
| 5 | Tool errors are silent | **CONFIRMED P1** | `_execute_tool` returns `{"error": ...}` (`agent.py:208-219`); SSE emits as `tool_result.output`; frontend `applyToolResult` (`sessionStore.ts:270`) only inspects success-shaped results. User sees nothing unless the LLM verbalizes the error in its next text. |
| 6 | Partial reply discarded on error | **CONFIRMED P1** | `onError` sets `pendingAgent: null` (`sessionStore.ts:252`) and appends `"Eroare: ..."`. Any partial text the user already read is wiped from view. |
| 7 | Widget→text round-trip | **CONFIRMED P1** | `onWidgetSubmit` → `onSendText(value)` (`ChatSurface.tsx:258-260`). Widget's `targetField` is silently dropped — agent has to re-parse "Da" / "27.04.2026" / "proprietar". Trip-prone and wasted tokens. |
| 8 | Smooth scroll every delta | **CONFIRMED P2** | `endRef.scrollIntoView({behavior:"smooth"})` on every delta (`ChatStream.tsx:122-124`). Compounds with #13's caret flicker. |
| 9 | Unbounded localStorage | **CONFIRMED P2** | `saveMessages` (`sessionStore.ts:39-46`) serializes the whole array each turn. Per-doc growth only — single demo won't blow it up. |
| 10 | `voiceStartedRef` not cleared on reset | **CONFIRMED P2** | `reset()` (`sessionStore.ts:380-395`) doesn't touch it; ref lives in `ChatSurface`. Voice-only users hitting "/" lose auto-start until the component remounts. Mostly an accessibility regression. |
| 11 | SSE drop desync | **REFUTED for server-side history; but user message IS lost** | Server `contents` (`agent.py:360`) is a fresh `list(history)+[...]`, only persisted via `_remember` at terminal points — so dropped streams don't pollute `_conversations`. BUT the dropped user message is never persisted server-side. Next turn the backend's history is missing one user turn. See bug **B-NEW-A** below. |
| 12 | Conv memory process-local, 256-cap | **CONFIRMED P1** | `agent.py:146-155`. Single-worker FastAPI, restart wipes everything. The frontend stores `conversation_id` per-doc in localStorage, so on cache miss the backend just spawns a new conv → context loss mid-demo. |
| 13 | Streaming caret flicker on `<thinking>` leak | **CONFIRMED P2** | Client-side `THINKING_RE` (`ChatStream.tsx:8-13`) requires open+close tags. While streaming, the open tag and reasoning text are visible until the close arrives, then disappear. The backend `strip_thinking` (`text_hygiene.py`) only runs on the final accumulated text, not per delta. |

---

## Additional bugs found

### B-NEW-A — SSE drop loses the user's last turn server-side (P1)
- **Where**: `backend/app/agent.py:350-451`
- **Repro**: open chat, kill backend mid-stream → reload → first new message is treated as the conversation opener; the agent has no memory of what the user just said.
- **Root cause**: `_remember(conv_id, contents)` is called only at the successful `done`/exhausted-cap branches. If the connection drops or Gemini raises mid-loop, the user's message that was prepended at line 360-364 is never persisted into `_conversations`.
- **Fix sketch**: persist the user turn into `_conversations[conv_id]` BEFORE the Gemini call (right after line 365), and on stream failure persist the partial model turn (or revert to pre-turn history). Smallest patch: call `_remember(conv_id, contents)` once right after the user content is appended, then again at each terminal point as today.

### B-NEW-B — `applyToolResult` not awaited; tool results race (P1)
- **Where**: `frontend/lib/sseChat.ts:170` + `frontend/lib/sessionStore.ts:231-234`
- **Repro**: agent emits `set_field(adresa)` then `set_field(telefon)` in one turn → both `tool_result` frames trigger `get().applyToolResult(...)` in parallel; both call `api.getDocument()` concurrently; last-resolved wins. Right-pane `activeField` may flash to the wrong field.
- **Root cause**: `dispatchFrame` calls `h.onToolResult?.()` without `await`. Also `collectedToolCalls.find((c)=>c.name===name)` returns the FIRST call with that name → repeated same-name tool calls all get iteration-1 args (`sessionStore.ts:232`).
- **Fix sketch**: switch `dispatchFrame` to async + await `onToolResult`. Switch the matcher to a FIFO queue keyed by name (shift the matching `arguments` per result) so repeated same-name calls don't collide.

### B-NEW-C — Widgets re-arm on page reload (P1)
- **Where**: `frontend/components/chat/widgets/*Widget.tsx` (local `useState` for `picked`/`done`).
- **Repro**: submit a widget, refresh the page, the same widget message is re-rendered from localStorage with buttons re-enabled. User can submit again → another free-text turn to the agent.
- **Root cause**: widgets carry no "submitted" flag in the persisted `Message`. On reload, React state resets.
- **Fix sketch**: when `onWidgetSubmit` fires, mark the message's widget as submitted in the store (e.g., `widgets[i].submittedValue`) and persist. Render disabled state when `submittedValue !== undefined`.

### B-NEW-D — Text-chat path drops accessibility preferences (P1)
- **Where**: `frontend/lib/sessionStore.ts:210-215` (sendText body); `frontend/lib/sseChat.ts:26-31` accepts `preferences`.
- **Repro**: enable "Explică-mi mai simplu" in the accessibility menu → type a message → the agent answers in default register. The simple-language directive is never sent on the text path. Same for `voice_only` (admittedly less meaningful for text).
- **Root cause**: `sendText` never reads `useAccessibilityPrefs` and never includes `preferences` in the request body. Voice path DOES include it (`ChatSurface.tsx:193,218`).
- **Fix sketch**: have `ChatSurface.onSendText` (or a thin sendText overload) pass `{simple_language, voice_only}` through to `streamChat`. Backend already wires this end-to-end (`agent.py:255-261`).

### B-NEW-E — Agent's initial greeting absent from LLM context (P2)
- **Where**: `frontend/lib/sessionStore.ts:130-152` (`startProcedure` writes a greeting Message but never seeds the LLM history).
- **Repro**: open procedure → agent greeting appears → user says "ok" → LLM has no idea what it greeted with, may repeat itself.
- **Root cause**: greeting is UI-only. `_conversations[conv_id]` starts empty when the first sendText fires.
- **Fix sketch**: either remove the canned greeting and let the LLM produce one, or pass it as a seeded `model` turn on first sendText. Lowest-risk pre-demo: leave it, accept the duplication; flag for post-demo.

### B-NEW-F — Stale `pendingAgent` survives during voice WS reconnects (P2)
- **Where**: `frontend/lib/sessionStore.ts:266` (`finally { set({ sending: false, pendingAgent: null }) }`) protects the text path, but voice path mutates `pendingAgent` via `upsertPendingAgent` and is finalized in `onAgentMessage`. If the WS dies between deltas and the user reloads or starts a new turn, a half-rendered ghost bubble may linger because `useVoiceAgent.stop()` does not call `clearPending()`.
- **Repro**: speak → mid-response, mute network → call `voice.stop()` → ghost bubble persists.
- **Root cause**: `stop()` in `useVoiceAgent.ts:207-217` resets refs but doesn't notify the store to flush pending bubbles.
- **Fix sketch**: have `ChatSurface.stopVoice` call `useSessionStore.getState().clearPending()` (already exposed).

### B-NEW-G — Backend doesn't gate widget options vs. procedure schema (P2)
- **Where**: `backend/app/tools/propose_widget.py:42-51`.
- **Repro**: agent calls `propose_widget(type=choice, options=["proprietar","altceva"], target_field="status_locuinta")` but the schema's allowed options for `status_locuinta` are `["proprietar","chiriaș","găzduit"]`. The widget renders "altceva" but `set_field` later rejects with ValueError → silent error per Bug #5.
- **Root cause**: `propose_widget` doesn't cross-check options against the procedure field's `options`.
- **Fix sketch**: when `target_field` is set, look up the procedure (`ctx.document_id` → `procedure_id`) and assert all `options ⊆ field_spec.options` if defined. Raise ValueError if not.

### B-NEW-H — Voice/text duplicate-turn race when user types while WS is `speaking` (P2)
- **Where**: `frontend/components/chat/ChatSurface.tsx:243-254`.
- **Repro**: voice WS is replying ("speaking") → user types → text is forwarded to voice + appended locally. The voice WS will keep its current turn going (no `interrupted` signal), then process the typed text as a second user turn → ghost overlap of audio + text response.
- **Root cause**: typed text doesn't `flushAgent`/cancel the current playback. `GeminiLiveSession.sendText` does `flushUser/flushAgent` (`gemini-live.ts:403-404`) but the audio is already in `player`.
- **Fix sketch**: on text-into-voice, call `player.flush()` (need to expose via `useVoiceAgent.interrupt()`) and emit a synthetic `onInterrupted` to the store. Smallest patch: tell users not to type while voice is active (UI hint).

### B-NEW-I — 5-iteration cap silently swallows the agent's last text (P2)
- **Where**: `backend/app/agent.py:451-459`.
- **Repro**: force the agent into 5 tool loops (rare in normal flow). Final `done` message is the canned "Am procesat câteva acțiuni. Vrei să continuăm?" — any text the model emitted in iteration 5 is discarded.
- **Root cause**: when the loop exits without `return`, we send a generic fallback, ignoring whatever text was just emitted.
- **Fix sketch**: track `last_accumulated_text` across iterations; on cap exhaustion, emit it (or a strip_thinking'd version) instead of the canned line.

### B-NEW-J — Tool dispatch errors over voice not surfaced to UI (P2)
- **Where**: `frontend/lib/gemini-live.ts:354` + `useVoiceAgent.ts:190-194`.
- **Repro**: tool returns HTTP 400 → `dispatchTool` throws → `handleMessage` catches, sets `output={error: msg}`, sends to Gemini → BUT `userToolHandlerRef.current(name, {...args, _result: result})` (line 197-200) is in the SUCCESS branch and never fires on error → frontend store has zero knowledge. The model may or may not verbalize the error.
- **Fix sketch**: in the catch branch, still call `userToolHandlerRef.current(name, {...args, _error: msg})` so `applyToolResult` (or a sibling error handler) can surface a Romanian message.

### B-NEW-K — Repeated `lookup_procedure` mid-flow re-opens scenario plan (P2)
- **Where**: `frontend/lib/sessionStore.ts:296-307`.
- **Repro**: user is filling fields in a doc → asks something tangential → agent calls `lookup_procedure` → if hit returns a scenario_plan AND there's no `activeDocId`, it `pushPath(/p/...)` away from the current doc.
- **Root cause**: branch only checks `!activeDocId` — but during a doc-fill flow `activeDocId` is set, so the guard does work. However, if the user is on a scenario plan WITHOUT activeDocId and re-queries, the path changes unexpectedly.
- **Fix sketch**: also gate on `rightPane.kind !== "plan"` to avoid bouncing the user.

---

## Prioritized fix list

### P0 (demo-blocker)
1. **B-3: Tool-loop delta replacement** — without this, every multi-tool turn drops the assistant's preamble text. Pre-demo this is the #1 visual bug.

### P1 (must-fix before demo)
2. **B-4: No abort** — runaway turns kill demo recovery. Even a 5s `setTimeout(controller.abort, 30_000)` is a win.
3. **B-5: Silent tool errors** — paired with B-6, will eat user-facing failures in the worst possible way (on stage).
4. **B-6: Partial reply discarded on error** — preserve what the user already saw.
5. **B-7: Widget→text round-trip** — call `set_field` directly from the frontend on widget submit; bypass the LLM for the trivial "Da"/"Nu"/date case. Saves ~one tool round-trip per question and removes a re-parse failure mode.
6. **B-12: Conv memory process-local, 256-cap** — ensure single-worker demo run and add a "restart guard" log.
7. **B-NEW-A: SSE drop loses user's last turn** — persist user turn immediately.
8. **B-NEW-B: tool results race / repeated-name args** — sequential await + FIFO match.
9. **B-NEW-C: Widgets re-arm on reload** — persist submitted state on the Message.
10. **B-NEW-D: Text chat drops `preferences`** — wire through `simple_language` and `voice_only`.

### P2 (polish)
11. **B-1 (mostly OK)**: no action; confirm typing dots render.
12. **B-8: Smooth scroll every delta** — throttle to `behavior:"auto"` during streaming, smooth only on done.
13. **B-9: Unbounded localStorage** — trim to last 200 messages on save.
14. **B-10: `voiceStartedRef`** — reset inside `reset()` via a `useEffect` watching `rightPane.kind==="welcome"`.
15. **B-13: Thinking flicker** — keep the pendingAgent text but render through a guard that drops everything from an unclosed `<thinking>` to end-of-string.
16. **B-NEW-E: greeting not in LLM history** — defer.
17. **B-NEW-F: ghost pending bubble on voice stop** — call `clearPending()` in `stopVoice`.
18. **B-NEW-G: widget options vs schema** — defer; covered indirectly by B-7 if widgets call `set_field` directly.
19. **B-NEW-H: voice/text race while speaking** — quick UI hint "Microfon activ" greys out composer.
20. **B-NEW-I: 5-iter cap eats last text** — defer.
21. **B-NEW-J: voice tool errors not in UI** — defer.
22. **B-NEW-K: lookup_procedure mid-flow** — defer.

---

## Fix sketches (surgical, not full diffs)

### B-3 (P0) — Tool-loop delta replacement
- **File**: `backend/app/agent.py` (`_stream_agent_turn` lines 378-449) OR `frontend/lib/sessionStore.ts:223-227`.
- **Backend option** (preferred): track `total_text_so_far = ""` outside the iteration loop; each iteration adds `accumulated_text` to a running prefix. Emit `delta` with `total_text_so_far + accumulated_text`. The final `done.message` uses the full concatenation.
- **Frontend option**: in `onDelta`, append delta as `pendingAgent.text = bubblePrefix + full` where `bubblePrefix` is captured on each `tool_result` boundary as the current `pendingAgent.text`. Less surgical because frontend doesn't know iteration boundaries — derive from the fact that `onToolResult` fires between iterations.
- **Pick backend**. Smallest change: add a turn-scoped `transcript_so_far` variable.

### B-4 (P1) — No abort
- **File**: `frontend/lib/sessionStore.ts:192`, `frontend/components/chat/ChatSurface.tsx`, `frontend/components/chat/Composer.tsx`.
- **Sketch**: store an `AbortController` on the slice (`currentAbortController`). `sendText` creates one, passes `signal` to `streamChat`. Composer exposes a stop button when `sending===true`. On stop: `controller.abort()`. `streamChat`'s fetch will throw `AbortError`; the existing `catch`/`finally` in `sendText` already cleans pendingAgent.
- Add: 30s `setTimeout` server-side timeout as a safety net (FastAPI `await asyncio.wait_for(stream)`).

### B-5 (P1) — Silent tool errors
- **File**: `frontend/lib/sessionStore.ts` (`applyToolResult`).
- **Sketch**: inspect `_result` for `{error}` shape OR for HTTP-style failure. If present, `appendMessage({role:"system", text: "Eroare la pasul: <name> — <msg>"})`. Use Romanian text per constraint.
- Alternative: a dedicated `onToolError` SSE frame from backend. Bigger change, defer.

### B-6 (P1) — Partial reply discarded on error
- **File**: `frontend/lib/sessionStore.ts:250-258` (onError) and line 266 (finally).
- **Sketch**: in `onError`, if `pendingAgent.text` is non-empty, `appendMessage({role:"agent", text: pendingAgent.text})` BEFORE the system-error bubble. Then clear pending. Adjust the `finally` to not double-clear (it already sets `pendingAgent: null`, fine).

### B-7 (P1) — Widget→text round-trip
- **File**: `frontend/components/chat/ChatSurface.tsx:258-260`.
- **Sketch**: in `onWidgetSubmit`, check `_spec.type` and `_spec.targetField`. If type is `choice` or `date` AND `targetField` exists AND `activeDocId` is set: call `api.patchFields(docId, {[targetField]: value})` directly, then locally append the user bubble `"<value>"` AND call `applyToolResult("set_field", {name: targetField, value}, fresh)` so the right-pane updates. Skip the LLM entirely for this turn. Only forward to `onSendText(value)` for `confirm` (where the model has more to decide than just "Da"/"Nu") OR when no `targetField` is set.
- **Bonus**: include `"set via widget"` as a system bubble so the LLM sees the field was set when the user types next.

### B-12 (P1) — Conv memory cap
- **File**: `backend/app/agent.py:146-155`.
- **Sketch**: bump `_MAX_CONVERSATIONS=1024`; log a WARNING when eviction fires. Quick pre-demo win. Persistent store (Redis/SQLite) is a post-hackathon refactor.
- **Demo guard**: log `len(_conversations)` after each remember; alert at 80%.

### B-NEW-A (P1) — SSE drop loses user's last turn
- **File**: `backend/app/agent.py:360-365`.
- **Sketch**: right after building `contents` with the user message, call `_remember(conv_id, contents)` ONCE. Then continue. If the stream completes normally, `_remember` is called again at the bottom — idempotent.
- Risk: if Gemini fails on the first attempt and we retry, the duplicated user message is benign.

### B-NEW-B (P1) — Tool result race
- **File**: `frontend/lib/sseChat.ts:144` (make `dispatchFrame` async); `frontend/lib/sseChat.ts:122-130` (await inside the loop).
- **Sketch**: change to `async function dispatchFrame` and `await dispatchFrame(f, handlers)` inside the read loop. For the FIFO match, in `sessionStore.ts:228-234` replace `find` with `shift()` against a per-stream array.

### B-NEW-C (P1) — Widgets re-arm on reload
- **File**: `frontend/lib/types.ts:225-244` (add `submittedValue?: string` to each WidgetSpec); `frontend/lib/sessionStore.ts` (new `markWidgetSubmitted(messageId, widgetId, value)` action that mutates and persists); `frontend/components/chat/ChatSurface.tsx:258-260` (call it); widget components read `spec.submittedValue` for `disabled` state.

### B-NEW-D (P1) — Text chat drops preferences
- **File**: `frontend/components/chat/ChatSurface.tsx` (`onSendText`) and `frontend/lib/sessionStore.ts:192` (sendText body).
- **Sketch**: read `simpleLanguage` + `voiceOnly` from `useAccessibilityPrefs`. Either pass via a 2nd arg into `sendText` or merge into the existing `opts`. Wire to `streamChat({..., preferences})`.

---

## Open questions (need user's call before fixes start)

1. **Widget round-trip philosophy (B-7).** Should widget submissions bypass the LLM and call `set_field` directly? Pros: faster, no re-parse. Cons: the LLM doesn't observe the user's choice in its next turn (it'd see the doc state via context preamble only). Recommend YES for `choice`/`date`, NO for `confirm` (semantics vary by question).
2. **Abort UX (B-4).** Should the user be able to abort a turn? If yes — a stop button or a 30s auto-abort? Recommend BOTH.
3. **Greeting in LLM history (B-NEW-E).** Keep the canned greeting (cheap, sometimes redundant with LLM's own first turn) or seed it as a `model` turn into `_conversations`? Recommend KEEP for now, document.
4. **Server-side persistence (B-12).** Are we OK losing all conversation state on backend restart? If yes, current cap is fine. If no, move to Redis/SQLite — out of scope for tomorrow.
5. **Romanian system bubble copy for tool errors (B-5).** Generic "Eroare la pas" vs. tool-specific? Recommend `"A apărut o eroare la {tool_name}. Te rog reformulează sau încearcă din nou."` — keep it short, Romanian.
6. **Voice + text simultaneity (B-NEW-H).** Should the composer be disabled while voice WS is `speaking`? Recommend YES with a visible mic-on chip on the textarea.
7. **Tool-result error frame (B-5).** Should backend emit a distinct `tool_error` SSE frame, or keep stuffing `{error: ...}` in `tool_result`? Recommend latter (zero-effort).

---

## Timeboxes — assume demo is **2026-05-24 (tomorrow)**

### Next 2 hours (do this before sleep tonight)
**Top 3 P0/P1 fixes that compound demo confidence:**
1. **B-3 (P0)** — backend `_stream_agent_turn` accumulates `transcript_so_far` across iterations. ~15 lines, low risk.
2. **B-NEW-D (P1)** — pipe accessibility preferences through `sendText` → `streamChat`. ~10 lines.
3. **B-6 (P1)** — preserve partial reply on error. ~5 lines in `onError`.

Stretch goal if these go fast: **B-NEW-C** (widgets re-arm) — adds a `submittedValue` field on WidgetSpec + a store action. ~30 lines.

### 1 day (rest of today + tomorrow morning)
4. **B-7 (P1)** — widget direct-to-`set_field`. Most impactful for the demo flow.
5. **B-NEW-A (P1)** — `_remember` early in `_stream_agent_turn`.
6. **B-NEW-B (P1)** — async dispatchFrame + FIFO matcher.
7. **B-5 (P1)** — surface tool errors as Romanian system bubbles.
8. **B-4 (P1)** — abort button + 30s server timeout.
9. **B-13 (P2)** — caret flicker. Smaller is bigger: drop everything after an unmatched `<thinking>` open tag.
10. **B-8 (P2)** — non-smooth scroll during streaming.

### 1 week (post-demo, IF it survives)
11. **B-12** — Redis-backed `_conversations`.
12. **B-NEW-E** — seed LLM history with greeting.
13. **B-NEW-F / B-NEW-J** — voice cleanup paths.
14. **B-NEW-G** — propose_widget schema check.
15. **B-9** — message trim policy.
16. **B-10** — voice auto-start reset.
17. **B-NEW-H** — voice/text simultaneity disable.
18. **B-NEW-I** — 5-iter cap message preservation.
19. **B-NEW-K** — lookup_procedure mid-flow gating.

---

## Brutal cuts (what I'd NOT touch before tomorrow)

- Anything inside `gemini-live.ts` that touches the WS handshake. Last commit (`ffbb833 fix(voice): revert risky Live setup fields`) shows the team already paid that bill. Resist.
- Don't change `strip_thinking` regexes. They're tuned to known leaks; one bad change = thinking gets through on stage.
- Don't move conversation storage to Redis. Demo runs single-process; cap is fine if you log to alert.
- Don't refactor the `pendingAgent`/`pendingUser` model. Surgical patches only.

---

## What's working well (don't touch)
- Auth → procedure pick → doc create → chat path is solid in the static read.
- The conversation-id transparent refresh (`onConversation` callback) is a nice fallback for B-12.
- Backend `strip_thinking` is double-defended (server + client).
- Pydantic models + tool registry + JWT-gated /tools dispatch are tidy.
- Romanian copy is consistent.

End of audit.
