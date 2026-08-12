"""
Query decomposition service for breaking down complex queries.
"""

import logging
import re

from app.domain.advanced_rag import DecomposedQuery
from app.prompts import QUERY_DECOMPOSITION_PROMPT

logger = logging.getLogger(__name__)


class QueryDecomposer:
    """Service for decomposing complex queries into simpler sub-queries."""

    def __init__(self, llm_client):
        """
        Initialize query decomposer.

        Args:
            llm_client: LLM client for query decomposition
        """
        self.llm = llm_client
        self.decomposition_prompt = self._load_prompt()
        self.max_sub_queries = 4

    def _load_prompt(self) -> str:
        """Load decomposition prompt template."""
        return QUERY_DECOMPOSITION_PROMPT

    async def decompose(self, query: str) -> DecomposedQuery:
        """
        Decompose complex query into sub-queries.

        Args:
            query: User query to decompose

        Returns:
            DecomposedQuery with original query, sub-queries, and strategy
        """
        # Check if query needs decomposition
        if not self._needs_decomposition(query):
            logger.info(f"Query does not need decomposition: {query}")
            return DecomposedQuery(original_query=query, sub_queries=[query], decomposition_strategy="none")

        # Detect decomposition strategy
        strategy = self._detect_strategy(query)
        logger.info(f"Detected strategy: {strategy} for query: {query}")

        # Decompose using LLM
        sub_queries = await self._decompose_with_llm(query, strategy)

        return DecomposedQuery(original_query=query, sub_queries=sub_queries, decomposition_strategy=strategy)

    def _needs_decomposition(self, query: str) -> bool:
        """
        Check if query is complex enough to benefit from decomposition.

        Args:
            query: User query

        Returns:
            True if query should be decomposed
        """
        indicators = [
            # Comparison indicators
            ("和" in query or "与" in query)
            and any(word in query for word in ["区别", "对比", "比较", "difference", "compare"]),
            # Multiple aspects
            any(word in query for word in ["以及", "还有", "另外", "and also", "as well as"]),
            # Long query
            len(query) > 50,
            # Multiple questions
            query.count("?") > 1 or query.count("？") > 1,
            # Sequential indicators
            any(word in query for word in ["步骤", "如何", "怎么", "流程", "how to", "steps", "process"])
            and len(query) > 30,
        ]
        return any(indicators)

    def _detect_strategy(self, query: str) -> str:
        """
        Detect decomposition strategy based on query type.

        Args:
            query: User query

        Returns:
            Strategy name: comparison, sequential, parallel, or general
        """
        # Comparison queries
        if any(word in query for word in ["区别", "对比", "比较", "difference", "compare", "versus", "vs"]):
            return "comparison"

        # Sequential queries
        if any(word in query for word in ["步骤", "如何", "怎么", "流程", "how to", "steps", "process"]):
            return "sequential"

        # Parallel queries (multiple aspects)
        if any(word in query for word in ["和", "与", "以及", "还有", "另外", "and", "also", "as well as"]):
            return "parallel"

        return "general"

    async def _decompose_with_llm(self, query: str, strategy: str) -> list[str]:
        """
        Use LLM to decompose query into sub-queries.

        Args:
            query: User query
            strategy: Decomposition strategy

        Returns:
            List of sub-queries
        """
        prompt = self.decomposition_prompt.format(query=query, strategy=strategy)

        try:
            response = await self.llm.generate(prompt=prompt, max_tokens=300, temperature=0.3)

            # Parse sub-queries from response
            sub_queries = self._parse_sub_queries(response)

            # Limit to max sub-queries
            sub_queries = sub_queries[: self.max_sub_queries]

            # If parsing failed or no sub-queries, return original query
            if not sub_queries:
                logger.warning(f"Failed to parse sub-queries from LLM response: {response}")
                return [query]

            logger.info(f"Decomposed into {len(sub_queries)} sub-queries: {sub_queries}")
            return sub_queries

        except Exception as e:
            logger.error(f"Error decomposing query: {e}")
            return [query]

    def _parse_sub_queries(self, response: str) -> list[str]:
        """
        Parse sub-queries from LLM response.

        Args:
            response: LLM response text

        Returns:
            List of parsed sub-queries
        """
        lines = response.strip().split("\n")
        sub_queries = []

        for line in lines:
            # Remove numbering (1., 2), 1:, etc.)
            line = re.sub(r"^\d+[\.\)\:]\s*", "", line).strip()
            # Remove bullet points
            line = re.sub(r"^[-\*]\s*", "", line).strip()

            # Skip empty lines and very short lines
            if line and len(line) > 5:
                sub_queries.append(line)

        return sub_queries
