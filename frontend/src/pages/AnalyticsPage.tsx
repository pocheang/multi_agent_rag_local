import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AuthUser } from "@/types/api";
import { LanguageToggle } from "@/components/LanguageToggle";
import { analyticsApi, type AgentStats, type AnalyticsOverview, type DocumentStats } from "@/lib/analytics-api";
import "@/styles/pages/analytics.css";

type Props = {
  user: AuthUser | null;
  onLogout: () => Promise<void>;
};

const COLORS = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042"];

export function AnalyticsPage({ onLogout }: Props) {
  const { t } = useTranslation();
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [agents, setAgents] = useState<AgentStats[]>([]);
  const [documents, setDocuments] = useState<DocumentStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const [overviewData, agentsData, docsData] = await Promise.all([
        analyticsApi.overview(),
        analyticsApi.agents(),
        analyticsApi.documents(10),
      ]);

      setOverview(overviewData);
      setAgents(agentsData);
      setDocuments(docsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("pages.analytics.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void fetchData();
    const interval = window.setInterval(() => void fetchData(), 10000);
    return () => window.clearInterval(interval);
  }, [fetchData]);

  const handleExport = (format: "json" | "csv") => {
    window.open(analyticsApi.exportUrl(format), "_blank", "noopener,noreferrer");
  };

  if (loading && !overview) {
    return (
      <div className="analytics-loading">
        <p>{t("pages.analytics.loading")}</p>
      </div>
    );
  }

  const agentDistributionData = overview?.agent_distribution
    ? Object.entries(overview.agent_distribution).map(([name, value]) => ({
        name,
        value,
      }))
    : [];

  const agentPerformanceData = agents.map((agent) => ({
    name: agent.agent_class,
    queries: agent.query_count,
    success_rate: agent.success_rate,
    avg_time: agent.avg_retrieval_time_ms,
  }));

  const documentHeatmapData = documents.map((doc) => ({
    name: doc.source.length > 30 ? `${doc.source.substring(0, 27)}...` : doc.source,
    retrievals: doc.retrieval_count,
    avg_score: doc.avg_score,
  }));

  return (
    <div className="analytics-page">
      <header className="analytics-header">
        <div className="analytics-header-content">
          <h2>{t("pages.analytics.title")}</h2>
          <p>{t("pages.analytics.subtitle")}</p>
        </div>
        <div className="analytics-header-actions">
          <LanguageToggle />
          <Link to="/app/admin" className="back-btn">
            {t("pages.analytics.backToAdmin")}
          </Link>
          <button onClick={() => void onLogout()} className="logout-btn" type="button">
            {t("nav.logout")}
          </button>
        </div>
      </header>

      <div className="analytics-content">
        {error && <div className="status error">{error}</div>}

        <div className="analytics-title-bar">
          <h1>{t("pages.analytics.dashboard")}</h1>
          <button onClick={() => void fetchData()} className="refresh-btn" type="button">
            {loading ? t("pages.analytics.refreshing") : t("common.refresh")}
          </button>
        </div>

        <div className="analytics-stats-grid">
          <div className="stat-card-analytics blue">
            <h3>{t("pages.analytics.totalQueries")}</h3>
            <p>{overview?.total_queries || 0}</p>
          </div>

          <div className="stat-card-analytics green">
            <h3>{t("pages.analytics.successRate")}</h3>
            <p>{overview?.success_rate ? `${overview.success_rate.toFixed(1)}%` : "0%"}</p>
          </div>

          <div className="stat-card-analytics yellow">
            <h3>{t("pages.analytics.avgResponseTime")}</h3>
            <p>{overview?.avg_total_time_ms ? `${overview.avg_total_time_ms.toFixed(0)}ms` : "0ms"}</p>
          </div>

          <div className="stat-card-analytics orange">
            <h3>{t("pages.analytics.avgRetrievedDocs")}</h3>
            <p>{overview?.avg_retrieved_count ? overview.avg_retrieved_count.toFixed(1) : "0"}</p>
          </div>
        </div>

        <div className="analytics-charts-grid">
          <div className="chart-card">
            <h2>{t("pages.analytics.agentDistribution")}</h2>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={agentDistributionData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name}: ${((percent ?? 0) * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {agentDistributionData.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="chart-card">
            <h2>{t("pages.analytics.agentPerformance")}</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={agentPerformanceData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="queries" fill="#0088FE" name={t("pages.analytics.queryCount")} />
                <Bar dataKey="success_rate" fill="#00C49F" name={t("pages.analytics.successRatePercent")} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card-full">
          <h2>{t("pages.analytics.topDocuments")}</h2>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={documentHeatmapData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis dataKey="name" type="category" width={200} />
              <Tooltip />
              <Legend />
              <Bar dataKey="retrievals" fill="#0088FE" name={t("pages.analytics.retrievals")} />
              <Bar dataKey="avg_score" fill="#FFBB28" name={t("pages.analytics.avgScore")} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="analytics-export-actions">
          <button onClick={() => handleExport("json")} className="export-btn json" type="button">
            {t("pages.analytics.exportJson")}
          </button>
          <button onClick={() => handleExport("csv")} className="export-btn csv" type="button">
            {t("pages.analytics.exportCsv")}
          </button>
        </div>
      </div>
    </div>
  );
}
