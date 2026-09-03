import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { SessionMessage } from "@/types/api";
import { EMPTY_METADATA } from "@/pages/chat/constants";
import { MarkdownBlock } from "@/pages/chat/components/MarkdownBlock";
import { CollapsibleSection } from "@/pages/chat/components/CollapsibleSection";
import { MetadataBadges } from "@/pages/chat/components/MetadataBadges";
import { AnimatedButtonLite as AnimatedButton } from "@/components/animations/AnimatedButtonLite";
import { ThinkingIndicator } from "@/pages/chat/components/ThinkingIndicator";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useConfirmDialog } from "@/hooks/useConfirmDialog";

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
  const [processExpanded, setProcessExpanded] = useState(false);
  const confirmDialog = useConfirmDialog();

  // Determine if this is a streaming message (thinking state)
  const isStreaming = message.message_id === "local-assistant-stream";
  const isThinking = isStreaming && !message.content;
  const isGenerating = isStreaming && message.content;
  const hasExecutionSteps = (metadata.execution_steps || []).length > 0;

  // Calculate elapsed time from execution steps
  const getElapsedSeconds = () => {
    if (!hasExecutionSteps) return 0;
    const steps = metadata.execution_steps || [];
    const firstStep = steps[0];
    const lastStep = steps[steps.length - 1];
    if (!firstStep?.at || !lastStep?.at) return 0;
    const start = new Date(firstStep.at).getTime();
    const end = new Date(lastStep.at).getTime();
    return Math.round((end - start) / 1000);
  };

  return (
    <>
    <article
      className={`bubble ${isAssistant ? "assistant" : "user"}`}
      aria-label={isAssistant ? t("components.messages.assistantReply") : t("components.messages.userMessage")}
    >
      <div className="message-head">
        <div className="message-identity">
          <span className="message-avatar" aria-hidden="true">{isAssistant ? "AI" : "U"}</span>
          <span className="message-role">{isAssistant ? t("components.messages.assistant") : t("components.messages.you")}</span>
        </div>
        {!message.message_id || message.message_id.startsWith("local-") ? null : (
          <div className="row-actions">
            <AnimatedButton
              onClick={() => void onEditMessage(message)}
              variant="secondary"
              size="small"
              className="tiny-btn"
            >
              {t("components.messages.edit")}
            </AnimatedButton>
            <AnimatedButton
              onClick={async () => {
                const confirmMsg = message.role === "assistant"
                  ? t("components.messages.deleteAssistantConfirm")
                  : t("components.messages.deleteUserConfirm");
                const confirmed = await confirmDialog.confirm({ message: confirmMsg, isDanger: true });
                if (confirmed) {
                  await onRemoveMessage(message);
                }
              }}
              variant="danger"
              size="small"
              className="tiny-btn"
            >
              {t("components.messages.delete")}
            </AnimatedButton>
          </div>
        )}
      </div>

      {/* Show thinking indicator when streaming without content */}
      {isThinking ? (
        <ThinkingIndicator elapsedSeconds={getElapsedSeconds()} />
      ) : (
        <div className="markdown">
          <MarkdownBlock text={message.content || ""} />
          {isGenerating && <span className="cursor-blink">▍</span>}
        </div>
      )}

      {isAssistant && !isThinking && (
        <>
          <MetadataBadges metadata={metadata} />

          {/* Collapsible process summary - hidden by default */}
          {hasExecutionSteps && (
            <>
              <button
                className={`process-summary-toggle ${processExpanded ? "expanded" : ""}`}
                onClick={() => setProcessExpanded(!processExpanded)}
                aria-expanded={processExpanded}
                aria-label={processExpanded ? "隐藏执行过程" : "查看执行过程"}
              >
                <span>已思考 {getElapsedSeconds()} 秒</span>
                <span className="toggle-arrow">▾</span>
              </button>

              {processExpanded && (
                <CollapsibleSection
                  open={true}
                  className="process-panel"
                  title={t("components.messages.execution")}
                  ariaLabel={t("components.messages.toggleExecution")}
                >
                  <div className="process-timeline">
                    {(metadata.execution_steps || []).map((step, index) => {
                      // Filter out technical fields
                      const shouldShow = !["execution started", "trace", "STATUS"].some(
                        (tech) => step.label?.toLowerCase().includes(tech.toLowerCase())
                      );

                      if (!shouldShow) return null;

                      return (
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
                      );
                    })}
                  </div>
                </CollapsibleSection>
              )}
            </>
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

          {(metadata.tool_runs || []).length > 0 && (
            <CollapsibleSection title={t("components.messages.toolRuns")} ariaLabel={t("components.messages.toggleToolRuns")}>
              <ul className="compact-list">
                {(metadata.tool_runs || []).map((run, index) => (
                  <li key={`${message.message_id}-tool-${index}`}>
                    <strong>{run.tool_id}</strong>
                    {" — "}
                    {t(`components.messages.toolStatus.${run.status}`, { defaultValue: run.status })}
                    {run.summary ? `: ${run.summary}` : ""}
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {(metadata.citations || []).length > 0 && (
            <CollapsibleSection title={t("components.messages.citations")} ariaLabel={t("components.messages.toggleCitations")}>
              <div className="citation-grid">
                {/* Not truncated: the answer text cites these by number, so hiding
                    an entry leaves a [n] in the text that resolves to nothing. */}
                {(metadata.citations || []).map((citation, index) => (
                  <div key={`${message.message_id}-cit-${index}`} className="citation-card">
                    <strong>
                      {citation.marker ? `${citation.marker} ` : ""}
                      {citation.source || "unknown"}
                    </strong>
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
    <ConfirmDialog
      isOpen={confirmDialog.isOpen}
      title={t("components.messages.delete")}
      message={confirmDialog.options?.message || ""}
      isDanger={confirmDialog.options?.isDanger}
      onConfirm={confirmDialog.handleConfirm}
      onCancel={confirmDialog.handleCancel}
    />
    </>
  );
}
