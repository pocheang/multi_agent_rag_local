from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., description="User question")
    use_web_fallback: bool = Field(default=False)
    use_reasoning: bool = Field(default=False)
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,128}$")
    request_id: str | None = None
    agent_class_hint: str | None = None
    retrieval_strategy: str | None = None  # baseline|advanced|safe


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
    debug: dict[str, Any] = Field(default_factory=dict)



class SessionSummary(BaseModel):
    session_id: str
    title: str
    created_at: str | None = None
    updated_at: str | None = None
    message_count: int = 0


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
    is_online: bool = False
    is_online_10m: bool = False
    created_at: str | None = None


class AdminRoleUpdateRequest(BaseModel):
    role: str


class AdminStatusUpdateRequest(BaseModel):
    status: str


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
    loaded_documents: int = 0
    chunks_indexed: int = 0
    triplets_written: int = 0
    pages_by_source: dict[str, int] = Field(default_factory=dict)


class IndexedFileSummary(BaseModel):
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


class UserApiSettings(BaseModel):
    provider: str = Field(default="ollama", description="API provider: local, openai, anthropic, deepseek, ollama, custom")
    api_key: str = Field(default="", description="API key (encrypted in storage)")
    base_url: str = Field(default="", description="Base URL for API")
    model: str = Field(default="", description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature")
    max_tokens: int = Field(default=2048, ge=256, le=8192, description="Max tokens")


class UserApiSettingsView(BaseModel):
    provider: str = Field(default="ollama", description="API provider: local, openai, anthropic, deepseek, ollama, custom")
    api_key_masked: str = Field(default="", description="Masked API key")
    base_url: str = Field(default="", description="Base URL for API")
    model: str = Field(default="", description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature")
    max_tokens: int = Field(default=2048, ge=256, le=8192, description="Max tokens")


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


class AdminModelSettings(BaseModel):
    enabled: bool = Field(default=False, description="Apply this global model config to users without personal overrides")
    provider: str = Field(default="ollama", description="API provider: local, openai, anthropic, deepseek, ollama, custom")
    api_key: str = Field(default="", description="API key (encrypted in storage)")
    base_url: str = Field(default="", description="Base URL for API")
    chat_model: str = Field(default="", description="Chat model name")
    reasoning_model: str = Field(default="", description="Reasoning model name")
    embedding_model: str = Field(default="", description="Embedding model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature")
    max_tokens: int = Field(default=2048, ge=256, le=8192, description="Max tokens")


class AdminModelSettingsView(BaseModel):
    enabled: bool = False
    provider: str = "ollama"
    api_key_masked: str = ""
    base_url: str = ""
    chat_model: str = ""
    reasoning_model: str = ""
    embedding_model: str = ""
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=256, le=8192)
    embedding_reindexed: bool = False
    records_reindexed: int = 0


class AdminModelSettingsResponse(BaseModel):
    ok: bool = True
    settings: AdminModelSettingsView
