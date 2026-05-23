"use client";

import { create } from "zustand";
import { api } from "./api";
import {
  allRequiredFilled,
  computeInitialRightPaneFrom,
} from "./rightPaneState";
import type {
  Citizen,
  Document,
  Message,
  Procedure,
  RightPaneState,
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
  rightPane: RightPaneState;
  voiceStatus: VoiceStatus;
  drawerOpen: boolean;
  profileMenuOpen: boolean;
  sending: boolean;

  hydrateCitizen(): Promise<void>;
  startProcedure(procedureId: string): Promise<void>;
  loadDocument(docId: string): Promise<void>;
  sendText(text: string, opts?: { viaWs?: boolean }): Promise<void>;
  applyToolResult(
    toolName: string,
    args: Record<string, unknown>,
    result: unknown,
  ): Promise<void>;
  appendMessage(m: Message): void;
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
  rightPane: { kind: "welcome" },
  voiceStatus: "idle",
  drawerOpen: false,
  profileMenuOpen: false,
  sending: false,

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
      rightPane: { kind: "guide", procedureId },
      drawerOpen: false,
    });
    pushPath(`/r/${doc.id}`);
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
      // Voice WS active — agent reply will arrive via outputTranscription.
      return;
    }
    set({ sending: true });
    try {
      const r = await api.chat({
        conversation_id: conversationId,
        document_id: activeDocId ?? undefined,
        message: text,
      });
      const widgets = deriveWidgets(r.tool_calls);
      const agentMsg: Message = {
        id: makeId(),
        role: "agent",
        text: r.message,
        widgets: widgets.length ? widgets : undefined,
      };
      get().appendMessage(agentMsg);
      if (r.conversation_id !== conversationId) {
        set({ conversationId: r.conversation_id });
        if (activeDocId) saveConvId(activeDocId, r.conversation_id);
      }
      for (const tc of r.tool_calls ?? []) {
        await get().applyToolResult(tc.name, tc.arguments, null);
      }
    } catch (err) {
      const detail = err instanceof Error ? err.message : "necunoscută";
      get().appendMessage({
        id: makeId(),
        role: "system",
        text: `Eroare: ${detail}`,
      });
    } finally {
      set({ sending: false });
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
      case "lookup_procedure":
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
      rightPane: { kind: "welcome" },
      drawerOpen: false,
      profileMenuOpen: false,
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
    const widgetId =
      (a.widget_id as string | undefined) ??
      Math.random().toString(36).slice(2);
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
