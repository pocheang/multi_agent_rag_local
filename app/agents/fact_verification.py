"""Compatibility re-export for app.agents.validation.fact_verification; implementation lives in the canonical package."""

from app.agents.validation.fact_verification import (
    AnswerVerificationResult,
    FactClaim,
    FactVerificationConfig,
    FactVerifier,
    VerificationResult,
    check_citation_support,
    extract_claims,
    verify_claim_against_source,
)

__all__ = [
    "FactVerificationConfig",
    "FactClaim",
    "VerificationResult",
    "AnswerVerificationResult",
    "extract_claims",
    "check_citation_support",
    "verify_claim_against_source",
    "FactVerifier",
]
