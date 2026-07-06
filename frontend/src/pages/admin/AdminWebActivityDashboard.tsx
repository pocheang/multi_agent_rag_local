import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, authRequest } from "@/lib/api-client";
import { ExportButtons } from "@/utils/exportUtils";
import { WebActivityKpiCards } from "./components/WebActivityKpiCards";
import { WebActivityCharts } from "./components/WebActivityCharts";
import { WebActivityTables } from "./components/WebActivityTables";

interface WebActivityStats {
  summary: {
    total_searches: number;
    successful_searches: number;
    success_rate: number;
    sanitized_queries: number;
    unique_users: number;
    unique_websites: number;
    avg_query_length: number;
    avg_search_time: number;
  };
  top_websites: Array<{ domain: string; visit_count: number; avg_trust_score: number }>;
  top_users: Array<{ user_id: string; search_count: number }>;
  hourly_distribution: Record<string, number>;
}

interface Alert {
  timestamp: string;
  rule_name: string;
  level: string;
  message: string;
  metric_value: number;
  threshold: number;
}

interface AlertsResponse {
  alerts?: Alert[];
}

export function AdminWebActivityDashboard() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<WebActivityStats | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setError(null);
      const [statsData, alertsData] = await Promise.all([
        authRequest<WebActivityStats>("/api/v1/admin/web-activity/stats"),
        authRequest<AlertsResponse>("/api/v1/admin/web-activity/alerts?hours=24"),
      ]);
      setStats(statsData);
      setAlerts(alertsData.alerts || []);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError(t("admin.webActivity.authRequired", "Authentication required. Please sign in again."));
      } else {
        setError(t("admin.webActivity.loadingError", "Failed to fetch web activity data."));
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchData();
    if (!autoRefresh) return;
    const interval = window.setInterval(() => {
      void fetchData();
    }, 30000);
    return () => window.clearInterval(interval);
  }, [autoRefresh]);

  const hourlyData = stats
    ? Array.from({ length: 24 }, (_, i) => ({ hour: `${i}:00`, searches: stats.hourly_distribution[i] || 0 }))
    : [];

  const websitesData = stats?.top_websites.slice(0, 10) || [];
  const usersData = stats?.top_users.slice(0, 10) || [];

  const handleRetry = () => {
    setLoading(true);
    setError(null);
    void fetchData();
  };

  if (loading) {
    return <main className="panel ops-wrap"><div className="skeleton-list" /></main>;
  }

  if (error) {
    return (
      <main className="panel ops-wrap">
        <div className="section-head"><strong>{t("admin.webActivity.title", "Web Search Activity")}</strong></div>
        <div className="admin-state-panel is-error">
          <p>{error}</p>
          <button type="button" onClick={handleRetry} className="secondary tiny-btn">{t("admin.webActivity.retry", "Retry")}</button>
        </div>
      </main>
    );
  }

  return (
    <main className="panel ops-wrap">
      <div className="section-head">
        <strong>{t("admin.webActivity.title", "Web Search Activity")}</strong>
        <div className="row-actions">
          <ExportButtons
            data={stats ? [{ ...stats.summary, top_users: usersData, top_websites: websitesData }] : []}
            filename={`web-activity-${new Date().toISOString().split("T")[0]}`}
          />
          <button type="button" className="secondary tiny-btn" onClick={() => void fetchData()}>{t("admin.webActivity.refresh", "Refresh")}</button>
        </div>
      </div>

      <label className="ops-auto-refresh">
        <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
        <span>{t("admin.ui.autoRefresh30")}</span>
      </label>

      {stats && (
        <>
          <WebActivityKpiCards stats={stats.summary} />
          <WebActivityCharts data={{ hourlyData, websitesData }} />
          <WebActivityTables usersData={usersData} websitesData={websitesData} alerts={alerts} />
        </>
      )}
    </main>
  );
}