// Web activity detail tables.
import { useTranslation } from "react-i18next";

interface User {
  user_id: string;
  search_count: number;
}

interface Website {
  domain: string;
  visit_count: number;
  avg_trust_score: number;
}

interface Alert {
  timestamp: string;
  rule_name: string;
  level: string;
  message: string;
  metric_value: number;
  threshold: number;
}

interface Props {
  usersData: User[];
  websitesData: Website[];
  alerts: Alert[];
}

function formatAlertTime(timestamp: string) {
  return new Date(timestamp).toLocaleString(undefined, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function WebActivityTables({ usersData, websitesData, alerts }: Props) {
  const { t } = useTranslation();

  return (
    <>
      {usersData.length > 0 && (
        <section className="admin-section-block">
          <h3 className="section-subtitle">
            {t("admin.webActivity.topUsers", "Top Active Users")}
          </h3>
          <div className="audit-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th style={{ width: "60px", textAlign: "center" }}>#</th>
                  <th>{t("admin.webActivity.userId", "User ID")}</th>
                  <th style={{ width: "120px", textAlign: "right" }}>
                    {t("admin.webActivity.searchCount", "Searches")}
                  </th>
                  <th style={{ width: "100px", textAlign: "center" }}>
                    {t("admin.webActivity.activity", "Status")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {usersData.map((user, index) => (
                  <tr key={user.user_id}>
                    <td style={{ textAlign: "center", fontWeight: 600, color: "var(--text-secondary)" }}>
                      {index + 1}
                    </td>
                    <td style={{ fontFamily: "monospace", fontSize: "var(--text-sm)" }}>{user.user_id}</td>
                    <td style={{ textAlign: "right", fontWeight: 600 }}>{user.search_count}</td>
                    <td style={{ textAlign: "center" }}>
                      <span className={`badge badge-${user.search_count > 5 ? "success" : "warning"}`}>
                        {user.search_count > 5
                          ? t("admin.webActivity.active", "Active")
                          : t("admin.webActivity.low", "Low")}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {websitesData.length > 0 && (
        <section className="admin-section-block">
          <h3 className="section-subtitle">
            {t("admin.webActivity.websiteDetails", "Website Access Details")}
          </h3>
          <div className="audit-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th style={{ width: "60px", textAlign: "center" }}>#</th>
                  <th>{t("admin.webActivity.domain", "Domain")}</th>
                  <th style={{ width: "100px", textAlign: "right" }}>
                    {t("admin.webActivity.visitCount", "Visits")}
                  </th>
                  <th style={{ width: "120px", textAlign: "center" }}>
                    {t("admin.webActivity.trustScore", "Trust")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {websitesData.map((website, index) => {
                  const trustLevel =
                    website.avg_trust_score >= 0.8
                      ? "success"
                      : website.avg_trust_score >= 0.5
                        ? "warning"
                        : "danger";

                  return (
                    <tr key={website.domain}>
                      <td style={{ textAlign: "center", fontWeight: 600, color: "var(--text-secondary)" }}>
                        {index + 1}
                      </td>
                      <td>
                        <a
                          href={`https://${website.domain}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="admin-link-inline"
                        >
                          {website.domain}
                        </a>
                      </td>
                      <td style={{ textAlign: "right", fontWeight: 600 }}>{website.visit_count}</td>
                      <td style={{ textAlign: "center" }}>
                        <span className={`badge badge-${trustLevel}`}>
                          {(website.avg_trust_score * 100).toFixed(0)}%
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {alerts.length > 0 && (
        <section className="admin-section-block">
          <h3 className="section-subtitle">
            {t("admin.webActivity.securityAlerts", "Security Alerts (24h)")}
          </h3>
          <div className="audit-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th style={{ width: "160px" }}>{t("admin.webActivity.time", "Time")}</th>
                  <th style={{ width: "80px", textAlign: "center" }}>
                    {t("admin.webActivity.level", "Level")}
                  </th>
                  <th style={{ width: "180px" }}>{t("admin.webActivity.rule", "Rule")}</th>
                  <th>{t("admin.webActivity.message", "Message")}</th>
                  <th style={{ width: "120px", textAlign: "right" }}>
                    {t("admin.webActivity.value", "Value")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((alert) => (
                  <tr key={`${alert.timestamp}-${alert.rule_name}`}>
                    <td style={{ fontSize: "var(--text-xs)", fontFamily: "monospace" }}>
                      {formatAlertTime(alert.timestamp)}
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span className={`badge badge-${alert.level === "critical" ? "danger" : alert.level}`}>
                        {alert.level.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ fontSize: "var(--text-sm)" }}>{alert.rule_name}</td>
                    <td style={{ fontSize: "var(--text-sm)" }}>{alert.message}</td>
                    <td style={{ textAlign: "right", fontFamily: "monospace", fontSize: "var(--text-sm)" }}>
                      {alert.metric_value} / {alert.threshold}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
