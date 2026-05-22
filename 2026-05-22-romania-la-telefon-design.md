# România la Telefon — Cluj Hackathon 2026 Design Spec

**Date:** 2026-05-22
**Event:** Cluj Hackathon 2026 — *Digital Romania / NoQueue.Done*
**Venue / dates:** Bosch Engineering Center, Cluj-Napoca · May 22–24, 2026 (48h)
**Target tracks:** AI Civic Agents (special) · Most Brutal Fix · Killed the Queue Award · Grand Prize
**Team:** 4 — Backend (B), Voice/AI (V), Frontend/Design (F), PM/Domain/Pitch (P)

---

## 1. Context

Cluj Hackathon 2026's theme is *Digital Romania*: rebuild every citizen↔state interaction so it is fast, simple, and 100% digital. The official design principles judges will evaluate against:

- **Citizen-centric** — start from citizen needs, not institutional process
- **Single Login** — one account for all public services
- **Proactive** — the state notifies the citizen, not vice versa
- **Universally Accessible** — works for everyone regardless of ability
- **Feasible Today** — tech that exists now, no sci-fi
- **Human Language** — no bureaucratic jargon

Hard constraint: **working demo required, no PowerPoint**. Demos that fail live, lose. Demos that survive an unscripted juror question, win.

Sanctioned tools: **Lovable, Cursor, n8n, ElevenLabs, Anthropic Claude**.

## 2. The insight

Every other team will interpret "Digital Romania" as a web or mobile app with a chatbot. That interpretation excludes the population that suffers most from the broken state-citizen interface: **5M+ pensioners, rural Romanians, and anyone uncomfortable with apps**. They all have one thing in common: **they own a phone that dials**.

The official AI Civic Agents track says *"the future is conversational."* The literal interpretation — a chatbot — is crowded. The true interpretation — a real voice on a real phone line — is empty.

## 3. Product positioning

**Name:** România la Telefon ("Romania, on the line")

**One-line pitch:** *You don't need an app. You don't need Wi-Fi. You don't need to know how a PDF works. You call one number, and Romania answers.*

**Why this aligns with three prize lanes simultaneously:**

- **Grand Prize** — Universal access + a turnkey CX layer for any ministry partner + analytics on real citizen needs. An institutional partner can deploy on Monday.
- **Most Brutal Fix** — Fixes the access gap for the population the digital state has literally never reached.
- **Killed the Queue** — A 75-year-old reports a pothole in 90 seconds from her kitchen. The queue is dead.

**The secret weapon — institutional partner hook:** every call generates anonymized signal. The ministry dashboard surfaces *"47 callers asked about pediatricians in Cluj this week, 35 couldn't find a slot — you have a Tuesday-morning shortage."* The product is simultaneously **citizen access** and **free CX research for the state**. That is what gets a ministry to sign, not just admire.

## 4. Goals & non-goals

### Goals (in scope for 48h)

- A single Romanian phone number that any Romanian can call
- An AI agent answering in fluent, warm Romanian via ElevenLabs
- **Four** end-to-end use cases working live in the demo:
  1. **Pension status & simulator** ("când ies la pensie?")
  2. **Book a doctor / medical appointment** ("vreau la doctor")
  3. **Tax / ANAF status & deadlines** ("cât îi datorez statului?")
  4. **File a city complaint** ("am o groapă în fața blocului")
- A live jury-facing dashboard showing calls + transcripts + counters
- A ministry-facing dashboard view showing aggregate citizen needs
- A landing page with the phone number prominent
- SMS confirmations for booked appointments and filed reports
- A 5-minute demo that survives an unscripted juror question

### Non-goals (explicitly out of scope)

- Real integration with ANAF, CNAS, ANCPI, or any actual government API (mocked)
- Real CNP-based auth (caller ID → whitelisted demo profiles instead)
- Native mobile apps (web is enough; phone is the real channel)
- Streaming voice / sub-second latency (turn-based is reliable and good enough)
- WhatsApp channel (stretch goal only; explicitly cut if not done by Saturday 22:00)
- More than 4 use cases (extensibility is shown architecturally, not built)

## 5. Architecture

```
                  ┌────────────────────────────────────────────┐
                  │              CITIZEN CHANNELS              │
   📞 Phone call ──┤  Twilio Voice  ──┐                        │
   💬 WhatsApp* ──┤  Twilio WA      ──┼─► Channel Adapter      │
   🌐 Web chat  ──┤  Lovable widget ──┘   (normalize input)    │
                  └─────────────────────┬──────────────────────┘
                                        │ text turn
                                        ▼
                  ┌────────────────────────────────────────────┐
                  │   CONVERSATION CORE  (Node/Express)        │
                  │   • Claude Sonnet 4.6 with tool use        │
                  │   • System prompt in Romanian              │
                  │   • Caller ID → user profile (mocked CNP)  │
                  │   • Per-call conversation memory           │
                  └─────────────────────┬──────────────────────┘
                                        │ tool call
                                        ▼
                  ┌────────────────────────────────────────────┐
                  │            n8n ORCHESTRATION                │
                  │  ┌─────────────┐ ┌─────────────┐           │
                  │  │ get_pension │ │ book_doctor │           │
                  │  ├─────────────┤ ├─────────────┤           │
                  │  │ anaf_status │ │file_complaint│          │
                  │  └─────────────┘ └─────────────┘           │
                  │  Each = workflow → mocked govt API + SMS    │
                  └─────────────────────┬──────────────────────┘
                                        ▼
                  ┌────────────────────────────────────────────┐
                  │            VOICE OUT (ElevenLabs RO)        │
                  │   Stream TTS back to Twilio call           │
                  └────────────────────────────────────────────┘

                  ┌────────────────────────────────────────────┐
                  │       JURY-FACING DASHBOARD (Lovable)       │
                  │  • Live call ticker + transcript           │
                  │  • Counter: "Queues killed today: 312"     │
                  │  • Ministry view: top citizen needs        │
                  └────────────────────────────────────────────┘

   * WhatsApp = stretch goal only
```

### 5.1 Key architectural decisions

| Decision | Pick | Why |
|---|---|---|
| Voice loop style | **Turn-based** (record → STT → Claude → TTS → play) | Reliable on stage; streaming feels magical but breaks visibly on jitter. Demo Day > magic. |
| Brain | **Single Claude agent with 4 tools** | Anthropic is stack-sanctioned. Tool use is mature. One prompt to tune. No router complexity. |
| Orchestration | **n8n workflows per tool** | Visual, judge-friendly, stack-sanctioned. Each tool = one workflow + a JSON mock backend. |
| Auth | **Caller ID → whitelisted demo CNPs** | Voice-typing 13-digit CNPs is friction. Stage demo dials from pre-seeded phones. Real-world prod = OTP later. |
| Web | **Lovable for landing + dashboard** | Stack-sanctioned, fastest path to a beautiful site. Same Claude agent exposed via chat widget. |
| Voice | **ElevenLabs Romanian, warm female persona** | Stack-sanctioned. Voice should sound like a kind 40-year-old; that builds trust. |
| Channels at demo | **Phone primary, web chat secondary, WhatsApp stretch** | Two rock-solid channels beat three flaky ones. |

### 5.2 Alternative considered and rejected

**ElevenLabs Conversational AI (full streaming)** — lower latency, more "wow," but tool use is less mature there, and any network hiccup ruins the demo. Defer to post-Cluj v2 if a ministry partners with us.

## 6. Components & interfaces

### 6.1 Channel adapter

**Purpose:** normalize voice/text/WhatsApp input into a unified `Turn` object for the conversation core.

**Input:** Twilio webhook payloads, web chat WS messages.
**Output:**
```ts
type Turn = {
  conversationId: string;   // Twilio CallSid or web session
  userId: string;           // resolved from caller ID
  channel: 'voice' | 'web' | 'whatsapp';
  text: string;             // STT output for voice
  meta: { from?: string; locationHint?: string };
};
```

### 6.2 Conversation core

**Purpose:** drive the Claude turn loop with tool use.

**Responsibilities:**
- Look up user profile from `userId` and inject into system prompt
- Maintain per-conversation message history (in-memory map, TTL 30 min)
- Call Claude Sonnet 4.6 with the 4 tools registered
- Loop on tool-use responses until Claude returns plain text
- Emit `final_text` back to channel adapter for TTS/display

**System prompt outline (Romanian):**
- Identity: warm civic helper, plain Romanian, never patronizing
- Hard rules: never invent data; if a tool returns nothing, say so; decline political/medical/legal advice; redirect to a human if user asks
- Style: short sentences, no jargon, address user by name from profile

### 6.3 Tools (Claude tool definitions)

Each tool is an HTTP call to a single n8n webhook. Schema:

```ts
get_pension(userId): { yearsContributed, projectedRetirementDate, estimatedMonthlyAmount, confidence }
book_doctor(userId, specialty, preferredWindow): { appointmentId, datetime, clinic, smsSent }
anaf_status(userId): { balanceOwed, deadlines: [{type, amount, dueDate}], paymentLinkSent }
file_complaint(userId, category, description, locationHint): { ticketId, assignedDepartment, etaResponse }
```

**Invariant:** every tool returns a `confidence` field (`high | low`). Claude is prompted to say *"nu sunt complet sigur"* when confidence is low.

### 6.4 Mock data store

A single JSON file per use case, seeded with **6 fictional citizens** covering the demo personas:

- Maria Popescu (65, pensioner, Cluj) — pension demo
- Ion Ionescu (42, employed, Bucharest) — ANAF demo
- Andreea Pop (33, mother of 2, Cluj) — doctor booking demo
- Vasile Munteanu (58, rural, Sălaj) — pothole demo
- Plus 2 backup profiles for unscripted juror calls

### 6.5 Dashboards

**Citizen-facing landing page:**
- Hero: huge phone number, one line of copy, one CTA (call now)
- Section: "What you can ask" (the 4 use cases as cards)
- Section: live ticker (anonymized)

**Jury dashboard (the demo screen):**
- Real-time call list, status, transcript
- Counters: queues killed, hours saved, calls answered
- Map of Romania with anonymized call origins lighting up

**Ministry dashboard view (toggle on jury screen):**
- Top citizen pain points this week
- Sentiment per topic
- Top unanswered questions (= product roadmap for the ministry)

## 7. Demo Day choreography (5 minutes)

| Time | Beat |
|---|---|
| 0:00–0:30 | Hook: *"Raise your hand if your grandmother has ever used ANAF online."* Reveal the live number on the LED. |
| 0:30–1:30 | Live call from stage. Bunica script: pension query → SMS confirmation lands on visible phone. |
| 1:30–2:30 | **Hand the phone to a juror.** Let them ask anything. Off-script is the win. |
| 2:30–3:30 | Switch to jury dashboard — three parallel calls (teammates from floor) demonstrate doctor / ANAF / pothole. |
| 3:30–4:30 | Toggle ministry view. Tell the partner story: "this is what a ministry sees — anonymized, GDPR-safe, deployable Monday." |
| 4:30–5:00 | Close: *"Every tool is stack-sanctioned. Nothing is sci-fi. The number stays live for 48 hours after this demo — sunați."* |

**Demo redundancy:** a backup video of the bunica call recorded Sunday morning. A teammate on the floor ready to dial in if the juror declines.

## 8. 48-hour build plan

### Friday 18:00–02:00 (8h) — one call working end-to-end with one tool

| Time | B | V | F | P |
|---|---|---|---|---|
| 18–19 | Repo + Express + Anthropic SDK | Twilio number + webhook + hardcoded TwiML | Lovable landing + huge number | Mentor sync; sharpen 4 Romanian scripts |
| 19–21 | Claude tool loop; `get_pension` mock | STT + ElevenLabs TTS round-trip | Dashboard wireframe + fake ticker | Bunica script word-for-word + fallback lines |
| 21–23 | End-to-end pension call works | Same | Site live at public URL | 6 fictional citizens with full data |
| 23–02 | Add `book_doctor` + n8n workflow + SMS | Tune voice persona | WebSocket transcript stream | Sleep |

**Friday exit gate (02:00):** one teammate calls, asks for pension, gets correct voice answer. If broken, fall back to Twilio default TTS overnight.

### Saturday 02:00–24:00 (22h) — all 4 use cases + dashboard real

- 02–09: B+V sleep. F polishes dashboard.
- 09–13: Add `anaf_status` + `file_complaint` (~2h each).
- 13–17: **Bug-bash #1** — team takes turns calling, fixes prompts for weird Romanian phrasings.
- 17–20: Ministry dashboard view. **This wins Grand Prize.**
- 20–22: SMS confirmations across all 4 flows. Geo-tagging for complaints.
- 22–24: **Pitch rehearsal #1** — full 5-minute run, timed. Cut anything over 5:00.

**Saturday exit gate (24:00):** 4 tools working end-to-end, dashboard ticks, pitch fits in 5 minutes. WhatsApp dropped if not done.

### Sunday 00:00–demo — polish + redundancy + rehearse

- 00–07: Two sleep, two on **bug-bash #2** (off-script juror questions).
- 07–10: Final rehearsals — P delivers 4 times to teammates + 2 strangers.
- 10–12: Record backup video. Pre-stage a floor-teammate dial-in.
- 12–demo: **Code freeze.** No commits within 2h of pitch. Eat. Hydrate.

### Code-freeze rule

Any commit after **Saturday 22:00** requires 2-person review. Most demos die from a 04:00 Sunday "one more thing."

## 9. Risk register

| Risk | Mitigation |
|---|---|
| Twilio doesn't issue RO number in time | Buy Friday morning. If RO is blocked, use US/UK — still works for demo. |
| ElevenLabs RO voice sounds robotic | A/B 3 voices Friday night; lock one. |
| Claude invents fake pension data on stage | System prompt forbids invention; every tool returns `confidence`; agent says *"nu sunt sigur"* on low. |
| Stage Wi-Fi dies | Phone uses cellular. Backend is cloud-hosted. Backup video as last resort. |
| Juror asks something offensive/political | Prompt: politely decline political/medical-diagnostic/legal-advice queries; redirect to human. |
| Demo runs over 5:00 | Rehearse to 4:30. The 30s you cut is fluff, not features. |
| Team conflict on scope at 02:00 | This spec is the lock. Re-open only with full-team agreement. |

## 10. Success criteria

**Minimum (we shipped):** all 4 use cases work end-to-end via phone, demo is delivered live, jury dashboard is real.

**Target (we win something):** above + ministry view is real + juror's unscripted call is answered gracefully + at least one institutional partner asks to keep the number live post-event.

**Maximum (Grand Prize):** above + the demo closes with a partner publicly committing to a pilot in the Q&A. The phone keeps ringing after the event.

---

## Appendix A — Demo script (Romanian, full)

*To be drafted Friday 18:00–21:00 by P with mentor input. Lives in `docs/demo-script.md`.*

## Appendix B — Mock citizen profiles

*To be drafted Friday 21:00–23:00 by P. Lives in `data/citizens.json`.*

## Appendix C — Pitch deck (backup only)

Per Demo Day rules, no slides on stage. Backup deck (max 5 slides) only for sponsor handoff conversations post-demo.
