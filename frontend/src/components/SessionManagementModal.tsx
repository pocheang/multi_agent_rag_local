import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { SessionSearch, SessionMetadataEditor, SessionExportImport } from "@/components/SessionManagement";
import type { SessionMessage } from "@/types/api";

type Tab = "search" | "metadata" | "exportImport";

let modalStylesLoaded = false;
async function loadModalStyles() {
  if (!modalStylesLoaded) {
    await import("@/styles/components/modals.css");
    modalStylesLoaded = true;
  }
}

type Props = {
  isOpen: boolean;
  onClose: () => void;
  currentSessionId: string | null;
  messages: SessionMessage[];
  onSelectSession: (sessionId: string) => void;
};

/**
 * Advanced session management: tag/category search across sessions, metadata
 * editing (tags/category/description + auto-tag extraction) for the current
 * session, and export/import. Reuses the ApiSettings side-panel visual
 * pattern (.api-settings-overlay/.api-settings-panel) for consistency with
 * the app's one established modal style rather than inventing a new one.
 */
export function SessionManagementModal({ isOpen, onClose, currentSessionId, messages, onSelectSession }: Props) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("search");

  useEffect(() => {
    if (isOpen) void loadModalStyles();
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSelectSession = (sessionId: string) => {
    onSelectSession(sessionId);
    onClose();
  };

  return (
    <>
      <button
        type="button"
        className="api-settings-overlay"
        onClick={onClose}
        aria-label={t("common.close")}
      />
      <aside
        className="api-settings-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="session-management-title"
      >
        <header className="settings-header">
          <div className="settings-header-content">
            <div className="settings-icon" aria-hidden="true">SM</div>
            <div>
              <h2 id="session-management-title" className="settings-title">
                {t("sessionManagement.searchSessions")}
              </h2>
            </div>
          </div>
          <button type="button" className="close-btn" onClick={onClose} aria-label={t("common.close")}>
            <span aria-hidden="true">x</span>
          </button>
        </header>

        <div className="session-management-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "search"}
            className={`session-management-tab ${tab === "search" ? "active" : ""}`}
            onClick={() => setTab("search")}
          >
            {t("sessionManagement.searchSessions")}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "metadata"}
            className={`session-management-tab ${tab === "metadata" ? "active" : ""}`}
            onClick={() => setTab("metadata")}
            disabled={!currentSessionId}
            title={currentSessionId ? undefined : t("sessionManagement.noSessionToExport")}
          >
            {t("sessionManagement.editMetadata")}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "exportImport"}
            className={`session-management-tab ${tab === "exportImport" ? "active" : ""}`}
            onClick={() => setTab("exportImport")}
          >
            {t("sessionManagement.exportSession")} / {t("sessionManagement.importSession")}
          </button>
        </div>

        <div className="settings-content">
          {tab === "search" && <SessionSearch onSelectSession={handleSelectSession} />}
          {tab === "metadata" && currentSessionId && (
            <SessionMetadataEditor sessionId={currentSessionId} messages={messages} />
          )}
          {tab === "exportImport" && (
            <SessionExportImport sessionId={currentSessionId || undefined} onImportSuccess={() => onClose()} />
          )}
        </div>
      </aside>
    </>
  );
}
