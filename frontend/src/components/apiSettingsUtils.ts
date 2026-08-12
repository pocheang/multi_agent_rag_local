import type { ProviderCatalogEntry } from "@/types/api";
import { normalizeModelTemperature } from "@/lib/model-temperature";
import type { ApiConfig, Provider } from "./apiSettingsConstants";
import { PROVIDER_DEFAULTS } from "./apiSettingsConstants";

export function clampNumber(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function requiresApiKey(provider: Provider): boolean {
  return !["local", "ollama"].includes(provider);
}

export function requiresBaseUrl(provider: Provider): boolean {
  return provider !== "local";
}

export function validateConfig(config: ApiConfig): string {
  if (!config.provider) return "Please select provider";
  if (requiresBaseUrl(config.provider) && !config.baseUrl.trim()) return "Base URL is required";
  if (!config.model.trim()) return "Model is required";
  if (requiresApiKey(config.provider) && !config.apiKey.trim() && !config.apiKeyMasked.trim()) {
    return "API key is required for this provider";
  }
  return "";
}

export function buildApiPayload(config: ApiConfig) {
  return {
    provider: config.provider,
    api_key: config.apiKey.trim(),
    base_url: config.baseUrl.trim(),
    model: config.model.trim(),
    temperature: normalizeModelTemperature(Number(config.temperature), 0.7),
    max_tokens: clampNumber(Number(config.maxTokens), 256, 131072),
  };
}

export function applyProviderDefaults(provider: Provider, catalog?: ProviderCatalogEntry): Partial<ApiConfig> {
  const defaults = catalog
    ? { baseUrl: catalog.base_url, model: catalog.default_chat_model }
    : PROVIDER_DEFAULTS[provider];
  return {
    provider,
    baseUrl: defaults.baseUrl,
    model: defaults.model,
    apiKey: "",
    apiKeyMasked: "",
  };
}

export function parseApiResponse(response: any): ApiConfig {
  return {
    provider: (response.provider || "local") as Provider,
    apiKey: "",
    apiKeyMasked: response.api_key_masked || "",
    baseUrl: response.base_url || "",
    model: response.model || "",
    temperature: normalizeModelTemperature(Number(response.temperature), 0.7),
    maxTokens: Number(response.max_tokens ?? 2048),
    globalOverrideEnabled: !!response.global_override_enabled,
    globalProvider: response.global_provider || "",
    globalModel: response.global_model || "",
    effectiveProvider: response.effective_provider || "",
    effectiveModel: response.effective_model || "",
  };
}
