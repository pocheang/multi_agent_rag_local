import { Link } from "react-router-dom";

type Props = {
  userBadge: string;
  themeLabel: string;
  useWeb: boolean;
  useReasoning: boolean;
  agentClassHint: string;
  isAdmin: boolean;
  onToggleSidebar: () => void;
  onThemeToggle: () => void;
  onUseWebChange: (checked: boolean) => void;
  onUseReasoningChange: (checked: boolean) => void;
  onAgentClassHintChange: (value: string) => void;
  onLogout: () => Promise<void>;
};

export function ChatTopbar({
  userBadge,
  themeLabel,
  useWeb,
  useReasoning,
  agentClassHint,
  isAdmin,
  onToggleSidebar,
  onThemeToggle,
  onUseWebChange,
  onUseReasoningChange,
  onAgentClassHintChange,
  onLogout,
}: Props) {
  return (
    <header className="topbar">
      <div>
        <h2>网络安全攻防问答中枢（React）</h2>
        <p className="muted">已迁移：会话、流式问答、文档上传、Prompt 模板、RBAC。</p>
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
        <label className="checkline">
          <input type="checkbox" checked={useWeb} onChange={(e) => onUseWebChange(e.target.checked)} />
          联网校验
        </label>
        <label className="checkline">
          <input
            type="checkbox"
            checked={useReasoning}
            onChange={(e) => onUseReasoningChange(e.target.checked)}
          />
          推理模型
        </label>
        <label className="agent-hint-select">
          <span>Agent</span>
          <select value={agentClassHint} onChange={(e) => onAgentClassHintChange(e.target.value)}>
            <option value="">auto</option>
            <option value="cybersecurity">cybersecurity</option>
            <option value="artificial_intelligence">artificial_intelligence</option>
            <option value="pdf_text">pdf_text</option>
            <option value="general">general</option>
          </select>
        </label>
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
