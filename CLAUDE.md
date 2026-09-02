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

Note (2026-08-28): `tests/` and `scripts/` were cleared ahead of the v0.7 rewrite. `scripts/`
holds exactly one file, `scripts/audit/frontend_audit.py`, and still no
`scripts/init_db.py`; `tests/` is being rebuilt incrementally alongside bug fixes — see
Testing Strategy below.

**Tests and lint**
```bash
make test                           # pytest -q
make lint                           # ruff check . && ruff format --check .
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
249 settings fields (2026-09-01). See `docs/superpowers/plans/2026-08-29-backend-full-audit-remediation.md`
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
   reworked 2026-08-30). One action is registered today (disabling an owned
   integration). Selection is **multi-step**: select → invoke → observe → repeat,
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
3. **Answer validation**: Citation completeness, hallucination detection, NLI checks, and
   **sentence grounding** — `apply_sentence_grounding`
   (`app/services/retrieval/citation_grounding.py`), reached from
   `app/orchestration/finalization.py`, scores each sentence's token overlap with the
   evidence and hedges the ones under 0.22. It skips sentences that make no claim, which is
   not a nicety: it once counted a bare `[1]` as a sentence, found it unsupported, and
   hedged the attribution instead of the claim.
4. **Safety checks**: Two independent regex redaction paths, with different pattern sets.
   `app/services/answer_safety.py` runs on every finalized answer and covers OpenAI-style
   keys, AWS access key ids, private-key headers, and `password=`/`token=` assignments;
   it is gated by `ANSWER_SAFETY_SCAN_ENABLED`. `app/agents/validation/rules.py`
   additionally matches SSN, credit-card, email and phone patterns, and runs inside the
   validation cascade reached through the verifier. There is no content-moderation/toxicity
   filter and no bias-detection implementation.

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
the two genuinely caller-less ones in a documented allowlist. A partial guard would be
worse than none.

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

BM25 keeps one prebuilt index per access scope (`_load_scoped_bm25`, LRU), and separates
matching from ranking: a document is a candidate if it shares a term with the query, and
BM25 only orders the candidates. Do not reintroduce `score > 0` as the membership test —
BM25 IDF is negative for a term present in most documents, so in a small scope (one chunk,
now a routine case) every term scores below zero and matching documents get dropped. A
negative `bm25_score` in the output is normal and harmless: RRF fuses on rank, not score.

### Knowledge Agent and retrieval execution

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

### Retrieval Strategy

**Hybrid Retrieval** ([app/retrievers/hybrid/retriever.py](app/retrievers/hybrid/retriever.py)):
- **Vector search**: Sentence-Transformers BGE-M3 embeddings → ChromaDB
- **BM25 search**: Jieba tokenization → Rank-BM25
- **Fusion**: Reciprocal Rank Fusion (RRF)
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
talked out of it from the admin UI.

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

**What an administrator may change is an allowlist**, `app/core/config_schema.py`, not an
annotation per field. `Settings` has 236 of them; annotating individually would scatter a
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
than a default: each consumer either reads `get_settings()` per use, or is held by an object
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

Monitor these when modifying retrieval or synthesis:
- **Router accuracy**: Target >95% on test queries
- **Citation completeness**: Target >90% (answers with evidence should cite it)
- **P@5 (Precision at 5)**: Target >0.85 for retrieval
- **Latency P95**: Target <5 seconds for standard queries

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
freezes each file's current count of off-scale literals (135 radii, 194 shadows at the
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

### Testing Strategy

`tests/` was cleared ahead of the v0.7 rewrite and is being rebuilt incrementally: each bug
fix lands with the regression test that would have caught it, rather than as a separate
back-filling effort. As of 2026-09-01 there are 528 tests covering the chat round trip,
conversation context, graph routing, clarification, the async load guard, engine reuse,
answer safety, reader-facing citation numbering, stage-timeout degradation, the governed
tool stack with its multi-step loop and approve-then-resume cycle, retrieval
module-global isolation, connector persistence, streaming redaction, two-phase retrieval,
complexity- and plan-driven retrieval width, caller deadlines, skill-shaped synthesis,
follow-up completion, answer provenance, an answer that shows the reader none of the
machinery that produced it, a router cache that opens no event loop, a guard that every
Settings field has a reader, a guard that no module reads the environment behind
`Settings`'s back, the configuration-centre source with its three-step degradation, and the
admin configuration surface with the writes it refuses.

`tests/security/` (154 of those) pins the user-data isolation invariants — see
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
That suite is 40 tests across 7 files — small, and deliberately aimed at the things a
screenshot cannot check. `AdminConfigEditor.test.tsx` is the newest: it pins that a value
pinned in the process environment renders disabled, and that only edited fields are sent —
posting the whole form would turn a page load into a write of every value, and a stale read
into an overwrite. Note that auto-cleanup between renders only registers when vitest runs
with `globals`, which this project does not; a component test must call `cleanup()` itself
or every later query in the file finds two of everything.

Note: do not use `len(app.routes)` to count endpoints. FastAPI 0.138+ stores an
`_IncludedRouter` wrapper in `app.routes` instead of flattening child routes, so that number
varies by version. Count OpenAPI operations instead; the current baseline is 151 (CI asserts a >= 140 floor).

## Important Notes

- **Conda environment is mandatory**: Dependencies assume conda-managed packages
- **Do not commit** files in `.gitignore`: `internal_docs/`, `.env`, `data/chroma/`, logs
- **Document organization**: Use `docs/development/daily-logs/YYYY-MM-DD/` for daily work logs (create manually).
- **Bilingual system**: UI and responses support Chinese/English. Language detection is automatic via `language_analytics.py` (100% Chinese or 100% English, no mixing)
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
- **Clarification System** (added 2026-08-17, revised 2026-08-29): Dynamic clarification based on intent complexity, capped by `max_rounds_for(intent)` — one round per field the question catalogue actually has a question for, so `rag_design`: 4, `document_comparison`: 1, and anything already complete or unrecognised: 0. (This bullet used to quote the hand-written table those numbers replaced on 2026-08-29 — 7 and 5 — which promised rounds that could not happen; see "Dormant by design" above.) Key services: `app/agents/clarification/service.py` and `rules.py`, wired as both the LangGraph `clarification` node and the resumable `/api/v1/clarification/check` HTTP endpoint (`app/api/routes/public/clarification.py`) — the two share one implementation. Questions exist in Chinese and English (`_QUESTIONS_ZH` / `_QUESTIONS_EN`), selected from `force_language` or the query's script. Inside the pipeline the clarifier has no collected context and therefore always asks; the node logs that and continues with the original query rather than failing the request — interactive clarification belongs to the HTTP endpoint.
- **State management**: Frontend uses Zustand for global state, not Redux or Context API

## Common Issues

**"ModuleNotFoundError"**: Verify conda environment is activated
**"Neo4j connection failed"**: Neo4j is optional; system falls back to vector-only retrieval
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
