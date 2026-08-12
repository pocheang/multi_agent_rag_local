import { describe, expect, it } from "vitest";
import { parseStreamError } from "./streamUtils";

describe("stream error parsing", () => {
  it("normalizes FastAPI validation details without exposing objects", () => {
    expect(parseStreamError(JSON.stringify({ detail: [{ loc: ["body", "question"], msg: "field required", type: "missing" }] }))).toBe("Invalid request: field required");
  });

  it("preserves plain text and string details", () => {
    expect(parseStreamError("upstream unavailable")).toBe("upstream unavailable");
    expect(parseStreamError(JSON.stringify({ detail: "Access denied" }))).toBe("Access denied");
  });
});
