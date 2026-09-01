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

from app.api import dependencies as api_dependencies
from app.core.config import Settings, reload_settings
from app.graph.knowledge.client import Neo4jClient
from app.retrievers.stores.vector import clear_vector_store_cache
from app.services.models.runtime import clear_model_caches
from app.services.runtime.bulkhead import reset_bulkheads

logger = logging.getLogger(__name__)


def apply_config_reload() -> Settings:
    """Re-read `Settings` and drop everything built from the old ones.

    Note what this cannot do: a value already read into a module-level constant
    is not revisited, so anything still living in the legacy constant block
    keeps its start-up value until the process restarts. That is the practical
    reason those constants are being migrated into `Settings`, and why a field
    that is only safe to change at restart has to say so in the admin schema.
    """

    new_settings = reload_settings()
    api_dependencies.reload_query_runtime(new_settings)
    clear_model_caches()
    clear_vector_store_cache()
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


__all__ = ["apply_config_reload", "reload_from_remote_config"]
