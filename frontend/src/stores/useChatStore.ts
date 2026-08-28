import { create } from "zustand";
import type { IndexedFileSummary, PromptTemplate, SessionMessage, SessionSummary } from "@/types/api";
import type { Toast } from "@/pages/chat/types";
import type { AgentClassHint } from "@/pages/chat/constants";

export interface ChatState {
  // Session State
  sidebarOpen: boolean;
  sidebarCollapsed: boolean;
  sessions: SessionSummary[];
  sessionLoading: boolean;
  currentSessionId: string | null;
  messages: SessionMessage[];
  busySessionId: string | null;
  isCreatingSession: boolean;

  // Chat State
  question: string;
  isSending: boolean;
  runStatus: string;
  agentClassHint: AgentClassHint;
  pdfTargetFile: string;

  // Document State
  documents: IndexedFileSummary[];
  docsLoading: boolean;
  uploading: boolean;
  uploadInfo: string;
  uploadProgress: number;
  uploadProgressText: string;
  uploadVisibility: "private" | "public";
  docDropActive: boolean;
  composerDropActive: boolean;

  // Prompt State
  prompts: PromptTemplate[];
  promptsLoading: boolean;
  promptTitle: string;
  promptContent: string;
  editingPromptId: string | null;
  promptCheckInfo: string;

  // UI State
  toasts: Toast[];
  error: string;
  settingsOpen: boolean;

  // Actions / Setters
  setSidebarOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
  setSidebarCollapsed: (collapsed: boolean | ((prev: boolean) => boolean)) => void;
  setSessions: (sessions: SessionSummary[] | ((prev: SessionSummary[]) => SessionSummary[])) => void;
  setSessionLoading: (loading: boolean | ((prev: boolean) => boolean)) => void;
  setCurrentSessionId: (id: string | null | ((prev: string | null) => string | null)) => void;
  setMessages: (messages: SessionMessage[] | ((prev: SessionMessage[]) => SessionMessage[])) => void;
  setBusySessionId: (id: string | null | ((prev: string | null) => string | null)) => void;
  setIsCreatingSession: (creating: boolean | ((prev: boolean) => boolean)) => void;

  setQuestion: (question: string | ((prev: string) => string)) => void;
  setIsSending: (isSending: boolean | ((prev: boolean) => boolean)) => void;
  setRunStatus: (status: string | ((prev: string) => string)) => void;
  setAgentClassHint: (hint: AgentClassHint | ((prev: AgentClassHint) => AgentClassHint)) => void;
  setPdfTargetFile: (file: string | ((prev: string) => string)) => void;

  setDocuments: (docs: IndexedFileSummary[] | ((prev: IndexedFileSummary[]) => IndexedFileSummary[])) => void;
  setDocsLoading: (loading: boolean | ((prev: boolean) => boolean)) => void;
  setUploading: (uploading: boolean | ((prev: boolean) => boolean)) => void;
  setUploadInfo: (info: string | ((prev: string) => string)) => void;
  setUploadProgress: (progress: number | ((prev: number) => number)) => void;
  setUploadProgressText: (text: string | ((prev: string) => string)) => void;
  setUploadVisibility: (vis: "private" | "public" | ((prev: "private" | "public") => "private" | "public")) => void;
  setDocDropActive: (active: boolean | ((prev: boolean) => boolean)) => void;
  setComposerDropActive: (active: boolean | ((prev: boolean) => boolean)) => void;

  setPrompts: (prompts: PromptTemplate[] | ((prev: PromptTemplate[]) => PromptTemplate[])) => void;
  setPromptsLoading: (loading: boolean | ((prev: boolean) => boolean)) => void;
  setPromptTitle: (title: string | ((prev: string) => string)) => void;
  setPromptContent: (content: string | ((prev: string) => string)) => void;
  setEditingPromptId: (id: string | null | ((prev: string | null) => string | null)) => void;
  setPromptCheckInfo: (info: string | ((prev: string) => string)) => void;

  setToasts: (toasts: Toast[] | ((prev: Toast[]) => Toast[])) => void;
  setError: (error: string | ((prev: string) => string)) => void;
  setSettingsOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
}

function updateValue<T>(val: T | ((prev: T) => T), prev: T): T {
  return typeof val === "function" ? (val as (prev: T) => T)(prev) : val;
}

export const useChatStore = create<ChatState>((set) => ({
  // Session State
  sidebarOpen: false,
  sidebarCollapsed: false,
  sessions: [],
  sessionLoading: true,
  currentSessionId: null,
  messages: [],
  busySessionId: null,
  isCreatingSession: false,

  // Chat State
  question: "",
  isSending: false,
  runStatus: "",
  agentClassHint: "",
  pdfTargetFile: "",

  // Document State
  documents: [],
  docsLoading: false,
  uploading: false,
  uploadInfo: "",
  uploadProgress: 0,
  uploadProgressText: "",
  uploadVisibility: "private",
  docDropActive: false,
  composerDropActive: false,

  // Prompt State
  prompts: [],
  promptsLoading: false,
  promptTitle: "",
  promptContent: "",
  editingPromptId: null,
  promptCheckInfo: "",

  // UI State
  toasts: [],
  error: "",
  settingsOpen: false,

  // Setters supporting both raw values and functional updates
  setSidebarOpen: (val) => set((s) => ({ sidebarOpen: updateValue(val, s.sidebarOpen) })),
  setSidebarCollapsed: (val) => set((s) => ({ sidebarCollapsed: updateValue(val, s.sidebarCollapsed) })),
  setSessions: (val) => set((s) => ({ sessions: updateValue(val, s.sessions) })),
  setSessionLoading: (val) => set((s) => ({ sessionLoading: updateValue(val, s.sessionLoading) })),
  setCurrentSessionId: (val) => set((s) => ({ currentSessionId: updateValue(val, s.currentSessionId) })),
  setMessages: (val) => set((s) => ({ messages: updateValue(val, s.messages) })),
  setBusySessionId: (val) => set((s) => ({ busySessionId: updateValue(val, s.busySessionId) })),
  setIsCreatingSession: (val) => set((s) => ({ isCreatingSession: updateValue(val, s.isCreatingSession) })),

  setQuestion: (val) => set((s) => ({ question: updateValue(val, s.question) })),
  setIsSending: (val) => set((s) => ({ isSending: updateValue(val, s.isSending) })),
  setRunStatus: (val) => set((s) => ({ runStatus: updateValue(val, s.runStatus) })),
  setAgentClassHint: (val) => set((s) => ({ agentClassHint: updateValue(val, s.agentClassHint) })),
  setPdfTargetFile: (val) => set((s) => ({ pdfTargetFile: updateValue(val, s.pdfTargetFile) })),

  setDocuments: (val) => set((s) => ({ documents: updateValue(val, s.documents) })),
  setDocsLoading: (val) => set((s) => ({ docsLoading: updateValue(val, s.docsLoading) })),
  setUploading: (val) => set((s) => ({ uploading: updateValue(val, s.uploading) })),
  setUploadInfo: (val) => set((s) => ({ uploadInfo: updateValue(val, s.uploadInfo) })),
  setUploadProgress: (val) => set((s) => ({ uploadProgress: updateValue(val, s.uploadProgress) })),
  setUploadProgressText: (val) => set((s) => ({ uploadProgressText: updateValue(val, s.uploadProgressText) })),
  setUploadVisibility: (val) => set((s) => ({ uploadVisibility: updateValue(val, s.uploadVisibility) })),
  setDocDropActive: (val) => set((s) => ({ docDropActive: updateValue(val, s.docDropActive) })),
  setComposerDropActive: (val) => set((s) => ({ composerDropActive: updateValue(val, s.composerDropActive) })),

  setPrompts: (val) => set((s) => ({ prompts: updateValue(val, s.prompts) })),
  setPromptsLoading: (val) => set((s) => ({ promptsLoading: updateValue(val, s.promptsLoading) })),
  setPromptTitle: (val) => set((s) => ({ promptTitle: updateValue(val, s.promptTitle) })),
  setPromptContent: (val) => set((s) => ({ promptContent: updateValue(val, s.promptContent) })),
  setEditingPromptId: (val) => set((s) => ({ editingPromptId: updateValue(val, s.editingPromptId) })),
  setPromptCheckInfo: (val) => set((s) => ({ promptCheckInfo: updateValue(val, s.promptCheckInfo) })),

  setToasts: (val) => set((s) => ({ toasts: updateValue(val, s.toasts) })),
  setError: (val) => set((s) => ({ error: updateValue(val, s.error) })),
  setSettingsOpen: (val) => set((s) => ({ settingsOpen: updateValue(val, s.settingsOpen) })),
}));
