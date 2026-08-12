import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AdminModelSettingsView } from "@/types/api";
import type { AdminActionsParams } from "./types";

const apiMocks = vi.hoisted(() => ({
  adminSaveModelSettings: vi.fn(),
  adminTestModelSettings: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ appApi: apiMocks }));

import { createModelActions } from "./modelActions";

const settings: AdminModelSettingsView = {
  enabled: false,
  provider: "local",
  api_key_masked: "",
  base_url: "",
  chat_model: "local-evidence",
  reasoning_model: "local-evidence",
  embedding_model: "local-hash-384",
  temperature: 1.4,
  max_tokens: 2048,
};

function modelActionParams(): AdminActionsParams {
  return {
    modelSettings: settings,
    modelApiKey: "",
    isAdmin: false,
    setModelSettings: () => undefined,
    setError: () => undefined,
    setModelLoading: () => undefined,
    setModelSaving: () => undefined,
    setModelTesting: () => undefined,
    setModelApiKey: () => undefined,
    setModelTestResult: () => undefined,
    setOps: () => undefined,
  } as unknown as AdminActionsParams;
}

beforeEach(() => {
  vi.clearAllMocks();
  apiMocks.adminSaveModelSettings.mockResolvedValue({ ok: true, settings });
  apiMocks.adminTestModelSettings.mockResolvedValue({
    ok: true,
    reachable: true,
    provider: "local",
    model: "local-evidence",
    latency_ms: 1,
    message: "",
    preview: "OK",
  });
});

describe("admin model temperature payloads", () => {
  it("normalizes stale temperatures for both save and test", async () => {
    const actions = createModelActions(modelActionParams(), {
      handleApiError: async () => undefined,
    });

    await actions.saveModelSettings();
    await actions.testModelSettings();

    expect(apiMocks.adminSaveModelSettings.mock.calls[0]?.[0]).toMatchObject({ temperature: 1 });
    expect(apiMocks.adminTestModelSettings.mock.calls[0]?.[0]).toMatchObject({ temperature: 1 });
  });
});
