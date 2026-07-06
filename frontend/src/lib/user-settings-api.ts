import { authFetch, parseOrThrow } from "./api-client";

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
