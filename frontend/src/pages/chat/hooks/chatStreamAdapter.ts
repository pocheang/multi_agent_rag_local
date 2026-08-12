import { isExecutionEvent, type ExecutionEvent } from "../../../features/execution-trace/types";

export type LegacyChatStreamEventType =
  | "execution_started"
  | "status"
  | "route"
  | "thought"
  | "error"
  | "vector_result"
  | "graph_result"
  | "web_result"
  | "answer_chunk"
  | "answer_reset"
  | "done"
  | "stream_end";

export type LegacyChatStreamEvent = {
  type: LegacyChatStreamEventType;
  [key: string]: unknown;
};

export type ExecutionEnvelopeEvent = {
  type: "execution_event";
  event: ExecutionEvent;
};

export type ChatStreamEvent = LegacyChatStreamEvent | ExecutionEnvelopeEvent;

const LEGACY_EVENT_TYPES: readonly LegacyChatStreamEventType[] = [
  "execution_started",
  "status",
  "route",
  "thought",
  "error",
  "vector_result",
  "graph_result",
  "web_result",
  "answer_chunk",
  "answer_reset",
  "done",
  "stream_end",
];

export function parseChatStreamFrame(frame: string): ChatStreamEvent | null {
  const data = frame
    .replace(/\r\n/g, "\n")
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice("data:".length).replace(/^ /, ""))
    .join("\n");
  if (!data) return null;
  try {
    const value: unknown = JSON.parse(data);
    if (isExecutionEvent(value)) return { type: "execution_event", event: value };
    return parseLegacyChatStreamEvent(value);
  } catch {
    return null;
  }
}

function parseLegacyChatStreamEvent(value: unknown): LegacyChatStreamEvent | null {
  if (!value || typeof value !== "object") return null;
  const event = value as Record<string, unknown>;
  const type = event.type;
  if (typeof type !== "string" || !LEGACY_EVENT_TYPES.includes(type as LegacyChatStreamEventType)) {
    return null;
  }
  return { ...event, type: type as LegacyChatStreamEventType };
}

function executionId(event: ExecutionEvent): string | null {
  return event.metadata.find((item) => item.key === "execution_id")?.value ?? null;
}

export async function consumeChatStream(
  response: Response,
  options: { signal: AbortSignal; onEvent: (event: ChatStreamEvent) => void },
): Promise<{ completed: boolean; executionId: string | null }> {
  if (!response.body) throw new Error("Stream response has no body");
  if (options.signal.aborted) return { completed: false, executionId: null };

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let completed = false;
  let latestExecutionId: string | null = null;
  let disposed = false;
  const cancelReader = () => {
    disposed = true;
    void reader.cancel();
  };
  options.signal.addEventListener("abort", cancelReader, { once: true });

  const handleFrame = (frame: string) => {
    if (disposed || options.signal.aborted) return;
    const event = parseChatStreamFrame(frame);
    if (!event) return;
    if (event.type === "execution_event") {
      latestExecutionId = executionId(event.event) ?? latestExecutionId;
      if (event.event.status === "failed") throw new Error(event.event.message || "stream error");
      if (event.event.stage === "complete" && event.event.status === "completed") completed = true;
    }
    options.onEvent(event);
  };

  try {
    while (!options.signal.aborted) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() ?? "";
      frames.forEach(handleFrame);
    }
    buffer += decoder.decode();
    if (!options.signal.aborted && buffer.trim()) handleFrame(buffer);
    if (options.signal.aborted) return { completed: false, executionId: latestExecutionId };
    if (!completed) throw new Error("Stream ended before completion");
    return { completed, executionId: latestExecutionId };
  } finally {
    disposed = true;
    options.signal.removeEventListener("abort", cancelReader);
    try {
      await reader.cancel();
    } catch {
      // The stream may already be closed.
    }
    reader.releaseLock();
  }
}

export type ChatRunToken = number;

export function createChatRunLifecycle() {
  let mounted = true;
  let activeRun: ChatRunToken | null = null;
  let nextRun = 0;
  return {
    mount(): void {
      mounted = true;
    },
    begin(): ChatRunToken | null {
      if (!mounted || activeRun !== null) return null;
      activeRun = ++nextRun;
      return activeRun;
    },
    isActive(run: ChatRunToken): boolean {
      return mounted && activeRun === run;
    },
    stop(run: ChatRunToken): void {
      if (activeRun === run) activeRun = null;
    },
    dispose(): void {
      mounted = false;
      activeRun = null;
    },
  };
}
