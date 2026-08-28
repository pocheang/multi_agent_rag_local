import type { SessionMessage } from "@/types/api";

export interface StreamMessageUpdaterOptions {
  setMessages: React.Dispatch<React.SetStateAction<SessionMessage[]>>;
}

export function createStreamMessageUpdater({ setMessages }: StreamMessageUpdaterOptions) {
  return {
    replaceWithStoppedMessage: (content: string) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.message_id === "local-assistant-stream"
            ? { ...m, content: content.trim() || "[Stopped by user]" }
            : m
        )
      );
    },

    replaceWithErrorMessage: (errorText: string) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.message_id === "local-assistant-stream" ? { ...m, content: errorText } : m
        )
      );
    },
  };
}
