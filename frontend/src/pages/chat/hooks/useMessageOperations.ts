import type { Dispatch, SetStateAction } from "react";
import { useTranslation } from "react-i18next";
import { appApi } from "@/lib/api";
import type { SessionMessage, SessionSummary } from "@/types/api";
import type { Toast } from "@/pages/chat/types";

interface UseMessageOperationsParams {
  currentSessionId: string | null;
  setMessages: Dispatch<SetStateAction<SessionMessage[]>>;
  notify: (text: string, kind?: Toast["kind"], ttl?: number) => void;
  handleApiError: (e: unknown, fallback: string) => Promise<void>;
  refreshSessions: (preferSelectFirst?: boolean, silent?: boolean) => Promise<SessionSummary[]>;
  promptInput: (opts: { message: string; title?: string; defaultValue?: string; multiline?: boolean }) => Promise<string | null>;
}

export function useMessageOperations(params: UseMessageOperationsParams) {
  const { t } = useTranslation();
  const {
    currentSessionId,
    setMessages,
    notify,
    handleApiError,
    refreshSessions,
    promptInput,
  } = params;

  const editMessage = async (msg: SessionMessage) => {
    if (!currentSessionId || !msg.message_id) return;
    const next = await promptInput({
      title: t("components.messages.edit"),
      message: t("components.messages.editPromptTitle"),
      defaultValue: msg.content || "",
      multiline: true,
    });
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
      notify(t("components.messages.updateSuccess"), "success");
    } catch (e) {
      await handleApiError(e, t("components.messages.updateFailed"));
    }
  };

  const removeMessage = async (msg: SessionMessage) => {
    if (!currentSessionId || !msg.message_id) return;
    try {
      const detail = await appApi.messageDelete(currentSessionId, msg.message_id);
      setMessages(detail.messages || []);
      await refreshSessions();
      notify(t("components.messages.deleteSuccess"), "success");
    } catch (e) {
      await handleApiError(e, t("components.messages.deleteFailed"));
    }
  };

  return {
    editMessage,
    removeMessage,
  };
}
