import { authFetch } from "@/services/http/client";
import type { ExecutionEvent } from "@/features/execution-trace/types";
import { consumeExecutionEventStream } from "@/features/execution-trace/sse";

export async function streamExecutionEvents(
  executionId: string,
  signal: AbortSignal,
  onEvent: (event: ExecutionEvent) => void,
): Promise<void> {
  const response = await authFetch(
    `/api/v1/orchestration/executions/${encodeURIComponent(executionId)}/events`,
    { signal },
  );
  if (!response.ok) return;
  await consumeExecutionEventStream(response, onEvent, signal);
}
