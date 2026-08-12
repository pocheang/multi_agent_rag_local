from app.domain.text import normalize_string
from app.core.config import get_settings

_ALLOWED = {"baseline", "advanced", "safe"}


def normalize_retrieval_profile(value: str | None) -> str:
    v = normalize_string(value, lowercase=True)
    if v in _ALLOWED:
        return v
    default = normalize_string(get_settings().retrieval_profile, lowercase=True) or "advanced"
    return default if default in _ALLOWED else "advanced"


def profile_to_strategy(profile: str) -> str:
    p = normalize_retrieval_profile(profile)
    return p


def profile_force_local_only(profile: str) -> bool:
    return normalize_retrieval_profile(profile) == "safe"
