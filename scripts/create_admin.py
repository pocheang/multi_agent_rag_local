#!/usr/bin/env python
"""Create (or reset) the local development administrator.

    conda run -n rag-local python scripts/create_admin.py

The account is a **development fixture**, not a deployment step. It exists so the
admin surface can be opened and looked at on a checkout: before this there was no
account with the `admin` role at all, so `/admin/config/schema`, the ops pages and
the user management screens could not be exercised by anyone.

The password comes from `ADMIN_PASSWORD` when it is set, and is otherwise
generated and printed **once**. It is never written to a file in the repository,
because a credential in version control is a credential in everyone's checkout —
and a fixture password has a way of reaching a server that is not a fixture.

Idempotent: an existing account is left alone unless `--reset-password` is given,
so re-running this after a database reset is safe and re-running it by accident
costs nothing.

Policy (`app/services/auth/validation.py`): at least 12 characters, with
lowercase, uppercase, a digit and one of `!@#$%^&*()_+-=[]{}|;:,.<>?`.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

LOWER = "abcdefghijkmnopqrstuvwxyz"  # no l
UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I, O
DIGITS = "23456789"  # no 0, 1
SPECIAL = "!@#$%^&*_+-=?"


def generate_password(length: int = 20) -> str:
    """A password that satisfies the policy by construction, not by retrying.

    Ambiguous glyphs are left out because this one gets read off a terminal and
    typed into a browser.
    """

    alphabet = LOWER + UPPER + DIGITS + SPECIAL
    required = [
        secrets.choice(LOWER),
        secrets.choice(UPPER),
        secrets.choice(DIGITS),
        secrets.choice(SPECIAL),
    ]
    rest = [secrets.choice(alphabet) for _ in range(max(length - len(required), 0))]
    chars = required + rest
    # Shuffle so the guaranteed characters are not always in the same positions.
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--username", default=os.getenv("ADMIN_USERNAME", "admin"))
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Set a new password on an account that already exists.",
    )
    args = parser.parse_args(argv)

    from app.core.config import get_settings
    from app.services.auth.auth_service import AuthDBService
    from app.services.auth.password_utils import generate_salt, hash_password
    from app.services.auth.validation import validate_password

    settings = get_settings()
    service = AuthDBService()

    supplied = os.getenv("ADMIN_PASSWORD", "")
    password = supplied or generate_password()
    try:
        validate_password(password)
    except ValueError as exc:
        print(f"ADMIN_PASSWORD does not meet the policy: {exc}", file=sys.stderr)
        return 1

    with service._connect() as conn:
        row = conn.execute(
            "SELECT user_id, role FROM users WHERE lower(username) = ?", (args.username.lower(),)
        ).fetchone()

    if row is not None and not args.reset_password:
        print(f"'{args.username}' already exists with role '{row[1]}'; nothing to do.")
        print("Pass --reset-password to set a new password.")
        return 0

    if row is not None:
        # `change_password` verifies the old password, which a reset does not
        # have, so the hash is rewritten with the same primitives the service
        # uses to create one. Keeping the user_id matters: it owns documents.
        salt = generate_salt()
        with service._connect() as conn:
            conn.execute(
                "UPDATE users SET salt = ?, password_hash = ? WHERE user_id = ?",
                (salt, hash_password(password, salt), row[0]),
            )
            conn.commit()
        action = "password reset for"
    else:
        service.create_user_with_role(username=args.username, password=password, role="admin")
        action = "created"

    print(f"{action} administrator '{args.username}' in {settings.users_path}")
    if supplied:
        print("password: (taken from ADMIN_PASSWORD)")
    else:
        print(f"password: {password}")
        print("\nThis is printed once and stored only as a hash. Save it now.")
    print("\nDevelopment fixture. Do not reuse this account or password anywhere real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
