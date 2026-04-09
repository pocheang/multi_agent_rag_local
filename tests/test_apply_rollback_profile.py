from pathlib import Path
import subprocess
import sys


def test_apply_rollback_profile_updates_env_file():
    profile = Path("data/eval/.tmp_profile.env")
    env_file = Path("data/eval/.tmp_env.env")
    profile.write_text("RETRIEVAL_STRATEGY=baseline\nQUERY_REWRITE_ENABLED=false\n", encoding="utf-8")
    env_file.write_text("FOO=bar\n", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/apply_rollback_profile.py",
            "--profile",
            str(profile),
            "--env-file",
            str(env_file),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    text = env_file.read_text(encoding="utf-8")
    assert "RETRIEVAL_STRATEGY=baseline" in text
    assert "QUERY_REWRITE_ENABLED=false" in text
    profile.unlink(missing_ok=True)
    env_file.unlink(missing_ok=True)
