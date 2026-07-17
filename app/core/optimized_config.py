"""
Configuration settings for v0.4.4 optimized RAG pipeline.

Add these settings to the generated .runtime environment file or application config.
"""

# ============================================================================
# V0.4.4 Optimized RAG Settings
# ============================================================================

# Multi-Path Retrieval
ENABLE_MULTI_PATH_RETRIEVAL = True
MULTI_PATH_TOP_K = 50
MULTI_PATH_VECTOR_K = 30
MULTI_PATH_BM25_K = 30
MULTI_PATH_HYBRID_K = 20

# Fast Reranking
ENABLE_FAST_RERANK = True
FAST_RERANKER_MODEL = "BAAI/bge-reranker-base"  # or "BAAI/bge-reranker-v2-m3"
FAST_RERANKER_DEVICE = "cuda"  # "cuda", "cpu", or "auto"
FAST_RERANKER_BATCH_SIZE = 32
FAST_RERANKER_MAX_LENGTH = 512
FAST_RERANKER_THRESHOLD = 0.3
FAST_RERANKER_PRE_FILTER_K = 30

# Rule-Based Compression
ENABLE_RULE_COMPRESSION = True
COMPRESSION_MAX_LENGTH = 4000
COMPRESSION_KEEP_RATIO = 0.6
COMPRESSION_MIN_SENTENCE_LENGTH = 10
COMPRESSION_MAX_SENTENCE_LENGTH = 300

# Adaptive Strategy Routing
ENABLE_ADAPTIVE_ROUTING = True
ADAPTIVE_ROUTING_MODE = "auto"  # "auto", "fast", "standard", "precise"

# Strategy Time Targets (milliseconds)
STRATEGY_FAST_TARGET_MS = 400
STRATEGY_STANDARD_TARGET_MS = 800
STRATEGY_PRECISE_TARGET_MS = 1500

# Query Cache
ENABLE_QUERY_CACHE = True
QUERY_CACHE_MAX_SIZE = 1000
QUERY_CACHE_TTL_SECONDS = 3600

# Optimized Prompts
USE_OPTIMIZED_PROMPTS = True
PROMPT_STYLE = "simplified"  # "simplified", "comprehensive", "minimal"
ENABLE_STREAMING_OUTPUT = True

# Performance Monitoring
ENABLE_PERFORMANCE_TRACKING = True
LOG_SLOW_QUERIES_MS = 2000
LOG_STAGE_TIMINGS = True

# Fallback Settings
FALLBACK_TO_HYBRID_SEARCH = True
FALLBACK_TO_SCORE_RANKING = True

# ============================================================================
# Example Complete Configuration
# ============================================================================

# Example .runtime entries:
"""
# V0.4.4 Optimized RAG
ENABLE_MULTI_PATH_RETRIEVAL=true
ENABLE_FAST_RERANK=true
FAST_RERANKER_MODEL=BAAI/bge-reranker-base
FAST_RERANKER_DEVICE=cuda
ENABLE_RULE_COMPRESSION=true
ENABLE_ADAPTIVE_ROUTING=true
ENABLE_QUERY_CACHE=true
USE_OPTIMIZED_PROMPTS=true
"""

# ============================================================================
# Configuration Classes
# ============================================================================

from pydantic import Field
from pydantic_settings import BaseSettings


class OptimizedRAGSettings(BaseSettings):
    """Settings for v0.4.4 optimized RAG pipeline."""

    # Multi-path retrieval
    enable_multi_path_retrieval: bool = Field(default=True)
    multi_path_top_k: int = Field(default=50)
    multi_path_vector_k: int = Field(default=30)
    multi_path_bm25_k: int = Field(default=30)
    multi_path_hybrid_k: int = Field(default=20)

    # Fast reranking
    enable_fast_rerank: bool = Field(default=True)
    fast_reranker_model: str = Field(default="BAAI/bge-reranker-base")
    fast_reranker_device: str = Field(default="auto")
    fast_reranker_batch_size: int = Field(default=32)
    fast_reranker_max_length: int = Field(default=512)
    fast_reranker_threshold: float = Field(default=0.3)
    fast_reranker_pre_filter_k: int = Field(default=30)

    # Rule-based compression
    enable_rule_compression: bool = Field(default=True)
    compression_max_length: int = Field(default=4000)
    compression_keep_ratio: float = Field(default=0.6)
    compression_min_sentence_length: int = Field(default=10)
    compression_max_sentence_length: int = Field(default=300)

    # Adaptive routing
    enable_adaptive_routing: bool = Field(default=True)
    adaptive_routing_mode: str = Field(default="auto")

    # Strategy targets
    strategy_fast_target_ms: int = Field(default=400)
    strategy_standard_target_ms: int = Field(default=800)
    strategy_precise_target_ms: int = Field(default=1500)

    # Cache
    enable_query_cache: bool = Field(default=True)
    query_cache_max_size: int = Field(default=1000)
    query_cache_ttl_seconds: int = Field(default=3600)

    # Prompts
    use_optimized_prompts: bool = Field(default=True)
    prompt_style: str = Field(default="simplified")
    enable_streaming_output: bool = Field(default=True)

    # Monitoring
    enable_performance_tracking: bool = Field(default=True)
    log_slow_queries_ms: int = Field(default=2000)
    log_stage_timings: bool = Field(default=True)

    # Fallbacks
    fallback_to_hybrid_search: bool = Field(default=True)
    fallback_to_score_ranking: bool = Field(default=True)

    class Config:
        env_prefix = ""
        case_sensitive = False


# Singleton instance
_optimized_settings: OptimizedRAGSettings | None = None


def get_optimized_settings() -> OptimizedRAGSettings:
    """Get or create optimized RAG settings instance."""
    global _optimized_settings
    if _optimized_settings is None:
        _optimized_settings = OptimizedRAGSettings()
    return _optimized_settings
