import { useEffect, useMemo, useRef } from "react";
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
import type { User, UserRole } from "@/hooks/usePermissions";
import { appApi } from "@/lib/api";

// Route-specific CSS (code-split by Vite)
import "@/styles/pages/chat-entry.css";

export function ChatPage({ user, onLogout, themeLabel, onThemeToggle }: Props) {
  const { t } = useTranslation();
  const lastOverrideStateRef = useRef<{ enabled: boolean; provider: string; model: string } | null>(null);
  // Convert AuthUser to User type for permission system
  const permissionUser: User | null = user ? {
    user_id: user.user_id,
    username: user.username,
    role: user.role as UserRole,
    status: user.status,
    display_name: user.display_name ?? undefined,
  } : null;
  const {
    sidebarOpen, setSidebarOpen,
    sidebarCollapsed, setSidebarCollapsed,
    sessions, setSessions,
    sessionLoading, setSessionLoading,
    currentSessionId, setCurrentSessionId,
    messages, setMessages,
    busySessionId, setBusySessionId,
    question, setQuestion,
    isSending, setIsSending,
    runStatus, setRunStatus,
    useWeb, setUseWeb,
    useReasoning, setUseReasoning,
    agentClassHint, setAgentClassHint,
    retrievalStrategy, setRetrievalStrategy,
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
  });

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
    <div className={`page-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <ChatSidebar
        sidebarOpen={sidebarOpen}
        sidebarCollapsed={sidebarCollapsed}
        sessions={sessions}
        sessionLoading={sessionLoading}
        currentSessionId={currentSessionId}
        busySessionId={busySessionId}
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
        <ChatTopbar
          themeLabel={themeLabel}
          sidebarCollapsed={sidebarCollapsed}
          user={permissionUser}
          onToggleSidebar={handleSidebarToggle}
          onOpenSettings={() => setSettingsOpen(true)}
          onThemeToggle={onThemeToggle}
        />

        <ChatMessages
          messages={messages}
          containerRef={chatScrollRef}
          documentsCount={documents.length}
          sessionsCount={sessions.length}
          onEditMessage={(msg) => messageActions.editMessage(msg, useWeb, useReasoning)}
          onRemoveMessage={messageActions.removeMessage}
          onCreateSession={async () => { await actions.createSession(); }}
          onNavigateToArchitecture={() => window.location.href = '/architecture'}
        />

        <ChatComposer
          composerDropActive={composerDropActive}
          question={question}
          questionRef={questionRef}
          chatUploadInputRef={chatUploadInputRef}
          isSending={isSending}
          quickPrompts={smartQuickPrompts}
          runStatus={runStatus}
          error={error}
          useWeb={useWeb}
          useReasoning={useReasoning}
          agentClassHint={agentClassHint}
          retrievalStrategy={retrievalStrategy}
          onQuestionChange={setQuestion}
          onAsk={() => messageActions.ask({ question, isSending, useWeb, useReasoning, agentClassHint, retrievalStrategy })}
          onStop={() => messageActions.stopCurrentRun(isSending)}
          onClearQuestion={() => setQuestion("")}
          onPromptPick={setQuestion}
          onUseWebChange={setUseWeb}
          onUseReasoningChange={setUseReasoning}
          onAgentClassHintChange={(v) => setAgentClassHint((v as AgentClassHint) || "")}
          onRetrievalStrategyChange={(v) => setRetrievalStrategy((v as RetrievalStrategy) || "advanced")}
          onComposerDragEnter={dragHandlers.onComposerDragEnter}
          onComposerDragOver={dragHandlers.onComposerDragOver}
          onComposerDragLeave={dragHandlers.onComposerDragLeave}
          onComposerDrop={fileUploadHandlers.onComposerDrop}
          onChatUploadChange={fileUploadHandlers.onChatUploadChange}
        />
      </main>

      <ToastStack toasts={toasts} />
      <ApiSettings isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <KeyboardHelp />
    </div>
  );
}
