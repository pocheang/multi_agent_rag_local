import type { UserIdentity } from "./auth";

export type AuthUser = UserIdentity;

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
  pinned?: boolean;
};

export type Citation = {
  source: string;
  content: string;
  document_id?: string;
  page?: number;
  metadata?: Record<string, unknown>;
};

export type PipelineProfile = "standard" | "strict_quality" | "advanced";

export type StandardQueryResponse = {
  answer: string;
  route: string;
  citations: Citation[];
  graph_entities: string[];
  web_used: boolean;
  detected_language: string;
  debug: Record<string, unknown>;
  execution_id: string | null;
};

export type StrictQualityQueryResponse = {
  answer: string;
  citations: Citation[];
  quality_report: Record<string, unknown>;
  route_used: string;
  route_reason: string;
  skill_used: string;
  agent_class: string;
  execution_metadata: Record<string, unknown>;
};

export type AdvancedQueryResponse = {
  query: string;
  decomposed_query: Record<string, unknown> | null;
  sub_query_results: Array<Record<string, unknown>>;
  final_answer: string;
  answer_quality: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
};

export type NormalizedQueryResult = {
  profile: PipelineProfile;
  answer: string;
  citations: Citation[];
  route?: string;
  qualityReport?: Record<string, unknown>;
  executionMetadata?: Record<string, unknown>;
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
  quality_report?: Record<string, unknown>;
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
    } | {
      source: string;
      rel1?: string;
      middle: string;
      rel2?: string;
      target: string;
    }>;
    context?: string;
  };
};

export type SessionMessage = {
  message_id: string | null;
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
  document_id?: string | null;
  indexing_status?: "pending" | "indexing" | "ready" | "failed" | string;
  indexing_stage?: string;
  indexing_error?: string;
  triplets_written?: number;
  parser_profile?: string;
};

export type FileIndexActionResponse = {
  ok: boolean;
  filename: string;
  chunks_removed: number;
  vector_ids_removed: number;
  triplets_removed: number;
  file_removed: boolean;
  loaded_documents?: number;
  chunks_indexed?: number;
  triplets_written?: number;
  pages_by_source?: Record<string, number>;
  skipped?: boolean;
  reason?: string;
};

export type UploadResponse = {
  ok: boolean;
  filenames: string[];
  skipped_files?: string[];
  visibility_applied?: "private" | "public" | string;
  assigned_agent_classes?: Record<string, string>;
  document_ids?: string[];
  indexing_status?: string;
  duplicate_files?: string[];
  reused_document_ids?: string[];
  loaded_documents: number;
  chunks_indexed: number;
  triplets_written: number;
  pages_by_source?: Record<string, number>;
};

export type IndexHealthResponse = {
  total_documents: number;
  ready_documents: number;
  failed_documents: number;
  indexing_documents: number;
  total_chunks: number;
  total_triplets: number;
  documents: IndexedFileSummary[];
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
  credit_balance: number;
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

export type ModelProvider = "local" | "ollama" | "openai" | "deepseek" | "anthropic" | "custom";

export type ModelCatalogItem = {
  id: string;
  label: string;
  roles: Array<"chat" | "reasoning" | "embedding" | string>;
  recommended?: boolean;
  deprecated_after?: string | null;
};

export type ProviderCatalogEntry = {
  label: string;
  base_url: string;
  default_chat_model: string;
  default_reasoning_model: string;
  default_embedding_model: string;
  requires_api_key: boolean;
  supports_embeddings: boolean;
  api_style: "local" | "ollama" | "openai" | "anthropic" | string;
  note?: string;
  models: ModelCatalogItem[];
};

export type ModelCatalogResponse = {
  version: string;
  providers: Record<ModelProvider, ProviderCatalogEntry>;
};

export type AdminRuntimeSnapshot = {
  generated_at: string;
  status: "healthy" | "degraded" | string;
  blocking_services: string[];
  resources: {
    cpu_percent: number;
    memory_percent: number;
    disk_percent: number;
    process_memory_mb: number;
  };
  traffic: {
    window_seconds: number;
    requests_total: number;
    requests_per_second: number;
    avg_response_ms: number;
    p95_response_ms: number;
    error_rate_percent: number;
    active_requests: number;
  };
  services: Record<string, OpsServiceHealth & { message?: string }>;
  model: AdminModelSettingsView;
};

export type AdminModelSettingsPayload = {
  enabled: boolean;
  provider: ModelProvider | string;
  api_key: string;
  base_url: string;
  chat_model: string;
  reasoning_model: string;
  embedding_model: string;
  temperature: number;
  max_tokens: number;
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

// Clarification types
export type ClarificationQuestion = {
  question: string;
  options: string[];
  allow_custom_input: boolean;
  field_name: string;
};

export type ClarificationContext = {
  collected_info: Record<string, string>;
  asked_questions: string[];
  clarification_round: number;
  max_rounds: number;
  intent: string;
};

export type ClarificationCheckRequest = {
  question: string;
  session_id: string;
  field_name?: string;
  answer?: string;
};

export type ClarificationResponse = {
  action: "CONTINUE" | "NEED_CLARIFICATION";
  clarification?: ClarificationQuestion;
  context: ClarificationContext;
  route?: {
    intent: string;
    route?: string;
    confidence: number;
    requires_plan: boolean;
    allowed_capabilities: string[];
    reason: string;
  };
};
