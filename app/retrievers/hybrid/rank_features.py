from datetime import datetime, timezone


def parse_iso_datetime(value: str) -> datetime | None:
    """Parse ISO datetime string with timezone support."""
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        raw = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def rank_feature_score(item: dict, settings) -> float:
    """Calculate rank feature score based on source, freshness, and diversity."""
    if not bool(getattr(settings, "rank_feature_enabled", True)):
        return 0.0
    metadata = item.get("metadata", {}) or {}
    source_weight = float(getattr(settings, "rank_feature_source_weight", 0.08) or 0.08)
    freshness_weight = float(getattr(settings, "rank_feature_freshness_weight", 0.07) or 0.07)
    diversity_weight = float(getattr(settings, "rank_feature_retrieval_diversity_weight", 0.05) or 0.05)

    source_signal = 0.0
    src = str(metadata.get("source", "")).lower()
    if src:
        if src.endswith((".md", ".pdf", ".docx", ".txt")):
            source_signal = 1.0
        else:
            source_signal = 0.6

    freshness_signal = 0.0
    for key in ("updated_at", "created_at", "ingested_at", "timestamp"):
        dt = parse_iso_datetime(str(metadata.get(key, "")))
        if not dt:
            continue
        age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
        freshness_signal = max(0.0, 1.0 - min(age_days / 365.0, 1.0))
        break

    retrieval_sources = item.get("retrieval_sources", [])
    if not isinstance(retrieval_sources, list):
        retrieval_sources = [str(retrieval_sources)]
    diversity_signal = min(1.0, len(set([str(x) for x in retrieval_sources])) / 2.0)

    return (source_weight * source_signal) + (freshness_weight * freshness_signal) + (diversity_weight * diversity_signal)
