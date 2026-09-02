import { useTranslation } from "react-i18next";

type AgentClassHint = "" | "general" | "cybersecurity" | "artificial_intelligence" | "pdf_text";

type AgentMode = {
  key: AgentClassHint;
  title: string;
  desc: string;
};

type Props = {
  agentClassHint: AgentClassHint;
  agentModes: AgentMode[];
  agentDistribution: Array<{ agent: string; count: number }>;
  onSwitchAgentMode: (mode: AgentClassHint) => void;
};

export function AgentWorkbench({
  agentClassHint,
  agentModes,
  agentDistribution,
  onSwitchAgentMode,
}: Props) {
  const { t } = useTranslation();

  return (
    <section className="panel">
      <div className="section-head">
        <strong>{t("components.messages.agentWorkbench")}</strong>
        <small className="muted">{t("components.messages.current", { mode: agentClassHint || t("components.workbench.auto") })}</small>
      </div>
      <div className="agent-mode-grid">
        {agentModes.map((mode) => (
          <button
            key={mode.title}
            type="button"
            className={`agent-mode-card ${agentClassHint === mode.key ? "active" : ""}`}
            /* One mode is in effect at a time, so these are a single-select
               group, not four independent actions. Without this the selection
               is carried by colour alone and is not announced at all. */
            aria-pressed={agentClassHint === mode.key}
            onClick={() => onSwitchAgentMode(mode.key)}
            title={`${mode.title}: ${mode.desc}`}
          >
            <strong>{mode.title}</strong>
            <span>{mode.desc}</span>
          </button>
        ))}
      </div>
      <div className="agent-stats">
        {agentDistribution.length === 0 && <span className="muted">{t("components.messages.noIndexedDocs")}</span>}
        {agentDistribution.map((item) => (
          <span key={item.agent} className="chip">
            {item.agent}: {item.count}
          </span>
        ))}
      </div>
    </section>
  );
}
