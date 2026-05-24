"use client";

import { create } from "zustand";
import { api } from "./api";
import { streamChat, type StreamChatToolCall } from "./sseChat";
import type {
  Citizen,
  Document,
  FrontendEvent,
  LookupMatch,
  Message,
  Procedure,
  ScenarioPlan,
  SessionSnapshot,
  VoiceStatus,
  WidgetSpec,
} from "./types";

const LS_MSG_KEY = (docId: string) => `egata:session:${docId}`;
const LS_CONV_KEY = (docId: string) => `egata:conv:${docId}`;

function makeId(): string {
  return Math.random().toString(36).slice(2, 11);
}

function loadMessages(docId: string): Message[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(LS_MSG_KEY(docId));
    return raw ? (JSON.parse(raw) as Message[]) : [];
  } catch {
    return [];
  }
}

function saveMessages(docId: string, msgs: Message[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(LS_MSG_KEY(docId), JSON.stringify(msgs));
  } catch {
    /* quota or disabled */
  }
}

function loadConvId(docId: string): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(LS_CONV_KEY(docId));
}

function saveConvId(docId: string, id: string | null) {
  if (typeof window === "undefined") return;
  if (id) localStorage.setItem(LS_CONV_KEY(docId), id);
  else localStorage.removeItem(LS_CONV_KEY(docId));
}

// Navigation indirection: defaults to window.history.pushState (no React
// dependency, works in tests), but the React tree replaces it with the
// Next.js router via setNavigate() so the route tree actually re-renders
// instead of just the URL bar changing. Without that, useParams() stays
// stale after a store-driven navigation and the popstate handler is the
// only thing that ever re-syncs.
type Navigate = (path: string) => void;

let _navigate: Navigate = (path) => {
  if (typeof window === "undefined") return;
  if (window.location.pathname !== path) {
    window.history.pushState(null, "", path);
  }
};

export function setNavigate(fn: Navigate): void {
  _navigate = fn;
}

function pushPath(path: string) {
  if (typeof window !== "undefined" && window.location.pathname === path) return;
  _navigate(path);
}

export interface SessionState {
  // Identity + working set
  citizen: Citizen | null;
  activeDocId: string | null;
  document: Document | null;
  procedure: Procedure | null;
  conversationId: string | null;
  messages: Message[];
  voiceStatus: VoiceStatus;
  /** True when the microphone is actively recording. Orthogonal to
   * voiceStatus: text-only sessions also open the unified Live WS
   * (status becomes "listening") but the mic stays off. */
  micOn: boolean;
  drawerOpen: boolean;
  profileMenuOpen: boolean;
  sending: boolean;
  scenarioPlan: ScenarioPlan | null;
  lookupMatches: LookupMatch[];

  // The backend session — single source of truth for agent state.
  session: SessionSnapshot | null;

  // Actions
  hydrateCitizen(): Promise<void>;
  startProcedure(procedureId: string): Promise<void>;
  loadDocument(docId: string): Promise<void>;
  openScenarioPlan(scenarioId: string): Promise<void>;
  sendText(text: string, opts?: { viaWs?: boolean }): Promise<void>;
  /** Abort the in-flight chat turn. Safe to call when no turn is running. */
  abortCurrentTurn(): void;
  /** Submit a previously-proposed widget's answer.
   *
   * Bypasses the model for the trivial "Da/Nu/option/date" case: the backend
   * resolves the pending widget, runs set_field if appropriate, persists,
   * and returns a fresh snapshot. The widget's spec is marked
   * `submittedValue` so reloads don't re-arm it. */
  submitWidget(widgetSpec: WidgetSpec, value: string): Promise<void>;
  appendMessage(m: Message): void;

  /** Live messages stream their content in-place — used by both text
   * streaming and voice transcripts so the two paths feel identical. */
  beginLiveMessage(role: "user" | "agent"): string;
  updateLiveMessage(id: string, text: string): void;
  finalizeLiveMessage(id: string, text: string): void;

  /** Backend session snapshot subscription. */
  setSession(snapshot: SessionSnapshot): void;

  /** Structured frontend events emitted by tools (document_opened,
   * widget_proposed, field_updated, document_delivered, lookup_returned,
   * redirect). The store is the single dispatcher for UI side-effects. */
  handleFrontendEvent(event: FrontendEvent): Promise<void>;

  setVoiceStatus(s: VoiceStatus): void;
  setMicOn(on: boolean): void;
  openDrawer(): void;
  closeDrawer(): void;
  toggleProfileMenu(): void;
  closeProfileMenu(): void;
  reset(): void;
}

// Out-of-band ref so we don't try to store the AbortController in zustand
// state (it's not serializable and triggers needless re-renders).
let _currentAbort: AbortController | null = null;

// Helper: optimistically toggle a widget's submittedValue in the messages
// array (and persist). Passing `null` rolls back a prior submission on
// error. Shared between submitWidget's two branches and its catch block.
function _markWidgetSubmitted(
  get: () => SessionState,
  set: (partial: Partial<SessionState>) => void,
  activeDocId: string | null,
  widgetId: string,
  value: string | null,
) {
  const messages = get().messages;
  const next = messages.map((m) => {
    if (m.role !== "agent" || !m.widgets) return m;
    const updated = m.widgets.map((w) =>
      w.widgetId === widgetId ? { ...w, submittedValue: value } : w,
    );
    return { ...m, widgets: updated };
  });
  set({ messages: next });
  if (activeDocId) saveMessages(activeDocId, next);
}

export const useSessionStore = create<SessionState>((set, get) => ({
  citizen: null,
  activeDocId: null,
  document: null,
  procedure: null,
  conversationId: null,
  messages: [],
  voiceStatus: "idle",
  micOn: false,
  drawerOpen: false,
  profileMenuOpen: false,
  sending: false,
  scenarioPlan: null,
  lookupMatches: [],
  session: null,

  setSession(snapshot) {
    const current = get().session;
    // Drop stale snapshots if seq goes backwards — defense against
    // out-of-order delivery on reconnects or future buffered transports.
    if (
      current &&
      typeof current.seq === "number" &&
      typeof snapshot.seq === "number" &&
      snapshot.seq < current.seq &&
      current.id === snapshot.id
    ) {
      return;
    }
    set({ session: snapshot });
  },

  async handleFrontendEvent(event) {
    switch (event.type) {
      case "document_opened": {
        // Carry the in-flight conversation forward when the AGENT opens a
        // brand-new doc via start_procedure (vs. the user explicitly clicking
        // a procedure card, which goes through startProcedure() and already
        // carries state). Without this, loadDocument reads LS_CONV_KEY /
        // LS_MSG_KEY for a freshly-created docId, finds nothing, and resets
        // the in-memory store — so the next chat turn ships with conv=null
        // and the backend spawns a brand-new session, losing the entire
        // prior conversation. Persist current state to the new doc's LS keys
        // before loadDocument reads them.
        const { conversationId, messages, activeDocId } = get();
        if (activeDocId !== event.document_id) {
          if (conversationId) saveConvId(event.document_id, conversationId);
          if (messages.length > 0) saveMessages(event.document_id, messages);
        }
        try {
          await get().loadDocument(event.document_id);
        } catch (err) {
          const detail = err instanceof Error ? err.message : "necunoscută";
          get().appendMessage({
            id: makeId(),
            role: "system",
            text: `Nu am putut deschide documentul: ${detail}`,
          });
        }
        return;
      }
      case "widget_proposed": {
        const spec: WidgetSpec =
          event.widget_type === "choice"
            ? {
                type: "choice",
                question: event.question,
                options: event.options,
                targetField: event.target_field ?? "",
                widgetId: event.widget_id,
              }
            : event.widget_type === "date"
              ? {
                  type: "date",
                  question: event.question,
                  targetField: event.target_field ?? "",
                  widgetId: event.widget_id,
                }
              : {
                  type: "confirm",
                  question: event.question,
                  widgetId: event.widget_id,
                };
        const messages = get().messages;
        // Attach the widget to the most recent agent message, or create one.
        let realIdx = -1;
        for (let i = messages.length - 1; i >= 0; i--) {
          if (messages[i]?.role === "agent") {
            realIdx = i;
            break;
          }
        }
        if (realIdx === -1) {
          get().appendMessage({
            id: makeId(),
            role: "agent",
            text: event.question,
            widgets: [spec],
          });
          return;
        }
        const target = messages[realIdx];
        if (!target || target.role !== "agent") return;
        const next: Message = {
          id: target.id,
          role: "agent",
          text: target.text,
          widgets: [...(target.widgets ?? []), spec],
          live: target.live,
        };
        const newMessages = [...messages];
        newMessages[realIdx] = next;
        const { activeDocId } = get();
        if (activeDocId) saveMessages(activeDocId, newMessages);
        set({ messages: newMessages });
        return;
      }
      case "field_updated": {
        // Optimistic local fields update so the UI reflects the change
        // before the next snapshot arrives.
        const { document } = get();
        if (!document || document.id !== event.document_id) return;
        const newFields = {
          ...(document.fields ?? {}),
          [event.name]: event.value,
        };
        set({ document: { ...document, fields: newFields } });
        return;
      }
      case "document_delivered": {
        // The right pane derives "delivered" from session.state. We just
        // need to refresh the doc so ref_number / pdf_url land in the
        // document object for the DonePane to read.
        try {
          const fresh = await api.getDocument(event.document_id);
          set({ document: fresh });
        } catch {
          // best effort
        }
        return;
      }
      case "redirect": {
        get().appendMessage({
          id: makeId(),
          role: "system",
          text: `Această cerere se face la ${event.name}. Vezi ${event.url}.`,
        });
        return;
      }
      case "lookup_returned": {
        set({
          lookupMatches: event.matches,
          scenarioPlan: event.scenario_plan,
        });
        return;
      }
    }
  },

  async hydrateCitizen() {
    const c = await api.getCitizenMe();
    set({ citizen: c });
  },

  async startProcedure(procedureId: string) {
    const procedure = await api.getProcedure(procedureId);
    const doc = await api.createDocument({ procedure_id: procedureId });
    const greeting: Message = {
      id: makeId(),
      role: "agent",
      text: `Bun, te ajut cu „${procedure.title}". Vezi în dreapta ce vom face pas cu pas și ce acte ai nevoie. Apasă „Continuă" sau spune-mi dacă vrei altceva.`,
    };
    const messages = [greeting];
    saveMessages(doc.id, messages);
    // Preserve the existing conversationId: if the user arrived here from a
    // matches pane after a `lookup_procedure` turn, the agent already has
    // context. The backend folds the new document_id into the session via
    // _resolve_session (CONFIRMING_MATCH → FILLING is a legal transition).
    // Clearing it here would force a fresh session and the agent would lose
    // memory of what the user just confirmed.
    const { conversationId } = get();
    if (conversationId) saveConvId(doc.id, conversationId);
    set({
      activeDocId: doc.id,
      document: doc,
      procedure,
      messages,
      drawerOpen: false,
    });
    pushPath(`/r/${doc.id}`);
  },

  async openScenarioPlan(scenarioId: string) {
    try {
      const plan = await api.getScenarioPlan(scenarioId);
      set({
        scenarioPlan: plan,
        drawerOpen: false,
      });
      pushPath(`/p/${scenarioId}`);
    } catch (err) {
      const detail = err instanceof Error ? err.message : "necunoscută";
      get().appendMessage({
        id: makeId(),
        role: "system",
        text: `Nu am putut încărca planul: ${detail}`,
      });
    }
  },

  async loadDocument(docId: string) {
    const doc = await api.getDocument(docId);
    const procedure = await api.getProcedure(doc.procedure_id);
    const messages = loadMessages(docId);
    const conversationId = loadConvId(docId);
    set({
      activeDocId: docId,
      document: doc,
      procedure,
      conversationId,
      messages,
      drawerOpen: false,
    });
    pushPath(`/r/${docId}`);
  },

  async sendText(text: string, opts) {
    const { activeDocId, conversationId } = get();
    const userMsg: Message = {
      id: makeId(),
      role: "user",
      text,
      via: "text",
    };
    get().appendMessage(userMsg);
    if (opts?.viaWs) {
      // Voice WS active — agent reply arrives via the bridge's
      // outputTranscription deltas → live messages.
      return;
    }
    set({ sending: true });
    const liveId = get().beginLiveMessage("agent");
    const collectedToolCalls: StreamChatToolCall[] = [];
    let finalText = "";
    // Replace any stale controller from a prior turn that never cleared.
    if (_currentAbort) _currentAbort.abort();
    _currentAbort = new AbortController();
    const signal = _currentAbort.signal;
    try {
      await streamChat(
        {
          conversation_id: conversationId,
          document_id: activeDocId ?? undefined,
          message: text,
        },
        {
          onConversation: (id) => {
            if (id !== get().conversationId) {
              set({ conversationId: id });
              // Re-read activeDocId from the store: if the agent calls
              // start_procedure mid-turn, document_opened fires before we
              // get the conversation id back, and the closure's activeDocId
              // is stale. Without this the convId never persists on a
              // discovery-first flow that opens a doc.
              const docId = get().activeDocId;
              if (docId) saveConvId(docId, id);
            }
          },
          onDelta: (full) => {
            get().updateLiveMessage(liveId, full);
          },
          onToolCall: (call) => {
            collectedToolCalls.push(call);
          },
          onToolResult: (name, _output, error) => {
            if (error) {
              get().appendMessage({
                id: makeId(),
                role: "system",
                text: `A apărut o eroare la pasul „${name}": ${error}`,
              });
            }
          },
          onSessionSnapshot: (snapshot) => {
            get().setSession(snapshot);
          },
          onFrontendEvent: (event) => {
            void get().handleFrontendEvent(event);
          },
          onDone: (final) => {
            finalText = final.message;
            get().finalizeLiveMessage(liveId, finalText);
            if (
              final.conversation_id &&
              final.conversation_id !== get().conversationId
            ) {
              set({ conversationId: final.conversation_id });
              const docId = get().activeDocId;
              if (docId) saveConvId(docId, final.conversation_id);
            }
          },
          onError: (err) => {
            const detail = err instanceof Error ? err.message : "necunoscută";
            // AbortError is the user's own intent; don't shout an error bubble.
            const aborted =
              err instanceof Error &&
              (err.name === "AbortError" || detail.includes("aborted"));
            get().finalizeLiveMessage(liveId, finalText || "");
            if (!aborted) {
              get().appendMessage({
                id: makeId(),
                role: "system",
                text: `Eroare: ${detail}`,
              });
            }
          },
        },
        signal,
      );
    } catch (err) {
      void err; // onError already pushed a system bubble + finalized
    } finally {
      // If onDone never fired (mid-stream abort), make sure the live
      // message is finalized so it stops showing the streaming caret.
      get().finalizeLiveMessage(liveId, finalText || "");
      if (_currentAbort?.signal === signal) _currentAbort = null;
      set({ sending: false });
    }
  },

  abortCurrentTurn() {
    if (_currentAbort) {
      _currentAbort.abort();
      _currentAbort = null;
    }
  },

  appendMessage(m) {
    // When the user replies via text/voice (not by clicking a widget),
    // dismiss every still-pending widget so the buttons disappear from
    // earlier agent bubbles. submittedValue is the same marker
    // ChatStream filters on — '__dismissed__' is distinguishable from
    // a real value if downstream code ever needs to tell them apart.
    const prior = get().messages;
    const cleaned = m.role === "user"
      ? prior.map((msg) => {
          if (msg.role !== "agent" || !msg.widgets) return msg;
          const widgets = msg.widgets.map((w) =>
            w.submittedValue ? w : { ...w, submittedValue: "__dismissed__" },
          );
          return { ...msg, widgets };
        })
      : prior;
    const next = [...cleaned, m];
    set({ messages: next });
    const id = get().activeDocId;
    if (id) saveMessages(id, next);
  },

  async submitWidget(widgetSpec, value) {
    const { conversationId, activeDocId } = get();
    if (!conversationId) {
      // No active conversation — fall back to plain text so the agent
      // hears the answer in its first turn (sendText appends the bubble).
      _markWidgetSubmitted(get, set, activeDocId, widgetSpec.widgetId, value);
      void get().sendText(value);
      return;
    }

    // Optimistically mark the widget submitted so the UI disables it
    // immediately — protects against double-click.
    _markWidgetSubmitted(get, set, activeDocId, widgetSpec.widgetId, value);

    // Show the loading bubble immediately on click. Without this, the
    // user clicks a button and stares at silence for ~300-800ms while
    // /agent/widget-result is in flight before sendText eventually flips
    // sending=true. sendText idempotently re-sets the same flag, so this
    // is safe even on the chat-followup path.
    set({ sending: true });

    try {
      const res = await api.submitWidget({
        conversation_id: conversationId,
        widget_id: widgetSpec.widgetId,
        value,
      });
      get().setSession(res.snapshot);

      if (res.requires_chat_followup) {
        // Confirm widget without a target_field — the agent must run a
        // turn to decide what to do (typically start_procedure). sendText
        // appends the user bubble + streams the agent's response, so we
        // don't append a user bubble ourselves here.
        await get().sendText(value);
        return;
      }

      // Direct set_field path: append the user bubble and process any
      // side-effect events from the dispatcher (field_updated, etc.).
      get().appendMessage({
        id: makeId(),
        role: "user",
        text: value,
        via: "text",
      });
      for (const ev of res.events) {
        if (ev.kind === "frontend_event" && ev.event) {
          void get().handleFrontendEvent(
            ev.event as unknown as FrontendEvent,
          );
        } else if (ev.kind === "tool_result" && ev.error) {
          get().appendMessage({
            id: makeId(),
            role: "system",
            text: `Eroare la trimiterea răspunsului: ${ev.error}`,
          });
        }
      }
      // Direct set_field path completed — clear the loading bubble we
      // turned on at click time. The chat-followup branch above returned
      // early so sendText owns the flag in that case.
      set({ sending: false });
    } catch (err) {
      const detail = err instanceof Error ? err.message : "necunoscută";
      get().appendMessage({
        id: makeId(),
        role: "system",
        text: `Nu am putut trimite răspunsul: ${detail}`,
      });
      // Roll back the optimistic submittedValue so user can retry.
      _markWidgetSubmitted(get, set, activeDocId, widgetSpec.widgetId, null);
      set({ sending: false });
    }
  },

  beginLiveMessage(role) {
    const id = makeId();
    const msg: Message =
      role === "user"
        ? { id, role: "user", text: "", via: "voice", live: true }
        : { id, role: "agent", text: "", live: true };
    set((s) => {
      const messages = [...s.messages, msg];
      if (s.activeDocId) saveMessages(s.activeDocId, messages);
      return { messages };
    });
    return id;
  },

  updateLiveMessage(id, text) {
    set((s) => {
      const messages = s.messages.map((m) =>
        m.id === id && m.role !== "system" ? { ...m, text } : m,
      );
      if (s.activeDocId) saveMessages(s.activeDocId, messages);
      return { messages };
    });
  },

  finalizeLiveMessage(id, text) {
    set((s) => {
      const messages = s.messages.map((m) =>
        m.id === id && m.role !== "system"
          ? { ...m, text, live: false }
          : m,
      );
      if (s.activeDocId) saveMessages(s.activeDocId, messages);
      return { messages };
    });
  },

  setVoiceStatus(s) {
    set({ voiceStatus: s });
  },

  setMicOn(on) {
    set({ micOn: on });
  },

  openDrawer() {
    set({ drawerOpen: true });
  },
  closeDrawer() {
    set({ drawerOpen: false });
  },
  toggleProfileMenu() {
    set({ profileMenuOpen: !get().profileMenuOpen });
  },
  closeProfileMenu() {
    set({ profileMenuOpen: false });
  },

  reset() {
    set({
      activeDocId: null,
      document: null,
      procedure: null,
      conversationId: null,
      messages: [],
      drawerOpen: false,
      profileMenuOpen: false,
      scenarioPlan: null,
      lookupMatches: [],
      session: null,
    });
    pushPath("/");
  },
}));
