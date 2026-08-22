import hashlib
import hmac
import secrets

# 安全改进：提升迭代次数到 OWASP 2023 推荐值
# OWASP 推荐 PBKDF2-SHA256 至少 600,000 次迭代
# 参考：https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
DEFAULT_ITERATIONS = 600_000


def hash_password(password: str, salt_hex: str, iterations: int = DEFAULT_ITERATIONS) -> str:
    """
    使用 PBKDF2-HMAC-SHA256 哈希密码

    安全改进：默认迭代次数从 200,000 提升到 600,000（OWASP 2023 推荐）

    Args:
        password: 明文密码
        salt_hex: 十六进制盐值
        iterations: PBKDF2 迭代次数（默认 600,000）

    Returns:
        十六进制密码哈希
    """
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()


def generate_salt() -> str:
    """生成加密安全的随机盐值"""
    return secrets.token_hex(16)


def verify_password(password: str, salt_hex: str, password_hash: str, iterations: int = DEFAULT_ITERATIONS) -> bool:
    """
    验证密码

    使用常量时间比较防止时序攻击

    Args:
        password: 待验证的明文密码
        salt_hex: 十六进制盐值
        password_hash: 存储的密码哈希
        iterations: PBKDF2 迭代次数（默认 600,000）

    Returns:
        密码是否匹配
    """
    hashed = hash_password(password, salt_hex, iterations)
    return hmac.compare_digest(hashed, password_hash)
