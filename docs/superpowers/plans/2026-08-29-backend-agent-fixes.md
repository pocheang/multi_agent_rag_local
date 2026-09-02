# Backend Agent Audit Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the concrete correctness bugs found by the 2026-08-29 backend agent audit, delete confirmed-orphaned "unfinished migration" modules (including `app/agents/tool/react.py`), and correct the CLAUDE.md claims that no longer match the running system.

**Architecture:** No architectural changes. Every fix is a small, local edit inside an existing module (citation-marker regex, prompt text, one helper function, one comment block) or a deletion of a module with zero production call sites (verified by repo-wide grep before this plan was written). Nothing in `app/orchestration/`, `app/domain/`, or the LangGraph topology changes.

**Tech Stack:** Python 3.11+, pytest + pytest-asyncio (already a dependency; no `tests/` tree exists yet in this repo — this plan creates the first files under it).

## Global Constraints

- Conda environment `rag-local` must be active for every command in this plan.
- Do not change default values of any settings/env flags (e.g. `CASCADE_ENABLE_LEVEL2`, `ENABLE_CALIBRATION`, `knowledge_orchestrator_enabled`) — this plan fixes bugs and removes dead code, it does not activate previously-dormant features. That is an explicit, separate decision the user has not made yet.
- Every deletion task must be preceded by a verification grep (already run once while writing this plan; re-run it as the task's first step in case the tree changed) confirming zero remaining references outside the file(s) being deleted.
- Follow existing code style: `from __future__ import annotations`, Pydantic-first typed contracts, no new dependencies.
- Run `ruff check <changed files>` and `ruff format <changed files>` before each commit in this plan.

---

## File Structure

- Modify: `app/agents/validation/citations.py` — fix the inline-citation-marker regex.
- Create: `tests/agents/validation/test_citations.py` — regression test for the regex fix.
- Modify: `app/prompts/core/canonical_agent_prompts.py` — fix `ANSWER_PROMPT`/`REVIEW_PROMPT` citation instructions to describe the `[E1]`/`[E2]` marker convention instead of the unused `[doc_id:page]` format.
- Modify: `app/agents/synthesizer/templates.py` — fix the 5 answer templates + `COT_REASONING_PROMPT` for the same reason.
- Create: `tests/agents/synthesizer/test_prompt_citation_format.py` — regression test asserting the stale format string never comes back.
- Modify: `app/agents/synthesizer/service.py` — fix `_citation_label()` to key off `source` (matching the live `nodes.py` convention) instead of `document_id`.
- Create: `tests/agents/synthesizer/test_service.py` — regression test for the citation-label fix.
- Modify: `app/agents/shared/config.py` — fix the Level 2 / Level 3 docstrings, which currently describe the wrong validator.
- Delete: `app/agents/router/enhanced_service.py`, `hybrid_clarification.py`, `accuracy.py`, `frontend_integration.py`, `validator.py`, `adapter.py`, `pipeline.py`.
- Modify: `app/agents/router/config.py` — remove the flags/functions that only the deleted files consumed.
- Delete: `app/agents/rag/enhanced_vector.py`, `app/agents/rag/fusion.py`.
- Delete: `app/agents/validation/quality_orchestrator.py`.
- Delete: `app/agents/tool/react.py`.
- Modify: `app/services/observability/agent_health.py` — remove the health check for the now-deleted `react` module.
- Modify: `CLAUDE.md` — correct six claims that no longer match the running system.

---

### Task 1: Fix the inline-citation-marker regex in the validation cascade

**Files:**
- Modify: `app/agents/validation/citations.py:43`
- Test: `tests/agents/validation/test_citations.py`

**Interfaces:**
- Consumes: `app.agents.validation.models.ValidationRequest`, `CitationValidator` (both already exist, unchanged).
- Produces: nothing new — this only fixes `CitationValidator.validate()`'s internal marker-detection logic.

**Context:** The live evidence-rendering convention (`app/knowledge/context.py:124`, `_render_item`) always labels evidence blocks `[E1]`, `[E2]`, ... — never bare digits. `CitationValidator.validate()` currently checks `re.findall(r"\[(\d+)\]", request.answer)` to decide whether an answer already carries a visible citation marker before flagging `missing_citation`. That pattern can never match `[E1]`, so any answer that correctly cites evidence as `[E1]` but has zero *structured* `request.citations` (e.g. citation parsing dropped them) gets an incorrect `missing_citation` issue.

- [ ] **Step 1: Write the failing test**

Create `tests/agents/validation/test_citations.py`:

```python
"""Regression tests for CitationValidator's inline-marker detection."""

from __future__ import annotations

import pytest

from app.agents.validation.citations import CitationValidator
from app.agents.validation.models import ValidationRequest


@pytest.mark.asyncio
async def test_evidence_marker_citation_suppresses_missing_citation_issue():
    """An answer that already cites [E1] must not be flagged as uncited,
    even when no structured ValidationCitation objects were supplied."""
    request = ValidationRequest.from_compatibility(
        query="What was the reported revenue?",
        answer="Revenue grew to 42 million dollars [E1].",
        source_docs=[{"id": "doc1", "content": "Revenue grew to 42 million dollars in Q4."}],
        citations=[],
    )

    result = await CitationValidator().validate(request)

    issue_types = [issue.issue_type for issue in result.issues]
    assert "missing_citation" not in issue_types


@pytest.mark.asyncio
async def test_factual_answer_without_any_marker_is_still_flagged():
    """An answer with a factual claim and no citation marker at all must
    still be flagged — the fix must not disable this check entirely."""
    request = ValidationRequest.from_compatibility(
        query="What was the reported revenue?",
        answer="Revenue grew to 42 million dollars.",
        source_docs=[{"id": "doc1", "content": "Revenue grew to 42 million dollars in Q4."}],
        citations=[],
    )

    result = await CitationValidator().validate(request)

    issue_types = [issue.issue_type for issue in result.issues]
    assert "missing_citation" in issue_types
```

- [ ] **Step 2: Run the test to verify the first case fails**

Run: `conda run -n rag-local pytest tests/agents/validation/test_citations.py -v`
Expected: `test_evidence_marker_citation_suppresses_missing_citation_issue` FAILS (assertion error: `"missing_citation"` is present), `test_factual_answer_without_any_marker_is_still_flagged` PASSES.

- [ ] **Step 3: Fix the regex**

In `app/agents/validation/citations.py`, change line 43:

```python
            has_inline_marker = bool(re.findall(r"\[(\d+)\]", request.answer))
```

to:

```python
            has_inline_marker = bool(re.findall(r"\[E\d+\]", request.answer))
```

- [ ] **Step 4: Run the tests to verify both pass**

Run: `conda run -n rag-local pytest tests/agents/validation/test_citations.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Lint and commit**

```bash
conda run -n rag-local ruff check app/agents/validation/citations.py
conda run -n rag-local ruff format app/agents/validation/citations.py
git add app/agents/validation/citations.py tests/agents/validation/test_citations.py
git commit -m "fix(validation): match the actual [E1] evidence-marker format in citation check"
```

---

### Task 2: Fix the citation-format contradiction in synthesis prompts

**Files:**
- Modify: `app/prompts/core/canonical_agent_prompts.py:98-118` (`ANSWER_PROMPT`), `:128-129` (`REVIEW_PROMPT`)
- Modify: `app/agents/synthesizer/templates.py` (`CONCEPT_TEMPLATE`, `COMPARISON_TEMPLATE`, `RELATIONSHIP_TEMPLATE`, `PROCEDURAL_TEMPLATE`, `GENERAL_TEMPLATE`, `COT_REASONING_PROMPT`)
- Test: `tests/agents/synthesizer/test_prompt_citation_format.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new — this only changes prompt text content, not any function signature.

**Context:** Evidence is always rendered to the model as `[E1] document=...; source=...` (`app/knowledge/context.py:124`), and `SynthesizerAgentService.synthesize_candidate()` only ever allow-lists labels of the form `E1`, `E2`, ... (`app/agents/synthesizer/service.py:40`). But `ANSWER_PROMPT` and `REVIEW_PROMPT` (in `canonical_agent_prompts.py`) and all 5 answer templates (in `templates.py`) instruct the model to cite using `[doc_id:page]`, with worked examples like `[doc1:p3]`. Any citation the model emits in the *taught* `[doc_id:page]` form gets silently stripped by `normalize_answer_citations()` (`app/agents/synthesizer/citations.py:21-34`, since it's not in `allowed_labels`), producing spurious `missing_citations` in `unresolved_items` and unnecessary verifier retries. This task makes every citation-instructing prompt describe the marker format the system actually uses.

- [ ] **Step 1: Write the failing test**

Create `tests/agents/synthesizer/test_prompt_citation_format.py`:

```python
"""Regression test: every citation-instructing prompt must describe the
[E1]/[E2] evidence-marker convention the system actually renders and
allow-lists, not the unused [doc_id:page] format."""

from __future__ import annotations

import pytest

from app.agents.synthesizer.templates import (
    COMPARISON_TEMPLATE,
    CONCEPT_TEMPLATE,
    COT_REASONING_PROMPT,
    GENERAL_TEMPLATE,
    PROCEDURAL_TEMPLATE,
    RELATIONSHIP_TEMPLATE,
)
from app.prompts.core.canonical_agent_prompts import ANSWER_PROMPT, REVIEW_PROMPT

_STALE_MARKERS = ("doc_id:page", "doc1:p3", "doc1:p5", "doc2:p1")


@pytest.mark.parametrize(
    "prompt_text",
    [
        ANSWER_PROMPT,
        REVIEW_PROMPT,
        CONCEPT_TEMPLATE,
        COMPARISON_TEMPLATE,
        RELATIONSHIP_TEMPLATE,
        PROCEDURAL_TEMPLATE,
        GENERAL_TEMPLATE,
        COT_REASONING_PROMPT,
    ],
)
def test_prompt_does_not_teach_the_unused_doc_id_page_format(prompt_text: str):
    for stale_marker in _STALE_MARKERS:
        assert stale_marker not in prompt_text, f"found stale marker {stale_marker!r}"


def test_answer_prompt_teaches_the_evidence_marker_format():
    assert "[E1]" in ANSWER_PROMPT
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `conda run -n rag-local pytest tests/agents/synthesizer/test_prompt_citation_format.py -v`
Expected: FAIL — `ANSWER_PROMPT`, `REVIEW_PROMPT`, and all 5 templates currently contain `doc_id:page` / `doc1:p3` / etc.

- [ ] **Step 3: Fix `ANSWER_PROMPT` in `app/prompts/core/canonical_agent_prompts.py`**

Replace the citation section (lines 98-118):

```python
引用规则（Citation-First Generation - Task 13）：
- 强制 每个事实性陈述必须有引用 [doc_id:page]
- 强制 上下文中的引用格式为 [doc_id:page] 内容，你必须在答案中逐字保留这些引用标记
- 强制 示例：如果上下文是 [doc1:p3] Transformer uses self-attention ，答案必须写成 Transformer uses self-attention [doc1:p3]
- 强制 无引用 = 不能声明为事实。无法引用的信息必须使用模糊语言或说明信息不足
- 禁止 不要编造、推测或添加上下文中未提供的信息
- 禁止 不要删除或省略上下文中的引用标记 [doc_id:page]
- 推荐 对于不完整的上下文，使用限定语言：根据提供的信息、部分包括、有限信息显示
- 推荐 根据问题类型（概念/对比/关系/步骤）组织答案结构，但每个要点都要有引用

引用格式说明：
- 输入格式：[doc_id:page] 内容
- 输出格式：内容 [doc_id:page] 或 内容[doc_id:page]
- 必须保留引用标记，可以调整位置使其自然嵌入句子中
```

with:

```python
引用规则（Citation-First Generation - Task 13）：
- 强制 每个事实性陈述必须有证据标记引用，如 [E1]、[E2]
- 强制 上下文中每条证据以 [E1] document=...; source=...; layer=... 开头，你必须在答案中逐字保留这些证据标记（[E1]、[E2] 等）
- 强制 示例：如果上下文是 [E1] document=doc1, page=3; source=doc1; layer=evidence\nTransformer uses self-attention ，答案必须写成 Transformer uses self-attention [E1]
- 强制 无引用 = 不能声明为事实。无法引用的信息必须使用模糊语言或说明信息不足
- 禁止 不要编造、推测或添加上下文中未提供的信息
- 禁止 不要删除或省略上下文中的证据标记（[E1]、[E2] 等），也不要发明不存在的标记
- 推荐 对于不完整的上下文，使用限定语言：根据提供的信息、部分包括、有限信息显示
- 推荐 根据问题类型（概念/对比/关系/步骤）组织答案结构，但每个要点都要有引用

引用格式说明：
- 输入格式：[E1] document=..., page=...; source=...; layer=...\n内容
- 输出格式：内容 [E1] 或 内容[E1]
- 必须保留证据标记（[E1]、[E2] 等），可以调整位置使其自然嵌入句子中
```

- [ ] **Step 4: Fix `REVIEW_PROMPT` in the same file**

Replace:

```python
4) Task 13 检查引用完整性：每个事实性陈述是否都有 [doc_id:page] 引用？
5) Task 13 检查引用真实性：答案中的引用是否都在上下文中存在？
```

with:

```python
4) Task 13 检查引用完整性：每个事实性陈述是否都有 [E1]/[E2] 等证据标记引用？
5) Task 13 检查引用真实性：答案中的证据标记是否都在上下文提供的证据中存在？
```

- [ ] **Step 5: Fix the 5 templates in `app/agents/synthesizer/templates.py`**

Replace `CONCEPT_TEMPLATE`:

```python
CONCEPT_TEMPLATE = """
Answer template for concept explanation:

1. Core definition with citation [doc_id:page]
2. Key characteristics (each with citation)
3. Scope and boundaries (cite sources or acknowledge limitation)

Citation rules:
- EVERY factual claim MUST have [doc_id:page] citation
- If information is not in context, explicitly state "根据提供的信息" (based on provided information)
- Use hedging language for uncertain or incomplete contexts: "部分应用包括..." (some applications include...)

Example structure:
<concept> 是 <definition> [doc1:p3]。它的主要特征包括：<feature1> [doc1:p5]，<feature2> [doc2:p1]。
"""
```

with:

```python
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
```

Replace `COMPARISON_TEMPLATE`:

```python
COMPARISON_TEMPLATE = """
Answer template for comparison questions:

1. Brief introduction of both subjects with citations
2. Structured comparison table or point-by-point analysis:
   - Dimension 1: Subject A [doc_id:page] vs Subject B [doc_id:page]
   - Dimension 2: Subject A [doc_id:page] vs Subject B [doc_id:page]
3. Summary of key differences with citations

Citation rules:
- Each comparison dimension MUST cite sources for BOTH subjects
- If one subject lacks context, explicitly state: "提供的信息中未包含<subject>的<aspect>" (provided information does not include...)
- Avoid subjective preference without citation

Example structure:
对比 <A> 和 <B>：
- 特征维度：<A>使用<method1> [doc1:p2]，而<B>采用<method2> [doc2:p5]
- 应用场景：<A>适用于<scenario1> [doc1:p8]，<B>用于<scenario2> [doc3:p1]
"""
```

with:

```python
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
```

Replace `RELATIONSHIP_TEMPLATE`:

```python
RELATIONSHIP_TEMPLATE = """
Answer template for relationship questions (how X relates to Y):

1. Establish context for both entities with citations
2. Direct relationship with citation [doc_id:page]
3. Supporting evidence or examples (each cited)
4. Scope limitation if context is incomplete

Citation rules:
- Direct relationship claim MUST have citation
- Supporting examples must cite sources
- If relationship is inferred, use hedging: "根据提供的信息，X和Y可能存在关联" (based on provided information, X and Y may be related)

Example structure:
<X> 与 <Y> 的关系：<X> 是 <Y> 的 <relationship> [doc1:p3]。具体表现为：<evidence1> [doc1:p4]，<evidence2> [doc2:p2]。
"""
```

with:

```python
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
```

Replace `PROCEDURAL_TEMPLATE`:

```python
PROCEDURAL_TEMPLATE = """
Answer template for procedural/how-to questions:

1. Overview of the process with citation
2. Step-by-step breakdown (each step cited):
   Step 1: <action> [doc_id:page]
   Step 2: <action> [doc_id:page]
   ...
3. Important notes or prerequisites (cited)

Citation rules:
- Each step MUST have supporting citation
- If steps are missing from context, explicitly state: "提供的信息中包含部分步骤" (provided information contains partial steps)
- Do not fabricate steps not in context

Example structure:
<process> 的步骤：
1. <step1> [doc1:p5]
2. <step2> [doc1:p6]
3. <step3> [doc2:p2]
注意：<prerequisite> [doc1:p4]
"""
```

with:

```python
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
```

Replace `GENERAL_TEMPLATE`:

```python
GENERAL_TEMPLATE = """
Answer template for general questions:

1. Direct answer to the question with citation [doc_id:page]
2. Supporting details (each with citation)
3. Context or qualifications if needed (cited)

Citation rules:
- EVERY factual claim MUST have [doc_id:page] citation
- No citation = no claim (use hedging or acknowledge limitation)
- For broad questions with narrow context, scope the answer: "根据提供的信息，<scoped_answer>"

Example structure:
<question_restatement>：<answer> [doc1:p3]。<detail1> [doc1:p5]，<detail2> [doc2:p1]。
"""
```

with:

```python
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
```

- [ ] **Step 6: Fix `COT_REASONING_PROMPT` in the same file**

Replace:

```python
3. Citation Planning:
   - Which doc_id:page supports each factual statement?
   - Are there unsupported claims I should remove or hedge?
   - Do I need to acknowledge information gaps?
```

with:

```python
3. Citation Planning:
   - Which evidence marker ([E1], [E2], ...) supports each factual statement?
   - Are there unsupported claims I should remove or hedge?
   - Do I need to acknowledge information gaps?
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `conda run -n rag-local pytest tests/agents/synthesizer/test_prompt_citation_format.py -v`
Expected: all PASS.

- [ ] **Step 8: Lint and commit**

```bash
conda run -n rag-local ruff check app/prompts/core/canonical_agent_prompts.py app/agents/synthesizer/templates.py
conda run -n rag-local ruff format app/prompts/core/canonical_agent_prompts.py app/agents/synthesizer/templates.py
git add app/prompts/core/canonical_agent_prompts.py app/agents/synthesizer/templates.py tests/agents/synthesizer/test_prompt_citation_format.py
git commit -m "fix(synthesizer): align citation prompts with the actual [E1] evidence-marker format"
```

---

### Task 3: Fix the citation-label field inconsistency in `SynthesizerAgentService.synthesize()`

**Files:**
- Modify: `app/agents/synthesizer/service.py:129-130` and its two call sites (`:99`, `:105`)
- Test: `tests/agents/synthesizer/test_service.py`

**Interfaces:**
- Consumes: `app.domain.contracts.EvidenceItem`, `EvidenceBundle`, `RouteDecision`; `app.orchestration.request.OrchestrationRequest`.
- Produces: no signature change — `SynthesizerAgentService.synthesize()` still returns `FinalAnswer`.

**Context:** `app/orchestration/langgraph/nodes.py:543-544` builds every user-visible citation label as `f"{source}:{page}"` (module-level `_citation_label(source, page)`), and this is the function that actually runs for every live request through the graph (both the `verifier` node at `nodes.py:355` and `output_filter` node at `nodes.py:396` call it). `SynthesizerAgentService.synthesize()` — the `OrchestrationServices.synthesizer` fallback used only when `candidate_synthesizer` is `None` (never true in current production wiring, but still a documented, reachable code path per `engine.py`'s `Synthesizer` protocol) — has its own, differently-keyed `_citation_label(document_id, page)` at `service.py:129-130`. `source` and `document_id` are legitimately different fields on `EvidenceItem` (`app/domain/contracts.py:159-160`). This task makes the fallback path consistent with the live path so it produces the same citation-label convention if it is ever exercised.

- [ ] **Step 1: Write the failing test**

Create `tests/agents/synthesizer/test_service.py`:

```python
"""Regression test: SynthesizerAgentService.synthesize() must label citations
the same way app/orchestration/langgraph/nodes.py does (by `source`, not
`document_id`) so the fallback synthesis path never disagrees with the live
LangGraph path on what a citation label means."""

from __future__ import annotations

import pytest

from app.agents.synthesizer.service import SynthesizerAgentService
from app.domain.contracts import EvidenceBundle, EvidenceItem, RouteDecision
from app.orchestration.request import OrchestrationRequest


def _fake_generate(*_args: object, **_kwargs: object) -> dict:
    return {"answer": "Paris is the capital of France [E1]."}


@pytest.mark.asyncio
async def test_citation_label_uses_source_not_document_id():
    item = EvidenceItem(
        content="Paris is the capital of France.",
        source="https://example.com/geography-article",
        document_id="internal-doc-42",
        version=1,
        page=3,
        retriever="vector",
    )
    evidence = EvidenceBundle(items=(item,))
    route = RouteDecision(confidence=0.9, requires_plan=False, allowed_capabilities=frozenset(), reason="test route")
    request = OrchestrationRequest(question="What is the capital of France?")
    service = SynthesizerAgentService(generate=_fake_generate)

    result = await service.synthesize(request, route, None, evidence, ())

    assert result.citations == ("https://example.com/geography-article:3",)
    assert "internal-doc-42:3" not in result.citations
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `conda run -n rag-local pytest tests/agents/synthesizer/test_service.py -v`
Expected: FAIL — `result.citations` is currently `("internal-doc-42:3",)`.

- [ ] **Step 3: Fix `_citation_label` and its call sites in `app/agents/synthesizer/service.py`**

Replace:

```python
def _citation_label(document_id: str, page: int | None) -> str:
    return f"{document_id}:{page}" if page is not None else document_id
```

with:

```python
def _citation_label(source: str, page: int | None) -> str:
    return f"{source}:{page}" if page is not None else source
```

Replace the two call sites inside `synthesize()`:

```python
        for index, item in reversed(tuple(enumerate(evidence.items, start=1))):
            text = text.replace(f"[E{index}]", f"[{_citation_label(item.document_id, item.page)}]")
        cited_ids = _evidence_ids_for_refs(candidate.citations, evidence)
        cited_id_set = frozenset(cited_ids)
        return FinalAnswer(
            answer=text,
            citations=tuple(
                _citation_label(item.document_id, item.page)
                for item in evidence.items
                if item.item_id in cited_id_set
            ),
```

with:

```python
        for index, item in reversed(tuple(enumerate(evidence.items, start=1))):
            text = text.replace(f"[E{index}]", f"[{_citation_label(item.source, item.page)}]")
        cited_ids = _evidence_ids_for_refs(candidate.citations, evidence)
        cited_id_set = frozenset(cited_ids)
        return FinalAnswer(
            answer=text,
            citations=tuple(
                _citation_label(item.source, item.page)
                for item in evidence.items
                if item.item_id in cited_id_set
            ),
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `conda run -n rag-local pytest tests/agents/synthesizer/test_service.py -v`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
conda run -n rag-local ruff check app/agents/synthesizer/service.py
conda run -n rag-local ruff format app/agents/synthesizer/service.py
git add app/agents/synthesizer/service.py tests/agents/synthesizer/test_service.py
git commit -m "fix(synthesizer): key citation labels by source, matching the live graph path"
```

---

### Task 4: Fix the misleading validation-cascade level comments

**Files:**
- Modify: `app/agents/shared/config.py:185-189`

**Interfaces:**
- Consumes/Produces: none — comment-only change, no behavior or default value changes.

**Context:** `app/agents/validation/cascade.py` wires `enable_level2` to `NLIValidator.validate()` (`cascade.py:112-113`) and `enable_level3` to `CitationValidator.validate()` (`cascade.py:108-109`). But `app/agents/shared/config.py`'s docstrings say the opposite: Level 2 = "Pattern matching validation" and Level 3 = "NLI model validation". This is a documentation-only bug (the code's behavior is correct and unchanged by this task) — it matters because it means anyone reading these comments to decide whether NLI-based hallucination detection is active (it is **not**, by default — `CASCADE_ENABLE_LEVEL2` defaults to `False`) will draw the wrong conclusion. This task does not change any default; it only makes the comment describe what the flag actually gates.

- [ ] **Step 1: Fix the docstrings**

In `app/agents/shared/config.py`, replace:

```python
CASCADE_ENABLE_LEVEL2: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL2", False)
"""Level 2: Pattern matching validation (disabled by default, experimental)."""

CASCADE_ENABLE_LEVEL3: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL3", True)
"""Level 3: NLI model validation (~75ms)."""
```

with:

```python
CASCADE_ENABLE_LEVEL2: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL2", False)
"""Level 2: NLI cross-encoder hallucination check, gates NLIValidator in
app/agents/validation/cascade.py (disabled by default)."""

CASCADE_ENABLE_LEVEL3: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL3", True)
"""Level 3: citation-completeness check, gates CitationValidator in
app/agents/validation/cascade.py (~75ms budget, enabled by default)."""
```

- [ ] **Step 2: Verify no other file repeats the stale description**

Run: `conda run -n rag-local grep -rn "Pattern matching validation" app/ || true`
Expected: no output (only the two lines just edited referenced it).

- [ ] **Step 3: Lint and commit**

```bash
conda run -n rag-local ruff check app/agents/shared/config.py
conda run -n rag-local ruff format app/agents/shared/config.py
git add app/agents/shared/config.py
git commit -m "docs(validation): correct which cascade level gates the NLI vs citation check"
```

---

### Task 5: Delete the orphaned router/clarification-rewrite module cluster

**Files:**
- Delete: `app/agents/router/enhanced_service.py`, `app/agents/router/hybrid_clarification.py`, `app/agents/router/accuracy.py`, `app/agents/router/frontend_integration.py`, `app/agents/router/validator.py`, `app/agents/router/adapter.py`, `app/agents/router/pipeline.py`
- Modify: `app/agents/router/config.py`

**Interfaces:**
- Consumes/Produces: none. These 7 files have zero import sites anywhere in `app/` outside each other (verified by grep while writing this plan). The live router path is `app/agents/router/service.py` → `routing.py`, and the live clarification path is `app/agents/clarification/service.py` + `rules.py` — neither imports anything from this cluster.

**Context:** This cluster is a "next-generation" router/clarification rewrite (hybrid rule+LLM clarification, confidence calibration pipeline, accuracy tracking, frontend integration helpers) that was built but never wired into `app/orchestration/capabilities.py`. CLAUDE.md incorrectly cites `app/agents/router/enhanced_service.py` as the "Key service" for the Enhanced Clarification System — Task 9 of this plan fixes that claim.

- [ ] **Step 1: Re-verify zero external references (tree may have changed since this plan was written)**

Run:
```bash
grep -rn "enhanced_service\|hybrid_clarification\|router\.accuracy\|router\.validator\|router\.adapter\|router\.pipeline\|frontend_integration\|RoutingPipeline\|decide_route_refactored\|RouteAccuracyTracker" app/ --include="*.py" | grep -v "^app/agents/router/\(enhanced_service\|hybrid_clarification\|accuracy\|frontend_integration\|validator\|adapter\|pipeline\)\.py"
```
Expected: no output. If this prints anything, STOP and investigate before deleting — a new caller may have appeared.

- [ ] **Step 2: Delete the 7 files**

```bash
git rm app/agents/router/enhanced_service.py app/agents/router/hybrid_clarification.py app/agents/router/accuracy.py app/agents/router/frontend_integration.py app/agents/router/validator.py app/agents/router/adapter.py app/agents/router/pipeline.py
```

- [ ] **Step 3: Trim `app/agents/router/config.py` to only the flags `routing.py` actually reads**

Read the current file first (`app/agents/router/config.py`), then replace its full contents with:

```python
"""Router module configuration."""

import os
from typing import Final

# Confidence calibration
ENABLE_CALIBRATION: Final[bool] = os.getenv("ENABLE_CALIBRATION", "false").lower() == "true"

# Web route control
ENABLE_WEB_ROUTE_DOWNGRADE: Final[bool] = os.getenv("ENABLE_WEB_ROUTE_DOWNGRADE", "false").lower() == "true"
```

(This removes `DISABLE_WEB_ROUTE`, `should_disable_web_route()`, `USE_REASONING_FOR_LOW_CONFIDENCE`, `should_use_reasoning_fallback()`, `ENABLE_ROUTER_ACCURACY_TRACKING`, `ROUTER_ACCURACY_LOG_FILE`, `USE_HYBRID_CLARIFICATION`, `LLM_FALLBACK_THRESHOLD`, `LLM_ENHANCED_EXTRACTION`, `LLM_DYNAMIC_QUESTIONS` — confirmed while writing this plan to have zero readers outside the 7 files just deleted. `ENABLE_CALIBRATION` and `ENABLE_WEB_ROUTE_DOWNGRADE` are kept because `app/agents/router/routing.py:17` imports both.)

- [ ] **Step 4: Verify the app still imports cleanly**

Run: `conda run -n rag-local python -c "import app.agents.router.service; import app.agents.router.routing; import app.orchestration.capabilities; print('ok')"`
Expected: prints `ok` with no `ImportError`/`ModuleNotFoundError`.

- [ ] **Step 5: Commit**

```bash
git add app/agents/router/config.py
git commit -m "chore(router): remove the orphaned enhanced-router/clarification-rewrite cluster

app/agents/router/{enhanced_service,hybrid_clarification,accuracy,frontend_integration,validator,adapter,pipeline}.py
had zero call sites outside each other; the live router/clarification path
is app/agents/router/service.py + app/agents/clarification/service.py."
```

---

### Task 6: Delete the orphaned RAG fusion/enhanced-vector modules

**Files:**
- Delete: `app/agents/rag/enhanced_vector.py`, `app/agents/rag/fusion.py`

**Interfaces:**
- Consumes/Produces: none. `app/agents/rag/fusion.py` (`fuse_evidence`) and `app/agents/rag/enhanced_vector.py` (`EnhancedVectorRAGAgent`) both have zero call sites in `app/` (verified by grep). The live RRF fusion path is `app/retrievers/hybrid/fusion.py`, used via `app/knowledge/orchestrator.py`; the live vector retrieval path is `app/agents/rag/vector.py`.

**Context:** `app/agents/rag/fusion.py::fuse_evidence` implements document/page deduplication by max score — not RRF despite the module name — and is never called. `enhanced_vector.py`'s only reference anywhere is a stale docstring comment in `app/agents/rag/vector.py:6,12` naming an even-older filename (`enhanced_vector_rag_agent.py`), not an actual import.

- [ ] **Step 1: Re-verify zero external references**

Run:
```bash
grep -rn "fuse_evidence\|EnhancedVectorRAGAgent\|from app.agents.rag.enhanced_vector\|from app.agents.rag.fusion\|agents\.rag\.fusion\|agents\.rag\.enhanced_vector" app/ --include="*.py" | grep -v "^app/agents/rag/\(fusion\|enhanced_vector\)\.py"
```
Expected: no output.

- [ ] **Step 2: Delete the 2 files**

```bash
git rm app/agents/rag/enhanced_vector.py app/agents/rag/fusion.py
```

- [ ] **Step 3: Verify the app still imports cleanly**

Run: `conda run -n rag-local python -c "import app.agents.rag.service; import app.agents.rag.vector; import app.knowledge.orchestrator; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(rag): remove unused fusion.py::fuse_evidence and enhanced_vector.py

Neither has any call sites; live fusion runs through
app/retrievers/hybrid/fusion.py via app/knowledge/orchestrator.py, and live
vector retrieval runs through app/agents/rag/vector.py."
```

---

### Task 7: Delete the orphaned second quality-scoring engine

**Files:**
- Delete: `app/agents/validation/quality_orchestrator.py`

**Interfaces:**
- Consumes/Produces: none. `orchestrate_quality()` and its `QualityReport` output have zero production call sites (verified by grep — only self-references and a stale comment in `app/agents/shared/result_schemas.py:82` remain, and that comment is not an import). `app.agents.shared.quality_models.QualityReport` (the type) is still used elsewhere (`app/orchestration/finalization.py`, `app/services/legacy_quality_compat.py`) and is **not** touched by this task — only the orchestrator function/module is unused.

**Context:** The live quality report is `OrchestratedQualityReport` (`app/domain/contracts.py:272-277`), produced by `app/orchestration/finalization.py`. `quality_orchestrator.py` implements a second, independent 5-dimension weighted-scoring system that predates it and was never wired into `FinalizationService` or anywhere else.

- [ ] **Step 1: Re-verify zero external references**

Run:
```bash
grep -rn "quality_orchestrator\|orchestrate_quality" app/ --include="*.py" | grep -v "^app/agents/validation/quality_orchestrator\.py"
```
Expected: only the comment line in `app/agents/shared/result_schemas.py` (not an import — safe to leave as-is, it is just a historical note).

- [ ] **Step 2: Delete the file**

```bash
git rm app/agents/validation/quality_orchestrator.py
```

- [ ] **Step 3: Verify the app still imports cleanly**

Run: `conda run -n rag-local python -c "import app.agents.validation.public; import app.orchestration.finalization; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(validation): remove the orphaned quality_orchestrator.py

orchestrate_quality() has zero callers; the live quality report is
OrchestratedQualityReport, produced by app/orchestration/finalization.py."
```

---

### Task 8: Delete the orphaned ReAct tool loop and its stale health check

**Files:**
- Delete: `app/agents/tool/react.py`
- Modify: `app/services/observability/agent_health.py`

**Interfaces:**
- Consumes/Produces: none. `app/agents/tool/react.py` (`ReActAgent`/`ReactAgent`) has zero call sites in `app/` outside itself (verified by grep). The production `tool_runner` is `ToolAgentService.run()` (`app/agents/tool/service.py`), which does not import or invoke `react.py` — it only regex-matches a "disable connector" command.

**Context:** This was confirmed and explicitly approved for deletion: `react.py` is a fully-built iterative ReAct loop (max-iteration bound, tool dispatch, observation accumulation) that is never invoked by any production request path. Its only reference anywhere is `app/services/observability/agent_health.py:64`, which does an `importlib.util.find_spec` existence check for a diagnostics endpoint — it does not import or run the module, so it degrades gracefully to `status: "error"` for missing modules already (see `_module_status`, `agent_health.py:18-24`). This task removes that now-permanently-stale health check entry along with the file it checks. `AgentValidator.validate_enhanced_router_agent` and `validate_workflow` already point at modules that don't exist under their current names (`app.agents.enhanced_router_agent`, `app.graph.execution.workflow`) — that is pre-existing breakage unrelated to this plan's changes, out of scope here, and not modified by this task.

- [ ] **Step 1: Re-verify zero external references**

Run:
```bash
grep -rn "agents\.tool\.react\|ReActAgent\|ReactAgent" app/ --include="*.py" | grep -v "^app/agents/tool/react\.py"
```
Expected: only `app/services/observability/agent_health.py:64` (the health-check reference this task also removes).

- [ ] **Step 2: Delete the file**

```bash
git rm app/agents/tool/react.py
```

- [ ] **Step 3: Remove the stale health-check entry**

In `app/services/observability/agent_health.py`, remove this method:

```python
@staticmethod
def validate_react_agent() -> dict[str, Any]:
    """Validate ReAct Agent module availability."""
    return _module_status("react", "app.agents.tool.react")
```

and remove its entry from `validate_all()`:

```python
        results = {
            "router": cls.validate_router_agent(),
            "vector_rag": cls.validate_vector_rag_agent(),
            "graph_rag": cls.validate_graph_rag_agent(),
            "react": cls.validate_react_agent(),
            "synthesis": cls.validate_synthesis_agent(),
            "enhanced_router": cls.validate_enhanced_router_agent(),
            "workflow": cls.validate_workflow(),
        }
```

becomes:

```python
        results = {
            "router": cls.validate_router_agent(),
            "vector_rag": cls.validate_vector_rag_agent(),
            "graph_rag": cls.validate_graph_rag_agent(),
            "synthesis": cls.validate_synthesis_agent(),
            "enhanced_router": cls.validate_enhanced_router_agent(),
            "workflow": cls.validate_workflow(),
        }
```

- [ ] **Step 4: Verify the app still imports cleanly and the health check still runs**

Run: `conda run -n rag-local python -c "from app.services.observability.agent_health import validate_agent_integration; import json; print(json.dumps(validate_agent_integration()['summary']))"`
Expected: prints a summary dict with no traceback (e.g. `{"total": 6, "ok": ..., "fallback": 0, "error": ...}`) — `total` should now be `6`, not `7`.

- [ ] **Step 5: Commit**

```bash
git add app/services/observability/agent_health.py
git commit -m "chore(tool): remove the unreachable ReAct loop and its stale health check

app/agents/tool/react.py had zero call sites from the production tool_runner
(ToolAgentService.run only handles a regex-matched connector-disable
command). Removing validate_react_agent keeps agent_health.py's diagnostics
from permanently reporting a deleted module as unavailable."
```

---

### Task 9: Correct CLAUDE.md claims that no longer match the running system

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:** none — documentation only.

**Context:** The audit found six specific claims in CLAUDE.md that describe either an abandoned code branch or aspirational behavior that was never wired in. This task corrects each to describe what Tasks 1-8 leave running today, without proposing to build anything new.

- [ ] **Step 1: Fix the Enhanced Clarification System note**

Find:
```markdown
- **Enhanced Clarification System** (added 2026-08-17): Dynamic 2-10 round clarification based on intent complexity. Key service: `app/agents/router/enhanced_service.py`. See daily logs for details.
```

Replace with:
```markdown
- **Clarification System** (added 2026-08-17, revised 2026-08-29): Dynamic clarification based on intent complexity, capped at 0-7 rounds depending on intent (`rag_design`: 7, `document_comparison`: 5, others: 5, already-complete: 0). Key services: `app/agents/clarification/service.py` and `rules.py`, wired as both the LangGraph `clarification` node and the resumable `/api/v1/clarification/check` HTTP endpoint (`app/api/routes/public/clarification.py`) — the two share one implementation. See daily logs for details.
```

- [ ] **Step 2: Fix the router_calibration.json note**

Find:
```markdown
**Essential config files** in `config/`:
- `router_calibration.json`: Few-shot examples, confidence thresholds
```

Replace with:
```markdown
**Essential config files** in `config/`:
- `router_calibration.json`: Few-shot examples, confidence thresholds. Only read when `ENABLE_CALIBRATION=true` (off by default); with calibration disabled, routing relies solely on the LLM classifier's own confidence output.
```

- [ ] **Step 3: Fix the retrieval quality scoring claim**

Find (in the Quality Assurance section):
```markdown
2. **Retrieval quality scoring**: Batch relevance checks via Claude Haiku
```

Replace with:
```markdown
2. **Retrieval quality scoring**: `app/agents/rag/relevance.py` implements a local-LLM (Ollama) batch relevance scorer, but it currently has no callers anywhere in the request pipeline — retrieval results are not quality-scored in production today.
```

- [ ] **Step 4: Fix the Dynamic Top-K claim**

Find:
```markdown
- **Dynamic Top-K**: Query complexity determines retrieval depth (15-30 results)
```

Replace with:
```markdown
- **Dynamic Top-K**: A complexity-adaptive calculator exists (`app/retrievers/hybrid/adaptive_params.py`, effective range ~6-16 results) but is only wired into the ReAct tool-search path and the offline `candidate_collection.py` pipeline. The default knowledge-node retrieval path used for ordinary chat queries currently retrieves a fixed `k=6` per source.
```

- [ ] **Step 5: Fix the Tool Runner description**

Find:
```markdown
5. **Tool Runner** - Multi-hop reasoning (ReAct pattern)
```

Replace with:
```markdown
5. **Tool Runner** - Governed connector actions. Today this means one action: disabling a connected integration by name, matched via regex against the raw question (`app/agents/tool/service.py`). Multi-hop/ReAct-style tool reasoning is not implemented; an earlier unreachable implementation (`app/agents/tool/react.py`) was removed on 2026-08-29.
```

- [ ] **Step 6: Fix the Safety checks claim**

Find:
```markdown
4. **Safety checks**: Content filtering, bias detection
```

Replace with:
```markdown
4. **Safety checks**: Regex-based PII/secret redaction (API keys, private keys, SSNs, credit card numbers, passwords, emails, phone numbers) via `app/services/answer_safety.py` and `app/agents/validation/rules.py`. There is no content-moderation/toxicity filter and no bias-detection implementation.
```

- [ ] **Step 7: Fix the Claude Haiku technology-stack line**

Find:
```markdown
**Models**: OpenAI GPT-5.5 (primary, `OPENAI_CHAT_MODEL`), Claude Haiku (batch scoring), Sentence-Transformers (embeddings)
```

Replace with:
```markdown
**Models**: OpenAI GPT-5.5 (primary, `OPENAI_CHAT_MODEL`), Claude Haiku (multimodal image description/OCR triage in `app/services/multimodal/image_processor.py`; not used for retrieval-quality batch scoring, see Quality Assurance section), Sentence-Transformers (embeddings)
```

- [ ] **Step 8: Add a dated note recording this cleanup**

Immediately below the existing `Note (2026-08-28): tests/ and scripts/ were cleared...` paragraph, add:

```markdown
Note (2026-08-29): A backend agent audit found several components documented above
that no longer matched the running code — an orphaned router/clarification rewrite
(`app/agents/router/{enhanced_service,hybrid_clarification,accuracy,frontend_integration,validator,adapter,pipeline}.py`),
an orphaned RAG fusion/vector duplicate (`app/agents/rag/{fusion.py::fuse_evidence,enhanced_vector.py}`),
an orphaned second quality-scoring engine (`app/agents/validation/quality_orchestrator.py`),
and an unreachable ReAct tool loop (`app/agents/tool/react.py`). All were deleted; the
claims above were corrected to describe what actually runs today.
```

- [ ] **Step 9: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: correct CLAUDE.md claims found stale by the 2026-08-29 backend audit"
```

---

## Self-Review

**Spec coverage** — every "real bug" and "dead code" item from the audit that the user approved for this scope has a task:
- Citation regex bug → Task 1.
- Citation prompt contradiction → Task 2.
- Citation label source/document_id inconsistency → Task 3.
- Cascade level comment mislabeling → Task 4.
- Router dead cluster → Task 5.
- RAG fusion/enhanced_vector dead code → Task 6.
- quality_orchestrator.py dead code → Task 7.
- react.py (explicitly approved for deletion) → Task 8.
- CLAUDE.md corrections (clarification service, calibration file, retrieval quality scoring, dynamic top-k, tool runner, safety/bias, Claude Haiku) → Task 9.

Explicitly **not** in scope (per the user's chosen scope): enabling `CASCADE_ENABLE_LEVEL2`, wiring dynamic top-k into the live retrieval path, applying `hybrid_vector_weight`/`hybrid_bm25_weight`, or building a replacement for ReAct multi-hop tooling. These are feature-completion decisions, not bug fixes, and were explicitly excluded when the user picked "真 bug + 文档 + 清理死代码" over "全部，包括补齐未接线的功能".

**Placeholder scan** — no task contains "TBD", "add error handling", or unshown code; every edit shows exact before/after text; every deletion has an explicit re-verification grep step.

**Type consistency** — `_citation_label(source: str, page: int | None) -> str` in Task 3 matches the existing signature shape of the same-named function in `nodes.py`. No new public functions or types are introduced anywhere in this plan.
