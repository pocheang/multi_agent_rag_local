"""
Synthesis Agent Answer Templates by Query Type

Provides structured templates for different query types to enforce
citation discipline and reduce hallucinations.

Task 13: Citation-first generation templates
"""

from typing import Literal

__all__ = [
    "QUERY_TYPE_CONCEPT",
    "QUERY_TYPE_COMPARISON",
    "QUERY_TYPE_RELATIONSHIP",
    "QUERY_TYPE_PROCEDURAL",
    "QUERY_TYPE_GENERAL",
    "QueryType",
    "CONCEPT_TEMPLATE",
    "COMPARISON_TEMPLATE",
    "RELATIONSHIP_TEMPLATE",
    "PROCEDURAL_TEMPLATE",
    "GENERAL_TEMPLATE",
    "get_answer_template",
    "infer_query_type",
    "COT_REASONING_PROMPT",
    "get_cot_reasoning_prompt",
    "HEDGING_GUIDELINES",
    "get_hedging_guidelines",
]

# Query type constants
QUERY_TYPE_CONCEPT = "concept"
QUERY_TYPE_COMPARISON = "comparison"
QUERY_TYPE_RELATIONSHIP = "relationship"
QUERY_TYPE_PROCEDURAL = "procedural"
QUERY_TYPE_GENERAL = "general"

QueryType = Literal["concept", "comparison", "relationship", "procedural", "general"]


# ============================================================================
# Answer Templates by Query Type
# ============================================================================

CONCEPT_TEMPLATE = """
Answer template for concept explanation:

1. Core definition with citation [E1]
2. Key characteristics (each with citation)
3. Scope and boundaries (cite sources or acknowledge limitation)

Citation rules:
- EVERY factual claim MUST have an evidence-marker citation, e.g. [E1]
- If information is not in context, explicitly state "根据提供的信息" (based on provided information)
- Use hedging language for uncertain or incomplete contexts: "部分应用包括..." (some applications include...)

Example structure:
<concept> 是 <definition> [E1]。它的主要特征包括：<feature1> [E1]，<feature2> [E2]。
"""

COMPARISON_TEMPLATE = """
Answer template for comparison questions:

1. Brief introduction of both subjects with citations
2. Structured comparison table or point-by-point analysis:
   - Dimension 1: Subject A [E1] vs Subject B [E2]
   - Dimension 2: Subject A [E1] vs Subject B [E2]
3. Summary of key differences with citations

Citation rules:
- Each comparison dimension MUST cite sources for BOTH subjects
- If one subject lacks context, explicitly state: "提供的信息中未包含<subject>的<aspect>" (provided information does not include...)
- Avoid subjective preference without citation

Example structure:
对比 <A> 和 <B>：
- 特征维度：<A>使用<method1> [E1]，而<B>采用<method2> [E2]
- 应用场景：<A>适用于<scenario1> [E1]，<B>用于<scenario2> [E3]
"""

RELATIONSHIP_TEMPLATE = """
Answer template for relationship questions (how X relates to Y):

1. Establish context for both entities with citations
2. Direct relationship with citation [E1]
3. Supporting evidence or examples (each cited)
4. Scope limitation if context is incomplete

Citation rules:
- Direct relationship claim MUST have citation
- Supporting examples must cite sources
- If relationship is inferred, use hedging: "根据提供的信息，X和Y可能存在关联" (based on provided information, X and Y may be related)

Example structure:
<X> 与 <Y> 的关系：<X> 是 <Y> 的 <relationship> [E1]。具体表现为：<evidence1> [E1]，<evidence2> [E2]。
"""

PROCEDURAL_TEMPLATE = """
Answer template for procedural/how-to questions:

1. Overview of the process with citation
2. Step-by-step breakdown (each step cited):
   Step 1: <action> [E1]
   Step 2: <action> [E1]
   ...
3. Important notes or prerequisites (cited)

Citation rules:
- Each step MUST have supporting citation
- If steps are missing from context, explicitly state: "提供的信息中包含部分步骤" (provided information contains partial steps)
- Do not fabricate steps not in context

Example structure:
<process> 的步骤：
1. <step1> [E1]
2. <step2> [E1]
3. <step3> [E2]
注意：<prerequisite> [E1]
"""

GENERAL_TEMPLATE = """
Answer template for general questions:

1. Direct answer to the question with citation [E1]
2. Supporting details (each with citation)
3. Context or qualifications if needed (cited)

Citation rules:
- EVERY factual claim MUST have an evidence-marker citation, e.g. [E1]
- No citation = no claim (use hedging or acknowledge limitation)
- For broad questions with narrow context, scope the answer: "根据提供的信息，<scoped_answer>"

Example structure:
<question_restatement>：<answer> [E1]。<detail1> [E1]，<detail2> [E2]。
"""


# ============================================================================
# Template Selection
# ============================================================================


def get_answer_template(query_type: QueryType) -> str:
    """
    Get answer template for specific query type.

    Args:
        query_type: Type of query (concept, comparison, relationship, procedural, general)

    Returns:
        Template string with citation guidelines
    """
    templates = {
        QUERY_TYPE_CONCEPT: CONCEPT_TEMPLATE,
        QUERY_TYPE_COMPARISON: COMPARISON_TEMPLATE,
        QUERY_TYPE_RELATIONSHIP: RELATIONSHIP_TEMPLATE,
        QUERY_TYPE_PROCEDURAL: PROCEDURAL_TEMPLATE,
        QUERY_TYPE_GENERAL: GENERAL_TEMPLATE,
    }
    return templates.get(query_type, GENERAL_TEMPLATE)


def infer_query_type(question: str) -> QueryType:
    """
    Infer query type from question text.

    Args:
        question: User question

    Returns:
        Inferred query type
    """
    question_lower = question.lower()

    # Comparison indicators
    comparison_keywords = [
        "比较",
        "对比",
        "区别",
        "差异",
        "vs",
        "versus",
        "compare",
        "difference between",
        "相比",
        "versus",
        "和...的区别",
    ]
    if any(kw in question_lower for kw in comparison_keywords):
        return QUERY_TYPE_COMPARISON

    # Relationship indicators
    relationship_keywords = [
        "关系",
        "关联",
        "联系",
        "影响",
        "作用",
        "relationship",
        "connection",
        "how does",
        "affect",
        "influence",
        "relate to",
        "与...的关系",
    ]
    if any(kw in question_lower for kw in relationship_keywords):
        return QUERY_TYPE_RELATIONSHIP

    # Procedural indicators
    procedural_keywords = [
        "如何",
        "怎么",
        "怎样",
        "步骤",
        "方法",
        "过程",
        "流程",
        "how to",
        "how do",
        "steps",
        "procedure",
        "process",
        "方式",
    ]
    if any(kw in question_lower for kw in procedural_keywords):
        return QUERY_TYPE_PROCEDURAL

    # Concept indicators (what is, define, explain)
    concept_keywords = [
        "什么是",
        "定义",
        "解释",
        "介绍",
        "含义",
        "what is",
        "what are",
        "define",
        "explain",
        "meaning of",
        "是什么",
    ]
    if any(kw in question_lower for kw in concept_keywords):
        return QUERY_TYPE_CONCEPT

    # Default to general
    return QUERY_TYPE_GENERAL


# ============================================================================
# Chain-of-Thought Reasoning Prompts
# ============================================================================

COT_REASONING_PROMPT = """
Before generating the answer, think through:

1. Query Analysis:
   - What is the user really asking?
   - What type of query is this (concept/comparison/relationship/procedural)?
   - What would be a complete answer?

2. Context Assessment:
   - What factual claims can I make from the provided context?
   - What citations support each claim?
   - What information is missing?

3. Citation Planning:
   - Which evidence marker ([E1], [E2], ...) supports each factual statement?
   - Are there unsupported claims I should remove or hedge?
   - Do I need to acknowledge information gaps?

4. Answer Structure:
   - How should I organize the answer (definition, comparison, steps, etc.)?
   - Where do citations fit naturally?
   - What hedging language is needed for uncertain areas?

Then generate the answer following the template for the query type.
"""


def get_cot_reasoning_prompt() -> str:
    """
    Get chain-of-thought reasoning prompt for synthesis.

    Returns:
        Chain-of-thought reasoning prompt
    """
    return COT_REASONING_PROMPT


# ============================================================================
# Hedging Language Guidelines
# ============================================================================

HEDGING_GUIDELINES = """
Hedging Language Guidelines (for uncertain or incomplete contexts):

Chinese hedging phrases:
- "根据提供的信息" (based on provided information)
- "部分<noun>包括" (some <noun> include)
- "可能" (may/might) - use sparingly and with context
- "一般来说" (generally speaking)
- "在某些情况下" (in some cases)
- "提供的信息中提到" (the provided information mentions)
- "有限的信息显示" (limited information shows)

English hedging phrases:
- "based on the provided information"
- "some examples include"
- "may" or "might" - use sparingly and with context
- "generally"
- "in some cases"
- "according to the available context"
- "limited information suggests"

When to hedge:
- Broad questions with narrow context (e.g., "all applications" when context lists 2)
- Inferences not directly stated in context
- Partial information about a topic
- When connecting information across documents without explicit link

When NOT to hedge:
- Direct facts from context with clear citations
- Well-supported claims with multiple citations
- Don't over-hedge to the point of being unhelpful
"""


def get_hedging_guidelines() -> str:
    """
    Get hedging language guidelines.

    Returns:
        Hedging guidelines string
    """
    return HEDGING_GUIDELINES
