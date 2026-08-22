import { useEffect, useMemo, useRef, useState } from "react";
import type React from "react";
import { useTranslation } from "react-i18next";
import type { SessionSummary } from "@/types/api";
import { usePermissions } from "@/hooks/usePermissions";
import type { UserIdentity } from "@/types/auth";
import { ConfirmDialog } from "@/components/ConfirmDialog";

type Props = {
  sessions: SessionSummary[];
  sessionLoading: boolean;
  currentSessionId: string | null;
  busySessionId: string | null;
  isCreatingSession: boolean;
  searchRequestKey?: number;
  user: UserIdentity | null;
  onCreateSession: () => Promise<void>;
  onLoadSession: (sessionId: string) => Promise<void>;
  onDeleteSession: (sessionId: string) => Promise<void>;
  onRenameSession?: (sessionId: string, newTitle: string) => Promise<void>;
  onPinSession?: (sessionId: string, pinned: boolean) => Promise<void>;
};

function formatSessionTime(value: string | undefined, fallback: string, locale: string) {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;

  return date.toLocaleTimeString(locale === "zh" ? "zh-CN" : "en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function SessionList({
  sessions,
  sessionLoading,
  currentSessionId,
  busySessionId,
  isCreatingSession,
  searchRequestKey = 0,
  user,
  onCreateSession,
  onLoadSession,
  onDeleteSession,
  onRenameSession,
  onPinSession,
}: Props) {
  const { t, i18n } = useTranslation();
  const permissions = usePermissions(user);
  const [sessionQuery, setSessionQuery] = useState("");
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<{ id: string; title: string } | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const isSubmittingRenameRef = useRef<string | null>(null); // Track which session is submitting

  const normalizedQuery = sessionQuery.trim().toLowerCase();
  const filteredSessions = useMemo(() => {
    if (!normalizedQuery) return sessions;

    return sessions.filter((session) => {
      const title = session.title || t("components.chat.untitled");
      return title.toLowerCase().includes(normalizedQuery);
    });
  }, [normalizedQuery, sessions, t]);

  // Sort sessions: pinned first, then by updated_at
  const sortedSessions = useMemo(() => {
    return [...filteredSessions].sort((a, b) => {
      // Pinned sessions first
      const aPinned = a.pinned || false;
      const bPinned = b.pinned || false;
      if (aPinned !== bPinned) return aPinned ? -1 : 1;

      // Then by updated_at (most recent first)
      const aTime = new Date(a.updated_at || 0).getTime();
      const bTime = new Date(b.updated_at || 0).getTime();
      return bTime - aTime;
    });
  }, [filteredSessions]);

  useEffect(() => {
    if (searchRequestKey <= 0) return;
    setSessionQuery("");
    window.setTimeout(() => searchInputRef.current?.focus(), 0);
  }, [searchRequestKey]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpenMenuId(null);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpenMenuId(null);
      }
    }

    if (openMenuId) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleEscape);
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
        document.removeEventListener("keydown", handleEscape);
      };
    }
  }, [openMenuId]);

  useEffect(() => {
    if (renamingSessionId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingSessionId]);

  const handleMenuToggle = (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    setOpenMenuId(openMenuId === sessionId ? null : sessionId);
  };

  const handleRenameStart = (session: SessionSummary, event: React.MouseEvent) => {
    event.stopPropagation();
    setOpenMenuId(null);
    setRenamingSessionId(session.session_id);
    setRenameValue(session.title || "");
    isSubmittingRenameRef.current = null;
  };

  const handleRenameSubmit = async (sessionId: string, value?: string) => {
    if (!onRenameSession) return;

    // Use provided value (from Enter key with direct DOM read) or fallback to state
    const titleValue = value !== undefined ? value : renameValue;
    const trimmedTitle = titleValue.trim();

    // Exit early if empty
    if (!trimmedTitle) {
      setRenamingSessionId(null);
      setRenameValue("");
      isSubmittingRenameRef.current = null;
      return;
    }

    // Prevent double submission - check both state and ref
    if (actionLoading === sessionId || isSubmittingRenameRef.current === sessionId) {
      return;
    }

    // Mark as submitting
    isSubmittingRenameRef.current = sessionId;
    setActionLoading(sessionId);

    try {
      await onRenameSession(sessionId, trimmedTitle);

      // Success - exit edit mode
      setRenamingSessionId(null);
      setRenameValue("");
    } catch (error) {
      // Error handled by parent - keep edit mode open for retry
      console.error("Failed to rename session:", error);
    } finally {
      // Always cleanup
      isSubmittingRenameRef.current = null;
      setActionLoading(null);
    }
  };

  const handleRenameKeyDown = (sessionId: string, event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      // Read value directly from DOM to get the absolute latest value
      // bypassing React's asynchronous state updates
      const currentValue = event.currentTarget.value;
      void handleRenameSubmit(sessionId, currentValue);
    } else if (event.key === "Escape") {
      event.preventDefault();
      setRenamingSessionId(null);
      setRenameValue("");
      isSubmittingRenameRef.current = null;
    }
  };

  const handleRenameBlur = (sessionId: string) => {
    // Only submit if not already submitting (prevents duplicate submissions)
    if (actionLoading !== sessionId && isSubmittingRenameRef.current !== sessionId) {
      void handleRenameSubmit(sessionId);
    }
  };

  const handlePinToggle = async (session: SessionSummary, event: React.MouseEvent) => {
    event.stopPropagation();
    setOpenMenuId(null);

    if (!onPinSession) return;

    const newPinned = !session.pinned;
    setActionLoading(session.session_id);
    try {
      await onPinSession(session.session_id, newPinned);
    } catch (error) {
      // Error handled by parent
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteStart = (session: SessionSummary, event: React.MouseEvent) => {
    event.stopPropagation();
    setOpenMenuId(null);
    setSessionToDelete({
      id: session.session_id,
      title: session.title || t("components.chat.untitled"),
    });
    setDeleteConfirmOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!sessionToDelete) return;

    setDeleteConfirmOpen(false);
    setActionLoading(sessionToDelete.id);
    try {
      await onDeleteSession(sessionToDelete.id);
    } catch (error) {
      // Error handled by parent
    } finally {
      setActionLoading(null);
      setSessionToDelete(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteConfirmOpen(false);
    setSessionToDelete(null);
  };

  return (
    <>
      <section className="sidebar-history-panel">
        <label className="session-search" aria-label={t("components.chat.searchSessions")}>
          <span className="session-search-icon" aria-hidden="true" />
          <input
            ref={searchInputRef}
            type="search"
            value={sessionQuery}
            onChange={(event) => setSessionQuery(event.target.value)}
            placeholder={t("components.chat.searchSessions")}
          />
        </label>
        <button
          type="button"
          className="session-create-btn"
          onClick={() => void onCreateSession()}
          disabled={sessionLoading || isCreatingSession}
        >
          <span className="session-create-icon" aria-hidden="true">+</span>
          <span>{t("components.chat.newSession")}</span>
          <small>{sessions.length || 0}</small>
        </button>
        {sessionLoading && <div className="skeleton-list" />}
        {!sessionLoading && sessions.length === 0 && <div className="muted">{t("components.chat.noSessions")}</div>}
        {!sessionLoading && sessions.length > 0 && filteredSessions.length === 0 && (
          <div className="session-empty">{t("components.chat.noSessionMatches")}</div>
        )}
        {!sessionLoading && sortedSessions.length > 0 && (
          <ul className="list session-list">
            {sortedSessions.map((session) => {
              const title = session.title || t("components.chat.untitled");
              const isRenaming = renamingSessionId === session.session_id;
              const isLoading = actionLoading === session.session_id;

              return (
                <li
                  key={session.session_id}
                  className={`session-item ${session.session_id === currentSessionId ? "active" : ""} ${session.pinned ? "pinned" : ""}`}
                >
                  <button
                    type="button"
                    className="list-main-btn session-main-btn"
                    onClick={() => void onLoadSession(session.session_id)}
                    disabled={busySessionId === session.session_id || isRenaming || isLoading}
                  >
                    <span className="session-copy">
                      {isRenaming ? (
                        <input
                          ref={renameInputRef}
                          type="text"
                          className="session-rename-input"
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onBlur={() => handleRenameBlur(session.session_id)}
                          onKeyDown={(e) => handleRenameKeyDown(session.session_id, e)}
                          onClick={(e) => e.stopPropagation()}
                          disabled={isLoading}
                        />
                      ) : (
                        <>
                          <span className="session-title">
                            {session.pinned && <span className="session-pin-indicator">📌</span>}
                            {title}
                          </span>
                          <small className="session-meta">
                            {formatSessionTime(session.updated_at, t("components.chat.recent"), i18n.language)}
                          </small>
                        </>
                      )}
                    </span>
                    {!isRenaming && <small className="session-count">{session.message_count || 0}</small>}
                  </button>
                  {!isRenaming && (
                    <div className="session-menu-wrapper">
                      <button
                        type="button"
                        className="session-menu-btn"
                        onClick={(event) => handleMenuToggle(session.session_id, event)}
                        aria-label={t("components.chat.sessionOptions", {
                          title: session.title || t("components.chat.untitledSession"),
                        })}
                        disabled={isLoading}
                      >
                        ⋯
                      </button>
                      {openMenuId === session.session_id && (
                        <div ref={menuRef} className="session-dropdown-menu">
                          {onRenameSession && (
                            <button
                              type="button"
                              className="session-menu-item"
                              onClick={(event) => handleRenameStart(session, event)}
                            >
                              <span className="menu-icon" aria-hidden="true">✏️</span>
                              {t("components.chat.renameSession")}
                            </button>
                          )}
                          {onPinSession && (
                            <button
                              type="button"
                              className="session-menu-item"
                              onClick={(event) => handlePinToggle(session, event)}
                            >
                              <span className="menu-icon" aria-hidden="true">{session.pinned ? "📌" : "📍"}</span>
                              {session.pinned ? t("components.chat.unpinSession") : t("components.chat.pinSession")}
                            </button>
                          )}
                          {permissions.canDeleteSession && (
                            <button
                              type="button"
                              className="session-menu-item danger"
                              onClick={(event) => handleDeleteStart(session, event)}
                            >
                              <span className="menu-icon" aria-hidden="true">🗑️</span>
                              {t("components.chat.deleteSession")}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <ConfirmDialog
        isOpen={deleteConfirmOpen}
        title={t("components.chat.deleteSessionTitle")}
        message={t("components.chat.deleteSessionMessage", { title: sessionToDelete?.title || "" })}
        confirmText={t("common.delete")}
        cancelText={t("common.cancel")}
        isDanger={true}
        onConfirm={() => void handleDeleteConfirm()}
        onCancel={handleDeleteCancel}
      />
    </>
  );
}
