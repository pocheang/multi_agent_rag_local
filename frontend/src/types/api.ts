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
  agent_class?: string;
  web_used?: boolean;
  thoughts?: string[];
  graph_entities?: string[];
  citations?: Citation[];
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
  owner_user_id?: string | null;
  visibility?: "private" | "public" | string;
  exists_on_disk?: boolean;
  in_uploads?: boolean;
  pages?: number[];
};

export type FileIndexActionResponse = {
  filename: string;
  chunks_removed: number;
  triplets_removed: number;
  file_removed: boolean;
  loaded_documents?: number;
  chunks_indexed?: number;
  triplets_written?: number;
};

export type UploadResponse = {
  filenames: string[];
  skipped_files?: string[];
  visibility_applied?: "private" | "public" | string;
  loaded_documents: number;
  chunks_indexed: number;
  triplets_written: number;
};

export type PromptTemplate = {
  prompt_id: string;
  title: string;
  content: string;
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
  filters?: {
    actor_user_id?: string;
    action_keyword?: string;
  };
};
