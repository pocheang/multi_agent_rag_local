import { useState, useRef } from "react";
import type { IndexedFileSummary, PromptTemplate, SessionMessage, SessionSummary } from "@/types/api";
import type { PipelineProfile } from "@/types/api";
import type { Toast } from "@/pages/chat/types";
import type { AgentClassHint, RetrievalStrategy } from "@/pages/chat/constants";

export function useChatPageState() {
  // Session state
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [busySessionId, setBusySessionId] = useState<string | null>(null);

  // Chat state
  const [question, setQuestion] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [runStatus, setRunStatus] = useState("");
  const [useWeb, setUseWeb] = useState(false);
  const [useReasoning, setUseReasoning] = useState(false);
  const [agentClassHint, setAgentClassHint] = useState<AgentClassHint>("");
  const [retrievalStrategy, setRetrievalStrategy] = useState<RetrievalStrategy>("advanced");
  const [pipelineProfile, setPipelineProfile] = useState<PipelineProfile>("standard");
  const [pdfTargetFile, setPdfTargetFile] = useState("");

  // Document state
  const [documents, setDocuments] = useState<IndexedFileSummary[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadInfo, setUploadInfo] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadProgressText, setUploadProgressText] = useState("");
  const [uploadVisibility, setUploadVisibility] = useState<"private" | "public">("private");
  const [docDropActive, setDocDropActive] = useState(false);
  const [composerDropActive, setComposerDropActive] = useState(false);

  // Prompt state
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [promptsLoading, setPromptsLoading] = useState(false);
  const [promptTitle, setPromptTitle] = useState("");
  const [promptContent, setPromptContent] = useState("");
  const [editingPromptId, setEditingPromptId] = useState<string | null>(null);
  const [promptCheckInfo, setPromptCheckInfo] = useState("");

  // UI state
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [error, setError] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Refs
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatUploadInputRef = useRef<HTMLInputElement | null>(null);
  const questionRef = useRef<HTMLTextAreaElement | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);

  return {
    // Session state
    sidebarOpen,
    setSidebarOpen,
    sidebarCollapsed,
    setSidebarCollapsed,
    sessions,
    setSessions,
    sessionLoading,
    setSessionLoading,
    currentSessionId,
    setCurrentSessionId,
    messages,
    setMessages,
    busySessionId,
    setBusySessionId,

    // Chat state
    question,
    setQuestion,
    isSending,
    setIsSending,
    runStatus,
    setRunStatus,
    useWeb,
    setUseWeb,
    useReasoning,
    setUseReasoning,
    agentClassHint,
    setAgentClassHint,
    retrievalStrategy,
    setRetrievalStrategy,
    pipelineProfile,
    setPipelineProfile,
    pdfTargetFile,
    setPdfTargetFile,

    // Document state
    documents,
    setDocuments,
    docsLoading,
    setDocsLoading,
    uploading,
    setUploading,
    uploadInfo,
    setUploadInfo,
    uploadProgress,
    setUploadProgress,
    uploadProgressText,
    setUploadProgressText,
    uploadVisibility,
    setUploadVisibility,
    docDropActive,
    setDocDropActive,
    composerDropActive,
    setComposerDropActive,

    // Prompt state
    prompts,
    setPrompts,
    promptsLoading,
    setPromptsLoading,
    promptTitle,
    setPromptTitle,
    promptContent,
    setPromptContent,
    editingPromptId,
    setEditingPromptId,
    promptCheckInfo,
    setPromptCheckInfo,

    // UI state
    toasts,
    setToasts,
    error,
    setError,
    settingsOpen,
    setSettingsOpen,

    // Refs
    fileInputRef,
    chatUploadInputRef,
    questionRef,
    chatScrollRef,
  };
}
