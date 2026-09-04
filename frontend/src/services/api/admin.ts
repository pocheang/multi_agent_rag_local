import type {
  AdminModelSettingsPayload,
  AdminModelSettingsView,
  EffectiveModelConfigResponse,
  AdminRuntimeSnapshot,
  ConfigSaveResponse,
  ConfigSchemaResponse,
  AdminUserSummary,
  AuditLogEntry,
  BenchmarkTrendItem,
  ModelCatalogResponse,
  OpsOverview,
  SystemLogEntry,
} from "@/types/api";
import { request, ApiError, safeParsePayload, authFetch, parseOrThrow } from "@/services/http/client";
import { buildPatchRequest, buildPostRequest, buildGetRequest, buildQueryString, encodePathParam } from "@/lib/api-helpers";

export const adminUserApi = {
  adminUsers() {
    return request<AdminUserSummary[]>("/admin/users");
  },
  adminUpdateRole(userId: string, role: string) {
    return buildPatchRequest<AdminUserSummary>(`/admin/users/${encodePathParam(userId)}/role`, { role });
  },
  adminUpdateStatus(userId: string, statusValue: string) {
    return buildPatchRequest<AdminUserSummary>(`/admin/users/${encodePathParam(userId)}/status`, { status: statusValue });
  },
  adminAddCredits(userId: string, amount: number) {
    return buildPostRequest<AdminUserSummary>(`/admin/users/${encodePathParam(userId)}/credits/add`, { amount });
  },
  adminUpdateClassification(
    userId: string,
    input: { businessUnit?: string; department?: string; userType?: string; dataScope?: string },
  ) {
    return buildPatchRequest<AdminUserSummary>(`/admin/users/${encodePathParam(userId)}/classification`, {
      business_unit: input.businessUnit || null,
      department: input.department || null,
      user_type: input.userType || null,
      data_scope: input.dataScope || null,
    });
  },
  adminCreateAdmin(input: {
    username: string;
    password: string;
    approvalToken: string;
    ticketId: string;
    reason: string;
    newAdminApprovalToken: string;
  }) {
    return buildPostRequest<AdminUserSummary>("/admin/users/create-admin", {
      username: input.username,
      password: input.password,
      approval_token: input.approvalToken,
      ticket_id: input.ticketId,
      reason: input.reason,
      new_admin_approval_token: input.newAdminApprovalToken,
    });
  },
  adminResetApprovalToken(input: {
    userId: string;
    approvalToken: string;
    ticketId: string;
    reason: string;
    newAdminApprovalToken: string;
  }) {
    return buildPostRequest<AdminUserSummary>(`/admin/users/${encodePathParam(input.userId)}/reset-approval-token`, {
      approval_token: input.approvalToken,
      ticket_id: input.ticketId,
      reason: input.reason,
      new_admin_approval_token: input.newAdminApprovalToken,
    });
  },
  adminResetPassword(input: {
    userId: string;
    approvalToken: string;
    ticketId: string;
    reason: string;
    newPassword: string;
  }) {
    return buildPostRequest<AdminUserSummary>(`/admin/users/${encodePathParam(input.userId)}/reset-password`, {
      approval_token: input.approvalToken,
      ticket_id: input.ticketId,
      reason: input.reason,
      new_password: input.newPassword,
    });
  },
};

export const adminOpsApi = {
  adminRuntimeSnapshot() {
    return request<AdminRuntimeSnapshot>("/admin/ops/runtime");
  },
  adminOpsOverview(input: { hours?: number; actorUserId?: string; actionKeyword?: string } = {}) {
    return buildGetRequest<OpsOverview>("/admin/ops/overview", {
      hours: input.hours ?? 24,
      actor_user_id: input.actorUserId,
      action_keyword: input.actionKeyword,
    });
  },
  async adminOpsExportCsv(input: { hours?: number; actorUserId?: string; actionKeyword?: string } = {}) {
    const qs = buildQueryString({
      hours: input.hours ?? 24,
      actor_user_id: input.actorUserId,
      action_keyword: input.actionKeyword,
    });
    const res = await authFetch(`/admin/ops/export.csv?${qs}`, { method: "GET" });
    if (!res.ok) {
      const text = await res.text();
      const payload = safeParsePayload(text);
      const detail = payload && typeof payload === "object" && !Array.isArray(payload)
        ? (payload as Record<string, unknown>).detail
        : undefined;
      throw new ApiError(res.status, typeof detail === "string" ? detail : "request failed");
    }
    return res.text();
  },
  async adminOpsExportAuditReportMd(input: { hours?: number } = {}) {
    const qs = buildQueryString({ hours: input.hours ?? 24 });
    const res = await authFetch(`/admin/ops/audit-report.md?${qs}`, { method: "GET" });
    if (!res.ok) {
      throw new ApiError(res.status, "request failed");
    }
    return res.text();
  },
  adminBenchmarkTrends(input: { limit?: number } = {}) {
    return buildGetRequest<{ items: BenchmarkTrendItem[]; count: number }>("/admin/ops/benchmark/trends", {
      limit: input.limit ?? 30,
    });
  },
  /**
   * Queues a benchmark run. The backend answers 202 immediately and executes
   * the (multi-minute) run in its background queue; poll adminBenchmarkTrends
   * afterwards to see the result.
   */
  adminRunBenchmark(input: { maxQueries?: number } = {}) {
    return buildPostRequest<{ ok: boolean; status: string; max_queries: number }>("/admin/ops/benchmark/run", {
      max_queries: input.maxQueries ?? 20,
    });
  },
};

export const adminModelApi = {
  async modelCatalog() {
    const res = await authFetch("/model-catalog", { method: "GET" });
    return parseOrThrow<ModelCatalogResponse>(res);
  },
  async adminModelSettings() {
    const res = await authFetch("/admin/model-settings", { method: "GET" });
    return parseOrThrow<{ ok: boolean; settings: AdminModelSettingsView }>(res);
  },
  async adminEffectiveModelConfig() {
    const res = await authFetch("/admin/model-settings/effective", { method: "GET" });
    return parseOrThrow<EffectiveModelConfigResponse>(res);
  },
  async adminSaveModelSettings(settings: AdminModelSettingsPayload) {
    const res = await authFetch("/admin/model-settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    return parseOrThrow<{ ok: boolean; settings: AdminModelSettingsView }>(res);
  },
  async adminTestModelSettings(settings: AdminModelSettingsPayload) {
    const res = await authFetch("/admin/model-settings/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    return parseOrThrow<{
      ok: boolean;
      reachable: boolean;
      provider: string;
      model: string;
      latency_ms: number;
      message: string;
      preview: string;
    }>(res);
  },
};

export const adminAuditApi = {
  adminAudit(input: {
    limit: number;
    actorUserId?: string;
    actionKeyword?: string;
    eventCategory?: string;
    severity?: string;
    result?: string;
  }) {
    const qs = buildQueryString({
      limit: input.limit,
      actor_user_id: input.actorUserId,
      action_keyword: input.actionKeyword,
      event_category: input.eventCategory,
      severity: input.severity,
      result: input.result,
    });
    return request<AuditLogEntry[]>(`/admin/audit-logs?${qs}`);
  },
};

export const adminSystemLogApi = {
  adminSystemLogs(input: { limit?: number; level?: string; logger?: string; keyword?: string } = {}) {
    const qs = buildQueryString({
      limit: input.limit ?? 200,
      level: input.level,
      logger: input.logger,
      keyword: input.keyword,
    });
    return request<{ items: SystemLogEntry[]; count: number }>(`/admin/system-logs?${qs}`);
  },
};

export const adminConfigApi = {
  async adminReloadConfig() {
    const res = await authFetch("/admin/config/reload", { method: "POST" });
    return parseOrThrow<{
      ok: boolean;
      reloaded_at: string;
      snapshot: Record<string, unknown>;
    }>(res);
  },
  /** Every editable field, its current value, and which layer supplied it. */
  configSchema() {
    return request<ConfigSchemaResponse>("/admin/config/schema");
  },
  /** Only the fields that were actually edited; the server merges the rest into
   *  the document it already holds, so an untouched key keeps its value. */
  saveConfig(values: Record<string, string>, dataId?: string) {
    return buildPostRequest<ConfigSaveResponse>("/admin/config/values", { values, data_id: dataId ?? null });
  },
};
