"""Public QueryMind router assembly."""

from fastapi import APIRouter

from app.api.query.request import query
from app.api.routes.public.query_stream import stream_query
from app.api.schemas import QueryResponse

router = APIRouter(prefix="/query", tags=["query"])
router.add_api_route("", query, methods=["POST"], response_model=QueryResponse)
router.add_api_route("/query/stream", stream_query, methods=["POST"])
router.add_api_route("/stream", stream_query, methods=["POST"])

__all__ = ["router"]
