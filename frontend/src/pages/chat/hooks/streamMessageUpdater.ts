import { flushSync } from "react-dom";
import type { SessionMessage } from "@/types/api";
import type { StreamMetadata } from "./streamEventHandlers";

export interface StreamMessageUpdaterOptions {
  setMessages: React.Dispatch<React.SetStateAction<SessionMessage[]>>;
}

export function createStreamMessageUpdater({ setMessages }: StreamMessageUpdaterOptions) {
  return {
    patchStreamMessage: (content: string, meta: StreamMetadata) => {
      // Use flushSync to ensure immediate rendering of each chunk
      flushSync(() => {
        setMessages((prev) =>
          prev.map((m) =>
            m.message_id === "local-assistant-stream"
              ? { ...m, content, metadata: { ...meta, thoughts: meta.thoughts?.slice(-8) } }
              : m
          )
        );
      });
    },

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

    updateFinalMessage: (sessionMessages: SessionMessage[], finalMeta: StreamMetadata) => {
      const nextMessages = [...sessionMessages];
      for (let i = nextMessages.length - 1; i >= 0; i -= 1) {
        if (nextMessages[i]?.role !== "assistant") continue;
        nextMessages[i] = {
          ...nextMessages[i],
          metadata: {
            ...(nextMessages[i].metadata || {}),
            ...finalMeta,
          },
        };
        break;
      }
      setMessages(nextMessages);
    },
  };
}
