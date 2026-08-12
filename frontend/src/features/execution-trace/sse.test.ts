import { describe, expect, it } from "vitest";

import { consumeExecutionEventStream, parseExecutionEventSse } from "./sse";

describe("parseExecutionEventSse", () => {
  it("parses only the versioned execution_event SSE payload", () => {
    const event = parseExecutionEventSse(
      "event: execution_event\ndata: {\"version\":\"1\",\"stage\":\"rag\",\"status\":\"completed\",\"duration_ms\":2,\"message\":\"retrieved\",\"metadata\":[],\"occurred_at\":\"2026-08-06T00:00:00Z\"}\n\n",
    );

    expect(event?.stage).toBe("rag");
  });

  it("ignores a non-versioned or differently named SSE event", () => {
    expect(parseExecutionEventSse("event: status\ndata: {\"type\":\"status\"}\n\n")).toBeNull();
  });

  it.each([
    "{\"version\":\"1\",\"stage\":\"unknown\",\"status\":\"completed\",\"duration_ms\":2,\"message\":\"x\",\"metadata\":[],\"occurred_at\":\"2026-08-06T00:00:00Z\"}",
    "{\"version\":\"1\",\"stage\":\"rag\",\"status\":\"running\",\"duration_ms\":2,\"message\":\"x\",\"metadata\":[],\"occurred_at\":\"2026-08-06T00:00:00Z\"}",
    "{\"version\":\"1\",\"stage\":\"rag\",\"status\":\"completed\",\"duration_ms\":-1,\"message\":\"x\",\"metadata\":[],\"occurred_at\":\"2026-08-06T00:00:00Z\"}",
    "{\"version\":\"1\",\"stage\":\"rag\",\"status\":\"completed\",\"duration_ms\":2,\"message\":\"x\",\"metadata\":[{\"key\":3,\"value\":\"x\"}],\"occurred_at\":\"2026-08-06T00:00:00Z\"}",
  ])("rejects malformed version-1 execution events: %s", (payload) => {
    expect(parseExecutionEventSse(`event: execution_event\ndata: ${payload}\n\n`)).toBeNull();
  });

  it("consumes SSE frames incrementally without waiting for the complete response", async () => {
    const encoder = new TextEncoder();
    const received: string[] = [];
    const response = new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode("event: execution_event\ndata: {\"version\":\"1\",\"stage\":\"route\",\"status\":\"completed\",\"duration_ms\":1,\"message\":\"routed\",\"metadata\":[],\"occurred_at\":\"2026-08-06T00:00:00Z\"}\n\n"));
        controller.enqueue(encoder.encode("event: execution_event\ndata: {\"version\":\"1\",\"stage\":\"complete\",\"status\":\"completed\",\"duration_ms\":2,\"message\":\"\",\"metadata\":[],\"occurred_at\":\"2026-08-06T00:00:01Z\"}\n\n"));
        controller.close();
      },
    }));

    await consumeExecutionEventStream(response, (event) => received.push(event.message), new AbortController().signal);

    expect(received).toEqual(["routed", ""]);
  });
});
