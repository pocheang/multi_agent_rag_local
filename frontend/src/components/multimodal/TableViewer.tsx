import React from 'react';
import type { TableData } from '@/types/common';

interface TableViewerProps {
  data: TableData;
  summary?: string;
  maxRows?: number;
}

/**
 * Component for displaying structured table data
 */
export const TableViewer: React.FC<TableViewerProps> = ({
  data,
  summary,
  maxRows = 10,
}) => {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const displayRows = isExpanded ? data.rows : data.rows.slice(0, maxRows);
  const hasMore = data.rows.length > maxRows;

  return (
    <div className="table-viewer border rounded-lg p-4 my-4 bg-white">
      {/* Summary */}
      {summary && (
        <div className="mb-3 text-sm text-gray-600">
          {summary}
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {data.headers.map((header, idx) => (
                <th
                  key={idx}
                  className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {displayRows.map((row, rowIdx) => (
              <tr key={rowIdx} className="hover:bg-gray-50">
                {row.map((cell, cellIdx) => (
                  <td
                    key={cellIdx}
                    className="px-4 py-2 text-sm text-gray-900 whitespace-nowrap"
                  >
                    {cell !== null && cell !== undefined ? String(cell) : '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Expand/Collapse */}
      {hasMore && (
        <div className="mt-3 text-center">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-sm text-blue-600 hover:underline"
          >
            {isExpanded
              ? '收起'
              : `显示全部 ${data.rows.length} 行 (当前显示 ${maxRows} 行)`}
          </button>
        </div>
      )}
    </div>
  );
};

export default TableViewer;
