# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

**Conda Environment**: `rag-local` (Python 3.11+)

All operations must use this conda environment:
```bash
conda activate rag-local
```

## Project Information

**Name**: QueryMind（智询）  
**Version**: 0.6.2.1  
**Language Support**: Bilingual (Chinese/English) via i18next  
**License**: MIT

## Common Commands

### Backend

**Start Development Server**
```bash
uvicorn app.api.main:app --reload --port 8000
# Alternative entry point:
uvicorn app.main:app --reload --port 8000
```

**Linting and Formatting**
```bash
ruff check .                        # Lint check
ruff format .                       # Format code
```

Note (2026-08-28, counts refreshed 2026-09-04): `tests/` and `scripts/` were cleared ahead
of the v0.7 rewrite. `scripts/` was down to one file then and holds six now — `audit/frontend_audit.py`,
`check_lock_wheels.py`, `check_sensitive.py`, `create_admin.py`, `eval_retrieval.py`,
`verify_config_centre.py` — each added with the thing it verifies, and still no
`scripts/init_db.py`. `tests/` is being rebuilt incrementally alongside bug fixes — see
Testing Strategy below.

**Tests and lint**
```bash
make test                           # pytest -q
make lint                           # ruff check . && ruff format --check .
```

**Optional services and offline evaluation**
```bash
make up                             # start Neo4j for local dev (Browser on :7474)
make down                           # stop it
make eval-retrieval                 # BM25 retrieval quality over config/eval/ (no model needed)
```

Note (2026-08-29): A backend agent audit found several components documented above
that no longer matched the running code — an orphaned router/clarification rewrite
(`app/agents/router/{enhanced_service,hybrid_clarification,accuracy,frontend_integration,validator,adapter,pipeline}.py`),
an orphaned RAG fusion/vector duplicate (`app/agents/rag/{fusion.py::fuse_evidence,enhanced_vector.py}`),
an orphaned second quality-scoring engine (`app/agents/validation/quality_orchestrator.py`),
and an unreachable ReAct tool loop (`app/agents/tool/react.py`). All were deleted; the
claims above were corrected to describe what actually runs today.

Note (2026-08-29, second pass): A full-backend audit found the chat path was not
persisting messages, conversation context was filled but never read, the query
endpoint never returned its execution_id, the `graph` route never queried the
graph, and 184 modules (~13,000 lines) had zero importers. All were fixed or
deleted; `app/` went from 583 to 371 Python files and Settings from 261 to 216
fields. Those are what the audit left behind, not a ceiling — today it is 379 files and
244 settings fields (2026-09-04). See `docs/superpowers/plans/2026-08-29-backend-full-audit-remediation.md`
for the plan, what was deliberately left dormant, and what remains open.

### Frontend

**Start Development Server**
```bash
cd frontend
npm install                         # First time only
npm run dev                         # Starts Vite dev server (port 5173)
```

**Build for Production**
```bash
cd frontend
npm run build                       # TypeScript compile + Vite build
npm run preview                     # Preview production build (port 4173)
```

**Checks and visual verification**
```bash
cd frontend
npm run lint                        # eslint, gates on errors (warning ratchet: 25)
npm run type-check                  # tsc -b --noEmit
npm run lint:design                 # shape/depth scale ratchet (see Frontend styling)
npm test -- --run                   # vitest (.test.ts and .test.tsx)
npm run screenshots                 # both servers up; PNGs of 8 app states
```

CI runs everything above except `screenshots`, which is a local before/after tool
by design — see [Frontend styling](#frontend-styling-adopted-2026-08-31) for when to
reach for which.

### Docker Deployment

```bash
export OPENAI_API_KEY="your-api-key"
./deploy/scripts/deploy.sh production balanced
```

Configuration lives in `config/` and runtime files in `.runtime/`.

## Architecture Overview

### Pragmatic RAG System in Transition

This is a **working RAG system** built on proven components (LangChain, ChromaDB, FastAPI). The system evolved from a multi-agent LangGraph architecture and is currently in a **transition state** - core functionality is stable, but the architecture is being incrementally modernized.

**Current architecture**: Legacy retrieval and synthesis components wrapped with adapter services for cleaner interfaces. The `RAGPipeline` provides the public API, while `OrchestrationEngine` coordinates execution flow.

**What works well**: Retrieval quality, answer synthesis, bilingual support, session management.

**What's being improved**: Service boundaries, configuration management, error handling consistency.

### Core Components

The system has **3 primary components** and **3 optional components**:

**Primary (always active)**:
1. **Router** ([app/agents/router/service.py](app/agents/router/service.py))
   - Query intent classification and route selection

2. **Retriever** ([app/agents/rag/service.py](app/agents/rag/service.py))
   - Hybrid search: vector (ChromaDB) + BM25 + reranking
   - Optional: Knowledge graph (Neo4j), web search

3. **Synthesizer** ([app/agents/synthesizer/service.py](app/agents/synthesizer/service.py))
   - Citation-first answer generation from evidence

**Optional (route-dependent)**:
4. **Planner** - Task decomposition for complex queries
5. **Tool Runner** - Governed connector actions, selected by a model from a
   schema-declared catalogue (`app/agents/tool/selector.py` + `service.py`,
   reworked 2026-08-30). Two actions are registered (2026-09-04): a `read` that
   lists the caller's own connectors (`querymind_connector_list_owned`) and a
   `write` that disables one (`querymind_connector_disable_owned`). The read is
   what makes the loop worth having -- it is how the model finds the id of a
   connector before acting on it, and `operation="read"` skips approval entirely
   so it costs the user no confirmation. Its summary is composed from
   `connector_id` and `status` alone, never `ConnectorView.name`: a read-only
   tool's summary *is* fed back as a `ToolObservation`, `name` is user-authored
   free text, and a summary built from a `^[a-z][a-z0-9_-]{0,63}$` id and a
   two-value Literal is structurally incapable of carrying an instruction. That
   is what makes the read-then-write composition safe rather than untested, and
   `tests/security/test_connector_list_tool_scoping.py` pins it. Selection is **multi-step**: select → invoke → observe → repeat,
   bounded by `TOOL_MAX_STEPS` (default 3) and by the shared
   `STAGE_TIMEOUT_TOOL_MS` ceiling. The loop stops on anything other than a clean
   success — an `approval_required` result means the action has *not* happened,
   so planning a next step on top of it would be reasoning from a false premise —
   and it stops if the model repeats a call it already made.

   **The selector is deliberately blind to retrieved content.** Its inputs are
   the user's question, the conversation, and the tool catalogue; it takes no
   `EvidenceBundle`/`ContextBundle`, and `ToolRunner` no longer receives evidence
   either, so there is no argument to pass by mistake. Retrieved chunks are
   attacker-controllable the moment one user can put a document where another
   user's query will retrieve it, and a model that chose tools from them would
   put this system in the middle of the lethal trifecta. While selection was a
   regex over the question this was true by accident;
   `tests/security/test_tool_selection_is_evidence_blind.py` makes it a property.
   If a tool ever genuinely needs retrieved content, that is a deliberate change
   with its own threat model.

   **Feeding results back re-opens that question one layer down**, which is what
   `ToolRisk == "open_world"` now answers: such a tool reaches content this
   system does not control, so its summary is somebody else's writing and
   contributes only its id and status to the next decision, never its text
   (`app/agents/tool/service.py::_observation`). Every tool registered today
   composes its own summary, so today they all contribute it.

   Arguments come from a model now, so `ToolDefinition.parameters` (name,
   required, `max_length`, `pattern`) is the only thing between it and the
   executor; `ToolRegistry.invoke` validates against it before spending an
   approval round trip, and `ToolRegistry.catalog(actor)` only offers tools the
   actor is authorized to run.

   A `write` tool always returns `approval_required` on its first call; the
   caller confirms and re-sends with the token. See "Governed tool stack" below.
6. **Finalizer** - Quality validation and safety checks

### Pipeline Profile

The system runs a single profile, **advanced** (web research and full quality
validation). `ExecutionPolicy.for_profile` in `app/orchestration/policies.py` is the
only place that decides what a profile enables. A parallel set of descriptors in
`app/pipeline/profiles.py` (`ProfileCapabilities`, `CapabilityBudget`,
`PROFILE_DEFINITIONS`) had no readers and had drifted into contradicting the policy;
it was deleted on 2026-08-29, leaving only the `PipelineProfile` enum.

### Execution Flow

```
Request → RAGPipeline.execute()
   ↓
OrchestrationEngine
   ↓
1. Router → determines query type and route
2. Planner → (optional) decomposes complex queries
3. Retriever → gathers evidence from vector/BM25/graph/web
4. Tool Runner → (optional) multi-step governed tool loop, react route only
5. Synthesizer → generates answer with inline citations
6. Finalizer → (optional) validates quality and safety
   ↓
PipelineResult → returned to caller
```

**Note**: Steps 2, 4, 6 are conditionally executed based on route and profile settings. The flow is sequential with concurrent retrieval from multiple sources in step 3.

### Quality Assurance

**Validation layers** (applied based on profile):
1. **Route confidence checks**: Threshold-based validation
2. **Retrieval quality scoring**: none. A local-LLM (Ollama) batch relevance scorer existed in `app/agents/rag/relevance.py` with no callers anywhere in the request pipeline; it was deleted on 2026-08-29. Retrieval results are not quality-scored.
3. **Answer validation**: Citation completeness, hallucination detection, NLI checks
   (**switched on 2026-09-04; before that this line was false**, see below), and
   **sentence grounding** — `apply_sentence_grounding`
   (`app/services/retrieval/citation_grounding.py`), reached from
   `app/orchestration/finalization.py`, scores each sentence's token overlap with the
   evidence and hedges the ones under 0.22. It skips sentences that make no claim, which is
   not a nicety: it once counted a bare `[1]` as a sentence, found it unsupported, and
   hedged the attribution instead of the claim.

   **The NLI stage had never run, and three separate defects meant turning it on would
   have been worse than leaving it off** (all fixed 2026-09-04). The switch was
   `CASCADE_ENABLE_LEVEL2`, defaulting false — and the numbering was itself wrong:
   `enable_level2` gated NLI while `enable_level3` gated the citation check, so reading
   the configuration told you the opposite of what ran. The switches are named for their
   stages now (`CASCADE_ENABLE_RULES` / `_CITATIONS` / `_NLI` / `_DEEP`), and two of the
   four timeout settings were deleted because nothing consumed them — note that
   `test_settings_have_readers` passed for both, since **assigning a field to an attribute
   nobody reads counts as a reader**.

   The three defects, in increasing order of how badly they would have hurt:

   - **It blocked the event loop.** `model.predict` — a synchronous cross-encoder forward
     pass — ran directly inside `async def`, with no `to_thread`, no timeout and no
     breaker; the loader ran there too, without `local_files_only=True`, so a machine
     without the model would have started an untimed download inside a request. It now
     copies `rerank_evidence` exactly: sync core, `wait_for(to_thread(...))`, circuit
     breaker, deterministic fallback.
   - **The deterministic fallback could not score Chinese.** It tokenised with `\w+`, and
     `\w` matches CJK, so a whole clause became one token. Measured: a verbatim clause
     copy scored 1.00, but a paraphrase, a recombination of two sources, and an added
     connective all scored **0.00** — and synthesis paraphrases by construction. A 0.00
     becomes `factuality < 0.7`, then a retry, then a rejected answer.
   - **The scoring was inverted.** The code read `scores[:, 2]` as the entailment column,
     but the configured model's `id2label` is `{0: contradiction, 1: entailment,
     2: neutral}` — column 2 is *neutral* — and those are raw logits that were clamped
     into [0,1] rather than softmaxed. Measured against the real model: an entailed
     sentence scored **0.000** and an unrelated one **0.894**. The column now comes from
     the model's own `id2label` (so a different `NLI_MODEL_NAME` still works) and the row
     is softmaxed: 0.993 / 0.001 / 0.000 for entailed / contradicting / unrelated.

   **The model is English and the system is bilingual**, so the cross-encoder runs only on
   predominantly-Latin text; everything else takes the repaired deterministic path.
   `CascadeResult.backend` records which ran and `validation_method` reports
   `standard_lexical` rather than `standard` when it was not the cross-encoder — a method
   name that claims a check happened when it did not is the failure this file keeps
   describing. Shipping a Chinese-capable NLI model is a separate evaluation project.

   `CASCADE_*` is not in `config_schema.py`, but the reason changed on 2026-09-04. It
   used to be that `_get_validation_cascade` caches a module-global `ValidationCascade`
   that `apply_config_reload` did not clear, so an admin edit would have reported success
   and changed nothing until restart. `clear_validation_caches()` now runs in the reload
   sequence -- dropping the cascade *and* the `lru_cache`d NLI model, which is keyed on
   `NLI_MODEL_NAME` -- so that blocker is gone and whether to expose these is now an
   ordinary decision about what an operator should be able to change mid-flight, not a
   workaround for a stale cache.
4. **Safety checks**: one pattern set, `app/services/security/outbound_redaction.py`,
   enforced at three points. Matches become stable `<KIND_n>` tokens, so the same value
   twice in one text gets the same token and the model can still reason about "that
   number" — and the counts returned to the caller never carry the matched value.

   | boundary | where | default |
   |---|---|---|
   | the question | `privacy_permission` node, `inspect_input` | mandatory, no `on_timeout` |
   | LLM + embedding egress | the model wrapper, `redact_messages_for_provider`, external providers only | `OUTBOUND_LLM_REDACTION_ENABLED` / `..._EMBEDDING_...`, both true |
   | the answer | `output_filter` node, `filter_output` | a `MANDATORY_STAGES` member |

   `app/services/answer_safety.py` (OpenAI-style keys, AWS key ids, private-key headers,
   `password=`/`token=`) is not a rival set: `filter_output` composes it with the shared
   one. `app/agents/validation/rules.py` does keep its own SSN/credit-card/email/phone
   patterns, and runs inside the validation cascade reached through the verifier.

   **China-specific identifiers were added on 2026-09-04, and there were none before
   that.** Resident ID cards, bank cards and mainland mobile numbers were caught anyway —
   all three are long digit runs, so the generic `PHONE` rule swallowed them — but every
   one was *reported* as a phone number, which makes a privacy finding describe something
   that did not happen, and a passport number (eight digits, one under that rule's
   minimum) was reported as nothing at all. `ID_CARD_CN`, `MOBILE_CN`, `BANK_CARD`,
   `PASSPORT_CN` and `USCC_CN` now match ahead of `PHONE`, which is load-bearing: patterns
   apply in order and the first to match owns the span, so a specific rule placed after
   the generic one is indistinguishable from not having written it. IPv6 landed in the
   same pass; only IPv4 had been covered.

   Order matters *among* the specific rules too, and the first attempt got it wrong in
   both directions. `USCC_CN` ahead of `BANK_CARD` claimed every 18-digit order number as
   a company registration, because the credit-code alphabet includes digits; putting the
   digits-only rule first fixes it, since a real credit code carries letters. Then
   `BANK_CARD`'s right boundary of `(?!\d)` turned out to be satisfied by a *letter*, so
   it took the seventeen leading digits out of a credit code ending in its checksum letter
   — the boundary has to be non-alphanumeric. And `[EGDSPH]` plus eight digits is also how
   a dated document id is written (`E20260904`), so the passport rule excludes eight
   digits that read as a calendar date: a passport number that happens to spell a recent
   date is rare, and redacting every document reference of that shape corrupts text the
   model has to reason about.

   All three came out of an adversarial false-positive pass, and none of them would have.
   The first such pass reused inputs already known to be clean, so it reported zero
   findings and could not have reported anything else — the same defect as a secret
   scanner nobody has watched fail. `tests/security/test_chinese_pii_redaction.py` pins
   each one.

   **A kind must be added in two places.** `redact_sensitive_text` skips anything outside
   `allowed_kinds`, and those sets are `PII_KINDS`/`INPUT_KINDS`/`OUTPUT_KINDS` in
   `app/privacy/text.py`. A pattern added only to `outbound_redaction.py` compiles, reads
   correctly and matches nothing; `test_every_pattern_kind_is_reachable` is the guard.
   `URL` is the one kind deliberately in `INPUT_KINDS` and not `OUTPUT_KINDS` — an answer
   keeps its links.

   `app/agents/rag/web.py::_sanitize_query` used to be a fourth set, seven hand-written
   patterns, and the weakest: it missed a mainland mobile number (eleven digits, under its
   13-digit card threshold), an API key, a Bearer token, an internal URL and a Windows
   path. It never leaked, because `privacy_permission` redacts the question before the web
   retriever sees it — which is exactly why it was worth deleting rather than extending. A
   boundary that only appears to be guarded is worse than an unguarded one: weakening the
   layer that does the work would have shown up there as nothing at all. It now calls the
   shared redactor, and the second pass is kept because a search engine is outside every
   agreement this system has.

   **Still not covered, deliberately or otherwise**: names, street addresses, licence
   plates; no content-moderation/toxicity filter and no bias detection. Uploaded documents
   are never inspected — `app/services/documents/` calls nothing from `app/privacy/` — so
   chunks sit raw in ChromaDB, BM25 and on disk, and `mask_evidence` redacts at *read*
   time. That is defensible (it is the user's own document, in their own tenant, and they
   have to be able to read it back) but it means a scope-resolution bug exposes original
   text rather than redacted text. And `privacy_permission` inspects `request.question`
   only: the API persists the raw query into session history and feeds it back as
   conversation on the next turn, so input redaction is per-turn. Egress is still covered
   by the wrapper above; what makes this worth watching is `QUERY_REWRITE_WITH_LLM`, false
   today, which is what would let that history reach a retrieval query.

**Skills shape the answer** (wired 2026-08-31). The router picks one of nine skills per
query and `RouteDecision.skill` has always carried the choice, but nothing read it:
`SynthesizerAgentService` hardcoded `answer_with_citations`, and `skill_name` reached the
model as a bare header line with no content behind it.

`app/agents/synthesizer/skills.py` is the one place that decides what a skill means, and it
**selects** a template rather than adding one. `templates.py` already infers a *query type*
from the question by keyword and puts its template in the prompt; a parallel set of skill
templates would have put two competing answer shapes in front of the model. Skill and query
type answer the same question, and the skill is the better answer — an LLM read the whole
question, `infer_query_type` matches a keyword list. So:

- six skills have a shape of their own (`timeline_builder`, `web_fact_check`,
  `incident_response_playbook`, `cyber_attack_analysis`, `cyber_defense_hardening`,
  `pdf_text_reader`);
- `compare_entities` maps onto the existing `COMPARISON_TEMPLATE`, which means an
  LLM-detected comparison now reaches it even when the wording carries none of the keywords
  — the same "the route is an instruction, not a hint" reasoning as on the retrieval side;
- `answer_with_citations` and `ai_knowledge_assistant` state no shape and keep today's
  question-based inference, as does an unrecognised skill.

Every authored template teaches the internal `[E{k}]` marker, never `[1]`: `output_filter`
renumbers after DLP settles which citations survive, so a template teaching reader-facing
numbers would teach the model to invent numbering the pipeline then overwrites.
`tests/agents/synthesizer/test_skill_templates.py` checks the three sets partition
`VALID_SKILLS`, so a skill added to the router without guidance fails the suite.

**Citation-First Principle**: Factual claims must carry an inline citation during
generation. Two marker formats are involved and they are not interchangeable:

- `[E1]`, `[E2]` … are the **internal** evidence markers. `ContextBuilder` renders one in
  front of each excerpt (`app/knowledge/context.py::_render_item`), the prompts teach that
  form, and `normalize_answer_citations` allow-lists it, so `[E{k}]` always names an exact
  position in the evidence list.
- `[1]`, `[2]` … are what the **reader** sees. `output_filter`
  (`app/orchestration/langgraph/nodes.py`) rewrites the internal markers via
  `number_evidence_markers` and appends the numbered reference list, so entry *n* is what
  `[n]` in the text points at.

The rewrite happens in `output_filter` and nowhere earlier, because that is the first stage
that knows which citations survive DLP: a marker whose evidence the filter dropped is
removed rather than left pointing at nothing. It used to live only in
`SynthesizerAgentService.synthesize()`, which the LangGraph path never calls, so `[E1]`
reached the browser verbatim with no legend.

Numbering is by **first appearance in the answer**, not retrieval order, and two excerpts
that render as the same reference line (same `source`, same `page`) share one number.
`EvidenceBundle.items` comes back from `output_filter` in that same order, which is what
lets `RAGPipeline` set `PipelineCitation.marker` by enumeration.

`EvidenceRef.version` is optional on purpose, mirroring `EvidenceItem.version`: web results
and graph context are real evidence with no version to point at. Requiring one there meant
every marker aimed at them was silently dropped, so a web-routed answer returned no
citations at all and finished `degraded`.

**Self-RAG runs where the caller asks for it, and nowhere else** (2026-09-03).
`_run_self_rag_evaluation` in `app/api/routes/public/query.py` is the only Self-RAG there
is: it awaits `SelfRAGEvaluator` properly and is gated by the request's `enable_self_rag`.
There used to be a second one in `app/agents/rag/vector.py` -- a `_evaluate_retrieval` that
returned `{"enabled": True, "evaluated_count": N}` beside a comment saying the real
implementation would be async. It had never run: the agent's one construction site supplies
no `llm_client`, so the evaluator was always `None`; the branch was additionally gated on
`VectorRAGConfig.enable_evaluation`, default false; and `run_vector_rag` rebuilt the result
from five keys, dropping `evaluation` anyway.

Connecting it was never the option: the evaluator's methods are coroutines, `execute` is
synchronous and reached from `asyncio.to_thread`, and driving a coroutine from there is the
defect already fixed twice in this repository. It is deleted, along with the config field
`GET /api/advanced-rag/config` was reporting as `self_rag.enabled_by_default` -- a field
that gated nothing, reading `false` for the same reason the real switch does, which is why
nobody noticed. That endpoint now reports the request flag, and
`tests/api/test_advanced_rag_config.py` asserts each key follows the thing that gates it
rather than asserting a value.

**Dormant by design (2026-08-29)**: the following exist and are reachable but are
switched off on the live request path. Turning any of them on is a cost/latency
decision, not a bug fix — do not "fix" them by flipping the flag.

- **Fact verification and self-review**: `app/agents/synthesizer/service.py` calls
  `synthesize_answer(..., enable_fact_verification=False, enable_self_review=False)`.
  Fact verification is now switchable without a code edit
  (`ANSWER_FACT_VERIFICATION_ENABLED`, default false) **and works when switched
  on**: the synthesizer passes it the structured evidence directly. It used to
  rebuild source documents by regexing `[doc_id:page]` out of the rendered
  context -- a form retired when ContextBuilder moved to `[E{k}]` -- so it
  verified every answer against an empty list and reported perfect groundedness.
  With no source documents it now skips rather than passing vacuously.
- **Router confidence calibration**: `ENABLE_CALIBRATION` defaults to false, and
  turning it on now does something. The loop was closed on 2026-08-30:
  `_record_routing_outcome` (in the verifier node) feeds `record_routing_feedback`,
  which previously had no caller anywhere. Only outcomes *attributable to routing*
  are recorded -- retrieval finding nothing is the route's fault, retrieval finding
  plenty and the verifier approving is to its credit, and a degraded answer that
  had evidence is somebody else's failure and records nothing.
  `RouteDecision.raw_confidence` exists to carry the pre-calibration value that
  far; feeding the calibrated one back would train the calibrator on its own
  output. Accumulated outcomes live at `ROUTER_CALIBRATION_PATH` under `data/`,
  seeded once from the tracked `config/router_calibration.json`, and are flushed
  every 20 records -- the calibrator used to rewrite that tracked file
  synchronously on every request.
- **Clarification round caps**: derived from the number of fields each intent
  actually has questions for (`rules.py::_REQUIRED_FIELDS`), not hand-written.
  The old table said 7 for `rag_design`, which has four fields, so the cap could
  never be reached and the UI promised three rounds that do not exist.
- **Enhanced graph lookup**: `GRAPH_RAG_ENHANCED` defaults false, so the graph route uses
  `app/tools/graph/core.py::graph_lookup`. Until 2026-08-31 the switch was not dormant but
  *broken* — `_run_graph_rag_impl` required `retrieved_docs` to enter the enhanced branch and
  the one production caller had none, so all 495 lines of `app/agents/rag/enhanced_graph.py`
  were unreachable. It now works, and staying off is a cost decision: the enhanced lookup
  loops per entity (up to 5 neighbor queries + 3 path queries) where the basic one batches,
  so it trades roughly 3 Neo4j round-trips for up to 9 in exchange for better entity
  normalization, alias matching, quality-adaptive limits, and a low-quality skip that falls
  back to vector. Turning it on also turns on two-phase retrieval — see Retrieval Strategy.
  `ClarificationAgentService` advances the round when it *asks*; the session
  store used to be the only thing that advanced it, and only when the user
  answered, so a caller that re-asked without answering looped forever.

**Note**: Quality validation is controlled by `ExecutionPolicy`, not by per-profile
settings — see Pipeline Profile above.

### Governed tool stack

`app/mcp/runtime.py::get_tool_stack()` builds the approval store, registry,
gateway and connector service **once per process**, lazily. Both the FastAPI
container (`app/api/deps/runtime.py`) and the RAG pipeline
(`ToolAgentService`, resolved at call time so `CoreCapabilities()` stays cheap)
resolve that one stack.

Sharing is a correctness requirement, not a performance one: `ToolRegistry`
mints an approval token into *its* `ApprovalStore` and
`POST /api/v1/connectors/approvals/{token}` redeems it from whichever store the
FastAPI dependency hands out. Two stores means a token that can never be
redeemed. Before 2026-08-30 the API built its own stack and the pipeline had
none at all, so every pipeline tool call returned "tool system not initialized".

`ToolAgentService` resolves the stack on first *use* rather than at
construction: `CoreCapabilities` builds it by `default_factory`, and eager
construction would demand `API_SETTINGS_ENCRYPTION_KEY` of every test and script
that touches capabilities. Do not inject it via `RAGPipeline(tool_agent=…)`
either — that sets `_uses_default_capabilities` False and rebuilds the LangGraph
workflow per request (~20ms of synchronous CPU on the event loop).

**Approval is resumed by replay, not by checkpoint restore** (2026-08-30). A
`write` tool returns `approval_required` with a token; the run finishes normally
and `PipelineResult.status` becomes `pending_approval`. The client confirms at
`POST /api/v1/connectors/approvals/{token}` and then **re-sends the same query
with `approval_token`**. That second run re-executes from the top and its tool
stage replays the approved call.

Replay rather than a LangGraph checkpointer, on purpose: re-running means
`privacy_permission` **re-resolves** the caller's access scope instead of
restoring one captured before the pause. Permissions can change while a human
looks at a confirmation dialog, and a checkpoint restore would have replayed the
stale scope silently. It also avoids a new persistence store, conversation-scoped
thread semantics, and TTL cleanup. The cost is one extra retrieval + synthesis,
only on the approval path. **The `checkpointer` parameter on
`OrchestrationEngine`/`build_workflow` is still never passed and this design does
not need it — do not assume that path works.**

Resume does **not** re-run tool selection: `ApprovalStore.approved_call` rebuilds
the exact call from the approval record. A model re-reading the same question is
not obliged to choose the same call, and the approval has to authorize the action
the user was shown.

`_call_fingerprint` no longer includes `execution_id`. It used to, which made a
token structurally unredeemable — every chat turn is a new execution, so the
retry's fingerprint could never equal the approved call's. Approval still binds
to one actor, is single-use, and expires in 5 minutes.

Before this the loop was broken in three independent places: the frontend
approved a token and then only cleared its panel, `OrchestrationRequest` had no
field to carry a token back, and the fingerprint could not match.

**Connector storage is persisted** (2026-08-30). `ConnectorMetadataRepository`
and `CredentialRepository` were process-local dicts, which was survivable only
while the tool path could not execute anything: a restart silently emptied every
user's integrations, and a connector configured on one worker was invisible to
the next. Both are now SQLite tables in `APP_DB_PATH`, following the store
pattern the rest of the app uses (own connection per call, schema on
construction) rather than a shared pool, which this codebase deliberately does
not have.

Both tables carry `owner_id REFERENCES users(user_id) ON DELETE CASCADE`, so a
deleted account cannot leave behind an encrypted secret. `create` relies on the
primary key rather than read-compare-write under a lock, which only ever made
the race single-process.

**The encryption key now has to outlive the process too.** Ciphertext is what
gets stored, so persisting it does not widen what a database read exposes — but
rotating or regenerating `API_SETTINGS_ENCRYPTION_KEY` turns stored credentials
from *absent* into *undecryptable*.

### Upload storage

`store_uploaded_files` (`app/services/documents/dedup.py`) is the front door for user
documents, and three of its decisions outlive the request. The directory a file lands in
(`uploads_path/<owner_user_id>/`) is what document visibility falls back to for rows
indexed before owner metadata existed; the visibility it resolves is what the row is
indexed with; and the hash it computes is what stops the same file being stored twice.

Two rules worth keeping in mind before changing it. **Public needs an approval that is
exactly `True`** -- a missing answer is not a yes, and this is the last place a private
document can stop being private. And **an index row is not evidence that a file exists**:
`_existing_duplicate` re-hashes the stored copy before telling a request it already has
the file, because the index can outlive what it points at.

`tests/security/test_upload_storage.py` pins the refusals, which are the direction that
fails open.

### User Data Isolation

Retrieval is scoped, not just filtered afterwards (fixed 2026-08-30). Two properties
carry it, and both are pinned by `tests/security/`:

- `privacy_permission` (`app/orchestration/langgraph/nodes.py`) resolves the caller's
  `AccessScope` and **rewrites `request.source_scope` from it**, so no later stage can
  be handed a wider range than the resolver authorized — whatever the API layer passed.
  This is why `pipeline_contract.py` may still pass `allowed_sources=None` harmlessly.
- `similarity_search` fails closed: a missing `allowed_sources` raises rather than
  searching every tenant's corpus, and an *empty* one returns nothing. Those two cases
  must stay distinct — collapsing them is what previously turned "this user has no
  documents" into an unrestricted search.

`evidence_is_authorized` (`app/privacy/dlp.py`) remains the output-side check. `web` and
`tool` evidence is exempt (not user documents); `memory` is checked against the
`memory://{tenant}/{user}/` namespace its store already enforces, not against
`allowed_sources`, which only ever holds document paths.

Counts of scope-dropped evidence are logged, never returned: they would tell a caller
how many documents *other* tenants hold on a topic.

An **empty** document scope (a user who has uploaded nothing) and a **missing** one are
different states and must stay so. Empty drops the document-backed retrievers but keeps
web — web results are not documents — and returns quietly; missing raises. Collapsing
them in either direction is a bug: one way silently removes web search from every new
user, the other turns "a caller bypassed the resolver" into a result that reads as "no
matches found". `KnowledgeOrchestrator._retrieve_source` skips only
`vector`/`bm25`/`graph`/`wiki`/`multimodal` on an empty scope; `RAGAgentService.retrieve`
matches that list rather than short-circuiting ahead of it.

The store adds a second, independent check: `similarity_search` takes an `OwnerScope` and
requires the chunk's own `owner_user_id`/`visibility`/`tenant_id` metadata to match, not
just its `source`. Source paths are *derived* from the visibility rules; owner metadata is
written independently at ingest, so requiring both narrows what a wrong source list can
reach. **This means chunks indexed before ingest wrote owner metadata are invisible once
the clause is on — `$eq` does not match an absent key (verified on chromadb 1.5.9). Reindex
any pre-existing store before deploying.** Every `similarity_search` call site must pass an
owner; `tests/security/test_no_unrestricted_retrieval.py` enumerates them via AST and keeps
the one genuinely caller-less site in a documented allowlist -- the offline evaluation
harness, which has no request and no user. A partial guard would be worse than none. The
second entry was `candidate_collection`'s default `vector_fn`, an ownerless
`similarity_search` kept out of reach by every live caller injecting an owner-bound
partial; `vector_fn` is required and defaultless now, so the module no longer reaches the
store at all and the entry is gone rather than reworded.

**The owner must survive every hop, not just the call site** (fixed 2026-08-30). The AST
guard only sees direct `similarity_search` calls, so it passed the whole time the graph
route was reaching the store through `run_graph_rag → _fallback_to_vector_rag →
run_vector_rag → hybrid_search_with_diagnostics → _safe_similarity_search`. Every hop wrote
`owner=owner`, which satisfies an AST check — but `_fallback_to_vector_rag` declared
`owner: OwnerScope | None = None` and two of its three callers relied on that default. Neo4j
is optional and an empty graph result is routine, so the *common* fallback searched with the
source filter alone and no ownership clause.

The fix is a shape, not a patch: on every function between a request and the store, `owner`
is **keyword-only with no default**, so omitting it is a `TypeError` rather than a silent
widening. `similarity_search` itself is the one exemption — it is where "no owner" is
interpreted. Two guards keep it that way: `test_no_retrieval_helper_defaults_its_owner_away`
(no `owner=None` default anywhere upstream) and
`test_no_module_passes_a_null_owner_without_saying_why` (writing `owner=None` requires an
`OWNERLESS_CALL_SITES` entry). `hybrid_search()` and `_collect_candidates()` were deleted in
the same pass: both were callerless and neither could take an owner, so each was a
ready-made way back to an ownership-blind search.

Documents are addressed by `document_id`, not filename: two users routinely hold a
`report.pdf`, so `/documents/{filename}` refuses whenever the name is ambiguous and
`/documents/by-id/{document_id}` is the form the frontend uses. A `?source=` query
parameter *narrows* the candidates a filename resolves to — it must never select one on
its own, which is what let an admin act on a file they could not even list. "No such
document" and "not yours" both return 404 on purpose: distinguishing them discloses that
someone else's document exists.

**Chinese tokenization is jieba plus character bigrams** (fixed 2026-09-04).
jieba's dictionary used to be the only vocabulary: single-character tokens were
dropped -- they carry almost no signal alone -- so a word the dictionary does not
know produced *nothing*. `年假` splits into two single characters, so it vanished
from the query and from the document alike and could never match. Measured over 30
realistic domain terms only one behaved that way, but it is a silent *total*
failure and the affected set is unpredictable.

The more common failure is worse than a miss: jieba emits a sub-word, and the
sub-word gets used as if it were the word. `陪产假` (paternity leave) tokenized to
exactly `产假` (maternity leave) -- an identical token set, so BM25 could not tell
them apart, and a query about one ranked the other first. That is a wrong answer,
not a missing one.

Bigrams over each CJK run fix both without a dictionary, and are added *alongside*
jieba's tokens so a known word keeps its whole-word match. Runs stop at
punctuation. Measured on `config/eval/`: MRR 0.9062 -> 0.9688.

**What it does not fix, and cannot**: asking about `产假` still ranks the `陪产假`
document first, because `产假` is genuinely a substring and BM25 rewards matches
without penalising a document for extra terms. That is the boundary of lexical
retrieval -- the production pipeline fuses BM25 with vector search, which the
BM25-only evaluation harness deliberately does not. It is pinned as
`KNOWN_LEXICAL_LIMITS` in `tests/evaluation/test_retrieval_metric.py`, with the
rank asserted exactly so an improvement fails the test as loudly as a regression.

BM25 keeps one prebuilt index per access scope (`_load_scoped_bm25`, LRU), and separates
matching from ranking: a document is a candidate if it shares a term with the query, and
BM25 only orders the candidates. Do not reintroduce `score > 0` as the membership test —
BM25 IDF is negative for a term present in most documents, so in a small scope (one chunk,
now a routine case) every term scores below zero and matching documents get dropped. A
negative `bm25_score` in the output is normal and harmless: RRF fuses on rank, not score.

### Audit log vocabulary

Action names have one definition, `app/services/security/audit_actions.py::AuditAction`
(added 2026-09-03). Forty-nine names are written at some seventy call sites across
`app/api`, read back by string comparison in `app/services/runtime/runtime_ops.py`, and
listed again in the admin console's filter — three lists that had to agree, with nothing
checking that they did.

**Unlike the permission vocabulary next door, a divergence here fails silently**, and two
had already happened when the enum was introduced. The console offered
`admin.user.create`, `admin.user.password_reset` and `admin.user.approval_token_reset`
against a backend that writes `create_admin`, `reset_password` and
`reset_approval_token`; the filter is a substring match, so four of its sixteen options
(`query.stream` was the fourth) could only ever return nothing. And `build_ops_alerts`
averaged the grounding ratio over rows with action `query.run`, which nothing has ever
written. A counter that matches no row reports zero and a filter that matches no row
reports "no results" — neither looks like a defect to anyone.

`StrEnum`, so members are strings: `sqlite3` and `json.dumps` both see `"auth.login"` and
no call site changed behaviour. What changed is that a name that does not exist is an
`AttributeError` at import.

`tests/security/test_audit_action_vocabulary.py` scans every module in `app/` for a
literal equal to any member — which is how twelve *positional* call sites in
`admin/users.py` turned up, passed to `handle_service_exception` and
`check_self_modification` rather than to `_audit` — and checks the console's list against
the enum, and that the list is declared once. It was declared twice in `frontend/src`,
identically, which is how the first divergence went unnoticed.

**The three `query.*` actions are written only when a query is *refused*.** No successful
query is audited, which is why nothing carries a per-answer quality metric — see Answer
quality telemetry under Important Notes for where that goes instead.

### Knowledge Agent and retrieval execution

**The Knowledge Agent is not an agent.** `app/orchestration/capabilities.py` constructs
`KnowledgeAgentService()` with no `decider`, so `_rule_strategy` -- a set of regexes over
the question plus the route's hints -- is the only path that runs in production. The
`StrategyDecider` seam is real and `_bounded` polices what one would return, but nothing is
plugged into it. That is a defensible design (fast, deterministic, auditable); it is
recorded here because the name promises otherwise and the next reader will go looking for
an LLM that is not there.

Source selection and retrieval execution are separate jobs, and since 2026-08-30
they are separated properly. `KnowledgeAgentService.decide` picks the sources;
`RAGAgentService.retrieve(request, route, plan, strategy, scope)` runs exactly
that strategy through `KnowledgeOrchestrator` with `build_default_adapters()`.

Before this, `RAGAgentService` built a strategy of its own -- always vector+BM25,
graph on two routes, `rewrite=False` -- which silently overrode the one the
Knowledge Agent had just produced. Three consequences, all fixed together:
`memory`, `wiki` and `multimodal` were unreachable on the chat path however the
Agent chose them; query rewriting never ran; and a verifier retry re-ran the
identical search, because the retry query lives in the strategy.

**The route is an instruction, not a hint.** `_knowledge_hints` translates each
route into the sources it implies and `KnowledgeAgentService` includes them
unconditionally. Consulting only keywords is what let a `graph` route degrade to
vector+BM25 whenever the wording carried no relationship words.

**Web has two independent authorizations.** The router choosing the `web` route
*is* permission to search the web; `use_web_fallback` additionally allows a
freshness-driven web search on routes that did not ask for it. Requiring the flag
for both meant its default (False on every chat request) removed web search from
the web route itself.

There is one retrieval path. `KNOWLEDGE_ORCHESTRATOR_ENABLED` used to switch
between two, and the default sent every request through the branch that
discarded the strategy.

`FinalAnswer.evidence` is the full authorized retrieval set and
`FinalAnswer.cited_evidence` is the cited subset in citation-number order. They
were the same list, which made `PipelineResult.contexts` and `citations`
duplicates and hid every retrieved chunk the model chose not to cite.

### Multi-turn follow-ups

A follow-up question is completed before it is retrieved on, not after (wired 2026-08-31).
`request.conversation` used to reach only the synthesizer and the tool selector, neither of
which retrieves: the router saw only `request.question`, the Knowledge Agent used it
verbatim as the retrieval query, and `build_rewrite_queries` took a query with no history.
So "成本呢？" ran a vector search on those three characters and the synthesizer had to
answer from evidence fetched for the wrong query — a failure that reads as poor retrieval.

The completion happens in the rewrite step the repository already had:
`KnowledgeOrchestrator._rewrite_once` → `build_rewrite_queries` → `_llm_rewrite`, which was
missing only the conversation argument. With history present the rewriter switches to a
standalone-question prompt; with none it keeps its original wording-only prompt, so a first
turn costs nothing new. `QUERY_REWRITE_WITH_LLM` still gates the LLM call and still defaults
false — turning it on is the cost decision, and it is now a switch that does something (see
Caller deadlines: `_llm_rewrite` could not run at all before `request_context` was opened
for the workflow).

**The original question always survives.** `_with_queries` merges it in ahead of the
variants, so a wrong completion adds a bad query rather than replacing the good one — the
model is guessing what the user meant and can guess wrong. `primary_query` (what reranking
scores against) is read before the merge and stays the question as asked.

`enable_context_tracking` finally has a meaning, and it is enforced in one place per
consumer: `RAGAgentService.retrieve` decides what retrieval may know about the session, and
`SynthesizerAgentService.synthesize_candidate` decides what generation may. Off means
neither sees it.

**`app/services/context_management.py` is deliberately not on this path.** Those 642 lines
implement the older rule-based alternative (pronoun → entity), and it decides a question
needs resolving by substring-matching a fixed pronoun list. Both directions fail on ordinary
Chinese: the most common follow-up shape drops the subject entirely, leaving nothing to
match ("成本呢？"), while 那/这 are substrings of ordinary words and particles, so a
self-contained question gets a stale entity substituted into it ("那延迟呢"). It also carries
a hardcoded company gazetteer and a process-local per-session dict. It keeps its one real
reader, the session-export endpoint, where an entity and topic list is a reasonable product;
`tests/knowledge/test_followup_rewriting.py` pins both failure directions so reviving it
stays a deliberate choice.

**The API sends turns, not a blob.** `POST /api/advanced-rag/query` used to collapse the
session into one `system` message holding a pre-rendered memory block. Synthesis could live
with that; rewriting cannot, because completing a follow-up means knowing what the previous
turn asked. The block still leads the sequence — it also carries the long-term memories the
raw turns do not — and `_render_turns` skips it when building the rewrite prompt so the same
rounds are not shown twice in two formats. One consequence of the old shape: the
`max_turns=12` bound in `_render_conversation` was dead, because there was only ever one turn.

### Knowledge graph extraction

**A triplet's confidence now says how it was produced** (fixed 2026-09-04), and until it
did, the graph route was serving invented relationships as evidence.

`extract_graph_triplets` stamped `confidence=0.7, method="legacy"` on *every* triplet
regardless of extractor, so `filter_triplets(min_confidence=...)` could not tell an
LLM-extracted relation from a regex-chained one and its threshold was inert. What it was
failing to filter matters: `extract_triplets_rules` does not find relations. It takes the
ten most **frequent** `ENTITY_PATTERN` matches -- and that pattern matches any 2-12
character CJK run, so in Chinese it matches nearly every word, including the "系统/模块/功能"
the LLM prompt explicitly excludes -- then pairs them **by adjacent frequency rank**, which
is an artefact of sort order, and labels every pair in a chunk with one relation keyed off
the whole chunk's wording.

And it was the default path, not an edge case: `MODEL_BACKEND=local` is what a fresh
checkout runs, the offline stand-in cannot emit the required JSON array, and
`extract_triplets` fell through to rules on every chunk.

`LLM_TRIPLET_CONFIDENCE` is 0.7 (today's effective value) and `RULE_TRIPLET_CONFIDENCE` is
0.25, below every shipped `graph_min_confidence` (`app/services/parser_profiles.py`:
0.55 / 0.6 / 0.65 / 0.75 -- **not** `Settings` fields).
`test_every_shipped_parser_profile_threshold_excludes_rule_confidence` pins that coupling,
which is otherwise invisible across two files. Three method values, because "this
deployment configured rules" and "this deployment's LLM is broken" were previously
indistinguishable: `llm`, `rules`, `rules_llm_fallback`.

**So an installation with no working LLM now writes zero triplets**, which is the truthful
number and must not be silently zero: `_triplet_rows` counts per method,
`ingest_paths` reports `triplets_discarded_low_confidence` and `triplet_methods`, and
`_insert_triplets` logs at INFO when everything was discarded, naming the threshold. A
graph route that quietly goes empty otherwise reads as a retrieval problem rather than a
configuration one. Deliberately *not* added: a `GRAPH_RULE_TRIPLET_CONFIDENCE` setting --
a knob whose only purpose is re-enabling a path judged to be fabrication is a knob for
turning fabrication back on. Lowering the profile thresholds was considered and rejected
for the same reason.

**There is no safe automatic migration for graphs already written, and none should be
attempted.** `batch_upsert_triplets` writes `confidence_max/count/avg` and **no `method`
property at all**; `graph_lookup` never reads confidence (it is write-only); and every
existing edge carries exactly 0.7, because both the old stamp and the client's own
normaliser default to it. So 0.7 is not a marker of junk, it is what everything looks like,
and `_write_graph_triplets` has no delete path so a reset reingest only adds edges beside
the old ones. The operator step is explicit:

```cypher
MATCH ()-[r:RELATED]->() DELETE r
```

then reingest. Neo4j is optional and empty on most installs.

**One read-side mitigation applies to existing graphs with no migration.**
`infer_relation` returns `RELATED_TO` whenever no keyword matched, making it the most
common relation in any graph built without an LLM -- and `_NOISY_RELATIONS`
(`app/tools/graph/core.py`) contained `"related"` but not `"related_to"`, so those edges
scored 0.6 and survived the filter that exists to drop exactly them. Adding it drops them
at read time on the next query. Its limit is worth stating: `infer_relation` also emits
`DEPENDS_ON`/`INCLUDES`/`USES`/`STORES_IN` on keyword hits, and those still survive.

### Multimodal retrieval

`multimodal` is a retrieval source the Knowledge Agent selects on visual or
tabular wording (`_VISUAL_QUERY_PATTERN` in `app/agents/knowledge/service.py`).
Until 2026-09-03 it was selected and returned nothing, every time, for three
independent reasons: `_retrieve_text` queried a collection named `text_chunks`
where the real one is `local_rag_collection`, so it logged a traceback per query;
`image_descriptions` and `table_summaries` were written by methods with no
caller; and the source spent a retrieval slot -- one the planner can otherwise
give to `web` -- to return nothing on exactly the questions it exists for.

**Ingestion is the producer now.** `_index_images` and `_index_tables`
(`app/services/documents/ingest.py`) run inside `ingest_paths` and report
`images_indexed` / `tables_indexed` in its result.

**Images** are indexed with whatever was actually read out of them -- the
loader's description or OCR text, or `ocr_image_bytes` run here when the loader
left it bare. An image nothing could read is skipped rather than indexed with the
reason: "Tesseract executable not found" as retrievable evidence is worse than
the image being absent.

**The vision caption is read from metadata, not from the rendered block** (fixed
2026-09-04), and that distinction is the whole of it. `ocr_image_bytes` renders the
scene caption, the people summary and the OCR result into one `page_content` and marks
a failed OCR with `[image_ocr_error]`; `_readable_image_text` discarded the entire
string whenever that marker appeared. Correct for the diagnostic, and it took the
caption with it -- *precisely* in the case a vision model exists for: a photo, a
diagram, a chart with no extractable text. With `IMAGE_CAPTION_ENABLED` on and
Tesseract missing, the model produced a perfect description and the image was indexed
as nothing at all, silently. `metadata["image_caption"]` carries the raw caption and
never holds a diagnostic, so reading it separately keeps both properties. It is
de-duplicated against the rendered block, which also contains it on the success path.

Note what this does *not* turn on: `IMAGE_CAPTION_ENABLED` still defaults false, and
captioning still needs a vision model. The fix means that switching it on now does
something on the images that need it most.

**Tables are indexed whole, and that is the point of them.** The chunker splits
by size and knows nothing about tables. Measured on a 40-row table: seven child
chunks, and *only the first carries the header row*. Parent expansion does not
rescue it either -- the second parent holds sixteen rows and no header. So a
question about a row in the middle retrieves `| Region-30 | 130 | 230 | 330 |`
with nothing to say which column is which, and the model answers from position.
It does not fail; it is confidently wrong. `_table_from_markdown` reads the
header and body back out of the pipe table the loader rendered, so `headers` is a
header again.

**Charts are inert on purpose.** `ChartContent` is only ever produced by
`ChartAnalyzer` looking at an image with a vision model, so there is nothing to
index without one. The retriever's chart path skips a missing collection quietly
rather than erroring, so it costs nothing while it waits. That is the difference
between it and the text modality, which was deleted: text is what the `vector`
source is for, and this source contributes what that one cannot.

**These collections sit outside the corpus `similarity_search` guards**, so both
of that function's checks are reproduced here deliberately. `_scope_filter`
constrains by tenant *and* by source or document *and* by `_owner_clause` -- the
same helper the store uses, not a second implementation -- and `index_image` /
`index_table` write `owner_user_id` and `visibility` alongside the tenant. An
absent key does not match `$eq`, so anything indexed without those fields is
invisible rather than public, which is why `visibility` defaults to private
rather than to `""`. `tests/security/test_multimodal_indexing.py` pins the
refusals.

**Everything on this path is synchronous, and that shaped it.** `ingest_paths` is
reached from `asyncio.to_thread`; `index_image` and `index_table` were `async`
while awaiting nothing, and dropping the keyword is what let ingestion call them
at all rather than driving an event loop from a worker thread.

**PyMuPDF is the optional `multimodal` extra and must stay a lazy import.** Three
modules imported it at module scope, which was survivable only while nothing
imported them -- ingestion does now, so on an installation without the extra the
first document containing an image or a table would have crashed the ingest. All
four modules import without it, which is what `app/services/multimodal/__init__.py`
has always claimed.

### Retrieval Strategy

**Hybrid Retrieval** ([app/retrievers/hybrid/retriever.py](app/retrievers/hybrid/retriever.py)):
- **Vector search**: Sentence-Transformers BGE-M3 embeddings → ChromaDB
- **BM25 search**: Jieba tokenization → Rank-BM25
- **Fusion**: Reciprocal Rank Fusion (RRF), over one ranked list per **(source, query)**
  pair -- not per source (2026-09-04). An adapter runs each of `plan.queries` and returns
  `RankedGroups`, one ranked tuple per query in that order; `_retrieve_source` masks each
  group separately, so dropping an unauthorized item closes the gap inside its own list
  rather than merging lists.

  This landed in two steps, and the first is worth remembering because it was not enough.
  A source used to fold its queries into one list, and RRF scores by *position*, so the
  second query's best hit arrived at rank `top_k + 1` and was charged a rank it had not
  earned. That was never dormant, though it was uneven: `QUERY_REWRITE_ENABLED` defaults
  true and the rule rewriter needs no LLM, and measured, a Chinese question containing
  punctuation yields 2-3 queries and a multi-word English one yields 3 -- but a short
  punctuation-free Chinese question yields 1, where the fold cost nothing. Interleaving
  (step one) moved that hit to rank 2 rather than rank 1: smaller, still wrong, and still
  growing with the number of queries. Keeping the lists apart (step two) removes it --
  every query's rank-1 gets the same `1/(k+1)`, and a document two queries both rank first
  accumulates two full contributions instead of one full and one discounted.

  `flatten_ranked_groups` survives as the flat *view* -- result counts, diagnostics, and
  the graph adapter's prior evidence -- and still interleaves, but nothing about ranking
  depends on it any more.

  **Not visible in `make eval-retrieval`**, which runs one query per source
  (`rewrite=False`), so there is a single group and fusion is unchanged: MRR stays 0.9688
  across step two. That is why the property is pinned by unit tests over
  `reciprocal_rank_fuse` rather than by the corpus metric -- a number that cannot move is
  not evidence.
- **Planner sub-queries reach the retrievers** (wired 2026-09-04). `PlannedTask.prompt` had
  exactly one reader in all of `app/` (`rag_pipeline.py`, for a diagnostics dict), because
  `_source_plan` hardcoded `queries=(query,)` and `RAGAgentService.retrieve` opened with
  `del plan`. A decomposed question therefore ran one search on the original wording --
  while the API returned the sub-queries to the client as `decomposed_query`, reporting
  work that never happened. `_source_plan` now builds `(question, *sub_queries)`.

  Four things about that shape are load-bearing. **The original question stays at index
  0**, because `KnowledgeOrchestrator` reads `sources[0].queries[0]` twice -- as
  `primary_query`, the single string reranking scores every candidate against, and as the
  rewriter's input -- so a sub-query there would rerank the whole result set against one
  facet. **De-duplication uses one shared definition** (`app/knowledge/queries.py`,
  imported by both the agent and the orchestrator; the agent must not import the
  orchestrator): a direct plan's single task prompt *is* the question, and
  `reciprocal_rank_fuse` accumulates per appearance, so a duplicate silently double-weights
  everything it returns. **`web` and `memory` are excluded** -- `_retrieve_web` calls
  `run_web_research` per query and concurrent `DDGS()` construction has wedged this process
  at zero CPU before, so an N-fold multiplier on third-party search is the worst failure
  mode available here. **The cap is enforced twice** from one constant
  (`MAX_PLAN_QUERIES_PER_SOURCE`), in `_source_plan` and in `_bounded`, because `_bounded`
  only runs on the decider path and `capabilities.py` constructs the agent with no decider
  -- a cap there alone would guard a path that does not exist in production.

  `_comparison_plan` now emits the bare target rather than "Retrieve authoritative evidence
  about X": those prompts are search queries now, and `bm25_search` matches on shared term
  membership, so the English boilerplate would have made every chunk containing "evidence"
  a candidate for a comparison usually asked in Chinese. Note that `_comparison_plan` runs
  *before* the `enable_decomposition` check in `PlannerAgentService.plan`, so
  comparison-shaped questions get multi-query retrieval by default.
- **Graph retrieval**: runs for both the `graph` and `hybrid` routes (fixed 2026-08-29; `graph` previously degraded silently to vector+BM25)
- **Two-phase retrieval** (added 2026-08-31): `KnowledgeOrchestrator` runs sources in one
  `asyncio.gather` because they are independent. An adapter that implements
  `PriorEvidenceAdapter` declares it is not, and gets a second phase fed the first phase's
  evidence. `GraphKnowledgeAdapter` is the only one, and it asks for that phase **only when
  `GRAPH_RAG_ENHANCED` is on** — with the switch off there is no reader for the prior
  evidence, so the deferral would buy nothing and cost the overlap.

  The cost is real: a deferred source's duration lands on the critical path instead of
  hiding under the others. Phase two therefore inherits what is *left* of
  `STAGE_TIMEOUT_RETRIEVAL_MS` rather than a fresh copy of its plan timeout — otherwise two
  phases could take `phase_one + phase_two` and trip the stage ceiling, turning a sharper
  graph lookup into a degraded stage, which is strictly worse than the plain lookup it
  replaced.

  **Prior evidence tunes retrieval; it must never widen it.** What crosses into
  `run_graph_rag` is a quality *score* over the retrieved text plus page/format metadata.
  `run_graph_rag_with_pdf_context` does not read entities out of the documents to query
  with, and `allowed_sources`/`owner` remain the ones `privacy_permission` resolved. So a
  document that argues for its own importance can buy itself a larger `max_neighbors` and
  nothing else. Do not extend this to letting document text choose which entities to look
  up: that is retrieved content steering retrieval, and the author of a retrieved document
  is not always the person asking — the same reasoning that keeps tool selection blind to
  evidence.

  Phase outcomes are reassembled **by index, not by source name**: `KnowledgeStrategy.sources`
  carries no uniqueness constraint, and downstream `zip(source_plans, outcomes, strict=True)`
  reads `plan.required` off the pair, so keying on the source would misattribute a failure.
  A failed source contributes no prior evidence — a timed-out source has no results, not zero
  results, and feeding its silence to the quality estimator reads as a poor corpus.

  `app/agents/rag/cache.py` was rewritten in the same pass. It memoizes pure functions over
  in-memory text, but wrapped an *async* cache by calling `asyncio.get_event_loop()` and
  `run_until_complete`. `run_graph_rag` reaches it from `asyncio.to_thread`, where
  `get_event_loop()` raises and the fallback installs a private, never-closed loop per pool
  worker — and an `asyncio.Lock` driven from several loops serializes nothing. The mirror
  failure waited on the main thread, where `run_until_complete` on a *running* loop raises.
  Neither ever fired because nothing reached the code. It is a plain synchronous TTL+LRU now;
  do not reconnect it to `app/services/caching/`, which exists for values worth a network
  round trip and is what made an in-memory memo look like it needed a loop.

  `app/agents/shared/cache.py`, the router decision memo, had the identical defect and took
  the identical fix, so the rule generalises: **nothing reached from `asyncio.to_thread` may
  drive an event loop.** `get_event_loop()` raises in a worker thread, and the fallback of
  installing a private one leaves a loop open per worker for the life of the process. A memo
  over in-memory values is a dictionary lookup; it never needed a loop.
  `tests/agents/test_router_cache.py` pins that.
- **Reranking**: BGE-Reranker-V2-M3 (top 5 results)
- **Retrieval width** (wired to the chat path 2026-08-31): how wide a search is now depends
  on the question and on the plan, and both decisions live in `KnowledgeAgentService` —
  the Agent shapes a search, the orchestrator executes it.

  `app/knowledge/width.py` holds the one complexity definition (long query / comparison
  wording / multiple question marks, 0-3) and two call sites scale different bases from it:
  the Knowledge Agent grows `TOP_K` (4) and `RERANKER_TOP_N` (5), the legacy hybrid path
  grows `VECTOR_TOP_K`/`BM25_TOP_K` (6). Keeping the bases apart matters — borrowing the
  hybrid default would have widened every *simple* query too, which is a different decision
  from making complex ones wider. It moved out of `app/retrievers/hybrid/adaptive_params.py`
  because the Knowledge Agent must not import a retriever; `app/retrievers/hybrid/`
  re-exports `adaptive_retrieval_params` under its old name.

  Reranking widens with the search: `KnowledgeStrategy.rerank_top_n` (None means use the
  setting) exists because feeding the reranker more candidates while holding its output
  size fixed just discards the extra ones. Before this, `DYNAMIC_RETRIEVAL_ENABLED` and the
  `DYNAMIC_*_CAP` settings only reached `candidate_collection.py`, which the chat path does
  not use, so every source got a flat `TOP_K` however complex the question was.

  **`TaskBudget.max_retrievals` bounds the source *count*, not the width.** The planner
  derives it as 2 (the required local pair) + 1 for a hybrid route + 1 for web — a count of
  retrieval calls, which is exactly the source list `_rule_strategy` builds. It used to be
  summed, checked against `PLANNER_MAX_RETRIEVAL_BUDGET`, and dropped. The ceiling is now
  spent in the planner's own order (required pair → sources the *route* hinted → keyword
  matches): truncating in discovery order spent the web slot on `multimodal`, because the
  keyword rules append `web` last. A plan totalling zero is a plan with no retrieval task
  (a pure tool call), which is the absence of an instruction rather than an instruction to
  search less, so the service ceiling stands.

### Configuration System

**Essential config files** in `config/`:
- `router_calibration.json`: Few-shot examples, confidence thresholds. Only read when `ENABLE_CALIBRATION=true` (off by default); with calibration disabled, routing relies solely on the LLM classifier's own confidence output.

**Runtime config**: [app/core/config.py](app/core/config.py) intentionally does **not** read a root
`.env` file — it reads `.runtime/{APP_ENV}.env`, generated by
`deploy/scripts/config.py render` from `config/env/` + `config/profiles/` (or a file pointed to by
`RUNTIME_ENV_FILE`). Setting values in a root `.env` has no effect; export real environment
variables or run the render step first.

`.runtime/` starts empty. Until `make config-render ENV=development` is run,
`Settings` falls back to its hardcoded defaults for every field — including
`MODEL_BACKEND=local`. Run the render step (or export real environment variables)
before treating any configured value as active.

**`MODEL_BACKEND=local` means there is no LLM in the loop at all**, and it is what a fresh
checkout runs — so it is the state most first impressions are formed in. `local` resolves to
`LocalEvidenceChatModel` (`app/services/models/runtime.py`), an offline stand-in that keeps
the app usable with no API key and no Ollama: it routes by keyword (`_route_json` —
关系/依赖/graph/relation/路径 → `hybrid`, everything else → `vector`) and assembles an answer
out of the evidence sections of its own prompt. Every quality number in this file — router
accuracy, citation completeness, P@5 — describes the LLM path and means nothing on this one.
`MODEL_BACKEND=local` in the real process environment additionally **overrides persisted
admin model settings** (`_local_backend_forced`), so a deployment that sets it cannot be
talked out of it from the admin UI -- and since 2026-09-04 the UI says so. `GET/POST
/admin/model-settings` return `environment_pinned` and a reason, and the page leads with a
warning banner. Without it an admin could save an OpenAI key and model, get a success
response, see the values echoed back and an audit row behind them, while every answer still
came from `LocalEvidenceChatModel` -- the same "reports something other than what runs"
failure as the old `advanced-rag/config` endpoint.

The write is **accepted**, not refused, which is the one place this differs from
`POST /admin/config/values` next door. That endpoint refuses a write to an
environment-pinned value because the write would go to a layer the process does not read;
this one persists correctly and takes effect the moment the pin is removed, so refusing it
would block legitimate preparation.

The same pass fixed a description that promised the opposite of the code. The `enabled`
flag was documented as applying the global config "to users without personal overrides",
but `get_chat_model` resolves `global_override or user_override` -- an enabled global
config wins over *every* user's own settings, so their personal key stops being used and
their queries bill the org's account. An admin ticking that box on the old promise would
have moved everyone's traffic silently. The wording now says what it does, in the schema
and on the checkbox.

Having no model to hide behind is why this is the path where prompt scaffolding leaks into
prose. It has narrated itself, echoed `ContextBuilder`'s `[E1] document=…; layer=…` header
as though it were text, and returned its own answer template as the answer.
`tests/services/test_answer_readability.py` pins all of it: the reader must never see the
machinery that produced the answer.

**A value read with `os.getenv` cannot be configured.** pydantic-settings loads
`.runtime/{APP_ENV}.env` into `Settings` **without exporting anything into the process
environment** — with `APP_ENV=development` in that file, `Settings().app_env` is
`development` while `os.getenv("APP_ENV")` is still unset. So `make config-render` cannot
set such a key, nor can anything that pushes values into `Settings`; it has to be a real
exported environment variable, present before the module is imported. None of the keys
below appeared anywhere in `config/env/`.

An AST census on 2026-09-01 found **47 live keys** outside `Settings`: 2 in the router,
2 in the request middleware (one of them `STRICT_CSP`, which picks the Content-Security-Policy),
5 in an admin endpoint, 2 duplicated in the Self-RAG evaluator, 37 behind the helper
functions in `app/agents/shared/config.py`, plus 5 in a module with no importers at all.
**All of them are gone**, and `app/` now contains no environment read outside the allowlist
below. See `docs/superpowers/plans/2026-09-01-configuration-management.md`.

The 37 did not all deserve migrating, which is the more useful half of that pass: **20 had
no reader anywhere** and were deleted rather than carried into `Settings` — including
`CASCADE_USE_FOR_VALIDATION`, whose branch logged "is retired" and then did the same thing
either way. Thirteen became fields. The four `ANSWER_WEIGHT_*` scoring weights stayed in
`app/agents/shared/config.py` as plain literals: they are one scheme that has to sum to 1.0,
and four independently settable knobs that must agree is a footgun, not a feature. Migrating
a constant nothing reads would have made the configuration surface bigger and no more
configurable.

**Precedence is declared once**, by the source order in
`Settings.settings_customise_sources`:

```
init > real process environment > configuration centre > .runtime/{APP_ENV}.env > defaults
```

`RemoteSettingsSource` (`app/core/remote_config.py`) is the configuration-centre slot; the
Nacos adapter behind it (`app/core/remote_config_nacos.py`) imports the SDK lazily, so an
`ImportError` degrades to the snapshot and an installation that has not adopted a
configuration centre never needs the dependency (`pip install -e .[config-centre]`). The
source returns `{}` unless `NACOS_ENABLED` is true, which is the default.

**The bootstrap must be a real environment variable, never a key in `.runtime/*.env`** —
that file is read into `Settings` without being exported, so a bootstrap key placed there is
silently ignored, which is the same trap the rest of this section is about. It belongs in the
process environment, which for a deployment means `environment:` in
`deploy/compose/compose.config-centre.yaml`:

| key | default | |
|---|---|---|
| `NACOS_ENABLED` | `false` | nothing below is read while this is off |
| `NACOS_SERVER_ADDR` | — | required when enabled |
| `NACOS_NAMESPACE` | `""` | the public namespace |
| `NACOS_GROUP` | `DEFAULT_GROUP` | |
| `NACOS_DATA_IDS` | `querymind` | comma-separated; **later ids override earlier ones**, the same rule the render step uses for its layers |
| `NACOS_USERNAME` / `NACOS_PASSWORD` | `""` | never `Settings` fields — see the allowlist below |
| `NACOS_TIMEOUT_MS` | `3000` | per fetch |
| `NACOS_POLL_INTERVAL_MS` | `30000` | how long a console edit takes to reach a running process |

`scripts/create_admin.py` creates the local development administrator, because until
2026-09-01 there was no account with the `admin` role at all and the admin surface could not
be opened by anyone. It is a fixture: the password comes from `ADMIN_PASSWORD` or is
generated and printed once, and is never written to a file in the repository.

`scripts/verify_config_centre.py` drives the **real** SDK against a stub server with no
container, and is the thing to run after touching the adapter or bumping the pin: a fake
client answers whatever shape it is asked for, so the unit tests cannot catch this
repository's calls drifting from the SDK's.

**`GET /admin/model-settings/effective` answers a different question from every other
admin surface** (added 2026-09-04): not "what did I save" but "what will the next question
use". They come apart quietly. The reranker and the NLI cross-encoder are both loaded with
`local_files_only=True`, so a model that was never downloaded returns `None` rather than
raising -- retrieval falls back to `lexical_rerank`, validation falls back to a
deterministic scorer, both keep answering, and from outside a degraded stage is
indistinguishable from a healthy one. `MODEL_BACKEND=local` discards a saved provider
config outright, and on the offline backend there is no language model at all.

So each component reports a **status**, and `degraded` is the one worth having: configured,
running, and not doing what its name implies. Probing loads the optional models, which is
why this is an admin endpoint and not part of a health check -- the cost is the one the
first real query would have paid, once per process.

`ENABLE_RERANKER`, `RERANKER_MODEL_NAME`, the four `CASCADE_ENABLE_*` switches, both
cascade timeouts, `NLI_MODEL_NAME` and `NLI_MAX_SENTENCES` became editable in the same
pass. Each needed its cache cleared by `apply_config_reload` first: `clear_model_caches`
covers the chat and embedding models only, so the reranker's own `lru_cache` kept the old
model while the page reported the new name. `test_the_reload_reaches_every_cache_that_holds_an_editable_setting`
now enforces that -- it finds every `@lru_cache` function reading an editable field and
requires the reload to clear it, following one level of indirection through the named
clearers, and it was verified able to fail by removing the reranker's.

**What an administrator may change is an allowlist**, `app/core/config_schema.py`, not an
annotation per field. `Settings` has 244 of them; annotating individually would scatter a
security-relevant decision across 236 lines and leave "what can console access reach?"
with no single answer. It is opt-in — a new field is not editable until it is named — and
`tests/core/test_config_schema.py` asserts by *shape* that nothing matching KEY, SECRET,
PASSWORD, TOKEN, PATH, URL, DSN, CORS or ORIGIN ever appears there, so a future addition has
to defeat the rule deliberately rather than by inattention.

`GET /admin/config/schema` returns each editable field with its current value and **which
layer supplied it**, and `POST /admin/config/values` writes to the configuration centre and
reloads. Two things it refuses, and both prevent the console from claiming a change it did
not make: a write with no configuration centre configured (there would be nowhere to put it
that the process reads), and a write to a value pinned in the process environment — the
environment outranks the centre, so it would succeed and change nothing. The browser
disables those inputs too, but that is a convenience: the rule is enforced server-side
because the browser is not where it can be.

**Each edited key is written back to the document that already defines it**, and each such
document is rewritten whole rather than patched. Writing everything to one document instead
put the same key in two places with the later id silently winning, so the page showed a value
from one document while the edit landed in another — found by clicking Save against a real
server. A key no document defines yet goes to the last data id, which is the fallback
precisely because later ids override earlier ones. The centre owns version history and
rollback; merging in this layer would be a second, worse implementation of both.

Verified end to end against a real Nacos 2.4.3, which is also where two defects the unit
tests could not see turned up: `RemoteDocuments` had no `publish` method at all — it had
landed on the wrong class in a refactor, and all eleven endpoint tests passed because the
fake they inject implements whatever it is asked for. One test now fakes only the client, the
actual network boundary, and drives the real store. Deployment note: with
`NACOS_AUTH_ENABLE=true` and the embedded store, the user table starts empty and
`nacos/nacos` fails with "User nacos not found" until `POST /nacos/v1/auth/users/admin`
bootstraps the account.

**The process environment sits above the centre on purpose**: a deployment needs one way to
pin a value the console cannot move, which is what `MODEL_BACKEND=local` already does to
persisted admin model settings. The rejected alternative — fetching remote values at startup
and writing them into `os.environ` — destroys exactly that, and smuggles values past
`Settings`'s validation.

**Nothing may break startup.** `get_settings()` is on the path to everything, so the source
degrades in three steps: the remote document, the snapshot written by the last *successful*
fetch (`.runtime/remote-config/`), then nothing at all — which simply leaves the lower
sources in charge. The SDK is called with `no_snapshot=True` because this layer keeps its
own: letting the SDK substitute its cache would make "the server answered" and "it did not"
indistinguishable, and that log line is what an operator has when a value fails to take
effect.

**A settings source must return values keyed by field *alias*.** `{"ENABLE_CALIBRATION":
True}` applies; `{"enable_calibration": True}` is **silently ignored** — `Settings` validates
by alias and `extra="ignore"` drops the rest, with no error anywhere. Aliases are what
`config/env/*` and the rendered file already use, so one name follows a value from the
repository to the console.

**Change detection is polled, not pushed, and that is not a preference.**
`nacos-sdk-python` 1.x does it in `_init_pulling`, which builds a
`multiprocessing.Manager()`, a `multiprocessing.Queue` and a ten-thread callback pool — and on
Windows, where the start method is spawn, registering a watcher never returned (verified twice
against a stub server, with and without a `__main__` guard). `watch_remote_config` runs one
daemon thread that re-fetches every `NACOS_POLL_INTERVAL_MS` (default 30s) and compares a
digest of the documents. The cost is up to that much latency on a console edit; what it buys
is one less process, one less thread pool, and the same behaviour on every platform.

**The SDK dependency is pinned to `>=1.0.0,<2.0` as a design constraint.** 2.x and 3.x import
as `v2.nacos`, not `nacos`, and their `get_config` is a coroutine — and this client is called
from synchronous `Settings()` construction, reachable from a request handler via
`reload_settings()`. Driving it there means `asyncio.run` (which raises inside a running loop)
or a private loop per call, the exact defect already fixed twice in this repository.

**There is one way configuration changes at runtime**, `write_config_values()`, and both the
admin page and the replay autotuner go through it. The autotuner used to assign its patch
onto the live `Settings` object instead — which failed twice over: the change belonged to no
layer, so it was lost at the next reload, and the page's "which layer did this come from"
column had no way to know. It now recommends, and applying inherits every refusal, including
the one for a value the process environment pins.

`requires_restart` is `False` on every editable field, and that is an audited claim rather
than a default -- and since 2026-09-04 an enforced one:
`tests/core/test_editable_settings_are_reloadable.py` fails if an editable field is read
through a `settings = get_settings()` bound at *module scope*. Six modules do that
(`app/api/dependencies.py`, `deps/{admin,documents,sessions}.py`,
`utils/{auth_helpers,memory_helpers}.py`); `get_settings` is `lru_cache`d and a reload
calls `cache_clear()`, which builds a new object, so those six keep the one they captured
at import for the life of the process. No editable field is read through them today, which
is why the test asserts rather than ratchets -- but it held by coincidence rather than by
construction, and the failure it prevents is silent: the console would report success and
the process would keep the old value. Same hazard as the `CASCADE_*` module global next
door, reached from a different direction. Verified able to fail by adding `MODEL_BACKEND`
(read in `deps/admin.py`) to the allowlist. The audit itself: each consumer either reads `get_settings()` per use, or is held by an object
`RAGPipeline` builds per request, or is rebuilt by the reload. The retrieval cache was the
one exception — it bakes its TTL in at construction and lives in a module global — so the
reload clears it rather than the page carrying a caveat.

A change pushed from the console and the admin endpoint's reload run the **same** sequence,
`app/api/application/config_reload.py::apply_config_reload()`. A watcher that cleared its own
subset of caches would be a second, quieter definition of "reloaded", and the difference
would only ever surface as "it took effect when I clicked the button but not when I saved it
in the console". That function's limit is worth knowing: a value already read into a
module-level constant is not revisited, so the legacy constant block keeps its start-up
values until the process restarts.

**A key in a configuration layer that `Settings` does not know is dead**, and dead in the
quietest way: validation is by alias with `extra="ignore"`, so an unrecognised key in
`config/env/*` or `config/profiles/*` is dropped without an error, and the render step copies
it into `.runtime/{APP_ENV}.env` where it looks exactly like a live setting. Two were found
that way on 2026-09-01 — `QUERY_RESULT_CACHE_BACKEND`, a sibling of the real
`RETRIEVAL_CACHE_BACKEND` that was never implemented, and `DEBUG`, which had no reader at all
while `deploy/scripts/config.py` enforced "DEBUG must not be true in production", a safety
rule about a value that could not have an effect. Both are gone, and
`tests/core/test_config_layers_are_live.py` checks every committed layer key against the
aliases, with a small allowlist for keys the deployment itself consumes.

`tests/core/test_config_has_one_source.py` keeps it that way: an AST guard that every
direct environment read in `app/` is in an allowlist keyed on `path::enclosing_function`
**with a reason**. It carried a ratchet over the legacy constant block as well until that
block was emptied; a guard that guards nothing is one more thing to read and no protection,
so it went with it. These reads are legitimately exempt and stay:
`resolve_runtime_env_file` (it chooses the settings file, so it cannot live in it),
`remote_config._bootstrap` (the same chicken-and-egg one layer out: it configures the source
that supplies `Settings`, which is also why `NACOS_PASSWORD` never becomes a field),
`_local_backend_forced` (a deployment pinning the local backend must beat persisted admin
settings), conda-environment diagnostics, and pytest detection.

Two consequences worth knowing. `ENABLE_WEB_ROUTE_DOWNGRADE` silently rewrites a `web`
route to `vector` inside `decide_route` — a third and invisible answer to "who authorized
the web", see Knowledge Agent above. And **anything read at import time cannot be
reconfigured at runtime**: the router's calibrator and the request-metrics deque were both
bound at import and are now resolved on first use, because a value that is only read once,
before `Settings` is loaded, is not configuration.

**`GET /api/advanced-rag/config` reports the switches that actually gate its two
features** (fixed 2026-09-01). Every value it returned was unrelated to what ran:
`query_decomposition.enabled_by_default` came from `ENABLE_QUERY_DECOMPOSITION` while the
real switch is `QUERY_DECOMPOSE_ENABLED`, **which defaults to on** — so the page reported
`false` on a feature that was running; `self_rag.enabled_by_default` came from
`ENABLE_SELF_RAG` while the gate is `VectorRAGConfig.enable_evaluation`; and
`max_sub_queries` came from an environment variable rather than the bound `QueryDecomposer`
enforces (now the named `DEFAULT_MAX_SUB_QUERIES`). A configuration page that reports
something other than the running configuration is worse than no page — it is the reason
this section exists.

**Additional config**: [app/agents/shared/config.py](app/agents/shared/config.py) contains component-specific settings (currently undergoing simplification - many constants are legacy tuning parameters that will be consolidated or removed)

### Technology Stack

**Backend**: FastAPI + LangChain
**Vector Store**: ChromaDB (local, persistent)
**Graph Store**: Neo4j (optional)
**Database**: SQLite only. Each store opens its own `sqlite3` connection
(`app/services/auth/auth_service.py`, `app/services/sessions/history.py`,
`app/services/sessions/metadata_db.py`, `app/services/prompts/store.py`,
`app/wiki/store.py`, `app/retrievers/stores/vector.py`,
`app/services/connectors/{metadata_repository,repository}.py`). There is no shared connection
pool and no PostgreSQL support: an async SQLAlchemy pool existed but was never used by
any business code and was removed on 2026-08-29, along with the `asyncpg`/`aiosqlite`
dependencies. `DATABASE_URL` **still exists** as a `Settings` field and is still read, by
`app/services/sessions/metadata_db.py::_get_db_path` — but only the `sqlite:///` form is
honoured, and anything else falls back to `./data/querymind.db`. That fallback used to be
silent, which is how `deploy/compose/compose.yaml` came to hand the backend a
`postgresql+asyncpg://` URL the application ignored; it logs a warning now, and the compose
entry is gone.
**Frontend**: React 18 + TypeScript + Vite + Zustand (state) + i18next (i18n)
**Models**: OpenAI GPT-5.5 (primary, `OPENAI_CHAT_MODEL`), Claude Haiku (multimodal image description/OCR triage in `app/services/multimodal/image_processor.py`; not used for retrieval-quality batch scoring, see Quality Assurance section), Sentence-Transformers (embeddings)
**Deployment**: Docker Compose with deployment scripts in `deploy/scripts/`. The `postgres`
service is behind the `with-n8n` profile, because n8n is the only thing that uses it — the
backend is SQLite-only, and gating its startup on a database it never opens bought nothing.

## Development Patterns

### Working with the Current Architecture

**Understanding the codebase**:
- Services in `app/agents/*Service` are **adapter wrappers** around existing implementations
- The actual logic is in modules like `app/agents/router/routing.py`, `app/agents/synthesizer/generation.py`
- Services provide cleaner interfaces but delegate to these legacy components

**When modifying functionality**:
1. **For interface changes**: Modify the `*Service` class in `service.py`
2. **For logic changes**: Modify the underlying implementation modules
3. **For new features**: Decide if it belongs in the adapter or the implementation

**Architecture guidelines**:
- Keep services stateless
- Use typed contracts (`RouteDecision`, `EvidenceBundle`, `FinalAnswer`) for communication
- Avoid adding more configuration constants unless absolutely necessary
- Consider if logic should be algorithmic vs. configuration-driven

### Quality Metrics

Monitor these when modifying retrieval or synthesis. **Each target now names what
measures it, and says "nothing" where nothing does** — three of the four had no
measurement behind them at all, which makes a number a wish rather than a claim (the same
principle as the `advanced-rag/config` fix).

| target | measured by |
|---|---|
| **Router accuracy** >95% | **nothing.** No labelled routing set exists. |
| **Citation completeness** >90% | **nothing** as an aggregate. It is *enforced* per answer by the cascade's citation stage, but never scored across a query set. |
| **P@5** >0.85 | **not comparable** — see below. `make eval-retrieval` reports P@5 and MRR over a tracked corpus, but that corpus has one relevant document per query. |
| **Latency P95** <5s | `build_ops_alerts`, from the `request_rows` ring the middleware writes. Process-local, so a restart empties it. |

**The retrieval numbers come from `make eval-retrieval`** (`scripts/eval_retrieval.py`,
`app/evaluation/retrieval_eval.py`, added 2026-09-04), which runs a tracked bilingual
micro-corpus through the **real `KnowledgeOrchestrator`** with a BM25-only strategy.
Through the orchestrator rather than through `app/evaluation/baselines/`, because those
baselines call `similarity_search` directly and never touch the orchestrator, the
adapters or `reciprocal_rank_fuse` — they cannot observe a change to any of them. BM25
only, because `read_corpus_records` reads a plain JSONL file, so it needs no embedding
model, no Chroma, no Neo4j and no LLM, and therefore runs on a fresh checkout.

**P@5 on the shipped set is capped at 0.2 and that is not a bad score**: every query names
exactly one relevant document, so at most one of five retrieved items can be relevant.
Reading it against a 0.85 target quoted for a multi-gold corpus is a category error, and
`tests/evaluation/test_retrieval_metric.py` pins it precisely so nobody makes it from a
metrics table. **MRR is the metric with headroom here, and it is pinned at exactly 1.0** —
BM25 over a fixed JSONL is deterministic, so it is asserted rather than ratcheted, per
query, so a failure names the query.

**The vector and hybrid paths stay a manual command, not a CI gate**, and the argument is
sharper than the one for `npm run screenshots`: `_load_cross_encoder` uses
`local_files_only=True`, so a CI runner without the model silently degrades to
`lexical_rerank` and would publish a number measuring the lexical fallback rather than the
reranker. A green metric measuring the wrong thing is worse than no metric.

Before trusting any of this, note the test that matters most:
`test_a_mismatched_scope_returns_nothing`. `mask_evidence` runs inside `_retrieve_source`,
so a corpus whose ownership metadata does not match the scope drops every item and scores
0.00 for reasons unrelated to retrieval — indistinguishable from a broken retriever.
Proving the metric can fail is the precondition for believing it when it passes.

Two limits that remain: the corpus is ~12 synthetic rows, so it exercises tokenisation,
fusion and scoping rather than real-world ranking; and `data/eval/retrieval_corpus.jsonl`
plus `data/eval/retrieval_queries.json` override the tracked defaults (first existing path
wins, the same shape as `_BENCHMARK_QUERY_PATHS`) for a deployment that wants to measure
its own corpus.

### Code Organization

**Backend Structure**:
- `app/pipeline/` - Public API entry point (`RAGPipeline`)
- `app/orchestration/` - Execution coordination and flow control
- `app/agents/<component>/` - Component implementations with service adapters
  - `service.py` - Adapter interface for orchestration
  - Other files - Actual implementation logic
- `app/domain/` - Shared contracts and types
- `app/api/` - FastAPI routes and HTTP layer
  - `app/api/routes/public/` - Public-facing endpoints
  - `app/api/routes/admin/` - Admin-only endpoints
  - `app/api/routes/operations/` - Operational/health endpoints
  - `app/api/routes/internal/` - Contracts shared between route modules, never registered as routers
- `app/retrievers/` - Retrieval implementations (vector, BM25, hybrid)
- `app/core/` - Core configuration and utilities

**Internal APIs**:

`app/api/routes/internal/pipeline_contract.py` exposes the standard RAG pipeline
execution contract used by:

- `admin/ops.py` - Performance profiling and benchmarking
- `public/sessions.py` - Message rerun functionality

Note (2026-08-29): this module and the live chat/SSE routes previously lived in
`app/api/routes/compatibility/`, whose name implied deprecated code and repeatedly
misled readers. The chat endpoint moved to `public/query.py`, the SSE endpoint to
`public/orchestration.py`, and this contract to `internal/`. No HTTP path changed.

**Frontend Structure**:
- `frontend/src/pages/` - Page components (ChatPage, LoginPage)
- `frontend/src/features/` - Feature-specific logic
- `frontend/src/stores/` - Zustand state management
- `frontend/src/services/` - API clients
- `frontend/src/i18n/` - Internationalization (zh/en)

**Note**: The `app/agents/` directory name is historical - it houses components, not autonomous agents.

### Frontend styling (adopted 2026-08-31)

**New and changed UI is written in Tailwind; the 73 hand-written stylesheets are
migrated as they are touched, never in bulk.** A wholesale rewrite would churn every
file in the app to fix a problem that is mostly cosmetic, and would discard visual
behaviour that was tuned against real screenshots.

**The cascade has an order now**, declared once in `styles/main.css`:

```
theme      Tailwind's token layer
legacy     the 73 hand-written stylesheets, being migrated away
components component-local CSS imported from a .tsx
design     core/elevation.css and core/surfaces.css
utilities  Tailwind
```

This is the thing that makes incremental adoption possible at all. Before it, every
hand-written sheet was *unlayered*, and unlayered rules beat every layer regardless of
specificity — so a Tailwind class written in a component silently lost to the CSS it was
meant to replace. That is why the codebase had four `tw:` class names against 1288
`className` attributes, and why none of the four did anything.

`styles/tailwind.css` is a stub: `@source` cannot be nested inside an import, so the
Tailwind directives live at the root of `main.css`. Without `@source`, importing
`tailwindcss/utilities.css` on its own emits **zero bytes** — `@import "tailwindcss"` is
what normally carries source detection, and this project does not use that form.

**Shape and depth come from a scale**, defined in `styles/core/elevation.css` and mirrored
into `@theme` so they exist as utilities:

| | token | utility |
|---|---|---|
| buttons, inputs, chips | `--shape-control` (8px) | `tw:rounded-control` |
| cards, rows, panels | `--shape-card` (12px) | `tw:rounded-card` |
| large containers, modals | `--shape-panel` (16px) | `tw:rounded-panel` |
| badges, avatars | `--shape-pill` | `tw:rounded-pill` |
| resting / hover / overlay | `--elev-1..3` | `tw:shadow-elev-1..3` |

`npm run lint:design` is a **ratchet**, not a ban: `scripts/design-scale-baseline.json`
freezes each file's current count of off-scale literals (135 radii, 193 shadows across 53 files at the
time of writing). A file may improve, never regress, and a new file starts at zero. Same
shape as `KNOWN_OFFENDERS` on the Python side. Re-freeze with `--write` only for values
that genuinely are not on the scale — a chart bar, a scrollbar thumb — and say why.

**Variants belong to the component, not to a stylesheet.** `animatedButtonVariants.ts`
exists because `groups.css` styled `.tiny-btn.danger` and `.tiny-btn.secondary`, class
names nothing has ever emitted (the component produces `animated-btn-lite--danger`). The
colour rule never matched, an unconditional white background above it did, and every
Delete button rendered white on white — contrast 1.0, a blank rectangle beside every
message, shipped and unnoticed. A `cva()` table makes the accepted values a type and the
emitted classes a value; a template literal cannot be checked by anything. Its classes are
still the hand-written ones on purpose — moving them to utilities is a later step that can
happen one variant at a time inside that file, without touching a call site.

**What this does not fix.** Of the eight defects found in this pass, tooling would have
prevented five: the class-name drift, the eight competing radii, a `var(--primary)` that
was never defined (transparent button, silent), the specificity fights, and missing
`aria-expanded` / `aria-pressed`. It would not have prevented the two that cost the most
time — a sidebar with `min-height: 100vh` and `overflow: auto` (an unbounded box cannot
scroll, so the *document* scrolled instead) and a composer occupying 68% of a phone
viewport. Those are a box-model reasoning error and a design judgement. Reach for the
tooling for consistency and contracts; it buys nothing on either of those.

**Fixing CSS: which tool, and in what order.** The first question is which of four kinds of
defect this is, because each has a different tool and none of them substitutes for another.
Reaching for the wrong one is how the last pass lost most of its time.

*Which rule wins?* Fix it in the **layer**, above — never by raising specificity and never
with `!important`. The layer order exists so a utility beats the sheet it replaces without
an arms race. `getComputedStyle(el)` names the value that won; `el.matches(selector)` says
whether your selector matched **at all**, which is the failure the white-on-white Delete
button actually was — a rule that looked right and was never applied to anything.

*Is a value wrong?* Use the token, then `npm run lint:design`. A literal that is genuinely
off-scale needs a `--write` re-freeze plus a sentence in the commit saying why.

*Is a class name wrong?* A `cva()` table in the component (`class-variance-authority` is
already a dependency), so the accepted variants are a type and the emitted classes a value.
No tool can check a stylesheet against class names the component never emits.

*Is it geometry, contrast, or overlap?* **No linter and no unit test will find this.**
Measure it in a real browser and read numbers, not impressions:

| symptom | the number that settles it |
|---|---|
| a box that will not scroll | `getComputedStyle(el).minHeight` — `100vh` with `overflow:auto` is an unbounded box, so the *document* scrolls instead |
| something covering something else | `getBoundingClientRect()` on both, plus their `z-index` (the floating controls sit at 10002, the sidebar at 1000) |
| a control eating the phone | `rect.height / window.innerHeight` at 375x812 |
| text nobody can read | the contrast ratio of the two *resolved* colours; 1.0 is a blank rectangle |

*Is it a11y state?* Read the accessibility tree, not the pixels. `aria-expanded` /
`aria-pressed` on a toggle is invisible in a screenshot and obvious in the tree.

**`npm run screenshots` captures the app's states to PNG** (`frontend/scripts/screenshots.mjs`,
Playwright + Chromium): desktop 1440x900 and phone 375x812, signed in and signed out, sidebar
open and closed, workbench collapsed and expanded — eight files. Both servers must be up
(`.claude/launch.json` starts them as `backend` and `frontend`); credentials come from
`SHOT_USER` / `SHOT_PASSWORD` so nothing usable is committed, and `SHOT_OUT` redirects the
output when you do not want eight more PNGs in the tree.

The protocol is the whole point: **run it before and after a change and look at the pair.**
It is deliberately **not a CI gate** — pixel gating needs a seeded corpus and a pinned font
stack, and without those it fails on the day somebody upgrades Chromium rather than the day
the UI breaks. It earned its place on the first run, twice: a floating control covering the
sidebar's own Collapse button, and a `padding-left` that pushed the brand block into the
button at the other end of the same row. Both were obvious on screen and invisible to every
suite, which were all green throughout.

**What vitest cannot do here, in principle.** jsdom has no layout engine, and it fails
*convincingly*: `getBoundingClientRect()` returns all zeros, `offsetHeight` is 0, `matchMedia`
is not a function — while `getComputedStyle(el).height` cheerfully returns the **declared**
`200px` that no layout ever computed. So a component test pins class names, ARIA and
behaviour, and can never see a clipped panel, an overlap, or a composer taking 68% of a
phone screen. That is the line between `npm test` and `npm run screenshots`, and it is why
both exist.

**What not to reach for.** No CSS-in-JS runtime and no second component library: this app
already runs two systems — the 73 legacy sheets and Tailwind — and is spending down to one.
A third makes it three. Do not add a pixel-diff CI gate for the reason above, and do not
"fix" a cascade problem by re-freezing the design baseline.

### Regular expressions

Sixteen patterns in this repository backtracked super-linearly (`S8786`, fixed
2026-09-03), and the fix has three shapes, in order of preference:

- **A negated class instead of a greedy `.`** -- `\|[^|\n]+\|` rather than
  `\|.+\|`. This is usually not a performance change at all but a statement:
  a table cell does not contain its own delimiter, and saying so removes the
  ambiguity the engine was exploring.
- **A bounded quantifier** -- `\s{0,8}` rather than `\s*`, the form the
  streaming redactor already used.
- **A possessive quantifier** (`[ \t]++`, Python 3.11+) where backtracking into
  the run could never succeed anyway, so the bound would be arbitrary.

**Two of the sixteen were wrong, not merely slow, and for the same reason:
`\s` matches a newline.** Under `re.MULTILINE` that let a pattern anchored with
`^...$` reach past the end of the line it started on -- the clarification parser
paired a bare `-` on one line with a field name several lines below it, and the
lock parser could pick up an environment marker belonging to the next
requirement. Prefer `[ \t]` whenever the intent is "spaces within this line".

**Anything reading text a user or a document supplied is worth measuring rather
than reasoning about.** The clarification parser took 117ms on 800 lines of
whitespace and grew with the square; it takes 0.4ms now. But do not assert the
timing in a test -- a clock is a bad thing to assert on in CI. Assert the
property that removed it, which for both of these was "this matches within one
line".

Changing a pattern is a behaviour change until proven otherwise, and the proof is
cheap: run the old and the new against the same inputs and diff. That is how the
three structure detectors in `app/agents/rag/config.py` and the lock parser were
verified (60 inputs and 336 pins respectively, zero differences).

### Testing Strategy

`tests/` was cleared ahead of the v0.7 rewrite and is being rebuilt incrementally: each bug
fix lands with the regression test that would have caught it, rather than as a separate
back-filling effort. As of 2026-09-04 there are 1429 tests covering the chat round trip,
conversation context, graph routing, clarification, the async load guard, engine reuse,
answer safety, reader-facing citation numbering, stage-timeout degradation, the governed
tool stack with its multi-step loop and approve-then-resume cycle, retrieval
module-global isolation, connector persistence, streaming redaction, two-phase retrieval,
complexity- and plan-driven retrieval width, caller deadlines, skill-shaped synthesis,
follow-up completion, answer provenance, an answer that shows the reader none of the
machinery that produced it, a router cache that opens no event loop, a guard that every
Settings field has a reader, a guard that no module reads the environment behind
`Settings`'s back, the configuration-centre source with its three-step degradation, the
admin configuration surface with the writes it refuses, one vocabulary for audit actions,
an ASCII API document, a grounding SLO that measures answers, and the five functions
unpicked in the 2026-09-03 complexity pass -- document ingestion, the distributed query
guard, candidate collection, route selection, the document visibility rules and upload
storage, each characterized against its old implementation before being split, and the
regular expressions that backtracked super-linearly over user-supplied text, the
multimodal source that had never had anything to retrieve, and the sensitive-content gate,
whose suite is mostly negative assertions because a scanner reports PASS just as readily
when its checks match nothing, an offline retrieval metric measured through the real
orchestrator over a corpus that ships with the repository -- whose most important test
proves the metric can *fail*, since a scope mismatch scores 0.00 for reasons unrelated to
retrieval -- a graph triplet whose confidence records which extractor produced it, planner
sub-queries that reach the retrievers, per-query result lists that are interleaved rather
than concatenated before RRF, an NLI stage that runs off the event loop and scores Chinese
and reports which scorer ran, a governed read tool whose summary cannot carry an
instruction, and the China-specific PII patterns that had never existed --
pinned by what each identifier is *called*, not only that it is caught, since three of them
were already caught under the wrong name -- and by an adversarial false-positive pass, which is
where all three defects in that change were found.

**That count is not 1236 independent assertions, and the number before it was stale.** Two
guards are parametrized one case per module — the audit-action scan over `app/` (376) and
the ASCII scan over `app/api` (60) — so they grow with the codebase rather than with
coverage. The real baseline on 2026-09-03 was 651, not the 538 this paragraph claimed:
the count had not been updated since 2026-09-02 while tests kept landing with fixes.
Parametrizing per module is deliberate — a failure names the file, and a new module is
covered the day it is added, where one test looping inside a single assertion reports the
first offender and stops — but it does mean this total is not comparable across the change
that introduced them.

`tests/security/` (743 of those, 376 being the per-module audit-action scan) pins the
user-data isolation invariants — see
`docs/superpowers/plans/2026-08-29-user-data-isolation.md`. That plan is complete
(phases 0-4) and all 8 of its `xfail(strict=True)` markers are cleared; keep using the same
pattern for a new gap, so a fix that makes the test pass fails the suite until the marker
is removed. `test_no_unrestricted_retrieval.py`
is a ratchet rather than a plain assertion: `KNOWN_OFFENDERS` records how many
unrestricted `similarity_search` calls each module has, and the count may only go down.
It is currently empty.

User questions must not reach the logs: `question_ref()`
(`app/services/observability/log_safety.py`) gives a stable digest instead, and
`tests/security/test_no_question_text_in_logs.py` enumerates every `logger.*` call via AST
to keep it that way. Truncating (`question[:50]`) does not count as redaction. Its
allowlist is keyed on `path::enclosing_function`; keying it on a line number made it
fail on any edit *above* an exempt call, which trains readers to re-point the entry
instead of asking whether a real leak appeared.

`test_streaming_redaction.py` tests the property, not the examples: for eight secret shapes
it asserts the streamed output equals the final redaction at *every* split offset, and that
what was already emitted is always a prefix of the final redaction. A chunk boundary is the
only thing that distinguishes streaming DLP from the batch kind, so a fixed set of chunk
sizes would test the wrong thing.

`pytest` is configured in `pyproject.toml` (`testpaths = ["tests"]`, strict asyncio mode).
CI runs it on every push and pull request (`.github/workflows/ci.yml`), together with ruff
and an OpenAPI endpoint census that fails if a refactor silently drops routers.

The frontend has vitest tests too: `src/**/*.test.ts` **and** `src/**/*.test.tsx`, run by
the `frontend` CI job, which also runs eslint (`--max-warnings 25`, itself a ratchet), `tsc`,
`npm run lint:design`, and the build. The `.tsx` half of that glob was missing until
2026-09-01, so every component suite was silently skipped — a component test cannot be
written in a `.ts` file. The default `environment` stays `node`; the two component suites
(`ExecutionTracePanel.test.tsx`, `ChatRuntimePanels.test.tsx`) opt into jsdom per file with
`// @vitest-environment jsdom`, rather than making the pure-logic suites — most of them — pay
for jsdom setup.

`pendingApproval.test.ts` pins that a governed action awaiting confirmation travels with
the question that produced it: ChatPage first tracked the question in a ref every
`ask` call site had to remember to set, and the clarification-complete path did not, so
confirming after a clarified query would have re-sent a stale question.
`storeReset.test.ts` covers the Zustand `reset()` that App.tsx calls on logout and on
any identity change: the stores outlive a logout, so a field added to a store but forgotten
in its `INITIAL_STATE` would show the next person on a shared browser the previous user's
data. The test discovers fields rather than listing them, so it catches that drift.
That suite is 56 tests across 9 files — small, and deliberately aimed at the things a
screenshot cannot check. `AdminConfigEditor.test.tsx` is the newest: it pins that a value
pinned in the process environment renders disabled, and that only edited fields are sent —
posting the whole form would turn a page load into a write of every value, and a stale read
into an overwrite. Note that auto-cleanup between renders only registers when vitest runs
with `globals`, which this project does not; a component test must call `cleanup()` itself
or every later query in the file finds two of everything.

Note: do not use `len(app.routes)` to count endpoints. FastAPI 0.138+ stores an
`_IncludedRouter` wrapper in `app.routes` instead of flattening child routes, so that number
varies by version. Count OpenAPI operations instead; the current baseline is 153 (CI asserts a >= 140 floor).

### Sensitive content gate (added 2026-09-04)

`scripts/check_sensitive.py` decides what may leave this machine. It runs in two places and
in three modes:

```bash
python scripts/check_sensitive.py                          # every tracked file (CI)
python scripts/check_sensitive.py FILE...                  # staged files (pre-commit)
python scripts/check_sensitive.py --tree DIR --expect N    # a delivery copy on disk
```

**The file list comes from `git ls-files`, not from a filesystem walk, and that is the whole
design.** A working tree legitimately contains `data/`, `logs/`, `internal_docs/`, `.venv/`
and `node_modules/` — all gitignored — so walking the filesystem would fail on every run and
be switched off within a week. Asking git instead turns the forbidden-path check into one
that means something: it fires on a `git add -f data/app.db`, which is how a database
actually reaches a repository.

Both hooks run it, and neither is redundant. The pre-commit hook blocks a secret **before it
enters history**, which is the only point at which removing one is cheap — once pushed, a
credential is compromised and the answer is rotation, not a revert. CI is the copy that
catches a `--no-verify` and a fresh clone where nobody ran `pre-commit install`.

**Nothing is rewritten automatically, and that is deliberate.** An auto-redacting commit hook
would mangle `tests/security/test_streaming_redaction.py` and `tests/services/test_answer_safety.py`,
whose fixtures *are* an AWS example key id, an `sk-` prefixed dummy and an OpenSSH private-key
header. A sweep that "desensitizes" the redaction feature's own test data breaks the security
suite, and does it in the worst possible way: after the suite has gone green. The gate reports
and blocks; a human removes the value.

Note that this section describes those fixtures rather than quoting them, and says "a Windows
user-profile path" rather than writing one. The first draft quoted all four verbatim and the
gate refused the commit — correctly. Adding `CLAUDE.md` to the baseline was the wrong fix: it
is long and edited constantly, so exempting it would mean a real key pasted here is never seen
again.

**The two baselines are ratchets, not allowlists.** `SECRET_BASELINE` (6 files) and
`LOCAL_PATH_BASELINE` (3 files) name individual files, not directories — exempting all of
`docs/` would have let a real key land in any document in the project. And on a whole-repository
scan, a baseline entry that no longer matches anything is itself a failure, so the exemption
list can only shrink. Same shape as `KNOWN_OFFENDERS` in `tests/security/` and
`scripts/design-scale-baseline.json`.

Three of those entries are the gate's own files, added after it refused the commit that
introduced them: the local-path pattern spells out git-bash's spelling of the Windows user
directory and therefore matches its own source, and the test cannot demonstrate that a
private-key header is caught without containing one. This paragraph was itself rejected once
for quoting that prefix — the gate is difficult to write about, which is a good sign.

**What it cannot catch**, which matters more than what it can:

- It matches *shapes*. A bare 32-character hex string, or a database password with no
  recognisable prefix, passes.
- It reads text files by extension allowlist. Anything inside a `.png`, `.pdf` or `.xlsx` is
  invisible to it — the eight tracked screenshots were checked by eye (they use the
  `walkthrough_alice` demo account and a public question).
- **It never looks at `.git/`.** History has to be audited separately. It was, on 2026-09-04:
  all 711 commits scanned for credential shapes and every hit was a placeholder
  (`NEO4J_PASSWORD=changeme`, an `sk-proj-` stub, the AWS documentation key), plus the
  once-committed `logs/web_activity/*.jsonl` (5 rows, all `test_user`/`Test query`, ip and UA
  `None`) and the once-committed demo corpus (`XX科技有限公司`). `internal_docs/` has never
  been committed.

#### Handing the whole folder to someone

Export with git; do not copy the folder and delete things afterwards.

```bash
git clone --no-hardlinks . ../querymind-delivery
python scripts/check_sensitive.py --tree ../querymind-delivery --expect 958
```

A clone contains only committed content by construction, so `.gitignore` — a rule this project
has already applied 700-odd times — does the filtering. "Copy, then `rm -rf` the sensitive
directories" is a denylist, and it misses `.venv/pyvenv.cfg` and `querymind.egg-info/PKG-INFO`,
both of which carry the developer's absolute path. Update `--expect` from
`git ls-files | wc -l`.

Two things learned doing this the first time:

- **Verifying the copy contaminates the copy.** Running ruff inside it left `.ruff_cache/`;
  running `pytest --collect-only` created `data/` — the exact directory name being excluded,
  produced by module import. `git clean -xfd` inside the copy is the fix (it cannot touch
  tracked files), and the final scan must come *after* every verification step.
- **A scanner that has never been proven to fail proves nothing.** Before trusting a PASS,
  point it at a directory holding a known secret, a `.db`, an env file with a value and a
  Windows user-profile path, and confirm all four trip and the exit code is 1. Doing that
  caught three defects in this script's own first draft, one of which — a regex where `\\+`
  had been reduced to `\+`, matching a literal plus sign — made every such path undetectable
  while the output looked entirely normal.

## Important Notes

- **Conda environment is mandatory**: Dependencies assume conda-managed packages
- **Do not commit** files in `.gitignore`: `internal_docs/`, `.env`, `data/chroma/`, logs
- **Document organization**: Use `docs/development/daily-logs/YYYY-MM-DD/` for daily work logs (create manually).
- **Bilingual system**: UI and responses support Chinese/English. Language detection is automatic via `language_analytics.py` (100% Chinese or 100% English, no mixing)
- **The OpenAPI document is ASCII**, pinned by
  `tests/api/test_openapi_descriptions_are_ascii.py`, which walks every `description=`
  keyword in `app/api`. The bilingual rule above is about prose shown to *users* — the
  Chinese and English question sets live in `app/agents/clarification/rules.py`; the API
  document is developer-facing and was already English in 80-odd places. The one router
  that was not had its bytes double-encoded (the UTF-8 encoding of a latin-1 misreading of
  UTF-8), so it served `å¼€å§‹æ—¥æœŸ` where the author typed `开始日期`. Nothing failed —
  a mangled description is still a valid string, and only a reader of the docs page would
  ever see it, which is why it survived. That was the only file in the repository in that
  state; the check is a whole-repo decode looking for character runs that round-trip back
  to CJK.
- **SSE streaming**: One subscription
  (`GET /api/v1/orchestration/executions/{execution_id}/events`, served by
  `app/api/routes/public/orchestration.py`) carries two event names. The query endpoint
  returns `metadata.execution_id`, which the client uses to subscribe.
  - `execution_event` — stage events, replayed from the tracker and `ExecutionEventStore`.
  - `answer_fragment` — the answer as it is written (added 2026-08-31, audit #14b).
    `SynthesizerAgentService._generate_streaming` publishes into the process-wide
    `AnswerStreamStore` (`app/orchestration/answer_stream.py`), bound to the execution by a
    ContextVar for the same reason the event store is: the engine is cached and shared, so
    instance state would file one request's fragments under another's id.

  **Fragments are a draft, and a separate event name so a client cannot mistake one for a
  finished answer.** They carry no citation numbering and no reference list — `output_filter`
  decides both, after the whole answer exists and after DLP has settled which citations
  survive — and internal `[E{k}]` markers are stripped rather than rendered. The frontend
  shows the draft in a `local-assistant-stream` bubble and replaces it with the answer from
  the query response.

  **Nothing unredacted may enter that store.** `StreamingRedactor`
  (`app/privacy/streaming.py`) releases only text whose redaction cannot still change: it
  holds back a margin, cuts at whitespace, and confirms `redact(raw[:b])` is still a prefix
  of `redact(raw[:b + margin])` before releasing — a secret like `password = hunter2` begins
  *before* a boundary and crosses it, so a margin at the tail alone is not enough. What was
  emitted is tracked as a string rather than a length, because redaction changes lengths and
  offset arithmetic desyncs. Both redaction pattern sets had their whitespace quantifiers
  bounded (`\s*` → `\s{0,8}`) so a partial buffer cannot make a pattern scan unboundedly.
- **Answer quality telemetry rides the request's own metrics row**, not the audit log
  (wired 2026-09-03). `record_grounding_support`
  (`app/api/transport/middleware.py`) puts the answer's `support_ratio` on the row
  `request_timing_middleware` writes, and `build_ops_alerts` reads it from the same
  `request_rows` its p95 comes from — one window and one definition of "the last N hours"
  for both SLOs, with no new store, retention policy or schema. Before this the SLO
  averaged over audit rows with action `query.run`, which nothing writes, so an average
  over zero samples was **1.0**: a perfect grounding ratio published for a metric never
  once observed, and an alert structurally incapable of firing. Absence is now absence
  (`None`), which is a different claim from 1.0.

  **Not the audit log**, which is where the dead code pointed: its read path is
  `list_audit_logs(limit=2000)`, one window shared by every reader, and a row per query
  would flush every login failure out of it. Degrading the security audit view to feed a
  monitoring metric is the wrong trade.

  **The carrier is `request.state`, and it has to be.** The metrics row is written in the
  middleware's `finally`, after the endpoint returned; `request.state` is backed by the
  ASGI scope dict that `call_next` hands downstream and reads back. A ContextVar cannot
  do this — `call_next` runs the endpoint in its own task, so nothing it sets is visible
  up there, and the failure would look exactly like the `query.run` one: plumbing that
  reads empty forever. `tests/services/test_ops_slo_grounding.py` drives a real app
  through `TestClient` rather than asserting it in prose.

  Two limits, both already true of the p95 beside it: the ring is process-local, so a
  restart empties it and each worker sees only its own. Crossing that boundary is a
  time-series-database decision, not a change to these five lines.

- **Both Dockerfile stages install with `--no-install-recommends`**, and name
  `ca-certificates` explicitly rather than receiving it as a recommends of
  `curl` (`docker:S6500`). Dropping recommends without naming it would have left
  TLS trust resting on what the base image happens to ship, which is the sort of
  thing that works until the base image changes.
- **A convenience must never be able to fail a login** (2026-09-03). The login
  form's "remember me" stored the username through a module called
  `secureStorage`, which XOR'd it against a key hardcoded three lines above and
  base64'd the result. `btoa` throws above code unit 255, so a Chinese username
  threw inside the login handler's `try`, *before* `onLogin` -- the server had
  accepted the credentials, the exception was caught as a login failure, and the
  user saw a generic error that repeated until they unticked the box. In an
  application whose reason for existing is that it works in Chinese.
  `frontend/src/lib/rememberedUsername.ts` replaces it: a remembered username is
  a convenience, not a secret, so it is stored as itself, and every access is
  wrapped because a private window throws on read too. The lesson is not about
  base64 -- it is that the failure of something optional was inside the path of
  something that is not.
- **Third-party GitHub Actions are pinned to a commit**, not a tag
  (`githubactions:S7637`). A tag on somebody else's repository can be moved, and
  these steps run with the workflow's secrets. GitHub's own `actions/*` keep
  their major tags: nobody else can move a tag in that namespace.
  `tests/core/test_ci_workflow_is_loadable.py` enforces it, because the rule
  itself lives in SonarCloud and only runs after a push -- the feedback loop for
  a one-line mistake was a full CI run plus an analysis.
- **`evidence_dedup_key` returns `(kind, payload)`**, both two long. The two
  kinds are computed from different fields, so nothing but the kind keeps a
  content key and a provenance key out of each other's way in the same
  dictionary; a variable-length tuple with a discriminant at position zero only
  implied that.
- **`python:S7503` is 39 open findings and 32 of them are correct.** "async
  without await" cannot see a contract: 22 of those functions are awaited, 4 are
  closures handed to `run_with_timeout`, 3 are default callbacks awaited through
  a variable, and 3 are gathered as coroutines. The remaining 7 have no caller
  because their *classes* have none -- `ImageProcessor`, `ChartAnalyzer`,
  `TableExtractor` and `SmartChunker` are never constructed anywhere in `app/`,
  and nothing outside `app/services/multimodal/` imports the package. Removing
  their `async` would satisfy the rule and leave the dead code; whether that
  subsystem stays is the actual question. The same goes for `python:S7484` on
  `agent_tracking.py`'s SSE poll: no client calls that endpoint, and
  `AgentExecutionTracker` is `threading.Lock`-based, so an `asyncio.Event` there
  would need `call_soon_threadsafe` -- the defect class fixed twice already.
- **Answer provenance**: what a message may claim about where it came from is computed in
  one place — `retrieval_summary` (`app/api/routes/internal/pipeline_contract.py`), from the
  knowledge diagnostics both entry points already carry. **`used` means a source contributed
  evidence, not that it was selected**: a web search that returned nothing is not what a
  reader means by "this answer used the web". The response therefore keeps three states
  apart — `sources` (every source with its status, result count and reason), the derived
  `contributing_sources`, and `web_used` for older readers. There used to be only that
  boolean and **no endpoint set it**: the chat endpoint had no such key and the client
  defaulted a missing value to false, so every answer displayed `web: no`, including ones
  written entirely from web results. It is not only a badge —
  `score_memory_candidate` weights `web_used` at 0.20, so every long-term memory candidate
  had been scored as though the answer were purely local. A source that ran and found
  nothing is worth showing (it explains a thin answer); one skipped because the caller has
  no documents is not a fact about this answer, and the badge leaves it out.
- **Retry logic**: Retrieval retries retain their existing fallback policy; answer regeneration is capped at one retry per request
- **Circuit breaker**: Opens after 5 consecutive failures, closes after 60s cooldown
- **Stage timeouts and degradation** (reworked 2026-08-30): stage ceilings live in
  `Settings.stage_timeout_*` (read by `TimeoutConfig.from_settings`), not in a module
  constant. They bound a *hang*; they are not latency targets, which is why they sit well
  above the P95 target above — the previous hardcoded values (a 2s router covering up to
  three LLM calls, a 5s synthesis) fired on ordinary traffic. A tripped ceiling used to be
  an unconditional 500; now `_run_stage(..., on_timeout=…)` supplies what the run continues
  with, and the stage reports a `failed` event whose `failure_reason` reaches the caller
  through `execution_metadata.workflow_diagnostics`. **`privacy_permission` and
  `output_filter` deliberately have no `on_timeout`** — skipping scope resolution or output
  DLP is a hole, not a degradation — and they are listed in
  `timeout_control.MANDATORY_STAGES`, which exempts them from the total-budget gate so an
  exhausted budget upstream cannot squeeze the output filter out.
- **Caller deadlines** (wired 2026-08-31): `POST /api/advanced-rag/query` takes an optional
  `timeout_ms`, which becomes `PipelineRequest.deadline_at` and reaches
  `ExecutionBudget(config, deadline_at=…)`. It **narrows** `remaining_ms()` and never extends
  it, so a deadline beyond `STAGE_TIMEOUT_TOTAL_MS` does nothing and a caller cannot pin a
  worker by asking for an hour. The wire format is relative and the contract absolute on
  purpose: two clocks need not agree, but a budget consumed across stages must not be
  re-derived at each one. The offset is measured once and everything after it runs on
  `perf_counter`, so an NTP correction cannot move a live request's budget; a naive datetime
  is read as UTC. `MANDATORY_STAGES` still applies — an aggressive deadline is not a way to
  buy out of scope resolution or output DLP. Before this the field was accepted, forwarded
  through `PipelineRequest`, and read by nobody.

  The same wiring opens `request_context` around the workflow, which is what
  `app/services/runtime/request_context.py` exists for and what nothing on the request path
  had ever set. Three helpers check that deadline themselves: the synthesizer's self-review
  and fact-verification exits (both dormant), and `rule_rewrite._llm_rewrite`, which treats
  `remaining_seconds() is None` as "no time left" — so `QUERY_REWRITE_WITH_LLM` was a switch
  that could not turn anything on.
- **Verifier retry affordability**: a retry replays knowledge + synthesis + verification
  (`TimeoutConfig.retry_round_ms`). The verifier now downgrades `retry_retrieval` to
  `degraded` when the remaining budget cannot fund all three, instead of starting a round
  that the total-budget check kills — which turned a merely degraded answer into a failed
  request.
- **`ExecutionBudget.check_budget` had never fired** (fixed 2026-08-30): it tested
  `has_budget()`, whose `required_ms=0` default reduces it to `remaining_ms() >= 0`, and
  `remaining_ms` already clamps at 0. Exhaustion still surfaced, but as the next stage being
  clamped to a 0ms ceiling and cancelled — which reads in a trace as "that stage was slow"
  rather than "the request ran out of time".
- **Concurrent `DDGS()` construction wedges the process, and one query does it.** The web
  retriever builds a `primp.Client` (Rust) that calls back into Python logging on the way
  up; two workers doing that at once parked in `ddgs/http_client.py::__init__` at
  `logging.getLogger` while the main thread stuck in `Thread.start()`, and the server
  answered nothing — `/health` included — at zero CPU. `app/tools/web/search.py` holds
  construction under one lock and searches outside it. The cause is inside a third-party
  Rust client, so this contains the symptom rather than pretending to fix it there.
- **A stage failure reaches the API wrapped, twice.** `run_with_timeout` re-raises as
  `StageExecutionError` with the original on `__cause__`, and LangGraph may wrap that again,
  so `except SomeSpecificError` at an endpoint never fires — the first attempt at the fix
  below did exactly that and still returned 500.
  `app/api/routes/public/query.py::_retrieval_failure` walks the cause chain instead.
- **Every retrieval source failing is a 503, not a 500** (fixed 2026-09-02). With an empty
  corpus `vector` and `bm25` are *skipped*, so `web` is the only source that runs; when
  DuckDuckGo throttled, half the queries returned `500 "Unable to process advanced query"`,
  naming neither cause nor remedy. 500 says look at this service, 503 says look at what it
  depends on, and only one of those was true. The sibling case — sources never attempted,
  which must return quietly — was fixed earlier in `RAGAgentService.retrieve`.
- **Lazy imports on the request path are a deadlock risk, not a startup optimization**
  (found 2026-09-02 by running one query). `from ddgs import DDGS` does not import ddgs:
  the name is a proxy whose metaclass runs `importlib.import_module` on the first *call*,
  holding its own lock, and the module it imports calls `logging.getLogger` on the way in.
  One query starts several web searches on separate worker threads, so those are several
  concurrent first calls — three threads inside `_load_real`, one parked in
  `logging.getLogger`. **It wedged the whole process, not just the request**: the stuck
  thread holds the logging lock, so uvicorn's per-request access log blocks and `/health`
  stops answering while the event loop sits idle and healthy. The tell is a hang at zero
  CPU. `app/tools/web/search.py::_resolve_ddgs_eagerly` resolves it at import, when one
  thread is running; `tests/services/test_web_search_import.py` asserts no first-call
  import remains. The call site's `timeout=10` never applied — it bounds the HTTP request,
  not the import.
- **LLM request timeout**: `Settings.llm_request_timeout_seconds` is passed to the OpenAI and
  Anthropic chat clients. Without it a hung provider connection pinned a pool thread for the
  life of the process: an `asyncio` stage timeout unblocks the event loop but cannot cancel
  the thread inside a blocking `invoke()`. `ChatOllama` takes no equivalent parameter and is
  still uncapped.
- **Per-source vs per-stage timeouts**: `RAGAgentService`'s per-source bound derives from
  `KNOWLEDGE_SOURCE_TIMEOUT_MS` so it stays under `STAGE_TIMEOUT_RETRIEVAL_MS`. It used to be
  a hardcoded 30s under a 10s stage ceiling, so the inner bound could never fire.
- **Admin ops benchmark/replay corpus** (fixed 2026-08-30): `POST /admin/ops/benchmark/run` and
  `POST /admin/ops/replay/run` run their queries under the requesting admin's identity. They used to
  pass no actor at all, and every query died in the pipeline's first node — `privacy_permission`
  resolves an access scope and fails closed with "authenticated user identity is required". The
  consequence of the fix is that a run measures the corpus that admin can see (the shared
  `data/docs/` set plus their own and public documents) rather than a fixed corpus, so trends from
  two admins with different visible documents are not directly comparable. Scoping the runs to
  `data/docs/` instead was rejected: it would measure something no real query ever does, and would
  need a synthetic actor, reopening the fail-closed hole the resolver exists to close.
- **Benchmark query set** (2026-08-30): `run_benchmark` reads `data/eval/benchmark_queries.txt` if
  present, otherwise the tracked default `config/eval/benchmark_queries.txt`. It previously read only
  the `data/` path, which is gitignored runtime state — absent on every checkout where nobody placed
  it by hand, so the job died with "benchmark query set is empty" inside the background queue, where
  the endpoint's 202 response never surfaces it. `#` starts a comment in that file. The shipped set is
  a corpus-agnostic starter: it exercises pipeline latency and route branches, but grounding and
  citation numbers only mean something once the queries match documents actually in the corpus.
- **Session management**: Frontend supports session rename and pin features (added 2026-08-16). See `docs/development/daily-logs/2026-08-16/` for implementation details.
- **Clarification does not decide retrieval** (2026-08-30): missing fields ride on
  `RouteDecision.clarification_fields`, not on a substitute `route="clarification"`.
  The router used to return early with that route *before the LLM router ran*, and
  its `allowed_capabilities={"rag"}` removed graph and web from every
  comparison-shaped question -- which mattered most where it was least visible,
  since interactive clarification cannot happen inside the pipeline and the run
  continued with the original question on a route nothing had chosen for it.
- **Clarification System** (added 2026-08-17, revised 2026-08-29): Dynamic clarification based on intent complexity, capped by `max_rounds_for(intent)` — one round per field the question catalogue actually has a question for, so `rag_design`: 4, `document_comparison`: 1, and anything already complete or unrecognised: 0. (This bullet used to quote the hand-written table those numbers replaced on 2026-08-29 — 7 and 5 — which promised rounds that could not happen; see "Dormant by design" above.) Key service: `app/agents/clarification/service.py` and `rules.py`, reached through the resumable `/api/v1/clarification/check` HTTP endpoint (`app/api/routes/public/clarification.py`). Questions exist in Chinese and English (`_QUESTIONS_ZH` / `_QUESTIONS_EN`), selected from `force_language` or the query's script.

  **There was also a LangGraph `clarification` node, and it was removed on 2026-09-04.**
  It spent a `route_timeout_ms` ceiling and one clarifier call per incomplete question to
  produce two state values (`clarification`, `complete_query`) that nothing in `app/` read.
  It could not have done otherwise: the multi-round state lives in the session store behind
  the HTTP endpoint, so a graph node has no collected context to pass and the clarifier
  therefore always returned `action="ask"` — which the node logged and ignored, continuing
  with the original question. Feeding it that store from a graph node would have created a
  second, quieter definition of a clarification round, which is the failure this file
  already describes for the round counter. `RouteDecision.clarification_fields` still
  carries what is missing and `RouterDecision.completeness` still reports it;
  `tests/orchestration/test_clarification_is_not_a_pipeline_stage.py` guards that the
  deletion removed the no-op and not the feature. `EventStage` and the frontend's
  `EXECUTION_STAGES` lost the entry together, since an unknown stage makes the UI drop the
  event silently.
- **State management**: Frontend uses Zustand for global state, not Redux or Context API

## Common Issues

**"ModuleNotFoundError"**: Verify conda environment is activated
**"Neo4j connection failed"**: Neo4j is optional; system falls back to vector-only retrieval.
To actually start it locally, `make up` (and `make down` to stop it). That command
was broken until 2026-09-04 -- it ran `docker compose up -d neo4j` with no `-f`,
and there is no compose file in the repository root, so it only ever printed "no
configuration file provided". It now names deploy/compose/compose.yaml plus the
dev overlay, supplies `.runtime/development.env` (compose.yaml declares
NEO4J_PASSWORD with `:?`, so rendering fails without it), and deliberately passes
no `--project-directory`: the relative paths in those files are written for
deploy/compose/ as the base, and overriding it sends `env_file: ../../.runtime/...`
and the `../../app` bind mounts two levels too high.

**The graph ports are published in development only.** compose.yaml maps nothing
-- containers reach each other over the `querymind` network and the backend uses
`bolt://neo4j:7687` -- but a locally run `uvicorn` is not on that network, and
`NEO4J_URI` defaults to `bolt://localhost:7687`. So compose.dev.yaml publishes
7474 (Browser) and 7687 (Bolt) on `127.0.0.1`, like every other port in that
file: this Neo4j holds a password from `.runtime/`, and `0.0.0.0` would offer it
to the local network. `tests/core/test_dev_compose_is_usable.py` pins both halves
-- the ports exist in development, and they still do not exist in production.

Note what you will see once it is up: with `MODEL_BACKEND=local` the graph is
**empty by design**, because rule-extracted triplets are now correctly filtered
out (see "Knowledge graph extraction"). An empty Neo4j Browser there is the
system working, not a broken ingest.
**Frontend CORS errors**: Ensure backend is running on port 8000

## Documentation Management

### Daily Work Logs

All daily work should be documented in `docs/development/daily-logs/YYYY-MM-DD/` (create the
folder and files manually — `scripts/create_daily_log.py` was removed ahead of the v0.7 rewrite).

Each day should include:
- `plan.md` - Daily goals and tasks
- `implementation.md` - Code changes and technical details
- `decisions.md` - Technical decisions and rationale
- `summary.md` - Completion status and lessons learned

**Important**: Keep project clean by moving any temporary documentation created elsewhere in the repo into the corresponding date folder at end of day. See [docs/development/daily-logs/README.md](docs/development/daily-logs/README.md) for detailed guidelines.
