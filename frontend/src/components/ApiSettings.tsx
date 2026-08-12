import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { IntegrationsPanel } from "@/features/integrations/IntegrationsPanel";
import { appApi } from "@/lib/api";
import type { ModelCatalogResponse } from "@/types/api";
import { ApiSettingsFormFields } from "./ApiSettingsFormFields";
import { ApiSettingsPresets } from "./ApiSettingsPresets";
import { ApiSettingsProviderTabs } from "./ApiSettingsProviderTabs";
import {
  type Provider,
  type ApiConfig,
  PROVIDER_MODELS,
  QUICK_PRESETS,
  PROVIDERS,
  DEFAULT_CONFIG,
} from "./apiSettingsConstants";
import {
  requiresApiKey,
  requiresBaseUrl,
  validateConfig,
  buildApiPayload,
  applyProviderDefaults,
  parseApiResponse,
} from "./apiSettingsUtils";

let modalStylesLoaded = false;
async function loadModalStyles() {
  if (!modalStylesLoaded) {
    await import("@/styles/components/modals.css");
    await import("@/styles/components/dropdowns.css");
    modalStylesLoaded = true;
  }
}

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

export function ApiSettings({ isOpen, onClose }: Props) {
  const { t } = useTranslation();
  const [config, setConfig] = useState<ApiConfig>(DEFAULT_CONFIG);
  const [showApiKey, setShowApiKey] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [result, setResult] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(isOpen);
  const [catalog, setCatalog] = useState<ModelCatalogResponse | null>(null);

  const selectedModels = useMemo(() => {
    const catalogModels = catalog?.providers[config.provider]?.models
      .filter((model) => model.roles.includes("chat") || model.roles.includes("reasoning"))
      .map((model) => model.id);
    return catalogModels?.length ? catalogModels : PROVIDER_MODELS[config.provider] || [];
  }, [catalog, config.provider]);
  const needsApiKey = requiresApiKey(config.provider);
  const needsBaseUrl = requiresBaseUrl(config.provider);

  const loadSettings = async () => {
    setIsLoading(true);
    setResult(null);
    try {
      const [response, catalogResponse] = await Promise.all([
        appApi.getUserApiSettings(),
        appApi.modelCatalog().catch(() => null),
      ]);
      if (catalogResponse) setCatalog(catalogResponse);
      if (response.ok && response.settings) {
        setConfig(parseApiResponse(response.settings));
      }
    } catch (error) {
      setResult({ type: "error", message: error instanceof Error ? error.message : t("components.apiSettings.loadFailed") });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      void loadModalStyles();
      void loadSettings();
    } else {
      setIsLoading(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const patchConfig = (patch: Partial<ApiConfig>) => {
    setConfig((prev) => ({ ...prev, ...patch }));
    setResult(null);
  };

  const changeProvider = (provider: Provider) => {
    patchConfig(applyProviderDefaults(provider, catalog?.providers[provider]));
  };

  const applyPreset = (preset: typeof QUICK_PRESETS[number]) => {
    const defaults = applyProviderDefaults(preset.provider, catalog?.providers[preset.provider]);
    patchConfig({ ...defaults, model: preset.model });
  };

  const handleCheck = async () => {
    setIsChecking(true);
    setResult(null);
    try {
      const message = validateConfig(config);
      if (message) throw new Error(message);
      const payload = buildApiPayload(config);
      const probe = await appApi.testUserApiSettings(payload);
      if (probe.ok && probe.reachable) {
        const previewSuffix = probe.preview ? t("components.apiSettings.preview", { preview: probe.preview }) : "";
        setResult({
          type: "success",
          message: t("components.apiSettings.connectionSuccess", {
            latency: probe.latency_ms,
            preview: previewSuffix,
          }),
        });
      } else {
        setResult({
          type: "error",
          message: probe.message || t("components.apiSettings.connectionFailed"),
        });
      }
    } catch (error) {
      setResult({ type: "error", message: error instanceof Error ? error.message : t("components.apiSettings.checkFailed") });
    } finally {
      setIsChecking(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setResult(null);
    try {
      const message = validateConfig(config);
      if (message) throw new Error(message);
      const payload = buildApiPayload(config);
      const saved = await appApi.saveUserApiSettings(payload);
      setConfig((prev) => ({
        ...prev,
        apiKey: "",
        apiKeyMasked: saved.settings?.api_key_masked || prev.apiKeyMasked,
      }));
      setResult({ type: "success", message: t("components.apiSettings.saveSuccess") });
      window.setTimeout(onClose, 900);
    } catch (error) {
      setResult({ type: "error", message: error instanceof Error ? error.message : t("components.apiSettings.saveFailed") });
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      <button
        type="button"
        className="api-settings-overlay"
        onClick={onClose}
        aria-label={t("components.apiSettings.close")}
      />
      <aside className="api-settings-panel" role="dialog" aria-modal="true" aria-labelledby="api-settings-title">
        <header className="settings-header">
          <div className="settings-header-content">
            <div className="settings-icon" aria-hidden="true">API</div>
            <div>
              <h2 id="api-settings-title" className="settings-title">{t("components.apiSettings.title")}</h2>
              <p className="settings-subtitle">{t("components.apiSettings.subtitle")}</p>
            </div>
          </div>
          <button type="button" className="close-btn" onClick={onClose} aria-label={t("components.apiSettings.close")}>
            <span aria-hidden="true">x</span>
          </button>
        </header>

        <div className="settings-content">
          {isLoading ? (
            <div className="settings-loading">{t("components.apiSettings.loading")}</div>
          ) : (
            <>
              {config.globalOverrideEnabled && (
                <div className="global-override-notice">
                  <span className="notice-icon" aria-hidden="true">ℹ️</span>
                  <div className="notice-content">
                    <strong>{t("components.apiSettings.globalOverrideNotice")}</strong>
                    <p>
                      {t("components.apiSettings.globalOverrideDesc", {
                        provider: config.globalProvider,
                        model: config.globalModel,
                      })}
                    </p>
                    <p className="muted">
                      {t("components.apiSettings.globalOverrideHint")}
                    </p>
                  </div>
                </div>
              )}

              <ApiSettingsPresets
                presets={QUICK_PRESETS}
                activeProvider={config.provider}
                activeModel={config.model}
                onApplyPreset={applyPreset}
              />

              <ApiSettingsProviderTabs
                providers={PROVIDERS}
                activeProvider={config.provider}
                onChangeProvider={changeProvider}
              />

              <ApiSettingsFormFields
                config={config}
                selectedModels={selectedModels}
                requiresApiKey={needsApiKey}
                requiresBaseUrl={needsBaseUrl}
                showApiKey={showApiKey}
                onShowApiKeyToggle={() => setShowApiKey((v) => !v)}
                onConfigChange={patchConfig}
              />

              <div className="settings-section">
                <IntegrationsPanel />
              </div>

              {result && <div className={`test-result ${result.type}`}>{result.message}</div>}
            </>
          )}
        </div>

        <footer className="settings-footer">
          <button type="button" className="api-btn secondary" onClick={handleCheck} disabled={isChecking || isSaving}>
            {isChecking ? t("components.apiSettings.checking") : t("components.apiSettings.check")}
          </button>
          <button type="button" className="api-btn primary" onClick={handleSave} disabled={isSaving || isChecking}>
            {isSaving ? t("components.apiSettings.saving") : t("components.apiSettings.save")}
          </button>
        </footer>
      </aside>
    </>
  );
}
