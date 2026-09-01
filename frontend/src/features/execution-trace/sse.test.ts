import { describe, expect, it } from "vitest";

import { parseAnswerFragmentSse, parseExecutionEventSse } from "./sse";
import { initialExecutionTraceState, reduceExecutionTrace } from "./state";

/**
 * One subscription carries two things: stage events and the answer as it is
 * written. They are separate SSE event names on purpose -- a draft carries no
 * citation numbering and no reference list, both of which the server decides
 * only once the whole answer exists, so a client must not be able to mistake
 * one for a finished answer.
 */
describe("answer fragment frames", () => {
  const frame = (text: string) => `event: answer_fragment\ndata: ${JSON.stringify({ text })}\n\n`;

  it("parses a fragment", () => {
    expect(parseAnswerFragmentSse(frame("Revenue grew"))).toBe("Revenue grew");
  });

  it("is not confused with an execution event", () => {
    const event = `event: execution_event\ndata: ${JSON.stringify({
      version: "1",
      stage: "synthesize",
      status: "completed",
      duration_ms: 1,
      message: "",
      metadata: [],
      occurred_at: "2026-08-30T00:00:00Z",
    })}\n\n`;

    expect(parseAnswerFragmentSse(event)).toBeNull();
    expect(parseExecutionEventSse(frame("x"))).toBeNull();
  });

  it("ignores a frame whose payload is not a fragment", () => {
    expect(parseAnswerFragmentSse(`event: answer_fragment\ndata: {"nope":1}\n\n`)).toBeNull();
    expect(parseAnswerFragmentSse(`event: answer_fragment\ndata: not json\n\n`)).toBeNull();
  });

  it("keeps an empty fragment distinguishable from a missing one", () => {
    expect(parseAnswerFragmentSse(frame(""))).toBe("");
  });
});

describe("draft accumulation", () => {
  it("appends fragments in arrival order", () => {
    let state = initialExecutionTraceState;
    for (const text of ["Revenue ", "grew ", "twelve percent."]) {
      state = reduceExecutionTrace(state, { type: "answer_fragment", text });
    }

    expect(state.draft).toBe("Revenue grew twelve percent.");
  });

  it("clears on a new run so one answer never bleeds into the next", () => {
    const written = reduceExecutionTrace(initialExecutionTraceState, {
      type: "answer_fragment",
      text: "first answer",
    });

    expect(reduceExecutionTrace(written, { type: "execution_started" }).draft).toBe("");
  });

  it("keeps events and draft independent", () => {
    const state = reduceExecutionTrace(
      reduceExecutionTrace(initialExecutionTraceState, { type: "answer_fragment", text: "draft" }),
      {
        type: "event_received",
        event: {
          version: "1",
          stage: "synthesize",
          status: "completed",
          duration_ms: 1,
          message: "",
          metadata: [],
          occurred_at: "2026-08-30T00:00:00Z",
        },
      },
    );

    expect(state.draft).toBe("draft");
    expect(state.events).toHaveLength(1);
  });
});
