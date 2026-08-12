import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { LanguageToggle } from "@/components/LanguageToggle";
import { getThemeIcon } from "@/lib/theme";
import { RoleBadge } from "@/hooks/usePermissions";
import type { UserIdentity } from "@/types/auth";

type Props = {
  themeLabel: string;
  sidebarCollapsed: boolean;
  user: UserIdentity | null;
  onToggleSidebar: () => void;
  onOpenSettings: () => void;
  onThemeToggle: () => void;
};

export function ChatTopbar({
  themeLabel,
  sidebarCollapsed,
  user,
  onToggleSidebar,
  onOpenSettings,
  onThemeToggle,
}: Props) {
  const { t } = useTranslation();
  const themeIcon = getThemeIcon(themeLabel);

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          type="button"
          className="secondary mobile-menu-btn topbar-rail-toggle"
          onClick={onToggleSidebar}
          aria-label={sidebarCollapsed ? t("components.chat.expandSidebar") : t("components.chat.openSidebar")}
          aria-expanded={!sidebarCollapsed}
        >
          {t("components.chat.menu")}
        </button>
        <div className="topbar-brand">
          <div className="brand-logo" aria-hidden="true">
            <span className="brand-logo-glyph">▶</span>
          </div>
          <div className="brand-info">
            <h2>QueryMind</h2>
            <span className="brand-subtitle">{t("components.chat.brandSubtitle")}</span>
          </div>
        </div>
      </div>

      <div className="top-actions">
        {user && (
          <div className="topbar-user-info" style={{ marginRight: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '14px', color: '#666' }}>{user.username}</span>
            <RoleBadge role={user.role} />
          </div>
        )}
        <LanguageToggle />
        {user && (
          <button type="button" className="topbar-btn" onClick={onOpenSettings} aria-label={t("components.chat.openSettings")}>
            <span className="btn-icon" aria-hidden="true">⚙</span>
            <span className="btn-label">{t("components.chat.settings")}</span>
          </button>
        )}
        <button
          type="button"
          className="topbar-btn"
          onClick={onThemeToggle}
          aria-label={t("components.chat.toggleTheme", { theme: themeLabel })}
        >
          <span className="btn-icon" aria-hidden="true">{themeIcon}</span>
          <span className="btn-label">{themeLabel}</span>
        </button>
        <Link className="topbar-btn" to="/app/architecture" aria-label={t("components.chat.viewArchitecture")}>
          <span className="btn-icon" aria-hidden="true">▦</span>
          <span className="btn-label">{t("components.chat.architecture")}</span>
        </Link>
      </div>
    </header>
  );
}
