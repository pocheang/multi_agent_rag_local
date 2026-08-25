// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { applyLightTheme } from "@/lib/theme";

describe("light-only theme", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("applies light mode and clears a previously saved dark preference", () => {
    localStorage.setItem("theme_preference", "dark");

    applyLightTheme();

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("theme_preference")).toBeNull();
  });

  it("still applies light mode when storage access is blocked", () => {
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new DOMException("Storage is blocked", "SecurityError");
    });

    expect(() => applyLightTheme()).not.toThrow();
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
