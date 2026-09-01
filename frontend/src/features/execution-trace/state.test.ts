import { describe, expect, it } from "vitest";

import { initialExecutionTraceState, reduceExecutionTrace } from "./state";

/**
 * This reducer used to live in `features/tool-approval/state.ts` and carry the
 * pending approval, which inverted the dependency (the trace panel imported its
 * own state from the approval feature) and gave the app two sources of truth for
 * a pending approval: the SSE event and the query response.
 *
 * Only the response path knows the question, and resuming means re-sending that
 * question with the approved token -- so the response is the source of truth and
 * this reducer is back to owning only what it is named for.
 */
describe("execution trace state", () => {
  const event = {
    version: "1",
    stage: "tool",
    status: "skipped",
    duration_ms: 0,
    message: "approval required",
    metadata: [{ key: "approval_request_id", value: "t".repeat(64) }],
    occurred_at: "2026-08-30T00:00:00Z",
  };

  it("accumulates execution events", () => {
    const next = reduceExecutionTrace(initialExecutionTraceState, { type: "event_received", event });

    expect(next.events).toHaveLength(1);
    expect(next.events[0].stage).toBe("tool");
  });

  it("ignores anything that is not an execution event", () => {
    const next = reduceExecutionTrace(initialExecutionTraceState, {
      type: "event_received",
      event: { nonsense: true },
    });

    expect(next.events).toHaveLength(0);
  });

  it("clears on a new run so one run's trace never bleeds into the next", () => {
    const withEvent = reduceExecutionTrace(initialExecutionTraceState, { type: "event_received", event });

    expect(reduceExecutionTrace(withEvent, { type: "execution_started" }).events).toHaveLength(0);
  });

  it("no longer carries approval state", () => {
    const next = reduceExecutionTrace(initialExecutionTraceState, { type: "event_received", event });

    expect(next).not.toHaveProperty("pendingApproval");
  });
});
