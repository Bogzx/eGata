"use client";

import { create } from "zustand";
import { api } from "./api";
import {
  allRequiredFilled,
  computeInitialRightPaneFrom,
} from "./rightPaneState";
import { streamChat, type StreamChatToolCall } from "./sseChat";
import type {
  Citizen,
  Document,
  FrontendEvent,
  LookupMatch,
  Message,
  PendingMessage,
  Procedure,
  RightPaneState,
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
  citizen: Citizen | null;
  activeDocId: string | null;
  document: Document | null;
  procedure: Procedure | null;
  conversationId: string | null;
  messages: Message[];
  /** In-progress user turn, rendered as a live-updating bubble. */
  pendingUser: PendingMessage | null;
  /** In-progress agent turn, rendered as a live-updating bubble. */
  pendingAgent: PendingMessage | null;
  rightPane: RightPaneState;
  voiceStatus: VoiceStatus;
  drawerOpen: boolean;
  profileMenuOpen: boolean;
  sending: boolean;
  scenarioPlan: ScenarioPlan | null;
  lookupMatches: LookupMatch[];

  hydrateCitizen(): Promise<void>;
  startProcedure(procedureId: string): Promise<void>;
  loadDocument(docId: string): Promise<void>;
  openScenarioPlan(scenarioId: string): Promise<void>;
  sendText(text: string, opts?: { viaWs?: boolean }): Promise<void>;
  applyToolResult(
    toolName: string,
    args: Record<string, unknown>,
    result: unknown,
  ): Promise<void>;
  appendMessage(m: Message): void;
  upsertPendingUser(text: string, via?: "text" | "voice"): void;
  upsertPendingAgent(text: string): void;
  finalizePendingUser(): void;
  finalizePendingAgent(widgets?: WidgetSpec[]): void;
  clearPending(): void;
  /** Live messages stream their content in-place (e.g., voice transcripts). */
  beginLiveMessage(role: "user" | "agent"): string;
  updateLiveMessage(id: string, text: string): void;
  finalizeLiveMessage(id: string, text: string): void;
  /** SP4: mirror the backend's session_snapshot frame. */
  session: SessionSnapshot | null;
  setSession(snapshot: SessionSnapshot): void;
  /** SP4: react to a structured frontend event from a tool. */
  handleFrontendEvent(event: FrontendEvent): void;
  transitionRightPane(next: RightPaneState): void;
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
  pendingUser: null,
  pendingAgent: null,
  rightPane: { kind: "welcome" },
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
        // Optimistic: applyToolResult also refetches the doc, but pushing the
        // field locally first means the UI reflects the change immediately.
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
        set({ rightPane: { kind: "done", refNumber: event.ref_number } });
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
      pendingUser: null,
      pendingAgent: null,
      rightPane: { kind: "guide", procedureId },
      drawerOpen: false,
    });
    pushPath(`/r/${doc.id}`);
  },

  async openScenarioPlan(scenarioId: string) {
    try {
      const plan = await api.getScenarioPlan(scenarioId);
      set({
        scenarioPlan: plan,
        rightPane: { kind: "plan", scenarioId },
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
      pendingUser: null,
      pendingAgent: null,
      rightPane: computeInitialRightPaneFrom(doc, procedure),
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
      // Voice WS active — agent reply arrives via outputTranscription deltas.
      return;
    }
    set({ sending: true });
    const pendingId = makeId();
    set({ pendingAgent: { id: pendingId, role: "agent", text: "" } });
    const collectedToolCalls: StreamChatToolCall[] = [];
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
            const cur = get().pendingAgent;
            if (!cur || cur.id !== pendingId) return;
            set({ pendingAgent: { ...cur, text: full } });
          },
          onToolCall: (call) => {
            collectedToolCalls.push(call);
          },
          onToolResult: async (name, output) => {
            const call = collectedToolCalls.find((c) => c.name === name);
            await get().applyToolResult(name, call?.arguments ?? {}, output);
          },
          onSessionSnapshot: (snapshot) => {
            get().setSession(snapshot);
          },
          onFrontendEvent: (event) => {
            void get().handleFrontendEvent(event);
          },
          onDone: (final) => {
            const widgets = deriveWidgets(final.tool_calls);
            const agentMsg: Message = {
              id: makeId(),
              role: "agent",
              text: final.message,
              widgets: widgets.length ? widgets : undefined,
            };
            set({ pendingAgent: null });
            get().appendMessage(agentMsg);
            if (final.conversation_id && final.conversation_id !== conversationId) {
              set({ conversationId: final.conversation_id });
              if (activeDocId) saveConvId(activeDocId, final.conversation_id);
            }
          },
          onError: (err) => {
            const detail = err instanceof Error ? err.message : "necunoscută";
            set({ pendingAgent: null });
            get().appendMessage({
              id: makeId(),
              role: "system",
              text: `Eroare: ${detail}`,
            });
          },
        },
      );
    } catch (err) {
      // streamChat re-throws on fetch / parse errors after invoking onError —
      // onError has already pushed the system bubble, so we just clean up.
      void err;
    } finally {
      set({ sending: false, pendingAgent: null });
    }
  },

  async applyToolResult(name, args, _result) {
    const { activeDocId, procedure } = get();
    switch (name) {
      case "set_field":
      case "generate_pdf":
      case "deliver": {
        if (!activeDocId || !procedure) return;
        const fresh = await api.getDocument(activeDocId).catch(() => null);
        if (!fresh) return;
        set({ document: fresh });
        const computed = computeInitialRightPaneFrom(fresh, procedure);
        if (name === "set_field" && computed.kind === "filling") {
          const fieldName =
            (args.name as string | undefined) ?? undefined;
          set({ rightPane: { kind: "filling", activeField: fieldName } });
        } else {
          set({ rightPane: computed });
        }
        if (
          name === "set_field" &&
          allRequiredFilled(procedure, fresh.fields)
        ) {
          set({ rightPane: { kind: "review" } });
        }
        break;
      }
      case "lookup_procedure": {
        const res = _result as
          | {
              scenario_plan?: ScenarioPlan | null;
              matches?: LookupMatch[];
            }
          | undefined;
        const sp = res?.scenario_plan ?? null;
        const matches = res?.matches ?? [];
        if (sp && !activeDocId) {
          set({
            scenarioPlan: sp,
            lookupMatches: matches,
            rightPane: { kind: "plan", scenarioId: sp.scenario_id },
          });
          pushPath(`/p/${sp.scenario_id}`);
        } else if (matches.length > 0 && !activeDocId) {
          set({
            lookupMatches: matches,
            rightPane: { kind: "matches" },
          });
        }
        break;
      }
      case "find_redirect":
      case "set_reminder":
      case "propose_widget":
        // No store mutation — widgets surface through messages already.
        break;
      default:
        break;
    }
  },

  appendMessage(m) {
    const next = [...get().messages, m];
    set({ messages: next });
    const id = get().activeDocId;
    if (id) saveMessages(id, next);
  },

  upsertPendingUser(text, via = "voice") {
    const cur = get().pendingUser;
    if (cur) {
      set({ pendingUser: { ...cur, text, via } });
    } else {
      set({
        pendingUser: { id: makeId(), role: "user", text, via },
      });
    }
  },

  upsertPendingAgent(text) {
    const cur = get().pendingAgent;
    if (cur) {
      set({ pendingAgent: { ...cur, text } });
    } else {
      set({
        pendingAgent: { id: makeId(), role: "agent", text },
      });
    }
  },

  finalizePendingUser() {
    set({ pendingUser: null });
  },

  finalizePendingAgent(_widgets) {
    set({ pendingAgent: null });
  },

  clearPending() {
    set({ pendingUser: null, pendingAgent: null });
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

  transitionRightPane(next) {
    set({ rightPane: next });
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
      pendingUser: null,
      pendingAgent: null,
      rightPane: { kind: "welcome" },
      drawerOpen: false,
      profileMenuOpen: false,
      scenarioPlan: null,
      lookupMatches: [],
    });
    pushPath("/");
  },
}));

function deriveWidgets(
  toolCalls:
    | { name: string; arguments: Record<string, unknown> }[]
    | undefined,
): WidgetSpec[] {
  if (!toolCalls) return [];
  const out: WidgetSpec[] = [];
  for (const tc of toolCalls) {
    if (tc.name !== "propose_widget") continue;
    const a = tc.arguments;
    const type = a.type as WidgetSpec["type"] | undefined;
    const question = (a.question as string | undefined) ?? "";
    const widgetId = Math.random().toString(36).slice(2);
    if (type === "choice") {
      out.push({
        type: "choice",
        question,
        options: (a.options as string[] | undefined) ?? [],
        targetField: (a.target_field as string | undefined) ?? "",
        widgetId,
      });
    } else if (type === "confirm") {
      out.push({
        type: "confirm",
        question,
        onConfirmTool: a.on_confirm_tool as string | undefined,
        widgetId,
      });
    } else if (type === "date") {
      out.push({
        type: "date",
        question,
        targetField: (a.target_field as string | undefined) ?? "",
        widgetId,
      });
    }
  }
  return out;
}
