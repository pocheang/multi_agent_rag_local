import type {
  AdminUserSummary,
  AuditLogEntry,
  AuthUser,
  FileIndexActionResponse,
  IndexedFileSummary,
  LoginResponse,
  PromptCheckResponse,
  PromptTemplate,
  OpsOverview,
  RetrievalProfileState,
  SessionDetail,
  SessionSummary,
  UploadResponse,
  BenchmarkTrendItem,
} from "@/types/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";
const TOKEN_KEY = "auth_token";

type Json = Record<string, unknown> | Array<unknown>;

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function toUrl(path: string) {
  return `${API_BASE}${path}`;
}

async function request<T = Json>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(toUrl(path), { ...init, headers });

  const text = await res.text();
  const payload = text ? JSON.parse(text) : {};
  if (!res.ok) {
    throw new ApiError(res.status, String((payload as any).detail || "request failed"));
  }
  return payload as T;
}

export async function authFetch(path: string, init: RequestInit = {}) {
  const token = getToken();
  const headers = new Headers(init.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(toUrl(path), { ...init, headers });
  if (res.status === 401) {
    authApi.setToken("");
    throw new ApiError(401, "unauthorized");
  }
  return res;
}

async function parseOrThrow<T>(res: Response): Promise<T> {
  const text = await res.text();
  const payload = text ? JSON.parse(text) : {};
  if (!res.ok) {
    throw new ApiError(res.status, String((payload as any).detail || "request failed"));
  }
  return payload as T;
}

export const authApi = {
  async me() {
    return request<AuthUser>("/auth/me");
  },
  async login(username: string, password: string) {
    return request<LoginResponse>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  },
  async register(username: string, password: string) {
    return request<AuthUser>("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  },
  async logout() {
    try {
      await request("/auth/logout", { method: "POST" });
    } catch {
      // ignore logout error
    }
  },
  setToken(token: string) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  },
  token() {
    return getToken();
  },
};

export const appApi = {
  sessions() {
    return request<SessionSummary[]>("/sessions");
  },
  sessionCreate() {
    return request<SessionDetail>("/sessions", { method: "POST" });
  },
  sessionDetail(sessionId: string) {
    return request<SessionDetail>(`/sessions/${encodeURIComponent(sessionId)}`);
  },
  async sessionDelete(sessionId: string) {
    const res = await authFetch(`/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
    return parseOrThrow<{ ok: boolean; session_id: string }>(res);
  },
  async messageUpdate(
    sessionId: string,
    messageId: string,
    content: string,
    rerun: boolean,
    useWebFallback: boolean,
    useReasoning: boolean,
  ) {
    const qs = new URLSearchParams({
      rerun: rerun ? "true" : "false",
      use_web_fallback: useWebFallback ? "1" : "0",
      use_reasoning: useReasoning ? "1" : "0",
    });
    const res = await authFetch(
      `/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(messageId)}?${qs.toString()}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      },
    );
    return parseOrThrow<SessionDetail>(res);
  },
  async messageDelete(sessionId: string, messageId: string) {
    const res = await authFetch(
      `/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(messageId)}`,
      { method: "DELETE" },
    );
    return parseOrThrow<SessionDetail>(res);
  },
  async streamQuery(input: {
    question: string;
    useWebFallback: boolean;
    useReasoning: boolean;
    sessionId: string;
    agentClassHint?: string;
  }) {
    const form = new FormData();
    form.append("question", input.question);
    form.append("use_web_fallback", input.useWebFallback ? "1" : "0");
    form.append("use_reasoning", input.useReasoning ? "1" : "0");
    form.append("session_id", input.sessionId);
    if (input.agentClassHint) form.append("agent_class_hint", input.agentClassHint);
    return authFetch("/query/stream", { method: "POST", body: form });
  },
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
      const token = getToken();
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

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
        let payload: any = {};
        try {
          payload = text ? JSON.parse(text) : {};
        } catch {
          payload = {};
        }

        if (xhr.status === 401) {
          authApi.setToken("");
          reject(new ApiError(401, "unauthorized"));
          return;
        }
        if (xhr.status < 200 || xhr.status >= 300) {
          reject(new ApiError(xhr.status, String(payload?.detail || "request failed")));
          return;
        }
        resolve(payload as UploadResponse);
      };

      xhr.send(form);
    });
  },
  documents() {
    return request<IndexedFileSummary[]>("/documents");
  },
  async documentDelete(filename: string, source: string, removeFile: boolean) {
    const qs = new URLSearchParams({
      remove_file: removeFile ? "true" : "false",
      source,
    });
    const res = await authFetch(`/documents/${encodeURIComponent(filename)}?${qs.toString()}`, {
      method: "DELETE",
    });
    return parseOrThrow<FileIndexActionResponse>(res);
  },
  async documentReindex(filename: string, source: string) {
    const qs = new URLSearchParams({ source });
    const res = await authFetch(
      `/documents/${encodeURIComponent(filename)}/reindex?${qs.toString()}`,
      { method: "POST" },
    );
    return parseOrThrow<FileIndexActionResponse>(res);
  },
  prompts() {
    return request<PromptTemplate[]>("/prompts");
  },
  async promptCheck(title: string, content: string, useReasoning: boolean) {
    const res = await authFetch("/prompts/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, content, use_reasoning: useReasoning }),
    });
    return parseOrThrow<PromptCheckResponse>(res);
  },
  async promptCreate(title: string, content: string) {
    const res = await authFetch("/prompts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, content }),
    });
    return parseOrThrow<PromptTemplate>(res);
  },
  async promptUpdate(promptId: string, title: string, content: string) {
    const res = await authFetch(`/prompts/${encodeURIComponent(promptId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, content }),
    });
    return parseOrThrow<PromptTemplate>(res);
  },
  async promptDelete(promptId: string) {
    const res = await authFetch(`/prompts/${encodeURIComponent(promptId)}`, { method: "DELETE" });
    return parseOrThrow<{ ok: boolean; prompt_id: string }>(res);
  },
  adminUsers() {
    return request<AdminUserSummary[]>("/admin/users");
  },
  async adminUpdateRole(userId: string, role: string) {
    const res = await authFetch(`/admin/users/${encodeURIComponent(userId)}/role`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    return parseOrThrow<AdminUserSummary>(res);
  },
  async adminUpdateStatus(userId: string, statusValue: string) {
    const res = await authFetch(`/admin/users/${encodeURIComponent(userId)}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: statusValue }),
    });
    return parseOrThrow<AdminUserSummary>(res);
  },
  async adminUpdateClassification(
    userId: string,
    input: { businessUnit?: string; department?: string; userType?: string; dataScope?: string },
  ) {
    const res = await authFetch(`/admin/users/${encodeURIComponent(userId)}/classification`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        business_unit: input.businessUnit || null,
        department: input.department || null,
        user_type: input.userType || null,
        data_scope: input.dataScope || null,
      }),
    });
    return parseOrThrow<AdminUserSummary>(res);
  },
  async adminCreateAdmin(input: {
    username: string;
    password: string;
    approvalToken: string;
    ticketId: string;
    reason: string;
    newAdminApprovalToken: string;
  }) {
    const res = await authFetch("/admin/users/create-admin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: input.username,
        password: input.password,
        approval_token: input.approvalToken,
        ticket_id: input.ticketId,
        reason: input.reason,
        new_admin_approval_token: input.newAdminApprovalToken,
      }),
    });
    return parseOrThrow<AdminUserSummary>(res);
  },
  async adminResetApprovalToken(input: {
    userId: string;
    approvalToken: string;
    ticketId: string;
    reason: string;
    newAdminApprovalToken: string;
  }) {
    const res = await authFetch(`/admin/users/${encodeURIComponent(input.userId)}/reset-approval-token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        approval_token: input.approvalToken,
        ticket_id: input.ticketId,
        reason: input.reason,
        new_admin_approval_token: input.newAdminApprovalToken,
      }),
    });
    return parseOrThrow<AdminUserSummary>(res);
  },
  async adminResetPassword(input: {
    userId: string;
    approvalToken: string;
    ticketId: string;
    reason: string;
    newPassword: string;
  }) {
    const res = await authFetch(`/admin/users/${encodeURIComponent(input.userId)}/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        approval_token: input.approvalToken,
        ticket_id: input.ticketId,
        reason: input.reason,
        new_password: input.newPassword,
      }),
    });
    return parseOrThrow<AdminUserSummary>(res);
  },
  adminAudit(input: {
    limit: number;
    actorUserId?: string;
    actionKeyword?: string;
    eventCategory?: string;
    severity?: string;
    result?: string;
  }) {
    const qs = new URLSearchParams();
    qs.set("limit", String(input.limit));
    if (input.actorUserId) qs.set("actor_user_id", input.actorUserId);
    if (input.actionKeyword) qs.set("action_keyword", input.actionKeyword);
    if (input.eventCategory) qs.set("event_category", input.eventCategory);
    if (input.severity) qs.set("severity", input.severity);
    if (input.result) qs.set("result", input.result);
    return request<AuditLogEntry[]>(`/admin/audit-logs?${qs.toString()}`);
  },
  adminOpsOverview(input: { hours?: number; actorUserId?: string; actionKeyword?: string } = {}) {
    const qs = new URLSearchParams();
    qs.set("hours", String(input.hours ?? 24));
    if (input.actorUserId) qs.set("actor_user_id", input.actorUserId);
    if (input.actionKeyword) qs.set("action_keyword", input.actionKeyword);
    return request<OpsOverview>(`/admin/ops/overview?${qs.toString()}`);
  },
  async adminOpsExportCsv(input: { hours?: number; actorUserId?: string; actionKeyword?: string } = {}) {
    const qs = new URLSearchParams();
    qs.set("hours", String(input.hours ?? 24));
    if (input.actorUserId) qs.set("actor_user_id", input.actorUserId);
    if (input.actionKeyword) qs.set("action_keyword", input.actionKeyword);
    const res = await authFetch(`/admin/ops/export.csv?${qs.toString()}`, { method: "GET" });
    if (!res.ok) {
      const text = await res.text();
      let payload: any = {};
      try {
        payload = text ? JSON.parse(text) : {};
      } catch {
        payload = {};
      }
      throw new ApiError(res.status, String(payload?.detail || "request failed"));
    }
    return res.text();
  },
  adminOpsRetrievalProfile() {
    return request<RetrievalProfileState>("/admin/ops/retrieval-profile");
  },
  async adminOpsSetRetrievalProfile(input: { profile: string; followConfigDefault?: boolean }) {
    const res = await authFetch("/admin/ops/retrieval-profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile: input.profile,
        follow_config_default: Boolean(input.followConfigDefault),
      }),
    });
    return parseOrThrow<RetrievalProfileState>(res);
  },
  async adminOpsSetCanary(input: { enabled: boolean; baselinePercent: number; safePercent: number; seed?: string }) {
    const res = await authFetch("/admin/ops/canary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        enabled: input.enabled,
        baseline_percent: input.baselinePercent,
        safe_percent: input.safePercent,
        seed: input.seed || "default",
      }),
    });
    return parseOrThrow<RetrievalProfileState>(res);
  },
  async adminReloadConfig() {
    const res = await authFetch("/admin/config/reload", { method: "POST" });
    return parseOrThrow<{
      ok: boolean;
      reloaded_at: string;
      snapshot: Record<string, unknown>;
    }>(res);
  },
  async adminOpsRollback() {
    const res = await authFetch("/admin/ops/rollback", { method: "POST" });
    return parseOrThrow<{ ok: boolean; state: RetrievalProfileState }>(res);
  },
  async adminOpsExportAuditReportMd(input: { hours?: number } = {}) {
    const qs = new URLSearchParams();
    qs.set("hours", String(input.hours ?? 24));
    const res = await authFetch(`/admin/ops/audit-report.md?${qs.toString()}`, { method: "GET" });
    if (!res.ok) {
      throw new ApiError(res.status, "request failed");
    }
    return res.text();
  },
  adminBenchmarkTrends(input: { limit?: number } = {}) {
    const qs = new URLSearchParams();
    qs.set("limit", String(input.limit ?? 30));
    return request<{ items: BenchmarkTrendItem[]; count: number }>(`/admin/ops/benchmark/trends?${qs.toString()}`);
  },
  async adminRunBenchmark(input: { maxQueries?: number; strategy?: string } = {}) {
    const qs = new URLSearchParams();
    qs.set("max_queries", String(input.maxQueries ?? 20));
    if (input.strategy) qs.set("strategy", input.strategy);
    const res = await authFetch(`/admin/ops/benchmark/run?${qs.toString()}`, { method: "POST" });
    return parseOrThrow<{ ok: boolean; result: BenchmarkTrendItem }>(res);
  },
};
