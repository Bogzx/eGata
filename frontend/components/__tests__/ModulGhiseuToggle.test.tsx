import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ModulGhiseuToggle } from "../ModulGhiseuToggle";
import { GHISEU_PREF_KEY } from "@/lib/ghiseuPref";

beforeEach(() => {
  localStorage.clear();
});

describe("ModulGhiseuToggle", () => {
  it("renders the Romanian label and hint", () => {
    render(<ModulGhiseuToggle />);
    expect(screen.getByText(/Modul Ghișeu/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Doar vorbește cu asistentul/i),
    ).toBeInTheDocument();
  });

  it("starts off (aria-checked=false) when no preference is stored", () => {
    render(<ModulGhiseuToggle />);
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false");
  });

  it("initializes from existing preference", () => {
    localStorage.setItem(GHISEU_PREF_KEY, "1");
    render(<ModulGhiseuToggle />);
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });

  it("persists to localStorage when toggled", () => {
    render(<ModulGhiseuToggle />);
    fireEvent.click(screen.getByRole("switch"));
    expect(localStorage.getItem(GHISEU_PREF_KEY)).toBe("1");
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getByRole("switch"));
    expect(localStorage.getItem(GHISEU_PREF_KEY)).toBe("0");
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false");
  });
});
