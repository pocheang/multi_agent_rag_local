from typing import Any, Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    source: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    answer: str
    route: str
    citations: list[Citation] = Field(default_factory=list)
    graph_entities: list[str] = Field(default_factory=list)
    web_used: bool = False
    detected_language: str = Field(default="zh", description="Detected or forced response language")
    debug: dict[str, Any] = Field(default_factory=dict)
    execution_id: str | None = Field(default=None, description="Execution tracking ID for agent-tracking endpoints")
    status: str = Field(default="completed", description="Query status: completed, processing, pending")
    request_id: str | None = Field(default=None, description="Request ID for status tracking")


class SessionSummary(BaseModel):
    session_id: str
    title: str
    created_at: str | None = None
    updated_at: str | None = None
    message_count: int = 0
    pinned: bool = False


class ChatMessage(BaseModel):
    message_id: str | None = None
    role: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class MessageUpdateRequest(BaseModel):
    content: str = Field(..., description="Updated message content")


class AuthCredentials(BaseModel):
    username: str
    password: str


class AuthUser(BaseModel):
    user_id: str
    username: str
    role: str = "viewer"
    status: str = "active"
    display_name: str | None = None
    credit_balance: int = Field(default=10, ge=0)


class AuthLoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_at: str
    user: AuthUser


class PromptTemplate(BaseModel):
    prompt_id: str
    title: str
    content: str
    agent_class: str = "general"
    created_at: str
    updated_at: str


class PromptTemplateCreateRequest(BaseModel):
    title: str
    content: str


class PromptTemplateUpdateRequest(BaseModel):
    title: str
    content: str


class PromptCheckRequest(BaseModel):
    title: str
    content: str
    use_reasoning: bool = False


class PromptCheckResponse(BaseModel):
    title: str
    content: str
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class AdminUserSummary(BaseModel):
    user_id: str
    username: str
    role: str
    status: str
    created_by_user_id: str | None = None
    created_by_username: str | None = None
    admin_ticket_id: str | None = None
    has_admin_approval_token: bool = False
    business_unit: str | None = None
    department: str | None = None
    user_type: str | None = None
    data_scope: str | None = None
    credit_balance: int = Field(default=10, ge=0)
    is_online: bool = False
    is_online_10m: bool = False
    created_at: str | None = None


class AdminRoleUpdateRequest(BaseModel):
    role: str


class AdminStatusUpdateRequest(BaseModel):
    status: str


class AdminCreditAddRequest(BaseModel):
    amount: int = Field(..., ge=1, le=1_000_000, strict=True)


class AdminUserClassificationUpdateRequest(BaseModel):
    business_unit: str | None = None
    department: str | None = None
    user_type: str | None = None
    data_scope: str | None = None


class AdminCreateAdminRequest(BaseModel):
    username: str
    password: str
    approval_token: str
    ticket_id: str
    reason: str
    new_admin_approval_token: str


class AdminResetApprovalTokenRequest(BaseModel):
    approval_token: str
    ticket_id: str
    reason: str
    new_admin_approval_token: str


class AdminResetPasswordRequest(BaseModel):
    approval_token: str
    ticket_id: str
    reason: str
    new_password: str


class AuditLogEntry(BaseModel):
    event_id: str
    actor_user_id: str | None = None
    actor_role: str | None = None
    action: str
    event_category: str | None = None
    severity: str | None = None
    resource_type: str
    resource_id: str | None = None
    result: str
    ip: str | None = None
    user_agent: str | None = None
    detail: str | None = None
    created_at: str


class SessionDetail(BaseModel):
    session_id: str
    title: str
    created_at: str | None = None
    updated_at: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)


class LongTermMemoryItem(BaseModel):
    candidate_id: str
    question: str
    answer: str
    score: float
    signals: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class UploadResponse(BaseModel):
    ok: bool = True
    filenames: list[str] = Field(default_factory=list)
    skipped_files: list[str] = Field(default_factory=list)
    visibility_applied: str = "private"
    assigned_agent_classes: dict[str, str] = Field(default_factory=dict)
    document_ids: list[str] = Field(default_factory=list)
    indexing_status: str = "complete"
    duplicate_files: list[str] = Field(default_factory=list)
    reused_document_ids: list[str] = Field(default_factory=list)
    loaded_documents: int = 0
    chunks_indexed: int = 0
    triplets_written: int = 0
    pages_by_source: dict[str, int] = Field(default_factory=dict)


class IndexedFileSummary(BaseModel):
    document_id: str | None = None
    filename: str
    source: str = ""
    chunks: int = 0
    pages: list[int] = Field(default_factory=list)
    page_count: int = 0
    owner_user_id: str | None = None
    visibility: str = "private"
    agent_class: str = "general"
    in_uploads: bool = False
    exists_on_disk: bool = False
    indexing_status: str = "ready"
    indexing_stage: str = "complete"
    indexing_error: str = ""
    triplets_written: int = 0
    parser_profile: str = ""


class FileIndexActionResponse(BaseModel):
    ok: bool = True
    filename: str
    chunks_removed: int = 0
    vector_ids_removed: int = 0
    triplets_removed: int = 0
    file_removed: bool = False
    loaded_documents: int = 0
    chunks_indexed: int = 0
    triplets_written: int = 0
    pages_by_source: dict[str, int] = Field(default_factory=dict)
    skipped: bool = False
    reason: str = ""


class IndexHealthResponse(BaseModel):
    total_documents: int = 0
    ready_documents: int = 0
    failed_documents: int = 0
    indexing_documents: int = 0
    total_chunks: int = 0
    total_triplets: int = 0
    documents: list[dict[str, Any]] = Field(default_factory=list)


class UserApiSettings(BaseModel):
    provider: str = Field(
        default="local", description="API provider: local, openai, anthropic, deepseek, ollama, custom"
    )
    api_key: str = Field(default="", description="API key (encrypted in storage)")
    base_url: str = Field(default="", description="Base URL for API")
    model: str = Field(default="", description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="Temperature")
    max_tokens: int = Field(default=2048, ge=256, le=131072, description="Max tokens")


class UserApiSettingsView(BaseModel):
    provider: str = Field(
        default="local", description="API provider: local, openai, anthropic, deepseek, ollama, custom"
    )
    api_key_masked: str = Field(default="", description="Masked API key")
    base_url: str = Field(default="", description="Base URL for API")
    model: str = Field(default="", description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="Temperature")
    max_tokens: int = Field(default=2048, ge=256, le=131072, description="Max tokens")
    global_override_enabled: bool = False
    global_provider: str | None = None
    global_model: str | None = None
    effective_provider: str = ""
    effective_model: str = ""


class UserApiSettingsResponse(BaseModel):
    ok: bool = True
    settings: UserApiSettingsView


class UserApiSettingsTestResponse(BaseModel):
    ok: bool = True
    reachable: bool = False
    provider: str
    model: str
    latency_ms: int = 0
    message: str = ""
    preview: str = ""


class ModelCatalogItem(BaseModel):
    id: str
    label: str
    roles: list[str] = Field(default_factory=list)
    recommended: bool = False
    deprecated_after: str | None = None


class ProviderCatalogEntry(BaseModel):
    label: str
    base_url: str = ""
    default_chat_model: str = ""
    default_reasoning_model: str = ""
    default_embedding_model: str = ""
    requires_api_key: bool = False
    supports_embeddings: bool = False
    api_style: str
    note: str = ""
    models: list[ModelCatalogItem] = Field(default_factory=list)


class ModelCatalogResponse(BaseModel):
    version: str
    providers: dict[str, ProviderCatalogEntry]


class AdminModelSettings(BaseModel):
    enabled: bool = Field(
        default=False,
        # Says what it does, not what would be gentler. `get_chat_model` resolves
        # `global_override or user_override`, so an enabled global config wins
        # over a user's own -- their personal key stops being used and their
        # queries bill the org's account. The old wording ("to users without
        # personal overrides") described the opposite.
        description="Apply this global model config to every user, overriding their personal API settings",
    )
    provider: str = Field(
        default="local", description="API provider: local, openai, anthropic, deepseek, ollama, custom"
    )
    api_key: str = Field(default="", description="API key (encrypted in storage)")
    base_url: str = Field(default="", description="Base URL for API")
    chat_model: str = Field(default="", description="Chat model name")
    reasoning_model: str = Field(default="", description="Reasoning model name")
    embedding_model: str = Field(default="", description="Embedding model name")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="Temperature")
    max_tokens: int = Field(default=2048, ge=256, le=131072, description="Max tokens")


class AdminModelSettingsView(BaseModel):
    enabled: bool = False
    provider: str = "local"
    api_key_masked: str = ""
    base_url: str = ""
    chat_model: str = ""
    reasoning_model: str = ""
    embedding_model: str = ""
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=2048, ge=256, le=131072)
    embedding_reindexed: bool = False
    records_reindexed: int = 0
    # Whether these settings are actually in effect. `MODEL_BACKEND=local` in the
    # real process environment makes `get_chat_model` discard the global override
    # entirely (`_local_backend_forced`), so without this the page could report a
    # saved OpenAI configuration while every answer came from the offline stand-in
    # -- a page describing something other than what runs.
    environment_pinned: bool = False
    pinned_reason: str = ""


class EffectiveModelComponent(BaseModel):
    """One model in the stack and whether it is doing its job.

    `status` is the point. "degraded" means configured, running, and not doing
    what its name implies -- a reranker whose model was never downloaded still
    returns results, by falling back to lexical scoring, and looks healthy from
    outside.
    """

    component: str
    status: Literal["active", "degraded", "disabled", "unavailable"]
    configured: str
    detail: str
    source: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class EffectiveModelConfigResponse(BaseModel):
    ok: bool = True
    components: list[EffectiveModelComponent] = Field(default_factory=list)
    degraded: int = 0


class AdminModelSettingsResponse(BaseModel):
    ok: bool = True
    settings: AdminModelSettingsView
