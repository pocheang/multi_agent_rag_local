import hashlib
import hmac
import secrets


def hash_password(password: str, salt_hex: str, iterations: int = 200_000) -> str:
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()


def generate_salt() -> str:
    return secrets.token_hex(16)


def verify_password(password: str, salt_hex: str, password_hash: str) -> bool:
    hashed = hash_password(password, salt_hex)
    return hmac.compare_digest(hashed, password_hash)
