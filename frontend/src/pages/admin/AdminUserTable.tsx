import type { AdminUserSummary } from "@/types/api";
import { useTranslation } from "react-i18next";

type Props = {
  users: AdminUserSummary[];
  roleOptions: string[];
  statusOptions: string[];
  onUpdateRole: (user: AdminUserSummary, role: string) => Promise<void>;
  onUpdateStatus: (user: AdminUserSummary, status: string) => Promise<void>;
  onAddCredits: (user: AdminUserSummary) => Promise<void>;
  onOpenClassEditor: (user: AdminUserSummary) => void;
  onResetPassword: (user: AdminUserSummary) => Promise<void>;
  onResetApprovalToken: (user: AdminUserSummary) => Promise<void>;
};

export function AdminUserTable({
  users,
  roleOptions,
  statusOptions,
  onUpdateRole,
  onUpdateStatus,
  onAddCredits,
  onOpenClassEditor,
  onResetPassword,
  onResetApprovalToken,
}: Props) {
  const { t } = useTranslation();

  const renderValue = (value?: string | null) => value?.trim() || "-";

  return (
    <table className="table admin-user-table">
      <thead>
        <tr>
          <th>{t("admin.ui.username")}</th>
          <th>{t("admin.ui.role")}</th>
          <th>{t("admin.ui.status")}</th>
          <th>{t("admin.ui.credits")}</th>
          <th>{t("admin.ui.operation")}</th>
          <th>{t("admin.ui.businessUnit")}</th>
          <th>{t("admin.ui.type")}</th>
          <th>{t("admin.ui.createdBy")}</th>
          <th>{t("admin.ui.token")}</th>
        </tr>
      </thead>
      <tbody>
        {users.map((row) => (
          <tr key={row.user_id}>
            <td>
              <div className="admin-user-identity">
                <span className="admin-username">{row.username}</span>
                <span className="admin-user-id" title={row.user_id}>{row.user_id}</span>
              </div>
            </td>
            <td>
              <select value={row.role} onChange={(e) => void onUpdateRole(row, e.target.value)}>
                {([...(row.role === "admin" ? ["admin"] : []), ...roleOptions] as string[]).map((x) => (
                  <option key={x} value={x}>
                    {x}
                  </option>
                ))}
              </select>
            </td>
            <td>
              <div className="admin-user-status-cell">
                <select value={row.status} onChange={(e) => void onUpdateStatus(row, e.target.value)}>
                  {statusOptions.map((x) => (
                    <option key={x} value={x}>
                      {x}
                    </option>
                  ))}
                </select>
                <div className="admin-user-flags">
                  <span className={`admin-user-flag ${row.is_online ? "online" : "offline"}`}>
                    {row.is_online ? t("admin.ui.online") : t("admin.ui.offline")}
                  </span>
                  <span className={`admin-user-flag ${row.is_online_10m ? "active" : "empty"}`}>
                    {row.is_online_10m ? t("admin.ui.active10m") : "-"}
                  </span>
                </div>
              </div>
            </td>
            <td>
              <span className="admin-user-flag token-set">
                {(row.role || "").toLowerCase() === "admin" ? t("admin.ui.unlimited") : row.credit_balance}
              </span>
            </td>
            <td>
              <div className="row-actions user-row-actions user-table-actions">
                <button type="button" className="secondary tiny-btn" onClick={() => onOpenClassEditor(row)}>
                  {t("admin.ui.classify")}
                </button>
                <button type="button" className="secondary tiny-btn" onClick={() => void onResetPassword(row)}>
                  {t("admin.ui.resetPassword")}
                </button>
                {(row.role || "").toLowerCase() !== "admin" ? (
                  <button type="button" className="secondary tiny-btn" onClick={() => void onAddCredits(row)}>
                    {t("admin.ui.addCredits")}
                  </button>
                ) : null}
                {(row.role || "").toLowerCase() === "admin" ? (
                  <button type="button" className="secondary tiny-btn" onClick={() => void onResetApprovalToken(row)}>
                    {t("admin.ui.resetToken")}
                  </button>
                ) : null}
              </div>
            </td>
            <td>
              <div className="admin-user-stack">
                <span>{renderValue(row.business_unit)}</span>
                <span className="admin-user-subtle">{renderValue(row.department)}</span>
              </div>
            </td>
            <td>
              <div className="admin-user-stack">
                <span>{renderValue(row.user_type)}</span>
                <span className="admin-user-subtle">{renderValue(row.data_scope)}</span>
              </div>
            </td>
            <td>
              <div className="admin-user-stack">
                <span>{renderValue(row.created_by_username || row.created_by_user_id)}</span>
                <span className="admin-user-subtle">{renderValue(row.admin_ticket_id)}</span>
              </div>
            </td>
            <td>
              <span className={`admin-user-flag ${row.has_admin_approval_token ? "token-set" : "empty"}`}>
                {row.has_admin_approval_token ? t("admin.ui.tokenSet") : t("admin.ui.tokenUnset")}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
