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

export function ChatMessages({ messages, containerRef, onEditMessage, onRemoveMessage }: Props) {
  return (
    <section className="chat-window panel" ref={containerRef}>
      {messages.length === 0 && <div className="muted">还没有消息，输入一个问题开始分析。</div>}
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
                  {md.agent_class && <span className="chip">agent: {md.agent_class}</span>}
                  <span className="chip">web: {md.web_used ? "yes" : "no"}</span>
                  {(md.graph_entities || []).slice(0, 6).map((x) => (
                    <span key={x} className="chip">
                      {x}
                    </span>
                  ))}
                </div>
                {(md.thoughts || []).length > 0 && (
                  <details>
                    <summary>查看过程</summary>
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
