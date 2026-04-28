export type AuthUser = {
  user_id: string;
  username: string;
  role: "admin" | "analyst" | "viewer" | string;
  status: "active" | "disabled" | string;
};

export type LoginResponse = {
  token: string;
  token_type: string;
  expires_at: string;
  user: AuthUser;
};

export type SessionSummary = {
  session_id: string;
  title: string;
  message_count: number;
  updated_at?: string;
};

export type Citation = {
  source?: string;
  content?: string;
};

export type SessionMessageMetadata = {
  route?: string;
  execution_route?: string;
  retrieval_strategy?: string;
  agent_class?: string;
  web_used?: boolean;
  latency_ms?: number;
  thoughts?: string[];
  graph_entities?: string[];
  citations?: Citation[];
  current_status?: string;
  execution_steps?: Array<{
    kind: string;
    label: string;
    detail?: string;
    at?: string;
  }>;
  graph_result?: {
    neighbors: Array<{
      entity: string;
      relation: string;
      direction: "in" | "out";
    }>;
    paths: Array<{
      entities: string[];
      relations: string[];
    }>;
    context?: string;
  };
};

export type SessionMessage = {
  message_id: string;
  role: "user" | "assistant" | string;
  content: string;
  created_at?: string;
  metadata?: SessionMessageMetadata;
};

export type SessionDetail = {
  session_id: string;
  title: string;
  message_count?: number;
  messages: SessionMessage[];
};

export type IndexedFileSummary = {
  filename: string;
  source: string;
  chunks: number;
  pages?: number[];
  page_count?: number;
  agent_class?: string;
  owner_user_id?: string | null;
  visibility?: "private" | "public" | string;
  exists_on_disk?: boolean;
  in_uploads?: boolean;
};

export type FileIndexActionResponse = {
  filename: string;
  chunks_removed: number;
  triplets_removed: number;
  file_removed: boolean;
  loaded_documents?: number;
  chunks_indexed?: number;
  triplets_written?: number;
  pages_by_source?: Record<string, number>;
};

export type UploadResponse = {
  filenames: string[];
  skipped_files?: string[];
  visibility_applied?: "private" | "public" | string;
  assigned_agent_classes?: Record<string, string>;
  loaded_documents: number;
  chunks_indexed: number;
  triplets_written: number;
  pages_by_source?: Record<string, number>;
};

export type PromptTemplate = {
  prompt_id: string;
  title: string;
  content: string;
  agent_class?: string;
};

export type PromptCheckResponse = {
  title: string;
  content: string;
  issues: string[];
  suggestions: string[];
};

export type AdminUserSummary = {
  user_id: string;
  username: string;
  role: string;
  status: string;
  created_by_user_id?: string | null;
  created_by_username?: string | null;
  admin_ticket_id?: string | null;
  has_admin_approval_token?: boolean;
  business_unit?: string | null;
  department?: string | null;
  user_type?: string | null;
  data_scope?: string | null;
  is_online?: boolean;
  is_online_10m?: boolean;
  created_at?: string;
};

export type AuditLogEntry = {
  event_id: string;
  actor_user_id?: string;
  actor_role?: string;
  action: string;
  event_category?: string;
  severity?: string;
  resource_type: string;
  resource_id?: string;
  result: string;
  detail?: string;
  ip?: string | null;
  user_agent?: string | null;
  created_at?: string;
};

export type OpsServiceHealth = {
  ok: boolean;
  required?: boolean;
  latency_ms?: number;
  error?: string;
  path?: string;
  models?: string[];
};

export type OpsOverview = {
  generated_at: string;
  window_hours: number;
  status: "healthy" | "degraded" | string;
  kpi: {
    requests_total: number;
    requests_success: number;
    requests_error: number;
    error_rate_percent: number;
    active_users: number;
    active_sessions: number;
    queries: number;
    uploads: number;
    login_success: number;
    login_failed: number;
  };
  users: {
    total: number;
    active: number;
    disabled: number;
    admin: number;
  };
  top_actions: Array<{ action: string; count: number }>;
  top_resource_types: Array<{ resource_type: string; count: number }>;
  top_error_reasons: Array<{ reason: string; count: number }>;
  slow_requests: Array<{
    ts: string;
    method: string;
    path: string;
    status_code: number;
    duration_ms: number;
    error?: string;
  }>;
  hourly: Array<{ bucket: string; count: number; errors: number }>;
  services: Record<string, OpsServiceHealth>;
  diagnostics?: {
    python_executable: string;
    python_version: string;
    conda_prefix?: string;
    conda_env?: string;
    model_backend?: string;
    reasoning_model_backend?: string;
    ollama_base_url?: string;
    ollama_chat_model?: string;
    ollama_embed_model?: string;
    global_model_settings?: AdminModelSettingsView;
    recent_errors?: Array<{
      created_at: string;
      level: string;
      logger: string;
      message: string;
      exception?: string;
    }>;
    recent_failures?: Array<{
      ts: string;
      path: string;
      status_code: number;
      error?: string;
      duration_ms: number;
    }>;
  };
  filters?: {
    actor_user_id?: string;
    action_keyword?: string;
  };
};

export type AdminModelSettingsView = {
  enabled: boolean;
  provider: string;
  api_key_masked: string;
  base_url: string;
  chat_model: string;
  reasoning_model: string;
  embedding_model: string;
  temperature: number;
  max_tokens: number;
  embedding_reindexed?: boolean;
  records_reindexed?: number;
};

export type RetrievalProfileState = {
  active_profile: string;
  config_default_profile: string;
  follow_config_default: boolean;
  canary: {
    enabled: boolean;
    baseline_percent: number;
    safe_percent: number;
    seed: string;
  };
  updated_at: string;
  profiles?: Array<{ id: string; label: string; desc: string }>;
};

export type BenchmarkTrendItem = {
  created_at: string;
  num_queries: number;
  strategy: string;
  latency_ms: {
    p50: number;
    p95: number;
    avg: number;
  };
  grounding_support_ratio: {
    avg: number;
    min: number;
  };
  citations: {
    avg: number;
    max: number;
  };
};

export type SystemLogEntry = {
  created_at: string;
  level: string;
  logger: string;
  message: string;
  module?: string;
  func?: string;
  line?: number;
  thread?: string;
  exception?: string;
};
