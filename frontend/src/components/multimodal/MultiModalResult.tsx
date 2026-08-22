import React from 'react';
import { ImagePreview } from './ImagePreview';
import { TableViewer } from './TableViewer';
import type { TableData } from '@/types/common';

interface MultiModalResultProps {
  result: {
    type: 'text' | 'image' | 'table' | 'chart';
    content: string;
    image_url?: string;
    description?: string;
    ocr_text?: string;
    table_data?: TableData;
    summary?: string;
    metadata?: Record<string, unknown>;
  };
}

/**
 * Component for displaying multi-modal retrieval results
 */
export const MultiModalResult: React.FC<MultiModalResultProps> = ({ result }) => {
  return (
    <div className="multimodal-result">
      {result.type === 'text' && (
        <div className="text-content prose dark:prose-invert max-w-none">
          <p className="whitespace-pre-wrap">{result.content}</p>
        </div>
      )}

      {result.type === 'image' && result.image_url && (
        <ImagePreview
          src={result.image_url}
          description={result.description || result.content}
          ocrText={result.ocr_text}
        />
      )}

      {result.type === 'table' && result.table_data && (
        <TableViewer
          data={result.table_data}
          summary={result.summary || result.content}
        />
      )}

      {result.type === 'chart' && (
        <div className="chart-content border rounded-lg p-4 my-4 bg-blue-50 dark:bg-blue-900/20">
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0">
              <svg
                className="w-6 h-6 text-blue-600 dark:text-blue-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
            </div>
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">
                图表内容
              </h4>
              <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                {result.description || result.content}
              </p>
              {result.image_url && (
                <img
                  src={result.image_url}
                  alt="Chart"
                  className="mt-3 rounded-md max-h-[300px] object-contain"
                />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Metadata badge */}
      {result.metadata && typeof result.metadata === 'object' && (
        <div className="mt-2 flex items-center space-x-2 text-xs text-gray-500 dark:text-gray-400">
          <span className="px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded">
            {result.type === 'text' && '文本'}
            {result.type === 'image' && '图片'}
            {result.type === 'table' && '表格'}
            {result.type === 'chart' && '图表'}
          </span>
          {'page_number' in result.metadata && result.metadata.page_number !== null && result.metadata.page_number !== undefined && (
            <span>第 {String(result.metadata.page_number)} 页</span>
          )}
        </div>
      )}
    </div>
  );
};

export default MultiModalResult;
