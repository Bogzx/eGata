import { describe, it, expect, vi } from "vitest";
import { _internal } from "../sseChat";

const { parseFrames, dispatchFrame } = _internal;

describe("parseFrames", () => {
  it("splits two complete frames and keeps the partial in rest", () => {
    const buf =
      'event: delta\ndata: {"text":"hello"}\n\n' +
      'event: delta\ndata: {"text":"hello world"}\n\n' +
      "event: don";
    const { frames, rest } = parseFrames(buf);
    expect(frames).toHaveLength(2);
    expect(frames[0]?.event).toBe("delta");
    expect(JSON.parse(frames[0]?.data ?? "{}")).toEqual({ text: "hello" });
    expect(JSON.parse(frames[1]?.data ?? "{}")).toEqual({
      text: "hello world",
    });
    expect(rest).toBe("event: don");
  });

  it("tolerates CRLF line endings", () => {
    const buf =
      "event: delta\r\ndata: {\"text\":\"ok\"}\r\n\r\n";
    const { frames, rest } = parseFrames(buf);
    expect(frames).toHaveLength(1);
    expect(rest).toBe("");
    expect(JSON.parse(frames[0]?.data ?? "{}")).toEqual({ text: "ok" });
  });

  it("joins multiple data: lines with newlines", () => {
    const buf = "event: delta\ndata: line1\ndata: line2\n\n";
    const { frames } = parseFrames(buf);
    expect(frames[0]?.data).toBe("line1\nline2");
  });
});

describe("dispatchFrame", () => {
  it("routes delta → onDelta(text)", () => {
    const onDelta = vi.fn();
    dispatchFrame({ event: "delta", data: '{"text":"hi"}' }, { onDelta });
    expect(onDelta).toHaveBeenCalledWith("hi");
  });

  it("routes tool_call → onToolCall({name, arguments})", () => {
    const onToolCall = vi.fn();
    dispatchFrame(
      {
        event: "tool_call",
        data: '{"name":"set_field","arguments":{"name":"adresa","value":"X"}}',
      },
      { onToolCall },
    );
    expect(onToolCall).toHaveBeenCalledWith({
      name: "set_field",
      arguments: { name: "adresa", value: "X" },
    });
  });

  it("routes done → onDone(final)", () => {
    const onDone = vi.fn();
    dispatchFrame(
      {
        event: "done",
        data:
          '{"conversation_id":"c1","message":"ok","tool_calls":[]}',
      },
      { onDone },
    );
    expect(onDone).toHaveBeenCalledWith({
      conversation_id: "c1",
      message: "ok",
      tool_calls: [],
    });
  });

  it("routes error → onError(Error)", () => {
    const onError = vi.fn();
    dispatchFrame(
      { event: "error", data: '{"detail":"boom"}' },
      { onError },
    );
    expect(onError).toHaveBeenCalledTimes(1);
    const err = onError.mock.calls[0]?.[0];
    expect(err).toBeInstanceOf(Error);
    expect((err as Error).message).toBe("boom");
  });

  it("silently ignores unknown events", () => {
    const onDelta = vi.fn();
    dispatchFrame({ event: "foo", data: "{}" }, { onDelta });
    expect(onDelta).not.toHaveBeenCalled();
  });
});
