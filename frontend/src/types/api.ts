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
  /** Reader-facing marker ("[1]") matching the one in the answer text. */
  marker?: string;
  source: string;
  content: string;
  document_id?: string;
  page?: number;
  metadata?: Record<string, unknown>;
};

/** One governed tool invocation, as the run reports it. */
export type ToolRun = {
  tool_id: string;
  status: string;
  summary: string;
};

/** A governed action the run produced but did not perform. */
export type PendingApproval = {
  tool_id: string;
  token: string;
  summary: string;
};

export type AdvancedQueryResponse = {
  query: string;
  decomposed_query: Record<string, unknown> | null;
  sub_query_results: Array<Record<string, unknown>>;
  final_answer: string;
  status?: "complete" | "pending_approval";
  pending_approval?: PendingApproval | null;
  answer_quality: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
};

export type NormalizedQueryResult = {
  answer: string;
  citations: Citation[];
  /** "pending_approval" means the answer is complete but the action the user
   *  asked for is waiting on their confirmation and has NOT been performed. */
  status: "complete" | "pending_approval";
  pendingApproval: PendingApproval | null;
  toolRuns: ToolRun[];
  route?: string;
  executionId?: string;
  qualityReport?: Record<string, unknown>;
  executionMetadata?: Record<string, unknown>;
};

export type RetrievalSourceOutcome = {
  source: string;
  status: string;
  count: number;
  /** Why a source did not complete. `EmptyAccessScope` means the caller has no
   *  documents, which is not a failure. */
  reason?: string | null;
};

export type SessionMessageMetadata = {
  route?: string;
  execution_route?: string;
  agent_class?: string;
  web_used?: boolean;
  /** Which sources the run actually reached, and what each returned. Derived
   *  from the run's own diagnostics rather than assumed: `web_used` alone was a
   *  single bit for a system with eight sources, and nothing set it. */
  sources?: RetrievalSourceOutcome[];
  contributing_sources?: string[];
  latency_ms?: number;
  thoughts?: string[];
  graph_entities?: string[];
  citations?: Citation[];
  /** What the governed tool loop actually did, so a multi-step run leaves a
   *  record instead of only whatever the answer prose mentions. */
  tool_runs?: ToolRun[];
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
  // Whether these settings are actually in effect. MODEL_BACKEND=local in the
  // process environment makes the backend discard the global override, so a
  // saved configuration can be stored and inert at the same time.
  environment_pinned?: boolean;
  pinned_reason?: string;
  records_reindexed?: number;
};

export type BenchmarkTrendItem = {
  created_at: string;
  num_queries: number;
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
  original_query?: string;
};

export type ClarificationCheckRequest = {
  question: string;
  session_id: string;
  field_name?: string;
  answer?: string;
  workflow_thread_id?: string;
  resume_token?: string;
};

export type ClarificationResponse = {
  action: "CONTINUE" | "NEED_CLARIFICATION";
  clarification?: ClarificationQuestion;
  context: ClarificationContext;
  complete_query?: string;
  workflow_thread_id: string;
  resume_token?: string | null;
  route?: {
    intent: string;
    route?: string;
    confidence: number;
    requires_plan: boolean;
    allowed_capabilities: string[];
    reason: string;
  };
};

/** One field an administrator may change, and where its current value came from.
 *
 *  `layer` is the thing the page exists to show: a value pinned in the process
 *  environment outranks the configuration centre, so editing it would look like
 *  it worked and change nothing. `editable_here` is false for exactly those. */
export type ConfigField = {
  alias: string;
  group: string;
  summary: string;
  type: string;
  value: string | number | boolean;
  default: string | number | boolean;
  layer: "environment" | "config-centre" | "runtime-file" | "default";
  editable_here: boolean;
  requires_restart: boolean;
};

export type ConfigSchemaResponse = {
  config_centre_enabled: boolean;
  fields: ConfigField[];
};

export type ConfigSaveResponse = {
  ok: boolean;
  data_id: string;
  changed: string[];
  fields: ConfigField[];
};
