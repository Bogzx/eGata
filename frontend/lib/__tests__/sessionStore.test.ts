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
    rightPane: { kind: "welcome" },
    voiceStatus: "idle",
    drawerOpen: false,
    profileMenuOpen: false,
    sending: false,
  });
  localStorage.clear();
});

describe("sessionStore initial state", () => {
  it("starts in welcome state with no doc", () => {
    const s = useSessionStore.getState();
    expect(s.rightPane.kind).toBe("welcome");
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
    const raw = localStorage.getItem("civicai:session:d1");
    expect(raw).toContain("hi");
  });

  it("does not persist when no active doc", () => {
    useSessionStore.getState().appendMessage({
      id: "m1",
      role: "agent",
      text: "no-doc-yet",
    });
    expect(useSessionStore.getState().messages).toHaveLength(1);
    // No key should be created
    expect(localStorage.length).toBe(0);
  });
});

describe("sessionStore transitions and toggles", () => {
  it("transitionRightPane sets new state", () => {
    useSessionStore.getState().transitionRightPane({ kind: "review" });
    expect(useSessionStore.getState().rightPane.kind).toBe("review");
  });

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

describe("sessionStore reset", () => {
  it("clears state", () => {
    useSessionStore.setState({
      activeDocId: "d1",
      messages: [{ id: "m", role: "user", text: "x", via: "text" }],
      rightPane: { kind: "review" },
      drawerOpen: true,
    });
    useSessionStore.getState().reset();
    const s = useSessionStore.getState();
    expect(s.activeDocId).toBeNull();
    expect(s.messages).toEqual([]);
    expect(s.rightPane.kind).toBe("welcome");
    expect(s.drawerOpen).toBe(false);
  });
});
