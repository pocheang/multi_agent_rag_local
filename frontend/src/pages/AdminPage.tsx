import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, appApi } from "@/lib/api";
import type { AdminUserSummary, AuditLogEntry, AuthUser } from "@/types/api";

type Props = {
  user: AuthUser | null;
  onLogout: () => Promise<void>;
  themeLabel: string;
  onThemeToggle: () => void;
};

const ROLE_OPTIONS = ["viewer", "analyst", "admin"];
const STATUS_OPTIONS = ["active", "disabled"];

export function AdminPage({ user, onLogout, themeLabel, onThemeToggle }: Props) {
  const [users, setUsers] = useState<AdminUserSummary[]>([]);
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [auditLimit, setAuditLimit] = useState(200);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [error, setError] = useState("");

  const isAdmin = useMemo(() => (user?.role || "").toLowerCase() === "admin", [user?.role]);

  const handleApiError = async (e: unknown, fallback: string) => {
    if (e instanceof ApiError && e.status === 401) {
      await onLogout();
      return;
    }
    setError(e instanceof Error ? e.message : fallback);
  };

  const loadUsers = async () => {
    if (!isAdmin) return;
    setLoadingUsers(true);
    try {
      const rows = await appApi.adminUsers();
      setUsers(rows);
      setError("");
    } catch (e) {
      await handleApiError(e, "加载用户失败");
    } finally {
      setLoadingUsers(false);
    }
  };

  const loadLogs = async () => {
    if (!isAdmin) return;
    setLoadingLogs(true);
    try {
      const rows = await appApi.adminAudit(auditLimit);
      setLogs(rows);
      setError("");
    } catch (e) {
      await handleApiError(e, "加载审计日志失败");
    } finally {
      setLoadingLogs(false);
    }
  };

  const updateRole = async (target: AdminUserSummary, role: string) => {
    if (target.role === role) return;
    const isSelf = user && target.user_id === user.user_id;
    if (isSelf && !window.confirm("你正在修改自己的角色，可能会失去管理后台权限，是否继续？")) return;
    if (target.role === "admin" && role !== "admin") {
      if (!window.confirm(`高风险操作：用户 ${target.username} 将失去管理员权限，确认继续？`)) return;
    }
    setStatusText("正在更新角色...");
    try {
      const updated = await appApi.adminUpdateRole(target.user_id, role);
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
      setStatusText(`角色已更新: ${updated.username} => ${updated.role}`);
    } catch (e) {
      await handleApiError(e, "角色更新失败");
      await loadUsers();
    }
  };

  const updateStatus = async (target: AdminUserSummary, statusValue: string) => {
    if (target.status === statusValue) return;
    const isSelf = user && target.user_id === user.user_id;
    if (statusValue === "disabled") {
      const text = isSelf
        ? "你正在禁用自己的账号，会立即退出登录，是否继续？"
        : `高风险操作：将禁用用户 ${target.username}，是否继续？`;
      if (!window.confirm(text)) return;
    }
    setStatusText("正在更新状态...");
    try {
      const updated = await appApi.adminUpdateStatus(target.user_id, statusValue);
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
      setStatusText(`状态已更新: ${updated.username} => ${updated.status}`);
      if (isSelf && updated.status === "disabled") {
        await onLogout();
      }
    } catch (e) {
      await handleApiError(e, "状态更新失败");
      await loadUsers();
    }
  };

  useEffect(() => {
    void loadUsers();
    void loadLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  useEffect(() => {
    if (!isAdmin) return;
    void loadLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auditLimit]);

  return (
    <div className="admin-shell">
      <header className="topbar">
        <div>
          <h2>管理后台（React）</h2>
          <p className="muted">用户管理与审计日志已迁移。</p>
        </div>
        <div className="top-actions">
          <button className="secondary" type="button" onClick={onThemeToggle}>
            {themeLabel}
          </button>
          <Link className="secondary link-btn" to="/app">
            返回聊天
          </Link>
          <button type="button" onClick={() => void onLogout()}>
            退出
          </button>
        </div>
      </header>

      {!isAdmin && (
        <main className="panel">
          <div className="status error">你没有管理员权限。</div>
        </main>
      )}

      {isAdmin && (
        <>
          <main className="panel">
            <div className="section-head">
              <strong>用户管理</strong>
              <button type="button" className="secondary tiny-btn" onClick={() => void loadUsers()}>
                刷新
              </button>
            </div>
            {loadingUsers && <div className="skeleton-list" />}
            {!loadingUsers && (
              <table className="table">
                <thead>
                  <tr>
                    <th>用户名</th>
                    <th>角色</th>
                    <th>状态</th>
                    <th>创建时间</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((row) => (
                    <tr key={row.user_id}>
                      <td>{row.username}</td>
                      <td>
                        <select
                          value={row.role}
                          onChange={(e) => void updateRole(row, e.target.value)}
                        >
                          {ROLE_OPTIONS.map((x) => (
                            <option key={x} value={x}>
                              {x}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <select
                          value={row.status}
                          onChange={(e) => void updateStatus(row, e.target.value)}
                        >
                          {STATUS_OPTIONS.map((x) => (
                            <option key={x} value={x}>
                              {x}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>{row.created_at || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </main>

          <main className="panel">
            <div className="section-head">
              <strong>审计日志</strong>
              <div className="row-actions">
                <select value={auditLimit} onChange={(e) => setAuditLimit(Number(e.target.value) || 200)}>
                  <option value={100}>最近 100 条</option>
                  <option value={200}>最近 200 条</option>
                  <option value={500}>最近 500 条</option>
                </select>
                <button type="button" className="secondary tiny-btn" onClick={() => void loadLogs()}>
                  刷新
                </button>
              </div>
            </div>
            {loadingLogs && <div className="skeleton-list" />}
            {!loadingLogs && (
              <table className="table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>执行者</th>
                    <th>动作</th>
                    <th>资源</th>
                    <th>结果</th>
                    <th>详情</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((x) => (
                    <tr key={x.event_id}>
                      <td>{x.created_at || "-"}</td>
                      <td>
                        {x.actor_user_id || "-"} ({x.actor_role || "-"})
                      </td>
                      <td>{x.action || "-"}</td>
                      <td>
                        {x.resource_type || "-"} / {x.resource_id || "-"}
                      </td>
                      <td>{x.result || "-"}</td>
                      <td>{x.detail || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </main>
        </>
      )}

      {statusText && <div className="status">{statusText}</div>}
      {error && <div className="status error">{error}</div>}
    </div>
  );
}
