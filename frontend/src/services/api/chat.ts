import type {
  AdvancedQueryResponse,
  Citation,
  ClarificationCheckRequest,
  ClarificationContext,
  ClarificationResponse,
  FileIndexActionResponse,
  IndexHealthResponse,
  IndexedFileSummary,
  NormalizedQueryResult,
  PromptCheckResponse,
  PromptTemplate,
  SessionDetail,
  SessionSummary,
  StandardQueryResponse,
  StrictQualityQueryResponse,
  UploadResponse,
} from "@/types/api";
import { ApiError, authFetch, authRequest, getToken, parseOrThrow, safeParsePayload, toUrl } from "@/services/http/client";
import { authApi } from "@/services/api/auth";
import { buildGetRequest, buildPatchRequest, buildPostRequest, buildQueryString, encodePathParam } from "@/lib/api-helpers";
import { addCsrfHeader } from "@/lib/csrf";

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

export const sessionApi = {
  sessions() {
    return authRequest<SessionSummary[]>("/sessions");
  },
  sessionCreate(signal?: AbortSignal) {
    return authRequest<SessionDetail>("/sessions", { method: "POST", signal });
  },
  sessionDetail(sessionId: string, signal?: AbortSignal) {
    return authRequest<SessionDetail>(`/sessions/${encodePathParam(sessionId)}`, { signal });
  },
  sessionDelete(sessionId: string) {
    return authRequest<{ ok: boolean; session_id: string }>(`/sessions/${encodePathParam(sessionId)}`, { method: "DELETE" });
  },
  sessionRename(sessionId: string, title: string) {
    return buildPatchRequest<SessionDetail>(
      `/sessions/${encodePathParam(sessionId)}`,
      { title },
    );
  },
  sessionPin(sessionId: string, pinned: boolean) {
    return buildPatchRequest<SessionDetail>(
      `/sessions/${encodePathParam(sessionId)}`,
      { pinned },
    );
  },
  messageUpdate(
    sessionId: string,
    messageId: string,
    content: string,
    rerun: boolean,
    useWebFallback: boolean,
    useReasoning: boolean,
  ) {
    const qs = buildQueryString({
      rerun: rerun ? "true" : "false",
      use_web_fallback: useWebFallback ? "1" : "0",
      use_reasoning: useReasoning ? "1" : "0",
    });
    return buildPatchRequest<SessionDetail>(
      `/sessions/${encodePathParam(sessionId)}/messages/${encodePathParam(messageId)}?${qs}`,
      { content },
    );
  },
  messageDelete(sessionId: string, messageId: string) {
    return authRequest<SessionDetail>(
      `/sessions/${encodePathParam(sessionId)}/messages/${encodePathParam(messageId)}`,
      { method: "DELETE" },
    );
  },
};

export const documentApi = {
  upload(
    files: File[],
    onProgress?: (percent: number) => void,
    visibility: "private" | "public" = "private",
  ): Promise<UploadResponse> {
    if (!onProgress) {
      return (async () => {
        const form = new FormData();
        for (const file of files) form.append("files", file);
        form.append("visibility", visibility);
        const res = await authFetch("/upload", { method: "POST", body: form });
        return parseOrThrow<UploadResponse>(res);
      })();
    }

    return new Promise<UploadResponse>((resolve, reject) => {
      const form = new FormData();
      for (const file of files) form.append("files", file);
      form.append("visibility", visibility);

      const xhr = new XMLHttpRequest();
      xhr.open("POST", toUrl("/upload"));
      xhr.withCredentials = true;
      const headers = new Headers();
      const token = getToken();
      if (token) headers.set("Authorization", `Bearer ${token}`);
      addCsrfHeader(headers);
      headers.forEach((value, key) => xhr.setRequestHeader(key, value));

      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable && evt.total > 0) {
          const percent = (evt.loaded / evt.total) * 100;
          onProgress(Math.min(100, Math.max(0, percent)));
          return;
        }
        onProgress(35);
      };

      xhr.onerror = () => {
        reject(new Error("network error"));
      };

      xhr.onload = () => {
        const text = xhr.responseText || "";
        const payload = safeParsePayload(text);

        if (xhr.status === 401) {
          authApi.setToken("");
          reject(new ApiError(401, "unauthorized"));
          return;
        }
        if (xhr.status < 200 || xhr.status >= 300) {
          const detail = payload && typeof payload === "object" && !Array.isArray(payload)
            ? (payload as Record<string, unknown>).detail
            : undefined;
          reject(new ApiError(xhr.status, typeof detail === "string" ? detail : "request failed"));
          return;
        }
        resolve(payload as UploadResponse);
      };

      xhr.send(form);
    });
  },

  documents(params?: { visibility?: "all" | "private" | "public"; doc_type?: "pdf" | "other" }) {
    return buildGetRequest<IndexedFileSummary[]>("/documents", params);
  },

  deleteDocument(filename: string) {
    return authFetch(`/documents/${encodePathParam(filename)}`, { method: "DELETE" }).then(parseOrThrow<{ ok: boolean; filename: string }>);
  },

  async documentDelete(filename: string, source: string, removeFile: boolean) {
    const qs = new URLSearchParams({
      remove_file: removeFile ? "true" : "false",
      source,
    });
    const res = await authFetch(`/documents/${encodePathParam(filename)}?${qs.toString()}`, {
      method: "DELETE",
    });
    return parseOrThrow<FileIndexActionResponse>(res);
  },

  reindexDocument(filename: string) {
    return authFetch(`/documents/${encodePathParam(filename)}/reindex`, { method: "POST" }).then(parseOrThrow<FileIndexActionResponse>);
  },

  async documentReindex(filename: string, source: string) {
    const qs = new URLSearchParams({ source });
    const res = await authFetch(
      `/documents/${encodePathParam(filename)}/reindex?${qs.toString()}`,
      { method: "POST" },
    );
    return parseOrThrow<FileIndexActionResponse>(res);
  },

  indexHealth() {
    return authFetch("/documents/index-health", { method: "GET" }).then(parseOrThrow<IndexHealthResponse>);
  },
};

export const promptApi = {
  prompts() {
    return authFetch("/prompts").then(parseOrThrow<PromptTemplate[]>);
  },
  promptCheck(title: string, content: string, useReasoning: boolean) {
    return buildPostRequest<PromptCheckResponse>("/prompts/check", {
      title,
      content,
      use_reasoning: useReasoning,
    });
  },
  promptCreate(title: string, content: string) {
    return buildPostRequest<PromptTemplate>("/prompts", { title, content });
  },
  promptUpdate(promptId: string, title: string, content: string) {
    return buildPatchRequest<PromptTemplate>(`/prompts/${encodePathParam(promptId)}`, { title, content });
  },
  async promptDelete(promptId: string) {
    const res = await authFetch(`/prompts/${encodePathParam(promptId)}`, { method: "DELETE" });
    return parseOrThrow<{ ok: boolean; prompt_id: string }>(res);
  },
};

export const clarificationApi = {
  checkClarification(request: ClarificationCheckRequest) {
    // Increase timeout to 60 seconds for clarification check (includes LLM call)
    return buildPostRequest<ClarificationResponse>("/api/v1/clarification/check", request, 60_000);
  },

  resetClarification(sessionId: string) {
    return buildPostRequest<{ status: string; message: string }>(
      `/api/v1/clarification/reset/${encodePathParam(sessionId)}`,
      {}
    );
  },

  getClarificationContext(sessionId: string) {
    return buildGetRequest<ClarificationContext>(
      `/api/v1/clarification/context/${encodePathParam(sessionId)}`
    );
  },
};
