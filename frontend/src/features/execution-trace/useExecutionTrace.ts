import { useEffect, useReducer } from "react";

import { initialExecutionTraceState, reduceExecutionTrace } from "../tool-approval/state";
import { streamExecutionEvents } from "@/services/execution/execution-api";

export function useExecutionTrace(executionId: string | null) {
  const [state, dispatch] = useReducer(reduceExecutionTrace, initialExecutionTraceState);

  useEffect(() => {
    dispatch({ type: "execution_started" });
    if (!executionId) return;
    const controller = new AbortController();
    void streamExecutionEvents(executionId, controller.signal, (event) => dispatch({ type: "event_received", event }));
    return () => controller.abort();
  }, [executionId]);

  return {
    ...state,
    resolveApproval: () => dispatch({ type: "approval_resolved" }),
  };
}
