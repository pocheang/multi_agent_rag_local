# Conditional Citation Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make synthesis show only citations backed by real RAG evidence and emit no citation markers when evidence is absent.

**Architecture:** Add a small citation-policy module shared by the legacy-compatible generator and the typed synthesizer service. Select evidence-aware or no-evidence prompts before model invocation, then validate generated citation markers against an evidence-derived allowlist for both synchronous and SSE responses.

**Tech Stack:** Python 3.11, FastAPI backend contracts, RAGPipeline-compatible synthesizer, pytest, Ruff.

## Global Constraints

- Retrieved evidence is the only source of truth for citation availability.
- Preserve `standard`, `strict_quality`, and `advanced` profile behavior.
- Do not change public routes, response schemas, or SSE event names.
- Do not add frontend citation heuristics; `MessageCard` remains driven by the backend citation array.
- Do not modify unrelated dirty-worktree files or commit implementation files that contain pre-existing user changes.
- Run every Python command through `conda run -n rag-local` (equivalent to activating the mandatory environment).

---

## File map

- Create `app/agents/synthesizer/citations.py`: extract evidence citation labels and normalize generated markers against an allowlist.
- Modify `app/prompts/core/canonical_agent_prompts.py`: add no-evidence generation and review prompts that contain no citation placeholders.
- Modify `app/agents/synthesizer/generation.py`: select prompts from evidence, include concrete allowed labels, and normalize sync/SSE answers.
- Modify `app/agents/synthesizer/service.py`: enforce the same allowlist at the typed FinalAnswer boundary.
- Modify `tests/test_agent_resilience.py`: generation and stream regression tests.
- Modify `tests/agents/test_synthesizer_context.py`: typed service valid/invalid/no-evidence citation tests.

### Task 1: Shared citation policy and synchronous synthesis

**Files:**
- Create: `app/agents/synthesizer/citations.py`
- Modify: `app/prompts/core/canonical_agent_prompts.py`
- Modify: `app/agents/synthesizer/generation.py`
- Modify: `app/agents/synthesizer/service.py`
- Test: `tests/test_agent_resilience.py`
- Test: `tests/agents/test_synthesizer_context.py`

**Interfaces:**
- Produces: `citation_labels_from_contexts(*contexts: str) -> frozenset[str]`
- Produces: `normalize_answer_citations(text: str, allowed_labels: Collection[str]) -> str`
- Consumes: existing context labels formatted as `^[label] content` by `SynthesizerAgentService`.

- [ ] **Step 1: Add failing no-evidence and allowlist tests**

Add tests that invoke the real synthesis functions with only the model boundary replaced:

```python
def test_synthesis_without_evidence_omits_prompt_placeholders_and_cleans_model_output(monkeypatch):
    seen = {}

    class FakeModel:
        def invoke(self, messages):
            seen["messages"] = messages
            return types.SimpleNamespace(content="Hello! [doc_id:page]")

    monkeypatch.setattr(synthesis_agent, "get_chat_model", lambda temperature=None: FakeModel())
    result = synthesis_agent.synthesize_answer("hi", "answer_with_citations", profile="standard")

    assert "[doc_id:page]" not in str(seen["messages"])
    assert result["answer"] == "Hello!"
```

Add a second test with `vector_context="[guide:7] RAG definition"` and model output `"RAG [guide:7]. Wrong [fake:99]."`; assert `[guide:7]` remains and `[fake:99]` does not.

Add typed service tests where evidence-backed output contains one valid and one invented marker, and where an empty evidence bundle returns a marker-free answer with empty citations.

- [ ] **Step 2: Run RED tests**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'
conda run -n rag-local pytest tests/test_agent_resilience.py tests/agents/test_synthesizer_context.py -k "citation or evidence or placeholder" -v
```

Expected: failures show that no-evidence prompts contain `[doc_id:page]` and invented markers survive.

- [ ] **Step 3: Implement the shared citation policy**

Create `citations.py` with line-anchored context extraction and marker normalization. Only citation-shaped colon markers and concrete allowlisted labels are treated as citations; ordinary Markdown links and arbitrary bracketed prose must remain untouched.

```python
import re
from collections.abc import Collection

_CONTEXT_LABEL_RE = re.compile(
    r"(?m)^\s*\[([A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)?)\]\s+\S"
)
_CITATION_MARKER_RE = re.compile(
    r"\[([A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+)\]"
)

def citation_labels_from_contexts(*contexts: str) -> frozenset[str]:
    """Return labels from leading `[label] content` evidence records."""
    combined = "\n".join(str(context or "") for context in contexts)
    return frozenset(match.group(1) for match in _CONTEXT_LABEL_RE.finditer(combined))

def normalize_answer_citations(text: str, allowed_labels: Collection[str]) -> str:
    """Preserve allowed citations and remove non-allowlisted citation markers."""
    allowed = frozenset(str(label) for label in allowed_labels)
    normalized = _CITATION_MARKER_RE.sub(
        lambda match: match.group(0) if match.group(1) in allowed else "",
        str(text or ""),
    )
    normalized = re.sub(r"[ \t]+([,.;:!?，。；：！？])", r"\1", normalized)
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    return normalized.strip()
```

The normalizer must turn `"Hello! [doc_id:page]"` into `"Hello!"`, preserve `"RAG [guide:7]"` when `guide:7` is allowed, and leave `[OpenAI](https://openai.com)` unchanged.

- [ ] **Step 4: Add no-evidence prompts**

In `canonical_agent_prompts.py`, add `NO_EVIDENCE_ANSWER_PROMPT` and `NO_EVIDENCE_REVIEW_PROMPT`. They retain language, safety, privacy, direct-answer, and no-fabrication rules but contain no citation syntax, examples, or citation-planning instructions.

- [ ] **Step 5: Integrate synchronous prompt selection and validation**

In `generation.py`:

1. Derive `allowed_labels` from vector, graph, and web contexts once per synthesis call.
2. Use `ANSWER_PROMPT`/`REVIEW_PROMPT` only when `allowed_labels` is non-empty.
3. Otherwise use the no-evidence prompts and omit `get_answer_template()` plus citation-oriented chain-of-thought text from the human prompt.
4. For evidence-backed prompts, append the concrete allowed markers so the model cannot substitute invented sources.
5. Normalize the final answer after optional self-review; if normalization produces an empty string, return the existing fallback.

In `service.py`, normalize generated text against labels built directly from `EvidenceBundle`. Retain the existing error when evidence exists but no valid visible citation remains.

- [ ] **Step 6: Run GREEN tests**

Run the Step 2 command again. Expected: all selected tests pass.

### Task 2: SSE completion normalization and regression verification

**Files:**
- Modify: `app/agents/synthesizer/generation.py`
- Modify: `tests/test_agent_resilience.py`

**Interfaces:**
- Consumes: `normalize_answer_citations()` and `citation_labels_from_contexts()` from Task 1.
- Produces: existing stream items only: text chunks plus optional `{"type": "reset", "content": str}` and metadata; no new event type.

- [ ] **Step 1: Add a failing split-marker stream test**

Use a fake model whose `stream()` returns `"Hello! "`, `"[doc_id:"`, and `"page]"`. Assert the completed event sequence includes a reset to `"Hello!"` and contains no final invalid citation. Add an evidence-backed stream case proving `[guide:7]` survives while `[fake:99]` is removed in the final reset.

- [ ] **Step 2: Run stream tests to verify RED**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'
conda run -n rag-local pytest tests/test_agent_resilience.py -k "stream and citation" -v
```

Expected: the current stream finishes with the raw invalid marker and emits no corrective reset.

- [ ] **Step 3: Normalize completed SSE answers**

After joining streamed chunks and completing optional review, normalize the final text with the same allowlist as synchronous synthesis. If it differs from the raw streamed answer, emit the existing reset item. Preserve detected-language metadata and all existing exception/fallback behavior.

- [ ] **Step 4: Run focused and neighboring tests**

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'
conda run -n rag-local pytest tests/test_agent_resilience.py tests/agents/test_synthesizer_context.py tests/agents/test_synthesis_citation.py tests/pipeline -v
conda run -n rag-local ruff check app/agents/synthesizer/citations.py app/agents/synthesizer/generation.py app/agents/synthesizer/service.py app/prompts/core/canonical_agent_prompts.py tests/test_agent_resilience.py tests/agents/test_synthesizer_context.py
```

Expected: focused tests and target Ruff checks pass.

- [ ] **Step 5: Validate frontend compatibility and task diff**

```powershell
Set-Location frontend
npm.cmd test -- --run
npm.cmd run build
Set-Location ..
git diff --check -- app/agents/synthesizer/citations.py app/agents/synthesizer/generation.py app/agents/synthesizer/service.py app/prompts/core/canonical_agent_prompts.py tests/test_agent_resilience.py tests/agents/test_synthesizer_context.py
```

Expected: frontend tests/build pass and the task-scoped diff has no whitespace errors.

- [ ] **Step 6: Runtime verification**

Restart or allow Uvicorn reload, verify `/health` returns 200, then invoke real configured synthesis for `hi` and assert the final answer contains neither `[doc_id:page]` nor any non-allowlisted citation marker. Do not print API keys or raw credentials.

- [ ] **Step 7: Independent review**

Sol must inspect the complete task-scoped diff and verify prompt selection, allowlist correctness, Markdown preservation, sync/SSE parity, typed service enforcement, profile preservation, tests, and runtime evidence. Any Blocker, High, or correctness-impacting Medium finding returns to Terra for a focused TDD repair and Sol re-review.
