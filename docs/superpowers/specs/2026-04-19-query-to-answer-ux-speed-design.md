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
- Citation coverage must not regress vs current baseline (≥85% of answers must include at least one citation)
- Re-ask rate: <15% of queries result in follow-up clarification within 5 minutes (measured via session continuity and query similarity >0.7 using embedding distance)
- Factual error rate: <2% based on automated fact-checking against source documents and manual spot-checks (sample 100 queries per week)

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
- Current system load signal

Output:
- `tier`: `fast | balanced | deep`
- `tier_reason`: structured reason string(s) for observability
- `tier_confidence`: float [0.0-1.0] for monitoring misclassification

Classification Logic:
- **Fast tier triggers**: Simple factual queries, single-entity lookup, high doc hit likelihood (>0.8), query length <50 tokens
- **Deep tier triggers**: Multi-hop reasoning required, low doc hit likelihood (<0.3), explicit user request for comprehensive answer, query contains "explain in detail/compare/analyze"
- **Balanced tier**: Default fallback for all other cases

Security:
- Rate limit tier classification to prevent DoS via repeated deep tier triggers (max 3 deep queries per user per minute)
- Input sanitization before classification to prevent prompt injection
- Tier override requires explicit user action (not automatic escalation)

Placement:
- After intent/router inference, before retrieval execution.

### 5.2 BudgetPolicy / LatencyBudgetManager (new)

Input:
- Tier
- Current runtime load signal
- Request toggles (`use_web_fallback`, `use_reasoning`)

Output:
- Per-request budget contract with concrete limits:

**Fast Tier Budget:**
- `retrieval_top_k`: 5
- `rerank_top_k`: 3
- `max_retrieval_time_ms`: 800
- `max_synthesis_tokens`: 300
- `web_fallback_enabled`: false
- `max_retry_attempts`: 1

**Balanced Tier Budget:**
- `retrieval_top_k`: 10
- `rerank_top_k`: 5
- `max_retrieval_time_ms`: 2000
- `max_synthesis_tokens`: 800
- `web_fallback_enabled`: true (conditional)
- `web_fallback_timeout_ms`: 3000
- `max_retry_attempts`: 2

**Deep Tier Budget:**
- `retrieval_top_k`: 20
- `rerank_top_k`: 10
- `max_retrieval_time_ms`: 5000
- `max_synthesis_tokens`: 1500
- `web_fallback_enabled`: true
- `web_fallback_timeout_ms`: 8000
- `max_retry_attempts`: 3

Load-based Degradation:
- When system load >80%, automatically downgrade tier by one level
- When load >95%, force all queries to fast tier

Purpose:
- Enforce predictable latency with hard limits instead of soft heuristics.

### 5.3 RetrievalExecutor (enhanced)

Behavior by tier:
- `fast`: shallow retrieval, light rerank, web fallback disabled
- `balanced`: moderate retrieval and rerank, conditional web fallback (only when local evidence score <0.5)
- `deep`: richer retrieval and stronger synthesis depth, web fallback enabled

Web Fallback Trigger Logic (balanced/deep tiers):
- Local evidence confidence score <0.5
- Query contains temporal keywords ("latest", "recent", "current", "2026")
- Explicit user request for web search
- Document corpus last updated >30 days ago for time-sensitive queries

Reuse existing modules:
- `hybrid_retriever`, `reranker`, `adaptive_rag_policy`, `query_guard`

### 5.4 SynthesisProfile (enhanced)

Tier-aligned answer framing:
- `fast`: short conclusion-first response with essential evidence
- `balanced`: conclusion + key evidence + uncertainty note if needed
- `deep`: complete evidence/conflict narrative and fuller reasoning detail

### 5.5 UX Telemetry (new)

Frontend:
- Display current tier with visual indicator (fast=green, balanced=blue, deep=purple)
- Display stage status and expected latency band (e.g., "Retrieving documents: 1-3s expected")
- Allow user manual tier override via settings (persisted per session)
- Show tier confidence score when <0.7 to indicate uncertainty

Backend metrics:
- first_token_ms, full_answer_ms (P50, P95, P99)
- tier distribution (fast/balanced/deep percentages)
- tier_misclassification_rate (user manual overrides / total queries)
- tier_confidence_distribution
- fallback trigger reasons and frequency
- citation coverage per tier
- re-ask signal (query similarity >0.7 within 5min window)
- budget_exceeded_count per tier and component
- load_based_degradation_count

## 6. End-to-End Request Flow

1. User sends query; UI immediately shows "classifying query complexity" status with tier icon placeholder.
2. Backend computes `tier + budget` and returns early metadata via response headers (`X-Query-Tier`, `X-Tier-Confidence`).
3. UI updates to show confirmed tier (fast=green, balanced=blue, deep=purple) and expected latency range.
4. Retrieval executes under budget contract with timeout enforcement.
5. If local evidence confidence <0.5 and tier allows, web fallback runs with strict timeout (non-blocking).
6. Streaming output sends answer skeleton first, then evidence/citations progressively.
7. If later evidence conflicts with earlier conclusion, explicit correction note is emitted with conflict explanation.
8. Final metadata (tier, confidence, actual latency, citation count, fallback status) persists for analytics and A/B testing.
9. If user manually overrides tier during session, preference is saved and applied to subsequent queries in same session.

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
- Must keep `/query` streaming behavior contract backward-compatible:
  - Response format remains unchanged for clients not requesting tier metadata
  - New tier metadata added as optional fields in response headers: `X-Query-Tier`, `X-Tier-Confidence`
  - Existing clients ignore new headers; new clients can opt-in to tier awareness
- Must keep current runtime profile mechanism usable by ops:
  - New tier system operates independently from existing `fast/balanced/deep` profiles
  - Profiles control retrieval strategy; tiers control latency budgets
  - When both are specified, tier budget takes precedence for timeout/token limits
  - Migration path: profiles will be deprecated in v0.3.0 after tier system stabilizes

## 10. Risks and Mitigation

Risk 1: Over-optimization for speed reduces answer quality
- Mitigation: Hard quality guardrails (citation ≥85%, factual error <2%) and release gates
- Mitigation: A/B testing framework to compare tier performance against baseline
- Mitigation: Weekly quality spot-checks (100 samples) with human review

Risk 2: Tier policy drift over time
- Mitigation: Tier reason logging + periodic replay validation
- Mitigation: Monthly tier classification audit using held-out test set
- Mitigation: Alert when tier distribution shifts >15% week-over-week

Risk 3: User confusion when behavior differs by query
- Mitigation: Clear tier/status cues in chat UI with visual indicators
- Mitigation: User education tooltip on first tier display
- Mitigation: Allow manual tier override with preference persistence

Risk 4: Tier classifier exploitation (DoS via deep tier abuse)
- Mitigation: Rate limiting (max 3 deep queries per user per minute)
- Mitigation: Load-based automatic tier degradation (>80% load → downgrade one level)
- Mitigation: Admin dashboard to monitor tier abuse patterns

Risk 5: Budget timeout causing incomplete answers
- Mitigation: Graceful degradation with partial results + "incomplete" flag
- Mitigation: Suggest tier upgrade when timeout occurs repeatedly
- Mitigation: Log timeout patterns for budget tuning

Risk 6: Backward compatibility break for existing API clients
- Mitigation: Tier metadata in optional response headers only
- Mitigation: Existing clients ignore new headers without breaking
- Mitigation: Versioned API endpoint (/v2/query) for tier-aware clients if needed

## 11. Deliverables for Next Phase

- Tier classification policy and budget schema
- Backend integration points and instrumentation additions
- Frontend minimal status/tier UX updates
- Test matrix and acceptance dashboard definitions

This document is the approved design baseline for the next implementation-planning phase.
