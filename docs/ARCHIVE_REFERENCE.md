# Documentation Archive Reference

**Last Updated**: 2026-04-27  
**Version**: v0.3.1  
**Purpose**: Clarify which documents are active vs. historical/archived

## Active Core Documents

These documents are the current source of truth and should be kept up-to-date:

| Document | Purpose | Update Frequency |
|----------|---------|------------------|
| [../README.md](../README.md) | Product overview, quick start, API surface | On major changes |
| [README.md](README.md) | Documentation hub and navigation | Quarterly or on structure change |
| [ENTERPRISE_DOCUMENTATION_STANDARD.md](ENTERPRISE_DOCUMENTATION_STANDARD.md) | Enterprise documentation organization standard | On process changes |
| [project/production_readiness_checklist.md](project/production_readiness_checklist.md) | Pre-deployment validation | Before each release |
| [DOCUMENTATION_STANDARD.md](DOCUMENTATION_STANDARD.md) | Documentation policy and format | As needed |
| [DOCUMENTATION_MAINTENANCE.md](DOCUMENTATION_MAINTENANCE.md) | Maintenance workflow | As needed |
| [VERSION_HISTORY.md](VERSION_HISTORY.md) | Version timeline and release notes | On each release |
| [API_SETTINGS_GUIDE.md](API_SETTINGS_GUIDE.md) | Runtime configuration reference | On config changes |
| [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md) | Tuning and optimization guidance | Quarterly |
| [runtime_speed_profiles.md](runtime_speed_profiles.md) | Latency tier reference | On tier changes |
| [../CLAUDE.md](../CLAUDE.md) | Development context and architecture | On major refactors |
| [../CHANGELOG.md](../CHANGELOG.md) | Authoritative version history | On each release |

## Historical/Archived Documents

These documents are preserved for audit, traceability, and historical reference. **Do not treat them as current operational guidance** unless explicitly cross-referenced from an active document.

All files listed below are now stored under `docs/archive/`.

### Summary Documents (Consolidated)
- `FIXES_SUMMARY.md` - Consolidated fixes summary
- `REFACTORING_SUMMARY.md` - Consolidated refactoring reports
- `RELEASE_v0.2.5_SUMMARY.md` - Consolidated v0.2.5 release documents
- `V0.3.0_SUMMARY.md` - Consolidated v0.3.0 status reports
- `V0.3.0_RELEASE_NOTES.md` - Complete v0.3.0 release notes

### Other Historical Documents
- `2026-04-26-documentation-update-summary.md` - Documentation update summary
- `CHANGELOG_2026-04-27.md` - Historical changelog snapshot
- `DOCUMENTATION_COMPLETENESS_REPORT.md` - Documentation audit report
- `README_CN.md` - Chinese version of README (archived)

## How to Use This Archive

1. **For current operational guidance**: Use only the "Active Core Documents" list above
2. **For historical context**: Reference archived documents with the understanding they represent point-in-time snapshots
3. **For audit/traceability**: Archived documents provide evidence of decisions and changes made
4. **When conflicts arise**: Active documents take precedence over archived ones

## Maintenance Notes

- Historical documents are preserved as-is for audit purposes
- No updates are made to archived documents unless correcting factual errors
- New documents should be added to the "Active Core Documents" list if they represent ongoing operational guidance
- Quarterly review recommended to identify documents that should be archived or consolidated

---

**Maintained by**: Bronit Team  
**Last Review**: 2026-04-27
