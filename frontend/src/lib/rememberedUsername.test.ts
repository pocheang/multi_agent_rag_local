/**
 * Remembering a username must never be able to fail a login.
 *
 * The implementation this replaced XORed the name against a hardcoded key and
 * base64'd it. `btoa` throws above code unit 255, so a Chinese username threw
 * inside the login handler's `try` before `onLogin` ran: the server had accepted
 * the credentials and the app reported a login failure anyway. Ticking "remember
 * me" made signing in impossible for anyone whose name is not Latin-1.
 *
 * The first two tests are that bug. The rest are the storage failures a browser
 * can hand you at any time -- a private window, blocked site data -- which are
 * the other way this could turn a convenience into an error.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  forgetRememberedUsername,
  hasRememberedUsername,
  rememberUsername,
  rememberedUsername,
} from "@/lib/rememberedUsername";

function installStorage(overrides: Partial<Storage> = {}) {
  const entries = new Map<string, string>();
  const storage = {
    getItem: (key: string) => entries.get(key) ?? null,
    setItem: (key: string, value: string) => void entries.set(key, value),
    removeItem: (key: string) => void entries.delete(key),
    ...overrides,
  };
  vi.stubGlobal("localStorage", storage);
  return entries;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("remembering a username", () => {
  it("round-trips a name that is not Latin-1", () => {
    installStorage();

    rememberUsername("张伟");

    expect(rememberedUsername()).toBe("张伟");
    expect(hasRememberedUsername()).toBe(true);
  });

  it("stores the name as itself, not as something only it can read back", () => {
    const entries = installStorage();

    rememberUsername("alice");

    expect(entries.get("remembered_username")).toBe("alice");
  });

  it("clears what the obfuscated version left behind", () => {
    const entries = installStorage();
    entries.set("sec_remembered_username", "Ew0OPAk=");

    rememberUsername("alice");

    expect(entries.has("sec_remembered_username")).toBe(false);
  });

  it("forgets both the current key and the old one", () => {
    const entries = installStorage();
    entries.set("remembered_username", "alice");
    entries.set("sec_remembered_username", "Ew0OPAk=");

    forgetRememberedUsername();

    expect(entries.size).toBe(0);
    expect(hasRememberedUsername()).toBe(false);
  });

  it("reports no name rather than throwing when storage cannot be read", () => {
    installStorage({
      getItem: () => {
        throw new Error("The operation is insecure.");
      },
    });

    expect(rememberedUsername()).toBe("");
    expect(hasRememberedUsername()).toBe(false);
  });

  it("swallows a storage write that fails, because a login must not fail with it", () => {
    installStorage({
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
    });

    expect(() => rememberUsername("alice")).not.toThrow();
    expect(() => forgetRememberedUsername()).not.toThrow();
  });

  it("returns nothing when there is no storage at all", () => {
    vi.stubGlobal("localStorage", undefined);

    expect(rememberedUsername()).toBe("");
    expect(() => rememberUsername("alice")).not.toThrow();
  });
});
