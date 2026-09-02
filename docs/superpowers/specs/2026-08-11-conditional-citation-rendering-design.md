# Conditional Citation Rendering Design

## Problem

The synthesis layer always injects citation-first instructions and answer templates containing the literal placeholder `[doc_id:page]`. A query such as `hi` has no retrieved evidence, but the model still sees those instructions and can echo the placeholder as if it were a real citation.

The frontend already hides its citation panel when the backend returns an empty citation list. The defect is therefore in answer generation and citation validation, not in visual rendering.

## Required behavior

1. Retrieved evidence is the only source of truth for whether citations are available.
2. When evidence contains valid citation labels, synthesis must require factual claims to cite only those labels.
3. When evidence is empty, synthesis must not request citations or show citation examples/placeholders to the model.
4. Citation-like labels absent from the evidence allowlist must not survive in the final answer.
5. The same rules apply to synchronous and SSE streaming responses.
6. The existing `standard`, `strict_quality`, and `advanced` profile meanings must remain unchanged.
7. The frontend continues to render its citation section only when the backend citation array is non-empty.

## Design

### Evidence-aware prompt policy

The synthesis module derives the allowed citation labels from the actual vector, graph, and web contexts already passed through the RAGPipeline-compatible synthesis boundary.

- With evidence: use the existing citation-first system rules and query-type template, augmented with the concrete allowed labels. Explicitly forbid invented labels.
- Without evidence: use a no-evidence system instruction and omit citation templates, citation examples, and citation planning text. The model may answer conversational or general non-evidentiary questions normally, but must not emit citation syntax.

This policy is based on evidence presence, not on whether the query is classified as casual. A casual query with real evidence may still cite it; a non-casual query with no evidence must not invent citations.

### Output validation

After generation, citation-like markers are checked against the allowlist derived from evidence.

- Allowed markers are preserved exactly.
- Unknown markers, including `[doc_id:page]`, are removed without deleting surrounding answer text.
- Validation targets the repository's citation-marker grammar only; it must not remove ordinary Markdown links or arbitrary bracketed prose.
- If evidence exists but the answer omits every allowed citation, the existing typed synthesizer contract continues to reject the evidence-backed answer rather than fabricating a citation.
- When evidence is empty, the final citation metadata remains empty.

For SSE, the normal token stream is preserved. The completed answer is validated before completion; if normalization changed it, the existing `reset` event replaces the client-visible answer with the validated text. No new SSE event type or backend contract is introduced.

### Frontend behavior

No new frontend citation heuristic is introduced. `MessageCard` remains data-driven and renders the citation section only when `metadata.citations.length > 0`. This prevents the frontend from guessing whether bracketed text is a source and keeps the backend as the contract authority.

## Error handling and safety

- Citation cleanup never exposes backend stack traces or provider details.
- A malformed marker is treated as untrusted model output.
- Empty answers after normalization use the existing synthesis fallback behavior.
- Real document IDs and pages are retained; only non-allowlisted markers are removed.

## Tests

Add regression coverage proving:

1. `hi` with no evidence builds a prompt without `[doc_id:page]` and returns no placeholder citation.
2. A non-casual question with no evidence follows the same no-citation rule.
3. Evidence-backed synthesis preserves a valid `[document_id:page]` marker.
4. Evidence-backed synthesis removes or rejects an invented marker not in the allowlist.
5. Streaming output emits a final validated/reset answer when invalid markers were generated.
6. Existing citation-first tests and profile-specific synthesis tests remain green.

## Scope

Only the synthesis prompt selection, citation validation, and directly related tests are changed. RAGPipeline routing, retrieval, public API schemas, SSE event names, and frontend citation rendering contracts are not changed.
