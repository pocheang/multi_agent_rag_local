import type React from "react";
import { useTranslation } from "react-i18next";
import { QuickActions } from "@/pages/chat/components/QuickActions";
import { AnimatedButtonLite as AnimatedButton } from "@/components/animations/AnimatedButtonLite";
import { useChatStore } from "@/stores/useChatStore";
import { useTextareaAutoResize } from "@/pages/chat/hooks/useTextareaAutoResize";

type Props = {
  questionRef: React.MutableRefObject<HTMLTextAreaElement | null>;
  chatUploadInputRef: React.MutableRefObject<HTMLInputElement | null>;
  isSending: boolean;
  quickPrompts: string[];
  onAsk: () => Promise<void>;
  onStop: () => void;
  onComposerDragEnter: (evt: React.DragEvent<HTMLElement>) => void;
  onComposerDragOver: (evt: React.DragEvent<HTMLElement>) => void;
  onComposerDragLeave: (evt: React.DragEvent<HTMLElement>) => void;
  onComposerDrop: (evt: React.DragEvent<HTMLElement>) => Promise<void>;
  onChatUploadChange: (evt: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
};

export function ChatComposer({
  questionRef,
  chatUploadInputRef,
  isSending,
  quickPrompts,
  onAsk,
  onStop,
  onComposerDragEnter,
  onComposerDragOver,
  onComposerDragLeave,
  onComposerDrop,
  onChatUploadChange,
}: Props) {
  const { t } = useTranslation();
  const question = useChatStore((s) => s.question);
  const setQuestion = useChatStore((s) => s.setQuestion);
  const runStatus = useChatStore((s) => s.runStatus);
  const composerDropActive = useChatStore((s) => s.composerDropActive);
  useTextareaAutoResize({ ref: questionRef, value: question });
  const modeHint = t("components.chat.modeHint.advancedReasoning");

  return (
    <section
      className={`panel composer-panel ${composerDropActive ? "dragover" : ""}`}
      onDragEnter={onComposerDragEnter}
      onDragOver={onComposerDragOver}
      onDragLeave={onComposerDragLeave}
      onDrop={(event) => void onComposerDrop(event)}
    >
      <div className="composer-main">
        <div className="composer-heading-row">
          <label className="composer-label">{t("components.chat.composerLabel")}</label>
          <span className="composer-drop-hint">{t("components.chat.composerDropHint")}</span>
        </div>

        <div className="composer-input-wrapper">
          <textarea
            ref={questionRef}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={t("components.chat.composerPlaceholder")}
            rows={3}
            aria-label={t("components.chat.questionInput")}
            aria-describedby="composer-hint"
            onKeyDown={(event) => {
              if (event.key === "Escape" && isSending) {
                event.preventDefault();
                onStop();
                return;
              }
              if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                event.preventDefault();
                void onAsk();
              }
            }}
          />
          <div className="composer-input-actions">
            <label className="composer-upload-btn" title={t("components.chat.uploadFiles")}>
              <span aria-hidden="true">+</span>
              <input
                ref={chatUploadInputRef}
                type="file"
                multiple
                accept=".pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp"
                style={{ display: "none" }}
                onChange={(event) => void onChatUploadChange(event)}
                aria-label={t("components.chat.uploadFilesAria")}
              />
            </label>
          </div>
        </div>
      </div>

      <div className="composer-controls">
        <AnimatedButton
          onClick={onAsk}
          state={isSending ? 'loading' : 'idle'}
          variant="primary"
          size="large"
          disabled={isSending}
          className="composer-primary-btn"
        >
          <span className="btn-text">{isSending ? t("components.chat.analyzing") : t("components.chat.startAnalysis")}</span>
          {!isSending && <span className="btn-shortcut">Ctrl / Cmd + Enter</span>}
        </AnimatedButton>
      </div>

      <div className="composer-hint" id="composer-hint">
        {modeHint}
      </div>

      <QuickActions
        quickPrompts={quickPrompts}
        question={question}
        isSending={isSending}
        onPromptPick={setQuestion}
        onStop={onStop}
        onClearQuestion={() => setQuestion("")}
      />

      {runStatus && <div className="status">{runStatus}</div>}
    </section>
  );
}
