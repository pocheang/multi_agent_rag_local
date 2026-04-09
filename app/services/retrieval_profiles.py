from app.core.config import get_settings


_ALLOWED = {"baseline", "advanced", "safe"}


def normalize_retrieval_profile(value: str | None) -> str:
    v = str(value or "").strip().lower()
    if v in _ALLOWED:
        return v
    default = str(get_settings().retrieval_profile or "advanced").strip().lower()
    return default if default in _ALLOWED else "advanced"


def profile_to_strategy(profile: str) -> str:
    p = normalize_retrieval_profile(profile)
    return p


def profile_force_local_only(profile: str) -> bool:
    return normalize_retrieval_profile(profile) == "safe"
