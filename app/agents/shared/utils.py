"""Canonical shared utility primitives for agent compatibility imports."""

import hashlib
import json
import logging
import re
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class ContextFormatter:
    @staticmethod
    def format_vector_context(results: list[dict[str, Any]], max_preview: int = 200) -> str:
        if not results:
            return ""
        blocks = []
        for item in results:
            metadata = item.get("metadata", {})
            source = str(metadata.get("source", "unknown"))
            text = item.get("text", "")[:max_preview]
            sources = item.get("retrieval_sources", [])
            if not isinstance(sources, list):
                sources = [str(sources)]
            source_text = ",".join(sources) if sources else "unknown"
            blocks.append(f"[SOURCE: {source}]\n[RETRIEVAL: {source_text}]\n{text}")
        return "\n\n".join(blocks)

    @staticmethod
    def format_graph_context(
        entities: list[dict[str, Any]],
        neighbors: list[dict[str, Any]] = None,
        paths: list[dict[str, Any]] = None,
    ) -> str:
        lines = []
        for entity in entities or []:
            name = entity.get("entity", "")
            if not name:
                continue
            lines.append(f"Entity: {name}")
            for relation in entity.get("relations", []):
                if relation.get("other"):
                    lines.append(
                        f"  - {relation.get('relation')} ({relation.get('weight', 0):.2f}) -> {relation.get('other')}"
                    )
        for neighbor in neighbors or []:
            if neighbor.get("entity") and neighbor.get("relation") and neighbor.get("other"):
                lines.append(
                    f"Neighbor: {neighbor['entity']} -[{neighbor['relation']}|{float(neighbor.get('weight', 0)):.2f}]- {neighbor['other']}"
                )
        for path in paths or []:
            if path.get("source") and path.get("middle") and path.get("target"):
                lines.append(
                    f"Path2Hop: {path['source']} -[{path.get('rel1', '')}]- {path['middle']} "
                    f"-[{path.get('rel2', '')}]- {path['target']} | w={float(path.get('weight', 0)):.2f}"
                )
        return "\n".join(lines)

    @staticmethod
    def merge_contexts(*contexts: str, separator: str = "\n\n") -> str:
        return separator.join(context for context in (str(value or "").strip() for value in contexts) if context)

    @staticmethod
    def append_context(existing: str, new: str) -> str:
        existing_text, new_text = str(existing or "").strip(), str(new or "").strip()
        if not existing_text:
            return new_text
        if not new_text:
            return existing_text
        return f"{existing_text}\n\n{new_text}"


class ResultValidator:
    @staticmethod
    def validate_vector_result(result: dict[str, Any]) -> bool:
        return all(key in result for key in ["context", "citations", "retrieved_count"])

    @staticmethod
    def validate_graph_result(result: dict[str, Any]) -> bool:
        return all(key in result for key in ["context", "entities"])

    @staticmethod
    def validate_router_result(result: dict[str, Any]) -> bool:
        return all(key in result for key in ["route", "reason", "skill", "agent_class", "confidence"])

    @staticmethod
    def validate_result_structure(result: Any, required_keys: list[str]) -> bool:
        return isinstance(result, dict) and all(key in result for key in required_keys)


class CacheKeyGenerator:
    @staticmethod
    def generate_key(query: str, **kwargs) -> str:
        return hashlib.sha256(json.dumps({"query": query, **kwargs}, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def generate_router_key(query: str, use_reasoning: bool, agent_class_hint: str | None) -> str:
        return CacheKeyGenerator.generate_key(
            query=query, use_reasoning=use_reasoning, agent_class_hint=agent_class_hint
        )

    @staticmethod
    def generate_vector_key(query: str, allowed_sources: list[str] | None) -> str:
        sources_key = ",".join(sorted(allowed_sources)) if allowed_sources else "all"
        return CacheKeyGenerator.generate_key(query=query, sources=sources_key)


class TextProcessor:
    @staticmethod
    def extract_json(text: str) -> dict[str, Any]:
        text = str(text or "").strip()
        for pattern, group_index in (
            (r"```(?:json)?\s*(\{.*?\})\s*```", 1),
            (r"\{.*\}", 0),
        ):
            match = re.search(pattern, text, flags=re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(group_index))
                except json.JSONDecodeError:
                    pass
        logger.warning("Failed to extract JSON from response")
        return {}

    @staticmethod
    def normalize_string(text: str, lowercase: bool = False) -> str:
        result = re.sub(r"\s+", " ", str(text or "").strip())
        return result.lower() if lowercase else result

    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        text = str(text or "")
        return text if len(text) <= max_length else text[: max_length - len(suffix)] + suffix


class ErrorMessageFormatter:
    @staticmethod
    def format_agent_error(agent_name: str, error: Exception) -> str:
        return f"{agent_name} failed: {type(error).__name__} - {str(error)}"

    @staticmethod
    def format_validation_error(field: str, issue: str) -> str:
        return f"Validation failed for '{field}': {issue}"

    @staticmethod
    def format_timeout_error(agent_name: str, timeout_seconds: int) -> str:
        return f"{agent_name} execution exceeded timeout ({timeout_seconds}s)"


class ListUtils:
    @staticmethod
    def deduplicate(items: list[Any], key_func: Callable | None = None) -> list[Any]:
        seen, result = set(), []
        for item in items:
            key = key_func(item) if key_func else item
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    @staticmethod
    def flatten(nested_list: list[list[Any]]) -> list[Any]:
        return [item for sublist in nested_list for item in sublist]

    @staticmethod
    def chunk_list(items: list[Any], chunk_size: int) -> list[list[Any]]:
        return [items[index : index + chunk_size] for index in range(0, len(items), chunk_size)]


class DictUtils:
    @staticmethod
    def merge_dicts(*dicts: dict[str, Any], deep: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for dictionary in dicts:
            for key, value in (dictionary or {}).items():
                if deep and key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = DictUtils.merge_dicts(result[key], value, deep=True)
                else:
                    result[key] = value
        return result

    @staticmethod
    def filter_none_values(d: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in d.items() if value is not None}

    @staticmethod
    def safe_get(d: dict[str, Any], path: str, default: Any = None) -> Any:
        value = d
        for key in path.split("."):
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value


__all__ = [
    "ContextFormatter",
    "ResultValidator",
    "CacheKeyGenerator",
    "TextProcessor",
    "ErrorMessageFormatter",
    "ListUtils",
    "DictUtils",
]
