def strategy_flags(retrieval_strategy: str | None) -> dict[str, bool]:
    """Parse retrieval strategy into feature flags."""
    strategy = str(retrieval_strategy or "advanced").strip().lower()
    if strategy == "baseline":
        return {"rewrite": False, "decompose": False, "dynamic": False, "rank_feature": False}
    if strategy == "safe":
        return {"rewrite": True, "decompose": False, "dynamic": False, "rank_feature": False}
    return {"rewrite": True, "decompose": True, "dynamic": True, "rank_feature": True}
