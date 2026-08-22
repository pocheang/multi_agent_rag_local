import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  AGENT_MODES,
  type AgentClassHint,
  type RetrievalStrategy,
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
import { KeyboardHelp } from "@/components/KeyboardHelp";
import { generateSmartPrompts } from "@/pages/chat/utils/smartPrompts";
import type { UserIdentity } from "@/types/auth";
import type { ClarificationResponse } from "@/types/api";
import { appApi } from "@/lib/api";
import { clarificationApi } from "@/services/api/chat";
import { ChatRuntimePanels } from "@/pages/chat/components/ChatRuntimePanels";
import { SectionToggleButton } from "@/pages/chat/components/SectionToggleButton";
import { useSectionToggle, useTopbarToggle } from "@/hooks/useSectionToggle";

// Route-specific CSS (code-split by Vite)
import "@/styles/pages/chat-entry.css";

export function ChatPage({ user, onLogout, onUserRefresh, themeLabel, onThemeToggle }: Props) {
  const { t } = useTranslation();
  const [executionId, setExecutionId] = useState<string | null>(null);
  const lastOverrideStateRef = useRef<{ enabled: boolean; provider: string; model: string } | null>(null);
  const permissionUser: UserIdentity | null = user;
  const { sectionsHidden, toggleSections } = useSectionToggle();
  const { topbarHidden, toggleTopbar } = useTopbarToggle();

  // Clarification state
  const [clarification, setClarification] = useState<ClarificationResponse | null>(null);
  const [isClarifying, setIsClarifying] = useState(false);
  const [originalQuestion, setOriginalQuestion] = useState<string>("");

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
    useWeb, setUseWeb,
    useReasoning, setUseReasoning,
    agentClassHint, setAgentClassHint,
  retrievalStrategy, setRetrievalStrategy,
    pipelineProfile, setPipelineProfile,
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
    useReasoning,
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

  // Clarification handlers
  const handleClarificationAnswer = async (fieldName: string, answer: string) => {
    if (!clarification || !currentSessionId || !originalQuestion) return;

    setIsClarifying(true);

    try {
      const response = await clarificationApi.checkClarification({
        question: originalQuestion,
        session_id: currentSessionId,
        field_name: fieldName,
        answer: answer,
      });

      if (response.action === "NEED_CLARIFICATION") {
        // Continue clarification
        setClarification(response);
      } else {
        // Information is sufficient, execute query
        setClarification(null);
        setOriginalQuestion("");
        await messageActions.ask({
          question: originalQuestion,
          isSending: false,  // Always pass false - let ask() manage its own state
          useWeb,
          useReasoning,
          agentClassHint,
          retrievalStrategy,
          pipelineProfile,
        });
      }
    } catch (error) {
      console.error("Clarification answer failed:", error);
      actions.notify(t("chat.clarificationError") || "Failed to submit clarification", "error");
    } finally {
      setIsClarifying(false);
    }
  };

  const handleClarificationSkip = async () => {
    if (!currentSessionId || !originalQuestion) return;

    try {
      await clarificationApi.resetClarification(currentSessionId);
      setClarification(null);
      setOriginalQuestion("");
      await messageActions.ask({
        question: originalQuestion,
        isSending: false,  // Always pass false - let ask() manage its own state
        useWeb,
        useReasoning,
        agentClassHint,
        retrievalStrategy,
        pipelineProfile,
      });
    } catch (error) {
      console.error("Skip clarification failed:", error);
      actions.notify(t("chat.skipClarificationError") || "Failed to skip clarification", "error");
    }
  };

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

      // Check if clarification is needed
      const response = await clarificationApi.checkClarification({
        question: questionText,
        session_id: sessionId,
      });

      if (response.action === "NEED_CLARIFICATION") {
        // Show clarification prompt
        setClarification(response);
        setOriginalQuestion(questionText);
        setIsSending(false);
        setRunStatus("");
        return;
      }

      // Information is sufficient, execute query directly
      await messageActions.ask({
        question: questionText,
        isSending: false,  // Always pass false - let ask() manage its own state
        sessionId,
        useWeb,
        useReasoning,
        agentClassHint,
        retrievalStrategy,
        pipelineProfile,
      });
    } catch (error: any) {
      console.error("Clarification check failed:", error);

      // Check if it's an authentication or permission error
      const status = error?.response?.status || error?.status;
      if (status === 403 || status === 401) {
        // Authentication/permission error: show error, don't fallback
        actions.notify(
          t("chat.clarificationAuthError") || "Authentication required for advanced features",
          "error",
        );
        setIsSending(false);
        setRunStatus("");
        return;
      }

      // Other errors (network, server): fallback to direct query
      console.warn("Clarification service unavailable, falling back to direct query");
      await messageActions.ask({
        question: questionText,
        isSending: false,  // Always pass false - let ask() manage its own state
        sessionId: sessionId || undefined,
        useWeb,
        useReasoning,
        agentClassHint,
        retrievalStrategy,
        pipelineProfile,
      });
    }
  };

  useEffect(() => {
    if (!pdfDocuments.length) {
      setPdfTargetFile("");
      return;
    }
    if (!pdfTargetFile || !pdfDocuments.some((doc) => doc.filename === pdfTargetFile)) {
      setPdfTargetFile(pdfDocuments[0]?.filename || "");
    }
  }, [pdfDocuments, pdfTargetFile, setPdfTargetFile]);

  useEffect(() => {
    void (async () => {
      const rows = await actions.refreshSessions();
      await actions.refreshDocuments();
      await actions.refreshPrompts();
      if (rows.length > 0) await actions.loadSession(rows[0].session_id);

      // Get initial global settings override status
      try {
        const res = await appApi.getUserApiSettings();
        if (res.ok && res.settings) {
          lastOverrideStateRef.current = {
            enabled: !!res.settings.global_override_enabled,
            provider: res.settings.global_provider || "",
            model: res.settings.global_model || "",
          };
        }
      } catch (e) {
        // Silent catch
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const el = questionRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(180, el.scrollHeight)}px`;
  }, [question, questionRef]);

  useEffect(() => {
    if (chatScrollRef.current) chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
  }, [messages, chatScrollRef]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void actions.refreshSessions(false, true);
      void actions.refreshDocuments(true);
      void actions.refreshPrompts(true);

      // Check global settings override status periodically
      void (async () => {
        try {
          const res = await appApi.getUserApiSettings();
          if (res.ok && res.settings) {
            const enabled = !!res.settings.global_override_enabled;
            const provider = res.settings.global_provider || "";
            const model = res.settings.global_model || "";

            if (lastOverrideStateRef.current !== null) {
              const prev = lastOverrideStateRef.current;
              if (prev.enabled !== enabled || prev.provider !== provider || prev.model !== model) {
                if (enabled) {
                  const desc = t("components.apiSettings.globalOverrideDesc", { provider, model });
                  actions.notify(
                    `${t("components.apiSettings.globalOverrideNotice")}: ${desc}`,
                    "info",
                    4000
                  );
                } else if (prev.enabled) {
                  actions.notify(
                    t("components.apiSettings.globalOverrideDisabledNotice"),
                    "info",
                    4000
                  );
                }
              }
            }
            lastOverrideStateRef.current = { enabled, provider, model };
          }
        } catch (e) {
          // Silent catch
        }
      })();
    }, 25000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const preventDefault = (evt: DragEvent) => evt.preventDefault();
    window.addEventListener("dragover", preventDefault);
    window.addEventListener("drop", preventDefault);
    return () => {
      window.removeEventListener("dragover", preventDefault);
      window.removeEventListener("drop", preventDefault);
    };
  }, []);

  const handleSidebarToggle = () => {
    if (window.innerWidth <= 1080) {
      setSidebarOpen((value) => !value);
      return;
    }
    setSidebarCollapsed((value) => !value);
  };

  // 智能生成快速提示
  const smartQuickPrompts = useMemo(() => {
    return generateSmartPrompts(messages);
  }, [messages]);

  return (
    <>
      <ChatTopbar
        themeLabel={themeLabel}
        sidebarCollapsed={sidebarCollapsed}
        user={permissionUser}
        topbarHidden={topbarHidden}
        sectionsHidden={sectionsHidden}
        onToggleSidebar={handleSidebarToggle}
        onOpenSettings={() => setSettingsOpen(true)}
        onThemeToggle={onThemeToggle}
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
          onEditMessage={(msg) => messageActions.editMessage(msg, useWeb, useReasoning)}
          onRemoveMessage={messageActions.removeMessage}
          onCreateSession={async () => { await actions.createSession(); }}
          onNavigateToArchitecture={() => window.location.href = '/app/architecture'}
        />

        <ChatRuntimePanels executionId={executionId} />

        {/* Clarification Prompt */}
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
          useWeb={useWeb}
          useReasoning={useReasoning}
          agentClassHint={agentClassHint}
          retrievalStrategy={retrievalStrategy}
          pipelineProfile={pipelineProfile}
          onQuestionChange={setQuestion}
          onAsk={async () => {
            if (clarification) return; // Prevent sending while clarifying
            await handleSendWithClarification(question);
          }}
          onStop={() => messageActions.stopCurrentRun(isSending)}
          onClearQuestion={() => setQuestion("")}
          onPromptPick={setQuestion}
          onUseWebChange={setUseWeb}
          onUseReasoningChange={setUseReasoning}
          onAgentClassHintChange={(v) => setAgentClassHint((v as AgentClassHint) || "")}
          onRetrievalStrategyChange={(v) => setRetrievalStrategy((v as RetrievalStrategy) || "advanced")}
          onPipelineProfileChange={(v) => setPipelineProfile(v === "strict_quality" || v === "advanced" ? v : "standard")}
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
