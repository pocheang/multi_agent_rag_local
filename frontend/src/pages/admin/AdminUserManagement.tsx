import { useMemo, useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { AdminUserTable } from "@/pages/admin/AdminUserTable";
import { AdminPagination } from "@/components/AdminPagination";
import type { AdminUserSummary } from "@/types/api";

type Props = {
  users: AdminUserSummary[];
  loadingUsers: boolean;
  kw: string;
  fRole: string;
  fStatus: string;
  fOnline: string;
  editingUser: AdminUserSummary | null;
  editBu: string;
  editDept: string;
  editType: string;
  editScope: string;
  savingClass: boolean;
  roleOptions: string[];
  statusOptions: string[];
  onKwChange: (value: string) => void;
  onFRoleChange: (value: string) => void;
  onFStatusChange: (value: string) => void;
  onFOnlineChange: (value: string) => void;
  onEditingUserChange: (user: AdminUserSummary | null) => void;
  onEditBuChange: (value: string) => void;
  onEditDeptChange: (value: string) => void;
  onEditTypeChange: (value: string) => void;
  onEditScopeChange: (value: string) => void;
  onLoadUsers: () => void;
  onSaveClass: () => void;
  onUpdateRole: (target: AdminUserSummary, role: string) => Promise<void>;
  onUpdateStatus: (target: AdminUserSummary, status: string) => Promise<void>;
  onAddCredits: (target: AdminUserSummary) => Promise<void>;
  onOpenClassEditor: (user: AdminUserSummary) => void;
  onResetPassword: (target: AdminUserSummary) => Promise<void>;
  onResetApprovalToken: (target: AdminUserSummary) => Promise<void>;
};

export function AdminUserManagement({
  users,
  loadingUsers,
  kw,
  fRole,
  fStatus,
  fOnline,
  editingUser,
  editBu,
  editDept,
  editType,
  editScope,
  savingClass,
  roleOptions,
  statusOptions,
  onKwChange,
  onFRoleChange,
  onFStatusChange,
  onFOnlineChange,
  onEditingUserChange,
  onEditBuChange,
  onEditDeptChange,
  onEditTypeChange,
  onEditScopeChange,
  onLoadUsers,
  onSaveClass,
  onUpdateRole,
  onUpdateStatus,
  onAddCredits,
  onOpenClassEditor,
  onResetPassword,
  onResetApprovalToken,
}: Props) {
  const { t } = useTranslation();
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

  const [pageSize, setPageSize] = useState<number>(10);
  const [currentPage, setCurrentPage] = useState<number>(1);

  useEffect(() => {
    setCurrentPage(1);
  }, [kw, fRole, fStatus, fOnline]);

  const paginatedUsers = useMemo(() => {
    const startIdx = (currentPage - 1) * pageSize;
    return filteredUsers.slice(startIdx, startIdx + pageSize);
  }, [filteredUsers, currentPage, pageSize]);

  return (
    <main className="panel admin-users-panel">
      <div className="section-head">
        <strong>{t("admin.userManagement")}</strong>
        <button type="button" className="secondary tiny-btn" onClick={onLoadUsers}>{t("common.refresh")}</button>
      </div>
      <p className="muted admin-users-hint">{t("admin.ui.usersHint")}</p>

      <div className="ops-two-col admin-filter-grid">
        <label className="admin-field">
          <span>{t("admin.ui.search")}</span>
          <input placeholder={t("admin.ui.userSearchPlaceholder")} value={kw} onChange={(e) => onKwChange(e.target.value)} />
        </label>
        <label className="admin-field">
          <span>{t("admin.ui.role")}</span>
          <select value={fRole} onChange={(e) => onFRoleChange(e.target.value)}>
            <option value="">{t("admin.ui.allRoles")}</option>
            <option value="admin">admin</option>
            <option value="analyst">analyst</option>
            <option value="viewer">viewer</option>
          </select>
        </label>
      </div>

      <div className="ops-two-col admin-filter-grid">
        <label className="admin-field">
          <span>{t("admin.ui.status")}</span>
          <select value={fStatus} onChange={(e) => onFStatusChange(e.target.value)}>
            <option value="">{t("admin.ui.allStatuses")}</option>
            <option value="active">active</option>
            <option value="disabled">disabled</option>
          </select>
        </label>
        <label className="admin-field">
          <span>{t("admin.ui.onlineStatus")}</span>
          <select value={fOnline} onChange={(e) => onFOnlineChange(e.target.value)}>
            <option value="">{t("admin.ui.allOnlineStatuses")}</option>
            <option value="online_10m">{t("admin.ui.online10m")}</option>
            <option value="online">{t("admin.ui.online")}</option>
            <option value="offline">{t("admin.ui.offline")}</option>
          </select>
        </label>
      </div>

      {editingUser && (
        <div className="panel" style={{ marginBottom: 12 }}>
          <div className="section-head">
            <strong>{t("admin.ui.userClassification", { username: editingUser.username })}</strong>
            <button type="button" className="secondary tiny-btn" onClick={() => onEditingUserChange(null)}>{t("common.cancel")}</button>
          </div>
          <div className="ops-two-col">
            <input placeholder={t("admin.ui.businessUnit")} value={editBu} onChange={(e) => onEditBuChange(e.target.value)} />
            <input placeholder={t("admin.ui.department")} value={editDept} onChange={(e) => onEditDeptChange(e.target.value)} />
          </div>
          <div className="ops-two-col">
            <input placeholder={t("admin.ui.userType")} value={editType} onChange={(e) => onEditTypeChange(e.target.value)} />
            <input placeholder={t("admin.ui.dataScope")} value={editScope} onChange={(e) => onEditScopeChange(e.target.value)} />
          </div>
          <div className="row-actions">
            <button type="button" className="primary-action-btn" disabled={savingClass} onClick={onSaveClass}>
              {savingClass ? t("admin.ui.saving") : t("admin.ui.saveClassification")}
            </button>
          </div>
        </div>
      )}

      {loadingUsers && <div className="skeleton-list" />}
      {!loadingUsers && (
        <>
          {filteredUsers.length > 0 && (
            <AdminPagination
              totalItems={filteredUsers.length}
              currentPage={currentPage}
              pageSize={pageSize}
              pageSizeOptions={[10, 20, 50]}
              onPageChange={setCurrentPage}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setCurrentPage(1);
              }}
            />
          )}
          <div className="user-table-wrap">
            <AdminUserTable
              users={paginatedUsers}
              roleOptions={roleOptions}
              statusOptions={statusOptions}
              onUpdateRole={onUpdateRole}
              onUpdateStatus={onUpdateStatus}
              onAddCredits={onAddCredits}
              onOpenClassEditor={onOpenClassEditor}
              onResetPassword={onResetPassword}
              onResetApprovalToken={onResetApprovalToken}
            />
          </div>
        </>
      )}
    </main>
  );
}
