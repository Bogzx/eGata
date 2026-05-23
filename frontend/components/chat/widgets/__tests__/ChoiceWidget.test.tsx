import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChoiceWidget } from "../ChoiceWidget";

describe("ChoiceWidget", () => {
  const spec = {
    type: "choice" as const,
    question: "Cum locuiești?",
    options: ["Proprietar", "Chiriaș", "Găzduit"],
    targetField: "tip_locuinta",
    widgetId: "w1",
  };

  it("renders question and options", () => {
    render(<ChoiceWidget spec={spec} onSubmit={() => {}} />);
    expect(screen.getByText("Cum locuiești?")).toBeInTheDocument();
    expect(screen.getByText("Proprietar")).toBeInTheDocument();
    expect(screen.getByText("Chiriaș")).toBeInTheDocument();
    expect(screen.getByText("Găzduit")).toBeInTheDocument();
  });

  it("calls onSubmit once with the picked value and disables after click", () => {
    const onSubmit = vi.fn();
    render(<ChoiceWidget spec={spec} onSubmit={onSubmit} />);
    const btn = screen.getByText("Chiriaș");
    fireEvent.click(btn);
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("Chiriaș");
    // Second click on a different option should be a no-op (disabled).
    fireEvent.click(screen.getByText("Proprietar"));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
