# Frontend Audit Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close out the 3 remaining partial-fix items from the prior QueryMind frontend audit: (1) the Zustand chat store still causes cross-cutting re-renders because `ChatPage` subscribes to the entire store and threads every field through props, (2) native `window.confirm`/`window.prompt` dialogs still bypass the app's own dialog UI, and (3) `FileUploadErrorBoundary` is dead code that isn't mounted anywhere.

**Architecture:** Part 1 moves ownership of high-churn store fields (typed-into-every-keystroke fields like `question`, `promptTitle`, and per-tick fields like `uploadProgress`) out of `ChatPage`'s monolithic selector and into the specific leaf components that actually render them (`ChatComposer`, `ChatSidebar`), using individual/grouped Zustand selectors. `ChatPage` keeps only the slice it needs for its own orchestration logic (session/message CRUD, computed permissions, effects) and reads stable action setters via `useChatStore.getState()` instead of subscribing to their values. Part 2 introduces a Promise-based `usePromptDialog` sibling to a Promise-ified `useConfirmDialog` (the latter already exists but is unused dead code), so every `window.confirm`/`window.prompt` call site converts with a minimal `await`-based diff instead of a callback-driven rewrite. Part 3 deletes `FileUploadErrorBoundary` after confirming no upload-related component has genuine render-time throw risk.

**Tech Stack:** React 18 + TypeScript + Vite, Zustand (`useChatStore`, `useAdminStore`), react-i18next, no test runner configured for `frontend/`.

## Global Constraints

- No test suite exists in this repo (`tests/` was cleared ahead of the v0.7 rewrite; this applies to backend, but `frontend/` also has no test runner configured). Every task's verification step is `npx tsc -b --force` (type check) run from `frontend/`, plus `npm run build` at the end of each Part, plus a manual dev-server check where noted. There is no red/green test step in this plan — treat "make the change" + "typecheck clean" as the task's pass condition.
- Do not add new npm dependencies. Build `PromptDialog`/`usePromptDialog` using the same patterns already in the repo (`ConfirmDialog`/`useConfirmDialog`, `styles/components/confirm-dialog.css`).
- Reuse existing i18n keys wherever the English/Chinese strings already say the right thing (verified present in both `frontend/src/i18n/locales/en.json` and `zh.json` during research for this plan). Do not add new i18n keys unless a task explicitly says so.
- No comments unless documenting a non-obvious constraint; match existing code style (no default exports, named function components, `t()` from `useTranslation()`).
- Scope for Part 1 is the **chat** page only (`ChatPage.tsx` and its named children). `useAdminState.ts`/`useAdminStore.ts` have the same monolithic-selector shape, but the task instructions only named `useAdminState.ts`/`useAdminStore.ts` as background context, not as components to refactor — `AdminPage.tsx` and its section components are out of scope for Part 1. Flag this to the user after the plan lands; do not silently expand scope.
- Part 1 deliberately does **not** add `React.memo`/`useCallback` to `ChatSidebar`/`ChatComposer`/`ChatMessages`/`ChatTopbar`. Reason (confirmed by reading `useChatActions.ts`, `useChatHelpers.ts`, `useFileUpload.ts`, `useMessageActions.ts`, `useClarification.ts`): every handler passed into these components is a fresh closure returned by a hook that runs unmemoized on every `ChatPage` render, so `React.memo` would be defeated immediately and only add complexity without benefit. The actual fix is at the subscription source: once `ChatPage` no longer subscribes to a field, `ChatPage` simply does not re-render when that field changes, so there is no cascade to prevent in the first place. `ChatMessages`/`ChatTopbar` need no field-ownership changes at all (see Task 6) because they don't hold any store slice `ChatPage` doesn't already need for its own logic.

---

## Part 1: Zustand direct-subscription refactor (chat page)

### Task 1: Rewrite `useChatPageState` to stop subscribing to the whole store

**Files:**
- Modify: `frontend/src/pages/chat/hooks/useChatPageState.ts`

**Interfaces:**
- Produces: `useChatPageState()` returns the same top-level shape as before (same key names), but `question`, `runStatus`, `agentClassHint`, `docsLoading`, `uploading`, `uploadInfo`, `uploadProgress`, `uploadProgressText`, `docDropActive`, `composerDropActive`, `prompts`, `promptsLoading`, `promptTitle`, `promptContent`, `editingPromptId`, `promptCheckInfo`, `error`, `sessionLoading`, `busySessionId`, `isCreatingSession` are **no longer returned as values** — only their setters are. `sidebarOpen`, `sidebarCollapsed`, `sessions`, `currentSessionId`, `messages`, `isSending`, `pdfTargetFile`, `documents`, `uploadVisibility`, `toasts`, `settingsOpen` are still returned as reactive values (ChatPage's own JSX/effects/business logic need them). `fileInputRef`, `chatUploadInputRef`, `questionRef`, `chatScrollRef` are unchanged (still plain `useRef`s, never touched the store).

- [ ] **Step 1: Replace the file contents**

```ts
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
```

- [ ] **Step 2: Typecheck**

Run (from `frontend/`): `npx tsc -b --force`
Expected: New errors only in `ChatPage.tsx` (still destructuring removed fields like `question`) and `useChatHelpers.ts` call site — these are fixed in later tasks. No errors in `useChatPageState.ts` itself.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/chat/hooks/useChatPageState.ts
git commit -m "refactor(chat): stop subscribing to the whole chat store in useChatPageState"
```

---

### Task 2: Make `ChatComposer` own `question`/`runStatus`/`composerDropActive` directly

**Files:**
- Modify: `frontend/src/pages/chat/components/ChatComposer.tsx`

**Interfaces:**
- Consumes: `useChatStore` from `@/stores/useChatStore` (fields: `question: string`, `setQuestion: (v: string) => void`, `runStatus: string`, `composerDropActive: boolean`), `useTextareaAutoResize` from `@/pages/chat/hooks/useTextareaAutoResize` (unchanged signature `{ ref, value }`).
- Produces: `ChatComposer` no longer accepts `question`, `onQuestionChange`, `runStatus`, `composerDropActive`, `error`, `onClearQuestion`, `onPromptPick` as props. `questionRef` and `chatUploadInputRef` remain props (shared DOM refs also used by `useDocumentActions` in `ChatPage` to reset `.value` after upload — they cannot become fully internal).

- [ ] **Step 1: Replace the file contents**

```tsx
import type React from "react";
import { useTranslation } from "react-i18next";
import { QuickActions } from "@/pages/chat/components/QuickActions";
import { AnimatedButtonLite as AnimatedButton } from "@/components/animations/AnimatedButtonLite";
import { useChatStore } from "@/stores/useChatStore";
import { useTextareaAutoResize } from "@/pages/chat/hooks/useTextareaAutoResize";

type Props = {
  questionRef: React.MutableRefObject<HTMLTextAreaElement | null>;
  chatUploadInputRef: React.MutableRefObject<HTMLInputElement | null>;
  isSending: boolean;
  quickPrompts: string[];
  onAsk: () => Promise<void>;
  onStop: () => void;
  onComposerDragEnter: (evt: React.DragEvent<HTMLElement>) => void;
  onComposerDragOver: (evt: React.DragEvent<HTMLElement>) => void;
  onComposerDragLeave: (evt: React.DragEvent<HTMLElement>) => void;
  onComposerDrop: (evt: React.DragEvent<HTMLElement>) => Promise<void>;
  onChatUploadChange: (evt: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
};

export function ChatComposer({
  questionRef,
  chatUploadInputRef,
  isSending,
  quickPrompts,
  onAsk,
  onStop,
  onComposerDragEnter,
  onComposerDragOver,
  onComposerDragLeave,
  onComposerDrop,
  onChatUploadChange,
}: Props) {
  const { t } = useTranslation();
  const question = useChatStore((s) => s.question);
  const setQuestion = useChatStore((s) => s.setQuestion);
  const runStatus = useChatStore((s) => s.runStatus);
  const composerDropActive = useChatStore((s) => s.composerDropActive);
  useTextareaAutoResize({ ref: questionRef, value: question });
  const modeHint = t("components.chat.modeHint.advancedReasoning");

  return (
    <section
      className={`panel composer-panel ${composerDropActive ? "dragover" : ""}`}
      onDragEnter={onComposerDragEnter}
      onDragOver={onComposerDragOver}
      onDragLeave={onComposerDragLeave}
      onDrop={(event) => void onComposerDrop(event)}
    >
      <div className="composer-main">
        <div className="composer-heading-row">
          <label className="composer-label">{t("components.chat.composerLabel")}</label>
          <span className="composer-drop-hint">{t("components.chat.composerDropHint")}</span>
        </div>

        <div className="composer-input-wrapper">
          <textarea
            ref={questionRef}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={t("components.chat.composerPlaceholder")}
            rows={3}
            aria-label={t("components.chat.questionInput")}
            aria-describedby="composer-hint"
            onKeyDown={(event) => {
              if (event.key === "Escape" && isSending) {
                event.preventDefault();
                onStop();
                return;
              }
              if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                event.preventDefault();
                void onAsk();
              }
            }}
          />
          <div className="composer-input-actions">
            <label className="composer-upload-btn" title={t("components.chat.uploadFiles")}>
              <span aria-hidden="true">+</span>
              <input
                ref={chatUploadInputRef}
                type="file"
                multiple
                accept=".pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp"
                style={{ display: "none" }}
                onChange={(event) => void onChatUploadChange(event)}
                aria-label={t("components.chat.uploadFilesAria")}
              />
            </label>
          </div>
        </div>
      </div>

      <div className="composer-controls">
        <AnimatedButton
          onClick={onAsk}
          state={isSending ? 'loading' : 'idle'}
          variant="primary"
          size="large"
          disabled={isSending}
          className="composer-primary-btn"
        >
          <span className="btn-text">{isSending ? t("components.chat.analyzing") : t("components.chat.startAnalysis")}</span>
          {!isSending && <span className="btn-shortcut">Ctrl / Cmd + Enter</span>}
        </AnimatedButton>
      </div>

      <div className="composer-hint" id="composer-hint">
        {modeHint}
      </div>

      <QuickActions
        quickPrompts={quickPrompts}
        question={question}
        isSending={isSending}
        onPromptPick={setQuestion}
        onStop={onStop}
        onClearQuestion={() => setQuestion("")}
      />

      {runStatus && <div className="status">{runStatus}</div>}
    </section>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc -b --force`
Expected: Errors remain only where `ChatPage.tsx` still passes the now-removed props (fixed in Task 5).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/chat/components/ChatComposer.tsx
git commit -m "refactor(chat): ChatComposer subscribes to question/runStatus/composerDropActive directly"
```

---

### Task 3: Make `ChatSidebar` own its full session/document/prompt display slice directly

**Files:**
- Modify: `frontend/src/pages/chat/components/ChatSidebar.tsx`

**Interfaces:**
- Consumes: `useChatStore` + `useShallow` from `zustand/react/shallow` for a grouped selector.
- Produces: `ChatSidebar`'s `Props` drops every field that lives in `useChatStore` (`sidebarOpen`, `sidebarCollapsed`, `sessions`, `sessionLoading`, `currentSessionId`, `busySessionId`, `isCreatingSession`, `agentClassHint`, `pdfTargetFile`, `documents`, `docsLoading`, `uploading`, `uploadInfo`, `uploadProgress`, `uploadProgressText`, `uploadVisibility`, `docDropActive`, `prompts`, `promptsLoading`, `promptTitle`, `promptContent`, `editingPromptId`, `promptCheckInfo`). Computed/derived props (`agentModes`, `agentDistribution`, `pdfDocuments`, `pdfNeedingReindex`, `canUploadAndManageDocs`, `isAdmin`, `user`), the shared `fileInputRef`, and all `onXxx` handler callbacks are unchanged.

- [ ] **Step 1: Replace the file contents**

```tsx
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
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc -b --force`
Expected: Remaining errors only in `ChatPage.tsx` (fixed in Task 5).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/chat/components/ChatSidebar.tsx
git commit -m "refactor(chat): ChatSidebar subscribes to its session/document/prompt slice directly"
```

---

### Task 4: Update `useChatHelpers` to read prompt fields at call time instead of via props

**Files:**
- Modify: `frontend/src/pages/chat/hooks/useChatHelpers.ts`

**Interfaces:**
- Consumes: `useChatStore.getState()` for `promptTitle`, `promptContent`, `editingPromptId` (read fresh at call time inside `savePrompt`/`checkPrompt`/`deletePrompt`, since these are no longer available reactively in `ChatPage`).
- Produces: `UseChatHelpersParams` drops `promptTitle`, `promptContent`, `editingPromptId`. Returned function names/signatures (`closeSidebar`, `switchAgentMode`, `draftPdfQuestion`, `deleteDocument`, `reindexDocument`, `savePrompt`, `checkPrompt`, `deletePrompt`) are unchanged.

- [ ] **Step 1: Replace the file contents**

```ts
import { useCallback } from "react";
import type { IndexedFileSummary, PromptTemplate } from "@/types/api";
import type { AgentClassHint } from "@/pages/chat/constants";
import { isMobile } from "@/pages/chat/constants";
import { useChatStore } from "@/stores/useChatStore";

interface ChatActions {
  notify: (message: string, type: "success" | "info" | "warn" | "error") => void;
  deleteDocument: (item: IndexedFileSummary, removeFile: boolean) => Promise<void>;
  reindexDocument: (item: IndexedFileSummary) => Promise<void>;
  savePrompt: (title: string, content: string, editingId: string | null) => Promise<void>;
  checkPrompt: (title: string, content: string, useReasoning: boolean) => Promise<void>;
  deletePrompt: (item: PromptTemplate, editingId: string | null) => Promise<void>;
}

interface UseChatHelpersParams {
  canUploadAndManageDocs: boolean;
  pdfDocuments: IndexedFileSummary[];
  pdfTargetFile: string;
  setSidebarOpen: (open: boolean) => void;
  setAgentClassHint: (hint: AgentClassHint) => void;
  setQuestion: (question: string) => void;
  questionRef: React.RefObject<HTMLTextAreaElement>;
  actions: ChatActions;
}

export function useChatHelpers({
  canUploadAndManageDocs,
  pdfDocuments,
  pdfTargetFile,
  setSidebarOpen,
  setAgentClassHint,
  setQuestion,
  questionRef,
  actions,
}: UseChatHelpersParams) {
  const closeSidebar = useCallback(() => {
    if (isMobile()) setSidebarOpen(false);
  }, [setSidebarOpen]);

  const switchAgentMode = useCallback(
    (next: AgentClassHint) => {
      setAgentClassHint(next);
      actions.notify(`Mode switched to ${next || "auto"}`, "success");
    },
    [setAgentClassHint, actions]
  );

  const draftPdfQuestion = useCallback(() => {
    if (!pdfDocuments.length) {
      actions.notify("No PDF/image docs available. Upload first.", "warn");
      return;
    }
    const target = pdfTargetFile || pdfDocuments[0]?.filename || "";
    if (!target) return;
    setAgentClassHint("pdf_text");
    setQuestion(`Read "${target}" and provide key points, major risks, and supporting evidence.`);
    questionRef.current?.focus();
    actions.notify("Drafted a PDF-focused question.", "success");
  }, [pdfDocuments, pdfTargetFile, setAgentClassHint, setQuestion, questionRef, actions]);

  const deleteDocument = useCallback(
    async (item: IndexedFileSummary, removeFile: boolean) => {
      if (!canUploadAndManageDocs) {
        actions.notify("No document management permission", "warn");
        return;
      }
      await actions.deleteDocument(item, removeFile);
    },
    [canUploadAndManageDocs, actions]
  );

  const reindexDocument = useCallback(
    async (item: IndexedFileSummary) => {
      if (!canUploadAndManageDocs) {
        actions.notify("No document management permission", "warn");
        return;
      }
      await actions.reindexDocument(item);
    },
    [canUploadAndManageDocs, actions]
  );

  const savePrompt = useCallback(async () => {
    const { promptTitle, promptContent, editingPromptId } = useChatStore.getState();
    await actions.savePrompt(promptTitle, promptContent, editingPromptId);
  }, [actions]);

  const checkPrompt = useCallback(async () => {
    const { promptTitle, promptContent } = useChatStore.getState();
    await actions.checkPrompt(promptTitle, promptContent, true);
  }, [actions]);

  const deletePrompt = useCallback(
    async (item: PromptTemplate) => {
      const { editingPromptId } = useChatStore.getState();
      await actions.deletePrompt(item, editingPromptId);
    },
    [actions]
  );

  return {
    closeSidebar,
    switchAgentMode,
    draftPdfQuestion,
    deleteDocument,
    reindexDocument,
    savePrompt,
    checkPrompt,
    deletePrompt,
  };
}
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc -b --force`
Expected: Remaining errors only in `ChatPage.tsx`'s `useChatHelpers({...})` call site (fixed in Task 5).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/chat/hooks/useChatHelpers.ts
git commit -m "refactor(chat): useChatHelpers reads prompt fields from the store at call time"
```

---

### Task 5: Update `ChatPage.tsx` to match the new ownership boundaries

**Files:**
- Modify: `frontend/src/pages/ChatPage.tsx`

**Interfaces:**
- Consumes: `useChatStore` (imported fresh) for the single `useChatStore.getState().question` read inside `onAsk`.

- [ ] **Step 1: Add the `useChatStore` import**

```diff
 import { useEffect, useMemo, useState } from "react";
 import {
   AGENT_MODES,
   type AgentClassHint,
 } from "@/pages/chat/constants";
 import type { Props } from "@/pages/chat/types";
+import { useChatStore } from "@/stores/useChatStore";
```

- [ ] **Step 2: Trim the `useChatPageState()` destructure**

Replace the whole destructure block (currently `const { sidebarOpen, setSidebarOpen, ... } = useChatPageState();`) with:

```tsx
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
```

- [ ] **Step 3: Drop the `promptTitle`/`promptContent`/`editingPromptId` args from the `useChatHelpers` call**

```diff
   const helpers = useChatHelpers({
     canUploadAndManageDocs,
     pdfDocuments,
     pdfTargetFile,
-    promptTitle,
-    promptContent,
-    editingPromptId,
     setSidebarOpen,
     setAgentClassHint,
     setQuestion,
     questionRef,
     actions,
   });
```

- [ ] **Step 4: Remove the now-orphaned `useTextareaAutoResize` call and import**

```diff
-import { useTextareaAutoResize } from "@/pages/chat/hooks/useTextareaAutoResize";
 import { useAutoScroll } from "@/pages/chat/hooks/useAutoScroll";
```

```diff
   // Custom hooks for side effects
-  useTextareaAutoResize({ ref: questionRef, value: question });
   useAutoScroll({ ref: chatScrollRef, messages });
```

- [ ] **Step 5: Trim the `ChatSidebar` JSX to only the props it still accepts**

```tsx
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
```

- [ ] **Step 6: Trim the `ChatComposer` JSX and stop reading `question` reactively in `onAsk`**

```tsx
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
```

- [ ] **Step 7: Typecheck**

Run: `npx tsc -b --force`
Expected: Clean — 0 errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/ChatPage.tsx
git commit -m "refactor(chat): ChatPage stops threading question/prompt/upload fields through props"
```

---

### Task 6: Verify `ChatMessages`/`ChatTopbar` need no changes, then manually verify the fix

**Files:** none (verification-only task)

**Rationale to record:** `ChatMessages` needs `messages` reactively — but `ChatPage` already needs `messages` for `smartQuickPrompts` (`useMemo(() => generateSmartPrompts(messages), [messages])`) and for `SessionManagementModal`, so `ChatPage` was never going to stop subscribing to it; moving the subscription into `ChatMessages` would not reduce anything. `ChatTopbar`/`TopbarMenu` consume no Zustand chat-store field at all — `topbarHidden`/`sectionsHidden` come from `useSectionToggle`/`useTopbarToggle` (local component state), and `user` is an auth prop. Both components were already insulated from the reported bug once `ChatPage` stopped subscribing to `question`/`promptTitle`/etc. (Task 1): `ChatPage` simply no longer re-renders for those changes, so there's no cascade reaching either component.

- [ ] **Step 1: Typecheck the whole frontend**

Run (from `frontend/`): `npx tsc -b --force`
Expected: 0 errors.

- [ ] **Step 2: Production build**

Run: `npm run build`
Expected: Build succeeds.

- [ ] **Step 3: Manual dev-server check**

Run: `npm run dev`, open the chat page in a browser with React DevTools "Highlight updates when components render" enabled.
- Type in the composer textarea: only `ChatComposer` (and its `QuickActions` child) should flash — the session list, message list, and sidebar workbench must stay unlit.
- Type in a prompt-template title/content field (sidebar → Prompt Library): only `ChatSidebar`'s subtree should flash — `ChatComposer`/`ChatMessages` must stay unlit.
- Upload a file and watch the progress bar tick: only `ChatSidebar` should flash repeatedly, not `ChatComposer`/`ChatMessages`.
- Sanity-check core flows still work end-to-end: create/rename/pin/delete a session, send a question and see the answer stream in, switch agent mode, save/check/use/delete a prompt template, upload/reindex/delete a document, select a PDF target file and draft a question.

- [ ] **Step 4: Commit** (only if Step 3 surfaced fixes; otherwise this task has nothing to commit)

---

## Part 2: Replace `window.confirm`/`window.prompt` with in-app dialogs

Scope confirmed by search: `useDocumentActions.ts` (1 `window.confirm`), `usePromptActions.ts` (1 `window.confirm`), `useMessageOperations.ts` (1 `window.prompt`), `MessageCard.tsx` (1 `window.confirm` — **found during this plan's research, not in the original task list, but the same category of issue and trivial to include**), and `userActions.ts` (6 `window.prompt`). No other `window.confirm`/`window.prompt` call sites exist in `frontend/src`.

### Task 7: Build `PromptDialog`, the text-input counterpart to `ConfirmDialog`

**Files:**
- Create: `frontend/src/components/PromptDialog.tsx`
- Modify: `frontend/src/styles/components/confirm-dialog.css`

**Interfaces:**
- Produces: `PromptDialog` component — `{ isOpen, title, message, defaultValue?, placeholder?, confirmText?, cancelText?, multiline?, inputType?: "text" | "password", onConfirm: (value: string) => void, onCancel: () => void }`.

- [ ] **Step 1: Create `PromptDialog.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import type React from "react";
import { useTranslation } from "react-i18next";

type Props = {
  isOpen: boolean;
  title: string;
  message: string;
  defaultValue?: string;
  placeholder?: string;
  confirmText?: string;
  cancelText?: string;
  multiline?: boolean;
  inputType?: "text" | "password";
  onConfirm: (value: string) => void;
  onCancel: () => void;
};

export function PromptDialog({
  isOpen,
  title,
  message,
  defaultValue = "",
  placeholder,
  confirmText,
  cancelText,
  multiline = false,
  inputType = "text",
  onConfirm,
  onCancel,
}: Props) {
  const { t } = useTranslation();
  const [value, setValue] = useState(defaultValue);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setValue(defaultValue);
    window.setTimeout(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    }, 0);
  }, [isOpen, defaultValue]);

  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onCancel();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  return (
    <div className="confirm-dialog-overlay" onClick={onCancel}>
      <div className="confirm-dialog prompt-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="confirm-dialog-header">
          <h3 className="confirm-dialog-title">{title}</h3>
        </div>
        <div className="confirm-dialog-body">
          <p className="confirm-dialog-message">{message}</p>
          {multiline ? (
            <textarea
              ref={inputRef as React.RefObject<HTMLTextAreaElement>}
              className="prompt-dialog-input prompt-dialog-textarea"
              value={value}
              placeholder={placeholder}
              rows={5}
              onChange={(event) => setValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                  event.preventDefault();
                  onConfirm(value);
                }
              }}
            />
          ) : (
            <input
              ref={inputRef as React.RefObject<HTMLInputElement>}
              type={inputType}
              className="prompt-dialog-input"
              value={value}
              placeholder={placeholder}
              onChange={(event) => setValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  onConfirm(value);
                }
              }}
            />
          )}
        </div>
        <div className="confirm-dialog-footer">
          <button
            type="button"
            className="confirm-dialog-btn confirm-dialog-btn-cancel"
            onClick={onCancel}
          >
            {cancelText || t("common.cancel")}
          </button>
          <button
            type="button"
            className="confirm-dialog-btn confirm-dialog-btn-confirm"
            onClick={() => onConfirm(value)}
          >
            {confirmText || t("common.confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Append dialog input styles**

Append to the end of `frontend/src/styles/components/confirm-dialog.css`:

```css

/* ============================================
   Prompt Dialog (text-input variant)
   ============================================ */

.prompt-dialog-input {
  width: 100%;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-medium);
  background: var(--surface);
  color: var(--text-primary);
  font-size: 14px;
  font-family: inherit;
}

.prompt-dialog-input:focus {
  outline: none;
  border-color: var(--accent);
}

.prompt-dialog-textarea {
  resize: vertical;
  min-height: 100px;
}
```

- [ ] **Step 3: Typecheck**

Run: `npx tsc -b --force`
Expected: 0 new errors (component isn't wired up yet, so it's dead code at this point — that's expected and temporary).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/PromptDialog.tsx frontend/src/styles/components/confirm-dialog.css
git commit -m "feat(frontend): add PromptDialog, a text-input counterpart to ConfirmDialog"
```

---

### Task 8: Make `useConfirmDialog` Promise-based and add `usePromptDialog`

**Files:**
- Modify: `frontend/src/hooks/useConfirmDialog.ts`
- Create: `frontend/src/hooks/usePromptDialog.ts`

**Interfaces:**
- Produces: `useConfirmDialog()` → `{ isOpen, options, confirm: (opts: ConfirmDialogOptions) => Promise<boolean>, handleConfirm: () => void, handleCancel: () => void }`. This is a breaking API change from the current callback-based `confirm({ onConfirm, onCancel })`, but the hook is confirmed unused anywhere in the codebase (`SessionList.tsx` manages its own local state instead), so nothing else needs to change.
- Produces: `usePromptDialog()` → `{ isOpen, options, promptInput: (opts: PromptDialogOptions) => Promise<string | null>, handleConfirm: (value: string) => void, handleCancel: () => void }`.

- [ ] **Step 1: Replace `useConfirmDialog.ts`**

```ts
import { useCallback, useRef, useState } from "react";

export interface ConfirmDialogOptions {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isDanger?: boolean;
}

export function useConfirmDialog() {
  const [isOpen, setIsOpen] = useState(false);
  const [options, setOptions] = useState<ConfirmDialogOptions | null>(null);
  const resolverRef = useRef<((confirmed: boolean) => void) | null>(null);

  const confirm = useCallback((opts: ConfirmDialogOptions): Promise<boolean> => {
    setOptions(opts);
    setIsOpen(true);
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve;
    });
  }, []);

  const handleConfirm = useCallback(() => {
    setIsOpen(false);
    resolverRef.current?.(true);
    resolverRef.current = null;
  }, []);

  const handleCancel = useCallback(() => {
    setIsOpen(false);
    resolverRef.current?.(false);
    resolverRef.current = null;
  }, []);

  return {
    isOpen,
    options,
    confirm,
    handleConfirm,
    handleCancel,
  };
}
```

- [ ] **Step 2: Create `usePromptDialog.ts`**

```ts
import { useCallback, useRef, useState } from "react";

export interface PromptDialogOptions {
  title?: string;
  message: string;
  defaultValue?: string;
  placeholder?: string;
  confirmText?: string;
  cancelText?: string;
  multiline?: boolean;
  inputType?: "text" | "password";
}

export function usePromptDialog() {
  const [isOpen, setIsOpen] = useState(false);
  const [options, setOptions] = useState<PromptDialogOptions | null>(null);
  const resolverRef = useRef<((value: string | null) => void) | null>(null);

  const promptInput = useCallback((opts: PromptDialogOptions): Promise<string | null> => {
    setOptions(opts);
    setIsOpen(true);
    return new Promise<string | null>((resolve) => {
      resolverRef.current = resolve;
    });
  }, []);

  const handleConfirm = useCallback((value: string) => {
    setIsOpen(false);
    resolverRef.current?.(value);
    resolverRef.current = null;
  }, []);

  const handleCancel = useCallback(() => {
    setIsOpen(false);
    resolverRef.current?.(null);
    resolverRef.current = null;
  }, []);

  return {
    isOpen,
    options,
    promptInput,
    handleConfirm,
    handleCancel,
  };
}
```

- [ ] **Step 3: Typecheck**

Run: `npx tsc -b --force`
Expected: 0 errors (`useConfirmDialog` is still unused; `usePromptDialog` is new and unused — both dead code at this point, wired up next).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useConfirmDialog.ts frontend/src/hooks/usePromptDialog.ts
git commit -m "refactor(frontend): make useConfirmDialog Promise-based; add usePromptDialog"
```

---

### Task 9: Wire the dialogs into chat's document/prompt/message actions

**Files:**
- Modify: `frontend/src/pages/chat/hooks/useDocumentActions.ts`
- Modify: `frontend/src/pages/chat/hooks/usePromptActions.ts`
- Modify: `frontend/src/pages/chat/hooks/useMessageOperations.ts`
- Modify: `frontend/src/pages/chat/hooks/useChatActions.ts`
- Modify: `frontend/src/pages/ChatPage.tsx`

**Interfaces:**
- Consumes: `confirm: (opts: ConfirmDialogOptions) => Promise<boolean>` and `promptInput: (opts: PromptDialogOptions) => Promise<string | null>`, threaded from `ChatPage` → `useChatActions` → `useDocumentActions`/`usePromptActions`/`useMessageOperations`.

- [ ] **Step 1: `useDocumentActions.ts` — add `confirm` param, convert `deleteDocument`**

```diff
 interface UseDocumentActionsParams {
   setDocuments: Dispatch<SetStateAction<IndexedFileSummary[]>>;
   setDocsLoading: Dispatch<SetStateAction<boolean>>;
   setUploading: Dispatch<SetStateAction<boolean>>;
   setUploadInfo: Dispatch<SetStateAction<string>>;
   setUploadProgress: Dispatch<SetStateAction<number>>;
   setUploadProgressText: Dispatch<SetStateAction<string>>;
   setAgentClassHint: Dispatch<SetStateAction<AgentClassHint>>;
   setError: Dispatch<SetStateAction<string>>;
   uploadVisibility: "private" | "public";
   fileInputRef: React.RefObject<HTMLInputElement | null>;
   chatUploadInputRef: React.RefObject<HTMLInputElement | null>;
   notify: (text: string, kind?: "info" | "success" | "warn" | "error", ttl?: number) => void;
   handleApiError: (e: unknown, fallback: string) => Promise<void>;
+  confirm: (opts: { message: string; title?: string; isDanger?: boolean }) => Promise<boolean>;
 }
```

```diff
   const deleteDocument = async (item: IndexedFileSummary, removeFile: boolean) => {
     const verb = removeFile
       ? t("components.workbench.deleteFileAndIndexVerb")
       : t("components.workbench.deleteIndexVerb");
-    if (!window.confirm(t("components.workbench.deleteDocConfirm", { verb, filename: item.filename }))) return;
+    const confirmed = await confirm({
+      message: t("components.workbench.deleteDocConfirm", { verb, filename: item.filename }),
+      isDanger: true,
+    });
+    if (!confirmed) return;
     try {
```

Also update the params destructure at the top of the function:

```diff
   const {
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
+    confirm,
   } = params;
```

- [ ] **Step 2: `usePromptActions.ts` — add `confirm` param, convert `deletePrompt`**

```diff
 interface UsePromptActionsParams {
   setPrompts: Dispatch<SetStateAction<PromptTemplate[]>>;
   setPromptsLoading: Dispatch<SetStateAction<boolean>>;
   setEditingPromptId: Dispatch<SetStateAction<string | null>>;
   setPromptTitle: Dispatch<SetStateAction<string>>;
   setPromptContent: Dispatch<SetStateAction<string>>;
   setPromptCheckInfo: Dispatch<SetStateAction<string>>;
   setAgentClassHint: Dispatch<SetStateAction<AgentClassHint>>;
   setError: Dispatch<SetStateAction<string>>;
   notify: (text: string, kind?: Toast["kind"], ttl?: number) => void;
   handleApiError: (e: unknown, fallback: string) => Promise<void>;
+  confirm: (opts: { message: string; title?: string; isDanger?: boolean }) => Promise<boolean>;
 }
```

```diff
   const deletePrompt = async (item: PromptTemplate, editingPromptId: string | null) => {
     // Sanitize title for display in confirmation dialog
     const sanitizedTitle = sanitizeString(item.title);
-    if (!window.confirm(t("components.workbench.deleteTemplateConfirm", { title: sanitizedTitle }))) return;
+    const confirmed = await confirm({
+      message: t("components.workbench.deleteTemplateConfirm", { title: sanitizedTitle }),
+      isDanger: true,
+    });
+    if (!confirmed) return;
 
     try {
```

Also update the params destructure at the top of the function:

```diff
   const { t } = useTranslation();
   const {
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
+    confirm,
   } = params;
```

- [ ] **Step 3: `useMessageOperations.ts` — add `promptInput` param, convert `editMessage`**

```diff
 interface UseMessageOperationsParams {
   currentSessionId: string | null;
   setMessages: Dispatch<SetStateAction<SessionMessage[]>>;
   notify: (text: string, kind?: Toast["kind"], ttl?: number) => void;
   handleApiError: (e: unknown, fallback: string) => Promise<void>;
   refreshSessions: (preferSelectFirst?: boolean, silent?: boolean) => Promise<SessionSummary[]>;
+  promptInput: (opts: { message: string; title?: string; defaultValue?: string; multiline?: boolean }) => Promise<string | null>;
 }
```

```diff
   const {
     currentSessionId,
     setMessages,
     notify,
     handleApiError,
     refreshSessions,
+    promptInput,
   } = params;

   const editMessage = async (msg: SessionMessage) => {
     if (!currentSessionId || !msg.message_id) return;
-    const next = window.prompt(t("components.messages.editPromptTitle"), msg.content || "");
+    const next = await promptInput({
+      title: t("components.messages.edit"),
+      message: t("components.messages.editPromptTitle"),
+      defaultValue: msg.content || "",
+      multiline: true,
+    });
     if (next === null) return;
     try {
```

- [ ] **Step 4: `useChatActions.ts` — thread `confirm`/`promptInput` through**

```diff
 interface UseChatActionsParams {
   ...
   currentSessionId: string | null;
   sessions: SessionSummary[];
   messages: SessionMessage[];
   uploadVisibility: "private" | "public";
   fileInputRef: React.RefObject<HTMLInputElement | null>;
   chatUploadInputRef: React.RefObject<HTMLInputElement | null>;
   onLogout: () => Promise<void>;
   closeSidebar: () => void;
+  confirm: (opts: { message: string; title?: string; isDanger?: boolean }) => Promise<boolean>;
+  promptInput: (opts: { message: string; title?: string; defaultValue?: string; multiline?: boolean }) => Promise<string | null>;
 }
```

```diff
   const {
     ...
     onLogout,
     closeSidebar,
+    confirm,
+    promptInput,
   } = params;
```

```diff
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
+    confirm,
   });
```

```diff
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
+    confirm,
   });
```

```diff
   const messageOperations = useMessageOperations({
     currentSessionId,
     setMessages,
     notify,
     handleApiError,
     refreshSessions: sessionActions.refreshSessions,
+    promptInput,
   });
```

- [ ] **Step 5: `ChatPage.tsx` — instantiate the dialogs, pass them into `useChatActions`, render both dialogs once**

Add imports:

```diff
 import { useChatStore } from "@/stores/useChatStore";
+import { ConfirmDialog } from "@/components/ConfirmDialog";
+import { PromptDialog } from "@/components/PromptDialog";
+import { useConfirmDialog } from "@/hooks/useConfirmDialog";
+import { usePromptDialog } from "@/hooks/usePromptDialog";
```

Instantiate near the top of the component body (after the `useChatPageState()` call):

```tsx
  const confirmDialog = useConfirmDialog();
  const promptDialog = usePromptDialog();
```

Thread into `useChatActions`:

```diff
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
+    confirm: confirmDialog.confirm,
+    promptInput: promptDialog.promptInput,
   });
```

Render both dialogs once, alongside the other modals near the end of the JSX (next to `<ApiSettings .../>`):

```tsx
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
```

- [ ] **Step 6: Typecheck**

Run: `npx tsc -b --force`
Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/chat/hooks/useDocumentActions.ts frontend/src/pages/chat/hooks/usePromptActions.ts frontend/src/pages/chat/hooks/useMessageOperations.ts frontend/src/pages/chat/hooks/useChatActions.ts frontend/src/pages/ChatPage.tsx
git commit -m "refactor(chat): replace window.confirm/window.prompt with ConfirmDialog/PromptDialog"
```

---

### Task 10: Convert `MessageCard`'s inline `window.confirm`

**Files:**
- Modify: `frontend/src/pages/chat/components/MessageCard.tsx`

- [ ] **Step 1: Add imports and a local confirm-dialog instance**

```diff
 import { useState } from "react";
 import { useTranslation } from "react-i18next";
 import type { SessionMessage } from "@/types/api";
 import { EMPTY_METADATA } from "@/pages/chat/constants";
 import { MarkdownBlock } from "@/pages/chat/components/MarkdownBlock";
 import { CollapsibleSection } from "@/pages/chat/components/CollapsibleSection";
 import { MetadataBadges } from "@/pages/chat/components/MetadataBadges";
 import { AnimatedButtonLite as AnimatedButton } from "@/components/animations/AnimatedButtonLite";
 import { ThinkingIndicator } from "@/pages/chat/components/ThinkingIndicator";
+import { ConfirmDialog } from "@/components/ConfirmDialog";
+import { useConfirmDialog } from "@/hooks/useConfirmDialog";
```

```diff
   const [processExpanded, setProcessExpanded] = useState(false);
+  const confirmDialog = useConfirmDialog();
```

- [ ] **Step 2: Convert the delete button's `onClick` and render the dialog**

```diff
             <AnimatedButton
               onClick={async () => {
                 const confirmMsg = message.role === "assistant"
                   ? t("components.messages.deleteAssistantConfirm")
                   : t("components.messages.deleteUserConfirm");
-                if (window.confirm(confirmMsg)) {
-                  await onRemoveMessage(message);
-                }
+                const confirmed = await confirmDialog.confirm({ message: confirmMsg, isDanger: true });
+                if (confirmed) {
+                  await onRemoveMessage(message);
+                }
               }}
               variant="danger"
               size="small"
               className="tiny-btn"
             >
               {t("components.messages.delete")}
             </AnimatedButton>
```

Wrap the component's return value in a fragment and add `<ConfirmDialog>` as a sibling of the top-level `<article>`:

```diff
   return (
+    <>
     <article
       className={`bubble ${isAssistant ? "assistant" : "user"}`}
       role="article"
       aria-label={isAssistant ? t("components.messages.assistantReply") : t("components.messages.userMessage")}
     >
       ...
     </article>
+    <ConfirmDialog
+      isOpen={confirmDialog.isOpen}
+      title={t("components.messages.delete")}
+      message={confirmDialog.options?.message || ""}
+      isDanger={confirmDialog.options?.isDanger}
+      onConfirm={confirmDialog.handleConfirm}
+      onCancel={confirmDialog.handleCancel}
+    />
+    </>
   );
 }
```

- [ ] **Step 3: Typecheck**

Run: `npx tsc -b --force`
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/chat/components/MessageCard.tsx
git commit -m "refactor(chat): MessageCard uses ConfirmDialog instead of window.confirm"
```

---

### Task 11: Wire `PromptDialog` into admin's `userActions.ts`

**Files:**
- Modify: `frontend/src/pages/admin/actions/types.ts`
- Modify: `frontend/src/pages/admin/actions/userActions.ts`
- Modify: `frontend/src/pages/AdminPage.tsx`

**Interfaces:**
- Consumes: `promptInput: (opts: { message: string; title?: string; defaultValue?: string; inputType?: "text" | "password" }) => Promise<string | null>`, added to `AdminActionsParams` and passed straight through by `AdminPage.tsx` (which already spreads the whole params object into `useAdminActions`, so `useAdminActions.ts` itself needs no change).

- [ ] **Step 1: Add `promptInput` to `AdminActionsParams`**

```diff
 export interface AdminActionsParams {
   users: AdminUserSummary[];
   ...
   isAdmin: boolean;
   onLogout: () => Promise<void>;
+  promptInput: (opts: { message: string; title?: string; defaultValue?: string; inputType?: "text" | "password" }) => Promise<string | null>;
   setUsers: (users: AdminUserSummary[] | ((prev: AdminUserSummary[]) => AdminUserSummary[])) => void;
   ...
 }
```

- [ ] **Step 2: Convert `userActions.ts`'s 6 `window.prompt` call sites**

```diff
 export function createUserActions(params: AdminActionsParams, errorHandler: ErrorHandler) {
   const {
     isAdmin,
     adminUsername,
     adminPassword,
     adminPassword2,
     adminApprovalToken,
     newAdminApprovalToken,
     adminTicketId,
     adminReason,
     editingUser,
     editBu,
     editDept,
     editType,
     editScope,
+    promptInput,
     setUsers,
```

```diff
   const addUserCredits = async (target: AdminUserSummary) => {
     if ((target.role || "").toLowerCase() === "admin") return;
-    const rawAmount = (window.prompt(t("admin.actions.creditsPrompt", { username: target.username })) || "").trim();
+    const raw = await promptInput({
+      title: t("admin.ui.addCredits"),
+      message: t("admin.actions.creditsPrompt", { username: target.username }),
+    });
+    const rawAmount = (raw || "").trim();
     if (!rawAmount) return;
```

```diff
   const resetAdminApprovalToken = async (target: AdminUserSummary) => {
     if ((target.role || "").toLowerCase() !== "admin") return;
-    const newToken = (
-      window.prompt(t("admin.actions.resetAdminTokenPrompt", { username: target.username })) || ""
-    ).trim();
+    const newTokenRaw = await promptInput({
+      title: t("admin.ui.resetToken"),
+      message: t("admin.actions.resetAdminTokenPrompt", { username: target.username }),
+      inputType: "password",
+    });
+    const newToken = (newTokenRaw || "").trim();
     if (!newToken || newToken.length < 12) return setError(t("admin.actions.newAdminTokenRequirements"));
-    const approvalToken = (window.prompt(t("admin.actions.yourApprovalTokenPrompt")) || "").trim();
-    const ticketId = (window.prompt(t("admin.actions.ticketIdPrompt")) || "").trim();
-    const reason = (window.prompt(t("admin.actions.reasonPrompt")) || "").trim();
+    const approvalTokenRaw = await promptInput({
+      title: t("admin.ui.resetToken"),
+      message: t("admin.actions.yourApprovalTokenPrompt"),
+      inputType: "password",
+    });
+    const approvalToken = (approvalTokenRaw || "").trim();
+    const ticketIdRaw = await promptInput({ title: t("admin.ui.resetToken"), message: t("admin.actions.ticketIdPrompt") });
+    const ticketId = (ticketIdRaw || "").trim();
+    const reasonRaw = await promptInput({ title: t("admin.ui.resetToken"), message: t("admin.actions.reasonPrompt") });
+    const reason = (reasonRaw || "").trim();
     if (!approvalToken || !ticketId || reason.length < 5) return setError(t("admin.actions.incompleteApprovalFields"));
     try {
```

```diff
   const resetUserPassword = async (target: AdminUserSummary) => {
-    const newPassword = (
-      window.prompt(t("admin.actions.resetPasswordPrompt", { username: target.username })) || ""
-    ).trim();
+    const newPasswordRaw = await promptInput({
+      title: t("admin.ui.resetPassword"),
+      message: t("admin.actions.resetPasswordPrompt", { username: target.username }),
+      inputType: "password",
+    });
+    const newPassword = (newPasswordRaw || "").trim();
     if (!newPassword) return;
-    const approvalToken = (window.prompt(t("admin.actions.yourApprovalTokenPrompt")) || "").trim();
-    const ticketId = (window.prompt(t("admin.actions.ticketIdPrompt")) || "").trim();
-    const reason = (window.prompt(t("admin.actions.resetReasonPrompt")) || "").trim();
+    const approvalTokenRaw = await promptInput({
+      title: t("admin.ui.resetPassword"),
+      message: t("admin.actions.yourApprovalTokenPrompt"),
+      inputType: "password",
+    });
+    const approvalToken = (approvalTokenRaw || "").trim();
+    const ticketIdRaw = await promptInput({ title: t("admin.ui.resetPassword"), message: t("admin.actions.ticketIdPrompt") });
+    const ticketId = (ticketIdRaw || "").trim();
+    const reasonRaw = await promptInput({ title: t("admin.ui.resetPassword"), message: t("admin.actions.resetReasonPrompt") });
+    const reason = (reasonRaw || "").trim();
     if (!approvalToken || !ticketId || reason.length < 5) return setError(t("admin.actions.incompleteApprovalFields"));
     try {
```

- [ ] **Step 3: `AdminPage.tsx` — instantiate the dialog, pass it in, render it once**

```diff
 import { useAdminActions } from "@/pages/admin/useAdminActions";
 import { useAdminState } from "@/pages/admin/useAdminState";
 import { formatAuditTime } from "@/pages/admin/utils";
 import { ROLE_OPTIONS, STATUS_OPTIONS, ACTION_KEYWORD_OPTIONS } from "@/pages/admin/constants";
+import { PromptDialog } from "@/components/PromptDialog";
+import { usePromptDialog } from "@/hooks/usePromptDialog";
```

```diff
   const state = useAdminState();
   const isAdmin = useMemo(() => (user?.role || "").toLowerCase() === "admin", [user?.role]);
+  const promptDialog = usePromptDialog();
```

```diff
   const actions = useAdminActions({
     ...state,
     isAdmin,
     onLogout,
+    promptInput: promptDialog.promptInput,
   });
```

Render the dialog once, near the top of the returned JSX (as a sibling of `<header className="topbar">`):

```tsx
      <PromptDialog
        isOpen={promptDialog.isOpen}
        title={promptDialog.options?.title || ""}
        message={promptDialog.options?.message || ""}
        defaultValue={promptDialog.options?.defaultValue}
        inputType={promptDialog.options?.inputType}
        onConfirm={promptDialog.handleConfirm}
        onCancel={promptDialog.handleCancel}
      />
```

- [ ] **Step 4: Typecheck**

Run: `npx tsc -b --force`
Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/admin/actions/types.ts frontend/src/pages/admin/actions/userActions.ts frontend/src/pages/AdminPage.tsx
git commit -m "refactor(admin): replace window.prompt with PromptDialog in userActions"
```

---

### Task 12: Verify Part 2 end-to-end

**Files:** none (verification-only task)

- [ ] **Step 1: Typecheck + build**

Run: `npx tsc -b --force` then `npm run build`
Expected: both clean.

- [ ] **Step 2: Manual dev-server check**

Run `npm run dev` and click through every converted flow — confirm no native browser dialog ever appears, the app's own dialog opens instead, Escape/Cancel abort the action, and the happy path still completes:
- Chat: delete a message, edit a message's content (multiline), delete an indexed document, delete a saved prompt template.
- Admin (as an admin user): add credits to a non-admin user, reset an admin's approval token (4 sequential prompts), reset a user's password (4 sequential prompts). Cancel partway through one of the multi-step admin flows and confirm it aborts cleanly (matches the old `window.prompt` returning `null` behavior).

- [ ] **Step 3: Commit** (only if Step 2 surfaced fixes)

---

## Part 3: Remove dead `FileUploadErrorBoundary`

### Task 13: Delete the unused error boundary

**Rationale:** Confirmed via grep that `FileUploadErrorBoundary` has zero imports anywhere in `frontend/src` — it isn't mounted. Reviewed every upload-related render path (`DocumentsPanel.tsx`, `DocumentItem.tsx`, `WorkbenchPanel.tsx`, `PdfWorkbench.tsx`) looking for genuine render-time throw risk (JSON.parse, unchecked array/object access, date parsing that could throw): none exists — all fields render with safe fallbacks (`|| 0`, `|| ""`, `String(...)`) and `new Date(...)` never throws in JS (produces `Invalid Date` instead). Upload failures are already handled via `try/catch` in `useDocumentActions.uploadFiles` (async, outside React's render phase — a render-phase error boundary cannot catch it regardless of placement). No component in the upload path has a plausible reason to throw during render. Consistent with this repo's existing policy of deleting confirmed-dead code (see `CLAUDE.md`'s note on the backend `tests/`/`scripts/` cleanup) rather than keeping speculative safety nets.

**Files:**
- Delete: `frontend/src/components/FileUploadErrorBoundary.tsx`

- [ ] **Step 1: Delete the file**

```bash
git rm frontend/src/components/FileUploadErrorBoundary.tsx
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc -b --force`
Expected: 0 errors (nothing imported it).

- [ ] **Step 3: Commit**

```bash
git commit -m "chore(frontend): remove unused FileUploadErrorBoundary"
```

---

## Final verification (all parts)

- [ ] `npx tsc -b --force` from `frontend/` — 0 errors.
- [ ] `npm run build` from `frontend/` — succeeds.
- [ ] `npm run dev` manual pass covering: composer typing (no sidebar/message-list re-render), prompt-title typing (no composer/message-list re-render), file upload progress (no composer/message-list re-render), all 4 converted `window.confirm` sites, all 9 converted `window.prompt` call sites (1 chat + 6 admin — note `addUserCredits` and `resetUserPassword`/`resetAdminApprovalToken` overlap on shared `yourApprovalTokenPrompt`/`ticketIdPrompt` strings, so total distinct call sites converted is 6 in admin + 1 in chat = 7, plus 4 `window.confirm` sites converted = 11 native dialogs removed in total).
