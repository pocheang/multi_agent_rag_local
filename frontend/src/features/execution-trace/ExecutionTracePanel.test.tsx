// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExecutionTracePanel } from "./ExecutionTracePanel";
import { initialExecutionTraceState } from "./state";
import type { ExecutionEvent } from "./types";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) => {
      if (key === "features.executionTrace.hide") return "Hide";
      if (key === "features.executionTrace.show") return "Show";
      if (key === "features.executionTrace.count") return `${options?.count} steps`;
      if (key === "features.executionTrace.event") return `${options?.stage}: ${options?.message}`;
      return (options?.defaultValue as string) ?? key;
    },
  }),
}));

const event = (stage: string): ExecutionEvent => ({
  version: "1",
  stage: stage as ExecutionEvent["stage"],
  status: "completed",
  duration_ms: 1,
  message: "",
  metadata: [],
  occurred_at: `2026-08-31T00:00:0${stage.length}Z`,
});

const trace = { ...initialExecutionTraceState, events: [event("route"), event("knowledge")] };

beforeEach(() => window.localStorage.clear());
afterEach(cleanup);

describe("collapsing the trace", () => {
  it("starts open", () => {
    render(<ExecutionTracePanel trace={trace} />);

    expect(screen.getByRole("button", { name: "Hide" }).getAttribute("aria-expanded")).toBe("true");
  });

  it("hides the events without unmounting them", () => {
    render(<ExecutionTracePanel trace={trace} />);
    fireEvent.click(screen.getByRole("button", { name: "Hide" }));

    const button = screen.getByRole("button", { name: "Show" });
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(document.getElementById("execution-trace-events")?.hasAttribute("hidden")).toBe(true);
  });

  it("shows the step count while collapsed", () => {
    /** Collapsed must not read as "nothing happened". */
    render(<ExecutionTracePanel trace={trace} />);
    fireEvent.click(screen.getByRole("button", { name: "Hide" }));

    expect(screen.getByText("2 steps")).toBeTruthy();
  });

  it("does not claim a step count when there are no events", () => {
    render(<ExecutionTracePanel trace={initialExecutionTraceState} />);
    fireEvent.click(screen.getByRole("button", { name: "Hide" }));

    expect(screen.queryByText(/steps/)).toBeNull();
  });
});

describe("remembering the choice", () => {
  it("survives a remount", () => {
    /** The panel unmounts between questions, so component state alone would
     *  re-open it on every turn and make the button useless. */
    render(<ExecutionTracePanel trace={trace} />);
    fireEvent.click(screen.getByRole("button", { name: "Hide" }));
    cleanup();

    render(<ExecutionTracePanel trace={trace} />);
    expect(screen.getByRole("button", { name: "Show" })).toBeTruthy();
  });

  it("reopens after the choice is reversed", () => {
    render(<ExecutionTracePanel trace={trace} />);
    fireEvent.click(screen.getByRole("button", { name: "Hide" }));
    fireEvent.click(screen.getByRole("button", { name: "Show" }));
    cleanup();

    render(<ExecutionTracePanel trace={trace} />);
    expect(screen.getByRole("button", { name: "Hide" })).toBeTruthy();
  });

  it("still renders when storage is unavailable", () => {
    /** A private window, cleared site data, or a browser set to block storage
     *  all throw here, and none is a reason to fail to render a trace. */
    const storage = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });
    const setter = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });

    render(<ExecutionTracePanel trace={trace} />);
    fireEvent.click(screen.getByRole("button", { name: "Hide" }));

    expect(screen.getByRole("button", { name: "Show" })).toBeTruthy();
    storage.mockRestore();
    setter.mockRestore();
  });
});
