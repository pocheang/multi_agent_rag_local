import { isExecutionEvent, type ExecutionEvent } from "../execution-trace/types";

export type { ExecutionEvent } from "../execution-trace/types";

export type PendingApproval = {
  token: string;
  message: string;
};

export type ExecutionTraceState = {
  events: readonly ExecutionEvent[];
  pendingApproval: PendingApproval | null;
};

export const initialExecutionTraceState: ExecutionTraceState = {
  events: [],
  pendingApproval: null,
};

export type ExecutionTraceAction =
  | { type: "execution_started" }
  | { type: "event_received"; event: unknown }
  | { type: "approval_resolved" };

export function reduceExecutionTrace(
  state: ExecutionTraceState,
  action: ExecutionTraceAction,
): ExecutionTraceState {
  if (action.type === "execution_started") return initialExecutionTraceState;
  if (action.type === "approval_resolved") return { ...state, pendingApproval: null };
  return reduceExecutionEvent(state, action.event);
}

export function reduceExecutionEvent(
  state: ExecutionTraceState,
  input: unknown,
): ExecutionTraceState {
  if (!isExecutionEvent(input)) return state;

  const token = input.metadata.find((item) => item.key === "approval_request_id")?.value;
  return {
    events: [...state.events, input],
    pendingApproval: input.stage === "tool" && input.message === "approval required" && token
      ? { token, message: input.message }
      : state.pendingApproval,
  };
}
