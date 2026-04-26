import type React from "react";
import type { SessionMessage } from "@/types/api";
import { EMPTY_METADATA } from "@/pages/chat/constants";
import { MarkdownBlock } from "@/pages/chat/components/MarkdownBlock";

type Props = {
  messages: SessionMessage[];
  containerRef: React.MutableRefObject<HTMLDivElement | null>;
  onEditMessage: (msg: SessionMessage) => Promise<void>;
  onRemoveMessage: (msg: SessionMessage) => Promise<void>;
};

function formatLatency(ms?: number) {
  const v = Number(ms || 0);
  if (!Number.isFinite(v) || v <= 0) return "";
  if (v < 1000) return `${Math.round(v)} ms`;
  return `${(v / 1000).toFixed(2)} s`;
}

export function ChatMessages({ messages, containerRef, onEditMessage, onRemoveMessage }: Props) {
  return (
    <section className="chat-window panel" ref={containerRef}>
      {messages.length === 0 && (
        <div className="empty-chat-state">
          <span className="empty-chat-label">Ready</span>
          <h3>开始一次有证据链的分析</h3>
          <p>
            你可以上传 PDF/图片，指定 Agent 模式，选择检索策略，或直接询问知识库。回答会展示路由、检索来源、执行过程和引用片段。
          </p>
        </div>
      )}
      {messages.map((msg) => {
        const isAssistant = msg.role === "assistant";
        const md = msg.metadata || EMPTY_METADATA;

        return (
          <article key={msg.message_id} className={`bubble ${isAssistant ? "assistant" : "user"}`}>
            <div className="message-head">
              <span className="message-role">{isAssistant ? "Assistant" : "You"}</span>
              {msg.message_id.startsWith("local-") ? null : (
                <div className="row-actions">
                  <button type="button" className="secondary tiny-btn" onClick={() => void onEditMessage(msg)}>
                    修改
                  </button>
                  <button type="button" className="danger tiny-btn" onClick={() => void onRemoveMessage(msg)}>
                    删除
                  </button>
                </div>
              )}
            </div>
            <div className="markdown">
              <MarkdownBlock text={msg.content || ""} />
            </div>
            {isAssistant && (
              <>
                <div className="chips">
                  {md.route && <span className="chip">route: {md.route}</span>}
                  {md.execution_route && <span className="chip">exec: {md.execution_route}</span>}
                  {md.retrieval_strategy && <span className="chip">strategy: {md.retrieval_strategy}</span>}
                  {md.route === "smalltalk_fast" && <span className="chip">smalltalk-fast</span>}
                  {md.agent_class && <span className="chip">agent: {md.agent_class}</span>}
                  <span className="chip">web: {md.web_used ? "yes" : "no"}</span>
                  {formatLatency(md.latency_ms) && <span className="chip">time: {formatLatency(md.latency_ms)}</span>}
                  {md.current_status && <span className="chip">status: {md.current_status}</span>}
                  {(md.graph_entities || []).slice(0, 6).map((x) => (
                    <span key={x} className="chip">
                      {x}
                    </span>
                  ))}
                </div>
                {(md.execution_steps || []).length > 0 && (
                  <details open={msg.message_id === "local-assistant-stream"} className="process-panel">
                    <summary>执行过程</summary>
                    <div className="process-timeline">
                      {(md.execution_steps || []).map((step, i) => (
                        <div key={`${msg.message_id}-step-${i}`} className="process-step">
                          <div className="process-step-head">
                            <span className={`process-kind kind-${step.kind || "default"}`}>{step.kind || "step"}</span>
                            <strong>{step.label || "处理中"}</strong>
                            <span className="process-time">
                              {step.at ? new Date(step.at).toLocaleTimeString("zh-CN", { hour12: false }) : ""}
                            </span>
                          </div>
                          {step.detail && <div className="process-detail">{step.detail}</div>}
                        </div>
                      ))}
                    </div>
                  </details>
                )}
                {(md.thoughts || []).length > 0 && (
                  <details>
                    <summary>思考摘要</summary>
                    <ul className="compact-list">
                      {(md.thoughts || []).slice(-8).map((x, i) => (
                        <li key={`${msg.message_id}-thought-${i}`}>{x}</li>
                      ))}
                    </ul>
                  </details>
                )}
                {(md.citations || []).length > 0 && (
                  <details>
                    <summary>引用证据</summary>
                    <div className="citation-grid">
                      {(md.citations || []).slice(0, 8).map((c, i) => (
                        <div key={`${msg.message_id}-cit-${i}`} className="citation-card">
                          <strong>{c.source || "unknown"}</strong>
                          <MarkdownBlock text={c.content || ""} />
                        </div>
                      ))}
                    </div>
                  </details>
                )}
                {md.graph_result && (md.graph_result.neighbors.length > 0 || md.graph_result.paths.length > 0) && (
                  <details>
                    <summary>图谱关系</summary>
                    <div className="graph-result-panel">
                      {md.graph_result.neighbors.length > 0 && (
                        <div className="graph-section">
                          <strong>邻居关系 ({md.graph_result.neighbors.length})</strong>
                          <ul className="compact-list">
                            {md.graph_result.neighbors.slice(0, 10).map((n, i) => (
                              <li key={`${msg.message_id}-neighbor-${i}`}>
                                {n.entity} -[{n.relation}]- {n.direction === "out" ? "→" : "←"}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {md.graph_result.paths.length > 0 && (
                        <div className="graph-section">
                          <strong>推理路径 ({md.graph_result.paths.length})</strong>
                          <ul className="compact-list">
                            {md.graph_result.paths.slice(0, 5).map((p, i) => (
                              <li key={`${msg.message_id}-path-${i}`}>
                                {p.entities.map((e, j) => (
                                  <span key={j}>
                                    {e}
                                    {j < p.relations.length && ` -[${p.relations[j]}]→ `}
                                  </span>
                                ))}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {md.graph_result.context && (
                        <div className="graph-section">
                          <strong>图谱上下文</strong>
                          <pre className="graph-context">{md.graph_result.context}</pre>
                        </div>
                      )}
                    </div>
                  </details>
                )}
              </>
            )}
          </article>
        );
      })}
    </section>
  );
}
