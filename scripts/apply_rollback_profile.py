import argparse
from pathlib import Path


def _parse_profile(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _apply_env(env_path: Path, values: dict[str, str]) -> None:
    existing: dict[str, str] = {}
    order: list[str] = []
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            key = k.strip()
            existing[key] = v.strip()
            order.append(key)
    for k, v in values.items():
        existing[k] = v
        if k not in order:
            order.append(k)
    lines = [f"{k}={existing[k]}" for k in order]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply rollback profile .env overrides.")
    parser.add_argument("--profile", default="artifacts/rollback.env")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()

    profile = Path(args.profile)
    values = _parse_profile(profile)
    if not values:
        print(f"no_values_loaded_from_profile:{profile}")
        return 1
    env_path = Path(args.env_file)
    _apply_env(env_path, values)
    print(f"applied:{len(values)}_keys_to:{env_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
