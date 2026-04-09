from app.services.runtime_ops import (
    apply_rollback_profile,
    choose_shadow,
    resolve_profile_for_request,
    set_active_profile,
    set_canary,
    set_shadow,
)


def test_runtime_profile_override_and_rollback():
    state = set_active_profile("advanced", follow_config_default=False)
    assert state["active_profile"] == "advanced"

    rolled = apply_rollback_profile()
    assert rolled["active_profile"] == "baseline"
    assert rolled["canary"]["enabled"] is False


def test_canary_profile_resolution():
    set_active_profile("advanced", follow_config_default=False)
    set_canary(enabled=True, baseline_percent=100, safe_percent=0, seed="test")
    profile, meta = resolve_profile_for_request(
        None,
        user_id="u1",
        session_id="s1",
        question="what is ragflow",
    )
    assert profile == "baseline"
    assert meta["reason"] == "canary_baseline"


def test_shadow_sampling_resolution():
    set_shadow(enabled=True, strategy="safe", sample_percent=100, seed="s")
    enabled, strategy = choose_shadow(user_id="u1", session_id="s1", question="q1")
    assert enabled is True
    assert strategy == "safe"
