export type ExecutionStage = "route" | "plan" | "rag" | "tool" | "synthesize" | "complete" | "failed";

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
  const stages: ExecutionStage[] = ["route", "plan", "rag", "tool", "synthesize", "complete", "failed"];
  const statuses: ExecutionStatus[] = ["completed", "failed", "skipped"];

  return hasExactKeys(event, ["version", "stage", "status", "duration_ms", "message", "metadata", "occurred_at"])
    && event.version === "1"
    && typeof event.stage === "string" && stages.includes(event.stage as ExecutionStage)
    && typeof event.status === "string" && statuses.includes(event.status as ExecutionStatus)
    && typeof event.duration_ms === "number" && Number.isFinite(event.duration_ms) && event.duration_ms >= 0
    && typeof event.message === "string" && typeof event.occurred_at === "string"
    && Array.isArray(event.metadata) && event.metadata.every(isExecutionMetadataItem);
}

function isExecutionMetadataItem(value: unknown): value is ExecutionMetadataItem {
  return !!value && typeof value === "object"
    && hasExactKeys(value as Record<string, unknown>, ["key", "value"])
    && typeof (value as Record<string, unknown>).key === "string"
    && typeof (value as Record<string, unknown>).value === "string";
}

function hasExactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value);
  return actual.length === keys.length && keys.every((key) => Object.prototype.hasOwnProperty.call(value, key));
}
