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


def test_ci_quality_gate_runtime_unavailable_fails_by_default_and_can_be_overridden():
    base_cmd = [
        sys.executable,
        "scripts/ci_quality_gate.py",
        "--dataset",
        "data/eval/retrieval_eval.jsonl",
    ]
    proc_default = subprocess.run(base_cmd, capture_output=True, text=True)
    proc_allow = subprocess.run(base_cmd + ["--allow-runtime-unavailable"], capture_output=True, text=True)

    assert proc_default.returncode in {0, 3}
    assert proc_allow.returncode in {0, 3}
    if proc_default.returncode == 3:
        assert proc_allow.returncode == 0
