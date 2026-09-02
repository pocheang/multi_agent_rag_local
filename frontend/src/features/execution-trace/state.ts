import { isExecutionEvent, type ExecutionEvent } from "./types";

export type { ExecutionEvent } from "./types";

export type ExecutionTraceState = {
  events: readonly ExecutionEvent[];
  /** The answer as it is being written. Server-side redacted, but a *draft*:
   *  no citation numbering and no reference list, both of which are decided
   *  once the whole answer exists. Replaced by the final answer on completion. */
  draft: string;
};

export const initialExecutionTraceState: ExecutionTraceState = { events: [], draft: "" };

export type ExecutionTraceAction =
  | { type: "execution_started" }
  | { type: "event_received"; event: unknown }
  | { type: "answer_fragment"; text: string };

export function reduceExecutionTrace(
  state: ExecutionTraceState,
  action: ExecutionTraceAction,
): ExecutionTraceState {
  if (action.type === "execution_started") return initialExecutionTraceState;
  if (action.type === "answer_fragment") return { ...state, draft: state.draft + action.text };
  if (!isExecutionEvent(action.event)) return state;
  return { ...state, events: [...state.events, action.event] };
}
