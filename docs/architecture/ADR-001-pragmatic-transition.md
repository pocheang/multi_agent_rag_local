# Architecture Decision Record: Pragmatic Transition Strategy

**Date**: 2026-08-19  
**Status**: ACCEPTED  
**Decision**: Adopt pragmatic transition strategy instead of big-bang rewrite

## Context

The system evolved from a LangGraph multi-agent architecture to an adapter-based architecture. During review, we identified:

1. **Naming vs. Reality Gap**: Code claims "service-based" but uses adapter pattern
2. **Configuration Debt**: 67+ constants in `app/agents/shared/config.py`, many are tuning parameters
3. **Module Boundaries**: `app/services/` importing from `app/agents/shared/`
4. **Type System**: Core classes use `Any` despite "typed orchestration" claims
5. **Over-Engineering**: "5-layer defense", excessive validation layers

## Decision

We choose the **pragmatic route**: acknowledge reality, fix critical issues, simplify incrementally.

### What We're Doing

1. ✅ **Honest Documentation**: Updated CLAUDE.md to reflect actual architecture state
2. ✅ **Fix Module Boundaries**: Created `app/core/shared_config.py` for cross-layer config
3. ✅ **Mark Debt**: Added clear warnings to problematic files
4. 🎯 **Simplify Gradually**: Will reduce config constants by 50% over next iteration
5. 🎯 **Focus on Value**: Prioritize working features over perfect architecture

### What We're NOT Doing

- ❌ Big rewrite from adapter to "pure services"
- ❌ Rename `app/agents/` to `app/components/` (not worth the churn)
- ❌ Implement DAG-based orchestration engine (current sequential flow works)
- ❌ Remove all legacy code immediately

## Rationale

**Why pragmatic over perfect?**

1. **System Works**: Users are getting value, retrieval quality is good
2. **Cost/Benefit**: 2 weeks of rewrite vs. 2 days of pragmatic fixes
3. **Risk**: Big rewrites often introduce new bugs
4. **Team Velocity**: Can deliver features while improving architecture incrementally

**What did we learn?**

- "Marketed architecture" ≠ "actual architecture" causes confusion
- Configuration explosion is a smell of over-tuning
- Simple, honest code > complex, aspirational code

## Consequences

### Positive

- Team has clear mental model of what the system IS vs. what we want it to be
- New developers won't be confused by mismatch between docs and code
- Incremental improvements are safer and measurable

### Negative

- We're admitting technical debt exists (but hiding it was worse)
- Some "cool" architectural claims are removed from docs
- Will need to revisit and continue simplification

### Neutral

- `app/agents/` directory name stays (it's just a name)
- Adapter pattern stays (it's a valid pattern, not a crime)
- Configuration will improve gradually, not overnight

## Action Items

### Completed (2026-08-19)
- [x] Update CLAUDE.md to reflect reality
- [x] Create `app/core/shared_config.py`
- [x] Fix `context_tracker.py` import
- [x] Add deprecation notices

### Next Sprint (Priority Order)
1. Audit config constants, identify top 20 "must keep"
2. Delete or merge remaining constants
3. Document why each kept constant exists
4. Add integration tests for critical paths
5. Measure actual quality metrics (vs. aspirational ones)

### Future (Technical Debt Backlog)
- Replace `Any` types in `CoreCapabilities` with protocols
- Consider: Do we need `ExecutionPolicy` or just `if` statements?
- Evaluate: Is "5-layer defense" providing value or just complexity?

## References

- Git commits: Recent "remove compatibility wrappers" series
- Related: CLAUDE.md architecture section
- Discussion: 2026-08-19 critical review session

## Notes

This ADR itself is an example of pragmatism: we're documenting our decision to be pragmatic, not perfect. The meta-irony is not lost on us, but documentation debt is real and worth addressing.
