import { Link } from "react-router-dom";

type Props = {
  userBadge: string;
  themeLabel: string;
  isAdmin: boolean;
  onToggleSidebar: () => void;
  onOpenSettings: () => void;
  onThemeToggle: () => void;
  onLogout: () => Promise<void>;
};

export function ChatTopbar({
  userBadge,
  themeLabel,
  isAdmin,
  onToggleSidebar,
  onOpenSettings,
  onThemeToggle,
  onLogout,
}: Props) {
  return (
    <header className="topbar">
      <div className="topbar-copy">
        <span className="workspace-kicker">Local RAG Command Center</span>
        <h2>Evidence Chat</h2>
        <p className="muted">统一调度会话、PDF 证据、混合检索和 Agent 路由。</p>
      </div>
      <div className="top-actions">
        <span className="user-badge">{userBadge}</span>
        <button type="button" className="secondary mobile-menu-btn" onClick={onToggleSidebar}>
          菜单
        </button>
        <button type="button" className="secondary settings-action-btn" onClick={onOpenSettings} title="API 设置">
          <span aria-hidden="true">⚙︎</span>
          <span>设置</span>
        </button>
        <button type="button" className="secondary" onClick={onThemeToggle}>
          {themeLabel}
        </button>
        <Link className="secondary link-btn" to="/app/architecture">
          架构总览
        </Link>
        {isAdmin && (
          <Link className="secondary link-btn" to="/app/admin">
            管理页
          </Link>
        )}
        <button type="button" className="logout-btn" onClick={() => void onLogout()}>
          退出
        </button>
      </div>
    </header>
  );
}
