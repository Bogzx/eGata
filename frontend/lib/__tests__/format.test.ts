import { describe, it, expect } from "vitest";
import { formatValue } from "../format";

describe("formatValue", () => {
  it("renders null and undefined as the em dash placeholder", () => {
    expect(formatValue(null)).toBe("—");
    expect(formatValue(undefined)).toBe("—");
  });

  it("renders empty string as the em dash placeholder", () => {
    expect(formatValue("")).toBe("—");
  });

  it("renders booleans as Da/Nu", () => {
    expect(formatValue(true)).toBe("Da");
    expect(formatValue(false)).toBe("Nu");
  });

  it("renders ISO dates as DD.MM.YYYY", () => {
    expect(formatValue("2026-05-24")).toBe("24.05.2026");
    expect(formatValue("2026-01-09")).toBe("09.01.2026");
  });

  it("renders ISO datetimes by dropping the time portion", () => {
    expect(formatValue("2026-05-24T12:00:00Z")).toBe("24.05.2026");
  });

  it("passes through plain strings", () => {
    expect(formatValue("Maria Ionescu")).toBe("Maria Ionescu");
    expect(formatValue("2851014123456")).toBe("2851014123456");
  });

  it("coerces numbers via String()", () => {
    expect(formatValue(42)).toBe("42");
    expect(formatValue(3.14)).toBe("3.14");
  });
});
