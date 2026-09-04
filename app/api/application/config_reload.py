"""One definition of "the configuration was reloaded".

Two things now trigger a reload -- the admin endpoint and a push from the
configuration centre -- and they must do the same work. A watcher that dropped
its own subset of the caches would be a second, quieter definition, and the
difference would only ever show up as "the value took effect when I clicked the
button but not when I saved it in the console".

Living in the API layer rather than under `app/services/` is deliberate: the
sequence has to touch `api_dependencies`, and a service importing the API layer
would invert the dependency.
"""

from __future__ import annotations

import logging

from app.agents.validation.public import clear_validation_caches
from app.api import dependencies as api_dependencies
from app.core.config import Settings, get_settings, reload_settings
from app.core.config_schema import describe, validate_values
from app.core.remote_config import RemoteDocuments, parse_properties, remote_config_enabled
from app.graph.knowledge.client import Neo4jClient
from app.retrievers.hybrid.caching import clear_retrieval_cache
from app.retrievers.reranker import clear_reranker_cache
from app.retrievers.stores.vector import clear_vector_store_cache
from app.services.models.runtime import clear_model_caches
from app.services.runtime.bulkhead import reset_bulkheads

logger = logging.getLogger(__name__)


def apply_config_reload() -> Settings:
    """Re-read `Settings` and drop everything built from the old ones.

    Every editable field's consumer is covered: read through `get_settings()` per
    use, or rebuilt here, or held by an object `RAGPipeline` constructs per
    request. That is what lets the admin schema report `requires_restart=False`
    across the board -- audited on 2026-09-01, and the retrieval cache was the one
    exception, which is why it is cleared here rather than marked.
    """

    new_settings = reload_settings()
    api_dependencies.reload_query_runtime(new_settings)
    clear_model_caches()
    clear_vector_store_cache()
    # The retrieval cache bakes its TTL and size in at construction and lives in
    # a module global, so a reload that left it alone would silently keep the old
    # TTL -- and the admin page would show the new one as though it had taken.
    clear_retrieval_cache()
    # Same shape as the retrieval cache above: the validation cascade bakes
    # every CASCADE_* value in at construction and lives in a module global,
    # and the NLI model is lru_cache'd on NLI_MODEL_NAME.
    clear_validation_caches()
    # clear_model_caches covers chat and embedding only; the reranker keeps
    # its own lru_cache keyed on RERANKER_MODEL_NAME.
    clear_reranker_cache()
    Neo4jClient.close_shared_driver()
    reset_bulkheads()
    return new_settings


def reload_from_remote_config() -> None:
    """Callback for the configuration centre; never raises into the SDK thread."""

    try:
        apply_config_reload()
        logger.info("remote config: change applied")
    except Exception:
        logger.exception("remote config: change could not be applied")


class ConfigWriteRefused(Exception):
    """The change was not written, and why."""


def write_config_values(values: dict[str, str], data_id: str | None = None) -> list[str]:
    """Persist edited values through the configuration centre, then reload.

    The one way configuration is changed at runtime. Both the admin page and the
    replay autotuner go through here, because the alternative -- what the
    autotuner used to do -- is to assign onto the live `Settings` object, and
    that fails twice over: the change is lost at the next reload, and the admin
    page's "which layer did this come from" column starts lying, since the value
    came from none of the layers.

    Returns the data ids written. Raises `ConfigWriteRefused` when the change
    cannot be made honestly: no configuration centre to write to, a value the
    process environment pins (the environment outranks the centre, so the write
    would succeed and change nothing), an unknown data id, or a value that is not
    editable or does not type-check.
    """

    if not values:
        return []
    if not remote_config_enabled():
        raise ConfigWriteRefused("no configuration centre is configured; set NACOS_ENABLED and restart")

    try:
        accepted = validate_values(values)
    except ValueError as exc:
        raise ConfigWriteRefused(str(exc)) from exc

    described = {row["alias"]: row for row in describe(get_settings())}
    pinned = sorted(alias for alias in accepted if not described.get(alias, {}).get("editable_here", True))
    if pinned:
        raise ConfigWriteRefused(
            f"pinned in the process environment, so the console cannot change them: {', '.join(pinned)}"
        )

    documents = RemoteDocuments()
    known = documents.config.data_ids
    if data_id is not None and data_id not in known:
        raise ConfigWriteRefused(f"unknown data id: {data_id}")

    current = {name: parse_properties(text) for name, text in documents.all().items()}
    fallback = data_id or known[-1]

    # Each key goes back to the document that already defines it. Writing
    # everything to one document instead puts the same key in two places, where
    # the later id silently wins -- so the page would show a value from one
    # document, the edit would land in another, and the two would drift apart.
    routed: dict[str, dict[str, str]] = {}
    for alias, value in accepted.items():
        target = data_id
        if target is None:
            owning = [name for name in known if alias in current.get(name, {})]
            target = owning[-1] if owning else fallback
        routed.setdefault(target, {})[alias] = value

    written: list[str] = []
    for name, changes in routed.items():
        merged = {**current.get(name, {}), **changes}
        try:
            published = documents.publish(name, merged)
        except Exception as exc:
            logger.exception("config write: publish failed for %s", name)
            raise ConfigWriteRefused(f"the configuration centre rejected the write: {exc}") from exc
        if not published:
            raise ConfigWriteRefused(f"the configuration centre did not accept the write to {name}")
        written.append(name)

    apply_config_reload()
    return sorted(written)


__all__ = [
    "ConfigWriteRefused",
    "apply_config_reload",
    "reload_from_remote_config",
    "write_config_values",
]
