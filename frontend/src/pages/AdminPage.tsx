import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, appApi } from "@/lib/api";
import type {
  AdminUserSummary,
  AuditLogEntry,
  AuthUser,
  BenchmarkTrendItem,
  OpsOverview,
  RetrievalProfileState,
  SystemLogEntry,
} from "@/types/api";

type Props = { user: AuthUser | null; onLogout: () => Promise<void>; themeLabel: string; onThemeToggle: () => void };
type Section = "ops" | "rag" | "admins" | "users" | "audit" | "syslog";

const ROLE_OPTIONS = ["viewer", "analyst"];
const STATUS_OPTIONS = ["active", "disabled"];
const ACTION_KEYWORD_OPTIONS = [
  "auth.login",
  "auth.logout",
  "session.create",
  "session.delete",
  "query.stream",
  "document.upload",
  "document.delete",
  "prompt.create",
  "prompt.update",
  "prompt.delete",
  "admin.user.create",
  "admin.user.role_update",
  "admin.user.status_update",
  "admin.user.classification_update",
  "admin.user.password_reset",
  "admin.user.approval_token_reset",
];

export function AdminPage({ user, onLogout, themeLabel, onThemeToggle }: Props) {
  const [section, setSection] = useState<Section>("ops");
  const [users, setUsers] = useState<AdminUserSummary[]>([]);
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [systemLogs, setSystemLogs] = useState<SystemLogEntry[]>([]);
  const [ops, setOps] = useState<OpsOverview | null>(null);
  const [statusText, setStatusText] = useState("");
  const [error, setError] = useState("");

  const [loadingUsers, setLoadingUsers] = useState(false);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [loadingSystemLogs, setLoadingSystemLogs] = useState(false);
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
  const [systemLogLimit, setSystemLogLimit] = useState(200);
  const [systemLogLevel, setSystemLogLevel] = useState("");
  const [systemLogLogger, setSystemLogLogger] = useState("");
  const [systemLogKeyword, setSystemLogKeyword] = useState("");

  const [opsHours, setOpsHours] = useState(24);
  const [opsActorUserId, setOpsActorUserId] = useState("");
  const [opsActionKeyword, setOpsActionKeyword] = useState("");
  const [opsAutoRefresh, setOpsAutoRefresh] = useState(true);
  const [profileState, setProfileState] = useState<RetrievalProfileState | null>(null);
  const [benchmarkTrends, setBenchmarkTrends] = useState<BenchmarkTrendItem[]>([]);
  const [benchmarkRunning, setBenchmarkRunning] = useState(false);
  const [canaryEnabled, setCanaryEnabled] = useState(false);
  const [canaryBaseline, setCanaryBaseline] = useState(0);
  const [canarySafe, setCanarySafe] = useState(0);
  const [canarySeed, setCanarySeed] = useState("default");

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

  const resolveActorUserId = (raw: string) => {
    const value = raw.trim();
    if (!value) return undefined;
    const exactId = users.find((u) => u.user_id === value);
    if (exactId) return exactId.user_id;
    const byUsername = users.find((u) => (u.username || "").toLowerCase() === value.toLowerCase());
    if (byUsername) return byUsername.user_id;
    const fuzzy = users.filter((u) => (u.username || "").toLowerCase().includes(value.toLowerCase()));
    if (fuzzy.length === 1) return fuzzy[0].user_id;
    return value;
  };

  const resolveActorUserIdForAudit = (raw: string) => {
    const value = raw.trim();
    if (!value) return undefined;
    const exactId = users.find((u) => u.user_id === value);
    if (exactId) return exactId.user_id;
    const exactName = users.find((u) => (u.username || "").toLowerCase() === value.toLowerCase());
    if (exactName) return exactName.user_id;
    const fuzzy = users.filter((u) => (u.username || "").toLowerCase().includes(value.toLowerCase()));
    if (fuzzy.length === 1) return fuzzy[0].user_id;
    if (/^[a-zA-Z0-9_-]{16,}$/.test(value)) return value;
    return undefined;
  };

  const formatAuditTime = (ts?: string | null) => {
    if (!ts) return "-";
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return ts;
    return new Intl.DateTimeFormat("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(d);
  };

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
  const recentFailures = ops?.diagnostics?.recent_failures ?? [];
  const recentErrors = ops?.diagnostics?.recent_errors ?? [];

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
      const rawActor = auditActorUserId.trim();
      const resolvedActorId = resolveActorUserIdForAudit(rawActor);
      let rows = await appApi.adminAudit({
        limit: auditLimit,
        actorUserId: resolvedActorId,
        actionKeyword: auditActionKeyword.trim() || undefined,
        eventCategory: auditEventCategory.trim() || undefined,
        severity: auditSeverity.trim() || undefined,
        result: auditResult.trim() || undefined,
      });

      // If actor input is a fuzzy name (not a resolvable ID), do client-side actor matching.
      if (rawActor && !resolvedActorId) {
        const q = rawActor.toLowerCase();
        rows = rows.filter((x) => {
          const uid = (x.actor_user_id || "").toLowerCase();
          const uname = (users.find((u) => u.user_id === x.actor_user_id)?.username || "").toLowerCase();
          return uid.includes(q) || uname.includes(q);
        });
      }

      setLogs(rows);
      setError("");
    } catch (e) {
      await handleApiError(e, "加载审计日志失败");
    } finally {
      setLoadingLogs(false);
    }
  };

  const loadSystemLogs = async () => {
    if (!isAdmin) return;
    setLoadingSystemLogs(true);
    try {
      const res = await appApi.adminSystemLogs({
        limit: systemLogLimit,
        level: systemLogLevel.trim() || undefined,
        logger: systemLogLogger.trim() || undefined,
        keyword: systemLogKeyword.trim() || undefined,
      });
      setSystemLogs(res.items || []);
      setError("");
    } catch (e) {
      await handleApiError(e, "加载系统日志失败");
    } finally {
      setLoadingSystemLogs(false);
    }
  };

  const loadOps = async () => {
    if (!isAdmin) return;
    setLoadingOps(true);
    try {
      setOps(await appApi.adminOpsOverview({
        hours: opsHours,
        actorUserId: resolveActorUserId(opsActorUserId),
        actionKeyword: opsActionKeyword.trim() || undefined,
      }));
      setError("");
    } catch (e) {
      await handleApiError(e, "加载运维指标失败");
    } finally {
      setLoadingOps(false);
    }
  };

  const loadRagOps = async () => {
    if (!isAdmin) return;
    try {
      const state = await appApi.adminOpsRetrievalProfile();
      setProfileState(state);
      setCanaryEnabled(Boolean(state.canary?.enabled));
      setCanaryBaseline(Number(state.canary?.baseline_percent || 0));
      setCanarySafe(Number(state.canary?.safe_percent || 0));
      setCanarySeed(String(state.canary?.seed || "default"));
      const trends = await appApi.adminBenchmarkTrends({ limit: 30 });
      setBenchmarkTrends(trends.items || []);
      setError("");
    } catch (e) {
      await handleApiError(e, "加载 RAG 运维配置失败");
    }
  };

  const exportOpsCsv = async () => {
    try {
      const csv = await appApi.adminOpsExportCsv({
        hours: opsHours,
        actorUserId: resolveActorUserId(opsActorUserId),
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

  const setRetrievalProfile = async (profile: string, followDefault = false) => {
    try {
      const next = await appApi.adminOpsSetRetrievalProfile({ profile, followConfigDefault: followDefault });
      setProfileState(next);
      setStatusText(`已切换检索策略为 ${next.active_profile}`);
      setError("");
    } catch (e) {
      await handleApiError(e, "切换策略失败");
    }
  };

  const saveCanary = async () => {
    try {
      const next = await appApi.adminOpsSetCanary({
        enabled: canaryEnabled,
        baselinePercent: canaryBaseline,
        safePercent: canarySafe,
        seed: canarySeed.trim() || "default",
      });
      setProfileState(next);
      setStatusText("灰度发布配置已保存");
      setError("");
    } catch (e) {
      await handleApiError(e, "保存灰度配置失败");
    }
  };

  const runBenchmark = async () => {
    setBenchmarkRunning(true);
    try {
      const strategy = profileState?.active_profile || "advanced";
      await appApi.adminRunBenchmark({ maxQueries: 20, strategy });
      const trends = await appApi.adminBenchmarkTrends({ limit: 30 });
      setBenchmarkTrends(trends.items || []);
      setStatusText("基准任务完成，趋势已更新");
    } catch (e) {
      await handleApiError(e, "运行基准失败");
    } finally {
      setBenchmarkRunning(false);
    }
  };

  const reloadConfig = async () => {
    try {
      await appApi.adminReloadConfig();
      await loadRagOps();
      setStatusText("配置热加载成功");
    } catch (e) {
      await handleApiError(e, "配置热加载失败");
    }
  };

  const rollbackRuntime = async () => {
    try {
      const res = await appApi.adminOpsRollback();
      setProfileState(res.state);
      setCanaryEnabled(false);
      setCanaryBaseline(0);
      setCanarySafe(0);
      setStatusText("已执行一键回滚（baseline）");
    } catch (e) {
      await handleApiError(e, "回滚失败");
    }
  };

  const exportAuditReportMd = async () => {
    try {
      const text = await appApi.adminOpsExportAuditReportMd({ hours: opsHours });
      const blob = new Blob([text], { type: "text/markdown;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ops_audit_report_${new Date().toISOString().replace(/[:.]/g, "-")}.md`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setStatusText("审计 Markdown 报告导出成功");
    } catch (e) {
      await handleApiError(e, "导出审计报告失败");
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
      setStatusText(`管理员已创建：${created.username}（ID: ${created.user_id}）`);
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
    void loadSystemLogs();
    void loadOps();
    void loadRagOps();
    // eslint-disable-next-line
  }, [isAdmin]);

  useEffect(() => {
    if (isAdmin) void loadLogs();
    // eslint-disable-next-line
  }, [auditLimit, auditActorUserId, auditActionKeyword, auditEventCategory, auditSeverity, auditResult, users.length]);

  useEffect(() => {
    if (isAdmin) void loadOps();
    // eslint-disable-next-line
  }, [opsHours, opsActorUserId, opsActionKeyword]);

  useEffect(() => {
    if (isAdmin) void loadSystemLogs();
    // eslint-disable-next-line
  }, [systemLogLimit, systemLogLevel, systemLogLogger, systemLogKeyword]);

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
              <button type="button" className={section === "rag" ? "" : "secondary"} onClick={() => setSection("rag")}>RAG/Agent 运维</button>
              <button type="button" className={section === "admins" ? "" : "secondary"} onClick={() => setSection("admins")}>创建管理员</button>
              <button type="button" className={section === "users" ? "" : "secondary"} onClick={() => setSection("users")}>用户管理</button>
              <button type="button" className={section === "audit" ? "" : "secondary"} onClick={() => setSection("audit")}>审计日志</button>
              <button type="button" className={section === "syslog" ? "" : "secondary"} onClick={() => setSection("syslog")}>系统日志</button>
            </div>
          </main>

          {section === "admins" && <main className="panel admin-create-panel">
            <div className="section-head"><strong>创建管理员</strong></div>
            <p className="muted admin-create-hint">请填写账号信息与审批信息。创建成功后会返回新管理员用户ID。</p>
            <div className="ops-two-col admin-create-grid">
              <label className="admin-field">
                <span>管理员用户名</span>
                <input placeholder="例如：sec_admin_01" value={adminUsername} onChange={(e) => setAdminUsername(e.target.value)} />
              </label>
              <label className="admin-field">
                <span>管理员密码</span>
                <input placeholder="至少 8 位" type="password" value={adminPassword} onChange={(e) => setAdminPassword(e.target.value)} />
              </label>
            </div>
            <div className="ops-two-col admin-create-grid">
              <label className="admin-field">
                <span>确认密码</span>
                <input placeholder="再次输入密码" type="password" value={adminPassword2} onChange={(e) => setAdminPassword2(e.target.value)} />
              </label>
              <label className="admin-field">
                <span>我的审批令牌</span>
                <input placeholder="当前管理员审批令牌" type="password" value={adminApprovalToken} onChange={(e) => setAdminApprovalToken(e.target.value)} />
              </label>
            </div>
            <div className="ops-two-col admin-create-grid">
              <label className="admin-field">
                <span>新管理员令牌</span>
                <input placeholder="至少 12 位" type="password" value={newAdminApprovalToken} onChange={(e) => setNewAdminApprovalToken(e.target.value)} />
              </label>
              <label className="admin-field">
                <span>工单号</span>
                <input placeholder="例如：SEC-2026-001" value={adminTicketId} onChange={(e) => setAdminTicketId(e.target.value)} />
              </label>
            </div>
            <div className="ops-two-col admin-create-grid">
              <label className="admin-field">
                <span>创建原因</span>
                <input placeholder="请输入创建原因（至少 5 个字符）" value={adminReason} onChange={(e) => setAdminReason(e.target.value)} />
              </label>
              <div className="admin-create-actions">
                <button type="button" disabled={creatingAdmin} onClick={() => void createAdmin()}>
                  {creatingAdmin ? "创建中..." : "创建管理员"}
                </button>
              </div>
            </div>
          </main>}

          {section === "ops" && <main className="panel ops-wrap">
            <div className="section-head"><strong>系统监控</strong><div className="row-actions"><button type="button" className="secondary tiny-btn" onClick={() => void loadOps()}>刷新</button><button type="button" className="secondary tiny-btn" onClick={() => void exportOpsCsv()}>导出 CSV</button></div></div>
            <div className="ops-two-col ops-controls-row"><select value={opsHours} onChange={(e) => setOpsHours(Number(e.target.value) || 24)}><option value={1}>1小时</option><option value={6}>6小时</option><option value={24}>24小时</option><option value={72}>72小时</option><option value={168}>7天</option></select><label className="ops-auto-refresh"><input type="checkbox" checked={opsAutoRefresh} onChange={(e) => setOpsAutoRefresh(e.target.checked)} /><span>每 30 秒自动刷新</span></label></div>
            <div className="ops-two-col ops-filter-row"><input list="actor-user-options" placeholder="执行者用户ID或用户名（可选）" value={opsActorUserId} onChange={(e) => setOpsActorUserId(e.target.value)} /><select value={opsActionKeyword} onChange={(e) => setOpsActionKeyword(e.target.value)}><option value="">全部动作（可选）</option>{ACTION_KEYWORD_OPTIONS.map((x) => <option key={`ops-${x}`} value={x}>{x}</option>)}</select></div>
            <p className="muted" style={{ marginTop: -2 }}>
              筛选说明：`执行者` 支持填用户ID或用户名（系统会自动换算为用户ID）；`动作关键字` 用于筛选动作名。两个都不填表示查看全部。
            </p>
            {loadingOps && <div className="skeleton-list" />}
            {!loadingOps && ops && <>
              <div className="ops-kpi-grid ops-kpi-grid-primary">
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
              <div className="ops-kpi-grid ops-kpi-grid-secondary">
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
              <div className="section-head" style={{ marginTop: 4 }}>
                <strong>运行诊断</strong>
              </div>
              <p className="muted" style={{ marginTop: -2, marginBottom: 8 }}>
                用于排查“后端进程 / 环境 / 连接中断”类问题，直接展示当前解释器、Conda 环境、模型配置和最近错误。
              </p>
              <div className="ops-two-col">
                <div className="ops-trend-list">
                  <strong>环境与模型</strong>
                  <div className="ops-diagnostic-list">
                    <div><span>Python</span><code>{ops.diagnostics?.python_executable || "-"}</code></div>
                    <div><span>Python 版本</span><code>{ops.diagnostics?.python_version || "-"}</code></div>
                    <div><span>Conda 环境</span><code>{ops.diagnostics?.conda_env || "-"}</code></div>
                    <div><span>Conda Prefix</span><code>{ops.diagnostics?.conda_prefix || "-"}</code></div>
                    <div><span>模型后端</span><code>{ops.diagnostics?.model_backend || "-"}</code></div>
                    <div><span>推理后端</span><code>{ops.diagnostics?.reasoning_model_backend || "-"}</code></div>
                    <div><span>Ollama URL</span><code>{ops.diagnostics?.ollama_base_url || "-"}</code></div>
                    <div><span>聊天模型</span><code>{ops.diagnostics?.ollama_chat_model || "-"}</code></div>
                    <div><span>Embedding</span><code>{ops.diagnostics?.ollama_embed_model || "-"}</code></div>
                  </div>
                </div>
                <div className="ops-trend-list">
                  <strong>关键服务细节</strong>
                  <div className="ops-diagnostic-list">
                    {Object.entries(ops.services || {}).map(([name, svc]) => (
                      <div key={`svc-detail-${name}`}>
                        <span>{name}</span>
                        <code>
                          {svc.ok ? "ok" : `error=${svc.error || "unknown"}`}
                          {svc.path ? ` | ${svc.path}` : ""}
                          {svc.models && svc.models.length > 0 ? ` | models=${svc.models.join(", ")}` : ""}
                        </code>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="section-head" style={{ marginTop: 4 }}>
                <strong>最近失败请求</strong>
              </div>
              <table className="table">
                <thead><tr><th>时间</th><th>路径</th><th>状态码</th><th>耗时</th><th>错误</th></tr></thead>
                <tbody>
                  {(recentFailures.length > 0 ? recentFailures : []).map((x, idx) => (
                    <tr key={`${x.ts}-${idx}`}>
                      <td>{x.ts}</td>
                      <td>{x.path}</td>
                      <td>{x.status_code}</td>
                      <td>{x.duration_ms}</td>
                      <td>{x.error || "-"}</td>
                    </tr>
                  ))}
                  {recentFailures.length === 0 && (
                    <tr><td colSpan={5}>暂无失败请求</td></tr>
                  )}
                </tbody>
              </table>
              <div className="section-head" style={{ marginTop: 4 }}>
                <strong>最近严重错误</strong>
              </div>
              <table className="table">
                <thead><tr><th>时间</th><th>Logger</th><th>消息</th><th>异常</th></tr></thead>
                <tbody>
                  {(recentErrors.length > 0 ? recentErrors : []).map((x, idx) => (
                    <tr key={`${x.created_at}-${idx}`}>
                      <td>{formatAuditTime(x.created_at)}</td>
                      <td>{x.logger || "-"}</td>
                      <td>{x.message || "-"}</td>
                      <td title={x.exception || "-"}>{x.exception || "-"}</td>
                    </tr>
                  ))}
                  {recentErrors.length === 0 && (
                    <tr><td colSpan={4}>暂无严重错误</td></tr>
                  )}
                </tbody>
              </table>
              <div className="ops-trend-list"><strong>按小时趋势</strong>{ops.hourly.map((x) => <div key={x.bucket} className="ops-trend-row"><span>{x.bucket.slice(11, 16)}</span><div className="ops-trend-bar"><div className="ops-trend-fill" style={{ width: `${Math.max(4, (x.count / hourlyMax) * 100)}%` }} /></div><strong>{x.count}/{x.errors}</strong></div>)}</div>
              <div className="section-head" style={{ marginTop: 4 }}>
                <strong>慢请求列表</strong>
              </div>
              <p className="muted" style={{ marginTop: -2, marginBottom: 8 }}>
                展示当前时间窗口内耗时较高的接口请求，用于排查性能瓶颈。时间为服务器记录时间，耗时单位为毫秒（ms）。
              </p>
              <table className="table"><thead><tr><th>时间</th><th>方法</th><th>路径</th><th>状态码</th><th>耗时</th><th>错误</th></tr></thead><tbody>{ops.slow_requests.map((x, idx) => <tr key={`${x.ts}-${idx}`}><td>{x.ts}</td><td>{x.method}</td><td>{x.path}</td><td>{x.status_code}</td><td>{x.duration_ms}</td><td>{x.error || "-"}</td></tr>)}</tbody></table>
            </>}
          </main>}

          {section === "rag" && <main className="panel ops-wrap">
            <div className="section-head">
              <strong>RAG / Agent 策略运营</strong>
              <div className="row-actions">
                <button type="button" className="secondary tiny-btn" onClick={() => void loadRagOps()}>刷新</button>
                <button type="button" className="secondary tiny-btn" onClick={() => void reloadConfig()}>热加载配置</button>
                <button type="button" className="secondary tiny-btn" onClick={() => void rollbackRuntime()}>一键回滚</button>
                <button type="button" className="secondary tiny-btn" onClick={() => void exportAuditReportMd()}>导出审计报告(MD)</button>
              </div>
            </div>

            <p className="muted">这里集中管理检索策略、灰度发布和基准趋势。策略默认参考 RAGFlow 的 baseline / advanced / safe。</p>
            <div className="ops-kpi-grid ops-kpi-grid-secondary">
              <div className="ops-kpi-card"><span>当前策略</span><strong>{profileState?.active_profile || "-"}</strong></div>
              <div className="ops-kpi-card"><span>配置默认</span><strong>{profileState?.config_default_profile || "-"}</strong></div>
              <div className="ops-kpi-card"><span>跟随配置</span><strong>{profileState?.follow_config_default ? "是" : "否"}</strong></div>
              <div className="ops-kpi-card"><span>上次更新时间</span><strong>{profileState?.updated_at ? formatAuditTime(profileState.updated_at) : "-"}</strong></div>
            </div>

            <div className="section-head" style={{ marginTop: 6 }}>
              <strong>策略配置</strong>
            </div>
            <div className="row-actions wrap">
              <button type="button" onClick={() => void setRetrievalProfile("advanced")}>切换 Advanced</button>
              <button type="button" className="secondary" onClick={() => void setRetrievalProfile("baseline")}>切换 Baseline</button>
              <button type="button" className="secondary" onClick={() => void setRetrievalProfile("safe")}>切换 Safe</button>
              <button type="button" className="secondary" onClick={() => void setRetrievalProfile("advanced", true)}>跟随配置默认</button>
            </div>

            <div className="section-head" style={{ marginTop: 8 }}>
              <strong>灰度发布（Canary）</strong>
            </div>
            <div className="ops-two-col">
              <label className="ops-auto-refresh">
                <input type="checkbox" checked={canaryEnabled} onChange={(e) => setCanaryEnabled(e.target.checked)} />
                <span>启用灰度分流</span>
              </label>
              <input placeholder="seed" value={canarySeed} onChange={(e) => setCanarySeed(e.target.value)} />
            </div>
            <div className="ops-two-col">
              <label className="admin-field">
                <span>Baseline 百分比</span>
                <input type="number" min={0} max={100} value={canaryBaseline} onChange={(e) => setCanaryBaseline(Number(e.target.value) || 0)} />
              </label>
              <label className="admin-field">
                <span>Safe 百分比</span>
                <input type="number" min={0} max={100} value={canarySafe} onChange={(e) => setCanarySafe(Number(e.target.value) || 0)} />
              </label>
            </div>
            <div className="row-actions">
              <button type="button" onClick={() => void saveCanary()}>保存灰度配置</button>
            </div>

            <div className="section-head" style={{ marginTop: 8 }}>
              <strong>真实基准趋势</strong>
              <div className="row-actions">
                <button type="button" className="secondary tiny-btn" disabled={benchmarkRunning} onClick={() => void runBenchmark()}>
                  {benchmarkRunning ? "运行中..." : "运行基准"}
                </button>
              </div>
            </div>
            {benchmarkTrends.length === 0 && <p className="muted">暂无趋势数据。点击“运行基准”后会自动记录。</p>}
            {benchmarkTrends.length > 0 && (
              <table className="table">
                <thead><tr><th>时间</th><th>策略</th><th>样本数</th><th>P50(ms)</th><th>P95(ms)</th><th>Grounding(avg)</th><th>Citations(avg)</th></tr></thead>
                <tbody>
                  {[...benchmarkTrends].reverse().map((x, idx) => (
                    <tr key={`${x.created_at}-${idx}`}>
                      <td>{formatAuditTime(x.created_at)}</td>
                      <td>{x.strategy}</td>
                      <td>{x.num_queries}</td>
                      <td>{x.latency_ms?.p50 ?? "-"}</td>
                      <td>{x.latency_ms?.p95 ?? "-"}</td>
                      <td>{x.grounding_support_ratio?.avg ?? "-"}</td>
                      <td>{x.citations?.avg ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </main>}

          {section === "users" && <main className="panel admin-users-panel">
            <div className="section-head">
              <strong>用户管理</strong>
              <button type="button" className="secondary tiny-btn" onClick={() => void loadUsers()}>刷新</button>
            </div>
            <p className="muted admin-users-hint">可按用户ID/用户名筛选，并直接执行角色、状态和安全操作。</p>

            <div className="ops-two-col admin-filter-grid">
              <label className="admin-field">
                <span>搜索</span>
                <input placeholder="搜索用户名 / 用户ID / 分类字段" value={kw} onChange={(e) => setKw(e.target.value)} />
              </label>
              <label className="admin-field">
                <span>角色</span>
                <select value={fRole} onChange={(e) => setFRole(e.target.value)}>
                  <option value="">全部角色</option>
                  <option value="admin">admin</option>
                  <option value="analyst">analyst</option>
                  <option value="viewer">viewer</option>
                </select>
              </label>
            </div>

            <div className="ops-two-col admin-filter-grid">
              <label className="admin-field">
                <span>状态</span>
                <select value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
                  <option value="">全部状态</option>
                  <option value="active">active</option>
                  <option value="disabled">disabled</option>
                </select>
              </label>
              <label className="admin-field">
                <span>在线状态</span>
                <select value={fOnline} onChange={(e) => setFOnline(e.target.value)}>
                  <option value="">全部在线状态</option>
                  <option value="online_10m">10分钟内在线</option>
                  <option value="online">在线</option>
                  <option value="offline">离线</option>
                </select>
              </label>
            </div>

            {editingUser && <div className="panel" style={{ marginBottom: 12 }}><div className="section-head"><strong>用户分类：{editingUser.username}</strong><button type="button" className="secondary tiny-btn" onClick={() => setEditingUser(null)}>取消</button></div><div className="ops-two-col"><input placeholder="业务单元" value={editBu} onChange={(e) => setEditBu(e.target.value)} /><input placeholder="部门" value={editDept} onChange={(e) => setEditDept(e.target.value)} /></div><div className="ops-two-col"><input placeholder="用户类型" value={editType} onChange={(e) => setEditType(e.target.value)} /><input placeholder="数据范围" value={editScope} onChange={(e) => setEditScope(e.target.value)} /></div><div className="row-actions"><button type="button" disabled={savingClass} onClick={() => void saveClass()}>{savingClass ? "保存中..." : "保存分类"}</button></div></div>}
            {loadingUsers && <div className="skeleton-list" />}
            {!loadingUsers && <table className="table admin-user-table"><thead><tr><th>用户ID</th><th>用户名</th><th>角色</th><th>状态</th><th>在线</th><th>10分钟</th><th>业务单元</th><th>部门</th><th>类型</th><th>范围</th><th>创建人</th><th>工单</th><th>令牌</th><th>操作</th></tr></thead><tbody>{filteredUsers.map((row) => <tr key={row.user_id}><td className="admin-user-id">{row.user_id}</td><td className="admin-username">{row.username}</td><td><select value={row.role} onChange={(e) => void updateRole(row, e.target.value)}>{([...(row.role === "admin" ? ["admin"] : []), ...ROLE_OPTIONS] as string[]).map((x) => <option key={x} value={x}>{x}</option>)}</select></td><td><select value={row.status} onChange={(e) => void updateStatus(row, e.target.value)}>{STATUS_OPTIONS.map((x) => <option key={x} value={x}>{x}</option>)}</select></td><td>{row.is_online ? "在线" : "离线"}</td><td>{row.is_online_10m ? "活跃" : "-"}</td><td>{row.business_unit || "-"}</td><td>{row.department || "-"}</td><td>{row.user_type || "-"}</td><td>{row.data_scope || "-"}</td><td>{row.created_by_username || row.created_by_user_id || "-"}</td><td>{row.admin_ticket_id || "-"}</td><td>{row.has_admin_approval_token ? "已设置" : "未设置"}</td><td><div className="row-actions user-row-actions"><button type="button" className="secondary tiny-btn" onClick={() => openClassEditor(row)}>分类</button><button type="button" className="secondary tiny-btn" onClick={() => void resetUserPassword(row)}>重置密码</button>{(row.role || "").toLowerCase() === "admin" ? <button type="button" className="secondary tiny-btn" onClick={() => void resetAdminApprovalToken(row)}>重置令牌</button> : null}</div></td></tr>)}</tbody></table>}
          </main>}

          {section === "audit" && <main className="panel admin-audit-panel">
            <div className="section-head">
              <strong>审计日志</strong>
              <div className="row-actions admin-audit-head-actions">
                <select value={auditLimit} onChange={(e) => setAuditLimit(Number(e.target.value) || 200)}>
                  <option value={100}>最近 100 条</option>
                  <option value={200}>最近 200 条</option>
                  <option value={500}>最近 500 条</option>
                </select>
                <button type="button" className="secondary tiny-btn" onClick={() => void loadLogs()}>刷新</button>
              </div>
            </div>
            <p className="muted admin-audit-hint">可按执行者、动作、分类、级别和结果筛选日志；用于回溯操作行为与安全审计。</p>
            {!!auditActorUserId.trim() && !users.some((u) => (u.username || "").toLowerCase() === auditActorUserId.trim().toLowerCase() || u.user_id === auditActorUserId.trim()) && (
              <p className="muted admin-audit-hint" style={{ marginTop: -6 }}>
                当前执行者未精确匹配用户，系统将按“用户名或用户ID包含关系”继续筛选。
              </p>
            )}
            <div className="ops-two-col admin-filter-grid">
              <label className="admin-field">
                <span>执行者</span>
                <input list="actor-user-options" placeholder="执行者用户ID或用户名" value={auditActorUserId} onChange={(e) => setAuditActorUserId(e.target.value)} />
              </label>
              <label className="admin-field">
                <span>动作</span>
                <select value={auditActionKeyword} onChange={(e) => setAuditActionKeyword(e.target.value)}><option value="">全部动作（可选）</option>{ACTION_KEYWORD_OPTIONS.map((x) => <option key={`audit-${x}`} value={x}>{x}</option>)}</select>
              </label>
            </div>
            <div className="ops-two-col admin-filter-grid">
              <label className="admin-field">
                <span>分类</span>
                <select value={auditEventCategory} onChange={(e) => setAuditEventCategory(e.target.value)}><option value="">全部分类</option><option value="auth">auth</option><option value="admin">admin</option><option value="data">data</option><option value="prompt">prompt</option><option value="system">system</option></select>
              </label>
              <label className="admin-field">
                <span>级别</span>
                <select value={auditSeverity} onChange={(e) => setAuditSeverity(e.target.value)}><option value="">全部级别</option><option value="info">info</option><option value="medium">medium</option><option value="high">high</option></select>
              </label>
            </div>
            <div className="ops-two-col admin-filter-grid">
              <label className="admin-field">
                <span>结果</span>
                <select value={auditResult} onChange={(e) => setAuditResult(e.target.value)}><option value="">全部结果</option><option value="success">success</option><option value="failed">failed</option><option value="denied">denied</option></select>
              </label>
              <div className="row-actions admin-audit-quick-actions">
                <button type="button" className="secondary tiny-btn" onClick={() => setAuditResult("failed")}>仅失败</button>
                <button type="button" className="secondary tiny-btn" onClick={() => setAuditSeverity("high")}>仅高危</button>
                <button type="button" className="secondary tiny-btn" onClick={() => { setAuditActorUserId(""); setAuditActionKeyword(""); setAuditEventCategory(""); setAuditSeverity(""); setAuditResult(""); }}>清空</button>
              </div>
            </div>
            {loadingLogs && <div className="skeleton-list" />}
            {!loadingLogs && (
              <p className="muted admin-audit-scroll-hint">表格支持左右滑动查看完整列，不必在一屏内展示全部内容。</p>
            )}
            {!loadingLogs && logs.length === 0 && (
              <div className="status">未命中审计数据。可尝试清空“执行者 / 动作 / 分类 / 级别 / 结果”中的一个或多个筛选条件。</div>
            )}
            {!loadingLogs && (
              <div className="audit-table-wrap">
                <table className="table admin-audit-table">
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>执行者</th>
                      <th>动作</th>
                      <th>分类</th>
                      <th>级别</th>
                      <th>资源</th>
                      <th>结果</th>
                      <th>IP</th>
                      <th>User-Agent</th>
                      <th>详情</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((x) => (
                      <tr key={x.event_id}>
                        <td className="audit-time">{formatAuditTime(x.created_at)}</td>
                        <td className="audit-actor">
                          <div className="audit-cell-stack">
                            <span className="audit-id" title={x.actor_user_id || "-"}>{x.actor_user_id || "-"}</span>
                            <span className="audit-sub">role: {x.actor_role || "-"}</span>
                          </div>
                        </td>
                        <td className="audit-action">
                          <span className="audit-code" title={x.action || "-"}>{x.action || "-"}</span>
                        </td>
                        <td>
                          <span className="audit-badge">{x.event_category || "-"}</span>
                        </td>
                        <td>
                          <span className={`audit-badge audit-severity-${(x.severity || "none").toLowerCase()}`}>{x.severity || "-"}</span>
                        </td>
                        <td className="audit-resource">
                          <div className="audit-cell-stack">
                            <span className="audit-code" title={x.resource_type || "-"}>{x.resource_type || "-"}</span>
                            <span className="audit-sub" title={x.resource_id || "-"}>{x.resource_id || "-"}</span>
                          </div>
                        </td>
                        <td>
                          <span className={`audit-badge audit-result-${(x.result || "none").toLowerCase()}`}>{x.result || "-"}</span>
                        </td>
                        <td className="audit-ip">{x.ip || "-"}</td>
                        <td className="audit-user-agent" title={x.user_agent || "-"}>{x.user_agent || "-"}</td>
                        <td className="audit-detail" title={x.detail || "-"}>{x.detail || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </main>}

          {section === "syslog" && <main className="panel admin-audit-panel">
            <div className="section-head">
              <strong>系统日志</strong>
              <div className="row-actions admin-audit-head-actions">
                <select value={systemLogLimit} onChange={(e) => setSystemLogLimit(Number(e.target.value) || 200)}>
                  <option value={100}>最近 100 条</option>
                  <option value={200}>最近 200 条</option>
                  <option value={500}>最近 500 条</option>
                </select>
                <button type="button" className="secondary tiny-btn" onClick={() => void loadSystemLogs()}>刷新</button>
              </div>
            </div>
            <p className="muted admin-audit-hint">展示应用运行日志（含错误堆栈），用于管理层查看系统健康与异常。</p>
            <div className="ops-two-col admin-filter-grid">
              <label className="admin-field">
                <span>级别</span>
                <select value={systemLogLevel} onChange={(e) => setSystemLogLevel(e.target.value)}>
                  <option value="">全部级别</option>
                  <option value="INFO">INFO</option>
                  <option value="WARNING">WARNING</option>
                  <option value="ERROR">ERROR</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </label>
              <label className="admin-field">
                <span>Logger</span>
                <input placeholder="例如 app.graph.streaming" value={systemLogLogger} onChange={(e) => setSystemLogLogger(e.target.value)} />
              </label>
            </div>
            <div className="ops-two-col admin-filter-grid">
              <label className="admin-field">
                <span>关键词</span>
                <input placeholder="关键字（message/exception）" value={systemLogKeyword} onChange={(e) => setSystemLogKeyword(e.target.value)} />
              </label>
              <div className="row-actions admin-audit-quick-actions">
                <button
                  type="button"
                  className="secondary tiny-btn"
                  onClick={() => {
                    setSystemLogLevel("");
                    setSystemLogLogger("");
                    setSystemLogKeyword("");
                  }}
                >
                  清空
                </button>
              </div>
            </div>
            {loadingSystemLogs && <div className="skeleton-list" />}
            {!loadingSystemLogs && systemLogs.length === 0 && <div className="status">未命中系统日志。</div>}
            {!loadingSystemLogs && systemLogs.length > 0 && (
              <div className="audit-table-wrap">
                <table className="table admin-audit-table">
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>级别</th>
                      <th>Logger</th>
                      <th>位置</th>
                      <th>消息</th>
                      <th>异常</th>
                    </tr>
                  </thead>
                  <tbody>
                    {systemLogs.map((x, idx) => (
                      <tr key={`${x.created_at}-${idx}`}>
                        <td className="audit-time">{formatAuditTime(x.created_at)}</td>
                        <td>
                          <span className={`audit-badge audit-severity-${String(x.level || "info").toLowerCase() === "error" ? "high" : "info"}`}>
                            {x.level || "-"}
                          </span>
                        </td>
                        <td className="audit-code" title={x.logger || "-"}>{x.logger || "-"}</td>
                        <td className="audit-code" title={`${x.module || "-"}:${x.line || 0}`}>
                          {(x.module || "-") + ":" + String(x.line || 0)}
                        </td>
                        <td className="audit-detail" title={x.message || "-"}>{x.message || "-"}</td>
                        <td className="audit-detail" title={x.exception || "-"}>{x.exception || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </main>}

          <datalist id="actor-user-options">
            {users.map((u) => (
              <option key={`actor-user-${u.user_id}`} value={u.username}>
                {`${u.username} (${u.user_id})`}
              </option>
            ))}
            {users.map((u) => (
              <option key={`actor-id-${u.user_id}`} value={u.user_id}>
                {`${u.username} (${u.user_id})`}
              </option>
            ))}
          </datalist>
        </>
      )}

      {statusText && <div className="status">{statusText}</div>}
      {error && <div className="status error">{error}</div>}
    </div>
  );
}
