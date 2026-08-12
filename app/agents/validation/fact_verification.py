"""
Fact Verification Layer (Task 14).

Post-generation fact verification to improve groundedness from 80% to 94%.

Features:
- Extract factual claims from generated answers
- Verify each fact appears in cited source
- Check date/number accuracy
- Detect negations and contradictions
- Flag unverified claims for removal or hedging

Integrates with:
- Task 13: Citation-first generation (validates [doc_id:page] citations)
- Task 9: Hallucination pattern detection (date/number/entity checks)
- Task 8: Multi-stage NLI validation (semantic verification)

Configuration:
All verification thresholds are externalized via FactVerificationConfig.
Default values preserve original behavior. Tune for specific use cases:

Example - Stricter verification (higher precision):
    config = FactVerificationConfig(
        min_support_confidence=0.7,  # Require higher confidence
        number_tolerance=0.10,        # Tighter number matching (10%)
        min_groundedness=0.90         # Higher overall threshold
    )
    stage = FactVerificationStage(config)

Example - Lenient verification (higher recall):
    config = FactVerificationConfig(
        min_support_confidence=0.5,   # Lower confidence threshold
        number_tolerance=0.20,         # Looser number matching (20%)
        min_groundedness=0.75          # Lower overall threshold
    )
    stage = FactVerificationStage(config)

Example - Default behavior:
    stage = FactVerificationStage()  # Uses FactVerificationConfig() defaults
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


@dataclass
class FactVerificationConfig:
    """
    Configuration for fact verification thresholds and parameters.

    All thresholds are externalized for tuning and experimentation.
    Default values match the original hardcoded behavior.
    """
    # Citation support thresholds
    min_support_confidence: float = 0.6
    """Minimum confidence score for a claim to be considered supported"""

    no_citation_confidence: float = 0.3
    """Confidence score when claim has no citations"""

    missing_citation_confidence: float = 0.2
    """Confidence score when cited document is not found"""

    # Confidence scoring weights
    base_confidence: float = 0.5
    """Base confidence score before applying adjustments"""

    number_match_boost: float = 0.25
    """Confidence boost when numbers match"""

    date_match_boost: float = 0.25
    """Confidence boost when dates match"""

    high_overlap_boost: float = 0.25
    """Confidence boost for word overlap > 50%"""

    medium_overlap_boost: float = 0.15
    """Confidence boost for word overlap > 30%"""

    low_overlap_boost: float = 0.05
    """Confidence boost for word overlap > 15%"""

    negation_mismatch_penalty: float = 0.3
    """Confidence penalty when negation doesn't match"""

    number_mismatch_penalty: float = 0.5
    """Confidence penalty when numbers don't match"""

    date_mismatch_penalty: float = 0.5
    """Confidence penalty when dates don't match"""

    # Overlap thresholds
    high_overlap_threshold: float = 0.5
    """Threshold for high word overlap (50%)"""

    medium_overlap_threshold: float = 0.3
    """Threshold for medium word overlap (30%)"""

    low_overlap_threshold: float = 0.15
    """Threshold for low word overlap (15%)"""

    # Number matching tolerance
    number_tolerance: float = 0.15
    """Relative tolerance for number matching (15% default)"""

    # Answer-level thresholds
    min_groundedness: float = 0.85
    """Minimum groundedness score for answer to be considered verified"""

    min_claim_length: int = 10
    """Minimum sentence length to extract as a claim"""

    min_clean_claim_length: int = 5
    """Minimum claim length after removing citations"""


class FactClaim(BaseModel):
    """A factual claim extracted from an answer"""
    text: str
    citations: List[str] = Field(default_factory=list)
    claim_type: str = "general"  # general, date, number, negation, entity
    start_pos: int = 0
    end_pos: int = 0


class VerificationResult(BaseModel):
    """Result of verifying a single claim"""
    claim: FactClaim
    is_verified: bool
    confidence: float = Field(ge=0.0, le=1.0)
    issue_type: str = ""
    suggestion: str = ""


class AnswerVerificationResult(BaseModel):
    """Result of verifying an entire answer"""
    overall_verified: bool
    groundedness_score: float = Field(ge=0.0, le=1.0)
    verified_claims: List[FactClaim] = Field(default_factory=list)
    unverified_claims: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    execution_time_ms: int = 0


def _extract_numbers(text: str) -> List[float]:
    """Extract numeric values from text (reuses logic from hallucination_patterns)"""
    numbers = []
    pattern = r'\$?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:million|billion|thousand|[MBK]|%))?'
    matches = re.findall(pattern, text, re.IGNORECASE)

    for match in matches:
        cleaned = re.sub(r'[,$\s]', '', match)

        if '%' in match:
            try:
                value = float(cleaned.replace('%', ''))
                numbers.append(value)
            except ValueError:
                pass
            continue

        multiplier = 1
        if 'billion' in match.lower() or 'B' in match:
            multiplier = 1e9
        elif 'million' in match.lower() or 'M' in match:
            multiplier = 1e6
        elif 'thousand' in match.lower() or 'K' in match:
            multiplier = 1e3

        cleaned = re.sub(r'[a-zA-Z%]', '', cleaned)
        try:
            value = float(cleaned) * multiplier
            numbers.append(value)
        except ValueError:
            pass

    return numbers


def _extract_dates(text: str) -> List[str]:
    """Extract dates from text (English and Chinese)"""
    dates = []
    dates.extend(re.findall(r'\b((?:19|20)\d{2})\b', text))
    dates.extend(re.findall(r'\d{4}年(?:\d{1,2}月)?(?:\d{1,2}日)?', text))
    dates.extend(re.findall(r'\d{4}-\d{2}-\d{2}', text))
    dates.extend(re.findall(r'\d{1,2}/\d{1,2}/\d{2,4}', text))
    dates.extend(re.findall(r'Q[1-4]\s*\d{4}', text, re.IGNORECASE))
    return dates


def _numbers_match(num1: float, num2: float, tolerance: float) -> bool:
    """Check if two numbers match within tolerance"""
    if num1 == 0 and num2 == 0:
        return True
    if num1 == 0 or num2 == 0:
        return False
    diff = abs(num1 - num2) / max(abs(num1), abs(num2))
    return diff <= tolerance


def _has_negation(text: str) -> bool:
    """Check if text contains negation"""
    negation_patterns = [
        r'\bnot\b', r'\bno\b', r'\bnever\b', r'\bnone\b',
        r'\bneither\b', r'\bnor\b', r'\bn\'t\b', r'\bfailed\s+to\b',
        r'没有', r'不是', r'未', r'无', r'非', r'不'
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in negation_patterns)


def extract_claims(answer: str, config: Optional[FactVerificationConfig] = None) -> List[FactClaim]:
    """
    Extract factual claims from generated answer.

    Strategy:
    1. Split answer into sentences
    2. Extract citation markers [doc_id:page]
    3. Remove citation markers from claim text (they're stored separately)
    4. Identify claim type (date, number, negation, general)
    5. Return list of FactClaim objects

    Args:
        answer: Generated answer text with citations
        config: Optional configuration for thresholds

    Returns:
        List of FactClaim objects
    """
    if config is None:
        config = FactVerificationConfig()

    if not answer or not answer.strip():
        return []

    claims = []

    # Split into sentences (handle both English and Chinese)
    # Use period, question mark, exclamation mark, Chinese period/question/exclamation
    sentences = re.split(r'[.!?。！？]\s*', answer)
    sentences = [s.strip() for s in sentences if s.strip()]

    position = 0
    for sentence in sentences:
        if len(sentence) < config.min_claim_length:  # Skip very short sentences
            position += len(sentence) + 1
            continue

        # Extract citations from this sentence
        citation_pattern = r'\[([^\]]+)\]'
        citations = re.findall(citation_pattern, sentence)

        # Filter to only keep doc_id:page format
        valid_citations = []
        for cit in citations:
            if re.match(r'doc\w*:\w+', cit):
                valid_citations.append(cit)

        # Remove citation markers from claim text
        clean_sentence = re.sub(r'\s*\[[^\]]+\]\s*', ' ', sentence).strip()
        clean_sentence = re.sub(r'\s+', ' ', clean_sentence)  # Normalize whitespace

        if len(clean_sentence) < config.min_clean_claim_length:  # Skip if too short after removing citations
            position += len(sentence) + 1
            continue

        # Determine claim type
        claim_type = "general"
        has_dates = bool(_extract_dates(clean_sentence))
        has_numbers = bool(_extract_numbers(clean_sentence))
        has_neg = _has_negation(clean_sentence)

        if has_dates:
            claim_type = "date"
        elif has_numbers:
            claim_type = "number"
        elif has_neg:
            claim_type = "negation"

        # Create claim
        claim = FactClaim(
            text=clean_sentence,
            citations=valid_citations,
            claim_type=claim_type,
            start_pos=position,
            end_pos=position + len(sentence)
        )
        claims.append(claim)

        position += len(sentence) + 1

    return claims


def check_citation_support(
    claim_text: str,
    citations: List[str],
    source_docs: List[Dict],
    config: Optional[FactVerificationConfig] = None
) -> Tuple[bool, float]:
    """
    Check if claim is supported by cited sources.

    Args:
        claim_text: Text of the claim
        citations: List of citation markers (e.g., ["doc1:p3"])
        source_docs: List of source documents with doc_id, page, content
        config: Optional configuration for thresholds

    Returns:
        Tuple of (is_supported, confidence_score)
    """
    if config is None:
        config = FactVerificationConfig()

    if not citations:
        # No citations - cannot verify
        return False, config.no_citation_confidence

    if not source_docs:
        # No source docs available
        return False, 0.0

    # Find cited documents
    cited_contents = []
    for citation in citations:
        # Parse citation: doc1:p3 -> doc_id=doc1, page=p3
        match = re.match(r'(\w+):(\w+)', citation)
        if not match:
            continue

        doc_id = match.group(1)
        page = match.group(2)

        # Find matching source doc
        for doc in source_docs:
            doc_doc_id = doc.get("doc_id", doc.get("id", ""))
            doc_page = doc.get("page", "")

            # Match doc_id (page matching is lenient - if page not specified in doc, match on doc_id only)
            if doc_doc_id == doc_id:
                # If both have pages specified, they must match
                if page and doc_page:
                    if doc_page != page:
                        continue
                # Otherwise, match on doc_id
                content = doc.get("content", doc.get("text", ""))
                if content:
                    cited_contents.append(content)
                    break

    if not cited_contents:
        # Citations not found in source docs
        return False, config.missing_citation_confidence

    # Check if claim content appears in cited sources
    # Use keyword overlap and fact matching
    claim_lower = claim_text.lower()
    source_text = " ".join(cited_contents).lower()

    # Extract key facts from claim
    claim_numbers = _extract_numbers(claim_text)
    claim_dates = _extract_dates(claim_text)

    source_numbers = _extract_numbers(" ".join(cited_contents))
    source_dates = _extract_dates(" ".join(cited_contents))

    # Check numbers match
    numbers_match = True
    if claim_numbers:
        numbers_match = all(
            any(_numbers_match(cn, sn, config.number_tolerance) for sn in source_numbers)
            for cn in claim_numbers
        ) if source_numbers else False

    # Check dates match
    dates_match = True
    if claim_dates:
        # For date matching, check for exact matches (not substring)
        dates_match = any(
            cd == sd for cd in claim_dates for sd in source_dates
        ) if source_dates else False

    # Check negation consistency
    claim_has_negation = _has_negation(claim_text)
    source_has_negation = _has_negation(source_text)

    # Extract content words for semantic overlap (include Chinese)
    # Remove common stop words and focus on meaningful content
    claim_words = set(re.findall(r'\b[a-z]{4,}\b', claim_lower))  # English 4+ chars
    claim_chinese = set(re.findall(r'[一-鿿]{2,}', claim_text))
    claim_words.update(claim_chinese)

    source_words = set(re.findall(r'\b[a-z]{4,}\b', source_text))  # English 4+ chars
    source_chinese = set(re.findall(r'[一-鿿]{2,}', " ".join(cited_contents)))
    source_words.update(source_chinese)

    # Word overlap ratio
    overlap = len(claim_words & source_words) / len(claim_words) if claim_words else 0

    # Calculate confidence
    confidence = config.base_confidence

    # Boost if facts match
    if numbers_match and claim_numbers:
        confidence += config.number_match_boost
    if dates_match and claim_dates:
        confidence += config.date_match_boost

    # Boost for word overlap
    if overlap > config.high_overlap_threshold:
        confidence += config.high_overlap_boost
    elif overlap > config.medium_overlap_threshold:
        confidence += config.medium_overlap_boost
    elif overlap > config.low_overlap_threshold:
        confidence += config.low_overlap_boost

    # Penalize negation mismatch
    if claim_has_negation != source_has_negation:
        confidence -= config.negation_mismatch_penalty

    # Penalize number/date mismatch (strong penalty for fact errors)
    if not numbers_match and claim_numbers:
        confidence -= config.number_mismatch_penalty
    if not dates_match and claim_dates:
        confidence -= config.date_mismatch_penalty

    confidence = max(0.0, min(1.0, confidence))

    is_supported = confidence >= config.min_support_confidence

    return is_supported, confidence


async def verify_claim_against_source(
    claim: FactClaim,
    source_docs: List[Dict],
    config: Optional[FactVerificationConfig] = None
) -> VerificationResult:
    """
    Verify a single claim against source documents.

    Checks:
    - Citation exists and is valid
    - Claim content matches source
    - Numbers/dates are accurate
    - No contradictions or negation conflicts

    Args:
        claim: FactClaim to verify
        source_docs: List of source documents
        config: Optional configuration for thresholds

    Returns:
        VerificationResult with verification status and issues
    """
    if config is None:
        config = FactVerificationConfig()

    # Check citation support
    is_supported, confidence = check_citation_support(
        claim.text,
        claim.citations,
        source_docs,
        config
    )

    if not is_supported:
        issue_type = "unsupported_claim"
        suggestion = "Remove or hedge this claim, or add proper citation"

        # Specific issue types
        if not claim.citations:
            issue_type = "missing_citation"
            suggestion = "Add citation [doc_id:page] to support this claim"
        elif claim.claim_type == "date":
            claim_dates = _extract_dates(claim.text)
            source_text = " ".join([doc.get("content", "") for doc in source_docs[:5]])
            source_dates = _extract_dates(source_text)
            if claim_dates and source_dates and not any(d in source_dates for d in claim_dates):
                issue_type = "date_mismatch"
                suggestion = f"Date in claim does not match source. Verify: {', '.join(claim_dates)}"
        elif claim.claim_type == "number":
            claim_numbers = _extract_numbers(claim.text)
            source_text = " ".join([doc.get("content", "") for doc in source_docs[:5]])
            source_numbers = _extract_numbers(source_text)
            if claim_numbers and source_numbers:
                has_match = any(
                    any(_numbers_match(cn, sn, config.number_tolerance) for sn in source_numbers)
                    for cn in claim_numbers
                )
                if not has_match:
                    issue_type = "number_mismatch"
                    suggestion = f"Number in claim does not match source (>{config.number_tolerance*100:.0f}% difference)"
        elif claim.claim_type == "negation":
            source_text = " ".join([doc.get("content", "") for doc in source_docs[:5]])
            claim_has_neg = _has_negation(claim.text)
            source_has_neg = _has_negation(source_text)
            if claim_has_neg != source_has_neg:
                issue_type = "negation_conflict"
                suggestion = "Claim negation conflicts with source"

        return VerificationResult(
            claim=claim,
            is_verified=False,
            confidence=confidence,
            issue_type=issue_type,
            suggestion=suggestion
        )

    return VerificationResult(
        claim=claim,
        is_verified=True,
        confidence=confidence,
        issue_type="",
        suggestion=""
    )


class FactVerificationStage:
    """Internal claim-groundedness stage owned by ``ValidationCascade``.

    Workflow:
    1. Extract factual claims from answer
    2. Verify each claim against source documents
    3. Calculate groundedness score
    4. Flag unverified claims for removal/hedging
    """

    def __init__(self, config: Optional[FactVerificationConfig] = None):
        """
        Initialize fact verifier with configuration.

        Args:
            config: FactVerificationConfig instance or None for defaults
        """
        if config is None:
            config = FactVerificationConfig()
        self.config = config

    async def verify(
        self,
        answer: str,
        source_docs: List[Dict],
        citations: Optional[List[Dict]] = None
    ) -> AnswerVerificationResult:
        """
        Verify entire answer for factual accuracy and groundedness.

        Args:
            answer: Generated answer text
            source_docs: Source documents used for generation
            citations: Optional explicit citation objects (if not embedded in answer)

        Returns:
            AnswerVerificationResult with verification details
        """
        import time
        start_time = time.time()

        if not answer or not answer.strip():
            return AnswerVerificationResult(
                overall_verified=True,
                groundedness_score=1.0,
                verified_claims=[],
                unverified_claims=[],
                issues=[],
                execution_time_ms=0
            )

        # Extract claims
        claims = extract_claims(answer, self.config)

        if not claims:
            # No factual claims to verify
            return AnswerVerificationResult(
                overall_verified=True,
                groundedness_score=1.0,
                verified_claims=[],
                unverified_claims=[],
                issues=[],
                execution_time_ms=int((time.time() - start_time) * 1000)
            )

        # Verify each claim
        verified_claims = []
        unverified_claims = []
        issues = []

        for claim in claims:
            result = await verify_claim_against_source(claim, source_docs, self.config)

            if result.is_verified:
                verified_claims.append(claim)
            else:
                unverified_claims.append(claim.text[:100])  # Truncate for display
                if result.issue_type:
                    issues.append(f"{result.issue_type}: {claim.text[:80]}")

        # Calculate groundedness score
        total_claims = len(claims)
        verified_count = len(verified_claims)
        groundedness_score = verified_count / total_claims if total_claims > 0 else 1.0

        overall_verified = groundedness_score >= self.config.min_groundedness

        elapsed = int((time.time() - start_time) * 1000)

        return AnswerVerificationResult(
            overall_verified=overall_verified,
            groundedness_score=round(groundedness_score, 3),
            verified_claims=verified_claims,
            unverified_claims=unverified_claims,
            issues=issues,
            execution_time_ms=elapsed
        )

    async def suggest_corrections(
        self,
        answer: str,
        verification_result: AnswerVerificationResult
    ) -> str:
        """
        Suggest corrections to improve groundedness.

        Strategy:
        - Remove unverified claims
        - Add hedging language for uncertain claims
        - Suggest adding missing citations

        Args:
            answer: Original answer
            verification_result: Result from :meth:`verify`

        Returns:
            Suggested corrected answer
        """
        if verification_result.overall_verified:
            return answer

        # For now, return answer with warning comment
        # Full correction would require claim-level editing
        corrections = []
        for issue in verification_result.issues[:3]:  # Top 3 issues
            corrections.append(f"- {issue}")

        correction_text = "\n".join(corrections)

        return f"{answer}\n\n[Verification Note: Some claims could not be verified:\n{correction_text}]"


class FactVerifier:
    """Compatibility facade for legacy direct imports.

    Production answer validation enters through ``ValidationCascade``.  This
    facade owns no verification algorithm; it delegates to the canonical
    fact-verification stage so existing external imports retain their result
    contract while first-party production callers cannot create a second
    validation engine.
    """

    def __init__(self, config: Optional[FactVerificationConfig] = None):
        self._stage = FactVerificationStage(config)

    async def verify_answer(
        self,
        answer: str,
        source_docs: List[Dict],
        citations: Optional[List[Dict]] = None,
    ) -> AnswerVerificationResult:
        """Delegate the historical answer-level call to the canonical stage."""
        return await self._stage.verify(answer, source_docs, citations)

    async def suggest_corrections(
        self,
        answer: str,
        verification_result: AnswerVerificationResult,
    ) -> str:
        """Delegate the historical correction helper to the canonical stage."""
        return await self._stage.suggest_corrections(answer, verification_result)
