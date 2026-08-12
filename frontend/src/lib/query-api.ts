import { authFetch, parseOrThrow } from "./api-client";
import type {
  AdvancedQueryResponse,
  Citation,
  NormalizedQueryResult,
  StandardQueryResponse,
  StrictQualityQueryResponse,
} from "@/types/api";

type StandardQueryInput = {
  question: string;
  useWebFallback: boolean;
  useReasoning: boolean;
  sessionId: string;
  agentClassHint?: string;
  retrievalStrategy?: string;
};

type StrictQualityQueryInput = {
  query: string;
  sessionId: string;
  retrievalStrategy?: string;
  agentClassHint?: string;
  enableContextTracking: boolean;
  signal?: AbortSignal;
};

type AdvancedQueryInput = {
  query: string;
  retrievalStrategy?: string;
  enableDecomposition: boolean;
  enableSelfRag: boolean;
  signal?: AbortSignal;
};

function citationList(value: unknown): Citation[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((citation): Citation[] => {
    if (typeof citation !== "object" || citation === null || Array.isArray(citation)) return [];
    const record = citation as Record<string, unknown>;
    if (typeof record.source !== "string") return [];
    return [{
      ...record,
      source: record.source,
      content: typeof record.content === "string" ? record.content : "",
    }];
  });
}

function recordOrUndefined(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
}

export const queryApi = {
  async streamQuery(input: StandardQueryInput & {
    signal?: AbortSignal;
  }) {
    const form = new FormData();
    form.append("question", input.question);
    form.append("use_web_fallback", input.useWebFallback ? "1" : "0");
    form.append("use_reasoning", input.useReasoning ? "1" : "0");
    form.append("session_id", input.sessionId);
    if (input.agentClassHint) form.append("agent_class_hint", input.agentClassHint);
    if (input.retrievalStrategy) form.append("retrieval_strategy", input.retrievalStrategy);
    return authFetch(
      "/query/stream",
      { method: "POST", body: form, signal: input.signal },
    );
  },
  async query(input: StandardQueryInput): Promise<StandardQueryResponse> {
    const res = await authFetch(
      "/query",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: input.question,
          use_web_fallback: input.useWebFallback,
          use_reasoning: input.useReasoning,
          session_id: input.sessionId,
          agent_class_hint: input.agentClassHint || null,
          retrieval_strategy: input.retrievalStrategy || null,
        }),
      },
    );
    return parseOrThrow<StandardQueryResponse>(res);
  },
  async strictQuality(input: StrictQualityQueryInput): Promise<NormalizedQueryResult> {
    const res = await authFetch("/api/v1/enhanced/query", {
      method: "POST",
      signal: input.signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: input.query,
        session_id: input.sessionId,
        retrieval_strategy: input.retrievalStrategy ?? null,
        agent_class_hint: input.agentClassHint ?? null,
        enable_context_tracking: input.enableContextTracking,
      }),
    });
    const payload = await parseOrThrow<StrictQualityQueryResponse>(res);
    return {
      profile: "strict_quality",
      answer: typeof payload.answer === "string" ? payload.answer : "",
      citations: citationList(payload.citations),
      route: typeof payload.route_used === "string" ? payload.route_used : undefined,
      qualityReport: recordOrUndefined(payload.quality_report),
      executionMetadata: recordOrUndefined(payload.execution_metadata),
    };
  },
  async advanced(input: AdvancedQueryInput): Promise<NormalizedQueryResult> {
    const res = await authFetch("/api/advanced-rag/query", {
      method: "POST",
      signal: input.signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: input.query,
        retrieval_strategy: input.retrievalStrategy ?? null,
        enable_decomposition: input.enableDecomposition,
        enable_self_rag: input.enableSelfRag,
      }),
    });
    const payload = await parseOrThrow<AdvancedQueryResponse>(res);
    const metadata = recordOrUndefined(payload.metadata) ?? {};
    return {
      profile: "advanced",
      answer: typeof payload.final_answer === "string" ? payload.final_answer : "",
      citations: citationList(metadata.citations),
      route: typeof metadata.route === "string" ? metadata.route : undefined,
      qualityReport: recordOrUndefined(payload.answer_quality),
      executionMetadata: metadata,
    };
  },
};
