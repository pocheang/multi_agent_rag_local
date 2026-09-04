import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminFormField, AdminFormSelect } from "@/components/AdminFormField";
import { appApi } from "@/lib/api";
import { normalizeModelTemperature } from "@/lib/model-temperature";
import type {
  AdminModelSettingsView,
  ModelCatalogItem,
  ModelCatalogResponse,
  ModelProvider,
  ProviderCatalogEntry,
} from "@/types/api";

const PROVIDERS: ModelProvider[] = ["local", "ollama", "openai", "deepseek", "anthropic", "custom"];

const FALLBACK_DEFAULTS: Record<
  ModelProvider,
  Pick<AdminModelSettingsView, "base_url" | "chat_model" | "reasoning_model" | "embedding_model">
> = {
  local: { base_url: "", chat_model: "local-evidence", reasoning_model: "local-evidence", embedding_model: "local-hash-384" },
  ollama: { base_url: import.meta.env.VITE_OLLAMA_BASE_URL || "http://localhost:11434", chat_model: "qwen3:14b", reasoning_model: "deepseek-r1:32b", embedding_model: "nomic-embed-text" },
  openai: { base_url: "https://api.openai.com/v1", chat_model: "gpt-5.5", reasoning_model: "gpt-5.5", embedding_model: "text-embedding-3-small" },
  deepseek: { base_url: "https://api.deepseek.com/v1", chat_model: "deepseek-v4-flash", reasoning_model: "deepseek-v4-pro", embedding_model: "" },
  anthropic: { base_url: "https://api.anthropic.com", chat_model: "claude-sonnet-5", reasoning_model: "claude-fable-5", embedding_model: "" },
  custom: { base_url: "", chat_model: "", reasoning_model: "", embedding_model: "" },
};

interface Props {
  modelSettings: AdminModelSettingsView | null;
  modelLoading: boolean;
  modelSaving: boolean;
  modelTesting: boolean;
  modelTestResult: { type: "success" | "error"; message: string } | null;
  onRefresh: () => void;
  onSave: () => void;
  onTest: () => void;
  onPatch: (patch: Partial<AdminModelSettingsView>) => void;
  modelApiKey: string;
  onApiKeyChange: (key: string) => void;
}

function optionsForRole(metadata: ProviderCatalogEntry | undefined, role: string) {
  return (metadata?.models || [])
    .filter((model) => model.roles.includes(role))
    .map((model) => ({ value: model.id, label: model.recommended ? `${model.label} - Recommended` : model.label }));
}

function selectedModel(metadata: ProviderCatalogEntry | undefined, id: string): ModelCatalogItem | undefined {
  return metadata?.models.find((model) => model.id === id);
}

export function AdminModelSettings({
  modelSettings,
  modelLoading,
  modelSaving,
  modelTesting,
  modelTestResult,
  onRefresh,
  onSave,
  onTest,
  onPatch,
  modelApiKey,
  onApiKeyChange,
}: Props) {
  const { t } = useTranslation();
  const [catalog, setCatalog] = useState<ModelCatalogResponse | null>(null);

  useEffect(() => {
    let active = true;
    void appApi.modelCatalog().then((data) => {
      if (active) setCatalog(data);
    }).catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const provider = (modelSettings?.provider || "local") as ModelProvider;
  const metadata = catalog?.providers?.[provider];
  const providerOptions = useMemo(
    () => PROVIDERS.map((value) => ({ value, label: catalog?.providers?.[value]?.label || value })),
    [catalog],
  );
  const chatOptions = optionsForRole(metadata, "chat");
  const reasoningOptions = optionsForRole(metadata, "reasoning");
  const embeddingOptions = optionsForRole(metadata, "embedding");
  const requiresApiKey = metadata?.requires_api_key ?? !["local", "ollama"].includes(provider);
  const supportsEmbeddings = metadata?.supports_embeddings ?? !["anthropic", "deepseek"].includes(provider);
  const selected = selectedModel(metadata, modelSettings?.chat_model || "");

  const changeProvider = (nextProvider: ModelProvider) => {
    const next = catalog?.providers?.[nextProvider];
    const fallback = FALLBACK_DEFAULTS[nextProvider];
    onPatch({
      provider: nextProvider,
      api_key_masked: "",
      base_url: next?.base_url ?? fallback.base_url,
      chat_model: next?.default_chat_model ?? fallback.chat_model,
      reasoning_model: next?.default_reasoning_model ?? fallback.reasoning_model,
      embedding_model: next?.default_embedding_model ?? fallback.embedding_model,
    });
    onApiKeyChange("");
  };

  const renderModelField = (
    label: string,
    value: string,
    options: Array<{ value: string; label: string }>,
    onChange: (value: string) => void,
  ) => options.length > 0 ? (
    <AdminFormSelect label={label} value={value} onChange={onChange} options={options} required />
  ) : (
    <AdminFormField label={label} value={value} onChange={onChange} placeholder="model-id" required />
  );

  return (
    <main className="panel ops-wrap admin-model-console">
      <div className="section-head">
        <div>
          <strong>{t("admin.ui.globalModelConfig", "Global model configuration")}</strong>
          <p className="admin-form-hint">
            {catalog ? `Provider catalog ${catalog.version}` : t("admin.ui.catalogFallback", "Using verified fallback catalog")}
          </p>
        </div>
        <div className="row-actions">
          <button type="button" className="secondary tiny-btn" onClick={onRefresh}>{t("common.refresh", "Refresh")}</button>
          <button type="button" className="secondary tiny-btn" onClick={onTest} disabled={modelTesting || modelSaving}>
            {modelTesting ? t("admin.ui.testing", "Testing") : t("admin.ui.connectionTest", "Connection test")}
          </button>
          <button type="button" className="tiny-btn" onClick={onSave} disabled={modelSaving || modelTesting}>
            {modelSaving ? t("admin.ui.saving", "Saving") : t("admin.ui.saveConfig", "Save config")}
          </button>
        </div>
      </div>

      {modelLoading && <div className="skeleton-list" />}
      {!modelLoading && !modelSettings && <div className="admin-state-panel is-error">Model settings are unavailable.</div>}

      {!modelLoading && modelSettings && (
        <>
          <div className="ops-kpi-grid ops-kpi-grid-secondary">
            <div className="ops-kpi-card"><span>Override</span><strong>{modelSettings.enabled ? "Enabled" : "Disabled"}</strong></div>
            <div className="ops-kpi-card"><span>Provider</span><strong>{metadata?.label || provider}</strong></div>
            <div className="ops-kpi-card"><span>Chat</span><strong>{modelSettings.chat_model || "-"}</strong></div>
            <div className="ops-kpi-card"><span>Embedding</span><strong>{supportsEmbeddings ? modelSettings.embedding_model || "-" : "Existing pipeline"}</strong></div>
          </div>

          {modelSettings.environment_pinned && (
            <div className="admin-model-banner admin-model-banner-warning" role="status">
              <span className="admin-model-banner-mark">!</span>
              <div>
                <strong>
                  {t(
                    "admin.ui.modelSettingsPinned",
                    "These settings are saved but not in effect",
                  )}
                </strong>
                <p>
                  {modelSettings.pinned_reason ||
                    t(
                      "admin.ui.modelSettingsPinnedReason",
                      "The process environment pins the model backend; this configuration takes effect once that is unset.",
                    )}
                </p>
              </div>
            </div>
          )}

          <div className="admin-model-banner">
            <span className="admin-model-banner-mark">API</span>
            <div>
              <strong>{metadata?.note || "Provider settings are validated by the backend before activation."}</strong>
              {selected?.deprecated_after && <p>Deprecated after {new Date(selected.deprecated_after).toLocaleString()}</p>}
            </div>
          </div>

          <div className="ops-two-col admin-section-head-offset">
            <label className="ops-auto-refresh">
              <input type="checkbox" checked={Boolean(modelSettings.enabled)} onChange={(event) => onPatch({ enabled: event.target.checked })} />
              <span>
                {t(
                  "admin.ui.enableGlobalModelOverride",
                  "Enable global model override (replaces every user's own API settings)",
                )}
              </span>
            </label>
            <AdminFormSelect label={t("admin.ui.backendType", "Backend type")} value={provider} onChange={(value) => changeProvider(value as ModelProvider)} options={providerOptions} />
          </div>

          {provider !== "local" && (
            <div className="ops-two-col">
              <AdminFormField label="Base URL" value={modelSettings.base_url} onChange={(value) => onPatch({ base_url: value })} placeholder="https://api.example.com/v1" required />
              <AdminFormField label="API Key" type="password" value={modelApiKey} onChange={onApiKeyChange} placeholder={modelSettings.api_key_masked ? `Saved: ${modelSettings.api_key_masked}` : "Stored securely after save"} required={requiresApiKey} />
            </div>
          )}

          <div className="ops-two-col">
            {renderModelField(t("admin.ui.chatModel", "Chat model"), modelSettings.chat_model, chatOptions, (value) => onPatch({ chat_model: value }))}
            {renderModelField(t("admin.ui.reasoningModel", "Reasoning model"), modelSettings.reasoning_model, reasoningOptions, (value) => onPatch({ reasoning_model: value }))}
          </div>

          <div className="ops-two-col">
            {supportsEmbeddings ? renderModelField(t("admin.ui.embeddingModel", "Embedding model"), modelSettings.embedding_model, embeddingOptions, (value) => onPatch({ embedding_model: value })) : (
              <div className="admin-state-panel">
                <strong>Embedding pipeline unchanged</strong>
                <p className="muted">This provider has no embedding endpoint. Existing vectors and the configured environment embedding model remain active.</p>
              </div>
            )}
            <AdminFormField label="Max Tokens" type="number" value={String(modelSettings.max_tokens)} onChange={(value) => onPatch({ max_tokens: Number(value) || 2048 })} />
          </div>

          <label className="admin-field admin-model-slider">
            <span>Temperature {Number(modelSettings.temperature || 0).toFixed(1)}</span>
            <input type="range" min={0} max={1} step={0.1} value={modelSettings.temperature} onChange={(event) => onPatch({
              temperature: normalizeModelTemperature(Number(event.target.value), modelSettings.temperature),
            })} />
          </label>

          {modelTestResult && <div className={`admin-state-panel ${modelTestResult.type === "error" ? "is-error" : "is-success"}`}>{modelTestResult.message}</div>}
        </>
      )}
    </main>
  );
}
