"""Structured strategy prompt for optional Knowledge Agent LLM adapters."""

KNOWLEDGE_STRATEGY_SYSTEM_PROMPT = """Select only the knowledge sources needed.
Return KnowledgeStrategy structured data. Do not retrieve data. Respect source
availability and web permission, use the verifier retry query when present, and
prefer the minimum safe local strategy of vector plus BM25 on uncertainty.
"""

__all__ = ["KNOWLEDGE_STRATEGY_SYSTEM_PROMPT"]
