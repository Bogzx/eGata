import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { useGhiseuStore } from "../ghiseuStore";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      submitDocument: vi.fn().mockResolvedValue({
        ref_number: "REG-2026-DEADBEEF",
        delivery: "city",
        delivered_at: "2026-05-24T10:00:00Z",
      }),
      getDocument: vi.fn().mockResolvedValue({
        id: "d1",
        procedure_id: "x",
        fields: {},
        ref_number: "REG-2026-DEADBEEF",
      }),
    },
  };
});

beforeEach(() => {
  useGhiseuStore.setState({
    state: "idle",
    muted: true,
    exportMethod: null,
    caption: { user: null, agent: null },
    _bridge: null,
  });
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("ghiseuStore initial state", () => {
  it("starts idle, muted, no export method, empty caption", () => {
    const s = useGhiseuStore.getState();
    expect(s.state).toBe("idle");
    expect(s.muted).toBe(true);
    expect(s.exportMethod).toBeNull();
    expect(s.caption).toEqual({ user: null, agent: null });
  });
});

describe("ghiseuStore caption event handlers", () => {
  it("appendUserPartial sets caption.user with live:true", () => {
    useGhiseuStore.getState().appendUserPartial("salut");
    const c = useGhiseuStore.getState().caption;
    expect(c.user).toEqual({ text: "salut", live: true });
    expect(c.agent).toBeNull();
  });

  it("commitUserMessage sets caption.user with live:false and schedules thinking-transition", () => {
    useGhiseuStore.setState({ state: "listening" });
    useGhiseuStore.getState().commitUserMessage("salut, vreau o adeverință");
    expect(useGhiseuStore.getState().caption.user).toEqual({
      text: "salut, vreau o adeverință",
      live: false,
    });
    expect(useGhiseuStore.getState().state).toBe("listening");
    vi.advanceTimersByTime(300);
    expect(useGhiseuStore.getState().state).toBe("thinking");
  });

  it("appendAgentPartial cancels the thinking-transition and goes straight to speaking", () => {
    useGhiseuStore.setState({ state: "listening" });
    useGhiseuStore.getState().commitUserMessage("salut");
    vi.advanceTimersByTime(100);
    useGhiseuStore.getState().appendAgentPartial("buna");
    expect(useGhiseuStore.getState().state).toBe("speaking");
    vi.advanceTimersByTime(500);
    expect(useGhiseuStore.getState().state).toBe("speaking");
  });

  it("commitAgentMessage returns state to listening and marks agent line non-live", () => {
    useGhiseuStore.setState({ state: "speaking" });
    useGhiseuStore.getState().commitAgentMessage("am inteles");
    expect(useGhiseuStore.getState().state).toBe("listening");
    expect(useGhiseuStore.getState().caption.agent).toEqual({
      text: "am inteles",
      live: false,
    });
  });

  it("user and agent captions live independently (no cross-bleed)", () => {
    useGhiseuStore.getState().appendUserPartial("user a");
    useGhiseuStore.getState().appendAgentPartial("agent a");
    const c = useGhiseuStore.getState().caption;
    expect(c.user?.text).toBe("user a");
    expect(c.agent?.text).toBe("agent a");
  });

  it("appendAgentPartial does NOT override 'done' state (post-export terminal)", () => {
    useGhiseuStore.setState({ state: "done" });
    useGhiseuStore.getState().appendAgentPartial("accidental agent reply");
    expect(useGhiseuStore.getState().state).toBe("done");
    expect(useGhiseuStore.getState().caption.agent?.text).toBe(
      "accidental agent reply",
    );
  });

  it("appendAgentPartial does NOT override 'review' state (user is reviewing fields)", () => {
    useGhiseuStore.setState({ state: "review" });
    useGhiseuStore.getState().appendAgentPartial("agent saying something");
    expect(useGhiseuStore.getState().state).toBe("review");
  });

  it("commitUserMessage does NOT schedule thinking-flash from 'done' state", () => {
    useGhiseuStore.setState({ state: "done" });
    useGhiseuStore.getState().commitUserMessage("accidental utterance");
    vi.advanceTimersByTime(500);
    expect(useGhiseuStore.getState().state).toBe("done");
  });

  it("commitAgentMessage does NOT override 'done' state", () => {
    useGhiseuStore.setState({ state: "done" });
    useGhiseuStore.getState().commitAgentMessage("done agent reply");
    expect(useGhiseuStore.getState().state).toBe("done");
  });
});

describe("ghiseuStore confirmDoc + amendDoc + pickExport + backToTalk", () => {
  it("confirmDoc transitions review → export", () => {
    useGhiseuStore.setState({ state: "review" });
    useGhiseuStore.getState().confirmDoc();
    expect(useGhiseuStore.getState().state).toBe("export");
  });

  it("amendDoc keeps state on review (user stays on review screen)", () => {
    useGhiseuStore.setState({ state: "review" });
    useGhiseuStore.getState().amendDoc();
    expect(useGhiseuStore.getState().state).toBe("review");
  });

  it("amendDoc cancels a pending thinking-transition", () => {
    useGhiseuStore.setState({ state: "review" });
    useGhiseuStore.getState().commitUserMessage("hello");
    vi.advanceTimersByTime(100);
    useGhiseuStore.getState().amendDoc();
    vi.advanceTimersByTime(1000);
    expect(useGhiseuStore.getState().state).toBe("review");
  });

  it("pickExport transitions export → submitting → done with real ref", async () => {
    const { useSessionStore } = await import("../sessionStore");
    useSessionStore.setState({ activeDocId: "d1" } as never);
    useGhiseuStore.setState({ state: "export" });
    vi.useRealTimers();

    const promise = useGhiseuStore.getState().pickExport("city");
    // Synchronously after the call, we should be in submitting.
    expect(useGhiseuStore.getState().state).toBe("submitting");
    expect(useGhiseuStore.getState().exportMethod).toBe("city");

    await promise;
    expect(useGhiseuStore.getState().state).toBe("done");
  });

  it("pickExport with no activeDocId goes to error (defensive)", async () => {
    const { useSessionStore } = await import("../sessionStore");
    useSessionStore.setState({ activeDocId: null } as never);
    useGhiseuStore.setState({ state: "export" });
    vi.useRealTimers();

    await useGhiseuStore.getState().pickExport("city");
    expect(useGhiseuStore.getState().state).toBe("error");
  });

  it("backToTalk returns to listening and unmutes", () => {
    useGhiseuStore.setState({ state: "export", muted: true });
    useGhiseuStore.getState().backToTalk();
    expect(useGhiseuStore.getState().state).toBe("listening");
    expect(useGhiseuStore.getState().muted).toBe(false);
  });
});

describe("ghiseuStore reset", () => {
  it("returns to idle, mutes, clears export method and caption", () => {
    useGhiseuStore.setState({
      state: "done",
      muted: false,
      exportMethod: "email",
      caption: { user: { text: "x", live: false }, agent: { text: "y", live: false } },
    });
    useGhiseuStore.getState().reset();
    const s = useGhiseuStore.getState();
    expect(s.state).toBe("idle");
    expect(s.muted).toBe(true);
    expect(s.exportMethod).toBeNull();
    expect(s.caption).toEqual({ user: null, agent: null });
  });

  it("reset() cancels a pending thinking-transition", () => {
    useGhiseuStore.setState({ state: "listening" });
    useGhiseuStore.getState().commitUserMessage("hello");
    vi.advanceTimersByTime(100);
    useGhiseuStore.getState().reset();
    vi.advanceTimersByTime(1000);
    expect(useGhiseuStore.getState().state).toBe("idle");
  });
});
