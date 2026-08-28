import type { Dispatch, SetStateAction } from "react";
import { appApi } from "@/lib/api";
import type { SessionMessage, SessionSummary } from "@/types/api";
import type { Toast } from "@/pages/chat/types";

interface UseMessageOperationsParams {
  currentSessionId: string | null;
  setMessages: Dispatch<SetStateAction<SessionMessage[]>>;
  notify: (text: string, kind?: Toast["kind"], ttl?: number) => void;
  handleApiError: (e: unknown, fallback: string) => Promise<void>;
  refreshSessions: (preferSelectFirst?: boolean, silent?: boolean) => Promise<SessionSummary[]>;
}

export function useMessageOperations(params: UseMessageOperationsParams) {
  const {
    currentSessionId,
    setMessages,
    notify,
    handleApiError,
    refreshSessions,
  } = params;

  const editMessage = async (msg: SessionMessage) => {
    if (!currentSessionId || !msg.message_id) return;
    const next = window.prompt("Edit message content", msg.content || "");
    if (next === null) return;
    try {
      const rerun = msg.role === "user";
      const detail = await appApi.messageUpdate(
        currentSessionId,
        msg.message_id,
        next,
        rerun,
      );
      setMessages(detail.messages || []);
      await refreshSessions();
      notify("Message updated", "success");
    } catch (e) {
      await handleApiError(e, "Failed to update message");
    }
  };

  const removeMessage = async (msg: SessionMessage) => {
    if (!currentSessionId || !msg.message_id) return;
    try {
      const detail = await appApi.messageDelete(currentSessionId, msg.message_id);
      setMessages(detail.messages || []);
      await refreshSessions();
      notify("Message deleted", "success");
    } catch (e) {
      await handleApiError(e, "Failed to delete message");
    }
  };

  return {
    editMessage,
    removeMessage,
  };
}
