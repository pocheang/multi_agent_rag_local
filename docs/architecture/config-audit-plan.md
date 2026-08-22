# Configuration Audit: 67 Constants Review

**Goal**: Reduce from 67 to ~20 essential constants  
**Timeline**: Next 2 sprints  
**Owner**: TBD

## Audit Status

- ✅ **Completed**: Shared config extracted to `app/core/shared_config.py`
- 🔄 **In Progress**: Categorizing remaining constants
- ⏳ **Next**: Deletion candidates identification

---

## Categories

### 🟢 KEEP (Essential Configuration)

**Core Retrieval** (~5 constants)
```python
MAX_CONTEXT_CHUNKS_DEFAULT = 10          # User-facing: controls response length
CHUNK_PREVIEW_LENGTH = 1200              # UX: visible in UI
MIN_CHUNK_LENGTH = 10                    # Data quality: filter noise
```

**Action**: Move to `app/retrievers/config.py` if not already there.

---

**Route Types & Skills** (~10 constants)
```python
ROUTE_VECTOR, ROUTE_GRAPH, ROUTE_HYBRID, ROUTE_REACT, ROUTE_WEB
VALID_ROUTES = frozenset({...})
SKILL_* constants
VALID_SKILLS = frozenset({...})
```

**Action**: These are enums, keep but consider using Python `Enum` class instead.

---

**Context Tracking** (✅ moved to `app/core/shared_config.py`)
```python
CONTEXT_MAX_HISTORY_TURNS = 10
CONTEXT_SUMMARY_FREQUENCY = 5
CONTEXT_SUMMARY_MIN_TURNS = 3
CONTEXT_TTL_SECONDS = 3600
```

**Status**: Already migrated. ✅

---

### 🟡 REVIEW (Needs Justification)

**Multiple Confidence Thresholds** (~6 constants)
```python
CLASSIFICATION_HIGH_CONFIDENCE = 0.8     # Used where?
CLASSIFICATION_MEDIUM_CONFIDENCE = 0.6   # Used where?
CLASSIFICATION_LOW_CONFIDENCE = 0.4      # Used where?
ROUTER_LOW_CONFIDENCE_THRESHOLD = 0.6    # Overlaps with above?
ROUTE_HIGH_CONFIDENCE_THRESHOLD = 0.85   # Different from above?
ROUTE_MEDIUM_CONFIDENCE_THRESHOLD = 0.60 # Different from above?
```

**Questions**:
- Do we need both CLASSIFICATION_* and ROUTE_* versions?
- Are these actively used or cargo-culted from old code?
- Could we use one threshold with runtime adjustment?

**Action**: Grep codebase for usage, consolidate or delete.

---

**Quality Weights** (~10 constants)
```python
RETRIEVAL_WEIGHT_COVERAGE = 0.30
RETRIEVAL_WEIGHT_RELEVANCE = 0.40
RETRIEVAL_WEIGHT_DIVERSITY = 0.15
RETRIEVAL_WEIGHT_COMPLETENESS = 0.15

ANSWER_WEIGHT_FACTUALITY = 0.40
ANSWER_WEIGHT_CITATION = 0.25
ANSWER_WEIGHT_QUALITY = 0.25
ANSWER_WEIGHT_SAFETY = 0.10

QUALITY_WEIGHT_ROUTE = 0.10
QUALITY_WEIGHT_RETRIEVAL = 0.30
QUALITY_WEIGHT_ANSWER_FACT = 0.45
QUALITY_WEIGHT_ANSWER_QUALITY = 0.10
QUALITY_WEIGHT_CITATION = 0.05
```

**Questions**:
- Are these actively tuned or set-once-and-forgotten?
- Do they sum to 1.0? Are they normalized anywhere?
- Could we compute weights adaptively based on query type?

**Action**: Check git history - if unchanged for 6+ months, they're candidates for deletion or algorithmic replacement.

---

**Cascade Timeouts** (6 constants)
```python
CASCADE_LEVEL1_TIMEOUT_MS = 10           # 10ms for rules check
CASCADE_LEVEL2_TIMEOUT_MS = 3000         # 3s for LLM
CASCADE_LEVEL3_TIMEOUT_MS = 75           # 75ms for NLI
CASCADE_LEVEL4_TIMEOUT_MS = 3000         # 3s for deep LLM
ROUTE_VALIDATOR_TIMEOUT_MS = 500
RETRIEVAL_QUALITY_TIMEOUT_MS = 200
```

**Questions**:
- Are these derived from actual P95 measurements or guesses?
- Do timeouts vary by model (Haiku vs GPT-4)?
- Could we use one base timeout + multipliers?

**Action**: Benchmark actual execution times, replace with dynamic timeouts.

---

### 🔴 DELETE CANDIDATES (Likely Unused or Redundant)

**Router Keyword Weights** (~3 constants)
```python
ROUTER_WEIGHT_KEYWORD = 0.3
ROUTER_WEIGHT_ENTITY_COUNT = 0.2
ROUTER_WEIGHT_QUESTION_TYPE = 0.5
```

**Rationale**: If router uses LLM intent detection, why keyword weights? Grep for usage.

---

**Entity Count Thresholds** (~2 constants)
```python
ENTITY_COUNT_HIGH = 3
ENTITY_COUNT_MEDIUM = 2
```

**Rationale**: Arbitrary thresholds, probably unused since router was upgraded.

---

**Score Thresholds Set to 0.0** (~2 constants)
```python
RERANK_SCORE_THRESHOLD = 0.0             # Why have this?
BM25_SCORE_THRESHOLD = 0.0               # Not filtering anything
```

**Rationale**: A threshold of 0.0 does nothing. Delete unless there's a plan to tune them.

---

**Retry Limits** (~3 constants)
```python
MAX_ROUTE_RETRIES = 1
MAX_ANSWER_RETRIES = 1
MAX_TOTAL_RETRIES = 2
```

**Questions**:
- Is retry logic even active? Check retry_policy.py
- Are these ever hit in production logs?
- Modern approach: exponential backoff + circuit breaker

**Action**: Check if retry logic is used. If not, delete. If yes, consolidate into retry policy config.

---

**Fallback Map** (~1 dict)
```python
FALLBACK_ROUTE_MAP = {
    "hybrid": "vector",
    "graph": "vector",
    "react": "vector"
}
```

**Questions**:
- Is this used? Grep for FALLBACK_ROUTE_MAP
- If graph fails, does system actually fallback to vector?

**Action**: Verify usage, delete if unused.

---

**Enable Flags** (~8 booleans)
```python
CASCADE_ENABLE_LEVEL1 = True
CASCADE_ENABLE_LEVEL2 = False            # Already disabled!
CASCADE_ENABLE_LEVEL3 = True
CASCADE_ENABLE_LEVEL4 = True
CASCADE_USE_FOR_VALIDATION = True
ENABLE_AUTO_FALLBACK = True
ENABLE_PERFORMANCE_LOGGING = True
ENABLE_VERBOSE_LOGGING = False
```

**Rationale**: If level 2 is disabled by default, why have the constant? Feature flags belong in profiles, not constants.

---

## Next Steps

### Week 1: Investigation
```bash
# Find unused constants
rg "CLASSIFICATION_HIGH_CONFIDENCE" app/
rg "ROUTER_WEIGHT_KEYWORD" app/
rg "FALLBACK_ROUTE_MAP" app/
# etc. for all REVIEW and DELETE candidates
```

### Week 2: Deletion Sprint
1. Create `app/agents/shared/config_minimal.py` with ~20 essential constants
2. Update imports gradually
3. Delete `app/agents/shared/config.py` (422 lines → ~150 lines)
4. Run full test suite

### Week 3: Measurement
- Measure actual quality metrics without the deleted constants
- Compare to baseline (should be same or better)
- Document what we learned

---

## Success Metrics

- [ ] Config file reduced from 422 lines to <200 lines
- [ ] Number of constants reduced from 67 to <25
- [ ] All tests still pass
- [ ] Quality metrics unchanged (±2%)
- [ ] New developer can understand config in <10 minutes

---

## Anti-Goals

- ❌ Delete constants just to hit a number target
- ❌ Break working functionality for "cleanliness"
- ❌ Add new constants during cleanup phase

---

## References

- Original: `app/agents/shared/config.py` (422 lines, 67 constants)
- Extracted: `app/core/shared_config.py` (cross-layer shared config)
- ADR: `docs/architecture/ADR-001-pragmatic-transition.md`
