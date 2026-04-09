from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from app.core.config import get_settings


def main():
    p = argparse.ArgumentParser(description="Move history sessions between hot/cold tiers")
    p.add_argument("--mode", choices=["to-cold", "to-hot"], default="to-cold")
    p.add_argument("--user-id", default="", help="optional user folder name under sessions")
    args = p.parse_args()

    settings = get_settings()
    hot_root = settings.sessions_path
    cold_root = settings.history_cold_path
    moved = 0

    if args.user_id:
        pairs = [(hot_root / args.user_id, cold_root / args.user_id)]
    else:
        pairs = []
        for pth in hot_root.iterdir():
            if pth.is_dir():
                pairs.append((pth, cold_root / pth.name))

    for hot_dir, cold_dir in pairs:
        cold_dir.mkdir(parents=True, exist_ok=True)
        if args.mode == "to-cold":
            src_dir, dst_dir = hot_dir, cold_dir
        else:
            src_dir, dst_dir = cold_dir, hot_dir
        if not src_dir.exists():
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)
        for f in src_dir.glob("*.json"):
            target = dst_dir / f.name
            shutil.move(str(f), str(target))
            moved += 1

    print(json.dumps({"ok": True, "mode": args.mode, "moved": moved}, ensure_ascii=False))


if __name__ == "__main__":
    main()
