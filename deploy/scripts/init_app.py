"""Idempotently initialize application-owned SQLite/auth schema."""

from app.api.utils.auth_dependencies import auth_service


def main() -> int:
    print(f"Application database initialized: {auth_service.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
