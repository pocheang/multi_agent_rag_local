import { Link } from "react-router-dom";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type React from "react";
import type { PromptTemplate } from "@/types/api";
import type { UserIdentity } from "@/types/auth";
import { SessionList } from "@/pages/chat/components/SessionList";
import { WorkbenchPanel } from "@/pages/chat/components/WorkbenchPanel";
import { useChatStore } from "@/stores/useChatStore";
import { useShallow } from "zustand/react/shallow";
import type { IndexedFileSummary } from "@/types/api";

type AgentClassHint = "" | "general" | "cybersecurity" | "artificial_intelligence" | "pdf_text";

type AgentMode = {
  key: AgentClassHint;
  title: string;
  desc: string;
};

type Props = {
  agentModes: AgentMode[];
  agentDistribution: Array<{ agent: string; count: number }>;
  pdfDocuments: IndexedFileSummary[];
  pdfNeedingReindex: IndexedFileSummary[];
  canUploadAndManageDocs: boolean;
  isAdmin: boolean;
  user: UserIdentity | null;
  fileInputRef: React.RefObject<HTMLInputElement>;
  onToggleSidebarCollapsed: () => void;
  onCreateSession: () => Promise<void>;
  onLoadSession: (sessionId: string) => Promise<void>;
  onDeleteSession: (sessionId: string) => Promise<void>;
  onRenameSession?: (sessionId: string, newTitle: string) => Promise<void>;
  onPinSession?: (sessionId: string, pinned: boolean) => Promise<void>;
  onSwitchAgentMode: (mode: AgentClassHint) => void;
  onPdfTargetFileChange: (filename: string) => void;
  onDraftQuestion: () => void;
  onRefreshDocuments: () => Promise<void>;
  onUploadVisibilityChange: (visibility: "private" | "public") => void;
  onMainUploadChange: (evt: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  onDocsDrop: (evt: React.DragEvent<HTMLDivElement>) => Promise<void>;
  onDocDropActiveChange: (active: boolean) => void;
  onReindexDocument: (doc: IndexedFileSummary) => Promise<void>;
  onDeleteDocument: (doc: IndexedFileSummary, removeFile: boolean) => Promise<void>;
  onRefreshPrompts: () => Promise<void>;
  onPromptTitleChange: (title: string) => void;
  onPromptContentChange: (content: string) => void;
  onCheckPrompt: () => Promise<void>;
  onSavePrompt: () => Promise<void>;
  onUsePrompt: (prompt: PromptTemplate) => void;
  onEditPrompt: (prompt: PromptTemplate) => void;
  onDeletePrompt: (prompt: PromptTemplate) => Promise<void>;
  onLogout: () => Promise<void>;
};

export function ChatSidebar({
  agentModes,
  agentDistribution,
  pdfDocuments,
  pdfNeedingReindex,
  canUploadAndManageDocs,
  isAdmin,
  user,
  fileInputRef,
  onToggleSidebarCollapsed,
  onCreateSession,
  onLoadSession,
  onDeleteSession,
  onRenameSession,
  onPinSession,
  onSwitchAgentMode,
  onPdfTargetFileChange,
  onDraftQuestion,
  onRefreshDocuments,
  onUploadVisibilityChange,
  onMainUploadChange,
  onDocsDrop,
  onDocDropActiveChange,
  onReindexDocument,
  onDeleteDocument,
  onRefreshPrompts,
  onPromptTitleChange,
  onPromptContentChange,
  onCheckPrompt,
  onSavePrompt,
  onUsePrompt,
  onEditPrompt,
  onDeletePrompt,
  onLogout,
}: Props) {
  const { t } = useTranslation();
  const {
    sidebarOpen,
    sidebarCollapsed,
    sessions,
    sessionLoading,
    currentSessionId,
    busySessionId,
    isCreatingSession,
    agentClassHint,
    pdfTargetFile,
    documents,
    docsLoading,
    uploading,
    uploadInfo,
    uploadProgress,
    uploadProgressText,
    uploadVisibility,
    docDropActive,
    prompts,
    promptsLoading,
    promptTitle,
    promptContent,
    editingPromptId,
    promptCheckInfo,
  } = useChatStore(
    useShallow((s) => ({
      sidebarOpen: s.sidebarOpen,
      sidebarCollapsed: s.sidebarCollapsed,
      sessions: s.sessions,
      sessionLoading: s.sessionLoading,
      currentSessionId: s.currentSessionId,
      busySessionId: s.busySessionId,
      isCreatingSession: s.isCreatingSession,
      agentClassHint: s.agentClassHint,
      pdfTargetFile: s.pdfTargetFile,
      documents: s.documents,
      docsLoading: s.docsLoading,
      uploading: s.uploading,
      uploadInfo: s.uploadInfo,
      uploadProgress: s.uploadProgress,
      uploadProgressText: s.uploadProgressText,
      uploadVisibility: s.uploadVisibility,
      docDropActive: s.docDropActive,
      prompts: s.prompts,
      promptsLoading: s.promptsLoading,
      promptTitle: s.promptTitle,
      promptContent: s.promptContent,
      editingPromptId: s.editingPromptId,
      promptCheckInfo: s.promptCheckInfo,
    }))
  );
  const isDesktop = typeof window !== "undefined" ? window.innerWidth > 1080 : true;
  const showCompactRail = sidebarCollapsed && isDesktop;
  const [sessionSearchRequest, setSessionSearchRequest] = useState(0);

  const handleCreateFromRail = async () => {
    onToggleSidebarCollapsed();
    await onCreateSession();
  };

  const handleSearchFromRail = () => {
    setSessionSearchRequest((current) => current + 1);
    onToggleSidebarCollapsed();
  };

  if (showCompactRail) {
    return (
      <aside className="sidebar sidebar-rail" aria-label={t("components.chat.railLabel")}>
        <div className="sidebar-rail-actions">
          <button type="button" className="sidebar-rail-btn active" onClick={onToggleSidebarCollapsed} title={t("components.chat.expandRail")}>
            <span className="rail-icon rail-icon-panel" aria-hidden="true" />
          </button>
          <button type="button" className="sidebar-rail-btn" onClick={() => void handleCreateFromRail()} title={t("components.chat.newSessionFromRail")}>
            <span className="rail-icon rail-icon-edit" aria-hidden="true" />
          </button>
          <button type="button" className="sidebar-rail-btn" onClick={handleSearchFromRail} title={t("components.chat.searchFromRail")}>
            <span className="rail-icon rail-icon-search" aria-hidden="true" />
          </button>
        </div>
        <div className="sidebar-rail-footer">
          <button type="button" className="sidebar-rail-user" onClick={onToggleSidebarCollapsed} title={t("components.chat.accountFromRail")}>
            {user?.username?.charAt(0).toUpperCase() || "U"}
          </button>
        </div>
      </aside>
    );
  }

  return (
    <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
      <div className="sidebar-shell">
        <div className="sidebar-header">
          <div className="sidebar-brand-mark" aria-hidden="true">
            <span>R</span>
          </div>
          <div className="sidebar-brand-block">
            <span className="sidebar-brand-kicker">{t("components.chat.brandKicker")}</span>
            <div className="brand">QueryMind</div>
            <p className="muted">{t("components.chat.sidebarDescription")}</p>
          </div>
          <button type="button" className="sidebar-collapse-btn" onClick={onToggleSidebarCollapsed}>
            {t("components.chat.collapse")}
          </button>
        </div>

        <div className="sidebar-history">
          <div className="sidebar-group-title">
            <span>{t("components.chat.sessions")}</span>
          </div>
          <SessionList
            sessions={sessions}
            sessionLoading={sessionLoading}
            currentSessionId={currentSessionId}
            busySessionId={busySessionId}
            isCreatingSession={isCreatingSession}
            searchRequestKey={sessionSearchRequest}
            user={user}
            onCreateSession={onCreateSession}
            onLoadSession={onLoadSession}
            onDeleteSession={onDeleteSession}
            onRenameSession={onRenameSession}
            onPinSession={onPinSession}
          />
        </div>

        <WorkbenchPanel
          agentClassHint={agentClassHint}
          agentModes={agentModes}
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
          user={user}
          prompts={prompts}
          promptsLoading={promptsLoading}
          promptTitle={promptTitle}
          promptContent={promptContent}
          editingPromptId={editingPromptId}
          promptCheckInfo={promptCheckInfo}
          fileInputRef={fileInputRef}
          onSwitchAgentMode={onSwitchAgentMode}
          onPdfTargetFileChange={onPdfTargetFileChange}
          onDraftQuestion={onDraftQuestion}
          onRefreshDocuments={onRefreshDocuments}
          onUploadVisibilityChange={onUploadVisibilityChange}
          onMainUploadChange={onMainUploadChange}
          onDocsDrop={onDocsDrop}
          onDocDropActiveChange={onDocDropActiveChange}
          onReindexDocument={onReindexDocument}
          onDeleteDocument={onDeleteDocument}
          onRefreshPrompts={onRefreshPrompts}
          onPromptTitleChange={onPromptTitleChange}
          onPromptContentChange={onPromptContentChange}
          onCheckPrompt={onCheckPrompt}
          onSavePrompt={onSavePrompt}
          onUsePrompt={onUsePrompt}
          onEditPrompt={onEditPrompt}
          onDeletePrompt={onDeletePrompt}
        />

        <div className="sidebar-footer">
          <div className="sidebar-user-info">
            <div className="sidebar-user-avatar">{user?.username?.charAt(0).toUpperCase() || "U"}</div>
            <div className="sidebar-user-details">
              <div className="sidebar-user-name">{user?.username || t("components.chat.userFallback")}</div>
              <div className="sidebar-user-role">{user?.role || "user"}</div>
            </div>
          </div>
          <div className="sidebar-user-actions">
            <Link to="/app/profile" className="sidebar-user-action-btn" title={t("components.chat.profile")}>
              <span>{t("components.chat.profile")}</span>
            </Link>
            <Link to="/app/change-password" className="sidebar-user-action-btn" title={t("components.chat.password")}>
              <span>{t("components.chat.password")}</span>
            </Link>
            {isAdmin && (
              <Link to="/app/admin" className="sidebar-user-action-btn sidebar-user-action-admin" title={t("components.chat.admin")}>
                <span>{t("components.chat.admin")}</span>
              </Link>
            )}
            <button type="button" className="sidebar-user-action-btn" onClick={() => void onLogout()} title={t("components.chat.logout")}>
              <span>{t("components.chat.logout")}</span>
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}
