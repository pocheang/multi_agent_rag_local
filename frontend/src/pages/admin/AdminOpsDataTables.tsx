import { useTranslation } from "react-i18next";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { OpsOverview } from "@/types/api";

type Props = {
  ops: OpsOverview;
  formatAuditTime: (ts?: string | null) => string;
};

const COLORS = ["#5b8cff", "#4fc3f7", "#8b7aff", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#ec4899"];

export function AdminOpsDataTables({ ops, formatAuditTime }: Props) {
  const { t } = useTranslation();
  const recentFailures = ops?.diagnostics?.recent_failures ?? [];
  const recentErrors = ops?.diagnostics?.recent_errors ?? [];

  const failuresByStatus = recentFailures.reduce<Record<string, number>>((acc, item) => {
    const status = item.status_code.toString();
    acc[status] = (acc[status] || 0) + 1;
    return acc;
  }, {});

  const statusChartData = Object.entries(failuresByStatus).map(([status, count]) => ({
    status,
    count,
    name: `HTTP ${status}`,
  }));

  const errorsByLogger = recentErrors.reduce<Record<string, number>>((acc, item) => {
    const logger = item.logger || "Unknown";
    acc[logger] = (acc[logger] || 0) + 1;
    return acc;
  }, {});

  const loggerChartData = Object.entries(errorsByLogger).map(([logger, count]) => ({
    logger: logger.length > 20 ? `${logger.slice(0, 20)}...` : logger,
    count,
  }));

  const failureTimeline = recentFailures
    .slice(0, 10)
    .reverse()
    .map((item, index) => ({
      time: `T-${10 - index}`,
      count: 1,
      duration: item.duration_ms,
    }));

  return (
    <>
      <div className="section-head admin-section-head-offset">
        <strong>{t("admin.ui.recentFailedRequests", "Recent Failed Requests")}</strong>
      </div>

      {recentFailures.length > 0 ? (
        <section className="admin-section-subblock">
          <div className="ops-two-col">
            <div className="chart-container">
              <h3 className="chart-title">{t("admin.ui.failureByStatus", "Failures by Status Code")}</h3>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={statusChartData} dataKey="count" nameKey="name" cx="50%" cy="50%" outerRadius={70} labelLine={false}>
                    {statusChartData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="chart-container">
              <h3 className="chart-title">{t("admin.ui.failureTimeline", "Failure Timeline")}</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={failureTimeline}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                  <XAxis dataKey="time" stroke="var(--text-tertiary)" fontSize={11} />
                  <YAxis stroke="var(--text-tertiary)" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      background: "var(--surface)",
                      border: "1px solid var(--border-medium)",
                      borderRadius: "var(--radius-md)",
                    }}
                  />
                  <Line type="monotone" dataKey="duration" stroke="var(--danger)" strokeWidth={2} dot={{ fill: "var(--danger)" }} name="Duration (ms)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="audit-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th style={{ width: "140px" }}>{t("admin.ui.time", "Time")}</th>
                  <th style={{ width: "200px" }}>{t("admin.ui.path", "Path")}</th>
                  <th style={{ width: "80px", textAlign: "center" }}>{t("admin.ui.statusCode", "Status")}</th>
                  <th style={{ width: "100px", textAlign: "right" }}>{t("admin.ui.duration", "Duration")}</th>
                  <th>{t("admin.ui.error", "Error")}</th>
                </tr>
              </thead>
              <tbody>
                {recentFailures.map((item, index) => (
                  <tr key={`${item.ts}-${index}`}>
                    <td style={{ fontSize: "var(--text-xs)", fontFamily: "monospace" }}>{formatAuditTime(item.ts)}</td>
                    <td style={{ fontSize: "var(--text-sm)", fontFamily: "monospace" }}>{item.path}</td>
                    <td style={{ textAlign: "center" }}>
                      <span className="badge badge-danger">{item.status_code}</span>
                    </td>
                    <td style={{ textAlign: "right", fontFamily: "monospace" }}>{item.duration_ms}ms</td>
                    <td style={{ fontSize: "var(--text-sm)", maxWidth: "400px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={item.error || "-"}>
                      {item.error || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <div className="admin-state-panel is-success">
          <div className="admin-state-icon">OK</div>
          <p>{t("admin.ui.noFailedRequests", "No failed requests")}</p>
          <p className="muted">{t("admin.ui.systemHealthy", "System is running smoothly")}</p>
        </div>
      )}

      <div className="section-head admin-section-head-offset">
        <strong>{t("admin.ui.recentCriticalErrors", "Recent Critical Errors")}</strong>
      </div>

      {recentErrors.length > 0 ? (
        <section className="admin-section-subblock">
          <div className="ops-two-col">
            <div className="chart-container">
              <h3 className="chart-title">{t("admin.ui.errorByLogger", "Errors by Logger")}</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={loggerChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                  <XAxis dataKey="logger" stroke="var(--text-tertiary)" fontSize={10} angle={-45} textAnchor="end" height={60} />
                  <YAxis stroke="var(--text-tertiary)" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      background: "var(--surface)",
                      border: "1px solid var(--border-medium)",
                      borderRadius: "var(--radius-md)",
                    }}
                  />
                  <Bar dataKey="count" fill="var(--danger)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="chart-container">
              <h3 className="chart-title">{t("admin.ui.errorSummary", "Error Summary")}</h3>
              <div className="ops-kpi-grid ops-kpi-grid-secondary">
                <div className="ops-kpi-card">
                  <span>{t("admin.ui.totalErrors", "Total Errors")}</span>
                  <strong style={{ color: "var(--danger)" }}>{recentErrors.length}</strong>
                </div>
                <div className="ops-kpi-card">
                  <span>{t("admin.ui.uniqueLoggers", "Unique Loggers")}</span>
                  <strong>{Object.keys(errorsByLogger).length}</strong>
                </div>
              </div>
            </div>
          </div>

          <div className="audit-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th style={{ width: "140px" }}>{t("admin.ui.time", "Time")}</th>
                  <th style={{ width: "150px" }}>Logger</th>
                  <th>{t("admin.ui.message", "Message")}</th>
                  <th style={{ width: "250px" }}>{t("admin.ui.exception", "Exception")}</th>
                </tr>
              </thead>
              <tbody>
                {recentErrors.map((item, index) => (
                  <tr key={`${item.created_at}-${index}`}>
                    <td style={{ fontSize: "var(--text-xs)", fontFamily: "monospace" }}>{formatAuditTime(item.created_at)}</td>
                    <td style={{ fontSize: "var(--text-sm)", fontFamily: "monospace" }}>{item.logger || "-"}</td>
                    <td style={{ fontSize: "var(--text-sm)", maxWidth: "300px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={item.message || "-"}>
                      {item.message || "-"}
                    </td>
                    <td style={{ fontSize: "var(--text-xs)", fontFamily: "monospace", maxWidth: "250px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={item.exception || "-"}>
                      {item.exception || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <div className="admin-state-panel is-success">
          <div className="admin-state-icon">OK</div>
          <p>{t("admin.ui.noCriticalErrors", "No critical errors")}</p>
          <p className="muted">{t("admin.ui.noErrorsDetected", "No errors detected in the system")}</p>
        </div>
      )}
    </>
  );
}
