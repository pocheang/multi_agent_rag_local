"""
Context management service for multi-turn conversations.

Tracks entities, resolves coreferences, and maintains topic continuity
across conversation turns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

__all__ = [
    "Entity",
    "ConversationContext",
    "ResolvedQuery",
    "EntityExtractor",
    "EntityTracker",
    "CoreferenceResolver",
    "TopicTracker",
    "ContextManagementService",
]


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class Entity:
    """Extracted entity from conversation."""

    text: str  # Entity text
    type: Literal["company", "person", "product", "location", "other"]
    mention_turn: int  # Turn number when mentioned
    confidence: float  # Confidence score (0-1)
    canonical_form: str | None = None  # Standardized form (e.g., "Apple" → "Apple Inc.")


@dataclass
class ConversationContext:
    """Conversation context state."""

    session_id: str
    entities: list[Entity] = field(default_factory=list)
    current_topic: str | None = None
    last_query: str = ""
    turn_count: int = 0


@dataclass
class ResolvedQuery:
    """Query with resolved coreferences."""

    original: str  # Original query
    resolved: str  # Resolved query
    entities_resolved: tuple[str, ...]  # Resolved entity texts
    confidence: float  # Resolution confidence
    needs_clarification: bool = False  # Whether user should clarify
    topic_switch: bool = False  # Whether topic has switched


# ============================================================================
# Entity Extractor
# ============================================================================


class EntityExtractor:
    """Extract entities from queries using rule-based patterns."""

    # Company patterns
    COMPANY_SUFFIXES = frozenset(
        [
            "公司",
            "集团",
            "企业",
            "股份",
            "有限",
            "Corporation",
            "Corp",
            "Inc",
            "Ltd",
            "Limited",
            "LLC",
        ]
    )

    KNOWN_COMPANIES = frozenset(
        [
            # Chinese companies
            "苹果",
            "微软",
            "谷歌",
            "亚马逊",
            "特斯拉",
            "Meta",
            "阿里巴巴",
            "腾讯",
            "百度",
            "字节跳动",
            "华为",
            "小米",
            "比亚迪",
            "宁德时代",
            "美团",
            "京东",
            "拼多多",
            # English companies
            "Apple",
            "Microsoft",
            "Google",
            "Amazon",
            "Tesla",
            "Meta",
            "Alibaba",
            "Tencent",
            "Baidu",
            "ByteDance",
            "Huawei",
            "Xiaomi",
            "BYD",
            "CATL",
            "Meituan",
            "JD",
            "Pinduoduo",
        ]
    )

    # Person patterns
    PERSON_TITLES = frozenset(
        [
            "CEO",
            "总裁",
            "董事长",
            "创始人",
            "CTO",
            "CFO",
            "总经理",
            "主席",
            "先生",
            "女士",
            "总监",
        ]
    )

    KNOWN_PERSONS = frozenset(
        [
            "马斯克",
            "库克",
            "纳德拉",
            "贝索斯",
            "扎克伯格",
            "马云",
            "马化腾",
            "李彦宏",
            "张一鸣",
            "雷军",
            "Musk",
            "Cook",
            "Nadella",
            "Bezos",
            "Zuckerberg",
        ]
    )

    # Product patterns (model numbers)
    PRODUCT_PATTERN = re.compile(r"\b(?:iPhone|iPad|MacBook|Model|GPT|Claude)\s*\d+(?:\s*Pro)?", re.IGNORECASE)

    def extract(self, query: str, turn: int) -> list[Entity]:
        """
        Extract entities from query.

        Args:
            query: User query
            turn: Current turn number

        Returns:
            List of extracted entities
        """
        entities = []

        # Extract companies
        entities.extend(self._extract_companies(query, turn))

        # Extract persons
        entities.extend(self._extract_persons(query, turn))

        # Extract products
        entities.extend(self._extract_products(query, turn))

        # Deduplicate by text
        seen = set()
        unique_entities = []
        for entity in entities:
            if entity.text not in seen:
                seen.add(entity.text)
                unique_entities.append(entity)

        return unique_entities

    def _extract_companies(self, query: str, turn: int) -> list[Entity]:
        """Extract company entities."""
        entities = []

        # Check known companies
        for company in self.KNOWN_COMPANIES:
            if company in query:
                entities.append(
                    Entity(
                        text=company,
                        type="company",
                        mention_turn=turn,
                        confidence=0.95,
                    )
                )

        # Check company suffixes
        for suffix in self.COMPANY_SUFFIXES:
            # Find potential company names before suffix
            pattern = rf"([一-龥a-zA-Z]+){re.escape(suffix)}"
            for match in re.finditer(pattern, query):
                company_name = match.group(1) + suffix
                if company_name not in [e.text for e in entities]:
                    entities.append(
                        Entity(
                            text=company_name,
                            type="company",
                            mention_turn=turn,
                            confidence=0.85,
                        )
                    )

        return entities

    def _extract_persons(self, query: str, turn: int) -> list[Entity]:
        """Extract person entities."""
        entities = []

        # Check known persons
        for person in self.KNOWN_PERSONS:
            if person in query:
                entities.append(
                    Entity(
                        text=person,
                        type="person",
                        mention_turn=turn,
                        confidence=0.95,
                    )
                )

        # Check title + name patterns
        for title in self.PERSON_TITLES:
            # Pattern: title + Chinese name (2-4 chars) or English name
            pattern = rf"{re.escape(title)}[\s ]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?|[一-龥]{{2,4}})"
            for match in re.finditer(pattern, query):
                person_name = match.group(1)
                if person_name not in [e.text for e in entities]:
                    entities.append(
                        Entity(
                            text=person_name,
                            type="person",
                            mention_turn=turn,
                            confidence=0.80,
                        )
                    )

        return entities

    def _extract_products(self, query: str, turn: int) -> list[Entity]:
        """Extract product entities."""
        entities = []

        for match in self.PRODUCT_PATTERN.finditer(query):
            product_name = match.group(0)
            entities.append(
                Entity(
                    text=product_name,
                    type="product",
                    mention_turn=turn,
                    confidence=0.90,
                )
            )

        return entities


# ============================================================================
# Entity Tracker
# ============================================================================


class EntityTracker:
    """Track entities across conversation turns."""

    DECAY_RATE = 0.8  # Weight decay per turn

    def __init__(self):
        self.entities: list[Entity] = []
        self.current_turn = 0

    def add_entities(self, entities: list[Entity]) -> None:
        """Add new entities, updating existing ones."""
        for new_entity in entities:
            # Check if entity already exists
            existing = next((e for e in self.entities if e.text == new_entity.text), None)

            if existing:
                # Update mention turn (refresh)
                existing.mention_turn = new_entity.mention_turn
                existing.confidence = max(existing.confidence, new_entity.confidence)
            else:
                # Add new entity
                self.entities.append(new_entity)

        self.current_turn += 1

    def get_recent_entities(self, n: int = 5, entity_type: str | None = None) -> list[Entity]:
        """
        Get most recent entities with decay weighting.

        Args:
            n: Number of entities to return
            entity_type: Filter by entity type

        Returns:
            List of entities sorted by relevance (decay-weighted)
        """
        filtered = self.entities
        if entity_type:
            filtered = [e for e in filtered if e.type == entity_type]

        # Calculate decay weight
        weighted = [(e, self._calculate_weight(e)) for e in filtered]

        # Sort by weight descending
        weighted.sort(key=lambda x: x[1], reverse=True)

        return [e for e, _ in weighted[:n]]

    def find_most_relevant(self, entity_type: str | None = None) -> Entity | None:
        """Find the most relevant entity (highest decay weight)."""
        recent = self.get_recent_entities(n=1, entity_type=entity_type)
        return recent[0] if recent else None

    def _calculate_weight(self, entity: Entity) -> float:
        """Calculate decay-weighted relevance score."""
        turns_ago = self.current_turn - entity.mention_turn
        decay = self.DECAY_RATE**turns_ago
        return entity.confidence * decay


# ============================================================================
# Coreference Resolver
# ============================================================================


class CoreferenceResolver:
    """Resolve coreferences (pronouns) to entities."""

    # Pronoun patterns
    PRONOUNS_ZH = frozenset(["它", "这", "那", "这个", "那个", "前者", "后者"])
    PRONOUNS_EN = frozenset(["it", "this", "that", "they", "them"])

    # Entity type compatibility with pronouns
    PRONOUN_ENTITY_TYPES = {
        "它": ["company", "product", "other"],
        "it": ["company", "product", "other"],
        "他": ["person"],
        "她": ["person"],
        "he": ["person"],
        "she": ["person"],
        "这": ["company", "product", "person", "other"],
        "那": ["company", "product", "person", "other"],
        "this": ["company", "product", "person", "other"],
        "that": ["company", "product", "person", "other"],
    }

    def resolve(self, query: str, tracker: EntityTracker) -> ResolvedQuery:
        """
        Resolve coreferences in query.

        Args:
            query: Original query
            tracker: Entity tracker with context

        Returns:
            ResolvedQuery with resolved text
        """
        # Detect if query has coreference
        if not self._has_coreference(query):
            return ResolvedQuery(
                original=query,
                resolved=query,
                entities_resolved=(),
                confidence=1.0,
            )

        # Find candidate entities
        candidates = tracker.get_recent_entities(n=3)

        if not candidates:
            # No entities in context
            return ResolvedQuery(
                original=query,
                resolved=query,
                entities_resolved=(),
                confidence=0.0,
                needs_clarification=True,
            )

        # Detect pronouns
        pronouns = self._detect_pronouns(query)

        if not pronouns:
            # No pronouns found (shouldn't happen if _has_coreference returned True)
            return ResolvedQuery(
                original=query,
                resolved=query,
                entities_resolved=(),
                confidence=1.0,
            )

        # Resolve each pronoun
        resolved_text = query
        resolved_entities = []
        total_confidence = 0.0

        for pronoun in pronouns:
            entity, confidence = self._find_best_match(pronoun, candidates)

            if entity and confidence > 0.6:
                # Replace pronoun with entity
                resolved_text = resolved_text.replace(pronoun, entity.text, 1)
                resolved_entities.append(entity.text)
                total_confidence += confidence
            else:
                # Low confidence, mark for clarification
                total_confidence += 0.3

        avg_confidence = total_confidence / len(pronouns) if pronouns else 0.0

        return ResolvedQuery(
            original=query,
            resolved=resolved_text,
            entities_resolved=tuple(resolved_entities),
            confidence=avg_confidence,
            needs_clarification=avg_confidence < 0.6,
        )

    def _has_coreference(self, query: str) -> bool:
        """Check if query contains coreference pronouns."""
        query_lower = query.lower()
        return any(pronoun in query or pronoun in query_lower for pronoun in self.PRONOUNS_ZH | self.PRONOUNS_EN)

    def _detect_pronouns(self, query: str) -> list[str]:
        """Detect pronouns in query."""
        found = []
        query_lower = query.lower()

        for pronoun in self.PRONOUNS_ZH:
            if pronoun in query:
                found.append(pronoun)

        for pronoun in self.PRONOUNS_EN:
            if pronoun in query_lower:
                found.append(pronoun)

        return found

    def _find_best_match(
        self,
        pronoun: str,
        candidates: list[Entity],
    ) -> tuple[Entity | None, float]:
        """Find best entity match for pronoun."""
        # Get compatible entity types for this pronoun
        compatible_types = self.PRONOUN_ENTITY_TYPES.get(pronoun, ["company", "product", "person", "other"])

        # Filter candidates by type
        compatible_candidates = [e for e in candidates if e.type in compatible_types]

        if not compatible_candidates:
            return None, 0.0

        # Return most recent (first in list, already sorted)
        best = compatible_candidates[0]
        confidence = 0.9  # High confidence for most recent

        return best, confidence


# ============================================================================
# Topic Tracker
# ============================================================================


class TopicTracker:
    """Track conversation topic."""

    # Topic keywords
    TOPIC_KEYWORDS = {
        "财务分析": ["营收", "利润", "现金流", "财报", "收入", "revenue", "profit"],
        "市场竞争": ["市场份额", "竞争对手", "市占率", "market share", "competitor"],
        "产品技术": ["产品", "技术", "功能", "创新", "product", "technology", "feature"],
        "公司运营": ["团队", "管理", "战略", "组织", "management", "strategy", "team"],
        "行业趋势": ["趋势", "预测", "发展", "前景", "trend", "forecast", "outlook"],
    }

    def extract_topic(self, query: str, entities: list[Entity]) -> str | None:
        """Extract topic from query and entities."""
        query_lower = query.lower()

        # Score each topic
        scores = {}
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > 0:
                scores[topic] = score

        if not scores:
            return None

        # Return highest scoring topic
        return max(scores.items(), key=lambda x: x[1])[0]

    def is_topic_switch(self, current_topic: str | None, previous_topic: str | None) -> bool:
        """Detect if topic has switched."""
        if not previous_topic:
            return False

        if not current_topic:
            return False

        return current_topic != previous_topic


# ============================================================================
# Main Service
# ============================================================================


class ContextManagementService:
    """Main service for context management."""

    def __init__(self):
        self.extractor = EntityExtractor()
        self.resolver = CoreferenceResolver()
        self.topic_tracker = TopicTracker()
        self.contexts: dict[str, tuple[ConversationContext, EntityTracker]] = {}

    def process_query(
        self,
        query: str,
        session_id: str,
    ) -> ResolvedQuery:
        """
        Process query with context management.

        Args:
            query: User query
            session_id: Session identifier

        Returns:
            ResolvedQuery with resolution result
        """
        # Get or create context
        if session_id not in self.contexts:
            context = ConversationContext(session_id=session_id)
            tracker = EntityTracker()
            self.contexts[session_id] = (context, tracker)
        else:
            context, tracker = self.contexts[session_id]

        # Extract entities from current query
        entities = self.extractor.extract(query, context.turn_count)

        # Add entities to tracker
        tracker.add_entities(entities)

        # Resolve coreferences
        resolved = self.resolver.resolve(query, tracker)

        # Extract topic from resolved query
        current_topic = self.topic_tracker.extract_topic(resolved.resolved, entities)

        # Detect topic switch
        topic_switch = False
        if context.current_topic and current_topic:
            topic_switch = self.topic_tracker.is_topic_switch(
                context.current_topic,
                current_topic,
            )

        # Update context
        context.entities.extend(entities)
        if current_topic:
            context.current_topic = current_topic
        context.last_query = query
        context.turn_count += 1

        # Return resolved query with topic_switch
        return ResolvedQuery(
            original=resolved.original,
            resolved=resolved.resolved,
            entities_resolved=resolved.entities_resolved,
            confidence=resolved.confidence,
            needs_clarification=resolved.needs_clarification,
            topic_switch=topic_switch,
        )

    def clear_context(self, session_id: str) -> None:
        """Clear context for session."""
        if session_id in self.contexts:
            del self.contexts[session_id]

    def get_context(self, session_id: str) -> ConversationContext | None:
        """Get current context for session."""
        if session_id in self.contexts:
            return self.contexts[session_id][0]
        return None


# ============================================================================
# Singleton Instance
# ============================================================================

_context_service_instance: ContextManagementService | None = None


def get_context_service() -> ContextManagementService:
    """
    Get singleton instance of ContextManagementService.

    Returns:
        Singleton service instance
    """
    global _context_service_instance
    if _context_service_instance is None:
        _context_service_instance = ContextManagementService()
    return _context_service_instance
