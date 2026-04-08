import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, appApi } from "@/lib/api";
import type { AdminUserSummary, AuditLogEntry, AuthUser, OpsOverview } from "@/types/api";

type Props = { user: AuthUser | null; onLogout: () => Promise<void>; themeLabel: string; onThemeToggle: () => void };
type Section = "ops" | "admins" | "users" | "audit";

const ROLE_OPTIONS = ["viewer", "analyst"];
const STATUS_OPTIONS = ["active", "disabled"];

export function AdminPage({ user, onLogout, themeLabel, onThemeToggle }: Props) {
  const [section, setSection] = useState<Section>("ops");
  const [users, setUsers] = useState<AdminUserSummary[]>([]);
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [ops, setOps] = useState<OpsOverview | null>(null);
  const [statusText, setStatusText] = useState("");
  const [error, setError] = useState("");

  const [loadingUsers, setLoadingUsers] = useState(false);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [loadingOps, setLoadingOps] = useState(false);
  const [creatingAdmin, setCreatingAdmin] = useState(false);
  const [savingClass, setSavingClass] = useState(false);

  const [kw, setKw] = useState("");
  const [fRole, setFRole] = useState("");
  const [fStatus, setFStatus] = useState("");
  const [fOnline, setFOnline] = useState("");

  const [auditLimit, setAuditLimit] = useState(200);
  const [auditActorUserId, setAuditActorUserId] = useState("");
  const [auditActionKeyword, setAuditActionKeyword] = useState("");
  const [auditEventCategory, setAuditEventCategory] = useState("");
  const [auditSeverity, setAuditSeverity] = useState("");
  const [auditResult, setAuditResult] = useState("");

  const [opsHours, setOpsHours] = useState(24);
  const [opsActorUserId, setOpsActorUserId] = useState("");
  const [opsActionKeyword, setOpsActionKeyword] = useState("");
  const [opsAutoRefresh, setOpsAutoRefresh] = useState(true);

  const [adminUsername, setAdminUsername] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [adminPassword2, setAdminPassword2] = useState("");
  const [adminApprovalToken, setAdminApprovalToken] = useState("");
  const [newAdminApprovalToken, setNewAdminApprovalToken] = useState("");
  const [adminTicketId, setAdminTicketId] = useState("");
  const [adminReason, setAdminReason] = useState("");

  const [editingUser, setEditingUser] = useState<AdminUserSummary | null>(null);
  const [editBu, setEditBu] = useState("");
  const [editDept, setEditDept] = useState("");
  const [editType, setEditType] = useState("");
  const [editScope, setEditScope] = useState("");

  const isAdmin = useMemo(() => (user?.role || "").toLowerCase() === "admin", [user?.role]);

  const filteredUsers = useMemo(() => {
    const q = kw.trim().toLowerCase();
    return users.filter((u) => {
      if (q && ![u.username, u.user_id, u.business_unit, u.department, u.user_type, u.data_scope].join(" ").toLowerCase().includes(q)) return false;
      if (fRole && (u.role || "") !== fRole) return false;
      if (fStatus && (u.status || "") !== fStatus) return false;
      if (fOnline === "online" && !u.is_online) return false;
      if (fOnline === "offline" && u.is_online) return false;
      if (fOnline === "online_10m" && !u.is_online_10m) return false;
      return true;
    });
  }, [users, kw, fRole, fStatus, fOnline]);

  const actionMax = useMemo(() => Math.max(1, ...(ops?.top_actions || []).map((x) => x.count)), [ops]);
  const resourceMax = useMemo(() => Math.max(1, ...(ops?.top_resource_types || []).map((x) => x.count)), [ops]);
  const errorMax = useMemo(() => Math.max(1, ...(ops?.top_error_reasons || []).map((x) => x.count)), [ops]);
  const hourlyMax = useMemo(() => Math.max(1, ...(ops?.hourly || []).map((x) => x.count)), [ops]);

  const handleApiError = async (e: unknown, fallback: string) => {
    if (e instanceof ApiError && e.status === 401) return onLogout();
    setError(e instanceof Error ? e.message : fallback);
  };

  const loadUsers = async () => {
    if (!isAdmin) return;
    setLoadingUsers(true);
    try {
      setUsers(await appApi.adminUsers());
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
      setLogs(await appApi.adminAudit({
        limit: auditLimit,
        actorUserId: auditActorUserId.trim() || undefined,
        actionKeyword: auditActionKeyword.trim() || undefined,
        eventCategory: auditEventCategory.trim() || undefined,
        severity: auditSeverity.trim() || undefined,
        result: auditResult.trim() || undefined,
      }));
      setError("");
    } catch (e) {
      await handleApiError(e, "加载审计日志失败");
    } finally {
      setLoadingLogs(false);
    }
  };

  const loadOps = async () => {
    if (!isAdmin) return;
    setLoadingOps(true);
    try {
      setOps(await appApi.adminOpsOverview({
        hours: opsHours,
        actorUserId: opsActorUserId.trim() || undefined,
        actionKeyword: opsActionKeyword.trim() || undefined,
      }));
      setError("");
    } catch (e) {
      await handleApiError(e, "加载运维指标失败");
    } finally {
      setLoadingOps(false);
    }
  };

  const exportOpsCsv = async () => {
    try {
      const csv = await appApi.adminOpsExportCsv({
        hours: opsHours,
        actorUserId: opsActorUserId.trim() || undefined,
        actionKeyword: opsActionKeyword.trim() || undefined,
      });
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ops_report_${new Date().toISOString().replace(/[:.]/g, "-")}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setStatusText("运维报表导出成功");
    } catch (e) {
      await handleApiError(e, "导出失败");
    }
  };

  const createAdmin = async () => {
    const username = adminUsername.trim();
    if (!username) return setError("管理员用户名不能为空");
    if (!adminPassword || adminPassword.length < 8) return setError("密码长度至少 8 位");
    if (adminPassword !== adminPassword2) return setError("两次密码不一致");
    if (!adminApprovalToken.trim()) return setError("审批令牌不能为空");
    if (!newAdminApprovalToken.trim() || newAdminApprovalToken.trim().length < 12) return setError("新管理员令牌至少 12 位");
    if (!adminTicketId.trim()) return setError("工单号不能为空");
    if (!adminReason.trim() || adminReason.trim().length < 5) return setError("原因至少 5 个字符");
    setCreatingAdmin(true);
    try {
      const created = await appApi.adminCreateAdmin({
        username,
        password: adminPassword,
        approvalToken: adminApprovalToken.trim(),
        ticketId: adminTicketId.trim(),
        reason: adminReason.trim(),
        newAdminApprovalToken: newAdminApprovalToken.trim(),
      });
      setUsers((prev) => [created, ...prev]);
      setAdminUsername("");
      setAdminPassword("");
      setAdminPassword2("");
      setAdminApprovalToken("");
      setNewAdminApprovalToken("");
      setAdminTicketId("");
      setAdminReason("");
      setStatusText(`管理员已创建：${created.username}`);
      setError("");
    } catch (e) {
      await handleApiError(e, "创建管理员失败");
    } finally {
      setCreatingAdmin(false);
    }
  };

  const updateRole = async (target: AdminUserSummary, role: string) => {
    if (target.role === role) return;
    try {
      const updated = await appApi.adminUpdateRole(target.user_id, role);
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
    } catch (e) {
      await handleApiError(e, "角色更新失败");
    }
  };

  const updateStatus = async (target: AdminUserSummary, statusValue: string) => {
    if (target.status === statusValue) return;
    try {
      const updated = await appApi.adminUpdateStatus(target.user_id, statusValue);
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
    } catch (e) {
      await handleApiError(e, "状态更新失败");
    }
  };

  const openClassEditor = (u: AdminUserSummary) => {
    setEditingUser(u);
    setEditBu(u.business_unit || "");
    setEditDept(u.department || "");
    setEditType(u.user_type || "");
    setEditScope(u.data_scope || "");
  };

  const saveClass = async () => {
    if (!editingUser) return;
    setSavingClass(true);
    try {
      const updated = await appApi.adminUpdateClassification(editingUser.user_id, {
        businessUnit: editBu.trim(),
        department: editDept.trim(),
        userType: editType.trim(),
        dataScope: editScope.trim(),
      });
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
      setEditingUser(null);
      setStatusText("用户分类已保存");
    } catch (e) {
      await handleApiError(e, "分类更新失败");
    } finally {
      setSavingClass(false);
    }
  };

  const resetAdminApprovalToken = async (target: AdminUserSummary) => {
    if ((target.role || "").toLowerCase() !== "admin") return;
    const newToken = (window.prompt(`请输入 ${target.username} 的新管理员令牌（至少12位）`) || "").trim();
    if (!newToken || newToken.length < 12) return setError("新管理员令牌至少 12 位");
    const approvalToken = (window.prompt("请输入你的审批令牌") || "").trim();
    const ticketId = (window.prompt("请输入工单号") || "").trim();
    const reason = (window.prompt("请输入原因（至少5个字符）") || "").trim();
    if (!approvalToken || !ticketId || reason.length < 5) return setError("审批令牌/工单号/原因不完整");
    try {
      const updated = await appApi.adminResetApprovalToken({
        userId: target.user_id,
        approvalToken,
        ticketId,
        reason,
        newAdminApprovalToken: newToken,
      });
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
      setStatusText(`管理员令牌已重置：${updated.username}`);
    } catch (e) {
      await handleApiError(e, "重置管理员令牌失败");
    }
  };

  const resetUserPassword = async (target: AdminUserSummary) => {
    const newPassword = (window.prompt(`请输入 ${target.username} 的新密码（至少8位，含大小写和数字）`) || "").trim();
    if (!newPassword) return;
    const approvalToken = (window.prompt("请输入你的审批令牌") || "").trim();
    const ticketId = (window.prompt("请输入工单号") || "").trim();
    const reason = (window.prompt("请输入重置原因（至少5个字符）") || "").trim();
    if (!approvalToken || !ticketId || reason.length < 5) return setError("审批令牌/工单号/原因不完整");
    try {
      const updated = await appApi.adminResetPassword({
        userId: target.user_id,
        approvalToken,
        ticketId,
        reason,
        newPassword,
      });
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
      setStatusText(`用户密码已重置：${updated.username}`);
    } catch (e) {
      await handleApiError(e, "重置密码失败");
    }
  };

  useEffect(() => {
    void loadUsers();
    void loadLogs();
    void loadOps();
    // eslint-disable-next-line
  }, [isAdmin]);

  useEffect(() => {
    if (isAdmin) void loadLogs();
    // eslint-disable-next-line
  }, [auditLimit, auditActorUserId, auditActionKeyword, auditEventCategory, auditSeverity, auditResult]);

  useEffect(() => {
    if (isAdmin) void loadOps();
    // eslint-disable-next-line
  }, [opsHours, opsActorUserId, opsActionKeyword]);

  useEffect(() => {
    if (!isAdmin || section !== "ops" || !opsAutoRefresh) return;
    const t = window.setInterval(() => void loadOps(), 30000);
    return () => window.clearInterval(t);
    // eslint-disable-next-line
  }, [isAdmin, section, opsAutoRefresh, opsHours, opsActorUserId, opsActionKeyword]);

  return (
    <div className="admin-shell">
      <header className="topbar">
        <div><h2>管理控制台</h2><p className="muted">企业级管理工作台</p></div>
        <div className="top-actions">
          <button className="secondary" type="button" onClick={onThemeToggle}>{themeLabel}</button>
          <Link className="secondary link-btn" to="/app">返回聊天</Link>
          <button type="button" onClick={() => void onLogout()}>退出登录</button>
        </div>
      </header>

      {!isAdmin && <main className="panel"><div className="status error">当前账号没有管理员权限。</div></main>}
      {isAdmin && (
        <>
          <main className="panel">
            <div className="row-actions wrap admin-section-tabs">
              <button type="button" className={section === "ops" ? "" : "secondary"} onClick={() => setSection("ops")}>系统运维</button>
              <button type="button" className={section === "admins" ? "" : "secondary"} onClick={() => setSection("admins")}>创建管理员</button>
              <button type="button" className={section === "users" ? "" : "secondary"} onClick={() => setSection("users")}>用户管理</button>
              <button type="button" className={section === "audit" ? "" : "secondary"} onClick={() => setSection("audit")}>审计日志</button>
            </div>
          </main>

          {section === "admins" && <main className="panel">
            <div className="section-head"><strong>创建管理员</strong></div>
            <div className="ops-two-col"><input placeholder="管理员用户名" value={adminUsername} onChange={(e) => setAdminUsername(e.target.value)} /><input placeholder="管理员密码" type="password" value={adminPassword} onChange={(e) => setAdminPassword(e.target.value)} /></div>
            <div className="ops-two-col"><input placeholder="确认密码" type="password" value={adminPassword2} onChange={(e) => setAdminPassword2(e.target.value)} /><input placeholder="我的审批令牌" type="password" value={adminApprovalToken} onChange={(e) => setAdminApprovalToken(e.target.value)} /></div>
            <div className="ops-two-col"><input placeholder="新管理员令牌（>=12）" type="password" value={newAdminApprovalToken} onChange={(e) => setNewAdminApprovalToken(e.target.value)} /><input placeholder="工单号" value={adminTicketId} onChange={(e) => setAdminTicketId(e.target.value)} /></div>
            <div className="ops-two-col"><input placeholder="创建原因" value={adminReason} onChange={(e) => setAdminReason(e.target.value)} /><button type="button" disabled={creatingAdmin} onClick={() => void createAdmin()}>{creatingAdmin ? "创建中..." : "创建管理员"}</button></div>
          </main>}

          {section === "ops" && <main className="panel ops-wrap">
            <div className="section-head"><strong>系统监控</strong><div className="row-actions"><button type="button" className="secondary tiny-btn" onClick={() => void loadOps()}>刷新</button><button type="button" className="secondary tiny-btn" onClick={() => void exportOpsCsv()}>导出 CSV</button></div></div>
            <div className="ops-two-col"><select value={opsHours} onChange={(e) => setOpsHours(Number(e.target.value) || 24)}><option value={1}>1小时</option><option value={6}>6小时</option><option value={24}>24小时</option><option value={72}>72小时</option><option value={168}>7天</option></select><label className="row-actions" style={{ alignSelf: "center" }}><input type="checkbox" checked={opsAutoRefresh} onChange={(e) => setOpsAutoRefresh(e.target.checked)} /><span>每 30 秒自动刷新</span></label></div>
            <div className="ops-two-col"><input placeholder="执行者用户ID" value={opsActorUserId} onChange={(e) => setOpsActorUserId(e.target.value)} /><input placeholder="动作关键字" value={opsActionKeyword} onChange={(e) => setOpsActionKeyword(e.target.value)} /></div>
            {loadingOps && <div className="skeleton-list" />}
            {!loadingOps && ops && <>
              <div className="ops-kpi-grid">
                <div className="ops-kpi-card"><span>请求总数</span><strong>{ops.kpi.requests_total}</strong></div>
                <div className="ops-kpi-card"><span>成功请求</span><strong>{ops.kpi.requests_success}</strong></div>
                <div className="ops-kpi-card"><span>失败请求</span><strong>{ops.kpi.requests_error}</strong></div>
                <div className="ops-kpi-card"><span>错误率</span><strong>{ops.kpi.error_rate_percent}%</strong></div>
                <div className="ops-kpi-card"><span>活跃会话</span><strong>{ops.kpi.active_sessions}</strong></div>
                <div className="ops-kpi-card"><span>活跃用户</span><strong>{ops.kpi.active_users}</strong></div>
                <div className="ops-kpi-card"><span>问答请求</span><strong>{ops.kpi.queries}</strong></div>
                <div className="ops-kpi-card"><span>上传次数</span><strong>{ops.kpi.uploads}</strong></div>
                <div className="ops-kpi-card"><span>登录成功</span><strong>{ops.kpi.login_success}</strong></div>
                <div className="ops-kpi-card"><span>登录失败</span><strong>{ops.kpi.login_failed}</strong></div>
              </div>
              <div className="ops-kpi-grid">
                <div className="ops-kpi-card"><span>用户总数</span><strong>{ops.users.total}</strong></div>
                <div className="ops-kpi-card"><span>启用用户</span><strong>{ops.users.active}</strong></div>
                <div className="ops-kpi-card"><span>禁用用户</span><strong>{ops.users.disabled}</strong></div>
                <div className="ops-kpi-card"><span>管理员数量</span><strong>{ops.users.admin}</strong></div>
              </div>
              <div className="ops-two-col">
                <div className="ops-trend-list"><strong>高频动作</strong>{ops.top_actions.map((x) => <div key={x.action} className="ops-trend-row"><span>{x.action}</span><div className="ops-trend-bar"><div className="ops-trend-fill" style={{ width: `${Math.max(4, (x.count / actionMax) * 100)}%` }} /></div><strong>{x.count}</strong></div>)}</div>
                <div className="ops-trend-list"><strong>资源类型排行</strong>{ops.top_resource_types.map((x) => <div key={x.resource_type} className="ops-trend-row"><span>{x.resource_type}</span><div className="ops-trend-bar"><div className="ops-trend-fill" style={{ width: `${Math.max(4, (x.count / resourceMax) * 100)}%` }} /></div><strong>{x.count}</strong></div>)}</div>
              </div>
              <div className="ops-two-col">
                <div className="ops-trend-list"><strong>高频错误原因</strong>{ops.top_error_reasons.map((x) => <div key={x.reason} className="ops-trend-row"><span title={x.reason}>{x.reason.slice(0, 18)}</span><div className="ops-trend-bar"><div className="ops-trend-fill" style={{ width: `${Math.max(4, (x.count / errorMax) * 100)}%` }} /></div><strong>{x.count}</strong></div>)}</div>
                <div className="ops-trend-list">
                  <strong>服务健康状态</strong>
                  {Object.entries(ops.services || {}).map(([name, svc]) => (
                    <div key={name} className="ops-trend-row">
                      <span>{name}</span>
                      <strong>{svc.ok ? `正常（${svc.latency_ms ?? 0}ms）` : `异常：${svc.error || "unknown"}`}</strong>
                    </div>
                  ))}
                </div>
              </div>
              <div className="ops-trend-list"><strong>按小时趋势</strong>{ops.hourly.map((x) => <div key={x.bucket} className="ops-trend-row"><span>{x.bucket.slice(11, 16)}</span><div className="ops-trend-bar"><div className="ops-trend-fill" style={{ width: `${Math.max(4, (x.count / hourlyMax) * 100)}%` }} /></div><strong>{x.count}/{x.errors}</strong></div>)}</div>
              <table className="table"><thead><tr><th>时间</th><th>方法</th><th>路径</th><th>状态码</th><th>耗时</th><th>错误</th></tr></thead><tbody>{ops.slow_requests.map((x, idx) => <tr key={`${x.ts}-${idx}`}><td>{x.ts}</td><td>{x.method}</td><td>{x.path}</td><td>{x.status_code}</td><td>{x.duration_ms}</td><td>{x.error || "-"}</td></tr>)}</tbody></table>
            </>}
          </main>}

          {section === "users" && <main className="panel">
            <div className="section-head"><strong>用户管理</strong><button type="button" className="secondary tiny-btn" onClick={() => void loadUsers()}>刷新</button></div>
            <div className="ops-two-col"><input placeholder="搜索用户名/ID/分类" value={kw} onChange={(e) => setKw(e.target.value)} /><select value={fRole} onChange={(e) => setFRole(e.target.value)}><option value="">全部角色</option><option value="admin">admin</option><option value="analyst">analyst</option><option value="viewer">viewer</option></select></div>
            <div className="ops-two-col"><select value={fStatus} onChange={(e) => setFStatus(e.target.value)}><option value="">全部状态</option><option value="active">active</option><option value="disabled">disabled</option></select><select value={fOnline} onChange={(e) => setFOnline(e.target.value)}><option value="">全部在线状态</option><option value="online_10m">10分钟内在线</option><option value="online">在线</option><option value="offline">离线</option></select></div>
            {editingUser && <div className="panel" style={{ marginBottom: 12 }}><div className="section-head"><strong>用户分类：{editingUser.username}</strong><button type="button" className="secondary tiny-btn" onClick={() => setEditingUser(null)}>取消</button></div><div className="ops-two-col"><input placeholder="业务单元" value={editBu} onChange={(e) => setEditBu(e.target.value)} /><input placeholder="部门" value={editDept} onChange={(e) => setEditDept(e.target.value)} /></div><div className="ops-two-col"><input placeholder="用户类型" value={editType} onChange={(e) => setEditType(e.target.value)} /><input placeholder="数据范围" value={editScope} onChange={(e) => setEditScope(e.target.value)} /></div><div className="row-actions"><button type="button" disabled={savingClass} onClick={() => void saveClass()}>{savingClass ? "保存中..." : "保存分类"}</button></div></div>}
            {loadingUsers && <div className="skeleton-list" />}
            {!loadingUsers && <table className="table"><thead><tr><th>用户名</th><th>角色</th><th>状态</th><th>在线</th><th>10分钟</th><th>业务单元</th><th>部门</th><th>类型</th><th>范围</th><th>创建人</th><th>工单</th><th>令牌</th><th>操作</th></tr></thead><tbody>{filteredUsers.map((row) => <tr key={row.user_id}><td>{row.username}</td><td><select value={row.role} onChange={(e) => void updateRole(row, e.target.value)}>{([...(row.role === "admin" ? ["admin"] : []), ...ROLE_OPTIONS] as string[]).map((x) => <option key={x} value={x}>{x}</option>)}</select></td><td><select value={row.status} onChange={(e) => void updateStatus(row, e.target.value)}>{STATUS_OPTIONS.map((x) => <option key={x} value={x}>{x}</option>)}</select></td><td>{row.is_online ? "在线" : "离线"}</td><td>{row.is_online_10m ? "活跃" : "-"}</td><td>{row.business_unit || "-"}</td><td>{row.department || "-"}</td><td>{row.user_type || "-"}</td><td>{row.data_scope || "-"}</td><td>{row.created_by_username || row.created_by_user_id || "-"}</td><td>{row.admin_ticket_id || "-"}</td><td>{row.has_admin_approval_token ? "已设置" : "未设置"}</td><td><div className="row-actions"><button type="button" className="secondary tiny-btn" onClick={() => openClassEditor(row)}>分类</button><button type="button" className="secondary tiny-btn" onClick={() => void resetUserPassword(row)}>重置密码</button>{(row.role || "").toLowerCase() === "admin" ? <button type="button" className="secondary tiny-btn" onClick={() => void resetAdminApprovalToken(row)}>重置令牌</button> : null}</div></td></tr>)}</tbody></table>}
          </main>}

          {section === "audit" && <main className="panel">
            <div className="section-head"><strong>审计日志</strong><div className="row-actions"><select value={auditLimit} onChange={(e) => setAuditLimit(Number(e.target.value) || 200)}><option value={100}>最近 100 条</option><option value={200}>最近 200 条</option><option value={500}>最近 500 条</option></select><button type="button" className="secondary tiny-btn" onClick={() => void loadLogs()}>刷新</button></div></div>
            <div className="ops-two-col"><input placeholder="执行者用户ID" value={auditActorUserId} onChange={(e) => setAuditActorUserId(e.target.value)} /><input placeholder="动作关键字" value={auditActionKeyword} onChange={(e) => setAuditActionKeyword(e.target.value)} /></div>
            <div className="ops-two-col"><select value={auditEventCategory} onChange={(e) => setAuditEventCategory(e.target.value)}><option value="">全部分类</option><option value="auth">auth</option><option value="admin">admin</option><option value="data">data</option><option value="prompt">prompt</option><option value="system">system</option></select><select value={auditSeverity} onChange={(e) => setAuditSeverity(e.target.value)}><option value="">全部级别</option><option value="info">info</option><option value="medium">medium</option><option value="high">high</option></select></div>
            <div className="ops-two-col"><select value={auditResult} onChange={(e) => setAuditResult(e.target.value)}><option value="">全部结果</option><option value="success">success</option><option value="failed">failed</option><option value="denied">denied</option></select><div className="row-actions"><button type="button" className="secondary tiny-btn" onClick={() => setAuditResult("failed")}>仅失败</button><button type="button" className="secondary tiny-btn" onClick={() => setAuditSeverity("high")}>仅高危</button><button type="button" className="secondary tiny-btn" onClick={() => { setAuditActorUserId(""); setAuditActionKeyword(""); setAuditEventCategory(""); setAuditSeverity(""); setAuditResult(""); }}>清空</button></div></div>
            {loadingLogs && <div className="skeleton-list" />}
            {!loadingLogs && <table className="table"><thead><tr><th>时间</th><th>执行者</th><th>动作</th><th>分类</th><th>级别</th><th>资源</th><th>结果</th><th>IP</th><th>User-Agent</th><th>详情</th></tr></thead><tbody>{logs.map((x) => <tr key={x.event_id}><td>{x.created_at || "-"}</td><td>{x.actor_user_id || "-"} ({x.actor_role || "-"})</td><td>{x.action || "-"}</td><td>{x.event_category || "-"}</td><td>{x.severity || "-"}</td><td>{x.resource_type || "-"} / {x.resource_id || "-"}</td><td>{x.result || "-"}</td><td>{x.ip || "-"}</td><td>{x.user_agent || "-"}</td><td>{x.detail || "-"}</td></tr>)}</tbody></table>}
          </main>}
        </>
      )}

      {statusText && <div className="status">{statusText}</div>}
      {error && <div className="status error">{error}</div>}
    </div>
  );
}
