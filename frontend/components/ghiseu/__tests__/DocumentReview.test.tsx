import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DocumentReview } from "../DocumentReview";

describe("DocumentReview", () => {
  it("renders the review header and the auto-fill fields", () => {
    render(<DocumentReview onConfirm={() => {}} onAmend={() => {}} />);
    expect(
      screen.getByRole("heading", { name: /Iată cererea ta\. E corect totul\?/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Popescu Ana-Maria")).toBeInTheDocument();
    expect(screen.getByText("2940413081265")).toBeInTheDocument();
    expect(screen.getByText("Banca Transilvania — Cluj Centru")).toBeInTheDocument();
  });

  it("calls onConfirm when 'Da, e corect' clicked", () => {
    const onConfirm = vi.fn();
    render(<DocumentReview onConfirm={onConfirm} onAmend={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Da, e corect/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("calls onAmend when 'Mai am o corectură' clicked", () => {
    const onAmend = vi.fn();
    render(<DocumentReview onConfirm={() => {}} onAmend={onAmend} />);
    fireEvent.click(screen.getByRole("button", { name: /Mai am o corectură/i }));
    expect(onAmend).toHaveBeenCalledTimes(1);
  });
});
