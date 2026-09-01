import { useEffect, useReducer } from "react";

import { initialExecutionTraceState, reduceExecutionTrace } from "./state";
import { streamExecutionEvents } from "@/services/execution/execution-api";

export function useExecutionTrace(executionId: string | null) {
  const [state, dispatch] = useReducer(reduceExecutionTrace, initialExecutionTraceState);

  useEffect(() => {
    // Reset state when executionId becomes null (query starting)
    if (!executionId) {
      dispatch({ type: "execution_started" });
      return;
    }

    // Start streaming when we have an executionId
    const controller = new AbortController();
    void streamExecutionEvents(
      executionId,
      controller.signal,
      (event) => dispatch({ type: "event_received", event }),
      (text) => dispatch({ type: "answer_fragment", text }),
    );
    return () => controller.abort();
  }, [executionId]);

  return state;
}
