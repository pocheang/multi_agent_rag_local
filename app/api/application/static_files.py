"""Static-file configuration retained by the API application factory.

This module intentionally contains only HTTP adaptation for the built React
application and the Web Activity Dashboard assets.  It does not know about
routes, services, or application lifecycle concerns.
"""

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.transport.errors import not_found


@dataclass(frozen=True)
class StaticFilePaths:
    """Resolved frontend and dashboard locations used by the API entry point."""

    react_dist_dir: Path
    react_index_file: Path
    react_assets_dir: Path
    static_dir: Path


def build_frontend_handlers(paths: StaticFilePaths):
    """Build the frontend fallback handlers for a resolved path set."""

    def serve_react_index() -> FileResponse:
        """Serve the React index.html file."""
        if not paths.react_index_file.exists():
            raise not_found("frontend build")
        return FileResponse(str(paths.react_index_file))

    def serve_react_app_root() -> FileResponse:
        """Serve React app root."""
        return serve_react_index()

    def serve_react_app(frontend_path: str) -> FileResponse:
        """Serve React app for all frontend routes."""
        normalized = str(frontend_path or "").strip().strip("/")
        if normalized.startswith("assets/"):
            raise not_found("asset")
        return serve_react_index()

    return serve_react_index, serve_react_app_root, serve_react_app


def resolve_static_file_paths() -> StaticFilePaths:
    """Resolve the same frontend and dashboard paths used by ``app.api.main``."""
    repository_root = Path(__file__).resolve().parents[3]
    react_dist_dir = repository_root / "frontend" / "dist"
    return StaticFilePaths(
        react_dist_dir=react_dist_dir,
        react_index_file=react_dist_dir / "index.html",
        react_assets_dir=react_dist_dir / "assets",
        static_dir=repository_root / "app" / "static",
    )


def configure_static_files(
    app: FastAPI,
    paths: StaticFilePaths | None = None,
    handlers=None,
) -> StaticFilePaths:
    """Mount static content and register the unchanged React fallback routes.

    The caller must invoke this after router registration, matching the current
    order in ``app.api.main``.  Mount paths, mount names, root routes, and the
    fallback's missing-asset behavior intentionally match that entry point.
    """
    paths = paths or resolve_static_file_paths()

    if paths.react_assets_dir.exists():
        app.mount(
            "/app/assets",
            StaticFiles(directory=str(paths.react_assets_dir)),
            name="react-assets",
        )

    if paths.static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(paths.static_dir)), name="static")

    serve_react_index, serve_react_app_root, serve_react_app = handlers or build_frontend_handlers(paths)

    # Keep the original decorator registration order: /app/ then /app.
    app.add_api_route("/app/", serve_react_app_root, methods=["GET"])
    app.add_api_route("/app", serve_react_app_root, methods=["GET"])
    app.add_api_route("/app/{frontend_path:path}", serve_react_app, methods=["GET"])
    return paths


__all__ = [
    "StaticFilePaths",
    "build_frontend_handlers",
    "configure_static_files",
    "resolve_static_file_paths",
]
