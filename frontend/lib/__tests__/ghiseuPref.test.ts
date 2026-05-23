import { describe, it, expect, beforeEach } from "vitest";
import { getGhiseuPref, setGhiseuPref, GHISEU_PREF_KEY } from "../ghiseuPref";

beforeEach(() => {
  localStorage.clear();
});

describe("ghiseuPref", () => {
  it("returns false when no preference is stored", () => {
    expect(getGhiseuPref()).toBe(false);
  });

  it("returns true after setGhiseuPref(true)", () => {
    setGhiseuPref(true);
    expect(getGhiseuPref()).toBe(true);
    expect(localStorage.getItem(GHISEU_PREF_KEY)).toBe("1");
  });

  it("returns false after setGhiseuPref(false)", () => {
    setGhiseuPref(true);
    setGhiseuPref(false);
    expect(getGhiseuPref()).toBe(false);
    expect(localStorage.getItem(GHISEU_PREF_KEY)).toBe("0");
  });

  it("treats any other stored value as false", () => {
    localStorage.setItem(GHISEU_PREF_KEY, "garbage");
    expect(getGhiseuPref()).toBe(false);
  });
});
