import { useTranslation } from "react-i18next";
import type { BenchmarkTrendItem } from "@/types/api";

interface Props {
  benchmarkTrends: BenchmarkTrendItem[];
  benchmarkRunning: boolean;
  onRefresh: () => void;
  onReloadConfig: () => void;
  onExportAuditReport: () => void;
  onRunBenchmark: () => void;
  formatAuditTime: (ts?: string | null) => string;
}

export function AdminRagSettings({
  benchmarkTrends,
  benchmarkRunning,
  onRefresh,
  onReloadConfig,
  onExportAuditReport,
  onRunBenchmark,
  formatAuditTime,
}: Props) {
  const { t } = useTranslation();

  return (
    <main className="panel ops-wrap">
      <div className="section-head">
        <strong>{t("admin.ui.ragOps")}</strong>
        <div className="row-actions">
          <button type="button" className="secondary tiny-btn" onClick={onRefresh}>{t("common.refresh")}</button>
          <button type="button" className="secondary tiny-btn" onClick={onReloadConfig}>{t("admin.ui.hotReloadConfig")}</button>
          <button type="button" className="secondary tiny-btn" onClick={onExportAuditReport}>{t("admin.ui.exportAuditReport")}</button>
        </div>
      </div>

      <div className="section-head" style={{ marginTop: 8 }}>
        <strong>{t("admin.ui.benchmarkTrend")}</strong>
        <div className="row-actions">
          <button type="button" className="secondary tiny-btn" disabled={benchmarkRunning} onClick={onRunBenchmark}>
            {benchmarkRunning ? t("admin.ui.running") : t("admin.ui.runBenchmark")}
          </button>
        </div>
      </div>
      {benchmarkTrends.length === 0 && <p className="muted">{t("admin.ui.noTrend")}</p>}
      {benchmarkTrends.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>{t("admin.ui.time")}</th>
              <th>{t("admin.ui.samples")}</th>
              <th>P50(ms)</th>
              <th>P95(ms)</th>
              <th>Grounding(avg)</th>
              <th>Citations(avg)</th>
            </tr>
          </thead>
          <tbody>
            {[...benchmarkTrends].reverse().map((item, index) => (
              <tr key={`${item.created_at}-${index}`}>
                <td>{formatAuditTime(item.created_at)}</td>
                <td>{item.num_queries}</td>
                <td>{item.latency_ms?.p50 ?? "-"}</td>
                <td>{item.latency_ms?.p95 ?? "-"}</td>
                <td>{item.grounding_support_ratio?.avg ?? "-"}</td>
                <td>{item.citations?.avg ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
