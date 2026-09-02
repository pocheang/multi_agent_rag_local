"""Session management API routes."""

from fastapi import APIRouter

from .export import router as export_router
from .metadata import router as metadata_router

# Combined router for all session endpoints
router = APIRouter()
router.include_router(metadata_router)
router.include_router(export_router)

__all__ = ["router"]
