import { describe, expect, it } from "vitest";
import { consumeChatStream, createChatRunLifecycle, parseChatStreamFrame } from "./chatStreamAdapter";

const event = (overrides: Record<string, unknown> = {}) => ({
  version: "1", stage: "synthesize", status: "completed", duration_ms: 3, message: "writing",
  metadata: [{ key: "content", value: "Hello" }, { key: "execution_id", value: "run-1" }], occurred_at: "2026-08-11T00:00:00Z", ...overrides,
});

function responseFromChunks(chunks: string[]): Response {
  const encoder = new TextEncoder();
  return new Response(new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  }));
}

describe("versioned chat SSE parsing", () => {
  it("parses data-only v1 frames before legacy events", () => {
    expect(parseChatStreamFrame(`data: ${JSON.stringify(event())}`)).toMatchObject({ type: "execution_event", event: { version: "1" } });
  });

  it("accepts named v1, CRLF, and multiple data lines", () => {
    const payload = JSON.stringify(event()).replace("\"Hello\"", "\"Hel\\nlo\"");
    expect(parseChatStreamFrame(`event: execution_event\r\ndata: ${payload}\r\n`)).toMatchObject({ type: "execution_event" });
  });

  it("keeps legacy frames as backward-compatible input", () => {
    expect(parseChatStreamFrame('event: answer_chunk\ndata: {"type":"answer_chunk","content":"legacy"}')).toEqual({ type: "answer_chunk", content: "legacy" });
  });

  it("ignores malformed and unknown frames", () => {
    expect(parseChatStreamFrame("data: {oops")).toBeNull();
    expect(parseChatStreamFrame('data: {"type":"other"}')).toBeNull();
  });
});

describe("chat SSE lifecycle", () => {
  it("accepts a run after the StrictMode setup-cleanup-setup cycle", () => {
    const lifecycle = createChatRunLifecycle();
    lifecycle.mount();
    lifecycle.dispose();
    lifecycle.mount();

    expect(lifecycle.begin()).toBe(1);
  });

  it("rejects duplicate, stopped, and unmounted runs as inactive", () => {
    const lifecycle = createChatRunLifecycle();
    const first = lifecycle.begin();
    expect(first).toBe(1);
    expect(lifecycle.begin()).toBeNull();
    expect(lifecycle.isActive(first!)).toBe(true);
    lifecycle.stop(first!);
    expect(lifecycle.isActive(first!)).toBe(false);
    const second = lifecycle.begin();
    expect(second).toBe(2);
    lifecycle.dispose();
    expect(lifecycle.isActive(second!)).toBe(false);
  });
  it("emits split answer frames and completes only on the completed complete event", async () => {
    const seen: string[] = [];
    const result = await consumeChatStream(responseFromChunks([
      `data: ${JSON.stringify(event())}\n\n`.slice(0, 25),
      `data: ${JSON.stringify(event())}\n\n`.slice(25) + `data: ${JSON.stringify(event({ stage: "complete", status: "completed", metadata: [] }))}\n\n`,
    ]), { signal: new AbortController().signal, onEvent: (item) => seen.push(item.type) });

    expect(seen).toEqual(["execution_event", "execution_event"]);
    expect(result.executionId).toBe("run-1");
    expect(result.completed).toBe(true);
  });

  it("raises failed events and abnormal EOFs", async () => {
    await expect(consumeChatStream(responseFromChunks([`data: ${JSON.stringify(event({ status: "failed", stage: "failed", message: "backend failed" }))}\n\n`]), { signal: new AbortController().signal, onEvent: () => undefined })).rejects.toThrow("backend failed");
    await expect(consumeChatStream(responseFromChunks([`data: ${JSON.stringify(event())}\n\n`]), { signal: new AbortController().signal, onEvent: () => undefined })).rejects.toThrow("Stream ended before completion");
  });

  it("treats caller cancellation as quiet and never emits after disposal", async () => {
    const controller = new AbortController();
    controller.abort();
    const seen: string[] = [];
    const result = await consumeChatStream(responseFromChunks([`data: ${JSON.stringify(event())}\n\n`]), { signal: controller.signal, onEvent: (item) => seen.push(item.type) });
    expect(result.completed).toBe(false);
    expect(seen).toEqual([]);
  });

  it("cancels a reader that is already waiting and emits no further events", async () => {
    const controller = new AbortController();
    let cancelled = false;
    const response = new Response(new ReadableStream<Uint8Array>({
      cancel() {
        cancelled = true;
      },
    }));
    const seen: string[] = [];
    const pending = consumeChatStream(response, { signal: controller.signal, onEvent: (item) => seen.push(item.type) });
    controller.abort();

    await expect(pending).resolves.toEqual({ completed: false, executionId: null });
    expect(cancelled).toBe(true);
    expect(seen).toEqual([]);
  });

  it("rejects a response without a body", async () => {
    await expect(consumeChatStream(new Response(null), { signal: new AbortController().signal, onEvent: () => undefined })).rejects.toThrow("Stream response has no body");
  });
});
