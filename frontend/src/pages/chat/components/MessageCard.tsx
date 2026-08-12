import { useTranslation } from "react-i18next";
import type { SessionMessage } from "@/types/api";
import { EMPTY_METADATA } from "@/pages/chat/constants";
import { MarkdownBlock } from "@/pages/chat/components/MarkdownBlock";
import { CollapsibleSection } from "@/pages/chat/components/CollapsibleSection";
import { MetadataBadges } from "@/pages/chat/components/MetadataBadges";

type Props = {
  message: SessionMessage;
  onEditMessage: (msg: SessionMessage) => Promise<void>;
  onRemoveMessage: (msg: SessionMessage) => Promise<void>;
};

export function MessageCard({ message, onEditMessage, onRemoveMessage }: Props) {
  const { t, i18n } = useTranslation();
  const isAssistant = message.role === "assistant";
  const metadata = message.metadata || EMPTY_METADATA;
  const timeLocale = i18n.language === "zh" ? "zh-CN" : "en-US";

  return (
    <article
      className={`bubble ${isAssistant ? "assistant" : "user"}`}
      role="article"
      aria-label={isAssistant ? t("components.messages.assistantReply") : t("components.messages.userMessage")}
    >
      <div className="message-head">
        <div className="message-identity">
          <span className="message-avatar" aria-hidden="true">{isAssistant ? "AI" : "U"}</span>
          <span className="message-role">{isAssistant ? t("components.messages.assistant") : t("components.messages.you")}</span>
        </div>
        {!message.message_id || message.message_id.startsWith("local-") ? null : (
          <div className="row-actions">
            <button
              type="button"
              className="secondary tiny-btn"
              onClick={() => void onEditMessage(message)}
              aria-label={t("components.messages.editMessage")}
            >
              {t("components.messages.edit")}
            </button>
            <button
              type="button"
              className="danger tiny-btn"
              onClick={() => {
                if (window.confirm(t("components.messages.deleteConfirm"))) {
                  void onRemoveMessage(message);
                }
              }}
              aria-label={t("components.messages.deleteMessage")}
            >
              {t("components.messages.delete")}
            </button>
          </div>
        )}
      </div>

      <div className="markdown">
        <MarkdownBlock text={message.content || ""} />
      </div>

      {isAssistant && (
        <>
          <MetadataBadges metadata={metadata} />

          {(metadata.execution_steps || []).length > 0 && (
            <CollapsibleSection
              open={message.message_id === "local-assistant-stream"}
              className="process-panel"
              title={t("components.messages.execution")}
              ariaLabel={t("components.messages.toggleExecution")}
            >
              <div className="process-timeline">
                {(metadata.execution_steps || []).map((step, index) => (
                  <div key={`${message.message_id}-step-${index}`} className="process-step">
                    <div className="process-step-head">
                      <span className={`process-kind kind-${step.kind || "default"}`}>{step.kind || "step"}</span>
                      <strong>{step.label || t("components.messages.processing")}</strong>
                      <span className="process-time">
                        {step.at ? new Date(step.at).toLocaleTimeString(timeLocale, { hour12: false }) : ""}
                      </span>
                    </div>
                    {step.detail && <div className="process-detail">{step.detail}</div>}
                  </div>
                ))}
              </div>
            </CollapsibleSection>
          )}

          {(metadata.thoughts || []).length > 0 && (
            <CollapsibleSection title={t("components.messages.thoughts")} ariaLabel={t("components.messages.toggleThoughts")}>
              <ul className="compact-list">
                {(metadata.thoughts || []).slice(-8).map((thought, index) => (
                  <li key={`${message.message_id}-thought-${index}`}>{thought}</li>
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {(metadata.citations || []).length > 0 && (
            <CollapsibleSection title={t("components.messages.citations")} ariaLabel={t("components.messages.toggleCitations")}>
              <div className="citation-grid">
                {(metadata.citations || []).slice(0, 8).map((citation, index) => (
                  <div key={`${message.message_id}-cit-${index}`} className="citation-card">
                    <strong>{citation.source || "unknown"}</strong>
                    <MarkdownBlock text={citation.content || ""} />
                  </div>
                ))}
              </div>
            </CollapsibleSection>
          )}

          {metadata.quality_report && Object.keys(metadata.quality_report).length > 0 && (
            <CollapsibleSection title={t("components.messages.qualityReport")} ariaLabel={t("components.messages.toggleQualityReport")}>
              <pre className="graph-context">{JSON.stringify(metadata.quality_report, null, 2)}</pre>
            </CollapsibleSection>
          )}

          {metadata.graph_result &&
            (metadata.graph_result.neighbors.length > 0 || metadata.graph_result.paths.length > 0) && (
              <CollapsibleSection title={t("components.messages.graph")} ariaLabel={t("components.messages.toggleGraph")}>
                <div className="graph-result-panel">
                  {metadata.graph_result.neighbors.length > 0 && (
                    <div className="graph-section">
                      <strong>{t("components.messages.neighbors", { count: metadata.graph_result.neighbors.length })}</strong>
                      <div className="graph-neighbors">
                        {metadata.graph_result.neighbors.slice(0, 10).map((neighbor, index) => (
                          <div key={`${message.message_id}-neighbor-${index}`} className="graph-neighbor-item">
                            <span className="graph-entity">{neighbor.entity}</span>
                            <span className="graph-relation">
                              {neighbor.direction === "out" ? "->" : "<-"}
                              <span className="relation-label">{neighbor.relation}</span>
                              {neighbor.direction === "out" ? "->" : "<-"}
                            </span>
                            <span className="graph-target">{t("components.messages.targetEntity")}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {metadata.graph_result.paths.length > 0 && (
                    <div className="graph-section">
                      <strong>{t("components.messages.paths", { count: metadata.graph_result.paths.length })}</strong>
                      <div className="graph-paths">
                        {metadata.graph_result.paths.slice(0, 5).map((path, index) => {
                          const hasNewFormat = "entities" in path && Array.isArray(path.entities);
                          const hasOldFormat = "source" in path && "middle" in path && "target" in path;

                          if (hasNewFormat) {
                            return (
                              <div key={`${message.message_id}-path-${index}`} className="graph-path-item">
                                {path.entities.map((entity, entityIndex) => (
                                  <span key={`${entity}-${entityIndex}`} className="path-segment">
                                    <span className="path-entity">{entity}</span>
                                    {entityIndex < (path.relations?.length || 0) && (
                                      <span className="path-arrow">
                                        {" -> "}
                                        <span className="path-relation">{path.relations[entityIndex]}</span>
                                        {" -> "}
                                      </span>
                                    )}
                                  </span>
                                ))}
                              </div>
                            );
                          }

                          if (hasOldFormat) {
                            return (
                              <div key={`${message.message_id}-path-${index}`} className="graph-path-item">
                                <span className="path-segment">
                                  <span className="path-entity">{path.source}</span>
                                  <span className="path-arrow"> -&gt; <span className="path-relation">{path.rel1 || "RELATED"}</span> -&gt; </span>
                                </span>
                                <span className="path-segment">
                                  <span className="path-entity">{path.middle}</span>
                                  <span className="path-arrow"> -&gt; <span className="path-relation">{path.rel2 || "RELATED"}</span> -&gt; </span>
                                </span>
                                <span className="path-segment">
                                  <span className="path-entity">{path.target}</span>
                                </span>
                              </div>
                            );
                          }

                          return (
                            <div key={`${message.message_id}-path-${index}`} className="graph-path-item">
                              <span className="path-error">{t("components.messages.pathIncomplete")}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  {metadata.graph_result.context && (
                    <div className="graph-section">
                      <strong>{t("components.messages.graphContext")}</strong>
                      <pre className="graph-context">{metadata.graph_result.context}</pre>
                    </div>
                  )}
                </div>
              </CollapsibleSection>
            )}
        </>
      )}
    </article>
  );
}
