import { appApi } from "@/lib/api";
import type { AdminModelSettingsPayload, AdminModelSettingsView } from "@/types/api";
import type { AdminActionsParams, ErrorHandler } from "./types";

const DEFAULT_MODEL_SETTINGS: AdminModelSettingsView = {
  enabled: false,
  provider: "local",
  api_key_masked: "",
  base_url: "",
  chat_model: "local-evidence",
  reasoning_model: "local-evidence",
  embedding_model: "local-hash-384",
  temperature: 0.7,
  max_tokens: 2048,
};

export function createModelActions(params: AdminActionsParams, errorHandler: ErrorHandler) {
  const {
    modelSettings,
    modelApiKey,
    isAdmin,
    setModelSettings,
    setError,
    setModelLoading,
    setModelSaving,
    setModelTesting,
    setModelApiKey,
    setModelTestResult,
    setOps,
  } = params;

  const { handleApiError } = errorHandler;
  const getCurrentSettings = () => modelSettings ?? DEFAULT_MODEL_SETTINGS;

  const buildModelPayload = (): AdminModelSettingsPayload => {
    const settings = getCurrentSettings();
    return {
      enabled: Boolean(settings.enabled),
      provider: settings.provider,
      api_key: modelApiKey.trim(),
      base_url: settings.base_url.trim(),
      chat_model: settings.chat_model.trim(),
      reasoning_model: (settings.reasoning_model || settings.chat_model).trim(),
      embedding_model: settings.embedding_model.trim(),
      temperature: Math.min(2, Math.max(0, Number(settings.temperature || DEFAULT_MODEL_SETTINGS.temperature))),
      max_tokens: Math.min(131072, Math.max(256, Number(settings.max_tokens || DEFAULT_MODEL_SETTINGS.max_tokens))),
    };
  };

  const validateModelSettings = () => {
    const payload = buildModelPayload();
    if (!payload.provider) return "Choose a model provider first.";
    if (payload.provider !== "local" && !payload.base_url) return "Base URL is required for remote providers.";
    if (!payload.chat_model) return "Chat model cannot be empty.";
    if (!["anthropic", "deepseek"].includes(payload.provider) && !payload.embedding_model) return "Embedding model cannot be empty for this provider.";
    if (!["local", "ollama"].includes(payload.provider) && !payload.api_key && !getCurrentSettings().api_key_masked) {
      return "This provider requires an API key.";
    }
    return "";
  };

  const refreshOpsSnapshot = async () => {
    if (!isAdmin) return;
    try {
      setOps(await appApi.adminOpsOverview({ hours: params.opsHours, actorUserId: undefined, actionKeyword: undefined }));
    } catch (e) {
      await handleApiError(e, "Failed to refresh operations metrics.");
    }
  };

  const loadModelSettings = async () => {
    if (!isAdmin) return;
    setModelLoading(true);
    try {
      const res = await appApi.adminModelSettings();
      setModelSettings(res.settings);
      setModelApiKey("");
      setModelTestResult(null);
      setError("");
    } catch (e) {
      await handleApiError(e, "Failed to load model settings.");
    } finally {
      setModelLoading(false);
    }
  };

  const patchModelSettings = (patch: Partial<AdminModelSettingsView>) => {
    setModelSettings((prev) => ({ ...(prev ?? DEFAULT_MODEL_SETTINGS), ...patch }));
    setModelTestResult(null);
  };

  const saveModelSettings = async () => {
    const validationMessage = validateModelSettings();
    if (validationMessage) {
      setModelTestResult({ type: "error", message: validationMessage });
      return;
    }
    setModelSaving(true);
    try {
      const saved = await appApi.adminSaveModelSettings(buildModelPayload());
      setModelSettings(saved.settings);
      setModelApiKey("");
      setModelTestResult({ type: "success", message: "Global model settings saved. New requests will use the updated priority chain." });
      setError("");
      await refreshOpsSnapshot();
    } catch (e) {
      await handleApiError(e, "Failed to save model settings.");
    } finally {
      setModelSaving(false);
    }
  };

  const testModelSettings = async () => {
    const validationMessage = validateModelSettings();
    if (validationMessage) {
      setModelTestResult({ type: "error", message: validationMessage });
      return;
    }
    setModelTesting(true);
    try {
      const res = await appApi.adminTestModelSettings(buildModelPayload());
      setModelTestResult({
        type: res.reachable ? "success" : "error",
        message: res.reachable ? `Connection succeeded (${res.latency_ms}ms)${res.preview ? ` | ${res.preview}` : ""}` : res.message || "Connection failed.",
      });
      setError("");
    } catch (e) {
      await handleApiError(e, "Failed to test model settings.");
    } finally {
      setModelTesting(false);
    }
  };

  return { loadModelSettings, patchModelSettings, saveModelSettings, testModelSettings };
}