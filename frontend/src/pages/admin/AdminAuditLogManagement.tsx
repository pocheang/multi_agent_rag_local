import type { AdminUserSummary, AuditLogEntry } from "@/types/api";
import { useTranslation } from "react-i18next";
import { useMemo } from "react";
import { AdminAuditLogTable } from "@/pages/admin/AdminAuditLogTable";
import { AdminFormSelect } from "@/components/AdminFormField";
import { AdminPagination } from "@/components/AdminPagination";
import { ACTION_KEYWORD_OPTIONS } from "@/pages/admin/constants";


type Props = {
  logs: AuditLogEntry[];
  users: AdminUserSummary[];
  loadingLogs: boolean;
  auditLimit: number;
  auditActorUserId: string;
  auditActionKeyword: string;
  auditEventCategory: string;
  auditSeverity: string;
  auditResult: string;
  formatAuditTime: (ts?: string | null) => string;
  onAuditLimitChange: (value: number) => void;
  onAuditActorUserIdChange: (value: string) => void;
  onAuditActionKeywordChange: (value: string) => void;
  onAuditEventCategoryChange: (value: string) => void;
  onAuditSeverityChange: (value: string) => void;
  onAuditResultChange: (value: string) => void;
  onRefresh: () => void;
  onClearFilters: () => void;
  currentPage: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
};

export function AdminAuditLogManagement({
  logs,
  users,
  loadingLogs,
  auditLimit,
  auditActorUserId,
  auditActionKeyword,
  auditEventCategory,
  auditSeverity,
  auditResult,
  formatAuditTime,
  onAuditLimitChange,
  onAuditActorUserIdChange,
  onAuditActionKeywordChange,
  onAuditEventCategoryChange,
  onAuditSeverityChange,
  onAuditResultChange,
  onRefresh,
  onClearFilters,
  currentPage,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: Props) {
  const { t } = useTranslation();
  const hasExactActorMatch =
    !auditActorUserId.trim() ||
    users.some(
      (user) =>
        (user.username || "").toLowerCase() === auditActorUserId.trim().toLowerCase() ||
        user.user_id === auditActorUserId.trim(),
    );

  const paginatedLogs = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    return logs.slice(start, end);
  }, [logs, currentPage, pageSize]);

  return (
    <main className="panel admin-audit-panel">
      <div className="section-head">
        <strong>{t("admin.auditLog")}</strong>
        <div className="row-actions admin-audit-head-actions">
          <select value={auditLimit} onChange={(e) => onAuditLimitChange(Number(e.target.value) || 200)}>
            <option value={100}>{t("admin.ui.last100")}</option>
            <option value={200}>{t("admin.ui.last200")}</option>
            <option value={500}>{t("admin.ui.last500")}</option>
          </select>
          <button type="button" className="secondary tiny-btn" onClick={onRefresh}>{t("common.refresh")}</button>
        </div>
      </div>

      <p className="muted admin-audit-hint">{t("admin.ui.auditHint")}</p>

      {!hasExactActorMatch && (
        <p className="muted admin-audit-hint admin-audit-match-hint">
          {t("admin.ui.actorFuzzyHint")}
        </p>
      )}

      <div className="ops-two-col admin-filter-grid">
        <label className="admin-field">
          <span>{t("admin.ui.actor")}</span>
          <input list="actor-user-options" placeholder={t("admin.ui.actorPlaceholder")} value={auditActorUserId} onChange={(e) => onAuditActorUserIdChange(e.target.value)} />
        </label>
        <AdminFormSelect
          label={t("admin.ui.action")}
          value={auditActionKeyword}
          onChange={onAuditActionKeywordChange}
          options={[
            { value: "", label: t("admin.ui.allActions") },
            ...ACTION_KEYWORD_OPTIONS.map((action) => ({ value: action, label: action })),
          ]}
        />
      </div>

      <div className="ops-two-col admin-filter-grid">
        <AdminFormSelect
          label={t("admin.ui.category")}
          value={auditEventCategory}
          onChange={onAuditEventCategoryChange}
          options={[
            { value: "", label: t("admin.ui.allCategories") },
            { value: "auth", label: "auth" },
            { value: "admin", label: "admin" },
            { value: "data", label: "data" },
            { value: "prompt", label: "prompt" },
            { value: "system", label: "system" },
          ]}
        />
        <AdminFormSelect
          label={t("admin.ui.severity")}
          value={auditSeverity}
          onChange={onAuditSeverityChange}
          options={[
            { value: "", label: t("admin.ui.allSeverities") },
            { value: "info", label: "info" },
            { value: "medium", label: "medium" },
            { value: "high", label: "high" },
          ]}
        />
      </div>

      <div className="ops-two-col admin-filter-grid">
        <AdminFormSelect
          label={t("admin.ui.result")}
          value={auditResult}
          onChange={onAuditResultChange}
          options={[
            { value: "", label: t("admin.ui.allResults") },
            { value: "success", label: "success" },
            { value: "failed", label: "failed" },
            { value: "denied", label: "denied" },
          ]}
        />
        <div className="row-actions admin-audit-quick-actions">
          <button type="button" className="secondary tiny-btn" onClick={() => onAuditResultChange("failed")}>{t("admin.ui.failedOnly")}</button>
          <button type="button" className="secondary tiny-btn" onClick={() => onAuditSeverityChange("high")}>{t("admin.ui.highRiskOnly")}</button>
          <button type="button" className="secondary tiny-btn" onClick={onClearFilters}>{t("admin.ui.clear")}</button>
        </div>
      </div>

      {loadingLogs && <div className="skeleton-list" />}
      {!loadingLogs && <p className="muted admin-audit-scroll-hint">{t("admin.ui.auditScrollHint")}</p>}
      {!loadingLogs && logs.length === 0 && <div className="status">{t("admin.ui.auditEmpty")}</div>}
      {!loadingLogs && logs.length > 0 && (
        <>
          <AdminPagination
            currentPage={currentPage}
            pageSize={pageSize}
            totalItems={logs.length}
            onPageChange={onPageChange}
            onPageSizeChange={onPageSizeChange}
            pageSizeOptions={[20, 50, 100]}
          />
          <AdminAuditLogTable logs={paginatedLogs} formatAuditTime={formatAuditTime} />
        </>
      )}
    </main>
  );
}
