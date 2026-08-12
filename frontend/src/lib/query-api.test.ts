import { afterEach, describe, expect, it, vi } from "vitest";
import { queryApi } from "./query-api";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

describe("query profile HTTP contracts", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends the standard stream fields as multipart form data", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await queryApi.streamQuery({ question: "What changed?", useWebFallback: true, useReasoning: false, sessionId: "s1", agentClassHint: "general", retrievalStrategy: "safe" });

    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/query/stream");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect([...((init.body as FormData).entries())]).toEqual([
      ["question", "What changed?"], ["use_web_fallback", "1"], ["use_reasoning", "0"], ["session_id", "s1"], ["agent_class_hint", "general"], ["retrieval_strategy", "safe"],
    ]);
  });

  it("maps strict-quality JSON responses while keeping optional quality data safe", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ answer: "Verified", citations: [], quality_report: {}, route_used: "vector", route_reason: "fast", skill_used: "retrieve", agent_class: "general", execution_metadata: { execution_id: "e1" } }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await queryApi.strictQuality({ query: "Check this", sessionId: "s2", retrievalStrategy: "advanced", agentClassHint: "general", enableContextTracking: true });

    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/api/v1/enhanced/query");
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
    expect(JSON.parse(String(init.body))).toEqual({ query: "Check this", session_id: "s2", retrieval_strategy: "advanced", agent_class_hint: "general", enable_context_tracking: true });
    expect(result).toMatchObject({ profile: "strict_quality", answer: "Verified", citations: [], route: "vector", executionMetadata: { execution_id: "e1" } });
  });

  it("sends advanced-only JSON fields and normalizes citations from metadata", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ query: "Compare", decomposed_query: null, sub_query_results: [], final_answer: "Comparison", answer_quality: null, metadata: { route: "react", citations: [{ source: "guide", content: "evidence", metadata: { document_id: "d1", page: 3 } }] } }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await queryApi.advanced({ query: "Compare", retrievalStrategy: "safe", enableDecomposition: true, enableSelfRag: false });

    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/api/advanced-rag/query");
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
    expect(JSON.parse(String(init.body))).toEqual({ query: "Compare", retrieval_strategy: "safe", enable_decomposition: true, enable_self_rag: false });
    expect(result).toMatchObject({ profile: "advanced", answer: "Comparison", route: "react", citations: [{ source: "guide", content: "evidence" }] });
  });

  it("normalizes partial strict-quality results and forwards cancellation", async () => {
    const controller = new AbortController();
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ answer: null, citations: [{ source: "guide", content: 3 }, { source: 4, content: "ignored" }], quality_report: null, route_used: null, execution_metadata: null }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await queryApi.strictQuality({ query: "Check", sessionId: "s3", enableContextTracking: false, signal: controller.signal });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.signal).toBeDefined();
    expect(result).toEqual({
      profile: "strict_quality",
      answer: "",
      citations: [{ source: "guide", content: "" }],
      route: undefined,
      qualityReport: undefined,
      executionMetadata: undefined,
    });
  });

  it("normalizes an array advanced metadata payload to an empty record", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ final_answer: "Answer", metadata: [] })));

    const result = await queryApi.advanced({ query: "Question", enableDecomposition: false, enableSelfRag: false });

    expect(result.executionMetadata).toEqual({});
    expect(result.citations).toEqual([]);
  });
});
