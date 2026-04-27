import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def write_parent_records(records: list[dict[str, Any]], path: Path | None = None) -> None:
    settings = get_settings()
    target = path or settings.parent_store_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_parent_records(path: Path | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    target = path or settings.parent_store_path
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def get_parent_text_map(parent_ids: list[str]) -> dict[str, str]:
    wanted = {str(x) for x in parent_ids if x}
    if not wanted:
        return {}
    rows = read_parent_records()
    out: dict[str, str] = {}
    for row in rows:
        parent_id = str(row.get("id", ""))
        if parent_id in wanted:
            out[parent_id] = str(row.get("text", ""))
            # Early exit optimization: stop scanning if we found all wanted IDs
            if len(out) == len(wanted):
                break
    return out
