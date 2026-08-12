import type React from "react";
import { useTranslation } from "react-i18next";
import type { SessionMessage } from "@/types/api";
import { MessageCard } from "@/pages/chat/components/MessageCard";
import { WelcomeScreen } from "@/pages/chat/components/WelcomeScreen";

type Props = {
  messages: SessionMessage[];
  containerRef: React.MutableRefObject<HTMLDivElement | null>;
  documentsCount?: number;
  sessionsCount?: number;
  onEditMessage: (msg: SessionMessage) => Promise<void>;
  onRemoveMessage: (msg: SessionMessage) => Promise<void>;
  onCreateSession?: () => void;
  onNavigateToArchitecture?: () => void;
};

export function ChatMessages({
  messages,
  containerRef,
  documentsCount,
  sessionsCount,
  onEditMessage,
  onRemoveMessage,
  onCreateSession,
  onNavigateToArchitecture
}: Props) {
  const { t } = useTranslation();

  return (
    <section className="chat-window" ref={containerRef} role="log" aria-live="polite" aria-label={t("components.messages.logLabel")}>
      {messages.length === 0 && (
        <WelcomeScreen
          documentsCount={documentsCount}
          sessionsCount={sessionsCount}
          onCreateSession={onCreateSession}
          onNavigateToArchitecture={onNavigateToArchitecture}
        />
      )}
      {messages.map((message, index) => (
        <MessageCard
          key={message.message_id ?? `${message.role}-${message.created_at ?? "undated"}-${index}`}
          message={message}
          onEditMessage={onEditMessage}
          onRemoveMessage={onRemoveMessage}
        />
      ))}
    </section>
  );
}
