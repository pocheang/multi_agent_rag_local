import { afterEach, describe, expect, it, vi } from "vitest";
import { sessionApi } from "./session-api";

describe("session API contract", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renames a session with an encoded PATCH request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ session_id: "folder/name" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await sessionApi.sessionRename("folder/name", "New title");

    expect(fetchMock).toHaveBeenCalledWith(
      "/sessions/folder%2Fname",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ title: "New title" }),
        credentials: "include",
      }),
    );
  });

  it("uses the shared API error path when rename is rejected", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "rename rejected" }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(sessionApi.sessionRename("session-1", "Conflict")).rejects.toMatchObject({
      name: "ApiError",
      status: 409,
      message: "rename rejected",
    });
  });
});
