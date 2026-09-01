import { describe, expect, it } from "vitest";

import type { NormalizedQueryResult, PendingApproval } from "@/types/api";

/**
 * Confirming an approval re-sends the question that produced it. The question
 * and the approval therefore have to travel together.
 *
 * They did not at first: ChatPage tracked the question in a ref that each `ask`
 * call site had to remember to set, and one of the three -- the
 * clarification-complete path -- did not. A confirmation after a clarified
 * query would have re-sent a stale question, executing the approved action
 * against text the user never asked about in that turn.
 *
 * The pairing now comes out of the run itself (`onPendingApproval(approval,
 * question)`), which is what these tests pin: given a result, what the caller
 * should hold.
 */

type Held = { approval: PendingApproval; question: string } | null;

/** The rule ChatPage applies to every completed run. */
function holdFor(result: NormalizedQueryResult, question: string): Held {
  return result.status === "pending_approval" && result.pendingApproval
    ? { approval: result.pendingApproval, question }
    : null;
}

const approval: PendingApproval = {
  tool_id: "querymind_connector_disable_owned",
  token: "t".repeat(64),
  summary: "needs confirmation",
};

function result(overrides: Partial<NormalizedQueryResult> = {}): NormalizedQueryResult {
  return {
    answer: "…",
    citations: [],
    status: "complete",
    pendingApproval: null,
    toolRuns: [],
    ...overrides,
  };
}

describe("pending approval pairing", () => {
  it("keeps the question that produced the approval", () => {
    const held = holdFor(result({ status: "pending_approval", pendingApproval: approval }), "disable slack");

    expect(held).toEqual({ approval, question: "disable slack" });
  });

  it("pairs with the clarified question, not an earlier one", () => {
    const first = holdFor(result(), "what can you do?");
    const second = holdFor(
      result({ status: "pending_approval", pendingApproval: approval }),
      "disable slack\n\nConfirmed constraints:\n- scenario: enterprise",
    );

    expect(first).toBeNull();
    expect(second?.question).toContain("Confirmed constraints");
  });

  it("holds nothing when the run completed", () => {
    expect(holdFor(result(), "disable slack")).toBeNull();
  });

  it("holds nothing when the status says pending but no approval came with it", () => {
    expect(holdFor(result({ status: "pending_approval" }), "disable slack")).toBeNull();
  });

  it("clears the previous hold once the resumed run reports complete", () => {
    const held = holdFor(result({ status: "pending_approval", pendingApproval: approval }), "disable slack");
    const afterResume = holdFor(result(), "disable slack");

    expect(held).not.toBeNull();
    expect(afterResume).toBeNull();
  });
});
