def strategy_flags() -> dict[str, bool]:
    """Feature flags for the single supported retrieval strategy."""
    return {"rewrite": True, "decompose": True, "dynamic": True, "rank_feature": True}
