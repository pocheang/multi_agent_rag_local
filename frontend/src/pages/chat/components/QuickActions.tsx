import { useTranslation } from "react-i18next";
import { AnimatedButtonLite as AnimatedButton } from "@/components/animations/AnimatedButtonLite";

type Props = {
  quickPrompts: string[];
  question: string;
  isSending: boolean;
  onPromptPick: (prompt: string) => void;
  onStop: () => void;
  onClearQuestion: () => void;
};

export function QuickActions({
  quickPrompts,
  question,
  isSending,
  onPromptPick,
  onStop,
  onClearQuestion,
}: Props) {
  const { t } = useTranslation();

  return (
    <div className="quick-actions">
      {quickPrompts.map((prompt) => (
        <AnimatedButton
          key={prompt}
          onClick={() => onPromptPick(prompt)}
          variant="ghost"
          size="small"
          className="quick-action-btn"
        >
          {prompt}
        </AnimatedButton>
      ))}
      {isSending && (
        <AnimatedButton
          onClick={onStop}
          variant="danger"
          size="small"
          className="quick-action-btn"
        >
          {t("components.chat.stop")}
        </AnimatedButton>
      )}
      {question && !isSending && (
        <AnimatedButton
          onClick={onClearQuestion}
          variant="secondary"
          size="small"
          className="quick-action-btn"
        >
          {t("components.chat.clear")}
        </AnimatedButton>
      )}
    </div>
  );
}
