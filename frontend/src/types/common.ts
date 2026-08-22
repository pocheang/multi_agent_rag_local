// Common utility types for the application

/**
 * Generic table data structure
 */
export interface TableData {
  headers: string[];
  rows: Array<Array<string | number | boolean | null>>;
}

/**
 * Generic error with optional response data
 */
export interface ApiErrorResponse {
  message?: string;
  status?: number;
  response?: {
    status?: number;
    data?: {
      detail?: string;
      message?: string;
    };
  };
}

/**
 * Generic log entry
 */
export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  event_id?: string;
  action?: string;
  resource_type?: string;
  result?: string;
  [key: string]: unknown;
}

/**
 * System operations data - compatible with OpsOverview
 */
export interface SystemOpsData {
  cpu_usage?: number;
  memory_usage?: number;
  disk_usage?: number;
  active_sessions?: number;
  generated_at?: string;
  window_hours?: number;
  status?: string;
  kpi?: Record<string, unknown>;
  users?: Record<string, unknown>;
  top_actions?: Array<Record<string, unknown>>;
  top_resource_types?: Array<Record<string, unknown>>;
  top_error_reasons?: Array<Record<string, unknown>>;
  slow_requests?: Array<Record<string, unknown>>;
  hourly?: Array<Record<string, unknown>>;
  services?: Record<string, unknown>;
  diagnostics?: Record<string, unknown>;
  [key: string]: unknown;
}

/**
 * Benchmark trend data point
 */
export interface BenchmarkTrend {
  timestamp: string;
  metric: string;
  value: number;
  [key: string]: unknown;
}

// Alias for backward compatibility
export type BenchmarkTrendItem = BenchmarkTrend;

/**
 * Export data structure
 */
export interface ExportData {
  headers: string[];
  rows: Array<Record<string, string | number | boolean | null>>;
}

/**
 * Unknown JSON value (safer than any)
 */
export type JsonValue = string | number | boolean | null | JsonObject | JsonArray;
export interface JsonObject {
  [key: string]: JsonValue;
}
export type JsonArray = JsonValue[];
