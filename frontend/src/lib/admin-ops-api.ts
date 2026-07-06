import type { OpsOverview, RetrievalProfileState, BenchmarkTrendItem, AdminRuntimeSnapshot } from "@/types/api";
import { request, ApiError, safeParsePayload, authFetch } from "./api-client";
import { buildPostRequest, buildQueryString, buildGetRequest } from "./api-helpers";

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
      throw new ApiError(res.status, String(payload?.detail || "request failed"));
    }
    return res.text();
  },
  adminOpsRetrievalProfile() {
    return request<RetrievalProfileState>("/admin/ops/retrieval-profile");
  },
  adminOpsSetRetrievalProfile(input: { profile: string; followConfigDefault?: boolean }) {
    return buildPostRequest<RetrievalProfileState>("/admin/ops/retrieval-profile", {
      profile: input.profile,
      follow_config_default: Boolean(input.followConfigDefault),
    });
  },
  adminOpsSetCanary(input: { enabled: boolean; baselinePercent: number; safePercent: number; seed?: string }) {
    return buildPostRequest<RetrievalProfileState>("/admin/ops/canary", {
      enabled: input.enabled,
      baseline_percent: input.baselinePercent,
      safe_percent: input.safePercent,
      seed: input.seed || "default",
    });
  },
  adminOpsRollback() {
    return buildPostRequest<{ ok: boolean; state: RetrievalProfileState }>("/admin/ops/rollback", {});
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
  adminRunBenchmark(input: { maxQueries?: number; strategy?: string } = {}) {
    return buildPostRequest<{ ok: boolean; result: BenchmarkTrendItem }>("/admin/ops/benchmark/run", {
      max_queries: input.maxQueries ?? 20,
      strategy: input.strategy,
    });
  },
};
