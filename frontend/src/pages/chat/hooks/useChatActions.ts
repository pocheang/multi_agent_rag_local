import type { Dispatch, SetStateAction } from "react";
import { useTranslation } from "react-i18next";
import { createApiErrorHandler } from "@/lib/api-error-handler";
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
  confirm: (opts: { message: string; title?: string; isDanger?: boolean }) => Promise<boolean>;
  promptInput: (opts: { message: string; title?: string; defaultValue?: string; multiline?: boolean }) => Promise<string | null>;
}

export function useChatActions(params: UseChatActionsParams) {
  const { t } = useTranslation();
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
    confirm,
    promptInput,
  } = params;

  const notify = (text: string, kind: Toast["kind"] = "info", ttl = 2400) => {
    const id = crypto.randomUUID();
    setToasts((prev) => [...prev, { id, text, kind }]);
    window.setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), ttl);
  };

  const handleApiError = createApiErrorHandler({
    onLogout,
    onError: (msg) => {
      setError(msg);
      notify(msg, "error");
    },
    sessionExpiredMessage: t("common.sessionExpired"),
  });

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
    confirm,
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
    confirm,
  });

  // Message operations
  const messageOperations = useMessageOperations({
    currentSessionId,
    setMessages,
    notify,
    handleApiError,
    refreshSessions: sessionActions.refreshSessions,
    promptInput,
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
