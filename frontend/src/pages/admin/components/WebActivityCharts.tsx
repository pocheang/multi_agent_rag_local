import { useTranslation } from "react-i18next";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface ChartData {
  hourlyData: Array<{ hour: string; searches: number }>;
  websitesData: Array<{ domain: string; visit_count: number; avg_trust_score: number }>;
}

interface Props {
  data: ChartData;
}

export function WebActivityCharts({ data }: Props) {
  const { t } = useTranslation();

  return (
    <div className="ops-two-col admin-section-block">
      <div className="chart-container">
        <h3 className="chart-title">{t("admin.webActivity.hourlyDistribution", "24-Hour Activity Distribution")}</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={data.hourlyData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
            <XAxis dataKey="hour" stroke="var(--text-tertiary)" fontSize={12} />
            <YAxis stroke="var(--text-tertiary)" fontSize={12} />
            <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border-medium)", borderRadius: "var(--radius-md)" }} />
            <Bar dataKey="searches" fill="var(--accent)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-container">
        <h3 className="chart-title">{t("admin.webActivity.topWebsites", "Top 10 Websites")}</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={data.websitesData} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
            <XAxis type="number" stroke="var(--text-tertiary)" fontSize={12} />
            <YAxis dataKey="domain" type="category" stroke="var(--text-tertiary)" fontSize={11} width={120} />
            <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border-medium)", borderRadius: "var(--radius-md)" }} />
            <Bar dataKey="visit_count" fill="var(--info)" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}