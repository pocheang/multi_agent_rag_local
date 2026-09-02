import { useRef } from "react";
import { useChatStore } from "@/stores/useChatStore";

export function useChatPageState() {
  // Each field below is its own selector so ChatPage only re-renders when
  // that specific field changes. High-churn fields that ChatPage never
  // reads directly (question, runStatus, promptTitle, uploadProgress, ...)
  // are intentionally NOT selected here -- they're owned by the leaf
  // component that renders them (ChatComposer, ChatSidebar). See
  // docs/superpowers/plans/2026-08-29-frontend-audit-followups.md Part 1.
  const sidebarOpen = useChatStore((s) => s.sidebarOpen);
  const sidebarCollapsed = useChatStore((s) => s.sidebarCollapsed);
  const sessions = useChatStore((s) => s.sessions);
  const currentSessionId = useChatStore((s) => s.currentSessionId);
  const messages = useChatStore((s) => s.messages);
  const isSending = useChatStore((s) => s.isSending);
  const pdfTargetFile = useChatStore((s) => s.pdfTargetFile);
  const documents = useChatStore((s) => s.documents);
  const uploadVisibility = useChatStore((s) => s.uploadVisibility);
  const toasts = useChatStore((s) => s.toasts);
  const settingsOpen = useChatStore((s) => s.settingsOpen);

  // Action setters never change identity across renders, so reading them
  // via getState() here does not subscribe ChatPage to the values they
  // write.
  const {
    setSidebarOpen,
    setSidebarCollapsed,
    setSessions,
    setSessionLoading,
    setCurrentSessionId,
    setMessages,
    setBusySessionId,
    setIsCreatingSession,
    setQuestion,
    setIsSending,
    setRunStatus,
    setAgentClassHint,
    setPdfTargetFile,
    setDocuments,
    setDocsLoading,
    setUploading,
    setUploadInfo,
    setUploadProgress,
    setUploadProgressText,
    setUploadVisibility,
    setDocDropActive,
    setComposerDropActive,
    setPrompts,
    setPromptsLoading,
    setPromptTitle,
    setPromptContent,
    setEditingPromptId,
    setPromptCheckInfo,
    setToasts,
    setError,
    setSettingsOpen,
  } = useChatStore.getState();

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatUploadInputRef = useRef<HTMLInputElement | null>(null);
  const questionRef = useRef<HTMLTextAreaElement | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);

  return {
    sidebarOpen, setSidebarOpen,
    sidebarCollapsed, setSidebarCollapsed,
    sessions, setSessions,
    setSessionLoading,
    currentSessionId, setCurrentSessionId,
    messages, setMessages,
    setBusySessionId,
    setIsCreatingSession,
    setQuestion,
    isSending, setIsSending,
    setRunStatus,
    setAgentClassHint,
    pdfTargetFile, setPdfTargetFile,
    documents, setDocuments,
    setDocsLoading,
    setUploading,
    setUploadInfo,
    setUploadProgress,
    setUploadProgressText,
    uploadVisibility, setUploadVisibility,
    setDocDropActive,
    setComposerDropActive,
    setPrompts,
    setPromptsLoading,
    setPromptTitle,
    setPromptContent,
    setEditingPromptId,
    setPromptCheckInfo,
    toasts, setToasts,
    setError,
    settingsOpen, setSettingsOpen,
    fileInputRef,
    chatUploadInputRef,
    questionRef,
    chatScrollRef,
  };
}
