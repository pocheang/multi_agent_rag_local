import gc
import inspect
import os
import tempfile
from collections import Counter
from pathlib import Path


with tempfile.TemporaryDirectory(prefix="querymind-app-") as raw:
    root = Path(raw)
    os.environ.update(
        {
            "APP_ENV": "development",
            "APP_DB_PATH": str(root / "app.db"),
            "DATABASE_URL": f"sqlite:///{root / 'querymind.db'}",
            "SESSIONS_DIR": str(root / "sessions"),
            "UPLOADS_DIR": str(root / "uploads"),
            "DATA_DIR": str(root / "docs"),
            "CHROMA_PERSIST_DIR": str(root / "chroma"),
            "CORPUS_STORE_PATH": str(root / "chunks" / "chunks.jsonl"),
            "PARENT_STORE_PATH": str(root / "chunks" / "parents.jsonl"),
            "USERS_FILE": str(root / "security" / "users.json"),
            "AUTH_SESSIONS_FILE": str(root / "security" / "auth_sessions.json"),
            "HISTORY_SQLITE_PATH": str(root / "history.db"),
            "HISTORY_COLD_DIR": str(root / "sessions_cold"),
            "AUTO_INGEST_ENABLED": "false",
            "RESPONSE_SIGNING_ENABLED": "false",
            "API_SETTINGS_ENCRYPTION_KEY": "isolated-verification-key",
        }
    )

    from fastapi.routing import APIRoute

    from app.api import dependencies
    from app.api.main import app
    from app.api.routes.operations import evaluation
    from app.api.routes.sessions import metadata

    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    pairs = [
        (method, route.path)
        for route in routes
        for method in sorted(route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    ]
    duplicates = [pair for pair, count in Counter(pairs).items() if count > 1]
    assert not duplicates, duplicates

    by_path = {route.path: route for route in routes}

    def dependency_names(path: str) -> set[str]:
        names: set[str] = set()
        stack = list(by_path[path].dependant.dependencies)
        while stack:
            dependency = stack.pop()
            call = getattr(dependency, "call", None)
            names.add(str(getattr(call, "__name__", call)))
            stack.extend(dependency.dependencies)
        return names

    protected = {
        "/circuit-breakers",
        "/api/v1/agents/health",
        "/api/v1/agents/{agent_name}/health",
        "/api/advanced-rag/config",
        "/api/v1/enhanced/config",
        "/api/v1/enhanced/stats",
    }
    public = {"/health", "/ready", "/metrics"}
    missing_paths = (protected | public) - set(by_path)
    assert not missing_paths, missing_paths
    for path in protected:
        assert "require_admin" in dependency_names(path), (path, dependency_names(path))
    for path in public:
        assert "require_admin" not in dependency_names(path), (path, dependency_names(path))

    sync_functions = [
        metadata.update_session_metadata,
        metadata.get_session_metadata,
        metadata.delete_session_metadata,
        metadata.extract_auto_tags,
        metadata.search_sessions,
        metadata.get_all_tags,
        metadata.get_search_facets,
        evaluation.list_queries,
        evaluation.run_evaluation,
        evaluation.get_results,
        evaluation.compare_systems,
        evaluation.list_systems,
        evaluation.health_check,
    ]
    assert all(not inspect.iscoroutinefunction(function) for function in sync_functions)

    clarification_source = Path("app/api/routes/public/clarification.py").read_text(encoding="utf-8-sig")
    assert "query:execute" not in clarification_source
    assert clarification_source.count('"query:run"') == 3
    assert clarification_source.count('"session:create"') == 1

    print(f"api_routes={len(routes)}")
    print("duplicate_method_paths=0")
    print("diagnostic_auth_matrix=ok")
    print(f"sync_endpoints={len(sync_functions)}")
    print("clarification_permissions=ok")

    dependencies.get_query_runtime().shadow_queue.stop(timeout=2.0)
    gc.collect()
