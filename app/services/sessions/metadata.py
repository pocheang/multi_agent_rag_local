"""
Session metadata management service.

Provides rich metadata for sessions including tags, categories, descriptions,
and automatic tag extraction from conversation content.

Enhanced features:
- LRU cache with configurable capacity (default 1000 sessions)
- Input validation for tags and descriptions
- Tag format validation (alphanumeric, underscore, hyphen only)
- Tag normalization (lowercase, trim, deduplicate)
"""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

__all__ = [
    "SessionMetadata",
    "SessionCategory",
    "MetadataUpdate",
    "TagExtractor",
    "SessionMetadataService",
    "get_metadata_service",
]


# ============================================================================
# Constants
# ============================================================================

MAX_SESSIONS = 1000  # LRU cache limit
MAX_TAG_LENGTH = 50
MAX_DESCRIPTION_LENGTH = 500
MAX_TAGS_PER_SESSION = 10

# Valid tag pattern: alphanumeric, underscore, hyphen, no spaces
TAG_PATTERN = re.compile(r"^[\w-]+$", re.UNICODE)


def normalize_tags(tags: list[str]) -> list[str]:
    if len(tags) > MAX_TAGS_PER_SESSION:
        raise ValueError(f"Too many tags (max {MAX_TAGS_PER_SESSION})")
    normalized_tags: list[str] = []
    for tag in tags:
        normalized = str(tag or "").lower().strip()
        if not normalized:
            raise ValueError("Invalid tag: Tag cannot be empty")
        if len(normalized) > MAX_TAG_LENGTH:
            raise ValueError(f"Invalid tag '{tag}': Tag exceeds maximum length of {MAX_TAG_LENGTH}")
        if not TAG_PATTERN.fullmatch(normalized):
            raise ValueError(f"Invalid tag '{tag}': Tag can only contain letters, numbers, underscores, and hyphens")
        if normalized not in normalized_tags:
            normalized_tags.append(normalized)
    return normalized_tags


def normalize_description(description: str | None) -> str | None:
    if description is None:
        return None
    normalized = str(description).strip()
    if len(normalized) > MAX_DESCRIPTION_LENGTH:
        raise ValueError(f"Description exceeds maximum length of {MAX_DESCRIPTION_LENGTH}")
    return normalized or None


# ============================================================================
# Type Definitions
# ============================================================================

SessionCategory = Literal[
    "work",
    "personal",
    "research",
    "learning",
    "development",
    "analysis",
    "other",
]


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class SessionMetadata:
    """Session metadata model."""

    session_id: str
    tags: list[str] = field(default_factory=list)  # User-defined tags
    category: SessionCategory | None = None
    description: str | None = None
    auto_tags: list[str] = field(default_factory=list)  # Auto-extracted tags
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    query_count: int = 0
    last_query_at: datetime | None = None


@dataclass
class MetadataUpdate:
    """Metadata update request."""

    tags: list[str] | None = None
    category: SessionCategory | None = None
    description: str | None = None
    increment_query_count: bool = False


# ============================================================================
# Tag Extraction
# ============================================================================


class TagExtractor:
    """Extract tags from conversation content."""

    # Common stop words to filter out
    STOP_WORDS_EN = frozenset(
        [
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "up",
            "about",
            "into",
            "through",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "should",
            "could",
            "can",
            "may",
            "might",
            "must",
            "shall",
            "this",
            "that",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "what",
            "which",
            "who",
            "when",
            "where",
            "why",
            "how",
            "all",
            "each",
            "every",
            "both",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "please",
            "help",
            "need",
            "want",
        ]
    )

    STOP_WORDS_ZH = frozenset(
        [
            "的",
            "了",
            "在",
            "是",
            "我",
            "有",
            "和",
            "就",
            "不",
            "人",
            "都",
            "一",
            "个",
            "上",
            "也",
            "很",
            "到",
            "说",
            "要",
            "去",
            "你",
            "会",
            "着",
            "没",
            "看",
            "好",
            "自己",
            "这",
            "那",
            "能",
            "而",
            "可以",
            "什么",
            "怎么",
            "为什么",
            "如何",
            "请",
            "帮",
            "帮我",
            "想",
            "需要",
            "可以",
        ]
    )

    # Domain keywords (technology, business, etc.)
    DOMAIN_KEYWORDS = {
        # Technology
        "技术": [
            "AI",
            "机器学习",
            "深度学习",
            "算法",
            "代码",
            "编程",
            "开发",
            "API",
            "数据库",
            "云计算",
            "前端",
            "后端",
            "架构",
        ],
        "technology": [
            "AI",
            "machine learning",
            "deep learning",
            "algorithm",
            "code",
            "programming",
            "development",
            "API",
            "database",
            "cloud",
            "frontend",
            "backend",
            "architecture",
        ],
        # Business
        "商业": ["产品", "市场", "营销", "销售", "战略", "运营", "管理", "财务"],
        "business": ["product", "market", "marketing", "sales", "strategy", "operations", "management", "finance"],
        # Research
        "研究": ["论文", "研究", "实验", "分析", "数据", "模型", "假设", "结论"],
        "research": ["paper", "research", "experiment", "analysis", "data", "model", "hypothesis", "conclusion"],
    }

    def extract_keywords(self, text: str, max_keywords: int = 10) -> list[str]:
        """
        Extract keywords from text using frequency analysis.

        Args:
            text: Input text
            max_keywords: Maximum keywords to extract

        Returns:
            List of keywords
        """
        # Tokenize
        tokens = re.findall(r"\b[\w一-鿿]+\b", text.lower())

        # Filter stop words
        filtered = [t for t in tokens if t not in self.STOP_WORDS_EN and t not in self.STOP_WORDS_ZH and len(t) > 1]

        # Count frequencies
        freq: dict[str, int] = {}
        for token in filtered:
            freq[token] = freq.get(token, 0) + 1

        # Sort by frequency
        sorted_keywords = sorted(freq.items(), key=lambda x: x[1], reverse=True)

        # Return top N
        return [kw for kw, _ in sorted_keywords[:max_keywords]]

    def extract_domain_tags(self, text: str) -> list[str]:
        """
        Extract domain-specific tags from text.

        Args:
            text: Input text

        Returns:
            List of domain tags
        """
        text_lower = text.lower()
        tags = []

        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    # Add the domain category
                    domain_name = domain.split()[0] if " " not in domain else domain
                    if domain_name not in tags:
                        tags.append(domain_name)
                    break  # Found one keyword in this domain

        return tags

    def extract_tags(
        self,
        messages: list[dict[str, str]],
        max_tags: int = 5,
    ) -> list[str]:
        """
        Extract tags from conversation messages.

        Args:
            messages: List of message dicts with 'content' field
            max_tags: Maximum tags to extract

        Returns:
            List of extracted tags
        """
        if not messages:
            return []

        # Use recent messages (last 10)
        recent_messages = messages[-10:]

        # Combine content
        combined_text = " ".join(msg.get("content", "") for msg in recent_messages)

        if not combined_text.strip():
            return []

        # Extract domain tags first
        domain_tags = self.extract_domain_tags(combined_text)

        # Extract keywords
        keywords = self.extract_keywords(combined_text, max_keywords=10)

        # Combine and deduplicate
        all_tags = domain_tags + keywords
        seen = set()
        unique_tags = []
        for tag in all_tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)

        return unique_tags[:max_tags]


# ============================================================================
# Session Metadata Service
# ============================================================================


class SessionMetadataService:
    """
    Service for managing session metadata with validation and LRU cache.

    Features:
    - LRU cache with configurable capacity (default 1000)
    - Input validation for tags and descriptions
    - Tag normalization (lowercase, trim, deduplicate)
    - Automatic tag extraction from conversations
    """

    def __init__(self, max_sessions: int = MAX_SESSIONS):
        self.tag_extractor = TagExtractor()
        self._sessions: OrderedDict[str, SessionMetadata] = OrderedDict()
        self._max_sessions = max_sessions

    def _validate_tag(self, tag: str) -> tuple[bool, str | None]:
        """
        Validate a single tag.

        Args:
            tag: Tag to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not tag:
            return False, "Tag cannot be empty"

        if len(tag) > MAX_TAG_LENGTH:
            return False, f"Tag exceeds maximum length of {MAX_TAG_LENGTH}"

        if not TAG_PATTERN.match(tag):
            return False, "Tag can only contain letters, numbers, underscores, and hyphens"

        return True, None

    def _validate_tags(self, tags: list[str]) -> list[str]:
        """
        Validate and normalize tags.

        Args:
            tags: List of tags to validate

        Returns:
            Normalized tags (lowercase, deduplicated)

        Raises:
            ValueError: If validation fails
        """
        return normalize_tags(tags)

    def _validate_description(self, description: str | None) -> str | None:
        """
        Validate description.

        Args:
            description: Description to validate

        Returns:
            Validated description (trimmed) or None

        Raises:
            ValueError: If description is too long
        """
        return normalize_description(description)

    def _evict_oldest_if_needed(self) -> None:
        """Evict oldest session if at capacity (LRU)."""
        if len(self._sessions) >= self._max_sessions:
            evicted_id, _ = self._sessions.popitem(last=False)  # Remove oldest
            print(f"[SessionMetadata] LRU evicted session: {evicted_id}")

    def create_metadata(
        self,
        session_id: str,
        tags: list[str] | None = None,
        category: SessionCategory | None = None,
        description: str | None = None,
    ) -> SessionMetadata:
        """
        Create new session metadata with validation.

        Args:
            session_id: Unique session identifier
            tags: User-defined tags (validated and normalized)
            category: Session category
            description: Session description (max 500 chars)

        Returns:
            Created metadata

        Raises:
            ValueError: If metadata already exists or validation fails
        """
        if session_id in self._sessions:
            raise ValueError(f"Metadata already exists for session {session_id}")

        # Validate inputs
        validated_tags = self._validate_tags(tags or [])
        validated_description = self._validate_description(description)

        # Evict oldest if at capacity
        self._evict_oldest_if_needed()

        metadata = SessionMetadata(
            session_id=session_id,
            tags=validated_tags,
            category=category,
            description=validated_description,
        )

        self._sessions[session_id] = metadata
        return metadata

    def get_metadata(self, session_id: str) -> SessionMetadata | None:
        """
        Get metadata for a session.

        Args:
            session_id: Session identifier

        Returns:
            SessionMetadata or None if not found
        """
        metadata = self._sessions.get(session_id)
        if metadata:
            # Move to end for LRU
            self._sessions.move_to_end(session_id)
        return metadata

    def update_metadata(
        self,
        session_id: str,
        update: MetadataUpdate,
    ) -> SessionMetadata:
        """
        Update existing session metadata with validation.

        Args:
            session_id: Session to update
            update: Update specification

        Returns:
            Updated metadata

        Raises:
            KeyError: If session not found
            ValueError: If validation fails
        """
        metadata = self._sessions[session_id]

        # Validate inputs if provided
        if update.tags is not None:
            validated_tags = self._validate_tags(update.tags)
            metadata.tags = validated_tags

        if update.category is not None:
            metadata.category = update.category

        if update.description is not None:
            validated_description = self._validate_description(update.description)
            metadata.description = validated_description

        if update.increment_query_count:
            metadata.query_count += 1
            metadata.last_query_at = datetime.utcnow()

        metadata.updated_at = datetime.utcnow()

        # Move to end for LRU
        self._sessions.move_to_end(session_id)

        return metadata

    def delete_metadata(self, session_id: str) -> bool:
        """
        Delete session metadata.

        Args:
            session_id: Session to delete

        Returns:
            True if deleted, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_all(self) -> list[SessionMetadata]:
        """
        List all session metadata.

        Returns:
            List of all metadata (most recently used first)
        """
        return list(reversed(self._sessions.values()))

    def list_all_metadata(self) -> list[SessionMetadata]:
        """
        List all session metadata (alias for list_all).

        Returns:
            List of all metadata (most recently used first)
        """
        return self.list_all()

    def extract_and_update_auto_tags(
        self,
        session_id: str,
        messages: list[dict],
        max_tags: int = 5,
    ) -> list[str]:
        """
        Extract automatic tags from messages and update metadata.

        Args:
            session_id: Session to update
            messages: Conversation messages
            max_tags: Maximum tags to extract

        Returns:
            List of extracted tags

        Raises:
            KeyError: If session not found
        """
        metadata = self._sessions[session_id]

        # Extract tags
        auto_tags = self.tag_extractor.extract_tags(messages, max_tags=max_tags)

        # Update metadata
        metadata.auto_tags = auto_tags
        metadata.updated_at = datetime.utcnow()

        return auto_tags

    def get_all_tags(self) -> list[str]:
        """
        Get all unique tags across all sessions.

        Returns:
            Sorted list of unique tags
        """
        all_tags = set()
        for metadata in self._sessions.values():
            all_tags.update(metadata.tags)
            all_tags.update(metadata.auto_tags)

        return sorted(all_tags)

    def get_stats(self) -> dict:
        """
        Get service statistics.

        Returns:
            Dictionary with stats:
            - total_sessions: number of sessions in cache
            - max_capacity: maximum capacity
            - total_tags: number of unique tags
            - utilization: percentage of capacity used
        """
        return {
            "total_sessions": len(self._sessions),
            "max_capacity": self._max_sessions,
            "total_tags": len(self.get_all_tags()),
            "utilization": len(self._sessions) / self._max_sessions if self._max_sessions > 0 else 0,
        }


# ============================================================================
# Singleton Instance
# ============================================================================

_metadata_service_instance: SessionMetadataService | None = None


def get_metadata_service() -> SessionMetadataService:
    """
    Get singleton instance of SessionMetadataService.

    Returns:
        Singleton service instance
    """
    global _metadata_service_instance
    if _metadata_service_instance is None:
        _metadata_service_instance = SessionMetadataService()
    return _metadata_service_instance
