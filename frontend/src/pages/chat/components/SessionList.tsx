import { useEffect, useMemo, useRef, useState } from "react";
import type React from "react";
import { useTranslation } from "react-i18next";
import type { SessionSummary } from "@/types/api";
import { usePermissions } from "@/hooks/usePermissions";
import type { UserIdentity } from "@/types/auth";

type Props = {
  sessions: SessionSummary[];
  sessionLoading: boolean;
  currentSessionId: string | null;
  busySessionId: string | null;
  searchRequestKey?: number;
  user: UserIdentity | null;
  onCreateSession: () => Promise<void>;
  onLoadSession: (sessionId: string) => Promise<void>;
  onDeleteSession: (sessionId: string) => Promise<void>;
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
  searchRequestKey = 0,
  user,
  onCreateSession,
  onLoadSession,
  onDeleteSession,
}: Props) {
  const { t, i18n } = useTranslation();
  const permissions = usePermissions(user);
  const [sessionQuery, setSessionQuery] = useState("");
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const normalizedQuery = sessionQuery.trim().toLowerCase();
  const filteredSessions = useMemo(() => {
    if (!normalizedQuery) return sessions;

    return sessions.filter((session) => {
      const title = session.title || t("components.chat.untitled");
      return title.toLowerCase().includes(normalizedQuery);
    });
  }, [normalizedQuery, sessions, t]);

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

    if (openMenuId) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [openMenuId]);

  const handleMenuToggle = (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    setOpenMenuId(openMenuId === sessionId ? null : sessionId);
  };

  const handleDelete = (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    setOpenMenuId(null);
    void onDeleteSession(sessionId);
  };

  return (
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
        disabled={sessionLoading}
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
      {!sessionLoading && filteredSessions.length > 0 && (
        <ul className="list session-list">
          {filteredSessions.map((session) => {
            const title = session.title || t("components.chat.untitled");
            return (
              <li key={session.session_id} className={`session-item ${session.session_id === currentSessionId ? "active" : ""}`}>
                <button
                  type="button"
                  className="list-main-btn session-main-btn"
                  onClick={() => void onLoadSession(session.session_id)}
                  disabled={busySessionId === session.session_id}
                >
                  <span className="session-copy">
                    <span className="session-title">{title}</span>
                    <small className="session-meta">
                      {formatSessionTime(session.updated_at, t("components.chat.recent"), i18n.language)}
                    </small>
                  </span>
                  <small className="session-count">{session.message_count || 0}</small>
                </button>
                <div className="session-menu-wrapper">
                  <button
                    type="button"
                    className="session-menu-btn"
                    onClick={(event) => handleMenuToggle(session.session_id, event)}
                    aria-label={t("components.chat.sessionOptions", {
                      title: session.title || t("components.chat.untitledSession"),
                    })}
                  >
                    ⋯
                  </button>
                  {openMenuId === session.session_id && (
                    <div ref={menuRef} className="session-dropdown-menu">
                      {permissions.canDeleteSession && (
                        <button
                          type="button"
                          className="session-menu-item danger"
                          onClick={(event) => handleDelete(session.session_id, event)}
                        >
                          <span className="menu-icon" aria-hidden="true">×</span>
                          {t("components.chat.delete")}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
