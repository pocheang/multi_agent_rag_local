import { useTranslation } from "react-i18next";
import type { ApiConfig } from "./apiSettingsConstants";

type Props = {
  config: ApiConfig;
  selectedModels: string[];
  requiresApiKey: boolean;
  requiresBaseUrl: boolean;
  showApiKey: boolean;
  onShowApiKeyToggle: () => void;
  onConfigChange: (patch: Partial<ApiConfig>) => void;
};

export function ApiSettingsFormFields({
  config,
  selectedModels,
  requiresApiKey,
  requiresBaseUrl,
  showApiKey,
  onShowApiKeyToggle,
  onConfigChange,
}: Props) {
  const { t } = useTranslation();

  return (
    <>
      <section className="settings-section">
        <div className="settings-note">{t("components.apiSettings.note")}</div>
      </section>

      {requiresApiKey && (
        <section className="settings-section">
          <label className="section-label" htmlFor="api-key-input">{t("components.apiSettings.apiKey")}</label>
          <div className="input-with-action">
            <input
              id="api-key-input"
              type={showApiKey ? "text" : "password"}
              className="api-input-field"
              placeholder={config.apiKeyMasked ? t("components.apiSettings.saved", { value: config.apiKeyMasked }) : "sk-..."}
              value={config.apiKey}
              onChange={(e) => onConfigChange({ apiKey: e.target.value, apiKeyMasked: "" })}
            />
            <button type="button" className="input-action-btn" onClick={onShowApiKeyToggle}>
              {showApiKey ? t("components.apiSettings.hide") : t("components.apiSettings.show")}
            </button>
          </div>
        </section>
      )}

      {requiresBaseUrl && (
        <section className="settings-section">
          <label className="section-label" htmlFor="base-url-input">{t("components.apiSettings.baseUrl")}</label>
          <input
            id="base-url-input"
            type="text"
            className="api-input-field"
            placeholder="https://api.example.com/v1"
            value={config.baseUrl}
            onChange={(e) => onConfigChange({ baseUrl: e.target.value })}
          />
        </section>
      )}

      <section className="settings-section">
        <label className="section-label" htmlFor="model-input">{t("components.apiSettings.model")}</label>
        {selectedModels.length > 0 ? (
          <select
            id="model-input"
            className="api-select"
            value={config.model}
            onChange={(e) => onConfigChange({ model: e.target.value })}
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
            onChange={(e) => onConfigChange({ model: e.target.value })}
          />
        )}
      </section>

      <section className="settings-section">
        <label className="section-label" htmlFor="temperature-input">
          {t("components.apiSettings.temperature")}
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
          onChange={(e) => onConfigChange({ temperature: Number(e.target.value) })}
        />
        <div className="slider-labels">
          <span>{t("components.apiSettings.stable")}</span>
          <span>{t("components.apiSettings.balanced")}</span>
          <span>{t("components.apiSettings.creative")}</span>
        </div>
      </section>

      <section className="settings-section">
        <label className="section-label" htmlFor="max-tokens-input">
          {t("components.apiSettings.maxTokens")}
          <span className="label-value">{config.maxTokens}</span>
        </label>
        <input
          id="max-tokens-input"
          type="range"
          className="api-slider"
          min="256"
          max="131072"
          step="1024"
          value={config.maxTokens}
          onChange={(e) => onConfigChange({ maxTokens: Number(e.target.value) })}
        />
        <div className="slider-labels">
          <span>256</span>
          <span>65536</span>
          <span>131072</span>
        </div>
      </section>
    </>
  );
}
