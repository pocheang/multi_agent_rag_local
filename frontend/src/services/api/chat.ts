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
  PendingApproval,
  PromptCheckResponse,
  ToolRun,
  PromptTemplate,
  SessionDetail,
  SessionSummary,
  UploadResponse,
} from "@/types/api";
import { ApiError, authFetch, authRequest, getToken, parseOrThrow, safeParsePayload, toUrl } from "@/services/http/client";
import { authApi } from "@/services/api/auth";
import { buildGetRequest, buildPatchRequest, buildPostRequest, buildQueryString, encodePathParam } from "@/lib/api-helpers";

type AdvancedQueryInput = {
  query: string;
  sessionId?: string;
  enableDecomposition: boolean;
  enableSelfRag: boolean;
  /** Resume a run whose governed action was awaiting confirmation. The backend
   *  replays the approved call rather than re-selecting a tool. */
  approvalToken?: string;
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

function toolRunList(value: unknown): ToolRun[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((run): ToolRun[] => {
    if (typeof run !== "object" || run === null || Array.isArray(run)) return [];
    const record = run as Record<string, unknown>;
    if (typeof record.tool_id !== "string" || typeof record.status !== "string") return [];
    return [{
      tool_id: record.tool_id,
      status: record.status,
      summary: typeof record.summary === "string" ? record.summary : "",
    }];
  });
}

function pendingApproval(value: unknown): PendingApproval | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  if (typeof record.token !== "string" || typeof record.tool_id !== "string") return null;
  return {
    tool_id: record.tool_id,
    token: record.token,
    summary: typeof record.summary === "string" ? record.summary : "",
  };
}

function recordOrUndefined(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
}

export const queryApi = {
  async advanced(input: AdvancedQueryInput): Promise<NormalizedQueryResult> {
    const res = await authFetch("/api/advanced-rag/query", {
      method: "POST",
      signal: input.signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: input.query,
        ...(input.sessionId ? { session_id: input.sessionId } : {}),
        enable_decomposition: input.enableDecomposition,
        enable_self_rag: input.enableSelfRag,
        ...(input.approvalToken ? { approval_token: input.approvalToken } : {}),
      }),
    });
    const payload = await parseOrThrow<AdvancedQueryResponse>(res);
    const metadata = recordOrUndefined(payload.metadata) ?? {};
    return {
      answer: typeof payload.final_answer === "string" ? payload.final_answer : "",
      citations: citationList(metadata.citations),
      status: payload.status === "pending_approval" ? "pending_approval" : "complete",
      pendingApproval: pendingApproval(payload.pending_approval),
      toolRuns: toolRunList(metadata.tool_runs),
      route: typeof metadata.route === "string" ? metadata.route : undefined,
      executionId: typeof metadata.execution_id === "string" ? metadata.execution_id : undefined,
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
  ) {
    const qs = buildQueryString({
      rerun: rerun ? "true" : "false",
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

  // Prefer the document_id form: a filename is not an identifier (two users
  // routinely hold a report.pdf), so the filename route has to refuse whenever
  // the name is ambiguous. Falls back for rows indexed before ids were assigned.
  async documentDelete(filename: string, source: string, removeFile: boolean, documentId?: string | null) {
    const qs = new URLSearchParams({ remove_file: removeFile ? "true" : "false" });
    const path = documentId
      ? `/documents/by-id/${encodePathParam(documentId)}?${qs.toString()}`
      : `/documents/${encodePathParam(filename)}?${qs.toString()}&source=${encodeURIComponent(source)}`;
    const res = await authFetch(path, { method: "DELETE" });
    return parseOrThrow<FileIndexActionResponse>(res);
  },

  reindexDocument(filename: string) {
    return authFetch(`/documents/${encodePathParam(filename)}/reindex`, { method: "POST" }).then(parseOrThrow<FileIndexActionResponse>);
  },

  async documentReindex(filename: string, source: string, documentId?: string | null) {
    const path = documentId
      ? `/documents/by-id/${encodePathParam(documentId)}/reindex`
      : `/documents/${encodePathParam(filename)}/reindex?source=${encodeURIComponent(source)}`;
    const res = await authFetch(path, { method: "POST" });
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
