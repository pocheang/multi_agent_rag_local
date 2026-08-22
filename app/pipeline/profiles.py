"""Profile definitions for the future unified RAG pipeline.

This module is deliberately configuration-only.  It does not import API routes
or workflows, so adding the contracts does not change any request traffic.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class PipelineProfile(StrEnum):
    """The compatibility profiles for the three existing public query APIs."""

    STANDARD = "standard"
    STRICT_QUALITY = "strict_quality"
    ADVANCED = "advanced"


@dataclass(frozen=True)
class CapabilityBudget:
    """Hard limits for model-assisted checks in one pipeline request.

    Deterministic checks intentionally have no numeric cap.  They do not make
    model calls and must remain available for every profile.
    """

    deterministic_checks_unlimited: bool = True
    max_deep_llm_validations: int = 1
    max_regenerations: int = 1
    default_llm_self_review: bool = False


@dataclass(frozen=True)
class ProfileCapabilities:
    """Existing capabilities exposed by a profile; this is not an executor."""

    local_retrieval: bool = True
    graph_retrieval: bool = True
    web_research: bool = True
    react_reasoning: bool = True
    conversation_context: bool = True
    language_control: bool = True
    citation_grounding: bool = True
    deterministic_validation: bool = True
    route_validation: bool = False
    retrieval_quality_scoring: bool = False
    answer_validation: bool = False
    quality_reporting: bool = False
    query_decomposition: bool = False
    self_rag: bool = False
    decomposition_requires_request_opt_in: bool = False
    self_rag_requires_request_opt_in: bool = False


@dataclass(frozen=True)
class ProfileDefinition:
    """Stable configuration for one compatibility profile."""

    profile: PipelineProfile
    public_endpoint: str
    capabilities: ProfileCapabilities
    budget: CapabilityBudget
    default_retrieval_strategy: str | None = None


_STANDARD_BUDGET: Final = CapabilityBudget()
_STRICT_QUALITY_BUDGET: Final = CapabilityBudget()
_ADVANCED_BUDGET: Final = CapabilityBudget()


# Defaults are deliberately derived from the existing request models and the
# task-1 baseline.  Any change requires a refreshed baseline and release note.
PROFILE_DEFINITIONS: Final[Mapping[PipelineProfile, ProfileDefinition]] = MappingProxyType(
    {
        PipelineProfile.STANDARD: ProfileDefinition(
            profile=PipelineProfile.STANDARD,
            public_endpoint="/query",
            capabilities=ProfileCapabilities(),
            budget=_STANDARD_BUDGET,
            default_retrieval_strategy=None,
        ),
        PipelineProfile.STRICT_QUALITY: ProfileDefinition(
            profile=PipelineProfile.STRICT_QUALITY,
            public_endpoint="/api/v1/enhanced/query",
            capabilities=ProfileCapabilities(
                route_validation=True,
                retrieval_quality_scoring=True,
                answer_validation=True,
                quality_reporting=True,
            ),
            budget=_STRICT_QUALITY_BUDGET,
            default_retrieval_strategy=None,
        ),
        PipelineProfile.ADVANCED: ProfileDefinition(
            profile=PipelineProfile.ADVANCED,
            public_endpoint="/api/advanced-rag/query",
            capabilities=ProfileCapabilities(
                conversation_context=False,
                query_decomposition=True,
                self_rag=True,
                decomposition_requires_request_opt_in=True,
                self_rag_requires_request_opt_in=True,
            ),
            budget=_ADVANCED_BUDGET,
            default_retrieval_strategy=None,
        ),
    }
)

ENDPOINT_PROFILES: Final[Mapping[str, PipelineProfile]] = MappingProxyType(
    {definition.public_endpoint: profile for profile, definition in PROFILE_DEFINITIONS.items()}
)


def get_profile_definition(profile: PipelineProfile | str) -> ProfileDefinition:
    """Return a profile definition, rejecting unsupported compatibility modes."""

    try:
        normalized_profile = PipelineProfile(profile)
    except ValueError as exc:
        raise ValueError(f"Unsupported pipeline profile: {profile!r}") from exc
    return PROFILE_DEFINITIONS[normalized_profile]


def profile_for_endpoint(endpoint: str) -> PipelineProfile:
    """Return the profile assigned to one of the three public query endpoints."""

    try:
        return ENDPOINT_PROFILES[endpoint]
    except KeyError as exc:
        raise ValueError(f"Unsupported pipeline endpoint: {endpoint!r}") from exc
