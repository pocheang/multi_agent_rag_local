import { useEffect, useMemo, useState } from "react";
import {
  AGENT_MODES,
  type AgentClassHint,
} from "@/pages/chat/constants";
import type { Props } from "@/pages/chat/types";
import { useChatStore } from "@/stores/useChatStore";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PromptDialog } from "@/components/PromptDialog";
import { useConfirmDialog } from "@/hooks/useConfirmDialog";
import { usePromptDialog } from "@/hooks/usePromptDialog";
import { ChatTopbar } from "@/pages/chat/components/ChatTopbar";
import { ChatMessages } from "@/pages/chat/components/ChatMessages";
import { ChatComposer } from "@/pages/chat/components/ChatComposer";
import { ClarificationPrompt } from "@/pages/chat/components/ClarificationPrompt";
import { ToastStack } from "@/pages/chat/components/ToastStack";
import { ChatSidebar } from "@/pages/chat/components/ChatSidebar";
import { ApiSettings } from "@/components/ApiSettings";
import { SessionManagementModal } from "@/components/SessionManagementModal";
import { useChatActions } from "@/pages/chat/hooks/useChatActions";
import { useFileUpload } from "@/pages/chat/hooks/useFileUpload";
import { useMessageActions } from "@/pages/chat/hooks/useMessageActions";
import { useChatPageState } from "@/pages/chat/hooks/useChatPageState";
import { useDragHandlers } from "@/pages/chat/hooks/useDragHandlers";
import { useChatComputed } from "@/pages/chat/hooks/useChatComputed";
import { useChatHelpers } from "@/pages/chat/hooks/useChatHelpers";
import { useClarification } from "@/pages/chat/hooks/useClarification";
import { useSettingsPolling } from "@/pages/chat/hooks/useSettingsPolling";
import { useAutoRefresh } from "@/pages/chat/hooks/useAutoRefresh";
import { useAutoScroll } from "@/pages/chat/hooks/useAutoScroll";
import { KeyboardHelp } from "@/components/KeyboardHelp";
import { generateSmartPrompts } from "@/pages/chat/utils/smartPrompts";
import type { UserIdentity } from "@/types/auth";
import { ChatRuntimePanels } from "@/pages/chat/components/ChatRuntimePanels";
import { SectionToggleButton } from "@/pages/chat/components/SectionToggleButton";
import { useSectionToggle, useTopbarToggle } from "@/hooks/useSectionToggle";

// Route-specific CSS (code-split by Vite)
import "@/styles/pages/chat-entry.css";

export function ChatPage({ user, onLogout, onUserRefresh }: Props) {
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [sessionManagementOpen, setSessionManagementOpen] = useState(false);
  const permissionUser: UserIdentity | null = user;
  const { sectionsHidden, toggleSections } = useSectionToggle();
  const { topbarHidden, toggleTopbar } = useTopbarToggle();

  const {
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
  } = useChatPageState();

  const confirmDialog = useConfirmDialog();
  const promptDialog = usePromptDialog();

  const dragHandlers = useDragHandlers(setComposerDropActive);

  const computed = useChatComputed({ documents, user });
  const {
    isAdmin,
    canUploadAndManageDocs,
    pdfDocuments,
    pdfNeedingReindex,
    agentDistribution,
  } = computed;

  const closeSidebar = () => {
    if (pdfDocuments.length > 0) setSidebarOpen(false);
  };

  const actions = useChatActions({
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
    confirm: confirmDialog.confirm,
    promptInput: promptDialog.promptInput,
  });

  const helpers = useChatHelpers({
    canUploadAndManageDocs,
    pdfDocuments,
    pdfTargetFile,
    setSidebarOpen,
    setAgentClassHint,
    setQuestion,
    questionRef,
    actions,
  });

  const fileUploadHandlers = useFileUpload({
    canUploadAndManageDocs,
    setDocDropActive,
    setComposerDropActive,
    notify: actions.notify,
    uploadFiles: actions.uploadFiles,
  });

  const messageActions = useMessageActions({
    currentSessionId,
    actions,
    setRunStatus,
    setMessages,
    setIsSending,
    setQuestion,
    onExecutionId: setExecutionId,
    onCreditsChanged: onUserRefresh,
  });

  // Clarification logic extracted to custom hook
  const {
    clarification,
    isClarifying,
    handleClarificationAnswer,
    handleClarificationSkip,
    checkAndInitiateClarification,
  } = useClarification({
    currentSessionId,
    onClarificationComplete: async (originalQuestion) => {
      await messageActions.ask({
        question: originalQuestion,
        isSending: false,
      });
    },
    onNotify: actions.notify,
  });

  const handleSendWithClarification = async (questionText: string) => {
    if (!questionText.trim()) return;

    setIsSending(true);
    setRunStatus("preparing");
    let sessionId = currentSessionId;

    try {
      sessionId = sessionId || await messageActions.ensureSessionForAsk();
      if (!sessionId) {
        setIsSending(false);
        setRunStatus("");
        return;
      }

      const needsClarification = await checkAndInitiateClarification(questionText, sessionId);
      if (needsClarification) {
        setIsSending(false);
        setRunStatus("");
        return;
      }

      // Information is sufficient, execute query directly
      await messageActions.ask({
        question: questionText,
        isSending: false,
        sessionId,
      });
    } catch (error: unknown) {
      // Auth errors are already handled (and notified) by checkAndInitiateClarification,
      // which re-throws ApiError (status only, never .response.status) for 401/403.
      const apiError = error as { response?: { status?: number }; status?: number };
      const status = apiError?.response?.status ?? apiError?.status;
      if (status === 403 || status === 401) {
        setIsSending(false);
        setRunStatus("");
        return;
      }

      // Fallback to direct query on other errors
      await messageActions.ask({
        question: questionText,
        isSending: false,
        sessionId: sessionId || undefined,
      });
    }
  };

  // Auto-select first PDF if needed
  useEffect(() => {
    if (!pdfDocuments.length) {
      setPdfTargetFile("");
      return;
    }
    if (!pdfTargetFile || !pdfDocuments.some((doc) => doc.filename === pdfTargetFile)) {
      setPdfTargetFile(pdfDocuments[0]?.filename || "");
    }
  }, [pdfDocuments, pdfTargetFile, setPdfTargetFile]);

  // Initialize on mount
  useEffect(() => {
    void (async () => {
      const rows = await actions.refreshSessions();
      await actions.refreshDocuments();
      await actions.refreshPrompts();
      if (rows.length > 0) await actions.loadSession(rows[0].session_id);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Custom hooks for side effects
  useAutoScroll({ ref: chatScrollRef, messages });
  useAutoRefresh({
    refreshSessions: actions.refreshSessions,
    refreshDocuments: actions.refreshDocuments,
    refreshPrompts: actions.refreshPrompts,
  });
  useSettingsPolling({ onNotify: actions.notify });

  const handleSidebarToggle = () => {
    if (window.innerWidth <= 1080) {
      setSidebarOpen((value) => !value);
      return;
    }
    setSidebarCollapsed((value) => !value);
  };

  // Smart prompt generation
  const smartQuickPrompts = useMemo(() => {
    return generateSmartPrompts(messages);
  }, [messages]);

  return (
    <>
      <ChatTopbar
        sidebarCollapsed={sidebarCollapsed}
        user={permissionUser}
        topbarHidden={topbarHidden}
        sectionsHidden={sectionsHidden}
        onToggleSidebar={handleSidebarToggle}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenSessionManagement={() => setSessionManagementOpen(true)}
        onToggleTopbar={toggleTopbar}
        onToggleSections={toggleSections}
      />

      <div className={`page-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
        <ChatSidebar
          agentModes={AGENT_MODES}
          agentDistribution={agentDistribution}
          pdfDocuments={pdfDocuments}
          pdfNeedingReindex={pdfNeedingReindex}
          canUploadAndManageDocs={canUploadAndManageDocs}
          isAdmin={isAdmin}
          user={permissionUser}
          fileInputRef={fileInputRef}
          onToggleSidebarCollapsed={handleSidebarToggle}
          onCreateSession={async () => { await actions.createSession(); }}
          onLoadSession={actions.loadSession}
          onDeleteSession={actions.deleteSession}
          onRenameSession={actions.renameSession}
          onPinSession={actions.pinSession}
          onSwitchAgentMode={helpers.switchAgentMode}
          onPdfTargetFileChange={setPdfTargetFile}
          onDraftQuestion={helpers.draftPdfQuestion}
          onRefreshDocuments={actions.refreshDocuments}
          onUploadVisibilityChange={setUploadVisibility}
          onMainUploadChange={fileUploadHandlers.onMainUploadChange}
          onDocsDrop={fileUploadHandlers.onDocsDrop}
          onDocDropActiveChange={setDocDropActive}
          onReindexDocument={helpers.reindexDocument}
          onDeleteDocument={helpers.deleteDocument}
          onRefreshPrompts={actions.refreshPrompts}
          onPromptTitleChange={setPromptTitle}
          onPromptContentChange={setPromptContent}
          onCheckPrompt={helpers.checkPrompt}
          onSavePrompt={helpers.savePrompt}
          onUsePrompt={(p) => {
            setQuestion(p.content || "");
            if (p.agent_class) setAgentClassHint((p.agent_class as AgentClassHint) || "");
          }}
          onEditPrompt={(p) => {
            setEditingPromptId(p.prompt_id);
            setPromptTitle(p.title || "");
            setPromptContent(p.content || "");
          }}
          onDeletePrompt={helpers.deletePrompt}
          onLogout={onLogout}
        />

        <div className={`backdrop ${sidebarOpen ? "show" : ""}`} onClick={() => setSidebarOpen(false)} />

        <main className="main">
          <ChatMessages
            messages={messages}
            containerRef={chatScrollRef}
            documentsCount={documents.length}
            sessionsCount={sessions.length}
            onEditMessage={(msg) => messageActions.editMessage(msg)}
            onRemoveMessage={messageActions.removeMessage}
            onCreateSession={async () => { await actions.createSession(); }}
            onNavigateToArchitecture={() => window.location.href = '/app/architecture'}
          />

          <ChatRuntimePanels executionId={executionId} />

          {clarification && clarification.action === "NEED_CLARIFICATION" && clarification.clarification && (
            <ClarificationPrompt
              question={clarification.clarification}
              context={clarification.context}
              onAnswer={handleClarificationAnswer}
              onSkip={handleClarificationSkip}
              isSubmitting={isClarifying}
            />
          )}

          <ChatComposer
            questionRef={questionRef}
            chatUploadInputRef={chatUploadInputRef}
            isSending={isSending || !!clarification}
            quickPrompts={smartQuickPrompts}
            onAsk={async () => {
              if (clarification) return;
              await handleSendWithClarification(useChatStore.getState().question);
            }}
            onStop={() => messageActions.stopCurrentRun(isSending)}
            onComposerDragEnter={dragHandlers.onComposerDragEnter}
            onComposerDragOver={dragHandlers.onComposerDragOver}
            onComposerDragLeave={dragHandlers.onComposerDragLeave}
            onComposerDrop={fileUploadHandlers.onComposerDrop}
            onChatUploadChange={fileUploadHandlers.onChatUploadChange}
          />
        </main>

        <ToastStack
          toasts={toasts}
          onRemove={(id) => setToasts((prev) => prev.filter((t) => t.id !== id))}
        />
        <SectionToggleButton sectionsHidden={sectionsHidden} onToggle={toggleSections} />
        <ApiSettings isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
        <ConfirmDialog
          isOpen={confirmDialog.isOpen}
          title={confirmDialog.options?.title || ""}
          message={confirmDialog.options?.message || ""}
          confirmText={confirmDialog.options?.confirmText}
          cancelText={confirmDialog.options?.cancelText}
          isDanger={confirmDialog.options?.isDanger}
          onConfirm={confirmDialog.handleConfirm}
          onCancel={confirmDialog.handleCancel}
        />
        <PromptDialog
          isOpen={promptDialog.isOpen}
          title={promptDialog.options?.title || ""}
          message={promptDialog.options?.message || ""}
          defaultValue={promptDialog.options?.defaultValue}
          placeholder={promptDialog.options?.placeholder}
          confirmText={promptDialog.options?.confirmText}
          cancelText={promptDialog.options?.cancelText}
          multiline={promptDialog.options?.multiline}
          inputType={promptDialog.options?.inputType}
          onConfirm={promptDialog.handleConfirm}
          onCancel={promptDialog.handleCancel}
        />
        <SessionManagementModal
          isOpen={sessionManagementOpen}
          onClose={() => setSessionManagementOpen(false)}
          currentSessionId={currentSessionId}
          messages={messages}
          onSelectSession={(sessionId) => void actions.loadSession(sessionId)}
        />
        <KeyboardHelp />
      </div>
    </>
  );
}
