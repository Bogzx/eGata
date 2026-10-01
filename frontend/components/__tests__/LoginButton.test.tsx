import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { LoginButton } from "../LoginButton";

afterEach(() => vi.unstubAllGlobals());

describe("LoginButton", () => {
  it("tells the visitor the server is unreachable when fetch itself fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<LoginButton onChallenge={() => {}} />);
    fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Serverul eGata nu răspunde");
  });

  it("keeps the generic error when the server answered with an error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "x" }), { status: 500 })),
    );
    render(<LoginButton onChallenge={() => {}} />);
    fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByRole("alert")).toHaveTextContent("A apărut o eroare");
  });
});
