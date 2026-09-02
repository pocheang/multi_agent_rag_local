import { useTranslation } from "react-i18next";

import type { RetrievalSourceOutcome, SessionMessageMetadata } from "@/types/api";

type Props = {
  metadata: SessionMessageMetadata;
};

function formatLatency(ms?: number) {
  const value = Number(ms || 0);
  if (!Number.isFinite(value) || value <= 0) return "";
  if (value < 1000) return `${Math.round(value)} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

/**
 * Which sources actually produced evidence for this answer.
 *
 * This used to be one chip, `web: yes/no`, reading a field that no endpoint set
 * -- so it said "no" on every answer, including the ones written entirely from
 * web results. One boolean was the wrong shape anyway: the pipeline searches up
 * to eight sources and knows what each returned.
 *
 * A source that ran and found nothing is worth showing (it explains a thin
 * answer); one skipped because the caller has no documents is not a fact about
 * this answer and stays out.
 */
function sourceChips(metadata: SessionMessageMetadata) {
  const outcomes: RetrievalSourceOutcome[] = metadata.sources ?? [];
  if (outcomes.length === 0) {
    // Older messages, persisted before the metadata carried source outcomes.
    return metadata.web_used ? [{ source: "web", status: "completed", count: 1 }] : [];
  }
  return outcomes.filter((outcome) => outcome.status === "completed");
}

export function MetadataBadges({ metadata }: Props) {
  const { t } = useTranslation();
  const latency = formatLatency(metadata.latency_ms);
  const sources = sourceChips(metadata);

  return (
    <div className="chips">
      {metadata.route && <span className="chip">route: {metadata.route}</span>}
      {metadata.execution_route && <span className="chip">exec: {metadata.execution_route}</span>}
      {metadata.route === "smalltalk_fast" && <span className="chip">smalltalk-fast</span>}
      {metadata.agent_class && <span className="chip">agent: {metadata.agent_class}</span>}
      {sources.length === 0 ? (
        <span className="chip">{t("chat.badges.noSources")}</span>
      ) : (
        sources.map((outcome) => (
          <span
            key={outcome.source}
            className={outcome.count > 0 ? "chip" : "chip chip-muted"}
            title={t("chat.badges.sourceDetail", { source: outcome.source, count: outcome.count })}
          >
            {outcome.source}
            {outcome.count > 0 ? ` ${outcome.count}` : ""}
          </span>
        ))
      )}
      {latency && <span className="chip">time: {latency}</span>}
      {metadata.current_status && <span className="chip">status: {metadata.current_status}</span>}
      {(metadata.graph_entities || []).slice(0, 6).map((entity) => (
        <span key={entity} className="chip">
          {entity}
        </span>
      ))}
    </div>
  );
}
