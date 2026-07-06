import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ApiError, authRequest } from "@/lib/api-client";
import { ExportButtons } from "@/utils/exportUtils";

interface AgentMetrics {
  agent_name: string;
  total_executions: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  avg_execution_time: number;
  avg_token_usage: number;
  last_execution: string;
  error_types: Record<string, number>;
}

interface AgentQualityStats {
  summary: {
    total_agents: number;
    total_executions: number;
    overall_success_rate: number;
    avg_response_time: number;
    active_agents: number;
  };
  agents: AgentMetrics[];
  timeline: Array<{
    timestamp: string;
    success: number;
    failure: number;
  }>;
  error_distribution: Record<string, number>;
}

const COLORS = ["#5b8cff", "#4fc3f7", "#8b7aff", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#ec4899"];

function getStatusTone(successRate: number) {
  if (successRate >= 0.9) return "success";
  if (successRate >= 0.7) return "warning";
  return "danger";
}

function getStatusLabel(successRate: number) {
  if (successRate >= 0.9) return "Excellent";
  if (successRate >= 0.7) return "Good";
  return "Poor";
}

export function AdminAgentQualityDashboard() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<AgentQualityStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState<string>("all");

  const fetchStats = async () => {
    try {
      setError(null);
      const data = await authRequest<AgentQualityStats>("/api/v1/admin/agent-quality/stats");
      setStats(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError(t("admin.agentQuality.authRequired", "Authentication required. Please sign in again."));
      } else {
        setError(t("admin.agentQuality.loadingError", "Failed to fetch agent quality data."));
      }
      console.error("Failed to fetch agent quality stats:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchStats();

    if (!autoRefresh) return;

    const interval = window.setInterval(() => {
      void fetchStats();
    }, 30000);

    return () => {
      window.clearInterval(interval);
    };
  }, [autoRefresh]);

  const handleRetry = () => {
    setLoading(true);
    setError(null);
    void fetchStats();
  };

  if (loading) {
    return (
      <main className="panel ops-wrap">
        <div className="skeleton-list" />
      </main>
    );
  }

  if (error) {
    return (
      <main className="panel ops-wrap">
        <div className="section-head">
          <strong>{t("admin.agentQuality.title", "Agent Quality Monitor")}</strong>
        </div>
        <div className="admin-state-panel is-error">
          <p>{error}</p>
          <button type="button" onClick={handleRetry} className="secondary tiny-btn">
            {t("common.retry", "Retry")}
          </button>
        </div>
      </main>
    );
  }

  const filteredAgents =
    selectedAgent === "all" ? stats?.agents || [] : stats?.agents.filter((agent) => agent.agent_name === selectedAgent) || [];

  const errorData = Object.entries(stats?.error_distribution || {}).map(([name, value]) => ({
    name,
    value,
  }));

  return (
    <main className="panel ops-wrap">
      <div className="section-head">
        <strong>{t("admin.agentQuality.title", "Agent Quality Monitor")}</strong>
        <div className="row-actions">
          <ExportButtons
            data={stats?.agents || []}
            filename={`agent-quality-${new Date().toISOString().split("T")[0]}`}
          />
          <button type="button" className="secondary tiny-btn" onClick={() => void fetchStats()}>
            {t("common.refresh", "Refresh")}
          </button>
        </div>
      </div>

      <div className="ops-controls-row">
        <select value={selectedAgent} onChange={(event) => setSelectedAgent(event.target.value)}>
          <option value="all">{t("admin.agentQuality.allAgents", "All Agents")}</option>
          {stats?.agents.map((agent) => (
            <option key={agent.agent_name} value={agent.agent_name}>
              {agent.agent_name}
            </option>
          ))}
        </select>

        <label className="ops-auto-refresh">
          <input type="checkbox" checked={autoRefresh} onChange={(event) => setAutoRefresh(event.target.checked)} />
          <span>{t("admin.ui.autoRefresh30", "Auto refresh every 30s")}</span>
        </label>
      </div>

      {stats && (
        <>
          <div className="ops-kpi-grid ops-kpi-grid-primary">
            <div className="ops-kpi-card">
              <span>{t("admin.agentQuality.totalAgents", "Total Agents")}</span>
              <strong>{stats.summary.total_agents}</strong>
            </div>
            <div className="ops-kpi-card">
              <span>{t("admin.agentQuality.activeAgents", "Active Agents")}</span>
              <strong style={{ color: "var(--success)" }}>{stats.summary.active_agents}</strong>
            </div>
            <div className="ops-kpi-card">
              <span>{t("admin.agentQuality.totalExecutions", "Total Executions")}</span>
              <strong>{stats.summary.total_executions}</strong>
            </div>
            <div className="ops-kpi-card">
              <span>{t("admin.agentQuality.successRate", "Success Rate")}</span>
              <strong style={{ color: `var(--${getStatusTone(stats.summary.overall_success_rate)})` }}>
                {(stats.summary.overall_success_rate * 100).toFixed(1)}%
              </strong>
            </div>
            <div className="ops-kpi-card">
              <span>{t("admin.agentQuality.avgResponseTime", "Avg Response Time")}</span>
              <strong>{stats.summary.avg_response_time.toFixed(2)}s</strong>
            </div>
          </div>

          <div className="ops-two-col">
            <section className="chart-container">
              <h3 className="chart-title">
                {t("admin.agentQuality.successFailureTimeline", "Success/Failure Timeline")}
              </h3>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={stats.timeline}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                  <XAxis dataKey="timestamp" stroke="var(--text-tertiary)" fontSize={10} />
                  <YAxis stroke="var(--text-tertiary)" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      background: "var(--surface)",
                      border: "1px solid var(--border-medium)",
                      borderRadius: "var(--radius-md)",
                    }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="success" stroke="var(--success)" strokeWidth={2} name={t("admin.agentQuality.success", "Success")} />
                  <Line type="monotone" dataKey="failure" stroke="var(--danger)" strokeWidth={2} name={t("admin.agentQuality.failure", "Failure")} />
                </LineChart>
              </ResponsiveContainer>
            </section>

            <section className="chart-container">
              <h3 className="chart-title">{t("admin.agentQuality.errorDistribution", "Error Distribution")}</h3>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie data={errorData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} labelLine={false}>
                    {errorData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </section>
          </div>

          <section className="admin-section-block">
            <h3 className="section-subtitle">{t("admin.agentQuality.agentPerformance", "Agent Performance Details")}</h3>
            <div className="audit-wrap">
              <table className="audit-table">
                <thead>
                  <tr>
                    <th style={{ width: "200px" }}>{t("admin.agentQuality.agentName", "Agent Name")}</th>
                    <th style={{ width: "100px", textAlign: "right" }}>{t("admin.agentQuality.executions", "Executions")}</th>
                    <th style={{ width: "100px", textAlign: "center" }}>{t("admin.agentQuality.successRate", "Success Rate")}</th>
                    <th style={{ width: "120px", textAlign: "right" }}>{t("admin.agentQuality.avgTime", "Avg Time")}</th>
                    <th style={{ width: "120px", textAlign: "right" }}>{t("admin.agentQuality.avgTokens", "Avg Tokens")}</th>
                    <th style={{ width: "180px" }}>{t("admin.agentQuality.lastExecution", "Last Execution")}</th>
                    <th style={{ width: "100px", textAlign: "center" }}>{t("admin.agentQuality.status", "Status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredAgents.map((agent) => {
                    const statusTone = getStatusTone(agent.success_rate);
                    return (
                      <tr key={agent.agent_name}>
                        <td style={{ fontWeight: 600, fontSize: "var(--text-sm)" }}>{agent.agent_name}</td>
                        <td style={{ textAlign: "right", fontFamily: "monospace" }}>{agent.total_executions}</td>
                        <td style={{ textAlign: "center" }}>
                          <span className={`badge badge-${statusTone}`}>{(agent.success_rate * 100).toFixed(1)}%</span>
                        </td>
                        <td style={{ textAlign: "right", fontFamily: "monospace" }}>{agent.avg_execution_time.toFixed(2)}s</td>
                        <td style={{ textAlign: "right", fontFamily: "monospace" }}>{agent.avg_token_usage.toFixed(0)}</td>
                        <td style={{ fontSize: "var(--text-xs)", fontFamily: "monospace" }}>
                          {agent.last_execution ? new Date(agent.last_execution).toLocaleString() : "N/A"}
                        </td>
                        <td style={{ textAlign: "center" }}>
                          <span className={`badge badge-${statusTone}`}>{getStatusLabel(agent.success_rate)}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section className="admin-section-block">
            <h3 className="section-subtitle">{t("admin.agentQuality.healthOverview", "Agent Health Overview")}</h3>
            <div className="ops-two-col">
              <div className="chart-container">
                <h3 className="chart-title">{t("admin.agentQuality.executionCount", "Execution Count by Agent")}</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={filteredAgents} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                    <XAxis type="number" stroke="var(--text-tertiary)" fontSize={11} />
                    <YAxis dataKey="agent_name" type="category" stroke="var(--text-tertiary)" fontSize={10} width={150} />
                    <Tooltip
                      contentStyle={{
                        background: "var(--surface)",
                        border: "1px solid var(--border-medium)",
                        borderRadius: "var(--radius-md)",
                      }}
                    />
                    <Bar dataKey="total_executions" fill="var(--accent)" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="chart-container">
                <h3 className="chart-title">{t("admin.agentQuality.avgExecutionTime", "Avg Execution Time by Agent")}</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={filteredAgents} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                    <XAxis type="number" stroke="var(--text-tertiary)" fontSize={11} />
                    <YAxis dataKey="agent_name" type="category" stroke="var(--text-tertiary)" fontSize={10} width={150} />
                    <Tooltip
                      contentStyle={{
                        background: "var(--surface)",
                        border: "1px solid var(--border-medium)",
                        borderRadius: "var(--radius-md)",
                      }}
                    />
                    <Bar dataKey="avg_execution_time" fill="var(--warning)" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
