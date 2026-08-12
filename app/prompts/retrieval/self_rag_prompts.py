"""
Self-RAG评估提示词 (Self-RAG Evaluation Prompts)

Self-RAG (Self-Reflective Retrieval-Augmented Generation)：
通过自我评估来提升检索和生成质量。

评估维度：
1. 检索相关性：评估检索到的文档是否与问题相关
2. 答案基础性：评估答案是否基于提供的文档
3. 答案实用性：评估答案是否真正有用
"""

SELF_RAG_RETRIEVAL_PROMPT = """Evaluate the relevance of this retrieved document to the user's question.

**Your Task:**
Determine if the document contains information that helps answer the question.

**Question:** {question}

**Document:**
{document}

**Evaluation Criteria:**

1. **RELEVANT** - Document is highly useful
   - Contains direct answers or key information
   - Addresses the main topic of the question
   - Provides facts, definitions, or explanations needed

   Example: Question about "XSS attacks" + Document explaining XSS attack principles

2. **PARTIALLY_RELEVANT** - Document is tangentially related
   - Mentions related concepts but not the main topic
   - Provides background context but not direct answers
   - Contains some useful information but incomplete

   Example: Question about "XSS attacks" + Document about web security (mentions XSS briefly)

3. **IRRELEVANT** - Document is not useful
   - Off-topic or unrelated to the question
   - Does not contain information that helps answer
   - Completely different subject matter

   Example: Question about "XSS attacks" + Document about network infrastructure

**Confidence Score:**
- 1.0: Very confident in the assessment
- 0.8-0.9: Confident with minor uncertainty
- 0.5-0.7: Moderate confidence
- 0.0-0.4: Low confidence

**Output Format (JSON only):**
{
  "relevance": "RELEVANT|PARTIALLY_RELEVANT|IRRELEVANT",
  "confidence": 0.0-1.0,
  "reason": "brief explanation (max 100 chars)"
}

**Examples:**

Question: "What is SQL injection?"
Document: "SQL injection is a web security vulnerability that allows an attacker to interfere with database queries..."
→ {"relevance": "RELEVANT", "confidence": 1.0, "reason": "directly explains SQL injection"}

Question: "What is SQL injection?"
Document: "Web applications should implement input validation to prevent various attacks..."
→ {"relevance": "PARTIALLY_RELEVANT", "confidence": 0.7, "reason": "mentions prevention but not SQL injection specifically"}

Question: "What is SQL injection?"
Document: "Network firewalls protect against unauthorized access to internal networks..."
→ {"relevance": "IRRELEVANT", "confidence": 0.9, "reason": "about network security, not SQL injection"}
"""

SELF_RAG_ANSWER_QUALITY_PROMPT = """Evaluate the quality of this generated answer.

**Your Task:**
Assess whether the answer is grounded in sources and useful for the user.

**Question:** {question}

**Answer:** {answer}

**Source Documents:** {documents}

**Evaluation Dimensions:**

1. **Groundedness** - Is the answer supported by sources?

   **FULLY_GROUNDED:**
   - Every factual claim is backed by source documents
   - All citations are correct and verifiable
   - No information added beyond what sources provide

   **PARTIALLY_GROUNDED:**
   - Most claims are supported but some lack backing
   - Some reasonable inferences made from sources
   - Minor additions that don't contradict sources

   **NOT_GROUNDED:**
   - Contains fabricated or unsupported information
   - Makes claims contradicting source documents
   - Adds substantial information not in sources

2. **Utility** - How useful is the answer for the user?

   **HIGH:**
   - Directly answers the question
   - Provides sufficient detail and context
   - Well-structured and easy to understand
   - Answers all parts of the question

   **MEDIUM:**
   - Partially answers the question
   - Missing some details or context
   - Could be more complete or clearer

   **LOW:**
   - Misses the point of the question
   - Too vague or generic
   - Doesn't provide actionable information

**Confidence Score:**
- How confident are you in your assessment? (0.0-1.0)

**Issues:**
- List specific problems found (if any)
- Be concrete and actionable

**Suggestions:**
- How could the answer be improved?
- What additional information would help?

**Output Format (JSON only):**
{
  "groundedness": "FULLY_GROUNDED|PARTIALLY_GROUNDED|NOT_GROUNDED",
  "utility": "HIGH|MEDIUM|LOW",
  "confidence": 0.0-1.0,
  "issues": ["issue1", "issue2", ...],
  "suggestions": ["suggestion1", "suggestion2", ...]
}

**Examples:**

Question: "What is phishing?"
Answer: "Phishing is a social engineering attack where attackers impersonate legitimate entities to steal credentials [1]."
Sources: [1] Document explaining phishing attacks
→ {
  "groundedness": "FULLY_GROUNDED",
  "utility": "HIGH",
  "confidence": 0.95,
  "issues": [],
  "suggestions": ["Could add examples of common phishing techniques"]
}

Question: "What is phishing?"
Answer: "Phishing is a cyber attack. It's very dangerous and everyone should be careful."
Sources: [1] Document explaining phishing attacks
→ {
  "groundedness": "PARTIALLY_GROUNDED",
  "utility": "LOW",
  "confidence": 0.9,
  "issues": ["Too vague", "Doesn't explain how phishing works", "No citations"],
  "suggestions": ["Add concrete definition", "Explain attack mechanism", "Cite sources"]
}
"""
