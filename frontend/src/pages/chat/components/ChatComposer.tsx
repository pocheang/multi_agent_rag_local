import type React from "react";
import { useTranslation } from "react-i18next";
import { QuickActions } from "@/pages/chat/components/QuickActions";
import { SelectControl } from "@/pages/chat/components/SelectControl";
import { ToggleControl } from "@/pages/chat/components/ToggleControl";
import {
  profileCapabilities,
  profileModeHint,
} from "@/pages/chat/components/profileCapabilities";
import type { PipelineProfile } from "@/types/api";
import { AnimatedButtonLite as AnimatedButton } from "@/components/animations/AnimatedButtonLite";

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
  pipelineProfile: PipelineProfile;
  onQuestionChange: (value: string) => void;
  onAsk: () => Promise<void>;
  onStop: () => void;
  onClearQuestion: () => void;
  onPromptPick: (prompt: string) => void;
  onUseWebChange: (next: boolean) => void;
  onUseReasoningChange: (next: boolean) => void;
  onAgentClassHintChange: (value: string) => void;
  onRetrievalStrategyChange: (value: string) => void;
  onPipelineProfileChange: (value: string) => void;
  onComposerDragEnter: (evt: React.DragEvent<HTMLElement>) => void;
  onComposerDragOver: (evt: React.DragEvent<HTMLElement>) => void;
  onComposerDragLeave: (evt: React.DragEvent<HTMLElement>) => void;
  onComposerDrop: (evt: React.DragEvent<HTMLElement>) => Promise<void>;
  onChatUploadChange: (evt: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
};

const RETRIEVAL_OPTIONS = [
  { value: "advanced", label: "advanced" },
  { value: "baseline", label: "baseline" },
  { value: "safe", label: "safe" },
];

const AGENT_OPTIONS = [
  { value: "", label: "auto" },
  { value: "cybersecurity", label: "cybersecurity" },
  { value: "artificial_intelligence", label: "artificial_intelligence" },
  { value: "pdf_text", label: "pdf_text" },
  { value: "general", label: "general" },
];

const PROFILE_OPTIONS = [
  { value: "standard", label: "standard" },
  { value: "strict_quality", label: "strict_quality" },
  { value: "advanced", label: "advanced" },
];

export function ChatComposer({
  composerDropActive,
  question,
  questionRef,
  chatUploadInputRef,
  isSending,
  quickPrompts,
  runStatus,
  // error, // Now shown via Toast instead of inline
  useWeb,
  useReasoning,
  agentClassHint,
  retrievalStrategy,
  pipelineProfile,
  onQuestionChange,
  onAsk,
  onStop,
  onClearQuestion,
  onPromptPick,
  onUseWebChange,
  onUseReasoningChange,
  onAgentClassHintChange,
  onRetrievalStrategyChange,
  onPipelineProfileChange,
  onComposerDragEnter,
  onComposerDragOver,
  onComposerDragLeave,
  onComposerDrop,
  onChatUploadChange,
}: Props) {
  const { t } = useTranslation();
  const strategy = t(`components.chat.strategy.${retrievalStrategy || "advanced"}`);
  const capabilities = profileCapabilities(pipelineProfile);
  const modeHint = t(
    `components.chat.modeHint.${profileModeHint(pipelineProfile, { useWeb, useReasoning })}`,
    { strategy },
  );

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
            onChange={(event) => onQuestionChange(event.target.value)}
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
        <div className="composer-options">
          {capabilities.web && (
            <ToggleControl
              label={t("components.chat.webSearch")}
              active={useWeb}
              onChange={onUseWebChange}
              ariaLabel={t("components.chat.webSearchAria")}
              title={t("components.chat.webSearchTitle")}
            />
          )}
          {capabilities.reasoning && (
            <ToggleControl
              label={t("components.chat.reasoning")}
              active={useReasoning}
              onChange={onUseReasoningChange}
              ariaLabel={t("components.chat.reasoningAria")}
              title={t("components.chat.reasoningTitle")}
            />
          )}
          {capabilities.retrieval && (
            <SelectControl
              label={t("components.chat.retrievalStrategy")}
              value={retrievalStrategy}
              options={RETRIEVAL_OPTIONS}
              onChange={onRetrievalStrategyChange}
              ariaLabel={t("components.chat.retrievalStrategyAria")}
            />
          )}
          <SelectControl
            label={t("components.chat.profile")}
            value={pipelineProfile}
            options={PROFILE_OPTIONS.map((option) => ({ ...option, label: t(`components.chat.profileOptions.${option.value}`) }))}
            onChange={onPipelineProfileChange}
            ariaLabel={t("components.chat.profileAria")}
          />
          {capabilities.agent && (
            <SelectControl
              label="Agent"
              value={agentClassHint}
              options={AGENT_OPTIONS}
              onChange={onAgentClassHintChange}
              ariaLabel={t("components.chat.agentTypeAria")}
            />
          )}
        </div>

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
        onPromptPick={onPromptPick}
        onStop={onStop}
        onClearQuestion={onClearQuestion}
      />

      {runStatus && <div className="status">{runStatus}</div>}
      {/* Error now shown via Toast in top-right corner */}
    </section>
  );
}
