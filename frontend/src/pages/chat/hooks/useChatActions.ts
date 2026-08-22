import type { Dispatch, SetStateAction } from "react";
import { ApiError } from "@/lib/api";
import type { IndexedFileSummary, PromptTemplate, SessionMessage, SessionSummary } from "@/types/api";
import type { Toast } from "@/pages/chat/types";
import { useSessionActions } from "./useSessionActions";
import { useDocumentActions } from "./useDocumentActions";
import { usePromptActions } from "./usePromptActions";
import { useMessageOperations } from "./useMessageOperations";

type AgentClassHint = "" | "general" | "cybersecurity" | "artificial_intelligence" | "pdf_text";

interface UseChatActionsParams {
  setToasts: Dispatch<SetStateAction<Toast[]>>;
  setError: Dispatch<SetStateAction<string>>;
  setSessions: Dispatch<SetStateAction<SessionSummary[]>>;
  setSessionLoading: Dispatch<SetStateAction<boolean>>;
  setCurrentSessionId: Dispatch<SetStateAction<string | null>>;
  setMessages: Dispatch<SetStateAction<SessionMessage[]>>;
  setBusySessionId: Dispatch<SetStateAction<string | null>>;
  setIsCreatingSession: Dispatch<SetStateAction<boolean>>;
  setDocuments: Dispatch<SetStateAction<IndexedFileSummary[]>>;
  setDocsLoading: Dispatch<SetStateAction<boolean>>;
  setUploading: Dispatch<SetStateAction<boolean>>;
  setUploadInfo: Dispatch<SetStateAction<string>>;
  setUploadProgress: Dispatch<SetStateAction<number>>;
  setUploadProgressText: Dispatch<SetStateAction<string>>;
  setAgentClassHint: Dispatch<SetStateAction<AgentClassHint>>;
  setPrompts: Dispatch<SetStateAction<PromptTemplate[]>>;
  setPromptsLoading: Dispatch<SetStateAction<boolean>>;
  setEditingPromptId: Dispatch<SetStateAction<string | null>>;
  setPromptTitle: Dispatch<SetStateAction<string>>;
  setPromptContent: Dispatch<SetStateAction<string>>;
  setPromptCheckInfo: Dispatch<SetStateAction<string>>;
  currentSessionId: string | null;
  sessions: SessionSummary[];
  messages: SessionMessage[];
  uploadVisibility: "private" | "public";
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  chatUploadInputRef: React.RefObject<HTMLInputElement | null>;
  onLogout: () => Promise<void>;
  closeSidebar: () => void;
}

export function useChatActions(params: UseChatActionsParams) {
  const {
    setToasts,
    setError,
    setSessions,
    setSessionLoading,
    setCurrentSessionId,
    setMessages,
    setBusySessionId,
    setIsCreatingSession,
    setDocuments,
    setDocsLoading,
    setUploading,
    setUploadInfo,
    setUploadProgress,
    setUploadProgressText,
    setAgentClassHint,
    setPrompts,
    setPromptsLoading,
    setEditingPromptId,
    setPromptTitle,
    setPromptContent,
    setPromptCheckInfo,
    currentSessionId,
    sessions,
    messages,
    uploadVisibility,
    fileInputRef,
    chatUploadInputRef,
    onLogout,
    closeSidebar,
  } = params;

  const notify = (text: string, kind: Toast["kind"] = "info", ttl = 2400) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setToasts((prev) => [...prev, { id, text, kind }]);
    window.setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), ttl);
  };

  const handleApiError = async (e: unknown, fallback: string) => {
    if (e instanceof ApiError && e.status === 401) {
      notify("Session expired. Please log in again.", "error");
      await onLogout();
      return;
    }
    const msg = e instanceof Error ? e.message : fallback;
    setError(msg);
    notify(msg, "error");
  };

  // Session management actions
  const sessionActions = useSessionActions({
    setToasts,
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
    onLogout,
    closeSidebar,
    notify,
    handleApiError,
  });

  // Document management actions
  const documentActions = useDocumentActions({
    setDocuments,
    setDocsLoading,
    setUploading,
    setUploadInfo,
    setUploadProgress,
    setUploadProgressText,
    setAgentClassHint,
    setError,
    uploadVisibility,
    fileInputRef,
    chatUploadInputRef,
    notify,
    handleApiError,
  });

  // Prompt management actions
  const promptActions = usePromptActions({
    setPrompts,
    setPromptsLoading,
    setEditingPromptId,
    setPromptTitle,
    setPromptContent,
    setPromptCheckInfo,
    setAgentClassHint,
    setError,
    notify,
    handleApiError,
  });

  // Message operations
  const messageOperations = useMessageOperations({
    currentSessionId,
    setMessages,
    notify,
    handleApiError,
    refreshSessions: sessionActions.refreshSessions,
  });

  return {
    notify,
    handleApiError,
    ...sessionActions,
    ...documentActions,
    ...promptActions,
    ...messageOperations,
  };
}
