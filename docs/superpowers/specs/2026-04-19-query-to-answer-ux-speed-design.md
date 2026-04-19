# Query-to-Answer UX Speed Design (v0.2.4)

Date: 2026-04-19
Scope: Multi-Agent Local RAG first-phase UX redesign for the `question -> answer` path
Priority: User experience first, with latency as the primary KPI and quality as guardrails

## 1. Context and Problem

Current system (`v0.2.4`) already includes:
- LangGraph multi-agent routing and synthesis
- Hybrid retrieval (Vector + BM25 + Rerank)
- Optional web fallback and reasoning switches
- Runtime profiles (`fast / balanced / deep`)
- Streaming + non-stream fallback path

Observed product challenge:
- Users feel uncertainty about latency and behavior changes per query.
- Runtime decisions are distributed across modules, making speed behavior less predictable.
- UX messaging for "what is happening now" is not explicit enough for user trust.

## 2. Product Goal and Boundaries

Primary goal (Phase 1):
- Optimize the end-to-end `question -> answer` journey for speed perception and response predictability.

User-priority decisions (confirmed):
- Primary journey: Query to answer
- Priority metric: Faster experience
- Latency target level: Balanced
- Main scenario: Hybrid Q&A (local docs + general/web supplement)
- Default policy when speed and completeness conflict: Intelligent switching

Non-goals (Phase 1):
- Full UI rewrite
- New agent family introduction
- Cross-product workflow redesign outside chat main path

## 3. Target UX Outcomes

Latency targets:
- First token latency: P50 <= 2s, P95 <= 4s
- End-to-end answer latency: P50 <= 12s (balanced target)

Quality guardrails:
- Citation coverage must not regress vs current baseline
- Re-ask rate for same intent within 5 minutes must not increase
- Factual error rate must not increase

Perceived UX improvements:
- User sees current execution tier and expected timing range
- User receives immediate processing feedback before heavy retrieval starts
- Failure cases degrade clearly instead of stalling silently

## 4. Recommended Architecture (Approved Option B)

Adopt a system-level tiered execution policy:

1. Add `Query Tier Classifier` before retrieval execution.
2. Add `Latency Budget Manager` to convert tier into hard runtime budgets.
3. Make retrieval/synthesis modules consume the same tier+budget context.
4. Keep one chat entry point in frontend; show tier and expected latency hints.
5. Add admin observability panels for tier hit ratio, latency, quality and fallbacks.

Rationale:
- Preserves existing architecture and investments.
- Turns "intelligent switching" into explicit, testable policy.
- Maximizes practical UX gain with medium implementation risk.

## 5. Core Components and Responsibilities

### 5.1 TierClassifier (new)

Input:
- Question text
- Session context
- Intent/routing signal
- Evidence hints (doc hit likelihood)

Output:
- `tier`: `fast | balanced | deep`
- `tier_reason`: structured reason string(s) for observability

Placement:
- After intent/router inference, before retrieval execution.

### 5.2 BudgetPolicy / LatencyBudgetManager (new)

Input:
- Tier
- Current runtime load signal
- Request toggles (`use_web_fallback`, `use_reasoning`)

Output:
- Per-request budget contract (e.g., retrieval depth, rerank intensity, web timeout, token caps, retry caps)

Purpose:
- Enforce predictable latency with hard limits instead of soft heuristics.

### 5.3 RetrievalExecutor (enhanced)

Behavior by tier:
- `fast`: shallow retrieval, light rerank, web fallback mostly off
- `balanced`: moderate retrieval and rerank, conditional web fallback
- `deep`: richer retrieval and stronger synthesis depth

Reuse existing modules:
- `hybrid_retriever`, `reranker`, `adaptive_rag_policy`, `query_guard`

### 5.4 SynthesisProfile (enhanced)

Tier-aligned answer framing:
- `fast`: short conclusion-first response with essential evidence
- `balanced`: conclusion + key evidence + uncertainty note if needed
- `deep`: complete evidence/conflict narrative and fuller reasoning detail

### 5.5 UX Telemetry (new)

Frontend:
- Display current tier
- Display stage status and expected latency band

Backend metrics:
- first_token_ms, full_answer_ms
- tier distribution
- fallback trigger reasons
- citation coverage
- re-ask signal

## 6. End-to-End Request Flow

1. User sends query; UI immediately shows "classifying query complexity" status.
2. Backend computes `tier + budget` and returns early metadata.
3. Retrieval executes under budget contract.
4. If local evidence is insufficient and conditions match, web fallback runs with strict timeout.
5. Streaming output sends answer skeleton first, then evidence/citations.
6. If later evidence conflicts with earlier conclusion, explicit correction note is emitted.
7. Final metadata persists for analytics and tuning.

## 7. Failure Handling and Degradation

1. Tier classifier failure:
- Fallback to `balanced`
- Set `tier_fallback=classifier_error`

2. Retrieval timeout or empty result:
- Return concise "insufficient evidence" response
- Include practical next-step guidance

3. Web fallback timeout:
- Do not block main answer
- Return local-evidence answer and mark web supplementation incomplete

4. Streaming interruption:
- Auto-fallback to non-stream completion path
- Keep same session continuity and avoid duplicate answer artifacts

5. Consistency conflict:
- Output explicit correction note, not silent overwrite

## 8. Testing and Acceptance Criteria

### 8.1 KPI gates
- First token latency: P50 <= 2s, P95 <= 4s
- Full answer latency: P50 <= 12s (balanced)

### 8.2 Quality gates
- Citation coverage >= current baseline
- No regression in factual correctness checks
- Re-ask rate non-increasing

### 8.3 Routing validity
- Tier distribution is healthy (no single-tier collapse)
- Web fallback trigger-benefit relationship is observable and explainable

### 8.4 Stability gates
- Stream interruption recovery success rate reaches release threshold
- Timeout paths always return readable user-facing responses

### 8.5 Rollout strategy
- Internal gray release first
- Monitor latency/quality dashboards
- Progressive rollout after stable trend confirmation

## 9. Implementation Constraints and Compatibility

- Must be incremental over current `v0.2.4` architecture.
- Must preserve existing auth/rbac and admin governance boundaries.
- Must keep `/query` streaming behavior contract backward-compatible.
- Must keep current runtime profile mechanism usable by ops.

## 10. Risks and Mitigation

Risk 1: Over-optimization for speed reduces answer quality
- Mitigation: hard quality guardrails and release gates

Risk 2: Tier policy drift over time
- Mitigation: tier reason logging + periodic replay validation

Risk 3: User confusion when behavior differs by query
- Mitigation: clear tier/status cues in chat UI

## 11. Deliverables for Next Phase

- Tier classification policy and budget schema
- Backend integration points and instrumentation additions
- Frontend minimal status/tier UX updates
- Test matrix and acceptance dashboard definitions

This document is the approved design baseline for the next implementation-planning phase.
