import { describe, expect, it } from "vitest";
import { sessionApi } from "./session-api";

describe("session API contract", () => {
  it("does not expose an unsupported session rename request", () => {
    expect("sessionRename" in sessionApi).toBe(false);
  });
});
