import type { Dispatch, SetStateAction } from "react";
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
  currentSessionId: string | null;
  onLogout: () => Promise<void>;
  closeSidebar: () => void;
  notify: (text: string, kind?: Toast["kind"], ttl?: number) => void;
  handleApiError: (e: unknown, fallback: string) => Promise<void>;
}

export function useSessionActions(params: UseSessionActionsParams) {
  const {
    setError,
    setSessions,
    setSessionLoading,
    setCurrentSessionId,
    setMessages,
    setBusySessionId,
    currentSessionId,
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
    try {
      const detail = await appApi.sessionCreate(signal);
      if (signal?.aborted) return null;
      setCurrentSessionId(detail.session_id);
      setMessages(detail.messages || []);
      if (!signal) {
        await refreshSessions();
        notify("Session created", "success");
      }
      closeSidebar();
      return detail.session_id;
    } catch (e) {
      if (signal?.aborted || (e instanceof DOMException && e.name === "AbortError")) return null;
      await handleApiError(e, "Failed to create session");
      return null;
    }
  };

  const deleteSession = async (sessionId: string) => {
    if (!window.confirm("Delete this session?")) return;
    try {
      await appApi.sessionDelete(sessionId);
      if (sessionId === currentSessionId) {
        setCurrentSessionId(null);
        setMessages([]);
      }
      await refreshSessions();
      notify("Session deleted", "success");
    } catch (e) {
      await handleApiError(e, "Failed to delete session");
    }
  };

  return {
    loadSession,
    refreshSessions,
    createSession,
    deleteSession,
  };
}
