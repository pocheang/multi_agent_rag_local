import type { AdminModelSettingsPayload, AdminModelSettingsView, ModelCatalogResponse } from "@/types/api";
import { authFetch, parseOrThrow } from "./api-client";

export const adminModelApi = {
  async modelCatalog() {
    const res = await authFetch("/model-catalog", { method: "GET" });
    return parseOrThrow<ModelCatalogResponse>(res);
  },
  async adminModelSettings() {
    const res = await authFetch("/admin/model-settings", { method: "GET" });
    return parseOrThrow<{ ok: boolean; settings: AdminModelSettingsView }>(res);
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
