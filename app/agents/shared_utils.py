"""
Shared utility functions for all agents.

Provides common functionality to reduce code duplication.
"""

import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ContextFormatter:
    """Format and merge contexts from different sources."""

    @staticmethod
    def format_vector_context(results: List[Dict[str, Any]], max_preview: int = 200) -> str:
        """
        Format vector retrieval results into readable context.

        Args:
            results: List of retrieval results
            max_preview: Maximum characters per chunk

        Returns:
            Formatted context string
        """
        if not results:
            return ""

        context_blocks = []
        for item in results:
            metadata = item.get("metadata", {})
            source = str(metadata.get("source", "unknown"))
            text = item.get("text", "")[:max_preview]

            retrieval_sources = item.get("retrieval_sources", [])
            if not isinstance(retrieval_sources, list):
                retrieval_sources = [str(retrieval_sources)]

            source_str = ",".join(retrieval_sources) if retrieval_sources else "unknown"
            context_blocks.append(f"[SOURCE: {source}]\n[RETRIEVAL: {source_str}]\n{text}")

        return "\n\n".join(context_blocks)

    @staticmethod
    def format_graph_context(
        entities: List[Dict[str, Any]],
        neighbors: List[Dict[str, Any]] = None,
        paths: List[Dict[str, Any]] = None
    ) -> str:
        """
        Format graph query results into readable context.

        Args:
            entities: List of entities with relations
            neighbors: List of neighbor relationships
            paths: List of multi-hop paths

        Returns:
            Formatted context string
        """
        lines = []

        # Format entities
        for entity in entities or []:
            name = entity.get("entity", "")
            if not name:
                continue

            lines.append(f"Entity: {name}")
            for rel in entity.get("relations", []):
                if rel.get("other"):
                    weight = rel.get("weight", 0)
                    lines.append(f"  - {rel.get('relation')} ({weight:.2f}) -> {rel.get('other')}")

        # Format neighbors
        for neighbor in neighbors or []:
            if neighbor.get("entity") and neighbor.get("relation") and neighbor.get("other"):
                weight = float(neighbor.get("weight", 0))
                lines.append(
                    f"Neighbor: {neighbor['entity']} -[{neighbor['relation']}|{weight:.2f}]- {neighbor['other']}"
                )

        # Format paths
        for path in paths or []:
            if path.get("source") and path.get("middle") and path.get("target"):
                weight = float(path.get("weight", 0))
                lines.append(
                    f"Path2Hop: {path['source']} -[{path.get('rel1', '')}]- {path['middle']} "
                    f"-[{path.get('rel2', '')}]- {path['target']} | w={weight:.2f}"
                )

        return "\n".join(lines)

    @staticmethod
    def merge_contexts(*contexts: str, separator: str = "\n\n") -> str:
        """
        Merge multiple context strings.

        Args:
            *contexts: Variable number of context strings
            separator: Separator between contexts

        Returns:
            Merged context string
        """
        valid_contexts = [str(ctx or "").strip() for ctx in contexts]
        valid_contexts = [ctx for ctx in valid_contexts if ctx]
        return separator.join(valid_contexts)

    @staticmethod
    def append_context(existing: str, new: str) -> str:
        """
        Append new context to existing context without leading blank lines.

        Args:
            existing: Existing context
            new: New context to append

        Returns:
            Combined context
        """
        existing_text = str(existing or "").strip()
        new_text = str(new or "").strip()

        if not existing_text:
            return new_text
        if not new_text:
            return existing_text

        return f"{existing_text}\n\n{new_text}"


class ResultValidator:
    """Validate agent results."""

    @staticmethod
    def validate_vector_result(result: Dict[str, Any]) -> bool:
        """
        Validate vector RAG result structure.

        Args:
            result: Vector RAG result

        Returns:
            True if valid, False otherwise
        """
        required_keys = ["context", "citations", "retrieved_count"]
        return all(key in result for key in required_keys)

    @staticmethod
    def validate_graph_result(result: Dict[str, Any]) -> bool:
        """
        Validate graph RAG result structure.

        Args:
            result: Graph RAG result

        Returns:
            True if valid, False otherwise
        """
        required_keys = ["context", "entities"]
        return all(key in result for key in required_keys)

    @staticmethod
    def validate_router_result(result: Dict[str, Any]) -> bool:
        """
        Validate router result structure.

        Args:
            result: Router result

        Returns:
            True if valid, False otherwise
        """
        required_keys = ["route", "reason", "skill", "agent_class", "confidence"]
        return all(key in result for key in required_keys)

    @staticmethod
    def validate_result_structure(result: Any, required_keys: List[str]) -> bool:
        """
        Generic result structure validator.

        Args:
            result: Result to validate
            required_keys: List of required keys

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(result, dict):
            return False
        return all(key in result for key in required_keys)


class CacheKeyGenerator:
    """Generate cache keys for agent results."""

    @staticmethod
    def generate_key(query: str, **kwargs) -> str:
        """
        Generate cache key from query and parameters.

        Args:
            query: User query
            **kwargs: Additional parameters

        Returns:
            Cache key hash
        """
        data = {"query": query, **kwargs}
        # Sort keys for consistent hashing
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    @staticmethod
    def generate_router_key(query: str, use_reasoning: bool, agent_class_hint: Optional[str]) -> str:
        """Generate router-specific cache key."""
        return CacheKeyGenerator.generate_key(
            query=query,
            use_reasoning=use_reasoning,
            agent_class_hint=agent_class_hint
        )

    @staticmethod
    def generate_vector_key(
        query: str,
        retrieval_strategy: Optional[str],
        allowed_sources: Optional[List[str]]
    ) -> str:
        """Generate vector RAG-specific cache key."""
        sources_key = ",".join(sorted(allowed_sources)) if allowed_sources else "all"
        return CacheKeyGenerator.generate_key(
            query=query,
            strategy=retrieval_strategy or "default",
            sources=sources_key
        )


class TextProcessor:
    """Text processing utilities."""

    @staticmethod
    def extract_json(text: str) -> Dict[str, Any]:
        """
        Extract JSON from text (handles markdown code blocks).

        Args:
            text: Text containing JSON

        Returns:
            Extracted JSON dictionary or empty dict
        """
        text = str(text or "").strip()

        # Try markdown code block
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try direct JSON
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to extract JSON from response")
        return {}

    @staticmethod
    def normalize_string(text: str, lowercase: bool = False) -> str:
        """
        Normalize string (trim, collapse whitespace).

        Args:
            text: Input text
            lowercase: Whether to convert to lowercase

        Returns:
            Normalized text
        """
        text = str(text or "").strip()
        text = re.sub(r'\s+', ' ', text)
        return text.lower() if lowercase else text

    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """
        Truncate text to maximum length.

        Args:
            text: Input text
            max_length: Maximum length
            suffix: Suffix to add if truncated

        Returns:
            Truncated text
        """
        text = str(text or "")
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix


class ErrorMessageFormatter:
    """Format error messages for users."""

    @staticmethod
    def format_agent_error(agent_name: str, error: Exception) -> str:
        """
        Format agent error message.

        Args:
            agent_name: Name of the agent
            error: Exception that occurred

        Returns:
            Formatted error message
        """
        error_type = type(error).__name__
        return f"{agent_name} failed: {error_type} - {str(error)}"

    @staticmethod
    def format_validation_error(field: str, issue: str) -> str:
        """
        Format validation error message.

        Args:
            field: Field that failed validation
            issue: Description of the issue

        Returns:
            Formatted error message
        """
        return f"Validation failed for '{field}': {issue}"

    @staticmethod
    def format_timeout_error(agent_name: str, timeout_seconds: int) -> str:
        """
        Format timeout error message.

        Args:
            agent_name: Name of the agent
            timeout_seconds: Timeout duration

        Returns:
            Formatted error message
        """
        return f"{agent_name} execution exceeded timeout ({timeout_seconds}s)"


class ListUtils:
    """List manipulation utilities."""

    @staticmethod
    def deduplicate(items: List[Any], key_func: callable = None) -> List[Any]:
        """
        Deduplicate list while preserving order.

        Args:
            items: List to deduplicate
            key_func: Optional function to extract comparison key

        Returns:
            Deduplicated list
        """
        if not key_func:
            seen = set()
            result = []
            for item in items:
                if item not in seen:
                    seen.add(item)
                    result.append(item)
            return result
        else:
            seen = set()
            result = []
            for item in items:
                key = key_func(item)
                if key not in seen:
                    seen.add(key)
                    result.append(item)
            return result

    @staticmethod
    def flatten(nested_list: List[List[Any]]) -> List[Any]:
        """
        Flatten nested list.

        Args:
            nested_list: Nested list

        Returns:
            Flattened list
        """
        return [item for sublist in nested_list for item in sublist]

    @staticmethod
    def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
        """
        Split list into chunks.

        Args:
            items: List to chunk
            chunk_size: Size of each chunk

        Returns:
            List of chunks
        """
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


class DictUtils:
    """Dictionary manipulation utilities."""

    @staticmethod
    def merge_dicts(*dicts: Dict[str, Any], deep: bool = False) -> Dict[str, Any]:
        """
        Merge multiple dictionaries.

        Args:
            *dicts: Variable number of dictionaries
            deep: Whether to perform deep merge

        Returns:
            Merged dictionary
        """
        if not deep:
            result = {}
            for d in dicts:
                result.update(d or {})
            return result
        else:
            # Deep merge
            result = {}
            for d in dicts:
                for key, value in (d or {}).items():
                    if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                        result[key] = DictUtils.merge_dicts(result[key], value, deep=True)
                    else:
                        result[key] = value
            return result

    @staticmethod
    def filter_none_values(d: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove keys with None values.

        Args:
            d: Dictionary to filter

        Returns:
            Filtered dictionary
        """
        return {k: v for k, v in d.items() if v is not None}

    @staticmethod
    def safe_get(d: Dict[str, Any], path: str, default: Any = None) -> Any:
        """
        Safely get nested dictionary value.

        Args:
            d: Dictionary
            path: Dot-separated path (e.g., "metadata.score")
            default: Default value if not found

        Returns:
            Value at path or default
        """
        keys = path.split(".")
        value = d
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
