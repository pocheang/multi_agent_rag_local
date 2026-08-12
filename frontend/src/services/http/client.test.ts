import { afterEach, describe, expect, it, vi } from "vitest";
import { authFetch, request } from "./client";

describe("HTTP client errors and cancellation", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("turns a string error detail into an ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Not found" }), { status: 404 })));

    await expect(request("/documents/missing")).rejects.toMatchObject({ status: 404, message: "Not found" });
  });

  it("preserves a successful JSON array response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([{ session_id: "s1" }]), { status: 200 })));

    await expect(request<Array<{ session_id: string }>>("/sessions")).resolves.toEqual([{ session_id: "s1" }]);
  });

  it("turns validation items into a safe validation message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ loc: ["body", "query"], msg: "field required", type: "missing" }] }), { status: 422 })));

    await expect(request("/query")).rejects.toMatchObject({ status: 422, message: "Invalid request: field required" });
  });

  it("preserves plain-text error messages", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Service unavailable", { status: 500 })));

    await expect(request("/query")).rejects.toMatchObject({ status: 500, message: "Service unavailable" });
  });

  it.each([401, 403])("preserves authentication status %i", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Access denied" }), { status })));

    await expect(request("/protected")).rejects.toMatchObject({ status, message: "Access denied" });
  });

  it("times out a normal request", async () => {
    vi.stubGlobal("fetch", vi.fn((_url: string, init?: RequestInit) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    })));

    await expect(request("/slow", {}, { timeoutMs: 5 })).rejects.toMatchObject({ status: 408, message: "Request timed out" });
  });

  it("keeps a caller abort distinguishable from a timeout", async () => {
    const controller = new AbortController();
    vi.stubGlobal("fetch", vi.fn((_url: string, init?: RequestInit) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    })));
    const pending = authFetch("/query/stream", { signal: controller.signal }, { timeoutMs: 100 });
    controller.abort();

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });
});
