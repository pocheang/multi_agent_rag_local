from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="dev", alias="APP_ENV")
    model_backend: str = Field(default="openai", alias="MODEL_BACKEND")
    reasoning_model_backend: str = Field(default="", alias="REASONING_MODEL_BACKEND")

    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_chat_model: str = Field(default="qwen2.5:7b-instruct", alias="OLLAMA_CHAT_MODEL")
    ollama_embed_model: str = Field(default="nomic-embed-text", alias="OLLAMA_EMBED_MODEL")
    ollama_reasoning_model: str = Field(default="", alias="OLLAMA_REASONING_MODEL")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    openai_chat_model: str = Field(default="gpt-5.4-codex", alias="OPENAI_CHAT_MODEL")
    openai_embed_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBED_MODEL")
    openai_reasoning_model: str = Field(default="gpt-5.4-codex", alias="OPENAI_REASONING_MODEL")

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_chat_model: str = Field(default="claude-sonnet-4-6", alias="ANTHROPIC_CHAT_MODEL")
    anthropic_reasoning_model: str = Field(default="claude-sonnet-4-6", alias="ANTHROPIC_REASONING_MODEL")

    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_username: str = Field(default="neo4j", alias="NEO4J_USERNAME")
    neo4j_password: str = Field(default="", alias="NEO4J_PASSWORD")

    chroma_collection: str = Field(default="local_rag_collection", alias="CHROMA_COLLECTION")
    chroma_persist_dir: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIR")
    data_dir: str = Field(default="./data/docs", alias="DATA_DIR")
    corpus_store_path: str = Field(default="./data/chunks/chunks.jsonl", alias="CORPUS_STORE_PATH")
    parent_store_path_str: str = Field(default="./data/chunks/parents.jsonl", alias="PARENT_STORE_PATH")

    parent_chunk_size: int = Field(default=1500, alias="PARENT_CHUNK_SIZE")
    parent_chunk_overlap: int = Field(default=200, alias="PARENT_CHUNK_OVERLAP")
    child_chunk_size: int = Field(default=600, alias="CHILD_CHUNK_SIZE")
    child_chunk_overlap: int = Field(default=120, alias="CHILD_CHUNK_OVERLAP")

    top_k: int = Field(default=4, alias="TOP_K")
    max_context_chunks: int = Field(default=6, alias="MAX_CONTEXT_CHUNKS")
    bm25_top_k: int = Field(default=6, alias="BM25_TOP_K")
    vector_top_k: int = Field(default=6, alias="VECTOR_TOP_K")
    hybrid_rrf_k: int = Field(default=60, alias="HYBRID_RRF_K")
    hybrid_vector_weight: float = Field(default=0.95, alias="HYBRID_VECTOR_WEIGHT")
    hybrid_bm25_weight: float = Field(default=0.05, alias="HYBRID_BM25_WEIGHT")
    vector_similarity_threshold: float = Field(default=0.2, alias="VECTOR_SIMILARITY_THRESHOLD")
    vector_similarity_relaxed_threshold: float = Field(default=0.05, alias="VECTOR_SIMILARITY_RELAXED_THRESHOLD")
    query_rewrite_enabled: bool = Field(default=True, alias="QUERY_REWRITE_ENABLED")
    query_rewrite_with_llm: bool = Field(default=False, alias="QUERY_REWRITE_WITH_LLM")
    query_decompose_enabled: bool = Field(default=True, alias="QUERY_DECOMPOSE_ENABLED")
    query_rewrite_max_variants: int = Field(default=6, alias="QUERY_REWRITE_MAX_VARIANTS")
    rank_feature_enabled: bool = Field(default=True, alias="RANK_FEATURE_ENABLED")
    rank_feature_source_weight: float = Field(default=0.08, alias="RANK_FEATURE_SOURCE_WEIGHT")
    rank_feature_freshness_weight: float = Field(default=0.07, alias="RANK_FEATURE_FRESHNESS_WEIGHT")
    rank_feature_retrieval_diversity_weight: float = Field(default=0.05, alias="RANK_FEATURE_RETRIEVAL_DIVERSITY_WEIGHT")
    dynamic_retrieval_enabled: bool = Field(default=True, alias="DYNAMIC_RETRIEVAL_ENABLED")
    dynamic_vector_top_k_cap: int = Field(default=16, alias="DYNAMIC_VECTOR_TOP_K_CAP")
    dynamic_bm25_top_k_cap: int = Field(default=16, alias="DYNAMIC_BM25_TOP_K_CAP")
    dynamic_reranker_top_n_cap: int = Field(default=10, alias="DYNAMIC_RERANKER_TOP_N_CAP")
    retrieval_cache_enabled: bool = Field(default=True, alias="RETRIEVAL_CACHE_ENABLED")
    retrieval_cache_ttl_seconds: int = Field(default=45, alias="RETRIEVAL_CACHE_TTL_SECONDS")
    retrieval_cache_max_items: int = Field(default=256, alias="RETRIEVAL_CACHE_MAX_ITEMS")
    circuit_breaker_enabled: bool = Field(default=True, alias="CIRCUIT_BREAKER_ENABLED")
    circuit_breaker_fail_threshold: int = Field(default=3, alias="CIRCUIT_BREAKER_FAIL_THRESHOLD")
    circuit_breaker_cooldown_seconds: int = Field(default=30, alias="CIRCUIT_BREAKER_COOLDOWN_SECONDS")
    retrieval_cache_backend: str = Field(default="auto", alias="RETRIEVAL_CACHE_BACKEND")  # auto|memory|redis|off
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    otel_tracing_enabled: bool = Field(default=True, alias="OTEL_TRACING_ENABLED")
    slo_p95_latency_ms_threshold: int = Field(default=3000, alias="SLO_P95_LATENCY_MS_THRESHOLD")
    slo_error_rate_percent_threshold: float = Field(default=5.0, alias="SLO_ERROR_RATE_PERCENT_THRESHOLD")
    slo_grounding_support_ratio_threshold: float = Field(default=0.6, alias="SLO_GROUNDING_SUPPORT_RATIO_THRESHOLD")
    retrieval_profile: str = Field(default="advanced", alias="RETRIEVAL_PROFILE")  # baseline|advanced|safe
    consistency_guard_enabled: bool = Field(default=True, alias="CONSISTENCY_GUARD_ENABLED")
    consistency_guard_similarity_threshold: float = Field(default=0.55, alias="CONSISTENCY_GUARD_SIMILARITY_THRESHOLD")
    web_domain_allowlist: str = Field(
        default="gov.cn,gov,edu,org,nist.gov,cisa.gov,mitre.org,wikipedia.org,owasp.org,microsoft.com,openai.com",
        alias="WEB_DOMAIN_ALLOWLIST",
    )
    web_min_source_score: float = Field(default=0.2, alias="WEB_MIN_SOURCE_SCORE")
    answer_safety_scan_enabled: bool = Field(default=True, alias="ANSWER_SAFETY_SCAN_ENABLED")

    enable_reranker: bool = Field(default=True, alias="ENABLE_RERANKER")
    reranker_model_name: str = Field(default="BAAI/bge-reranker-v2-m3", alias="RERANKER_MODEL_NAME")
    reranker_top_n: int = Field(default=5, alias="RERANKER_TOP_N")

    graph_extraction_mode: str = Field(default="llm", alias="GRAPH_EXTRACTION_MODE")
    graph_triplet_batch_chars: int = Field(default=2200, alias="GRAPH_TRIPLET_BATCH_CHARS")

    sessions_dir: str = Field(default="./data/sessions", alias="SESSIONS_DIR")
    uploads_dir: str = Field(default="./data/uploads", alias="UPLOADS_DIR")
    auto_ingest_enabled: bool = Field(default=False, alias="AUTO_INGEST_ENABLED")
    auto_ingest_interval_seconds: float = Field(default=3.0, alias="AUTO_INGEST_INTERVAL_SECONDS")
    auto_ingest_watch_docs: bool = Field(default=True, alias="AUTO_INGEST_WATCH_DOCS")
    auto_ingest_watch_uploads: bool = Field(default=True, alias="AUTO_INGEST_WATCH_UPLOADS")
    auto_ingest_recursive: bool = Field(default=True, alias="AUTO_INGEST_RECURSIVE")
    users_file: str = Field(default="./data/security/users.json", alias="USERS_FILE")
    auth_sessions_file: str = Field(default="./data/security/auth_sessions.json", alias="AUTH_SESSIONS_FILE")
    auth_token_ttl_hours: int = Field(default=24, alias="AUTH_TOKEN_TTL_HOURS")
    auth_expose_token_in_response: bool = Field(default=False, alias="AUTH_EXPOSE_TOKEN_IN_RESPONSE")
    auth_cookie_name: str = Field(default="auth_token", alias="AUTH_COOKIE_NAME")
    auth_cookie_secure: bool = Field(default=False, alias="AUTH_COOKIE_SECURE")
    auth_cookie_samesite: str = Field(default="lax", alias="AUTH_COOKIE_SAMESITE")  # strict|lax|none
    app_db_path_str: str = Field(default="./data/app.db", alias="APP_DB_PATH")

    auth_login_max_failures: int = Field(default=8, alias="AUTH_LOGIN_MAX_FAILURES")
    auth_login_window_seconds: int = Field(default=300, alias="AUTH_LOGIN_WINDOW_SECONDS")
    auth_register_max_attempts: int = Field(default=12, alias="AUTH_REGISTER_MAX_ATTEMPTS")
    auth_register_window_seconds: int = Field(default=300, alias="AUTH_REGISTER_WINDOW_SECONDS")
    query_rate_limit_max_attempts: int = Field(default=30, alias="QUERY_RATE_LIMIT_MAX_ATTEMPTS")
    query_rate_limit_window_seconds: int = Field(default=60, alias="QUERY_RATE_LIMIT_WINDOW_SECONDS")
    query_guard_backend: str = Field(default="auto", alias="QUERY_GUARD_BACKEND")  # auto|memory|redis
    query_max_concurrent: int = Field(default=24, alias="QUERY_MAX_CONCURRENT")
    query_max_waiting: int = Field(default=120, alias="QUERY_MAX_WAITING")
    query_acquire_timeout_ms: int = Field(default=3000, alias="QUERY_ACQUIRE_TIMEOUT_MS")
    query_request_timeout_ms: int = Field(default=20000, alias="QUERY_REQUEST_TIMEOUT_MS")
    query_overload_inflight_threshold: int = Field(default=20, alias="QUERY_OVERLOAD_INFLIGHT_THRESHOLD")
    query_overload_waiting_threshold: int = Field(default=60, alias="QUERY_OVERLOAD_WAITING_THRESHOLD")
    query_result_cache_backend: str = Field(default="auto", alias="QUERY_RESULT_CACHE_BACKEND")  # auto|memory|redis|off
    query_result_cache_ttl_seconds: int = Field(default=45, alias="QUERY_RESULT_CACHE_TTL_SECONDS")
    query_result_cache_max_items: int = Field(default=512, alias="QUERY_RESULT_CACHE_MAX_ITEMS")
    query_result_session_ttl_seconds: int = Field(default=300, alias="QUERY_RESULT_SESSION_TTL_SECONDS")
    stream_replay_cache_ttl_seconds: int = Field(default=600, alias="STREAM_REPLAY_CACHE_TTL_SECONDS")
    stream_replay_cache_max_events: int = Field(default=1200, alias="STREAM_REPLAY_CACHE_MAX_EVENTS")
    stream_heartbeat_seconds: float = Field(default=8.0, alias="STREAM_HEARTBEAT_SECONDS")
    shadow_queue_workers: int = Field(default=2, alias="SHADOW_QUEUE_WORKERS")
    shadow_queue_maxsize: int = Field(default=200, alias="SHADOW_QUEUE_MAXSIZE")
    synthesis_refine_max_rounds: int = Field(default=5, alias="SYNTHESIS_REFINE_MAX_ROUNDS")
    synthesis_refine_overload_rounds: int = Field(default=1, alias="SYNTHESIS_REFINE_OVERLOAD_ROUNDS")
    history_backend: str = Field(default="file", alias="HISTORY_BACKEND")  # file|sqlite
    history_sqlite_path_str: str = Field(default="./data/history.db", alias="HISTORY_SQLITE_PATH")
    history_cold_dir: str = Field(default="./data/sessions_cold", alias="HISTORY_COLD_DIR")
    history_hot_tier_days: int = Field(default=14, alias="HISTORY_HOT_TIER_DAYS")
    bulkhead_enabled: bool = Field(default=True, alias="BULKHEAD_ENABLED")
    bulkhead_llm_max_concurrent: int = Field(default=12, alias="BULKHEAD_LLM_MAX_CONCURRENT")
    bulkhead_neo4j_max_concurrent: int = Field(default=20, alias="BULKHEAD_NEO4J_MAX_CONCURRENT")
    bulkhead_web_max_concurrent: int = Field(default=8, alias="BULKHEAD_WEB_MAX_CONCURRENT")
    bulkhead_acquire_timeout_ms: int = Field(default=1500, alias="BULKHEAD_ACQUIRE_TIMEOUT_MS")
    alerting_enabled: bool = Field(default=False, alias="ALERTING_ENABLED")
    alert_webhook_url: str = Field(default="", alias="ALERT_WEBHOOK_URL")
    alert_webhook_allowlist: str = Field(default="", alias="ALERT_WEBHOOK_ALLOWLIST")  # csv domains
    alert_min_interval_seconds: int = Field(default=60, alias="ALERT_MIN_INTERVAL_SECONDS")
    response_signing_enabled: bool = Field(default=True, alias="RESPONSE_SIGNING_ENABLED")
    response_signing_secret: str = Field(default="", alias="RESPONSE_SIGNING_SECRET")
    response_signing_active_kid: str = Field(default="v1", alias="RESPONSE_SIGNING_ACTIVE_KID")
    response_signing_keys: str = Field(default="", alias="RESPONSE_SIGNING_KEYS")  # kid:secret;kid2:secret2
    api_settings_encryption_key: str = Field(default="", alias="API_SETTINGS_ENCRYPTION_KEY")
    api_base_url_allowlist: str = Field(default="", alias="API_BASE_URL_ALLOWLIST")  # csv host suffixes
    api_base_url_allow_private: bool = Field(default=False, alias="API_BASE_URL_ALLOW_PRIVATE")
    api_base_url_dns_check: bool = Field(default=True, alias="API_BASE_URL_DNS_CHECK")
    quota_enabled: bool = Field(default=False, alias="QUOTA_ENABLED")
    quota_query_max_per_minute: int = Field(default=120, alias="QUOTA_QUERY_MAX_PER_MINUTE")
    quota_web_max_per_minute: int = Field(default=30, alias="QUOTA_WEB_MAX_PER_MINUTE")
    quota_mode: str = Field(default="user", alias="QUOTA_MODE")  # user|business_unit
    feature_flags: str = Field(default="", alias="FEATURE_FLAGS")  # name=on|off|pct:10
    feature_flag_seed: str = Field(default="feature", alias="FEATURE_FLAG_SEED")
    query_retry_enabled: bool = Field(default=True, alias="QUERY_RETRY_ENABLED")
    query_retry_max_attempts: int = Field(default=2, alias="QUERY_RETRY_MAX_ATTEMPTS")
    query_retry_base_delay_ms: int = Field(default=120, alias="QUERY_RETRY_BASE_DELAY_MS")
    perf_gate_max_p95_ms: int = Field(default=4000, alias="PERF_GATE_MAX_P95_MS")
    perf_gate_max_error_rate_percent: float = Field(default=5.0, alias="PERF_GATE_MAX_ERROR_RATE_PERCENT")
    admin_create_approval_token: str = Field(default="", alias="ADMIN_CREATE_APPROVAL_TOKEN")
    admin_create_approval_token_hash: str = Field(default="", alias="ADMIN_CREATE_APPROVAL_TOKEN_HASH")

    upload_max_files: int = Field(default=20, alias="UPLOAD_MAX_FILES")
    upload_max_file_bytes: int = Field(default=20 * 1024 * 1024, alias="UPLOAD_MAX_FILE_BYTES")
    upload_max_total_bytes: int = Field(default=100 * 1024 * 1024, alias="UPLOAD_MAX_TOTAL_BYTES")
    upload_read_chunk_bytes: int = Field(default=1024 * 1024, alias="UPLOAD_READ_CHUNK_BYTES")
    tesseract_cmd: str = Field(default="", alias="TESSERACT_CMD")
    tesseract_lang: str = Field(default="chi_sim+eng", alias="TESSERACT_LANG")
    tessdata_prefix: str = Field(default="", alias="TESSDATA_PREFIX")
    ocr_preprocess_enabled: bool = Field(default=True, alias="OCR_PREPROCESS_ENABLED")
    ocr_upscale_min_side: int = Field(default=1200, alias="OCR_UPSCALE_MIN_SIDE")
    ocr_psm_modes: str = Field(default="6,11,3", alias="OCR_PSM_MODES")
    people_detection_enabled: bool = Field(default=True, alias="PEOPLE_DETECTION_ENABLED")
    people_detection_mode: str = Field(default="face", alias="PEOPLE_DETECTION_MODE")
    image_caption_enabled: bool = Field(default=False, alias="IMAGE_CAPTION_ENABLED")
    image_caption_backend: str = Field(default="auto", alias="IMAGE_CAPTION_BACKEND")
    openai_vision_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_VISION_MODEL")
    ollama_vision_model: str = Field(default="llava:7b", alias="OLLAMA_VISION_MODEL")
    cors_enabled: bool = Field(default=True, alias="CORS_ENABLED")
    cors_allow_origins: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000",
        alias="CORS_ALLOW_ORIGINS",
    )
    cors_allow_methods: str = Field(default="*", alias="CORS_ALLOW_METHODS")
    cors_allow_headers: str = Field(default="*", alias="CORS_ALLOW_HEADERS")
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")

    @property
    def chroma_path(self) -> Path:
        return Path(self.chroma_persist_dir)

    @property
    def docs_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def corpus_path(self) -> Path:
        return Path(self.corpus_store_path)

    @property
    def parent_store_path(self) -> Path:
        return Path(self.parent_store_path_str)

    @property
    def sessions_path(self) -> Path:
        return Path(self.sessions_dir)

    @property
    def uploads_path(self) -> Path:
        return Path(self.uploads_dir)

    @property
    def users_path(self) -> Path:
        return Path(self.users_file)

    @property
    def auth_sessions_path(self) -> Path:
        return Path(self.auth_sessions_file)

    @property
    def app_db_path(self) -> Path:
        return Path(self.app_db_path_str)

    @property
    def history_sqlite_path(self) -> Path:
        return Path(self.history_sqlite_path_str)

    @property
    def history_cold_path(self) -> Path:
        return Path(self.history_cold_dir)

    @property
    def cors_origins(self) -> list[str]:
        raw = str(self.cors_allow_origins or "").strip()
        if not raw:
            return []
        return [x.strip() for x in raw.split(",") if x.strip()]

    @property
    def cors_methods(self) -> list[str]:
        raw = str(self.cors_allow_methods or "").strip()
        if not raw:
            return ["*"]
        return [x.strip() for x in raw.split(",") if x.strip()]

    @property
    def cors_headers(self) -> list[str]:
        raw = str(self.cors_allow_headers or "").strip()
        if not raw:
            return ["*"]
        return [x.strip() for x in raw.split(",") if x.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    settings.docs_path.mkdir(parents=True, exist_ok=True)
    settings.corpus_path.parent.mkdir(parents=True, exist_ok=True)
    settings.parent_store_path.parent.mkdir(parents=True, exist_ok=True)
    settings.sessions_path.mkdir(parents=True, exist_ok=True)
    settings.uploads_path.mkdir(parents=True, exist_ok=True)
    settings.users_path.parent.mkdir(parents=True, exist_ok=True)
    settings.auth_sessions_path.parent.mkdir(parents=True, exist_ok=True)
    settings.app_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.history_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    settings.history_cold_path.mkdir(parents=True, exist_ok=True)
    return settings


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
