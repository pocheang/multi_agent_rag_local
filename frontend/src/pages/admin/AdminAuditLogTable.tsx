import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AuditLogEntry } from "@/types/api";

type Props = {
  logs: AuditLogEntry[];
  formatAuditTime: (ts?: string | null) => string;
};

const COLORS = ["#5b8cff", "#4fc3f7", "#8b7aff", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#ec4899"];

export function AdminAuditLogTable({ logs, formatAuditTime }: Props) {
  const { t } = useTranslation();

  const stats = useMemo(() => {
    const byCategory = logs.reduce<Record<string, number>>((acc, log) => {
      const category = log.event_category || "Unknown";
      acc[category] = (acc[category] || 0) + 1;
      return acc;
    }, {});

    const bySeverity = logs.reduce<Record<string, number>>((acc, log) => {
      const severity = log.severity || "Unknown";
      acc[severity] = (acc[severity] || 0) + 1;
      return acc;
    }, {});

    const byResult = logs.reduce<Record<string, number>>((acc, log) => {
      const result = log.result || "Unknown";
      acc[result] = (acc[result] || 0) + 1;
      return acc;
    }, {});

    const byActor = logs.reduce<Record<string, number>>((acc, log) => {
      const actor = log.actor_user_id || "Unknown";
      acc[actor] = (acc[actor] || 0) + 1;
      return acc;
    }, {});

    return {
      byCategory: Object.entries(byCategory).map(([name, value]) => ({ name, value })),
      bySeverity: Object.entries(bySeverity).map(([name, value]) => ({ name, value })),
      byResult: Object.entries(byResult).map(([name, value]) => ({ name, value })),
      byActor: Object.entries(byActor)
        .slice(0, 10)
        .map(([name, value]) => ({
          name: name.length > 15 ? `${name.slice(0, 15)}...` : name,
          value,
        })),
    };
  }, [logs]);

  return (
    <div className="audit-table-wrap">
      {logs.length > 0 && (
        <>
          <div className="section-head">
            <strong>{t("admin.ui.auditStatistics", "Audit Statistics")}</strong>
          </div>

          <div className="ops-two-col">
            <div className="chart-container">
              <h3 className="chart-title">{t("admin.ui.byCategory", "Events by Category")}</h3>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={stats.byCategory} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} labelLine={false}>
                    {stats.byCategory.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="chart-container">
              <h3 className="chart-title">{t("admin.ui.bySeverity", "Events by Severity")}</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={stats.bySeverity}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                  <XAxis dataKey="name" stroke="var(--text-tertiary)" fontSize={11} />
                  <YAxis stroke="var(--text-tertiary)" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      background: "var(--surface)",
                      border: "1px solid var(--border-medium)",
                      borderRadius: "var(--radius-md)",
                    }}
                  />
                  <Bar dataKey="value" fill="var(--accent)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="ops-two-col admin-section-block">
            <div className="chart-container">
              <h3 className="chart-title">{t("admin.ui.byResult", "Events by Result")}</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={stats.byResult}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                  <XAxis dataKey="name" stroke="var(--text-tertiary)" fontSize={11} />
                  <YAxis stroke="var(--text-tertiary)" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      background: "var(--surface)",
                      border: "1px solid var(--border-medium)",
                      borderRadius: "var(--radius-md)",
                    }}
                  />
                  <Bar dataKey="value" fill="var(--info)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="chart-container">
              <h3 className="chart-title">{t("admin.ui.topActors", "Top Actors")}</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={stats.byActor} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                  <XAxis type="number" stroke="var(--text-tertiary)" fontSize={11} />
                  <YAxis dataKey="name" type="category" stroke="var(--text-tertiary)" fontSize={10} width={100} />
                  <Tooltip
                    contentStyle={{
                      background: "var(--surface)",
                      border: "1px solid var(--border-medium)",
                      borderRadius: "var(--radius-md)",
                    }}
                  />
                  <Bar dataKey="value" fill="var(--warning)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="ops-kpi-grid ops-kpi-grid-primary">
            <div className="ops-kpi-card">
              <span>{t("admin.ui.totalEvents", "Total Events")}</span>
              <strong>{logs.length}</strong>
            </div>
            <div className="ops-kpi-card">
              <span>{t("admin.ui.uniqueActors", "Unique Actors")}</span>
              <strong>{new Set(logs.map((log) => log.actor_user_id)).size}</strong>
            </div>
            <div className="ops-kpi-card">
              <span>{t("admin.ui.successRate", "Success Rate")}</span>
              <strong style={{ color: "var(--success)" }}>
                {logs.length > 0 ? ((logs.filter((log) => log.result === "success").length / logs.length) * 100).toFixed(1) : 0}%
              </strong>
            </div>
            <div className="ops-kpi-card">
              <span>{t("admin.ui.failureCount", "Failures")}</span>
              <strong style={{ color: "var(--danger)" }}>{logs.filter((log) => log.result === "failure").length}</strong>
            </div>
          </div>

          <div className="section-head">
            <strong>{t("admin.ui.detailedLogs", "Detailed Audit Logs")}</strong>
          </div>
        </>
      )}

      <table className="table admin-audit-table">
        <thead>
          <tr>
            <th style={{ width: "140px" }}>{t("admin.ui.time")}</th>
            <th style={{ width: "140px" }}>{t("admin.ui.actor")}</th>
            <th style={{ width: "180px" }}>{t("admin.ui.action")}</th>
            <th style={{ width: "100px", textAlign: "center" }}>{t("admin.ui.category")}</th>
            <th style={{ width: "80px", textAlign: "center" }}>{t("admin.ui.severity")}</th>
            <th style={{ width: "200px" }}>{t("admin.ui.resource")}</th>
            <th style={{ width: "80px", textAlign: "center" }}>{t("admin.ui.result")}</th>
            <th style={{ width: "120px" }}>IP</th>
            <th>{t("admin.ui.detail")}</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((entry) => (
            <tr key={entry.event_id}>
              <td style={{ fontSize: "var(--text-xs)", fontFamily: "monospace" }}>{formatAuditTime(entry.created_at)}</td>
              <td className="audit-actor">
                <div className="audit-cell-stack">
                  <span className="audit-id" style={{ fontSize: "var(--text-sm)", fontWeight: 600 }} title={entry.actor_user_id || "-"}>
                    {entry.actor_user_id || "-"}
                  </span>
                  <span className="audit-sub" style={{ fontSize: "var(--text-xs)" }}>{entry.actor_role || "-"}</span>
                </div>
              </td>
              <td className="audit-action">
                <span className="audit-code" style={{ fontSize: "var(--text-sm)" }} title={entry.action || "-"}>
                  {entry.action || "-"}
                </span>
              </td>
              <td style={{ textAlign: "center" }}>
                <span className="audit-badge" style={{ fontSize: "var(--text-xs)" }}>{entry.event_category || "-"}</span>
              </td>
              <td style={{ textAlign: "center" }}>
                <span className={`audit-badge audit-severity-${(entry.severity || "none").toLowerCase()}`}>
                  {entry.severity || "-"}
                </span>
              </td>
              <td className="audit-resource">
                <div className="audit-cell-stack">
                  <span className="audit-code" style={{ fontSize: "var(--text-sm)" }} title={entry.resource_type || "-"}>
                    {entry.resource_type || "-"}
                  </span>
                  <span className="audit-sub" style={{ fontSize: "var(--text-xs)" }} title={entry.resource_id || "-"}>
                    {entry.resource_id || "-"}
                  </span>
                </div>
              </td>
              <td style={{ textAlign: "center" }}>
                <span className={`audit-badge audit-result-${(entry.result || "none").toLowerCase()}`}>
                  {entry.result || "-"}
                </span>
              </td>
              <td className="audit-ip" style={{ fontSize: "var(--text-xs)", fontFamily: "monospace" }}>{entry.ip || "-"}</td>
              <td className="audit-detail" style={{ fontSize: "var(--text-sm)", maxWidth: "300px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={entry.detail || "-"}>
                {entry.detail || "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
