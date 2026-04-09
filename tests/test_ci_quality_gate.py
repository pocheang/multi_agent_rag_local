from pathlib import Path
import subprocess
import sys


def test_ci_quality_gate_emits_rollback_profile_when_runtime_required():
    rollback = Path("data/eval/.tmp_rollback_test.env")
    report = Path("data/eval/.tmp_quality_report_test.md")
    if rollback.exists():
        rollback.unlink()
    if report.exists():
        report.unlink()
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/ci_quality_gate.py",
            "--dataset",
            "data/eval/retrieval_eval.jsonl",
            "--require-runtime",
            "--auto-rollback-file",
            str(rollback),
            "--report-md",
            str(report),
        ],
        capture_output=True,
        text=True,
    )
    # In lightweight test env, runtime is usually unavailable and should trigger rollback profile.
    assert proc.returncode in {0, 3}
    assert report.exists()
    if proc.returncode == 3:
        assert rollback.exists()
        content = rollback.read_text(encoding="utf-8")
        assert "RETRIEVAL_STRATEGY=baseline" in content
    if rollback.exists():
        rollback.unlink()
    if report.exists():
        report.unlink()
