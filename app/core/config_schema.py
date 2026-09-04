"""What an administrator may change from a console, and where each value came from.

Two decisions are recorded here, and both are deliberate.

**The editable set is a central allowlist, not an annotation on each field.**
`Settings` has 236 fields; annotating them individually would scatter a
security-relevant decision across 236 lines, and the question an operator or a
reviewer actually asks -- "what can someone with console access change?" -- would
have no single place to answer it. It is opt-in: a new field is not editable
until it is named here, which is the safe direction to fail.

**"Which layer did this value come from" is part of the schema.** It is the
question a configuration page exists to answer, and the one nothing in this
system could answer before: a value set in the process environment outranks the
console, so an administrator who changes something there and sees no effect needs
to be told *why*, not left to guess. The order mirrors
`Settings.settings_customise_sources` exactly.

`requires_restart` is honest rather than aspirational. Almost everything here is
hot because `RAGPipeline` and its services are built per request and
`apply_config_reload()` rebuilds the query runtime; the exceptions are values
read once into a module constant or captured by a long-lived object, and the
guard on that is `tests/core/test_config_has_one_source.py`, which keeps the
legacy constant block from growing. Nothing in that block is exposed here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.core.config import Settings, resolve_runtime_env_file
from app.core.remote_config import RemoteDocuments, parse_properties, remote_config_enabled


class ConfigLayer(StrEnum):
    """Where a value came from, in the precedence order Settings declares."""

    ENVIRONMENT = "environment"
    CONFIG_CENTRE = "config-centre"
    RUNTIME_FILE = "runtime-file"
    DEFAULT = "default"


@dataclass(frozen=True)
class EditableField:
    """One field an administrator may change, and what they need to know about it."""

    alias: str
    group: str
    summary: str
    requires_restart: bool = False


# Grouped the way the page should read, not the way Settings is ordered.
EDITABLE: tuple[EditableField, ...] = (
    # --- retrieval width -----------------------------------------------------
    EditableField("TOP_K", "retrieval", "Results per source before reranking."),
    EditableField("RERANKER_TOP_N", "retrieval", "Results kept after reranking."),
    # RERANKER_TOP_N was editable while the switch beside it and the model it
    # names were not, so an operator could change how many results reranking
    # returns but not whether it runs or what runs it. Both are safe to expose
    # now that `apply_config_reload` clears the reranker's own lru_cache -- until
    # 2026-09-04 it did not, and the page would have reported a model that was
    # not loaded.
    EditableField("ENABLE_RERANKER", "retrieval", "Rerank fused results with the cross-encoder."),
    EditableField(
        "RERANKER_MODEL_NAME",
        "retrieval",
        "Cross-encoder used for reranking. Must already be downloaded; retrieval falls back to lexical scoring if not.",
    ),
    EditableField("VECTOR_TOP_K", "retrieval", "Vector candidates on the legacy hybrid path."),
    EditableField("BM25_TOP_K", "retrieval", "BM25 candidates on the legacy hybrid path."),
    EditableField("DYNAMIC_RETRIEVAL_ENABLED", "retrieval", "Widen the search for complex questions."),
    EditableField("RANK_FEATURE_ENABLED", "retrieval", "Source and freshness weighting during fusion."),
    EditableField("RETRIEVAL_CACHE_ENABLED", "retrieval", "Reuse recent identical retrievals."),
    EditableField("RETRIEVAL_CACHE_TTL_SECONDS", "retrieval", "How long a cached retrieval stays valid."),
    # Editable because the replay autotuner writes it, and everything that
    # changes configuration at runtime goes through the same allowlist.
    EditableField("MAX_CONTEXT_CHUNKS", "retrieval", "Excerpts handed to the model after retrieval."),
    # --- query understanding -------------------------------------------------
    EditableField("QUERY_REWRITE_ENABLED", "query", "Rewrite the query before retrieving."),
    EditableField(
        "QUERY_REWRITE_WITH_LLM",
        "query",
        "Use an LLM for the rewrite. Costs a model call per query; this is what completes a follow-up question.",
    ),
    EditableField("QUERY_DECOMPOSE_ENABLED", "query", "Split a complex question into sub-queries."),
    EditableField("QUERY_EXPANSION_ENABLED", "query", "Expand the query with related terms."),
    # --- routing -------------------------------------------------------------
    EditableField("ENABLE_CALIBRATION", "routing", "Calibrate router confidence from recorded outcomes."),
    EditableField(
        "ENABLE_WEB_ROUTE_DOWNGRADE",
        "routing",
        "Rewrite a web route to vector. Removes web search from questions the router sent to the web.",
    ),
    EditableField(
        "GRAPH_RAG_ENHANCED",
        "routing",
        "Per-entity graph lookup instead of the batched one. Roughly 3 Neo4j round trips become up to 9.",
    ),
    # --- answer --------------------------------------------------------------
    # --- images -------------------------------------------------------------
    # Captioning is what makes an image searchable when OCR cannot read it -- a
    # photo, a diagram, a chart with no extractable text. It stayed off and
    # unreachable while its output was discarded on exactly those images; that
    # was fixed first, so turning it on now does something.
    EditableField("IMAGE_CAPTION_ENABLED", "images", "Describe images with a vision model during ingestion."),
    EditableField(
        "IMAGE_CAPTION_BACKEND",
        "images",
        "Which vision backend to try: auto, openai or ollama. auto follows MODEL_BACKEND and falls back.",
    ),
    EditableField("OPENAI_VISION_MODEL", "images", "Vision model for the OpenAI backend."),
    EditableField("OLLAMA_VISION_MODEL", "images", "Vision model for the Ollama backend."),
    EditableField("ANSWER_SAFETY_SCAN_ENABLED", "answer", "Redact secrets from finalized answers."),
    # The validation cascade. These were held back while `_get_validation_cascade`
    # cached a module global the reload did not clear -- an edit would have
    # reported success and changed nothing until restart. That is fixed, so
    # whether to expose them is now an ordinary decision, and the answer is yes:
    # each one changes how strictly an answer is judged, which is exactly the
    # kind of thing an operator tunes against real traffic.
    EditableField("CASCADE_ENABLE_RULES", "answer", "Rule checks: length, safety, obvious hallucination patterns."),
    EditableField("CASCADE_ENABLE_CITATIONS", "answer", "Check every claim carries a citation that resolves."),
    EditableField(
        "CASCADE_ENABLE_NLI",
        "answer",
        "Entailment check per sentence. Uses the cross-encoder on Latin text and a deterministic scorer otherwise.",
    ),
    EditableField("CASCADE_ENABLE_DEEP", "answer", "Ask the model to review a low-confidence answer. Costs a call."),
    EditableField("CASCADE_NLI_TIMEOUT_MS", "budgets", "Ceiling for the entailment check before it falls back."),
    EditableField("CASCADE_DEEP_TIMEOUT_MS", "budgets", "Ceiling for the deep review call."),
    EditableField("NLI_MAX_SENTENCES", "answer", "Sentences scored per answer. Bounds the entailment batch."),
    EditableField(
        "NLI_MODEL_NAME",
        "answer",
        "Cross-encoder for entailment. Must already be downloaded; the deterministic scorer runs if not.",
    ),
    EditableField(
        "ANSWER_FACT_VERIFICATION_ENABLED",
        "answer",
        "Verify claims against the evidence. Costs a model call per answer.",
    ),
    EditableField("SELF_RAG_RELEVANCE_THRESHOLD", "answer", "Below this, retrieved context counts as irrelevant."),
    EditableField("SELF_RAG_QUALITY_THRESHOLD", "answer", "Below this, an answer counts as low quality."),
    # --- budgets -------------------------------------------------------------
    EditableField("STAGE_TIMEOUT_TOTAL_MS", "budgets", "Ceiling for one whole request."),
    EditableField("STAGE_TIMEOUT_ROUTE_MS", "budgets", "Ceiling for routing."),
    EditableField("STAGE_TIMEOUT_RETRIEVAL_MS", "budgets", "Ceiling for retrieval."),
    EditableField("STAGE_TIMEOUT_SYNTHESIS_MS", "budgets", "Ceiling for answer generation."),
    EditableField("STAGE_TIMEOUT_TOOL_MS", "budgets", "Ceiling for the whole governed tool loop."),
    EditableField("KNOWLEDGE_SOURCE_TIMEOUT_MS", "budgets", "Ceiling for one retrieval source."),
    EditableField("LLM_REQUEST_TIMEOUT_SECONDS", "budgets", "Ceiling for one model call."),
    EditableField("TOOL_MAX_STEPS", "budgets", "Select-invoke-observe rounds per request."),
    # --- security ------------------------------------------------------------
    EditableField(
        "STRICT_CSP",
        "security",
        "Content-Security-Policy without unsafe-inline. The frontend must use nonces or it will break.",
    ),
)

EDITABLE_BY_ALIAS: dict[str, EditableField] = {field.alias: field for field in EDITABLE}


def _runtime_file_values() -> dict[str, str]:
    """What `.runtime/{APP_ENV}.env` holds, or nothing if there is no such file."""

    path = resolve_runtime_env_file()
    if not path:
        return {}
    try:
        return parse_properties(Path(path).read_text(encoding="utf-8"))
    except OSError:
        return {}


def _config_centre_values(documents: RemoteDocuments | None = None) -> dict[str, str]:
    """What the configuration centre holds, without going back to the network twice.

    A caller that already has the documents passes them; the `remote_config_enabled`
    check only decides whether to *build* a reader, never whether to read the one
    it was handed. Conflating the two made `describe(settings, documents)` ignore
    its own argument.
    """

    source = documents
    if source is None:
        if not remote_config_enabled():
            return {}
        source = RemoteDocuments()
    values: dict[str, str] = {}
    for document in source.all().values():
        values.update(parse_properties(document))
    return values


def describe(settings: Settings | None = None, documents: RemoteDocuments | None = None) -> list[dict[str, Any]]:
    """The editable fields, with their current value and the layer that supplied it.

    Resolution mirrors `Settings.settings_customise_sources`: the process
    environment wins, then the configuration centre, then the rendered runtime
    file, then the field's default. A value shown as `environment` cannot be
    changed from the console, and saying so is the point -- a deployment pins
    things deliberately, and an administrator editing into the void is the
    failure this column exists to prevent.
    """

    active = settings if settings is not None else Settings()
    remote = _config_centre_values(documents)
    from_file = _runtime_file_values()
    fields = Settings.model_fields

    described: list[dict[str, Any]] = []
    for editable in EDITABLE:
        name = next((n for n, f in fields.items() if (f.alias or n) == editable.alias), None)
        if name is None:  # pragma: no cover - the schema test forbids this
            continue
        if editable.alias in os.environ:
            layer = ConfigLayer.ENVIRONMENT
        elif editable.alias in remote:
            layer = ConfigLayer.CONFIG_CENTRE
        elif editable.alias in from_file:
            layer = ConfigLayer.RUNTIME_FILE
        else:
            layer = ConfigLayer.DEFAULT
        annotation = fields[name].annotation
        described.append(
            {
                "alias": editable.alias,
                "group": editable.group,
                "summary": editable.summary,
                "type": getattr(annotation, "__name__", str(annotation)),
                "value": getattr(active, name),
                "default": fields[name].default,
                "layer": str(layer),
                "editable_here": layer is not ConfigLayer.ENVIRONMENT,
                "requires_restart": editable.requires_restart,
            }
        )
    return described


def validate_values(values: dict[str, str]) -> dict[str, str]:
    """Type-check a proposed change by building a `Settings` from it.

    Returns the accepted values. Raises `ValueError` naming every rejected key,
    because a console that accepts `TOP_K=fifteen` and fails at the next request
    has moved the error somewhere nobody is looking.
    """

    unknown = sorted(set(values) - set(EDITABLE_BY_ALIAS))
    if unknown:
        raise ValueError(f"not editable: {', '.join(unknown)}")
    try:
        Settings(**values)
    except Exception as exc:  # pydantic's own message names the field and the reason
        raise ValueError(str(exc)) from exc
    return dict(values)


__all__ = [
    "EDITABLE",
    "EDITABLE_BY_ALIAS",
    "ConfigLayer",
    "EditableField",
    "describe",
    "validate_values",
]
