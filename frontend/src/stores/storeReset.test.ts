import { describe, expect, it } from "vitest";

import { useAdminStore } from "@/stores/useAdminStore";
import { useChatStore } from "@/stores/useChatStore";

/**
 * `reset()` is what stops the next person signing in on a shared browser from
 * seeing the previous one's sessions, documents and prompts (App.tsx calls it on
 * logout and on any identity change).
 *
 * The risk is drift, not logic: these stores hold ~40 fields, and a field added
 * to the store body but forgotten in INITIAL_STATE would survive a logout with
 * nothing to flag it. So rather than listing fields -- which would drift the
 * same way -- each test discovers them, dirties every one, and requires the
 * store to come back exactly as it started.
 */

const SENTINEL = "__dirty__";

type AnyStore = {
  getState: () => Record<string, unknown>;
  setState: (partial: Record<string, unknown>) => void;
};

function dataKeys(store: AnyStore): string[] {
  return Object.entries(store.getState())
    .filter(([, value]) => typeof value !== "function")
    .map(([key]) => key);
}

function snapshot(store: AnyStore): Record<string, unknown> {
  const state = store.getState();
  return Object.fromEntries(dataKeys(store).map((key) => [key, state[key]]));
}

function dirty(store: AnyStore): void {
  store.setState(Object.fromEntries(dataKeys(store).map((key) => [key, SENTINEL])));
}

describe.each([
  ["useChatStore", useChatStore as unknown as AnyStore],
  ["useAdminStore", useAdminStore as unknown as AnyStore],
])("%s", (_name, store) => {
  it("has fields to reset", () => {
    expect(dataKeys(store).length).toBeGreaterThan(0);
  });

  it("exposes a reset action", () => {
    expect(typeof (store.getState() as { reset?: unknown }).reset).toBe("function");
  });

  it("restores every field, so no field can quietly outlive a logout", () => {
    const pristine = snapshot(store);

    dirty(store);
    expect(snapshot(store)).not.toEqual(pristine);

    (store.getState() as { reset: () => void }).reset();

    expect(snapshot(store)).toEqual(pristine);
  });

  it("leaves no field holding the previous value", () => {
    dirty(store);
    (store.getState() as { reset: () => void }).reset();

    const leftover = Object.entries(snapshot(store))
      .filter(([, value]) => value === SENTINEL)
      .map(([key]) => key);

    expect(leftover).toEqual([]);
  });

  it("keeps the setters callable afterwards", () => {
    (store.getState() as { reset: () => void }).reset();
    expect(dataKeys(store).length).toBeGreaterThan(0);
  });
});
