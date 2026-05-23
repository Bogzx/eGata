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

const LS_MSG_KEY = (docId: string) => `civicai:session:${docId}`;
const LS_CONV_KEY = (docId: string) => `civicai:conv:${docId}`;

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

function pushPath(path: string) {
  if (typeof window === "undefined") return;
  if (window.location.pathname !== path) {
    window.history.pushState(null, "", path);
  }
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
  openDrawer(): void;
  closeDrawer(): void;
  toggleProfileMenu(): void;
  closeProfileMenu(): void;
  reset(): void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  citizen: null,
  activeDocId: null,
  document: null,
  procedure: null,
  conversationId: null,
  messages: [],
  voiceStatus: "idle",
  drawerOpen: false,
  profileMenuOpen: false,
  sending: false,
  scenarioPlan: null,
  lookupMatches: [],
  session: null,

  setSession(snapshot) {
    set({ session: snapshot });
  },

  async handleFrontendEvent(event) {
    switch (event.type) {
      case "document_opened": {
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
    set({
      activeDocId: doc.id,
      document: doc,
      procedure,
      conversationId: null,
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
              if (activeDocId) saveConvId(activeDocId, id);
            }
          },
          onDelta: (full) => {
            get().updateLiveMessage(liveId, full);
          },
          onToolCall: (call) => {
            collectedToolCalls.push(call);
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
              final.conversation_id !== conversationId
            ) {
              set({ conversationId: final.conversation_id });
              if (activeDocId) saveConvId(activeDocId, final.conversation_id);
            }
          },
          onError: (err) => {
            const detail = err instanceof Error ? err.message : "necunoscută";
            get().finalizeLiveMessage(liveId, finalText || "");
            get().appendMessage({
              id: makeId(),
              role: "system",
              text: `Eroare: ${detail}`,
            });
          },
        },
      );
    } catch (err) {
      void err; // onError already pushed a system bubble + finalized
    } finally {
      // If onDone never fired (mid-stream abort), make sure the live
      // message is finalized so it stops showing the streaming caret.
      get().finalizeLiveMessage(liveId, finalText || "");
      set({ sending: false });
    }
  },

  appendMessage(m) {
    const next = [...get().messages, m];
    set({ messages: next });
    const id = get().activeDocId;
    if (id) saveMessages(id, next);
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
