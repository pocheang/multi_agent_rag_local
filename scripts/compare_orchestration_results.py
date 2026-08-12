"""Summarize typed orchestration shadow observations for rollout review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.orchestration.shadow import ShadowObservation


def summarize_observations(path: Path) -> dict[str, object]:
    """Read JSONL observations and produce only aggregate rollout evidence."""
    observations: list[ShadowObservation] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                observations.append(ShadowObservation.model_validate_json(line))
            except ValueError:
                continue
    completed = [item for item in observations if item.status == "completed"]
    similarities = [item.answer_similarity for item in completed if item.answer_similarity is not None]
    grounding_deltas = [item.candidate_grounding - item.primary_grounding for item in completed]
    return {
        "total": len(observations),
        "completed": len(completed),
        "failed": sum(item.status == "failed" for item in observations),
        "skipped": sum(item.status == "skipped" for item in observations),
        "average_answer_similarity": round(sum(similarities) / len(similarities), 4) if similarities else None,
        "average_grounding_delta": round(sum(grounding_deltas) / len(grounding_deltas), 4)
        if grounding_deltas
        else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize orchestration shadow comparisons.")
    parser.add_argument("--input", default="data/eval/shadow_runs.jsonl")
    parser.add_argument("--output")
    args = parser.parse_args()
    summary = summarize_observations(Path(args.input))
    rendered = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
