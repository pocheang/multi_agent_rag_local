import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  LineChart,
  Line,
  CartesianGrid,
  Legend,
  Area,
  AreaChart,
} from "recharts";
import type { AdminRuntimeSnapshot } from "@/types/api";
import { adminOpsApi } from "@/lib/admin-ops-api";

export function AdminSystemMonitor() {
  const { t } = useTranslation();
  const [snapshot, setSnapshot] = useState<AdminRuntimeSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadSnapshot = async () => {
    try {
      setLoading(true);
      setError("");
      const data = await adminOpsApi.adminRuntimeSnapshot();
      setSnapshot(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSnapshot();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = window.setInterval(() => void loadSnapshot(), 3000);
    return () => window.clearInterval(timer);
  }, [autoRefresh]);

  if (loading && !snapshot) {
    return (
      <main className="panel">
        <div className="status">{t("common.loading", "Loading...")}</div>
      </main>
    );
  }

  if (error && !snapshot) {
    return (
      <main className="panel">
        <div className="status error">{error}</div>
        <button type="button" onClick={() => void loadSnapshot()}>
          {t("common.retry", "Retry")}
        </button>
      </main>
    );
  }

  if (!snapshot) {
    return (
      <main className="panel">
        <div className="status">{t("common.noData", "No data available")}</div>
      </main>
    );
  }

  const statusClass = snapshot.status === "healthy" ? "success" : "error";

  // Prepare chart data
  const resourceData = [
    { name: "CPU", value: snapshot.resources.cpu_percent, fill: "#3b82f6" },
    { name: "Memory", value: snapshot.resources.memory_percent, fill: "#8b5cf6" },
    { name: "Disk", value: snapshot.resources.disk_percent, fill: "#06b6d4" },
  ];

  const servicesData = Object.entries(snapshot.services).map(([name, health]) => ({
    name,
    status: health.ok ? 1 : 0,
    latency: health.latency_ms || 0,
  }));

  return (
    <>
      <main className="panel">
        <div className="row-actions">
          <h3>{t("pages.admin.monitor.title", "Runtime Monitor")}</h3>
          <div className="row-actions">
            <label>
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
              {t("pages.admin.monitor.autoRefresh", "Auto-refresh (3s)")}
            </label>
            <button type="button" className="secondary" onClick={() => void loadSnapshot()} disabled={loading}>
              {loading ? t("common.loading", "Loading...") : t("common.refresh", "Refresh")}
            </button>
          </div>
        </div>

        {error && <div className="status error">{error}</div>}

        <div className="ops-kpi-grid ops-kpi-grid-primary">
          <div className={`ops-kpi-card ${statusClass === 'success' ? 'is-success' : 'is-danger'}`}>
            <span>{t("pages.admin.monitor.systemStatus", "System Status")}</span>
            <strong>{snapshot.status.toUpperCase()}</strong>
            <p style={{ fontSize: '0.7rem', marginTop: '0.25rem', color: 'var(--admin-text-tertiary)' }}>
              {new Date(snapshot.generated_at).toLocaleTimeString()}
            </p>
          </div>

          <div className="ops-kpi-card">
            <span>{t("pages.admin.monitor.cpu", "CPU")}</span>
            <strong>{snapshot.resources.cpu_percent.toFixed(1)}%</strong>
          </div>

          <div className="ops-kpi-card">
            <span>{t("pages.admin.monitor.memory", "Memory")}</span>
            <strong>{snapshot.resources.memory_percent.toFixed(1)}%</strong>
          </div>

          <div className="ops-kpi-card">
            <span>{t("pages.admin.monitor.disk", "Disk")}</span>
            <strong>{snapshot.resources.disk_percent.toFixed(1)}%</strong>
          </div>

          <div className="ops-kpi-card">
            <span>{t("pages.admin.monitor.totalRequests", "Total Requests")}</span>
            <strong>{snapshot.traffic.requests_total}</strong>
            <p style={{ fontSize: '0.7rem', marginTop: '0.25rem', color: 'var(--admin-text-tertiary)' }}>
              {t("pages.admin.monitor.last", "Last")} {snapshot.traffic.window_seconds}s
            </p>
          </div>

          <div className="ops-kpi-card">
            <span>{t("pages.admin.monitor.avgResponseTime", "Avg Response")}</span>
            <strong>{snapshot.traffic.avg_response_ms.toFixed(1)} ms</strong>
          </div>

          <div className="ops-kpi-card">
            <span>{t("pages.admin.monitor.errorRate", "Error Rate")}</span>
            <strong>{snapshot.traffic.error_rate_percent.toFixed(2)}%</strong>
          </div>

          <div className="ops-kpi-card">
            <span>{t("pages.admin.monitor.activeRequests", "Active Requests")}</span>
            <strong>{snapshot.traffic.active_requests}</strong>
          </div>
        </div>
      </main>

      <div className="admin-ops-grid">
        <main className="panel">
          <h3>{t("pages.admin.monitor.resources", "System Resources")}</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={resourceData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" stroke="#94a3b8" style={{ fontSize: '14px' }} />
              <YAxis stroke="#94a3b8" domain={[0, 100]} style={{ fontSize: '14px' }} />
              <Tooltip
                contentStyle={{
                  background: "#0f172a",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.3)"
                }}
                labelStyle={{ color: "#f1f5f9", fontWeight: 600 }}
                itemStyle={{ color: "#cbd5e1" }}
                formatter={(value: unknown) => [`${Number(value).toFixed(1)}%`, 'Usage']}
              />
              <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                {resourceData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </main>

        <main className="panel">
          <h3>{t("pages.admin.monitor.trafficMetrics", "Traffic Metrics")}</h3>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart
              data={[
                {
                  name: 'Current',
                  requests: snapshot.traffic.requests_total,
                  errors: Math.round((snapshot.traffic.requests_total * snapshot.traffic.error_rate_percent) / 100),
                }
              ]}
              margin={{ top: 20, right: 30, left: 0, bottom: 5 }}
            >
              <defs>
                <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.1}/>
                </linearGradient>
                <linearGradient id="colorErrors" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0.1}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" stroke="#94a3b8" style={{ fontSize: '14px' }} />
              <YAxis stroke="#94a3b8" style={{ fontSize: '14px' }} />
              <Tooltip
                contentStyle={{
                  background: "#0f172a",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.3)"
                }}
                labelStyle={{ color: "#f1f5f9", fontWeight: 600 }}
              />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <Area
                type="monotone"
                dataKey="requests"
                stroke="#3b82f6"
                fillOpacity={1}
                fill="url(#colorRequests)"
                name="Total Requests"
              />
              <Area
                type="monotone"
                dataKey="errors"
                stroke="#ef4444"
                fillOpacity={1}
                fill="url(#colorErrors)"
                name="Errors"
              />
            </AreaChart>
          </ResponsiveContainer>
        </main>
      </div>

      <div className="admin-ops-grid">
        <main className="panel">
          <h3>{t("pages.admin.monitor.serviceLatency", "Service Latency")}</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={servicesData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" stroke="#94a3b8" style={{ fontSize: '14px' }} />
              <YAxis stroke="#94a3b8" style={{ fontSize: '14px' }} />
              <Tooltip
                contentStyle={{
                  background: "#0f172a",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.3)"
                }}
                labelStyle={{ color: "#f1f5f9", fontWeight: 600 }}
                itemStyle={{ color: "#cbd5e1" }}
                formatter={(value: unknown) => [`${Number(value)} ms`, 'Latency']}
              />
              <Bar dataKey="latency" fill="#10b981" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </main>

        <main className="panel">
          <h3>{t("pages.admin.monitor.responseTime", "Response Time")}</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart
              data={[
                { name: 'Avg', value: snapshot.traffic.avg_response_ms },
                { name: 'P95', value: snapshot.traffic.p95_response_ms },
              ]}
              margin={{ top: 20, right: 30, left: 0, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" stroke="#94a3b8" style={{ fontSize: '14px' }} />
              <YAxis stroke="#94a3b8" style={{ fontSize: '14px' }} />
              <Tooltip
                contentStyle={{
                  background: "#0f172a",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.3)"
                }}
                labelStyle={{ color: "#f1f5f9", fontWeight: 600 }}
                itemStyle={{ color: "#cbd5e1" }}
                formatter={(value: unknown) => [`${Number(value).toFixed(1)} ms`, 'Response Time']}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#f59e0b"
                strokeWidth={3}
                dot={{ fill: '#f59e0b', r: 6 }}
                activeDot={{ r: 8 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </main>
      </div>

      <main className="panel">
        <h3>{t("pages.admin.monitor.services", "Service Health")}</h3>
        <div className="admin-service-grid">
          {Object.entries(snapshot.services).map(([name, health]) => (
            <div key={name} className={`admin-service-card ${health.ok ? 'is-online' : 'is-offline'}`}>
              <div className="admin-service-signal"></div>
              <div style={{ minWidth: 0 }}>
                <strong>{name}</strong>
                <p>
                  {health.required ? t("common.required", "Required") : t("common.optional", "Optional")}
                  {health.latency_ms !== undefined && ` • ${health.latency_ms}ms`}
                </p>
              </div>
              <code>{health.ok ? "OK" : "FAILED"}</code>
            </div>
          ))}
        </div>
      </main>

      <main className="panel">
        <h3>{t("pages.admin.monitor.model", "Model Configuration")}</h3>
        <div className="ops-kpi-grid ops-kpi-grid-secondary">
          <div className="ops-kpi-card">
            <span>{t("pages.admin.monitor.enabled", "Enabled")}</span>
            <strong>{snapshot.model.enabled ? t("common.yes", "是") : t("common.no", "否")}</strong>
          </div>

          <div className="ops-kpi-card">
            <span>{t("pages.admin.monitor.provider", "Provider")}</span>
            <strong>{snapshot.model.provider}</strong>
          </div>

          <div className="ops-kpi-card">
            <span>{t("pages.admin.monitor.chatModel", "Chat Model")}</span>
            <strong style={{ fontSize: 'var(--text-lg)' }}>{snapshot.model.chat_model}</strong>
          </div>

          <div className="ops-kpi-card">
            <span>{t("pages.admin.monitor.reasoningModel", "Reasoning Model")}</span>
            <strong style={{ fontSize: 'var(--text-lg)' }}>{snapshot.model.reasoning_model}</strong>
          </div>

          <div className="ops-kpi-card">
            <span>{t("pages.admin.monitor.embeddingModel", "Embedding Model")}</span>
            <strong style={{ fontSize: 'var(--text-lg)' }}>{snapshot.model.embedding_model || "-"}</strong>
          </div>

          <div className="ops-kpi-card" style={{ gridColumn: 'span 2' }}>
            <span>{t("pages.admin.monitor.baseUrl", "Base URL")}</span>
            <strong style={{ fontSize: 'var(--text-sm)', wordBreak: 'break-all' }}>{snapshot.model.base_url}</strong>
          </div>
        </div>
      </main>
    </>
  );
}
