// @vitest-environment jsdom
import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatRuntimePanels } from "./ChatRuntimePanels";

/**
 * The streaming draft is published to the parent from an effect. Depending on
 * the callback itself made an inline arrow -- which is what ChatPage passes -- a
 * new dependency on every render, so publishing a draft re-rendered the parent,
 * which recreated the callback, which re-fired the effect. In the browser that
 * surfaced as "Maximum update depth exceeded" and the chat error boundary
 * replacing the whole conversation with an error card.
 */
let draft = "";

vi.mock("@/features/execution-trace/useExecutionTrace", () => ({
  useExecutionTrace: () => ({ events: [], draft, connected: true, error: null }),
}));
vi.mock("@/features/execution-trace/ExecutionTracePanel", () => ({
  ExecutionTracePanel: () => null,
}));
vi.mock("@/features/tool-approval/ToolApprovalPanel", () => ({
  ToolApprovalPanel: () => null,
}));

afterEach(() => {
  draft = "";
});

const props = {
  executionId: "exec-1",
  pendingApproval: null,
  onApproved: () => {},
  onDismissApproval: () => {},
};

describe("publishing the draft", () => {
  it("does not re-fire when the parent passes a new callback identity", () => {
    const calls: string[] = [];
    const { rerender } = render(<ChatRuntimePanels {...props} onDraft={(t) => calls.push(t)} />);

    // Every rerender passes a *different* arrow, exactly as ChatPage does.
    for (let i = 0; i < 5; i += 1) {
      rerender(<ChatRuntimePanels {...props} onDraft={(t) => calls.push(t)} />);
    }

    expect(calls).toHaveLength(1);
  });

  it("still fires when the draft itself changes", () => {
    const calls: string[] = [];
    const { rerender } = render(<ChatRuntimePanels {...props} onDraft={(t) => calls.push(t)} />);

    draft = "Revenue grew";
    rerender(<ChatRuntimePanels {...props} onDraft={(t) => calls.push(t)} />);
    draft = "Revenue grew twelve percent.";
    rerender(<ChatRuntimePanels {...props} onDraft={(t) => calls.push(t)} />);

    expect(calls).toEqual(["", "Revenue grew", "Revenue grew twelve percent."]);
  });

  it("uses the newest callback, not the one from the first render", () => {
    /** A ref that is never updated would be the other way to break this. */
    const first: string[] = [];
    const latest: string[] = [];
    const { rerender } = render(<ChatRuntimePanels {...props} onDraft={(t) => first.push(t)} />);

    rerender(<ChatRuntimePanels {...props} onDraft={(t) => latest.push(t)} />);
    draft = "written by the newest closure";
    rerender(<ChatRuntimePanels {...props} onDraft={(t) => latest.push(t)} />);

    expect(latest).toContain("written by the newest closure");
    expect(first).toEqual([""]);
  });
});
