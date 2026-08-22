import type { UserIdentity } from "@/types/auth";
import { TopbarMenu } from "@/pages/chat/components/TopbarMenu";

type Props = {
  themeLabel: string;
  sidebarCollapsed: boolean;
  user: UserIdentity | null;
  topbarHidden: boolean;
  sectionsHidden: boolean;
  onToggleSidebar: () => void;
  onOpenSettings: () => void;
  onThemeToggle: () => void;
  onToggleTopbar: () => void;
  onToggleSections: () => void;
};

export function ChatTopbar({
  themeLabel,
  user,
  topbarHidden,
  sectionsHidden,
  onOpenSettings,
  onThemeToggle,
  onToggleTopbar,
  onToggleSections,
}: Props) {
  return (
    <header
      className="topbar topbar-minimal"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        width: '100%',
        height: 0,
        minHeight: 0,
        padding: 0,
        margin: 0,
        border: 'none',
        background: 'transparent',
        zIndex: 10000,
        pointerEvents: 'none'
      }}
    >
      <div
        className="topbar-actions-right"
        style={{
          position: 'absolute',
          top: '16px',
          right: '16px',
          zIndex: 10001,
          pointerEvents: 'auto'
        }}
      >
        <TopbarMenu
          user={user}
          themeLabel={themeLabel}
          topbarHidden={topbarHidden}
          sectionsHidden={sectionsHidden}
          onToggleTopbar={onToggleTopbar}
          onToggleSections={onToggleSections}
          onOpenSettings={onOpenSettings}
          onThemeToggle={onThemeToggle}
        />
      </div>
    </header>
  );
}
