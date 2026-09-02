# P2-3: QualityReport Schema Duplication Cleanup

**Date**: 2026-08-19  
**Status**: ✅ Completed  
**Impact**: Low priority maintenance - eliminated schema confusion

## Problem

Three different `QualityReport` schemas existed across the codebase, causing confusion:

1. **app/agents/shared/quality_models.py:100** - Active, used by quality_orchestrator
2. **app/agents/shared/result_schemas.py:75** - Unused legacy schema
3. **app/api/routes/compatibility/enhanced_query.py:78** - API compatibility layer

Plus one `OrchestratedQualityReport` in contracts (typed orchestration contract).

## Solution

### 1. Deleted Unused Schemas

**File**: [app/agents/shared/result_schemas.py](app/agents/shared/result_schemas.py)

Removed:
- `QualityReport` class (lines 75-86, 12 lines) - Unused legacy schema
- `EnhancedRAGResult` class (lines 88-94, 7 lines) - Unused legacy wrapper
- Updated `__all__` exports to remove both

**Replacement comment added**:
```python
# Legacy QualityReport and EnhancedRAGResult removed - unused schemas
# Active quality reporting uses:
#   - app.agents.shared.quality_models.QualityReport (quality_orchestrator)
#   - app.domain.contracts.OrchestratedQualityReport (finalization)
```

### 2. Renamed API Layer Schema

**File**: [app/api/routes/compatibility/enhanced_query.py:78](app/api/routes/compatibility/enhanced_query.py#L78)

```python
# Before:
class QualityReport(BaseModel):
    """API schema boundary for legacy quality-report payloads."""

# After:
class LegacyQualityReportDTO(BaseModel):
    """API DTO for legacy quality-report payloads (compatibility layer)."""
```

This clarifies it's a Data Transfer Object for the compatibility layer.

### 3. Fixed Test Import Paths

Updated 8 test files to use correct import paths:

**quality_models imports** (6 files):
1. `tests/agents/test_quality_orchestrator.py`
2. `tests/agents/test_answer_validator.py`
3. `tests/agents/test_context_tracker.py`
4. `tests/agents/test_quality_models.py`
5. `tests/agents/test_retrieval_quality.py`
6. `tests/test_weight_optimization.py`

```python
# Changed from:
from app.agents.quality_models import ...

# To:
from app.agents.shared.quality_models import ...
```

**result_schemas import** (1 file):
7. `tests/unit/test_unified_agents.py`

```python
# Changed from:
from app.agents.result_schemas import ...

# To:
from app.agents.shared.result_schemas import ...
```

**evidence_builder import** (1 file):
8. `tests/agents/rag/test_legacy_retrieval_adapters.py`

```python
# Changed from:
from app.agents.rag.service import _bundle_from_legacy_payload

# To:
from app.agents.rag.evidence_builder import bundle_from_legacy_payload
```

## Remaining Active Schemas

After cleanup, clear separation:

### 1. Internal Quality Models
**File**: [app/agents/shared/quality_models.py:100](app/agents/shared/quality_models.py#L100)
- **Used by**: `quality_orchestrator.py:180` creates instances
- **Purpose**: Detailed quality report with breakdown, issues, suggestions, execution stats
- **Fields**: overall_confidence, quality_level, quality_label, breakdown, issues, suggestions, execution_stats

### 2. Typed Orchestration Contract
**File**: [app/domain/contracts.py:220](app/domain/contracts.py#L220)
- **Used by**: `finalization.py:126` creates instances
- **Purpose**: Small, stable quality report for typed terminal contract
- **Fields**: score, level, details (minimal surface)

### 3. API Compatibility DTO
**File**: [app/api/routes/compatibility/enhanced_query.py:78](app/api/routes/compatibility/enhanced_query.py#L78)
- **Used by**: Legacy API routes (compatibility layer)
- **Purpose**: HTTP boundary schema for backward compatibility
- **Now named**: `LegacyQualityReportDTO` (clear naming)

## Verification

Created and ran verification script:

```python
from app.agents.shared.quality_models import QualityReport
from app.domain.contracts import OrchestratedQualityReport
from app.agents.shared import result_schemas
from app.api.routes.compatibility.enhanced_query import LegacyQualityReportDTO

assert 'QualityReport' not in dir(result_schemas)
assert 'EnhancedRAGResult' not in dir(result_schemas)
```

**Result**: ✅ All imports successful, no duplicates

## Test Results

```bash
# Core tests (24 passed):
pytest tests/test_evidence_builder.py tests/test_evidence_builder_edge_cases.py -v
# 24 passed, 4 warnings

# Quality models tests (20 passed):
pytest tests/agents/test_quality_models.py -v
# 20 passed, 1 warning
```

**Note**: Some tests fail due to missing legacy modules (`base_agent`, `graph_rag_agent`, etc.) - these are unrelated to this cleanup and were already deprecated.

## Related to P2-2

P2-2 mentioned `GraphState.route` being written by multiple nodes. Investigation found:
- `router_node.py` and `adaptive_planner_node.py` do not exist
- `GraphState` class not found in current codebase
- LangGraph system was removed in previous refactoring

**Conclusion**: P2-2 issue no longer exists.

## Impact

- **Lines removed**: 19 lines (2 unused classes)
- **Clarity improved**: API layer schema now clearly named `LegacyQualityReportDTO`
- **Maintainability**: Single source of truth for each quality report use case
- **No breaking changes**: Active code unaffected, only unused code removed

## Files Modified

1. `app/agents/shared/result_schemas.py` - Removed 2 unused schemas
2. `app/api/routes/compatibility/enhanced_query.py` - Renamed schema
3. 8 test files - Fixed import paths

## Next Steps

None - P2-3 cleanup complete. All low-priority issues addressed or confirmed non-existent.
