"""
Rule-based hallucination pattern detection (Task 9).

Fast pattern matching (<5ms) for common hallucination types:
- Date mismatches
- Number mismatches (>15% tolerance)
- Entity mismatches
- Negation conflicts

Designed to complement NLI validation at cascade Level 1.
"""

import re
from typing import List, Set
from pydantic import BaseModel


class HallucinationPattern(BaseModel):
    """Detected hallucination pattern"""
    pattern_type: str
    severity: str  # "critical", "high", "medium", "low"
    content: str
    suggestion: str


def _extract_dates(text: str) -> Set[str]:
    """
    Extract dates from text (English and Chinese).

    Patterns:
    - 4-digit years: 2020, 2021
    - Chinese dates: 2020年3月15日
    - ISO dates: 2020-03-15
    - US dates: 03/15/2020
    - Quarter dates: Q1 2020

    Returns:
        Set of date strings found in text
    """
    dates = set()

    # 4-digit years (most common)
    dates.update(re.findall(r'\b((?:19|20)\d{2})\b', text))

    # Chinese date patterns
    dates.update(re.findall(r'\d{4}年(?:\d{1,2}月)?(?:\d{1,2}日)?', text))

    # ISO dates: YYYY-MM-DD
    dates.update(re.findall(r'\d{4}-\d{2}-\d{2}', text))

    # US dates: MM/DD/YYYY or M/D/YY
    dates.update(re.findall(r'\d{1,2}/\d{1,2}/\d{2,4}', text))

    # Quarter dates: Q1 2020, Q4 2021
    dates.update(re.findall(r'Q[1-4]\s*\d{4}', text, re.IGNORECASE))

    return dates


def _extract_numbers(text: str) -> List[float]:
    """
    Extract numeric values from text.

    Handles:
    - Plain numbers: 100, 3.14
    - Numbers with commas: 1,000,000
    - Percentages: 25%
    - Currency: $100M, $5B
    - Units: million, billion, thousand

    Returns:
        List of numeric values (normalized)
    """
    numbers = []

    # Match numbers with optional units and currency
    pattern = r'\$?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:million|billion|thousand|[MBK]|%))?'
    matches = re.findall(pattern, text, re.IGNORECASE)

    for match in matches:
        # Clean the match
        cleaned = re.sub(r'[,$\s]', '', match)

        # Handle percentages separately (keep as-is)
        if '%' in match:
            try:
                value = float(cleaned.replace('%', ''))
                numbers.append(value)
            except ValueError:
                pass
            continue

        # Handle unit multipliers
        multiplier = 1
        if 'billion' in match.lower() or 'B' in match:
            multiplier = 1e9
        elif 'million' in match.lower() or 'M' in match:
            multiplier = 1e6
        elif 'thousand' in match.lower() or 'K' in match:
            multiplier = 1e3

        # Remove letters and convert
        cleaned = re.sub(r'[a-zA-Z%]', '', cleaned)
        try:
            value = float(cleaned) * multiplier
            numbers.append(value)
        except ValueError:
            pass

    return numbers


def _extract_entities(text: str) -> Set[str]:
    """
    Extract named entities (proper nouns) from text.

    Patterns:
    - English: Capitalized words (John Smith, Acme Corp)
    - Chinese: 2-4 character sequences (common name length)

    Returns:
        Set of entity strings
    """
    entities = set()

    # English: Capitalized words (single or multi-word)
    entities.update(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text))

    # Chinese: 2-4 character sequences (typical name/entity length)
    # Limit to avoid extracting full phrases
    entities.update(re.findall(r'[一-鿿]{2,4}', text))

    return entities


def _numbers_match(num1: float, num2: float, tolerance: float = 0.15) -> bool:
    """
    Check if two numbers match within tolerance.

    Args:
        num1: First number
        num2: Second number
        tolerance: Allowed relative difference (default 15%)

    Returns:
        True if numbers match within tolerance
    """
    if num1 == 0 and num2 == 0:
        return True
    if num1 == 0 or num2 == 0:
        return False

    relative_diff = abs(num1 - num2) / max(abs(num1), abs(num2))
    return relative_diff <= tolerance


def detect_date_hallucinations(answer: str, source_text: str) -> List[HallucinationPattern]:
    """
    Detect date mismatches between answer and source.

    Args:
        answer: Generated answer text
        source_text: Source document text

    Returns:
        List of detected date hallucination patterns
    """
    if not answer or not source_text:
        return []

    issues = []

    answer_dates = _extract_dates(answer)
    source_dates = _extract_dates(source_text)

    if not answer_dates or not source_dates:
        return []

    # Find dates in answer not present in source
    mismatched_dates = answer_dates - source_dates

    if mismatched_dates:
        issues.append(HallucinationPattern(
            pattern_type="date_mismatch",
            severity="high",
            content=f"Date(s) not in source: {', '.join(sorted(mismatched_dates))}",
            suggestion="Verify dates against source documents"
        ))

    return issues


def detect_number_hallucinations(answer: str, source_text: str) -> List[HallucinationPattern]:
    """
    Detect number mismatches between answer and source.

    Numbers must match within 15% tolerance.

    Args:
        answer: Generated answer text
        source_text: Source document text

    Returns:
        List of detected number hallucination patterns
    """
    if not answer or not source_text:
        return []

    issues = []

    answer_numbers = _extract_numbers(answer)
    source_numbers = _extract_numbers(source_text)

    if not answer_numbers or not source_numbers:
        return []

    # Check each answer number against source numbers
    for ans_num in answer_numbers:
        has_match = any(
            _numbers_match(ans_num, src_num)
            for src_num in source_numbers
        )

        if not has_match:
            # Format number for display
            if ans_num >= 1e9:
                display = f"${ans_num/1e9:.1f}B"
            elif ans_num >= 1e6:
                display = f"${ans_num/1e6:.1f}M"
            elif ans_num >= 1e3:
                display = f"${ans_num/1e3:.1f}K"
            else:
                display = f"{ans_num}"

            issues.append(HallucinationPattern(
                pattern_type="number_mismatch",
                severity="high",
                content=f"Number {display} not found in sources (within 15% tolerance)",
                suggestion="Verify numeric claims against source"
            ))

    return issues


def detect_entity_hallucinations(answer: str, source_text: str) -> List[HallucinationPattern]:
    """
    Detect entity mismatches between answer and source.

    Checks proper nouns (names, organizations) in answer against source.

    Args:
        answer: Generated answer text
        source_text: Source document text

    Returns:
        List of detected entity hallucination patterns
    """
    if not answer or not source_text:
        return []

    issues = []

    answer_entities = _extract_entities(answer)
    source_entities = _extract_entities(source_text)

    if not answer_entities:
        return []

    # Common words to ignore (not real entities)
    common_words = {
        'The', 'A', 'An', 'In', 'On', 'At', 'To', 'For', 'Of', 'With',
        'CEO', 'CFO', 'CTO', 'COO', 'President', 'Director', 'Manager',
        'Company', 'Corporation', 'Inc', 'Ltd', 'LLC'
    }

    # Chinese common titles/roles to ignore
    chinese_common = {
        '首席执行', '执行官', '担任', '公司', '成立', '实现', '年成',
        '月日', '年月', '融资', '美元', '收入', '达到', '增长'
    }

    # Find entities in answer not in source (exact match)
    mismatched = answer_entities - source_entities

    # Filter out common words
    mismatched = {e for e in mismatched if e not in common_words and e not in chinese_common}

    # Check for substring/partial matches in source
    # Chinese entities often appear as substrings (李明 in source, 李明担任 in answer)
    truly_missing = set()
    for entity in mismatched:
        found_in_source = False

        if re.match(r'[一-鿿]+', entity):
            # Chinese entity: check if it appears as substring in source
            # OR if any source entity is a substring of it
            if entity in source_text:
                found_in_source = True
            else:
                # Check if any source entity is a substring of this entity
                # (e.g., "李明" in source, "李明担任" in answer)
                for src_entity in source_entities:
                    if src_entity in entity or entity in src_entity:
                        found_in_source = True
                        break
        else:
            # English entity: check if all words appear in source
            if ' ' in entity:
                # Multi-word: check if all words appear in source
                words = entity.split()
                if not all(word in source_text for word in words):
                    truly_missing.add(entity)
                    continue
                else:
                    found_in_source = True
            else:
                # Single word: check if it appears in source as substring
                if entity not in source_text:
                    truly_missing.add(entity)
                    continue
                else:
                    found_in_source = True

        if not found_in_source:
            truly_missing.add(entity)

    # Focus on likely proper nouns (multi-word names or Chinese person names)
    # For Chinese, focus on 2-char entities (typical person names like 李明, 王伟)
    likely_names = set()
    for e in truly_missing:
        if ' ' in e:
            # Multi-word English names
            likely_names.add(e)
        elif re.match(r'[一-鿿]{2}$', e):
            # Chinese 2-char entities - typical person names
            likely_names.add(e)
        elif re.match(r'[一-鿿]{3,4}$', e):
            # Chinese 3-4 char entities - check if NOT a common phrase
            if e not in chinese_common:
                likely_names.add(e)

    if likely_names:
        issues.append(HallucinationPattern(
            pattern_type="entity_mismatch",
            severity="medium",
            content=f"Entities not in source: {', '.join(sorted(likely_names))}",
            suggestion="Verify entity names against source"
        ))

    return issues


def detect_negation_hallucinations(answer: str, source_text: str) -> List[HallucinationPattern]:
    """
    Detect negation conflicts between answer and source.

    Flags cases where:
    - Answer negates what source affirms
    - Answer affirms what source negates

    Args:
        answer: Generated answer text
        source_text: Source document text

    Returns:
        List of detected negation hallucination patterns
    """
    if not answer or not source_text:
        return []

    issues = []

    # Negation patterns (English and Chinese)
    negation_patterns = [
        r'\bnot\b', r'\bno\b', r'\bnever\b', r'\bnone\b',
        r'\bneither\b', r'\bnor\b', r'\bn\'t\b', r'\bfailed\s+to\b',
        r'没有', r'不是', r'未', r'无', r'非', r'不'
    ]

    # Check for negation in answer
    answer_has_negation = any(
        re.search(pattern, answer, re.IGNORECASE)
        for pattern in negation_patterns
    )

    # Check for negation in source
    source_has_negation = any(
        re.search(pattern, source_text, re.IGNORECASE)
        for pattern in negation_patterns
    )

    # Flag if negation mismatch
    if answer_has_negation != source_has_negation:
        # Extract key content words (non-stop words)
        # English: 3+ chars to catch more words
        answer_words = set(re.findall(r'\b\w{3,}\b', answer.lower()))
        source_words = set(re.findall(r'\b\w{3,}\b', source_text.lower()))

        # Chinese words: 2-4 character sequences (covers more content)
        answer_chinese = set(re.findall(r'[一-鿿]{2,4}', answer))
        source_chinese = set(re.findall(r'[一-鿿]{2,4}', source_text))

        answer_words.update(answer_chinese)
        source_words.update(source_chinese)

        # Check for shared content (exact matches)
        shared_words = answer_words & source_words

        # Also check for word stems (e.g., "profitable" vs "profitability")
        # Simple stemming: check if any answer word is a prefix of source word or vice versa
        stem_matches = 0
        for ans_word in answer_words:
            if len(ans_word) < 4:  # Skip short words
                continue
            for src_word in source_words:
                if len(src_word) < 4:
                    continue
                # Check if one is prefix of the other (min 4 chars)
                if ans_word.startswith(src_word[:4]) or src_word.startswith(ans_word[:4]):
                    stem_matches += 1
                    break

        # If significant overlap, likely discussing same topic with opposite polarity
        # Threshold: at least 1 shared word + 1 stem match, OR 2 shared words, OR 1 Chinese word overlap
        has_chinese_overlap = len(answer_chinese & source_chinese) >= 1
        has_word_overlap = len(shared_words) >= 2 or (len(shared_words) >= 1 and stem_matches >= 1)

        if has_chinese_overlap or has_word_overlap or stem_matches >= 2:
            issues.append(HallucinationPattern(
                pattern_type="negation_conflict",
                severity="high",
                content="Answer negation conflicts with source",
                suggestion="Verify answer doesn't contradict source"
            ))

    return issues


def detect_all_patterns(answer: str, source_text: str) -> List[HallucinationPattern]:
    """
    Run all hallucination pattern detectors.

    Combines:
    - Date validation
    - Number validation
    - Entity validation
    - Negation detection

    Target: <5ms total

    Args:
        answer: Generated answer text
        source_text: Source document text (concatenated from source_docs)

    Returns:
        List of all detected hallucination patterns
    """
    all_issues = []

    # Run all detectors
    all_issues.extend(detect_date_hallucinations(answer, source_text))
    all_issues.extend(detect_number_hallucinations(answer, source_text))
    all_issues.extend(detect_entity_hallucinations(answer, source_text))
    all_issues.extend(detect_negation_hallucinations(answer, source_text))

    return all_issues
