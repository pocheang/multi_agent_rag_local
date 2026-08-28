import { useEffect, useMemo, useState } from "react";
import {
  AGENT_MODES,
  type AgentClassHint,
} from "@/pages/chat/constants";
import type { Props } from "@/pages/chat/types";
import { ChatTopbar } from "@/pages/chat/components/ChatTopbar";
import { ChatMessages } from "@/pages/chat/components/ChatMessages";
import { ChatComposer } from "@/pages/chat/components/ChatComposer";
import { ClarificationPrompt } from "@/pages/chat/components/ClarificationPrompt";
import { ToastStack } from "@/pages/chat/components/ToastStack";
import { ChatSidebar } from "@/pages/chat/components/ChatSidebar";
import { ApiSettings } from "@/components/ApiSettings";
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
import { useTextareaAutoResize } from "@/pages/chat/hooks/useTextareaAutoResize";
import { useAutoScroll } from "@/pages/chat/hooks/useAutoScroll";
import { useDragDropPrevention } from "@/pages/chat/hooks/useDragDropPrevention";
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
  const permissionUser: UserIdentity | null = user;
  const { sectionsHidden, toggleSections } = useSectionToggle();
  const { topbarHidden, toggleTopbar } = useTopbarToggle();

  const {
    sidebarOpen, setSidebarOpen,
    sidebarCollapsed, setSidebarCollapsed,
    sessions, setSessions,
    sessionLoading, setSessionLoading,
    currentSessionId, setCurrentSessionId,
    messages, setMessages,
    busySessionId, setBusySessionId,
    isCreatingSession, setIsCreatingSession,
    question, setQuestion,
    isSending, setIsSending,
    runStatus, setRunStatus,
    agentClassHint, setAgentClassHint,
    pdfTargetFile, setPdfTargetFile,
    documents, setDocuments,
    docsLoading, setDocsLoading,
    uploading, setUploading,
    uploadInfo, setUploadInfo,
    uploadProgress, setUploadProgress,
    uploadProgressText, setUploadProgressText,
    uploadVisibility, setUploadVisibility,
    docDropActive, setDocDropActive,
    composerDropActive, setComposerDropActive,
    prompts, setPrompts,
    promptsLoading, setPromptsLoading,
    promptTitle, setPromptTitle,
    promptContent, setPromptContent,
    editingPromptId, setEditingPromptId,
    promptCheckInfo, setPromptCheckInfo,
    toasts, setToasts,
    error, setError,
    settingsOpen, setSettingsOpen,
    fileInputRef,
    chatUploadInputRef,
    questionRef,
    chatScrollRef,
  } = useChatPageState();

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
  });

  const helpers = useChatHelpers({
    canUploadAndManageDocs,
    pdfDocuments,
    pdfTargetFile,
    promptTitle,
    promptContent,
    editingPromptId,
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
      // Auth errors are already handled by checkAndInitiateClarification
      if ((error as { response?: { status?: number } })?.response?.status === 403 ||
          (error as { response?: { status?: number } })?.response?.status === 401) {
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
  useTextareaAutoResize({ ref: questionRef, value: question });
  useAutoScroll({ ref: chatScrollRef, messages });
  useAutoRefresh({
    refreshSessions: actions.refreshSessions,
    refreshDocuments: actions.refreshDocuments,
    refreshPrompts: actions.refreshPrompts,
  });
  useSettingsPolling({ onNotify: actions.notify });
  useDragDropPrevention();

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
        onToggleTopbar={toggleTopbar}
        onToggleSections={toggleSections}
      />

      <div className={`page-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
        <ChatSidebar
          sidebarOpen={sidebarOpen}
          sidebarCollapsed={sidebarCollapsed}
          sessions={sessions}
          sessionLoading={sessionLoading}
          currentSessionId={currentSessionId}
          busySessionId={busySessionId}
          isCreatingSession={isCreatingSession}
          agentClassHint={agentClassHint}
          agentModes={AGENT_MODES}
          agentDistribution={agentDistribution}
          pdfDocuments={pdfDocuments}
          pdfNeedingReindex={pdfNeedingReindex}
          pdfTargetFile={pdfTargetFile}
          documents={documents}
          docsLoading={docsLoading}
          uploading={uploading}
          uploadInfo={uploadInfo}
          uploadProgress={uploadProgress}
          uploadProgressText={uploadProgressText}
          uploadVisibility={uploadVisibility}
          docDropActive={docDropActive}
          canUploadAndManageDocs={canUploadAndManageDocs}
          isAdmin={isAdmin}
          user={permissionUser}
          prompts={prompts}
          promptsLoading={promptsLoading}
          promptTitle={promptTitle}
          promptContent={promptContent}
          editingPromptId={editingPromptId}
          promptCheckInfo={promptCheckInfo}
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
            composerDropActive={composerDropActive}
            question={question}
            questionRef={questionRef}
            chatUploadInputRef={chatUploadInputRef}
            isSending={isSending || !!clarification}
            quickPrompts={smartQuickPrompts}
            runStatus={runStatus}
            error={error}
            onQuestionChange={setQuestion}
            onAsk={async () => {
              if (clarification) return;
              await handleSendWithClarification(question);
            }}
            onStop={() => messageActions.stopCurrentRun(isSending)}
            onClearQuestion={() => setQuestion("")}
            onPromptPick={setQuestion}
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
        <KeyboardHelp />
      </div>
    </>
  );
}
