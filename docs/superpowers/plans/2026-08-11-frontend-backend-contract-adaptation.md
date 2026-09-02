# Frontend-Backend Contract Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development while implementing each task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the React frontend consume the current FastAPI query, authentication, session, document, error, and SSE contracts without changing backend behavior.

**Architecture:** Keep `frontend/src/services/http/client.ts` as the single HTTP transport and `frontend/src/lib/*-api.ts` as domain clients. Standard queries use the backend's versioned SSE stream; strict-quality and advanced queries use their distinct JSON endpoints and are normalized only at the UI boundary, without pretending that their schemas are identical.

**Tech Stack:** React 18, TypeScript 5.9, Vite 6, Vitest 3, FastAPI/Pydantic/OpenAPI as contract source.

## Global Constraints

- Do not modify backend files or backend contracts.
- Do not add production orchestration that bypasses `RAGPipeline`.
- Preserve `standard`, `strict_quality`, and `advanced` as distinct profiles.
- Do not use `any`, mock endpoints, hard-coded answers, destructive Git commands, commits, or unrelated refactors.
- The checkout is on `main` with extensive user-owned changes. Touch only files listed below and preserve their current content.
- Write a failing frontend test before each production behavior change and record the red/green commands in the implementation report.

---

### Task 1: Typed HTTP transport, errors, timeout, and cancellation

**Files:**
- Modify: `frontend/src/services/http/client.ts`
- Create: `frontend/src/services/http/client.test.ts`

**Interfaces:**
- Consumes: FastAPI errors shaped as `{detail: string | validation-item[]}` or text; cookie authentication with `credentials: "include"`.
- Produces: typed `ApiError` with `status`, safe user message, and request helpers that honor caller cancellation plus an explicit timeout.

- [ ] Add failing tests proving string detail, 422 detail arrays, plain-text errors, 401/403 preservation, timeout, and external `AbortSignal` cancellation.
- [ ] Run `npm.cmd test -- --run src/services/http/client.test.ts`; confirm failures are caused by missing behavior.
- [ ] Replace `safeParsePayload(): any` and `as any` with `unknown` plus type guards; do not expose stack traces or arbitrary internal objects.
- [ ] Add timeout signal composition for normal requests; ensure an external abort remains distinguishable as cancellation. Do not automatically retry non-idempotent query requests.
- [ ] Re-run the focused test and then the complete frontend suite.

**Acceptance:** 400/401/403/404/422/500 payloads become safe `ApiError`s, callers can cancel, normal requests time out, and no new `any` is introduced.

### Task 2: Exact Profile clients and schemas

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/lib/query-api.ts`
- Create: `frontend/src/lib/query-api.test.ts`

**Interfaces:**
- Consumes: `POST /query`, `POST /query/stream`, `POST /api/v1/enhanced/query`, and `POST /api/advanced-rag/query`.
- Produces: `PipelineProfile = "standard" | "strict_quality" | "advanced"`; exact request/response types; a small UI-facing normalized result that retains citations, quality report, route, and execution metadata.

- [ ] Add failing tests asserting each real route, method, content type, request field spelling, and response mapping, including empty citations and absent optional quality data.
- [ ] Run the focused query client tests and confirm expected failures.
- [ ] Implement standard stream form fields, standard JSON response, strict-quality JSON fields (`query`, `session_id`, `retrieval_strategy`, `agent_class_hint`, `enable_context_tracking`), and advanced JSON fields (`query`, `retrieval_strategy`, `enable_decomposition`, `enable_self_rag`).
- [ ] Do not send standard-only fields to advanced or invent session persistence for advanced.
- [ ] Correct shared Pydantic-aligned types, including citation metadata/document/page fields, response `ok` fields, and nullable session message IDs.
- [ ] Re-run focused and complete frontend tests.

**Acceptance:** The three profile submissions hit the exact backend endpoints with profile-specific bodies and preserve their distinct response information.

### Task 3: Versioned SSE parser and lifecycle

**Files:**
- Modify: `frontend/src/pages/chat/hooks/chatStreamAdapter.ts`
- Create: `frontend/src/pages/chat/hooks/chatStreamAdapter.test.ts`
- Modify: `frontend/src/pages/chat/hooks/useMessageActions.ts`
- Modify: `frontend/src/pages/chat/hooks/streamMessageUpdater.ts`
- Modify if required: `frontend/src/pages/chat/hooks/streamUtils.ts`

**Interfaces:**
- Consumes: data-only `ExecutionEvent v1` frames from `/query/stream`; legacy frames only as backward-compatible input.
- Produces: progressive content, execution ID, terminal-complete detection, failed-event errors, abnormal-EOF errors, and deterministic cancellation/unmount cleanup.

- [ ] Add failing parser tests for data-only v1 frames, named v1 frames, legacy frames, CRLF, frames split across chunks, malformed JSON, unknown schemas, and multiple `data:` lines where applicable.
- [ ] Add failing lifecycle-focused tests for complete, failed, EOF-before-complete, caller cancel, no response body, and no update after disposal.
- [ ] Run focused tests and confirm contract-specific failures.
- [ ] Parse v1 before legacy and accept both named and unnamed v1 data frames. Read answer chunks only from metadata `content`, execution ID only from metadata `execution_id`, failure from `status="failed"`, and success only from `stage="complete"` plus completed status.
- [ ] Flush the final decoder buffer, release/cancel the reader, abort on unmount, ignore stale request completions, and remove automatic non-stream re-execution after a network break.
- [ ] After successful standard completion, load the real session detail to obtain persisted answer/citations/metadata. Empty citations and optional data must remain safe.
- [ ] Re-run focused and complete frontend tests.

**Acceptance:** Standard answers render progressively, failed/abnormal streams are visible errors, cancellation is quiet and final, and an unmounted or superseded request cannot update state.

### Task 4: Profile-aware chat UI and unsupported route removal

**Files:**
- Modify: `frontend/src/pages/chat/hooks/useChatPageState.ts`
- Modify: `frontend/src/pages/chat/components/ChatComposer.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`
- Modify: `frontend/src/pages/chat/hooks/useMessageActions.ts`
- Modify: `frontend/src/pages/chat/components/MessageCard.tsx`
- Modify: `frontend/src/pages/chat/components/ChatSidebar.tsx`
- Modify: `frontend/src/pages/chat/components/SessionList.tsx`
- Modify: `frontend/src/pages/chat/hooks/useSessionActions.ts`
- Modify: `frontend/src/lib/session-api.ts`
- Modify: `frontend/src/pages/LoginPage.tsx`
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/i18n/locales/zh.json`

**Interfaces:**
- Consumes: Task 2 profile client and Task 3 standard stream lifecycle.
- Produces: one compact Profile selector next to existing retrieval controls; standard streams, strict-quality and advanced use loading/final/error states; quality/citation metadata is shown when supplied.

- [ ] Add or extend tests that prove selecting each profile dispatches the correct profile, null message IDs do not crash, and no rename request exists.
- [ ] Run focused tests and confirm failures.
- [ ] Add Profile state with `standard` default and three clear localized labels/descriptions. Reuse `SelectControl`; do not redesign the page.
- [ ] For strict-quality and advanced, render a local final assistant message from their JSON response, including citations and optional quality metadata. Do not claim progressive SSE for endpoints that are not streaming.
- [ ] Remove the unsupported session rename control, action, and client method because the OpenAPI has no `PATCH /sessions/{session_id}` route.
- [ ] Guard editing/deleting when `message_id` is null. Replace `ChatSidebar`'s `user: any` with `UserIdentity | null`.
- [ ] Change Google login navigation from `/api/auth/google/login` to `/auth/google/login`.
- [ ] Re-run focused and complete frontend tests and production build.

**Acceptance:** Users can select and submit every real Profile, unsupported rename is not exposed, Google OAuth uses the real path, and optional backend fields cannot crash the chat.

### Task 5: Verification and handoff evidence

**Files:**
- Do not modify production files unless a failed verification proves a regression caused by Tasks 1-4.

- [ ] Run `npm.cmd ls --depth=0`.
- [ ] Run focused new tests, then `npm.cmd test -- --run`.
- [ ] Run `npm.cmd run build`.
- [ ] Note that no frontend lint script exists in `frontend/package.json`; do not invent one.
- [ ] Run `conda run -n rag-local pytest tests/api/test_query_stream_ownership.py tests/api/test_orchestration_stream.py -q`.
- [ ] Run applicable static checks on modified files and inspect `git diff -- frontend` plus `git status --short`.
- [ ] Report pre-existing test failures separately from regressions. Do not describe blocked live model/database scenarios as passing.

**Acceptance:** New frontend contract tests pass, production build exits zero, relevant backend SSE tests pass, and the implementation report lists exact commands, counts, failures, and touched files.
