"""Query status tracking endpoint for duplicate/async requests."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api import dependencies as api_dependencies
from app.api.dependencies import _require_user, _trace_id
from app.api.query.response import ensure_trackable_execution_result, parse_query_response
from app.api.schemas.http import QueryResponse
from app.api.transport.errors import not_found

router = APIRouter(prefix="/query", tags=["query"])


@router.get("/status/{request_id}", response_model=QueryResponse)
def get_query_status(
    request_id: str,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """
    获取查询状态（用于处理重复请求或长时间运行的查询）

    当查询返回 status="processing" 时，前端可以使用此端点轮询结果

    Args:
        request_id: 查询请求ID或cache_key
        request: FastAPI request对象
        user: 认证用户

    Returns:
        QueryResponse: 查询结果或处理状态
    """
    query_runtime = api_dependencies.get_query_runtime()
    query_result_cache = query_runtime.query_result_cache

    # 尝试从缓存中获取结果
    user_id = str(user.get("user_id", ""))

    # request_id 可能是完整的cache_key，也可能是部分ID
    # 我们需要在缓存中查找匹配的结果
    cached = query_result_cache.get(request_id, session_id=None, user_id=user_id)

    if isinstance(cached, dict) and cached:
        try:
            # 找到结果，返回完整响应
            cached_payload = ensure_trackable_execution_result(
                cached, question="", user=user
            )
            return parse_query_response(cached_payload)
        except (ValueError, TypeError):
            # 缓存损坏，返回404
            raise not_found("Query result")

    # 检查是否仍在处理中
    if query_result_cache.is_inflight(request_id):
        # 仍在处理，返回处理中状态
        return QueryResponse(
            answer="查询正在处理中，请继续等待...",
            route="processing",
            status="processing",
            request_id=request_id,
            detected_language="zh",
            debug={
                "message": "您的查询正在后台处理中",
                "trace_id": _trace_id(request),
                "suggestion": "请在几秒后重试此端点",
            }
        )

    # 既不在缓存也不在处理中，可能已过期或无效
    raise not_found("Query result not found or expired")


__all__ = ["router"]
