import { useTranslation } from "react-i18next";
import type { OpsOverview } from "@/types/api";

type Props = {
  ops: OpsOverview;
};

export function AdminOpsDiagnostics({ ops }: Props) {
  const { t } = useTranslation();

  const renderValue = (value: string | undefined | null, defaultText = "-") => {
    if (!value || value === "" || value === "null" || value === "undefined") {
      return <span style={{ color: 'var(--text-tertiary)', fontStyle: 'italic' }}>{defaultText}</span>;
    }
    return <code style={{ fontSize: 'var(--text-sm)' }}>{value}</code>;
  };

  const renderStatus = (ok: boolean, error?: string) => {
    if (ok) {
      return <span className="badge badge-success">✓ OK</span>;
    }
    return (
      <span className="badge badge-danger" title={error || "Unknown error"}>
        ✗ {error || "Error"}
      </span>
    );
  };

  return (
    <>
      <div className="section-head" style={{ marginTop: 'var(--space-4)' }}>
        <strong>{t("admin.ui.diagnostics", "System Diagnostics")}</strong>
      </div>
      <p className="muted" style={{ marginTop: -2, marginBottom: 'var(--space-4)' }}>
        {t("admin.ui.diagnosticsHint", "System environment, model configuration, and service status")}
      </p>

      <div className="ops-two-col">
        {/* Environment & Models */}
        <div className="ops-trend-list">
          <strong>{t("admin.ui.environmentModels", "Environment & Models")}</strong>
          <div className="ops-diagnostic-list" style={{ marginTop: 'var(--space-3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--border-light)' }}>
              <span style={{ fontWeight: 500 }}>Python</span>
              {renderValue(ops.diagnostics?.python_executable, "Not configured")}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--border-light)' }}>
              <span style={{ fontWeight: 500 }}>{t("admin.ui.pythonVersion", "Python Version")}</span>
              {renderValue(ops.diagnostics?.python_version, "Unknown")}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--border-light)' }}>
              <span style={{ fontWeight: 500 }}>{t("admin.ui.condaEnv", "Conda Environment")}</span>
              {renderValue(ops.diagnostics?.conda_env, "Not using Conda")}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--border-light)' }}>
              <span style={{ fontWeight: 500 }}>Conda Prefix</span>
              {renderValue(ops.diagnostics?.conda_prefix, "N/A")}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--border-light)' }}>
              <span style={{ fontWeight: 500 }}>{t("admin.ui.modelBackend", "Model Backend")}</span>
              {renderValue(ops.diagnostics?.model_backend, "Not configured")}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--border-light)' }}>
              <span style={{ fontWeight: 500 }}>{t("admin.ui.reasoningBackend", "Reasoning Backend")}</span>
              {renderValue(ops.diagnostics?.reasoning_model_backend, "Same as model backend")}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--border-light)' }}>
              <span style={{ fontWeight: 500 }}>Ollama URL</span>
              {renderValue(ops.diagnostics?.ollama_base_url, "Not configured")}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--border-light)' }}>
              <span style={{ fontWeight: 500 }}>{t("admin.ui.chatModel", "Chat Model")}</span>
              {renderValue(ops.diagnostics?.ollama_chat_model, "Default model")}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--space-2) 0' }}>
              <span style={{ fontWeight: 500 }}>Embedding Model</span>
              {renderValue(ops.diagnostics?.ollama_embed_model, "Default embedding")}
            </div>
          </div>
        </div>

        {/* Service Status */}
        <div className="ops-trend-list">
          <strong>{t("admin.ui.keyServiceDetails", "Service Status & Details")}</strong>
          <div className="ops-diagnostic-list" style={{ marginTop: 'var(--space-3)' }}>
            {Object.entries(ops.services || {}).length > 0 ? (
              Object.entries(ops.services || {}).map(([name, service]) => (
                <div
                  key={`svc-detail-${name}`}
                  style={{
                    padding: 'var(--space-3)',
                    marginBottom: 'var(--space-2)',
                    background: 'var(--surface-hover)',
                    borderRadius: 'var(--radius-md)',
                    border: `1px solid ${service.ok ? 'var(--success)' : 'var(--danger)'}`
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
                    <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)' }}>{name}</span>
                    {renderStatus(service.ok, service.error)}
                  </div>
                  {service.path && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)' }}>
                      <strong>Path:</strong> <code style={{ fontSize: 'var(--text-xs)' }}>{service.path}</code>
                    </div>
                  )}
                  {service.models && service.models.length > 0 && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)' }}>
                      <strong>Models:</strong> {service.models.map((model, idx) => (
                        <span key={idx} className="badge badge-info" style={{ marginLeft: 'var(--space-1)', fontSize: '10px' }}>
                          {model}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div style={{
                padding: 'var(--space-6)',
                textAlign: 'center',
                color: 'var(--text-tertiary)',
                fontStyle: 'italic'
              }}>
                {t("admin.ui.noServiceData", "No service data available")}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
