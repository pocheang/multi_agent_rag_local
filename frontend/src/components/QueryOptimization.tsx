import React from 'react';
import { useTranslation } from 'react-i18next';

interface QueryOptimizationProps {
  optimization: {
    should_optimize: boolean;
    quality: {
      score: number;
      level: 'high' | 'medium' | 'low' | 'very_low';
      issues: string[];
    };
    suggestion: {
      message: string;
      clarifications: string[];
      examples: string[];
    };
  };
  onExampleClick: (example: string) => void;
}

const QueryOptimization: React.FC<QueryOptimizationProps> = ({
  optimization,
  onExampleClick,
}) => {
  const { t } = useTranslation();

  if (!optimization.should_optimize) {
    return null;
  }

  const { quality, suggestion } = optimization;

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'very_low':
        return 'border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950';
      case 'low':
        return 'border-orange-200 bg-orange-50 dark:border-orange-900 dark:bg-orange-950';
      case 'medium':
        return 'border-yellow-200 bg-yellow-50 dark:border-yellow-900 dark:bg-yellow-950';
      default:
        return 'border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950';
    }
  };

  const getLevelIcon = (level: string) => {
    if (level === 'very_low' || level === 'low') {
      return (
        <svg className="w-5 h-5 text-red-500 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      );
    }
    return (
      <svg className="w-5 h-5 text-yellow-500 dark:text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    );
  };

  return (
    <div
      className={`rounded-lg border-2 p-4 mb-4 transition-all ${getLevelColor(
        quality.level
      )}`}
    >
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        {getLevelIcon(quality.level)}
        <div className="flex-1">
          <h3 className="font-semibold text-sm text-gray-900 dark:text-gray-100">
            {t('queryOptimization.title')}
          </h3>
          <p className="text-sm text-gray-700 dark:text-gray-300 mt-1">
            {suggestion.message}
          </p>
        </div>
      </div>

      {/* Clarifications */}
      {suggestion.clarifications.length > 0 && (
        <div className="mb-3">
          <h4 className="text-xs font-medium text-gray-700 dark:text-gray-400 mb-2">
            {t('queryOptimization.suggestClarify')}
          </h4>
          <ul className="space-y-1">
            {suggestion.clarifications.map((clarification, index) => (
              <li
                key={index}
                className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2"
              >
                <span className="text-gray-400 dark:text-gray-600">•</span>
                <span>{clarification}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Examples */}
      {suggestion.examples.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-gray-700 dark:text-gray-400 mb-2">
            {t('queryOptimization.examples')}
          </h4>
          <div className="space-y-2">
            {suggestion.examples.map((example, index) => (
              <button
                key={index}
                onClick={() => onExampleClick(example)}
                className="w-full text-left px-3 py-2 rounded-md bg-white dark:bg-gray-800
                         border border-gray-200 dark:border-gray-700
                         hover:border-blue-400 dark:hover:border-blue-600
                         hover:bg-blue-50 dark:hover:bg-blue-950
                         transition-all duration-200 group
                         flex items-center justify-between gap-2"
              >
                <span className="text-sm text-gray-700 dark:text-gray-300 flex-1">
                  {example}
                </span>
                <svg className="w-4 h-4 text-gray-400 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Quality Score (optional, subtle) */}
      <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-500">
          <span>{t('queryOptimization.qualityScore')}</span>
          <span className="font-mono">{quality.score.toFixed(0)}/100</span>
        </div>
      </div>
    </div>
  );
};

export default QueryOptimization;
