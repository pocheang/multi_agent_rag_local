import type { SessionMessageMetadata } from "@/types/api";

type Props = {
  metadata: SessionMessageMetadata;
};

function formatLatency(ms?: number) {
  const value = Number(ms || 0);
  if (!Number.isFinite(value) || value <= 0) return "";
  if (value < 1000) return `${Math.round(value)} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

export function MetadataBadges({ metadata }: Props) {
  const latency = formatLatency(metadata.latency_ms);

  return (
    <div className="chips">
      {metadata.route && <span className="chip">route: {metadata.route}</span>}
      {metadata.execution_route && <span className="chip">exec: {metadata.execution_route}</span>}
      {metadata.route === "smalltalk_fast" && <span className="chip">smalltalk-fast</span>}
      {metadata.agent_class && <span className="chip">agent: {metadata.agent_class}</span>}
      <span className="chip">web: {metadata.web_used ? "yes" : "no"}</span>
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
