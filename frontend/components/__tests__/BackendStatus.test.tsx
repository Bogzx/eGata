import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BackendStatus, probeBackend } from "../BackendStatus";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("probeBackend", () => {
  it("is up only on a 2xx from /health", async () => {
    const ok = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    expect(await probeBackend("https://api.test", 5000, ok)).toBe(true);
    expect(ok).toHaveBeenCalledWith("https://api.test/health", expect.anything());

    const notFound = vi.fn().mockResolvedValue(new Response("gone", { status: 404 }));
    expect(await probeBackend("https://api.test", 5000, notFound)).toBe(false);
  });

  it("treats a network or CORS failure as down", async () => {
    const refused = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    expect(await probeBackend("https://api.test", 5000, refused)).toBe(false);
  });

  it("gives up after the timeout", async () => {
    vi.useFakeTimers();
    const hang = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted")));
        }),
    );
    const result = probeBackend("https://api.test", 5000, hang as unknown as typeof fetch);
    await vi.advanceTimersByTimeAsync(5000);
    expect(await result).toBe(false);
  });
});

describe("BackendStatus", () => {
  it("renders nothing while the backend answers", async () => {
    const fetchOk = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchOk);
    render(<BackendStatus />);
    await waitFor(() => expect(fetchOk).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("says the demo server is offline and how to run it, and can be dismissed", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<BackendStatus />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Serverul demo nu răspunde");
    expect(alert).toHaveTextContent("docker compose up");
    expect(screen.getByRole("link", { name: "github.com/Bogzx/eGata" })).toHaveAttribute(
      "href",
      "https://github.com/Bogzx/eGata",
    );
    fireEvent.click(screen.getByRole("button", { name: "Închide mesajul" }));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
