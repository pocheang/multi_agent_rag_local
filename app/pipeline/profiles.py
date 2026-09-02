"""The pipeline profile enum.

The system runs a single profile.  The capability/budget descriptors that used
to live here -- ``ProfileCapabilities``, ``CapabilityBudget``,
``ProfileDefinition``, ``PROFILE_DEFINITIONS``, ``ENDPOINT_PROFILES`` and
``profile_for_endpoint`` -- were never read by any caller.
``get_profile_definition`` was invoked purely for its side effect of raising on
an unknown profile, which ``PipelineProfile(value)`` already does.

They had also drifted into contradicting the thing that is actually consulted:
``ProfileCapabilities`` declared ``answer_validation=False`` and
``quality_reporting=False`` while ``ExecutionPolicy.for_profile`` hardcodes both
to True.  Decorative configuration that disagrees with real configuration is
worse than none, so it was removed rather than kept in sync.

``ExecutionPolicy`` (app/orchestration/policies.py) is the single source of
truth for what a profile enables.
"""

from __future__ import annotations

from enum import StrEnum


class PipelineProfile(StrEnum):
    """The single supported pipeline profile for the public query API."""

    ADVANCED = "advanced"


__all__ = ["PipelineProfile"]
