import json

from app.services.resilience import TTLCache

_RETRIEVAL_CACHE: TTLCache | None = None
_REDIS_CLIENT = None


def cache_backend(settings) -> str:
    """Determine which cache backend to use."""
    raw = str(getattr(settings, "retrieval_cache_backend", "auto") or "auto").strip().lower()
    if raw in {"off", "none", "disabled"}:
        return "off"
    if raw in {"memory", "redis"}:
        return raw
    return "auto"


def redis_client(settings):
    """Get or create Redis client."""
    global _REDIS_CLIENT
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    try:
        import redis  # type: ignore
    except Exception:
        return None
    try:
        _REDIS_CLIENT = redis.from_url(str(getattr(settings, "redis_url", "")))
        _REDIS_CLIENT.ping()
    except Exception:
        _REDIS_CLIENT = None
    return _REDIS_CLIENT


def get_retrieval_cache(settings) -> TTLCache:
    """Get or create the in-memory retrieval cache."""
    global _RETRIEVAL_CACHE
    if _RETRIEVAL_CACHE is None:
        _RETRIEVAL_CACHE = TTLCache(
            ttl_seconds=int(getattr(settings, "retrieval_cache_ttl_seconds", 45) or 45),
            max_items=int(getattr(settings, "retrieval_cache_max_items", 256) or 256),
        )
    return _RETRIEVAL_CACHE


def clear_retrieval_cache() -> None:
    """Clear both memory and Redis caches."""
    global _RETRIEVAL_CACHE
    _RETRIEVAL_CACHE = None
    try:
        from app.core.config import get_settings
        settings = get_settings()
        backend = cache_backend(settings)
        if backend not in {"redis", "auto"}:
            return
        client = redis_client(settings)
        if client is None:
            return
        keys = list(client.scan_iter(match="retrieval:*", count=500))
        if keys:
            client.delete(*keys)
    except Exception:
        return


def cache_lookup(cache_key: str, settings, traced_span_fn):
    """Look up cached results from Redis or memory."""
    backend = cache_backend(settings)
    use_cache = bool(getattr(settings, "retrieval_cache_enabled", True)) and backend != "off"
    if not use_cache:
        return None

    with traced_span_fn("retrieval.cache_lookup", {"backend": backend}):
        if backend in {"redis", "auto"}:
            client = redis_client(settings)
        else:
            client = None
        if client is not None:
            try:
                raw = client.get(f"retrieval:{cache_key}")
                if raw:
                    payload = json.loads(raw)
                    out_diag = dict(payload.get("diagnostics", {}))
                    out_diag["cache_hit"] = True
                    out_diag["cache_backend"] = "redis"
                    return list(payload.get("results", [])), out_diag
            except Exception as e:
                import logging
                logging.getLogger(__name__).debug(f"Redis cache lookup failed, falling back to memory: {type(e).__name__}")
        cache = get_retrieval_cache(settings)
        cached = cache.get(cache_key)
        if cached:
            results, diagnostics = cached
            out_diag = dict(diagnostics)
            out_diag["cache_hit"] = True
            out_diag["cache_backend"] = "memory"
            return list(results), out_diag
    return None


def cache_store(cache_key: str, results: list, diagnostics: dict, settings):
    """Store results in cache (memory and optionally Redis)."""
    backend = cache_backend(settings)
    use_cache = bool(getattr(settings, "retrieval_cache_enabled", True)) and backend != "off"
    if not use_cache:
        return

    cache = get_retrieval_cache(settings)
    cache.set(cache_key, (list(results), dict(diagnostics)))
    if backend in {"redis", "auto"}:
        client = redis_client(settings)
        if client is not None:
            try:
                client.setex(
                    f"retrieval:{cache_key}",
                    int(getattr(settings, "retrieval_cache_ttl_seconds", 45) or 45),
                    json.dumps({"results": results, "diagnostics": diagnostics}, ensure_ascii=False),
                )
                diagnostics["cache_backend"] = "redis"
            except Exception:
                diagnostics["cache_backend"] = "memory"
        else:
            diagnostics["cache_backend"] = "memory"
