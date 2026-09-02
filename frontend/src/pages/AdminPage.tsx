import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { LanguageToggle } from "@/components/LanguageToggle";
import type { AuthUser } from "@/types/api";
import { AdminAgentQualityDashboard } from "@/pages/admin/AdminAgentQualityDashboard";
import { AdminAuditLogManagement } from "@/pages/admin/AdminAuditLogManagement";
import { AdminCreateForm } from "@/pages/admin/AdminCreateForm";
import { AdminModelSettings } from "@/pages/admin/AdminModelSettings";
import { AdminOpsOverview } from "@/pages/admin/AdminOpsOverview";
import { AdminRagSettings } from "@/pages/admin/AdminRagSettings";
import { AdminSystemLogTable } from "@/pages/admin/AdminSystemLogTable";
import { AdminSystemMonitor } from "@/pages/admin/AdminSystemMonitor";
import { AdminUserManagement } from "@/pages/admin/AdminUserManagement";
import { AdminWebActivityDashboard } from "@/pages/admin/AdminWebActivityDashboard";
import { useAdminActions } from "@/pages/admin/useAdminActions";
import { useAdminState } from "@/pages/admin/useAdminState";
import { formatAuditTime } from "@/pages/admin/utils";
import { ROLE_OPTIONS, STATUS_OPTIONS, ACTION_KEYWORD_OPTIONS } from "@/pages/admin/constants";
import { PromptDialog } from "@/components/PromptDialog";
import { usePromptDialog } from "@/hooks/usePromptDialog";

// Route-specific CSS (code-split by Vite)
import "@/styles/pages/admin-entry.css";

type Props = {
  user: AuthUser | null;
  onLogout: () => Promise<void>;
};

export function AdminPage({ user, onLogout }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const state = useAdminState();
  const isAdmin = useMemo(() => (user?.role || "").toLowerCase() === "admin", [user?.role]);
  const promptDialog = usePromptDialog();
  // Pagination state for audit logs
  const [auditPage, setAuditPage] = useState(1);
  const [auditPageSize, setAuditPageSize] = useState(20);

  // Pagination state for system logs
  const [systemLogCurrentPage, setSystemLogCurrentPage] = useState(1);
  const [systemLogPageSize, setSystemLogPageSize] = useState(20);

  const actions = useAdminActions({
    ...state,
    isAdmin,
    onLogout,
    promptInput: promptDialog.promptInput,
  });

  const actionMax = useMemo(() => Math.max(1, ...(state.ops?.top_actions || []).map((x) => x.count)), [state.ops]);
  const resourceMax = useMemo(() => Math.max(1, ...(state.ops?.top_resource_types || []).map((x) => x.count)), [state.ops]);
  const errorMax = useMemo(() => Math.max(1, ...(state.ops?.top_error_reasons || []).map((x) => x.count)), [state.ops]);
  const hourlyMax = useMemo(() => Math.max(1, ...(state.ops?.hourly || []).map((x) => x.count)), [state.ops]);

  const openClassEditor = (u: typeof state.users[0]) => {
    state.setEditingUser(u);
    state.setEditBu(u.business_unit || "");
    state.setEditDept(u.department || "");
    state.setEditType(u.user_type || "");
    state.setEditScope(u.data_scope || "");
  };

  useEffect(() => {
    void actions.loadUsers();
    void actions.loadLogs();
    void actions.loadSystemLogs();
    void actions.loadOps();
    void actions.loadRagOps();
    void actions.loadModelSettings();
    // eslint-disable-next-line
  }, [isAdmin]);

  useEffect(() => {
    if (isAdmin) void actions.loadLogs();
    // eslint-disable-next-line
  }, [state.auditLimit, state.auditActorUserId, state.auditActionKeyword, state.auditEventCategory, state.auditSeverity, state.auditResult, state.users.length]);

  useEffect(() => {
    if (isAdmin) void actions.loadOps();
    // eslint-disable-next-line
  }, [state.opsHours, state.opsActorUserId, state.opsActionKeyword]);

  useEffect(() => {
    if (isAdmin) void actions.loadSystemLogs();
    // eslint-disable-next-line
  }, [state.systemLogLimit, state.systemLogLevel, state.systemLogLogger, state.systemLogKeyword]);

  useEffect(() => {
    if (!isAdmin || state.section !== "ops" || !state.opsAutoRefresh) return;
    const t = window.setInterval(() => void actions.loadOps(), 30000);
    return () => window.clearInterval(t);
    // eslint-disable-next-line
  }, [isAdmin, state.section, state.opsAutoRefresh, state.opsHours, state.opsActorUserId, state.opsActionKeyword]);

  // Reset audit pagination when filters change
  useEffect(() => {
    setAuditPage(1);
  }, [state.auditLimit, state.auditActorUserId, state.auditActionKeyword, state.auditEventCategory, state.auditSeverity, state.auditResult]);

  // Reset system log pagination when filters change
  useEffect(() => {
    setSystemLogCurrentPage(1);
  }, [state.systemLogLevel, state.systemLogLogger, state.systemLogKeyword]);

  return (
    <div className="admin-shell">
      <PromptDialog
        isOpen={promptDialog.isOpen}
        title={promptDialog.options?.title || ""}
        message={promptDialog.options?.message || ""}
        defaultValue={promptDialog.options?.defaultValue}
        inputType={promptDialog.options?.inputType}
        onConfirm={promptDialog.handleConfirm}
        onCancel={promptDialog.handleCancel}
      />
      <header className="topbar">
        <div>
          <h2>{t("pages.admin.console")}</h2>
          <p className="muted">{t("pages.admin.subtitle")}</p>
        </div>
        <div className="top-actions">
          <LanguageToggle />
          <button className="secondary" type="button" onClick={() => navigate('/app/analytics')}>
            {t("pages.admin.viewAnalytics")}
          </button>
          <Link className="secondary link-btn" to="/app">{t("pages.admin.backToChat")}</Link>
          <button type="button" className="primary-action-btn" onClick={() => void onLogout()}>
            {t("nav.logout")}
          </button>
        </div>
      </header>

      {!isAdmin && (
        <main className="panel">
          <div className="status error">{t("pages.admin.noPermission")}</div>
        </main>
      )}

      {isAdmin && (
        <>
          <main className="panel">
            <div className="row-actions wrap admin-section-tabs">
              <button type="button" className={state.section === "ops" ? "" : "secondary"} onClick={() => state.setSection("ops")}>{t("pages.admin.sections.ops")}</button>
              <button type="button" className={state.section === "monitor" ? "" : "secondary"} onClick={() => state.setSection("monitor")}>{t("pages.admin.sections.monitor", "Runtime Monitor")}</button>
              <button type="button" className={state.section === "rag" ? "" : "secondary"} onClick={() => state.setSection("rag")}>{t("pages.admin.sections.rag")}</button>
              <button type="button" className={state.section === "models" ? "" : "secondary"} onClick={() => state.setSection("models")}>{t("pages.admin.sections.models")}</button>
              <button type="button" className={state.section === "webactivity" ? "" : "secondary"} onClick={() => state.setSection("webactivity")}>{t("pages.admin.sections.webactivity", "Web Activity")}</button>
              <button type="button" className={state.section === "agentquality" ? "" : "secondary"} onClick={() => state.setSection("agentquality")}>{t("pages.admin.sections.agentquality", "Agent Quality")}</button>
              <button type="button" className={state.section === "admins" ? "" : "secondary"} onClick={() => state.setSection("admins")}>{t("pages.admin.sections.admins")}</button>
              <button type="button" className={state.section === "users" ? "" : "secondary"} onClick={() => state.setSection("users")}>{t("pages.admin.sections.users")}</button>
              <button type="button" className={state.section === "audit" ? "" : "secondary"} onClick={() => state.setSection("audit")}>{t("pages.admin.sections.audit")}</button>
              <button type="button" className={state.section === "syslog" ? "" : "secondary"} onClick={() => state.setSection("syslog")}>{t("pages.admin.sections.syslog")}</button>
            </div>
          </main>

          {state.section === "admins" && (
            <AdminCreateForm
              adminUsername={state.adminUsername}
              adminPassword={state.adminPassword}
              adminPassword2={state.adminPassword2}
              adminApprovalToken={state.adminApprovalToken}
              newAdminApprovalToken={state.newAdminApprovalToken}
              adminTicketId={state.adminTicketId}
              adminReason={state.adminReason}
              creatingAdmin={state.creatingAdmin}
              onAdminUsernameChange={state.setAdminUsername}
              onAdminPasswordChange={state.setAdminPassword}
              onAdminPassword2Change={state.setAdminPassword2}
              onAdminApprovalTokenChange={state.setAdminApprovalToken}
              onNewAdminApprovalTokenChange={state.setNewAdminApprovalToken}
              onAdminTicketIdChange={state.setAdminTicketId}
              onAdminReasonChange={state.setAdminReason}
              onCreateAdmin={() => void actions.createAdmin()}
            />
          )}


          {state.section === "monitor" && <AdminSystemMonitor />}
          {state.section === "ops" && (
            <AdminOpsOverview
              ops={state.ops}
              loading={state.loadingOps}
              opsHours={state.opsHours}
              opsAutoRefresh={state.opsAutoRefresh}
              opsActorUserId={state.opsActorUserId}
              opsActionKeyword={state.opsActionKeyword}
              actionKeywordOptions={ACTION_KEYWORD_OPTIONS}
              actionMax={actionMax}
              resourceMax={resourceMax}
              errorMax={errorMax}
              hourlyMax={hourlyMax}
              formatAuditTime={formatAuditTime}
              onRefresh={() => void actions.loadOps()}
              onExportCsv={() => void actions.exportOpsCsv()}
              onOpsHoursChange={state.setOpsHours}
              onOpsAutoRefreshChange={state.setOpsAutoRefresh}
              onOpsActorUserIdChange={state.setOpsActorUserId}
              onOpsActionKeywordChange={state.setOpsActionKeyword}
            />
          )}

          {state.section === "models" && (
            <AdminModelSettings
              modelSettings={state.modelSettings}
              modelLoading={state.modelLoading}
              modelSaving={state.modelSaving}
              modelTesting={state.modelTesting}
              modelTestResult={state.modelTestResult}
              onRefresh={() => void actions.loadModelSettings()}
              onSave={() => void actions.saveModelSettings()}
              onTest={() => void actions.testModelSettings()}
              onPatch={actions.patchModelSettings}
              modelApiKey={state.modelApiKey}
              onApiKeyChange={state.setModelApiKey}
            />
          )}

          {state.section === "rag" && (
            <AdminRagSettings
              benchmarkTrends={state.benchmarkTrends}
              benchmarkRunning={state.benchmarkRunning}
              onRefresh={() => void actions.loadRagOps()}
              onReloadConfig={() => void actions.reloadConfig()}
              onExportAuditReport={() => void actions.exportAuditReportMd()}
              onRunBenchmark={() => void actions.runBenchmark()}
              formatAuditTime={formatAuditTime}
            />
          )}

          {state.section === "users" && (
            <AdminUserManagement
              users={state.users}
              loadingUsers={state.loadingUsers}
              kw={state.kw}
              fRole={state.fRole}
              fStatus={state.fStatus}
              fOnline={state.fOnline}
              editingUser={state.editingUser}
              editBu={state.editBu}
              editDept={state.editDept}
              editType={state.editType}
              editScope={state.editScope}
              savingClass={state.savingClass}
              roleOptions={ROLE_OPTIONS}
              statusOptions={STATUS_OPTIONS}
              onKwChange={state.setKw}
              onFRoleChange={state.setFRole}
              onFStatusChange={state.setFStatus}
              onFOnlineChange={state.setFOnline}
              onEditingUserChange={state.setEditingUser}
              onEditBuChange={state.setEditBu}
              onEditDeptChange={state.setEditDept}
              onEditTypeChange={state.setEditType}
              onEditScopeChange={state.setEditScope}
              onLoadUsers={() => void actions.loadUsers()}
              onSaveClass={() => void actions.saveClass()}
              onUpdateRole={actions.updateRole}
              onUpdateStatus={actions.updateStatus}
              onAddCredits={actions.addUserCredits}
              onOpenClassEditor={openClassEditor}
              onResetPassword={actions.resetUserPassword}
              onResetApprovalToken={actions.resetAdminApprovalToken}
            />
          )}

          {state.section === "audit" && (
            <AdminAuditLogManagement
              logs={state.logs}
              users={state.users}
              loadingLogs={state.loadingLogs}
              auditLimit={state.auditLimit}
              auditActorUserId={state.auditActorUserId}
              auditActionKeyword={state.auditActionKeyword}
              auditEventCategory={state.auditEventCategory}
              auditSeverity={state.auditSeverity}
              auditResult={state.auditResult}
              formatAuditTime={formatAuditTime}
              onAuditLimitChange={state.setAuditLimit}
              onAuditActorUserIdChange={state.setAuditActorUserId}
              onAuditActionKeywordChange={state.setAuditActionKeyword}
              onAuditEventCategoryChange={state.setAuditEventCategory}
              onAuditSeverityChange={state.setAuditSeverity}
              onAuditResultChange={state.setAuditResult}
              onRefresh={() => void actions.loadLogs()}
              onClearFilters={() => {
                state.setAuditActorUserId("");
                state.setAuditActionKeyword("");
                state.setAuditEventCategory("");
                state.setAuditSeverity("");
                state.setAuditResult("");
              }}
              currentPage={auditPage}
              pageSize={auditPageSize}
              onPageChange={setAuditPage}
              onPageSizeChange={setAuditPageSize}
            />
          )}

          {state.section === "syslog" && (
            <AdminSystemLogTable
              systemLogs={state.systemLogs}
              loadingSystemLogs={state.loadingSystemLogs}
              systemLogLimit={state.systemLogLimit}
              systemLogLevel={state.systemLogLevel}
              systemLogLogger={state.systemLogLogger}
              systemLogKeyword={state.systemLogKeyword}
              formatAuditTime={formatAuditTime}
              onSystemLogLimitChange={state.setSystemLogLimit}
              onSystemLogLevelChange={state.setSystemLogLevel}
              onSystemLogLoggerChange={state.setSystemLogLogger}
              onSystemLogKeywordChange={state.setSystemLogKeyword}
              onRefresh={() => void actions.loadSystemLogs()}
              onClearFilters={() => {
                state.setSystemLogLevel("");
                state.setSystemLogLogger("");
                state.setSystemLogKeyword("");
              }}
              systemLogCurrentPage={systemLogCurrentPage}
              systemLogPageSize={systemLogPageSize}
              onSystemLogPageChange={setSystemLogCurrentPage}
              onSystemLogPageSizeChange={setSystemLogPageSize}
            />
          )}

          {state.section === "webactivity" && <AdminWebActivityDashboard />}

          {state.section === "agentquality" && <AdminAgentQualityDashboard />}

          <datalist id="actor-user-options">
            {state.users.map((u) => (
              <option key={`actor-user-${u.user_id}`} value={u.username}>
                {`${u.username} (${u.user_id})`}
              </option>
            ))}
            {state.users.map((u) => (
              <option key={`actor-id-${u.user_id}`} value={u.user_id}>
                {`${u.username} (${u.user_id})`}
              </option>
            ))}
          </datalist>
        </>
      )}

      {state.statusText && <div className="status">{state.statusText}</div>}
      {state.error && <div className="status error">{state.error}</div>}
    </div>
  );
}
