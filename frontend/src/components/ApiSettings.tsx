import { useEffect, useMemo, useState } from "react";
import { appApi } from "@/lib/api";
import "./ApiSettings.css";

type Provider = "local" | "openai" | "anthropic" | "deepseek" | "ollama" | "custom";

type ApiConfig = {
  provider: Provider;
  apiKey: string;
  apiKeyMasked: string;
  baseUrl: string;
  model: string;
  temperature: number;
  maxTokens: number;
};

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

const PROVIDER_MODELS: Record<Provider, string[]> = {
  local: ["local-evidence"],
  openai: ["gpt-5.4-codex", "gpt-5.2", "gpt-4o", "gpt-4o-mini"],
  anthropic: ["claude-sonnet-4-6", "claude-opus-4-7", "claude-3-5-sonnet-20241022"],
  deepseek: ["deepseek-chat", "deepseek-reasoner"],
  ollama: ["qwen2.5:7b", "qwen2.5:7b-instruct", "llama3.2", "mistral", "phi3"],
  custom: [],
};

const PROVIDER_DEFAULTS: Record<Provider, Pick<ApiConfig, "baseUrl" | "model">> = {
  local: { baseUrl: "", model: "local-evidence" },
  openai: { baseUrl: "https://api.openai.com/v1", model: "gpt-5.4-codex" },
  anthropic: { baseUrl: "https://api.anthropic.com/v1", model: "claude-sonnet-4-6" },
  deepseek: { baseUrl: "https://api.deepseek.com/v1", model: "deepseek-chat" },
  ollama: { baseUrl: "http://localhost:11434", model: "qwen2.5:7b-instruct" },
  custom: { baseUrl: "", model: "" },
};

const QUICK_PRESETS: Array<{ name: string; provider: Provider; model: string; mark: string }> = [
  { name: "Local Evidence", provider: "local", model: "local-evidence", mark: "LC" },
  { name: "Ollama Local", provider: "ollama", model: "qwen2.5:7b-instruct", mark: "OL" },
  { name: "OpenAI GPT", provider: "openai", model: "gpt-5.4-codex", mark: "OA" },
  { name: "DeepSeek", provider: "deepseek", model: "deepseek-chat", mark: "DS" },
  { name: "Claude", provider: "anthropic", model: "claude-sonnet-4-6", mark: "CL" },
];

const DEFAULT_CONFIG: ApiConfig = {
  provider: "ollama",
  apiKey: "",
  apiKeyMasked: "",
  baseUrl: "http://localhost:11434",
  model: "qwen2.5:7b-instruct",
  temperature: 0.7,
  maxTokens: 2048,
};

function clampNumber(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function ApiSettings({ isOpen, onClose }: Props) {
  const [config, setConfig] = useState<ApiConfig>(DEFAULT_CONFIG);
  const [showApiKey, setShowApiKey] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [result, setResult] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen) void loadSettings();
  }, [isOpen]);

  const selectedModels = useMemo(() => PROVIDER_MODELS[config.provider] || [], [config.provider]);
  const requiresApiKey = !["local", "ollama"].includes(config.provider);
  const requiresBaseUrl = config.provider !== "local";

  const loadSettings = async () => {
    setIsLoading(true);
    setResult(null);
    try {
      const response = await appApi.getUserApiSettings();
      if (response.ok && response.settings) {
        setConfig({
          provider: (response.settings.provider || "ollama") as Provider,
          apiKey: "",
          apiKeyMasked: response.settings.api_key_masked || "",
          baseUrl: response.settings.base_url || "",
          model: response.settings.model || "",
          temperature: Number(response.settings.temperature ?? 0.7),
          maxTokens: Number(response.settings.max_tokens ?? 2048),
        });
      }
    } catch (error) {
      setResult({ type: "error", message: error instanceof Error ? error.message : "Failed to load settings" });
    } finally {
      setIsLoading(false);
    }
  };

  const patchConfig = (patch: Partial<ApiConfig>) => {
    setConfig((prev) => ({ ...prev, ...patch }));
    setResult(null);
  };

  const changeProvider = (provider: Provider) => {
    const defaults = PROVIDER_DEFAULTS[provider];
    patchConfig({ provider, baseUrl: defaults.baseUrl, model: defaults.model, apiKey: "", apiKeyMasked: "" });
  };

  const applyPreset = (preset: (typeof QUICK_PRESETS)[number]) => {
    const defaults = PROVIDER_DEFAULTS[preset.provider];
    patchConfig({ provider: preset.provider, baseUrl: defaults.baseUrl, model: preset.model, apiKey: "", apiKeyMasked: "" });
  };

  const validateConfig = () => {
    if (!config.provider) return "Please select provider";
    if (requiresBaseUrl && !config.baseUrl.trim()) return "Base URL is required";
    if (!config.model.trim()) return "Model is required";
    if (requiresApiKey && !config.apiKey.trim() && !config.apiKeyMasked.trim()) return "API key is required for this provider";
    return "";
  };

  const handleCheck = async () => {
    setIsChecking(true);
    setResult(null);
    try {
      const message = validateConfig();
      if (message) throw new Error(message);
      const payload = {
        provider: config.provider,
        api_key: config.apiKey.trim(),
        base_url: config.baseUrl.trim(),
        model: config.model.trim(),
        temperature: clampNumber(Number(config.temperature), 0, 2),
        max_tokens: clampNumber(Number(config.maxTokens), 256, 8192),
      };
      const probe = await appApi.testUserApiSettings(payload);
      if (probe.ok && probe.reachable) {
        const previewSuffix = probe.preview ? ` | Preview: ${probe.preview}` : "";
        setResult({
          type: "success",
          message: `Connection succeeded (${probe.latency_ms}ms)${previewSuffix}`,
        });
      } else {
        setResult({
          type: "error",
          message: probe.message || "Connection failed, check Base URL / API Key / Model",
        });
      }
    } catch (error) {
      setResult({ type: "error", message: error instanceof Error ? error.message : "Config check failed" });
    } finally {
      setIsChecking(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setResult(null);
    try {
      const message = validateConfig();
      if (message) throw new Error(message);
      const payload = {
        provider: config.provider,
        api_key: config.apiKey.trim(),
        base_url: config.baseUrl.trim(),
        model: config.model.trim(),
        temperature: clampNumber(Number(config.temperature), 0, 2),
        max_tokens: clampNumber(Number(config.maxTokens), 256, 8192),
      };
      const saved = await appApi.saveUserApiSettings(payload);
      setConfig((prev) => ({
        ...prev,
        apiKey: "",
        apiKeyMasked: saved.settings?.api_key_masked || prev.apiKeyMasked,
      }));
      setResult({ type: "success", message: "Settings saved. New queries will use this model config." });
      window.setTimeout(onClose, 900);
    } catch (error) {
      setResult({ type: "error", message: error instanceof Error ? error.message : "Save failed" });
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      <button type="button" className="api-settings-overlay" onClick={onClose} aria-label="Close settings" />
      <aside className="api-settings-panel" role="dialog" aria-modal="true" aria-labelledby="api-settings-title">
        <header className="settings-header">
          <div className="settings-header-content">
            <div className="settings-icon" aria-hidden="true">API</div>
            <div>
              <h2 id="api-settings-title" className="settings-title">Model API Settings</h2>
              <p className="settings-subtitle">Chat provider, key, model, and generation params</p>
            </div>
          </div>
          <button type="button" className="close-btn" onClick={onClose} aria-label="Close settings">
            <span aria-hidden="true">x</span>
          </button>
        </header>

        <div className="settings-content">
          {isLoading ? (
            <div className="settings-loading">Loading settings...</div>
          ) : (
            <>
              <section className="settings-section">
                <label className="section-label">Quick Presets</label>
                <div className="preset-grid">
                  {QUICK_PRESETS.map((preset) => (
                    <button
                      key={preset.name}
                      type="button"
                      className={`preset-card ${config.provider === preset.provider && config.model === preset.model ? "active" : ""}`}
                      onClick={() => applyPreset(preset)}
                    >
                      <span className="preset-icon">{preset.mark}</span>
                      <span className="preset-name">{preset.name}</span>
                    </button>
                  ))}
                </div>
              </section>

              <section className="settings-section">
                <label className="section-label">Provider</label>
                <div className="provider-tabs">
                  {(["local", "ollama", "openai", "deepseek", "anthropic", "custom"] as Provider[]).map((provider) => (
                    <button
                      key={provider}
                      type="button"
                      className={`provider-tab ${config.provider === provider ? "active" : ""}`}
                      onClick={() => changeProvider(provider)}
                    >
                      {provider}
                    </button>
                  ))}
                </div>
              </section>

              <section className="settings-section">
                <div className="settings-note">
                  These settings apply to chat and reasoning calls. Embeddings are configured globally by an admin so the vector index stays consistent.
                </div>
              </section>

              {requiresApiKey && (
                <section className="settings-section">
                  <label className="section-label" htmlFor="api-key-input">API Key</label>
                  <div className="input-with-action">
                    <input
                      id="api-key-input"
                      type={showApiKey ? "text" : "password"}
                      className="api-input-field"
                      placeholder={config.apiKeyMasked ? `Saved: ${config.apiKeyMasked}` : "sk-..."}
                      value={config.apiKey}
                      onChange={(e) => patchConfig({ apiKey: e.target.value, apiKeyMasked: "" })}
                    />
                    <button type="button" className="input-action-btn" onClick={() => setShowApiKey((v) => !v)}>
                      {showApiKey ? "Hide" : "Show"}
                    </button>
                  </div>
                </section>
              )}

              {requiresBaseUrl && <section className="settings-section">
                <label className="section-label" htmlFor="base-url-input">Base URL</label>
                <input
                  id="base-url-input"
                  type="text"
                  className="api-input-field"
                  placeholder="https://api.example.com/v1"
                  value={config.baseUrl}
                  onChange={(e) => patchConfig({ baseUrl: e.target.value })}
                />
              </section>}

              <section className="settings-section">
                <label className="section-label" htmlFor="model-input">Model</label>
                {selectedModels.length > 0 ? (
                  <select
                    id="model-input"
                    className="api-select"
                    value={config.model}
                    onChange={(e) => patchConfig({ model: e.target.value })}
                  >
                    {selectedModels.map((model) => (
                      <option key={model} value={model}>{model}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    id="model-input"
                    type="text"
                    className="api-input-field"
                    placeholder="model-name"
                    value={config.model}
                    onChange={(e) => patchConfig({ model: e.target.value })}
                  />
                )}
              </section>

              <section className="settings-section">
                <label className="section-label" htmlFor="temperature-input">
                  Temperature
                  <span className="label-value">{Number(config.temperature).toFixed(1)}</span>
                </label>
                <input
                  id="temperature-input"
                  type="range"
                  className="api-slider"
                  min="0"
                  max="2"
                  step="0.1"
                  value={config.temperature}
                  onChange={(e) => patchConfig({ temperature: Number(e.target.value) })}
                />
                <div className="slider-labels">
                  <span>Stable</span>
                  <span>Balanced</span>
                  <span>Creative</span>
                </div>
              </section>

              <section className="settings-section">
                <label className="section-label" htmlFor="max-tokens-input">
                  Max Tokens
                  <span className="label-value">{config.maxTokens}</span>
                </label>
                <input
                  id="max-tokens-input"
                  type="range"
                  className="api-slider"
                  min="256"
                  max="8192"
                  step="256"
                  value={config.maxTokens}
                  onChange={(e) => patchConfig({ maxTokens: Number(e.target.value) })}
                />
                <div className="slider-labels">
                  <span>256</span>
                  <span>4096</span>
                  <span>8192</span>
                </div>
              </section>

              {result && <div className={`test-result ${result.type}`}>{result.message}</div>}
            </>
          )}
        </div>

        <footer className="settings-footer">
          <button type="button" className="api-btn secondary" onClick={handleCheck} disabled={isChecking || isSaving}>
            {isChecking ? "Checking..." : "Check Config"}
          </button>
          <button type="button" className="api-btn primary" onClick={handleSave} disabled={isSaving || isChecking}>
            {isSaving ? "Saving..." : "Save Settings"}
          </button>
        </footer>
      </aside>
    </>
  );
}
