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
      {messages.length === 0 && <div className="muted">还没有消息，先从一个问题开始。</div>}
      {messages.map((msg) => {
        const isAssistant = msg.role === "assistant";
        const md = msg.metadata || EMPTY_METADATA;

        return (
          <article key={msg.message_id} className={`bubble ${isAssistant ? "assistant" : "user"}`}>
            <div className="message-head">
              <span>{isAssistant ? "助手" : "用户"}</span>
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
                    <summary>查看执行过程</summary>
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
                    <summary>查看思考过程</summary>
                    <ul className="compact-list">
                      {(md.thoughts || []).slice(-8).map((x, i) => (
                        <li key={`${msg.message_id}-thought-${i}`}>{x}</li>
                      ))}
                    </ul>
                  </details>
                )}
                {(md.citations || []).length > 0 && (
                  <details>
                    <summary>查看引用</summary>
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
              </>
            )}
          </article>
        );
      })}
    </section>
  );
}
