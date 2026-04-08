from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="dev", alias="APP_ENV")
    model_backend: str = Field(default="ollama", alias="MODEL_BACKEND")
    reasoning_model_backend: str = Field(default="", alias="REASONING_MODEL_BACKEND")

    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_chat_model: str = Field(default="qwen2.5:7b-instruct", alias="OLLAMA_CHAT_MODEL")
    ollama_embed_model: str = Field(default="nomic-embed-text", alias="OLLAMA_EMBED_MODEL")
    ollama_reasoning_model: str = Field(default="", alias="OLLAMA_REASONING_MODEL")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    openai_chat_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_CHAT_MODEL")
    openai_embed_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBED_MODEL")
    openai_reasoning_model: str = Field(default="gpt-5.2", alias="OPENAI_REASONING_MODEL")

    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_username: str = Field(default="neo4j", alias="NEO4J_USERNAME")
    neo4j_password: str = Field(default="neo4j_password", alias="NEO4J_PASSWORD")

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
    app_db_path_str: str = Field(default="./data/app.db", alias="APP_DB_PATH")

    auth_login_max_failures: int = Field(default=8, alias="AUTH_LOGIN_MAX_FAILURES")
    auth_login_window_seconds: int = Field(default=300, alias="AUTH_LOGIN_WINDOW_SECONDS")
    auth_register_max_attempts: int = Field(default=12, alias="AUTH_REGISTER_MAX_ATTEMPTS")
    auth_register_window_seconds: int = Field(default=300, alias="AUTH_REGISTER_WINDOW_SECONDS")

    upload_max_files: int = Field(default=20, alias="UPLOAD_MAX_FILES")
    upload_max_file_bytes: int = Field(default=20 * 1024 * 1024, alias="UPLOAD_MAX_FILE_BYTES")
    upload_max_total_bytes: int = Field(default=100 * 1024 * 1024, alias="UPLOAD_MAX_TOTAL_BYTES")
    upload_read_chunk_bytes: int = Field(default=1024 * 1024, alias="UPLOAD_READ_CHUNK_BYTES")
    tesseract_cmd: str = Field(default="", alias="TESSERACT_CMD")
    tesseract_lang: str = Field(default="chi_sim+eng", alias="TESSERACT_LANG")

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
    return settings
