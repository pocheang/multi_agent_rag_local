"""
Few-shot examples for router agent prompt engineering.

Provides curated examples of routing decisions across different query types
to improve LLM routing accuracy through in-context learning.
"""
from typing import List, Dict, Any

# Vector RAG examples - concept queries, definitions, facts
EXAMPLE_VECTOR_QUERIES = [
    {
        "query": "What is machine learning?",
        "route": "vector",
        "reason": "Concept definition query best answered from document text",
        "confidence": 0.95
    },
    {
        "query": "Explain the transformer architecture",
        "route": "vector",
        "reason": "Technical explanation requiring detailed text from papers/docs",
        "confidence": 0.92
    },
    {
        "query": "What are the benefits of cloud computing?",
        "route": "vector",
        "reason": "Factual information query, needs comprehensive text retrieval",
        "confidence": 0.90
    },
    {
        "query": "How does gradient descent work?",
        "route": "vector",
        "reason": "Algorithm explanation, best from educational content",
        "confidence": 0.93
    },
    {
        "query": "什么是深度学习？",  # What is deep learning?
        "route": "vector",
        "reason": "Chinese concept definition, semantic search in documents",
        "confidence": 0.94
    },
]

# Graph RAG examples - relationship queries, entity connections
EXAMPLE_GRAPH_QUERIES = [
    {
        "query": "Who reports to the CTO?",
        "route": "graph",
        "reason": "Org chart relationship query, needs knowledge graph traversal",
        "confidence": 0.96
    },
    {
        "query": "What projects is Alice working on?",
        "route": "graph",
        "reason": "Person-project relationship, graph entity connections",
        "confidence": 0.94
    },
    {
        "query": "Show me the connection between OpenAI and Anthropic",
        "route": "graph",
        "reason": "Entity relationship query, multi-hop reasoning in graph",
        "confidence": 0.91
    },
    {
        "query": "Which teams depend on the authentication service?",
        "route": "graph",
        "reason": "Dependency relationship query, graph traversal needed",
        "confidence": 0.93
    },
    {
        "query": "张三的直接下属有哪些？",  # Who are Zhang San's direct reports?
        "route": "graph",
        "reason": "Chinese org structure query, relationship traversal",
        "confidence": 0.95
    },
]

# Hybrid examples - queries needing both text and graph
EXAMPLE_HYBRID_QUERIES = [
    {
        "query": "Compare Python and Java for machine learning",
        "route": "hybrid",
        "reason": "Comparison needs concept understanding (vector) AND feature comparison (structured)",
        "confidence": 0.88
    },
    {
        "query": "What are the technical skills of team members in the AI department?",
        "route": "hybrid",
        "reason": "Combines org structure (graph) with skill descriptions (vector)",
        "confidence": 0.87
    },
    {
        "query": "How do microservices relate to our current architecture?",
        "route": "hybrid",
        "reason": "Concept explanation (vector) + architecture dependencies (graph)",
        "confidence": 0.86
    },
]

# ReAct examples - complex multi-step reasoning
EXAMPLE_REACT_QUERIES = [
    {
        "query": "Find all Python experts, check their current projects, and recommend who should lead the new ML initiative",
        "route": "react",
        "reason": "Multi-step task: search experts, analyze projects, make recommendation",
        "confidence": 0.89
    },
    {
        "query": "Compare the performance of different database solutions and suggest the best one for our use case",
        "route": "react",
        "reason": "Requires research, comparison, and contextual reasoning",
        "confidence": 0.85
    },
    {
        "query": "Analyze recent security incidents, identify common attack patterns, then recommend preventive measures",
        "route": "react",
        "reason": "Sequential investigation: retrieve incidents, analyze patterns, synthesize recommendations",
        "confidence": 0.87
    },
]


def get_few_shot_examples_by_route(route_type: str, count: int = 5) -> List[Dict[str, Any]]:
    """
    Get few-shot examples for a specific route type.

    Args:
        route_type: One of "vector", "graph", "hybrid", "react"
        count: Number of examples to return (default 5, max available)

    Returns:
        List of example dictionaries with query, route, reason, confidence
    """
    examples_map = {
        "vector": EXAMPLE_VECTOR_QUERIES,
        "graph": EXAMPLE_GRAPH_QUERIES,
        "hybrid": EXAMPLE_HYBRID_QUERIES,
        "react": EXAMPLE_REACT_QUERIES,
    }

    examples = examples_map.get(route_type, [])
    return examples[:count]


def format_examples_for_prompt(examples: List[Dict[str, Any]]) -> str:
    """
    Format few-shot examples for inclusion in LLM prompt.

    Args:
        examples: List of example dictionaries

    Returns:
        Formatted string for prompt injection
    """
    formatted_lines = ["Examples of correct routing decisions:\n"]

    for i, ex in enumerate(examples, 1):
        formatted_lines.append(f"\nExample {i}:")
        formatted_lines.append(f"Query: \"{ex['query']}\"")
        formatted_lines.append(f"Route: {ex['route']}")
        formatted_lines.append(f"Reason: {ex['reason']}")
        formatted_lines.append(f"Confidence: {ex['confidence']}")

    return "\n".join(formatted_lines)


def get_mixed_examples(vector_count: int = 2, graph_count: int = 2,
                       hybrid_count: int = 1, react_count: int = 1) -> str:
    """
    Get a balanced mix of examples across all route types.

    Args:
        vector_count: Number of vector examples
        graph_count: Number of graph examples
        hybrid_count: Number of hybrid examples
        react_count: Number of react examples

    Returns:
        Formatted prompt string with mixed examples
    """
    all_examples = []
    all_examples.extend(get_few_shot_examples_by_route("vector", vector_count))
    all_examples.extend(get_few_shot_examples_by_route("graph", graph_count))
    all_examples.extend(get_few_shot_examples_by_route("hybrid", hybrid_count))
    all_examples.extend(get_few_shot_examples_by_route("react", react_count))

    return format_examples_for_prompt(all_examples)
