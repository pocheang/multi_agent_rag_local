import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { LanguageToggle } from "@/components/LanguageToggle";
import { RoleBadge } from "@/hooks/usePermissions";
import type { UserIdentity } from "@/types/auth";

type Props = {
  user: UserIdentity | null;
  topbarHidden?: boolean;  // Optional - reserved for future use
  sectionsHidden?: boolean;  // Optional - reserved for future use
  onToggleTopbar?: () => void;  // Optional - reserved for future use
  onToggleSections?: () => void;  // Optional - reserved for future use
  onOpenSettings: () => void;
};

export function TopbarMenu({
  user,
  onOpenSettings,
}: Props) {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    };

    if (menuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleEscape);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [menuOpen]);

  return (
    <div className="topbar-menu-container" ref={menuRef}>
      <button
        type="button"
        className="topbar-menu-trigger"
        onClick={() => setMenuOpen(!menuOpen)}
        aria-label={t("components.chat.moreOptions")}
        aria-expanded={menuOpen}
      >
        <span aria-hidden="true">⋮</span>
      </button>

      {menuOpen && (
        <div className="topbar-menu-dropdown">
          {/* User info */}
          {user && (
            <div className="topbar-menu-section">
              <div className="topbar-menu-user">
                <span className="menu-user-name">{user.username}</span>
                <RoleBadge role={user.role} />
                <span className="menu-user-name">
                  {t("pages.profile.credits")}: {user.role.toLowerCase() === "admin"
                    ? t("pages.profile.unlimitedCredits")
                    : user.credit_balance}
                </span>
              </div>
            </div>
          )}

          {/* Divider */}
          {user && <div className="topbar-menu-divider" />}

          {/* Language toggle */}
          <div className="topbar-menu-item-wrapper">
            <LanguageToggle />
          </div>

          {/* Settings */}
          {user && (
            <button
              type="button"
              className="topbar-menu-item"
              onClick={() => {
                onOpenSettings();
                setMenuOpen(false);
              }}
            >
              <span className="menu-item-icon">⚙</span>
              <span className="menu-item-label">{t("components.chat.settings")}</span>
            </button>
          )}

          {/* Architecture link */}
          <Link
            className="topbar-menu-item"
            to="/app/architecture"
            onClick={() => setMenuOpen(false)}
          >
            <span className="menu-item-icon">▦</span>
            <span className="menu-item-label">{t("components.chat.architecture")}</span>
          </Link>
        </div>
      )}
    </div>
  );
}
