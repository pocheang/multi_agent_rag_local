import { request, toUrl, authFetch, parseOrThrow } from "@/services/http/client";
import { sessionApi, queryApi, documentApi, promptApi } from "./chat";

export interface AnalyticsOverview {
  total_queries: number;
  success_rate: number;
  avg_retrieval_time_ms: number;
  avg_total_time_ms: number;
  avg_retrieved_count: number;
  agent_distribution: Record<string, number>;
  route_distribution: Record<string, number>;
}

export interface AgentStats {
  agent_class: string;
  query_count: number;
  success_rate: number;
  avg_retrieval_time_ms: number;
  avg_retrieved_count: number;
}

export interface DocumentStats {
  source: string;
  retrieval_count: number;
  avg_score: number;
}

export const analyticsApi = {
  overview() {
    return request<AnalyticsOverview>("/api/analytics/overview");
  },

  agents() {
    return request<AgentStats[]>("/api/analytics/agents");
  },

  documents(limit = 10) {
    return request<DocumentStats[]>(`/api/analytics/documents?limit=${limit}`);
  },

  exportUrl(format: "json" | "csv") {
    return toUrl(`/api/analytics/export?format=${format}`);
  },
};

export const userSettingsApi = {
  async getUserApiSettings() {
    const res = await authFetch("/user/api-settings", { method: "GET" });
    return parseOrThrow<{
      ok: boolean;
      settings: {
        provider: string;
        api_key_masked: string;
        base_url: string;
        model: string;
        temperature: number;
        max_tokens: number;
        global_override_enabled: boolean;
        global_provider: string | null;
        global_model: string | null;
        effective_provider: string;
        effective_model: string;
      };
    }>(res);
  },
  async saveUserApiSettings(settings: {
    provider: string;
    api_key: string;
    base_url: string;
    model: string;
    temperature: number;
    max_tokens: number;
  }) {
    const res = await authFetch("/user/api-settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    return parseOrThrow<{
      ok: boolean;
      settings: {
        provider: string;
        api_key_masked: string;
        base_url: string;
        model: string;
        temperature: number;
        max_tokens: number;
        global_override_enabled: boolean;
        global_provider: string | null;
        global_model: string | null;
        effective_provider: string;
        effective_model: string;
      };
    }>(res);
  },
  async testUserApiSettings(settings: {
    provider: string;
    api_key: string;
    base_url: string;
    model: string;
    temperature: number;
    max_tokens: number;
  }) {
    const res = await authFetch("/user/api-settings/test", {
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

export const appApi = {
  ...sessionApi,
  ...queryApi,
  ...documentApi,
  ...promptApi,
  ...userSettingsApi,
};
