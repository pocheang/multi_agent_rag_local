import { useTranslation } from "react-i18next";

import type { UserIdentity } from "@/types/auth";
import { TopbarMenu } from "@/pages/chat/components/TopbarMenu";

type Props = {
  sidebarCollapsed: boolean;
  user: UserIdentity | null;
  topbarHidden: boolean;
  sectionsHidden: boolean;
  onToggleSidebar: () => void;
  onOpenSettings: () => void;
  onOpenSessionManagement: () => void;
  onToggleTopbar: () => void;
  onToggleSections: () => void;
};

export function ChatTopbar({
  sidebarCollapsed,
  user,
  topbarHidden,
  sectionsHidden,
  onToggleSidebar,
  onOpenSettings,
  onOpenSessionManagement,
  onToggleTopbar,
  onToggleSections,
}: Props) {
  const { t } = useTranslation();

  return (
    <header
      className="topbar topbar-minimal"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        width: "100%",
        height: 0,
        minHeight: 0,
        padding: 0,
        margin: 0,
        border: "none",
        background: "transparent",
        zIndex: 10000,
        pointerEvents: "none",
      }}
    >
      {/* Below 1080px the sidebar becomes an off-canvas drawer that needs the
          `open` class, and `.sidebar-collapse-btn` -- the only other way to
          bring it back -- is `display: none` at that breakpoint *and* lives
          inside the sidebar itself. `onToggleSidebar` was passed to this
          component and never destructured, so nothing rendered a control for
          it: on any window narrower than 1080px the sessions list, history and
          document tools were simply unreachable. */}
      <div
        className="topbar-actions-left"
        style={{
          position: "absolute",
          top: "16px",
          left: "16px",
          zIndex: 10001,
          pointerEvents: "auto",
        }}
      >
        <button
          type="button"
          className="topbar-menu-trigger"
          onClick={onToggleSidebar}
          aria-label={t("components.chat.toggleSidebar")}
          title={t("components.chat.toggleSidebar")}
          aria-expanded={!sidebarCollapsed}
        >
          <span aria-hidden="true">☰</span>
        </button>
      </div>
      <div
        className="topbar-actions-right"
        style={{
          position: "absolute",
          top: "16px",
          right: "16px",
          zIndex: 10001,
          pointerEvents: "auto",
        }}
      >
        <TopbarMenu
          user={user}
          topbarHidden={topbarHidden}
          sectionsHidden={sectionsHidden}
          onToggleTopbar={onToggleTopbar}
          onToggleSections={onToggleSections}
          onOpenSettings={onOpenSettings}
          onOpenSessionManagement={onOpenSessionManagement}
        />
      </div>
    </header>
  );
}
