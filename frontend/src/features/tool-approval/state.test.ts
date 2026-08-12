import { describe, expect, it } from "vitest";

import { initialExecutionTraceState, reduceExecutionEvent, reduceExecutionTrace } from "./state";

describe("reduceExecutionEvent", () => {
  it("adds a tool approval event to visible state", () => {
    const next = reduceExecutionEvent(initialExecutionTraceState, {
      version: "1",
      stage: "tool",
      status: "completed",
      duration_ms: 4,
      message: "approval required",
      metadata: [{ key: "approval_request_id", value: "token-123" }],
      occurred_at: "2026-08-06T00:00:00Z",
    });

    expect(next.pendingApproval?.token).toBe("token-123");
  });

  it("ignores an unknown event without mutating state", () => {
    expect(reduceExecutionEvent(initialExecutionTraceState, { version: "2" })).toBe(initialExecutionTraceState);
  });

  it.each([
    { version: "1", stage: "unknown", status: "completed", duration_ms: 0, message: "", metadata: [], occurred_at: "2026-08-06T00:00:00Z" },
    { version: "1", stage: "rag", status: "unknown", duration_ms: 0, message: "", metadata: [], occurred_at: "2026-08-06T00:00:00Z" },
    { version: "1", stage: "rag", status: "completed", duration_ms: 0, message: "", metadata: [{ key: "approval_request_id" }], occurred_at: "2026-08-06T00:00:00Z" },
  ])("keeps state identity for malformed version-1 input", (event) => {
    expect(reduceExecutionEvent(initialExecutionTraceState, event)).toBe(initialExecutionTraceState);
  });

  it("clears the previous trace on a new execution and clears a resolved approval", () => {
    const withApproval = reduceExecutionEvent(initialExecutionTraceState, {
      version: "1",
      stage: "tool",
      status: "skipped",
      duration_ms: 4,
      message: "approval required",
      metadata: [{ key: "approval_request_id", value: "request-123" }],
      occurred_at: "2026-08-06T00:00:00Z",
    });

    expect(reduceExecutionTrace(withApproval, { type: "approval_resolved" })).toEqual({
      events: withApproval.events,
      pendingApproval: null,
    });
    expect(reduceExecutionTrace(withApproval, { type: "execution_started" })).toBe(initialExecutionTraceState);
  });
});
