import { useState } from "react";
import { useTranslation } from "react-i18next";
import type React from "react";
import type { IndexedFileSummary, PromptTemplate } from "@/types/api";
import type { UserIdentity } from "@/types/auth";
import { AgentWorkbench } from "@/pages/chat/components/AgentWorkbench";
import { DocumentsPanel } from "@/pages/chat/components/DocumentsPanel";
import { PdfWorkbench } from "@/pages/chat/components/PdfWorkbench";
import { PromptTemplates } from "@/pages/chat/components/PromptTemplates";

type AgentClassHint = "" | "general" | "cybersecurity" | "artificial_intelligence" | "pdf_text";

type AgentMode = {
  key: AgentClassHint;
  title: string;
  desc: string;
};

type Props = {
  agentClassHint: AgentClassHint;
  agentModes: AgentMode[];
  agentDistribution: Array<{ agent: string; count: number }>;
  pdfDocuments: IndexedFileSummary[];
  pdfNeedingReindex: IndexedFileSummary[];
  pdfTargetFile: string;
  documents: IndexedFileSummary[];
  docsLoading: boolean;
  uploading: boolean;
  uploadInfo: string;
  uploadProgress: number;
  uploadProgressText: string;
  uploadVisibility: "private" | "public";
  docDropActive: boolean;
  canUploadAndManageDocs: boolean;
  isAdmin: boolean;
  user: unknown;
  prompts: PromptTemplate[];
  promptsLoading: boolean;
  promptTitle: string;
  promptContent: string;
  editingPromptId: string | null;
  promptCheckInfo: string;
  fileInputRef: React.RefObject<HTMLInputElement>;
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
};

export function WorkbenchPanel({
  agentClassHint,
  agentModes,
  agentDistribution,
  pdfDocuments,
  pdfNeedingReindex,
  pdfTargetFile,
  documents,
  docsLoading,
  uploading,
  uploadInfo,
  uploadProgress,
  uploadProgressText,
  uploadVisibility,
  docDropActive,
  canUploadAndManageDocs,
  isAdmin,
  user,
  prompts,
  promptsLoading,
  promptTitle,
  promptContent,
  editingPromptId,
  promptCheckInfo,
  fileInputRef,
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
}: Props) {
  const { t } = useTranslation();
  const [toolsCollapsed, setToolsCollapsed] = useState({
    agents: false,
    pdf: false,
    docs: true,
    prompts: true,
  });

  const allToolsCollapsed = Object.values(toolsCollapsed).every(Boolean);
  const indexedCount = documents.length;
  const indexingCount = documents.filter((doc) => ["pending", "indexing"].includes(String(doc.indexing_status || ""))).length;
  const readyCount = documents.filter((doc) => String(doc.indexing_status || "ready") === "ready").length;
  const failedCount = documents.filter((doc) => String(doc.indexing_status || "") === "failed").length;
  const moduleStatus = {
    agents: agentClassHint ? t("components.workbench.locked") : t("components.workbench.auto"),
    pdf: t("components.workbench.files", { count: pdfDocuments.length }),
    docs: t("components.workbench.docs", { count: documents.length }),
    prompts: t("components.workbench.saved", { count: prompts.length }),
  };

  const toggleToolSection = (key: keyof typeof toolsCollapsed) => {
    setToolsCollapsed((current) => ({ ...current, [key]: !current[key] }));
  };

  const toggleAllTools = () => {
    setToolsCollapsed({
      agents: !allToolsCollapsed,
      pdf: !allToolsCollapsed,
      docs: !allToolsCollapsed,
      prompts: !allToolsCollapsed,
    });
  };

  return (
    <div className="sidebar-tools">
      <div className="sidebar-group-title sidebar-group-title-with-action">
        <span>{t("components.workbench.workbench")}</span>
        <button type="button" className="sidebar-group-action" onClick={toggleAllTools}>
          {allToolsCollapsed ? t("components.workbench.expandAll") : t("components.workbench.collapseAll")}
        </button>
      </div>

      <section className="panel sidebar-module">
        <button type="button" className="sidebar-module-toggle" onClick={() => toggleToolSection("agents")}>
          <div className="sidebar-module-copy">
            <strong>{t("components.workbench.agentWorkbench")}</strong>
            <small>{t("components.workbench.agentWorkbenchDesc")}</small>
          </div>
          <span className={`sidebar-module-status ${agentClassHint ? "status-locked" : "status-auto"}`}>
            {moduleStatus.agents}
          </span>
        </button>
        {!toolsCollapsed.agents && (
          <div className="sidebar-module-body">
            <AgentWorkbench
              agentClassHint={agentClassHint}
              agentModes={agentModes}
              agentDistribution={agentDistribution}
              onSwitchAgentMode={onSwitchAgentMode}
            />
          </div>
        )}
      </section>

      <section className="panel sidebar-module">
        <button type="button" className="sidebar-module-toggle" onClick={() => toggleToolSection("pdf")}>
          <div className="sidebar-module-copy">
            <strong>{t("components.workbench.pdfWorkbench")}</strong>
            <small>{t("components.workbench.pdfWorkbenchDesc")}</small>
          </div>
          <span className="sidebar-module-status status-files">{moduleStatus.pdf}</span>
        </button>
        {!toolsCollapsed.pdf && (
          <div className="sidebar-module-body">
            <PdfWorkbench
              pdfDocuments={pdfDocuments}
              pdfNeedingReindex={pdfNeedingReindex}
              pdfTargetFile={pdfTargetFile}
              onPdfTargetFileChange={onPdfTargetFileChange}
              onSwitchAgentMode={onSwitchAgentMode}
              onDraftQuestion={onDraftQuestion}
            />
          </div>
        )}
      </section>

      <section className="panel sidebar-module">
        <button type="button" className="sidebar-module-toggle" onClick={() => toggleToolSection("docs")}>
          <div className="sidebar-module-copy">
            <strong>{t("components.workbench.knowledgeBase")}</strong>
            <small>{t("components.workbench.knowledgeBaseDesc")}</small>
          </div>
          <span className="sidebar-module-status status-docs">{moduleStatus.docs}</span>
        </button>
        {!toolsCollapsed.docs && (
          <div className="sidebar-module-body">
            <div className="sidebar-kb-metrics">
              <div className="sidebar-kb-card">
                <span>{t("components.workbench.indexed")}</span>
                <strong>{indexedCount}</strong>
              </div>
              <div className="sidebar-kb-card">
                <span>{t("components.workbench.pending")}</span>
                <strong>{indexingCount}</strong>
              </div>
              <div className="sidebar-kb-card">
                <span>Ready</span>
                <strong>{readyCount}</strong>
              </div>
              <div className="sidebar-kb-card">
                <span>Failed</span>
                <strong>{failedCount}</strong>
              </div>
            </div>
            <DocumentsPanel
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
              user={user as UserIdentity | null}
              fileInputRef={fileInputRef}
              onRefreshDocuments={onRefreshDocuments}
              onUploadVisibilityChange={onUploadVisibilityChange}
              onMainUploadChange={onMainUploadChange}
              onDocsDrop={onDocsDrop}
              onDocDropActiveChange={onDocDropActiveChange}
              onReindexDocument={onReindexDocument}
              onDeleteDocument={onDeleteDocument}
            />
          </div>
        )}
      </section>

      <section className="panel sidebar-module">
        <button type="button" className="sidebar-module-toggle" onClick={() => toggleToolSection("prompts")}>
          <div className="sidebar-module-copy">
            <strong>{t("components.workbench.promptLibrary")}</strong>
            <small>{t("components.workbench.promptLibraryDesc")}</small>
          </div>
          <span className="sidebar-module-status status-saved">{moduleStatus.prompts}</span>
        </button>
        {!toolsCollapsed.prompts && (
          <div className="sidebar-module-body">
            <PromptTemplates
              prompts={prompts}
              promptsLoading={promptsLoading}
              promptTitle={promptTitle}
              promptContent={promptContent}
              editingPromptId={editingPromptId}
              promptCheckInfo={promptCheckInfo}
              onRefreshPrompts={onRefreshPrompts}
              onPromptTitleChange={onPromptTitleChange}
              onPromptContentChange={onPromptContentChange}
              onCheckPrompt={onCheckPrompt}
              onSavePrompt={onSavePrompt}
              onUsePrompt={onUsePrompt}
              onEditPrompt={onEditPrompt}
              onDeletePrompt={onDeletePrompt}
            />
          </div>
        )}
      </section>
    </div>
  );
}
