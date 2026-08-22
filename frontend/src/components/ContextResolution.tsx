import React from 'react';
import { useTranslation } from 'react-i18next';

interface ContextResolutionProps {
  resolution: {
    original_query: string;
    resolved_query: string;
    needs_clarification: boolean;
    confidence: number;
    entities_resolved: string[];
    topic_switch: boolean;
  };
}

const ContextResolution: React.FC<ContextResolutionProps> = ({ resolution }) => {
  const { t } = useTranslation();

  // Don't render if no resolution occurred
  if (resolution.resolved_query === resolution.original_query && !resolution.topic_switch) {
    return null;
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600 dark:text-green-400';
    if (confidence >= 0.6) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  const getConfidenceLabel = (confidence: number) => {
    if (confidence >= 0.8) return t('contextResolution.confidence.high');
    if (confidence >= 0.6) return t('contextResolution.confidence.medium');
    return t('contextResolution.confidence.low');
  };

  return (
    <div className="mb-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
      <div className="flex items-start gap-3">
        {/* Icon */}
        <svg
          className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 10V3L4 14h7v7l9-11h-7z"
          />
        </svg>

        <div className="flex-1 space-y-2">
          {/* Title */}
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-100">
              {t('contextResolution.title')}
            </h4>
            <span className={`text-xs font-medium ${getConfidenceColor(resolution.confidence)}`}>
              {getConfidenceLabel(resolution.confidence)} ({Math.round(resolution.confidence * 100)}%)
            </span>
          </div>

          {/* Query Resolution */}
          {resolution.resolved_query !== resolution.original_query && (
            <div className="space-y-1">
              <div className="text-xs text-gray-600 dark:text-gray-400">
                {t('contextResolution.originalQuery')}:
              </div>
              <div className="text-sm text-gray-700 dark:text-gray-300 italic">
                "{resolution.original_query}"
              </div>
              <div className="flex items-center gap-2 my-1">
                <svg
                  className="w-4 h-4 text-blue-500 dark:text-blue-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 14l-7 7m0 0l-7-7m7 7V3"
                  />
                </svg>
                <span className="text-xs text-blue-600 dark:text-blue-400 font-medium">
                  {t('contextResolution.resolvedTo')}
                </span>
              </div>
              <div className="text-sm text-gray-900 dark:text-gray-100 font-medium">
                "{resolution.resolved_query}"
              </div>
            </div>
          )}

          {/* Entities Resolved */}
          {resolution.entities_resolved.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-gray-600 dark:text-gray-400">
                {t('contextResolution.entitiesResolved')}:
              </span>
              {resolution.entities_resolved.map((entity, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-800 text-blue-800 dark:text-blue-200"
                >
                  {entity}
                </span>
              ))}
            </div>
          )}

          {/* Topic Switch */}
          {resolution.topic_switch && (
            <div className="flex items-center gap-2 text-xs text-orange-600 dark:text-orange-400">
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"
                />
              </svg>
              {t('contextResolution.topicSwitch')}
            </div>
          )}

          {/* Needs Clarification Warning */}
          {resolution.needs_clarification && (
            <div className="flex items-center gap-2 p-2 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded">
              <svg
                className="w-4 h-4 text-yellow-600 dark:text-yellow-400 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
              <span className="text-xs text-yellow-800 dark:text-yellow-200">
                {t('contextResolution.needsClarification')}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ContextResolution;
