// Mirrors EventStage in app/domain/events.py. Keep both lists in sync: an
// unknown stage makes isExecutionEvent reject the event and the UI silently
// drops it.
export const EXECUTION_STAGES = [
  "privacy_permission",
  "route",
  "plan",
  "knowledge_strategy",
  "knowledge",
  "rag",
  "tool",
  "synthesize",
  "verifier",
  "finalize",
  "output_filter",
  "complete",
  "failed",
] as const;

export type ExecutionStage = (typeof EXECUTION_STAGES)[number];

export type ExecutionStatus = "completed" | "failed" | "skipped";

export type ExecutionMetadataItem = {
  key: string;
  value: string;
};

export type ExecutionEvent = {
  version: "1";
  stage: ExecutionStage;
  status: ExecutionStatus;
  duration_ms: number;
  message: string;
  metadata: ExecutionMetadataItem[];
  occurred_at: string;
};

export function isExecutionEvent(value: unknown): value is ExecutionEvent {
  if (!value || typeof value !== "object") return false;
  const event = value as Record<string, unknown>;
  const statuses: ExecutionStatus[] = ["completed", "failed", "skipped"];

  return hasKeys(event, ["version", "stage", "status", "duration_ms", "message", "metadata", "occurred_at"])
    && event.version === "1"
    && typeof event.stage === "string" && EXECUTION_STAGES.includes(event.stage as ExecutionStage)
    && typeof event.status === "string" && statuses.includes(event.status as ExecutionStatus)
    && typeof event.duration_ms === "number" && Number.isFinite(event.duration_ms) && event.duration_ms >= 0
    && typeof event.message === "string" && typeof event.occurred_at === "string"
    && Array.isArray(event.metadata) && event.metadata.every(isExecutionMetadataItem);
}

function isExecutionMetadataItem(value: unknown): value is ExecutionMetadataItem {
  return !!value && typeof value === "object"
    && hasKeys(value as Record<string, unknown>, ["key", "value"])
    && typeof (value as Record<string, unknown>).key === "string"
    && typeof (value as Record<string, unknown>).value === "string";
}

// Required fields must be present and well-typed, but extra ones are allowed:
// demanding an exact key set meant any field added to the backend
// ExecutionEvent would make the UI discard every event, not just misread one.
function hasKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return keys.every((key) => Object.prototype.hasOwnProperty.call(value, key));
}
