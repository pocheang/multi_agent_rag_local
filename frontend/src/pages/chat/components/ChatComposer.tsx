import type React from "react";

type Props = {
  composerDropActive: boolean;
  question: string;
  questionRef: React.MutableRefObject<HTMLTextAreaElement | null>;
  chatUploadInputRef: React.MutableRefObject<HTMLInputElement | null>;
  isSending: boolean;
  quickPrompts: string[];
  runStatus: string;
  error: string;
  useWeb: boolean;
  useReasoning: boolean;
  agentClassHint: string;
  retrievalStrategy: string;
  onQuestionChange: (value: string) => void;
  onAsk: () => Promise<void>;
  onStop: () => void;
  onClearQuestion: () => void;
  onPromptPick: (prompt: string) => void;
  onUseWebChange: (next: boolean) => void;
  onUseReasoningChange: (next: boolean) => void;
  onAgentClassHintChange: (value: string) => void;
  onRetrievalStrategyChange: (value: string) => void;
  onComposerDragEnter: (evt: React.DragEvent<HTMLElement>) => void;
  onComposerDragOver: (evt: React.DragEvent<HTMLElement>) => void;
  onComposerDragLeave: (evt: React.DragEvent<HTMLElement>) => void;
  onComposerDrop: (evt: React.DragEvent<HTMLElement>) => Promise<void>;
  onChatUploadChange: (evt: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
};

export function ChatComposer({
  composerDropActive,
  question,
  questionRef,
  chatUploadInputRef,
  isSending,
  quickPrompts,
  runStatus,
  error,
  useWeb,
  useReasoning,
  agentClassHint,
  retrievalStrategy,
  onQuestionChange,
  onAsk,
  onStop,
  onClearQuestion,
  onPromptPick,
  onUseWebChange,
  onUseReasoningChange,
  onAgentClassHintChange,
  onRetrievalStrategyChange,
  onComposerDragEnter,
  onComposerDragOver,
  onComposerDragLeave,
  onComposerDrop,
  onChatUploadChange,
}: Props) {
  const strategyLabel = retrievalStrategy === "baseline"
    ? "基础"
    : retrievalStrategy === "safe"
      ? "安全"
      : "高级";
  const modeHint = !useWeb && !useReasoning
    ? `本地快速模式，${strategyLabel}检索：适合低延迟问答和已入库资料分析。`
    : useWeb
      ? `联网增强已开启，${strategyLabel}检索：适合需要最新资料的问题，响应可能稍慢。`
      : `推理增强已开启，${strategyLabel}检索：适合复杂分析、审计和多步骤归纳。`;

  return (
    <section
      className={`panel composer-panel ${composerDropActive ? "dragover" : ""}`}
      onDragEnter={onComposerDragEnter}
      onDragOver={onComposerDragOver}
      onDragLeave={onComposerDragLeave}
      onDrop={(evt) => void onComposerDrop(evt)}
    >
      <div className="composer-main">
        <label className="composer-label">Ask the RAG system</label>
        <textarea
          ref={questionRef}
          value={question}
          onChange={(e) => onQuestionChange(e.target.value)}
          placeholder="输入问题，例如：总结最新上传 PDF 的安全风险并给出证据来源。Ctrl/Cmd + Enter 发送"
          rows={3}
          onKeyDown={(e) => {
            if (e.key === "Escape" && isSending) {
              e.preventDefault();
              onStop();
              return;
            }
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
              e.preventDefault();
              void onAsk();
            }
          }}
        />
      </div>

      <div className="chat-options-bar" aria-label="chat options">
        <div className="option-group">
          <span className="option-label">联网检索</span>
          <button
            type="button"
            className={`option-chip ${useWeb ? "active" : ""}`}
            onClick={() => onUseWebChange(!useWeb)}
          >
            {useWeb ? "开启" : "关闭"}
          </button>
        </div>
        <div className="option-group">
          <span className="option-label">推理增强</span>
          <button
            type="button"
            className={`option-chip ${useReasoning ? "active" : ""}`}
            onClick={() => onUseReasoningChange(!useReasoning)}
          >
            {useReasoning ? "开启" : "关闭"}
          </button>
        </div>
        <div className="option-group option-agent">
          <span className="option-label">检索策略</span>
          <select value={retrievalStrategy} onChange={(e) => onRetrievalStrategyChange(e.target.value)}>
            <option value="advanced">advanced</option>
            <option value="baseline">baseline</option>
            <option value="safe">safe</option>
          </select>
        </div>
        <div className="option-group option-agent">
          <span className="option-label">Agent</span>
          <select value={agentClassHint} onChange={(e) => onAgentClassHintChange(e.target.value)}>
            <option value="">auto</option>
            <option value="cybersecurity">cybersecurity</option>
            <option value="artificial_intelligence">artificial_intelligence</option>
            <option value="pdf_text">pdf_text</option>
            <option value="general">general</option>
          </select>
        </div>
      </div>
      <div className="option-hint">{modeHint}</div>

      <div className="composer-actions">
        <button type="button" className="primary-action" onClick={() => void onAsk()} disabled={isSending}>
          {isSending ? "处理中..." : "开始分析"}
        </button>
        {isSending && (
          <button type="button" className="danger" onClick={onStop}>
            Stop
          </button>
        )}
        <label className="secondary link-btn">
          上传 PDF/图片
          <input
            ref={chatUploadInputRef}
            type="file"
            multiple
            accept=".pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp"
            style={{ display: "none" }}
            onChange={(evt) => void onChatUploadChange(evt)}
          />
        </label>
        <button type="button" className="secondary" onClick={onClearQuestion}>
          清空
        </button>
      </div>
      <div className="quick-prompt-row">
        {quickPrompts.map((x) => (
          <button key={x} type="button" className="secondary tiny-btn" onClick={() => onPromptPick(x)}>
            {x}
          </button>
        ))}
      </div>
      {runStatus && <div className="status">{runStatus}</div>}
      {error && <div className="status error">{error}</div>}
    </section>
  );
}
