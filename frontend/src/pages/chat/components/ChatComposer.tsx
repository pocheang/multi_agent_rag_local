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
  onQuestionChange: (value: string) => void;
  onAsk: () => Promise<void>;
  onClearQuestion: () => void;
  onPromptPick: (prompt: string) => void;
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
  onQuestionChange,
  onAsk,
  onClearQuestion,
  onPromptPick,
  onComposerDragEnter,
  onComposerDragOver,
  onComposerDragLeave,
  onComposerDrop,
  onChatUploadChange,
}: Props) {
  return (
    <section
      className={`panel composer-panel ${composerDropActive ? "dragover" : ""}`}
      onDragEnter={onComposerDragEnter}
      onDragOver={onComposerDragOver}
      onDragLeave={onComposerDragLeave}
      onDrop={(evt) => void onComposerDrop(evt)}
    >
      <textarea
        ref={questionRef}
        value={question}
        onChange={(e) => onQuestionChange(e.target.value)}
        placeholder="输入安全问题，例如：如何检测疑似横向移动？Ctrl/⌘ + Enter 发送"
        rows={3}
        onKeyDown={(e) => {
          if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            e.preventDefault();
            void onAsk();
          }
        }}
      />
      <div className="row-actions">
        <button type="button" onClick={() => void onAsk()} disabled={isSending}>
          {isSending ? "分析中..." : "分析"}
        </button>
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
      <div className="row-actions wrap">
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
