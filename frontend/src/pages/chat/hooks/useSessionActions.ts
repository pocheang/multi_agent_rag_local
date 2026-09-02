import type { Dispatch, SetStateAction } from "react";
import { useTranslation } from "react-i18next";
import { appApi } from "@/lib/api";
import type { SessionMessage, SessionSummary } from "@/types/api";
import type { Toast } from "@/pages/chat/types";

interface UseSessionActionsParams {
  setToasts: Dispatch<SetStateAction<Toast[]>>;
  setError: Dispatch<SetStateAction<string>>;
  setSessions: Dispatch<SetStateAction<SessionSummary[]>>;
  setSessionLoading: Dispatch<SetStateAction<boolean>>;
  setCurrentSessionId: Dispatch<SetStateAction<string | null>>;
  setMessages: Dispatch<SetStateAction<SessionMessage[]>>;
  setBusySessionId: Dispatch<SetStateAction<string | null>>;
  setIsCreatingSession?: Dispatch<SetStateAction<boolean>>;
  currentSessionId: string | null;
  sessions: SessionSummary[];
  messages: SessionMessage[];
  onLogout: () => Promise<void>;
  closeSidebar: () => void;
  notify: (text: string, kind?: Toast["kind"], ttl?: number) => void;
  handleApiError: (e: unknown, fallback: string) => Promise<void>;
}

export function useSessionActions(params: UseSessionActionsParams) {
  const { t } = useTranslation();
  const {
    setError,
    setSessions,
    setSessionLoading,
    setCurrentSessionId,
    setMessages,
    setBusySessionId,
    setIsCreatingSession,
    currentSessionId,
    sessions,
    messages,
    closeSidebar,
    notify,
    handleApiError,
  } = params;

  const loadSession = async (sessionId: string) => {
    setBusySessionId(sessionId);
    try {
      const detail = await appApi.sessionDetail(sessionId);
      setCurrentSessionId(detail.session_id);
      setMessages(detail.messages || []);
      setError("");
      closeSidebar();
    } catch (e) {
      await handleApiError(e, "Failed to load session");
    } finally {
      setBusySessionId(null);
    }
  };

  const refreshSessions = async (preferSelectFirst = false, silent = false) => {
    if (!silent) setSessionLoading(true);
    try {
      const rows = await appApi.sessions();
      setSessions(rows);
      setError("");
      if (preferSelectFirst && rows.length > 0) await loadSession(rows[0].session_id);
      return rows;
    } catch (e) {
      await handleApiError(e, "Failed to refresh sessions");
      return [] as SessionSummary[];
    } finally {
      if (!silent) setSessionLoading(false);
    }
  };

  const createSession = async (signal?: AbortSignal) => {
    // Check if current chat is empty (no user messages)
    const hasUserMessages = messages.some((msg) => msg.role === "user");

    // If current chat is empty, don't create a new session - reuse current chat
    if (!hasUserMessages && currentSessionId) {
      notify(t("components.chat.emptyChatNotice"), "info");
      closeSidebar();
      return currentSessionId;
    }

    // Prevent duplicate creation
    if (setIsCreatingSession) setIsCreatingSession(true);

    try {
      const detail = await appApi.sessionCreate(signal);
      if (signal?.aborted) return null;
      setCurrentSessionId(detail.session_id);
      setMessages(detail.messages || []);
      if (!signal) {
        await refreshSessions();
        notify(t("components.chat.sessionCreated"), "success");
      }
      closeSidebar();
      return detail.session_id;
    } catch (e) {
      if (signal?.aborted || (e instanceof DOMException && e.name === "AbortError")) return null;
      await handleApiError(e, "Failed to create session");
      return null;
    } finally {
      if (setIsCreatingSession) setIsCreatingSession(false);
    }
  };

  const deleteSession = async (sessionId: string) => {
    try {
      const deletedIndex = sessions.findIndex((session) => session.session_id === sessionId);
      await appApi.sessionDelete(sessionId);

      // If deleting current session, intelligently select next one
      if (sessionId === currentSessionId) {
        const updatedSessions = await refreshSessions();

        if (updatedSessions.length > 0) {
          // Keep the user's position in the list when possible.
          const nextIndex = Math.min(Math.max(0, deletedIndex), updatedSessions.length - 1);
          const nextSession = updatedSessions[nextIndex];
          await loadSession(nextSession.session_id);
        } else {
          // No sessions left, clear the interface
          setCurrentSessionId(null);
          setMessages([]);
        }
      } else {
        await refreshSessions();
      }

      notify(t("components.chat.sessionDeleted"), "success");
    } catch (e) {
      await handleApiError(e, "Failed to delete session");
    }
  };

  const renameSession = async (sessionId: string, newTitle: string) => {
    try {
      await appApi.sessionRename(sessionId, newTitle);
      await refreshSessions();
      notify(t("components.chat.sessionRenamed"), "success");
    } catch (e) {
      await handleApiError(e, "Failed to rename session");
      throw e; // Re-throw to let UI handle it
    }
  };

  const pinSession = async (sessionId: string, pinned: boolean) => {
    try {
      await appApi.sessionPin(sessionId, pinned);
      await refreshSessions();
      notify(pinned ? t("components.chat.sessionPinned") : t("components.chat.sessionUnpinned"), "success");
    } catch (e) {
      await handleApiError(e, "Failed to pin session");
      throw e; // Re-throw to let UI handle it
    }
  };

  return {
    loadSession,
    refreshSessions,
    createSession,
    deleteSession,
    renameSession,
    pinSession,
  };
}
