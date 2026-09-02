// 数据导出工具函数
export function exportToCSV(data: Array<Record<string, unknown>>, filename: string) {
  if (data.length === 0) return;

  const headers = Object.keys(data[0]);
  const csvContent = [
    headers.join(','),
    ...data.map(row =>
      headers.map(header => {
        const value = row[header];
        // Skip complex objects and arrays
        if (value && typeof value === 'object') {
          return JSON.stringify(value);
        }
        // 转义包含逗号或引号的值
        if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
          return `"${value.replace(/"/g, '""')}"`;
        }
        return value;
      }).join(',')
    )
  ].join('\n');

  downloadFile(csvContent, filename, 'text/csv;charset=utf-8;');
}

export function exportToJSON(data: Array<Record<string, unknown>>, filename: string) {
  const jsonContent = JSON.stringify(data, null, 2);
  downloadFile(jsonContent, filename, 'application/json');
}

export function exportTableToExcel(tableId: string, filename: string) {
  // 简化版Excel导出（使用HTML table）
  const table = document.getElementById(tableId);
  if (!table) return;

  const html = table.outerHTML;
  const blob = new Blob([html], { type: 'application/vnd.ms-excel' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${filename}.xls`;
  link.click();
  URL.revokeObjectURL(url);
}

function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// React组件：导出按钮
import { useTranslation } from "react-i18next";

interface ExportButtonsProps {
  data: Array<Record<string, unknown>>;
  filename: string;
  onExport?: () => void;
}

export function ExportButtons({ data, filename, onExport }: ExportButtonsProps) {
  const { t } = useTranslation();

  const handleExportCSV = () => {
    exportToCSV(data, `${filename}.csv`);
    onExport?.();
  };

  const handleExportJSON = () => {
    exportToJSON(data, `${filename}.json`);
    onExport?.();
  };

  return (
    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
      <button
        type="button"
        className="secondary tiny-btn"
        onClick={handleExportCSV}
        title={t("admin.export.csv", "Export as CSV")}
      >
        📊 CSV
      </button>
      <button
        type="button"
        className="secondary tiny-btn"
        onClick={handleExportJSON}
        title={t("admin.export.json", "Export as JSON")}
      >
        📄 JSON
      </button>
    </div>
  );
}
