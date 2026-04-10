import { Link } from "react-router-dom";

type Props = {
  userBadge: string;
  themeLabel: string;
  isAdmin: boolean;
  onToggleSidebar: () => void;
  onThemeToggle: () => void;
  onLogout: () => Promise<void>;
};

export function ChatTopbar({
  userBadge,
  themeLabel,
  isAdmin,
  onToggleSidebar,
  onThemeToggle,
  onLogout,
}: Props) {
  return (
    <header className="topbar">
      <div>
        <h2>Agentic RAG Studio</h2>
        <p className="muted">统一管理会话、路由策略、PDF 知识与提示词。</p>
      </div>
      <div className="top-actions">
        <span className="user-badge">{userBadge}</span>
        <button type="button" className="secondary" onClick={onToggleSidebar}>
          菜单
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
        <button type="button" onClick={() => void onLogout()}>
          退出
        </button>
      </div>
    </header>
  );
}
