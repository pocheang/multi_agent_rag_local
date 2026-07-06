import { useTranslation } from "react-i18next";

interface Stats {
  total_searches: number;
  success_rate: number;
  unique_users: number;
  unique_websites: number;
  avg_query_length: number;
  avg_search_time: number;
}

interface Props {
  stats: Stats;
}

export function WebActivityKpiCards({ stats }: Props) {
  const { t } = useTranslation();

  return (
    <div className="ops-kpi-grid ops-kpi-grid-primary">
      <div className="ops-kpi-card"><span>{t("admin.webActivity.totalSearches", "Total Searches")}</span><strong>{stats.total_searches}</strong></div>
      <div className="ops-kpi-card"><span>{t("admin.webActivity.successRate", "Success Rate")}</span><strong>{(stats.success_rate * 100).toFixed(1)}%</strong></div>
      <div className="ops-kpi-card"><span>{t("admin.webActivity.uniqueUsers", "Unique Users")}</span><strong>{stats.unique_users}</strong></div>
      <div className="ops-kpi-card"><span>{t("admin.webActivity.uniqueWebsites", "Unique Websites")}</span><strong>{stats.unique_websites}</strong></div>
      <div className="ops-kpi-card"><span>{t("admin.webActivity.avgQueryLength", "Avg Query Length")}</span><strong>{stats.avg_query_length.toFixed(0)}</strong></div>
      <div className="ops-kpi-card"><span>{t("admin.webActivity.avgSearchTime", "Avg Search Time")}</span><strong>{stats.avg_search_time.toFixed(2)}s</strong></div>
    </div>
  );
}