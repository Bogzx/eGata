import { describe, it, expect, beforeEach } from "vitest";
import { useSessionStore } from "../sessionStore";

beforeEach(() => {
  useSessionStore.setState({
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
    session: null,
    scenarioPlan: null,
    lookupMatches: [],
  });
  localStorage.clear();
});

describe("sessionStore initial state", () => {
  it("starts with no session and no doc", () => {
    const s = useSessionStore.getState();
    expect(s.session).toBeNull();
    expect(s.activeDocId).toBeNull();
    expect(s.messages).toEqual([]);
    expect(s.voiceStatus).toBe("idle");
  });
});

describe("sessionStore appendMessage", () => {
  it("appends and persists to localStorage when a doc is active", () => {
    useSessionStore.setState({ activeDocId: "d1" });
    useSessionStore.getState().appendMessage({
      id: "m1",
      role: "user",
      text: "hi",
      via: "text",
    });
    expect(useSessionStore.getState().messages).toHaveLength(1);
    const raw = localStorage.getItem("egata:session:d1");
    expect(raw).toContain("hi");
  });

  it("does not persist when no active doc", () => {
    useSessionStore.getState().appendMessage({
      id: "m1",
      role: "agent",
      text: "no-doc-yet",
    });
    expect(useSessionStore.getState().messages).toHaveLength(1);
    expect(localStorage.length).toBe(0);
  });
});

describe("sessionStore open widgets", () => {
  function agentWithTwoChoices() {
    useSessionStore.setState({
      messages: [
        {
          id: "a1",
          role: "agent",
          text: "Adresă nouă?",
          widgets: [
            { type: "choice", question: "Tip proprietate", options: ["proprietar"], targetField: "tip_proprietate", widgetId: "w1" },
            { type: "choice", question: "Etaj", options: ["parter"], targetField: "etaj", widgetId: "w2" },
          ],
        },
      ],
    });
  }
  function openWidgetIds(): string[] {
    const first = useSessionStore.getState().messages[0];
    if (!first || first.role !== "agent") throw new Error("expected agent");
    return (first.widgets ?? []).filter((w) => !w.submittedValue).map((w) => w.widgetId);
  }

  it("a typed reply dismisses every open widget", () => {
    agentWithTwoChoices();
    useSessionStore.getState().appendMessage({ id: "u1", role: "user", text: "Str. Lungă 3", via: "text" });
    expect(openWidgetIds()).toEqual([]);
  });

  it("the echo of a clicked answer leaves the other widgets open", () => {
    agentWithTwoChoices();
    useSessionStore.getState().appendMessage({ id: "u1", role: "user", text: "proprietar", via: "widget" });
    expect(openWidgetIds()).toEqual(["w1", "w2"]);
  });
});

describe("sessionStore live messages", () => {
  it("begin → update → finalize lifecycle for an agent message", () => {
    useSessionStore.setState({ activeDocId: "d2" });
    const s = useSessionStore.getState();
    const id = s.beginLiveMessage("agent");
    expect(useSessionStore.getState().messages).toHaveLength(1);
    const first = useSessionStore.getState().messages[0];
    expect(first).toBeDefined();
    if (!first || first.role !== "agent") throw new Error("expected agent");
    expect(first.live).toBe(true);
    expect(first.text).toBe("");

    s.updateLiveMessage(id, "salut, te");
    s.updateLiveMessage(id, "salut, te ascult");
    s.finalizeLiveMessage(id, "salut, te ascult.");
    const last = useSessionStore.getState().messages[0];
    if (!last || last.role !== "agent") throw new Error("expected agent");
    expect(last.text).toBe("salut, te ascult.");
    expect(last.live).toBe(false);
  });

  it("user live message gets via: voice", () => {
    const s = useSessionStore.getState();
    const id = s.beginLiveMessage("user");
    const msg = useSessionStore.getState().messages[0];
    expect(msg).toBeDefined();
    if (!msg || msg.role !== "user") throw new Error("expected user");
    expect(msg.via).toBe("voice");
    s.finalizeLiveMessage(id, "ok");
  });
});

describe("sessionStore toggles", () => {
  it("voice status setter", () => {
    useSessionStore.getState().setVoiceStatus("listening");
    expect(useSessionStore.getState().voiceStatus).toBe("listening");
  });

  it("drawer toggles", () => {
    const s = useSessionStore.getState();
    s.openDrawer();
    expect(useSessionStore.getState().drawerOpen).toBe(true);
    s.closeDrawer();
    expect(useSessionStore.getState().drawerOpen).toBe(false);
  });

  it("profile menu toggles", () => {
    const s = useSessionStore.getState();
    s.toggleProfileMenu();
    expect(useSessionStore.getState().profileMenuOpen).toBe(true);
    s.toggleProfileMenu();
    expect(useSessionStore.getState().profileMenuOpen).toBe(false);
  });
});

describe("sessionStore setSession", () => {
  it("mirrors a snapshot from the backend", () => {
    useSessionStore.getState().setSession({
      id: "sess_x",
      citizen_id: "abc",
      state: "filling",
      active_document_id: "doc_y",
      scenario_id: null,
      step_index: null,
      pending_widgets: [],
    });
    const s = useSessionStore.getState();
    expect(s.session?.state).toBe("filling");
    expect(s.session?.active_document_id).toBe("doc_y");
  });

  it("drops a stale snapshot if seq goes backwards", () => {
    const store = useSessionStore.getState();
    store.setSession({
      id: "sess_x",
      citizen_id: "abc",
      state: "filling",
      active_document_id: "doc_y",
      scenario_id: null,
      step_index: null,
      pending_widgets: [],
      seq: 100,
    });
    // Older snapshot arrives — should be dropped.
    store.setSession({
      id: "sess_x",
      citizen_id: "abc",
      state: "exploring",
      active_document_id: null,
      scenario_id: null,
      step_index: null,
      pending_widgets: [],
      seq: 50,
    });
    expect(useSessionStore.getState().session?.state).toBe("filling");
    // Newer snapshot wins.
    store.setSession({
      id: "sess_x",
      citizen_id: "abc",
      state: "reviewing",
      active_document_id: "doc_y",
      scenario_id: null,
      step_index: null,
      pending_widgets: [],
      seq: 200,
    });
    expect(useSessionStore.getState().session?.state).toBe("reviewing");
  });

  it("does not apply seq guard across different session ids", () => {
    const store = useSessionStore.getState();
    store.setSession({
      id: "sess_a",
      citizen_id: "abc",
      state: "filling",
      active_document_id: "doc_y",
      scenario_id: null,
      step_index: null,
      pending_widgets: [],
      seq: 999,
    });
    // Different session id → always applies.
    store.setSession({
      id: "sess_b",
      citizen_id: "abc",
      state: "exploring",
      active_document_id: null,
      scenario_id: null,
      step_index: null,
      pending_widgets: [],
      seq: 1,
    });
    expect(useSessionStore.getState().session?.id).toBe("sess_b");
  });
});

describe("sessionStore abortCurrentTurn", () => {
  it("is a no-op when no turn is in flight", () => {
    // Smoke test only — exercise the code path so we don't regress the
    // null-guard in the future.
    expect(() => useSessionStore.getState().abortCurrentTurn()).not.toThrow();
  });
});

describe("sessionStore reset", () => {
  it("clears state", () => {
    useSessionStore.setState({
      activeDocId: "d1",
      messages: [{ id: "m", role: "user", text: "x", via: "text" }],
      drawerOpen: true,
      session: {
        id: "sess",
        citizen_id: "c",
        state: "filling",
        active_document_id: "d1",
        scenario_id: null,
        step_index: null,
        pending_widgets: [],
      },
    });
    useSessionStore.getState().reset();
    const s = useSessionStore.getState();
    expect(s.activeDocId).toBeNull();
    expect(s.messages).toEqual([]);
    expect(s.session).toBeNull();
    expect(s.drawerOpen).toBe(false);
  });
});
