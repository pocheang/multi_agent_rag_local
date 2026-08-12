"""
多租户隔离工具函数

提供统一的用户归属验证和资源访问控制机制，确保多租户环境下的数据隔离。
"""

import logging
from typing import Any

from app.api.transport.errors import forbidden

logger = logging.getLogger(__name__)


def verify_resource_ownership(
    resource: dict[str, Any],
    user: dict[str, Any],
    resource_type: str,
    allow_public: bool = False,
    owner_field: str = "owner_user_id",
) -> None:
    """
    验证用户是否有权限访问资源。

    Args:
        resource: 资源对象，必须包含用户归属信息
        user: 当前用户对象
        resource_type: 资源类型（用于错误消息）
        allow_public: 是否允许访问 public visibility 的资源
        owner_field: 资源对象中表示所有者的字段名

    Raises:
        HTTPException: 如果用户没有权限访问该资源

    Notes:
        - 管理员（admin）可以访问所有资源
        - 普通用户只能访问自己拥有的资源
        - 如果 allow_public=True，所有用户可以访问 public 资源
    """
    role = str(user.get("role", "viewer")).lower()

    # 管理员可以访问所有资源
    if role == "admin":
        logger.debug(f"Admin access granted to {resource_type}")
        return

    user_id = str(user.get("user_id", ""))

    # 尝试多个可能的所有者字段
    owner_id = str(resource.get(owner_field) or resource.get("user_id") or "")

    # 如果允许 public 资源，检查 visibility
    if allow_public:
        visibility = str(resource.get("visibility", "private")).lower()
        if visibility == "public":
            logger.debug(f"Public {resource_type} access granted")
            return

    # 验证所有者匹配
    if user_id != owner_id:
        logger.warning(
            f"Unauthorized {resource_type} access attempt: "
            f"user={user_id}, owner={owner_id}, resource_type={resource_type}"
        )
        raise forbidden(f"You do not have permission to access this {resource_type}")

    logger.debug(f"Owner access granted to {resource_type}: user={user_id}")


def verify_user_matches(expected_user_id: str, actual_user: dict[str, Any], context: str) -> None:
    """
    验证当前用户 ID 是否匹配期望的用户 ID。

    Args:
        expected_user_id: 期望的用户 ID
        actual_user: 当前用户对象
        context: 上下文描述（用于日志和错误消息）

    Raises:
        HTTPException: 如果用户 ID 不匹配且不是管理员
    """
    role = str(actual_user.get("role", "viewer")).lower()

    if role == "admin":
        return

    actual_user_id = str(actual_user.get("user_id", ""))

    if actual_user_id != expected_user_id:
        logger.warning(f"User ID mismatch in {context}: expected={expected_user_id}, actual={actual_user_id}")
        raise forbidden(f"Access denied: {context}")


def filter_resources_by_ownership(
    resources: list[dict[str, Any]], user: dict[str, Any], owner_field: str = "owner_user_id", allow_public: bool = True
) -> list[dict[str, Any]]:
    """
    过滤资源列表，只保留用户有权访问的资源。

    Args:
        resources: 资源列表
        user: 当前用户对象
        owner_field: 资源对象中表示所有者的字段名
        allow_public: 是否包含 public visibility 的资源

    Returns:
        过滤后的资源列表
    """
    role = str(user.get("role", "viewer")).lower()

    # 管理员可以看到所有资源
    if role == "admin":
        return resources

    user_id = str(user.get("user_id", ""))
    filtered = []

    for resource in resources:
        owner_id = str(resource.get(owner_field) or resource.get("user_id") or "")

        # 用户自己的资源
        if owner_id == user_id:
            filtered.append(resource)
            continue

        # Public 资源
        if allow_public:
            visibility = str(resource.get("visibility", "private")).lower()
            if visibility == "public":
                filtered.append(resource)
                continue

    return filtered


def get_user_scoped_cache_key(base_key: str, user_id: str, scope: str = "user") -> str:
    """
    生成带用户作用域的缓存键。

    Args:
        base_key: 基础缓存键
        user_id: 用户 ID
        scope: 作用域标识符

    Returns:
        用户作用域的缓存键
    """
    return f"{scope}:{user_id}:{base_key}"


def validate_cache_ownership(
    cached_data: dict[str, Any] | None, user: dict[str, Any], owner_field: str = "user_id"
) -> dict[str, Any] | None:
    """
    验证缓存数据的用户归属。

    Args:
        cached_data: 缓存的数据
        user: 当前用户对象
        owner_field: 数据中表示所有者的字段名

    Returns:
        如果验证通过返回缓存数据，否则返回 None
    """
    if not cached_data:
        return None

    role = str(user.get("role", "viewer")).lower()
    if role == "admin":
        return cached_data

    user_id = str(user.get("user_id", ""))
    cached_user_id = str(cached_data.get(owner_field, ""))

    if cached_user_id and cached_user_id != user_id:
        logger.warning(f"Cache ownership mismatch: expected={user_id}, cached={cached_user_id}")
        return None

    return cached_data
