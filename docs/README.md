# Documentation Hub

**Document Status**: Published  
**Last Updated**: 2026-04-28  
**Audience**: Engineering, Operations, Security, Product, Delivery  
**Scope**: Multi-Agent Local RAG repository documentation  
**Structure**: Enterprise-grade documentation organization

This directory is the enterprise documentation entry point for the project. It organizes documents by type and lifecycle stage, ensuring teams can find the current source of truth quickly.

## 📁 Documentation Structure

```
docs/
├── README.md                              # This file - documentation hub
├── ENTERPRISE_DOCUMENTATION_STANDARD.md   # Enterprise doc standards
├── DOCUMENTATION_STANDARD.md              # Documentation policy
├── DOCUMENTATION_MAINTENANCE.md           # Maintenance workflow
├── VERSION_HISTORY.md                     # Version timeline
├── API_SETTINGS_GUIDE.md                  # Configuration reference
├── PERFORMANCE_OPTIMIZATION.md            # Tuning guidance
├── runtime_speed_profiles.md              # Latency tier reference
├── ARCHIVE_REFERENCE.md                   # Historical docs index
│
├── archive/                               # Historical & audit records
│   ├── REFACTORING_*.md                   # Refactoring reports
│   ├── RELEASE_*.md                       # Release notes
│   ├── FIXES_*.md                         # Fix logs
│   ├── LOGIC_FIXES_*.md                   # Logic fix reports
│   ├── V0.3.0_*.md                        # Version-specific reports
│   └── ...                                # Other historical docs
│
├── project/                               # Project-specific guidance
│   ├── production_readiness_checklist.md  # Pre-deployment validation
│   └── ...                                # Other project docs
│
├── design/                                # Design specifications
│   ├── superpowers/specs/                 # Feature design specs
│   └── ...                                # Other design docs
│
├── operations/                            # Operational guidance
│   └── ...                                # Deployment, monitoring, etc.
│
└── development/                           # Development guidance
    └── ...                                # Dev setup, testing, etc.
```

## 🚀 Quick Navigation

### If you are new to the project

1. Read [../README.md](../README.md) - Product overview
2. Read [project/production_readiness_checklist.md](project/production_readiness_checklist.md) - Deployment checklist
3. Read [DOCUMENTATION_STANDARD.md](DOCUMENTATION_STANDARD.md) - Documentation standards

### If you are deploying or operating the system

- [project/production_readiness_checklist.md](project/production_readiness_checklist.md) - Pre-deployment validation
- [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md) - Performance tuning
- [runtime_speed_profiles.md](runtime_speed_profiles.md) - Latency profiles
- [API_SETTINGS_GUIDE.md](API_SETTINGS_GUIDE.md) - Configuration reference

### If you are developing features

- [../CLAUDE.md](../CLAUDE.md) - Development context
- [DOCUMENTATION_STANDARD.md](DOCUMENTATION_STANDARD.md) - Documentation policy
- [DOCUMENTATION_MAINTENANCE.md](DOCUMENTATION_MAINTENANCE.md) - Maintenance workflow
- [VERSION_HISTORY.md](VERSION_HISTORY.md) - Version timeline

### If you are managing releases

- [VERSION_DOCUMENTATION_STANDARD.md](VERSION_DOCUMENTATION_STANDARD.md) - Version documentation requirements
- [VERSION_DOCUMENTATION_GUIDE.md](VERSION_DOCUMENTATION_GUIDE.md) - Release documentation workflow
- [VERSION_DOCUMENTATION_CHECKLIST.md](VERSION_DOCUMENTATION_CHECKLIST.md) - Pre-release validation checklist
- [VERSION_HISTORY.md](VERSION_HISTORY.md) - Complete version history
- [../CHANGELOG.md](../CHANGELOG.md) - Authoritative change log

## Active Core Documents

| Document | Purpose | Primary Audience |
| --- | --- | --- |
| [../README.md](../README.md) | Product and technical overview | All teams |
| [project/production_readiness_checklist.md](project/production_readiness_checklist.md) | Production launch and go-live validation | Operations, SRE, Engineering |
| [ENTERPRISE_DOCUMENTATION_STANDARD.md](ENTERPRISE_DOCUMENTATION_STANDARD.md) | Enterprise documentation organization standard | Engineering, PM, Tech Writing |
| [DOCUMENTATION_STANDARD.md](DOCUMENTATION_STANDARD.md) | Documentation policy, format, and lifecycle | Engineering, PM, Tech Writing |
| [DOCUMENTATION_MAINTENANCE.md](DOCUMENTATION_MAINTENANCE.md) | Maintenance workflow and ownership model | Maintainers |
| [VERSION_HISTORY.md](VERSION_HISTORY.md) | Historical version timeline | Delivery, PM, Engineering |
| [VERSION_DOCUMENTATION_STANDARD.md](VERSION_DOCUMENTATION_STANDARD.md) | Version documentation requirements and standards | Release Managers, Engineering |
| [VERSION_DOCUMENTATION_GUIDE.md](VERSION_DOCUMENTATION_GUIDE.md) | Version release documentation workflow | Release Managers, Engineering |
| [VERSION_DOCUMENTATION_CHECKLIST.md](VERSION_DOCUMENTATION_CHECKLIST.md) | Pre-release documentation validation checklist | Release Managers, QA |
| [API_SETTINGS_GUIDE.md](API_SETTINGS_GUIDE.md) | Runtime API/model configuration | Admins, Operators |
| [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md) | Runtime tuning guidance | Engineering, Operations |
| [runtime_speed_profiles.md](runtime_speed_profiles.md) | Speed and latency profile reference | Engineering |
| [ARCHIVE_REFERENCE.md](ARCHIVE_REFERENCE.md) | Historical and archived document inventory | All teams |

## Historical And Audit Records

Historical documents are organized in the `archive/` directory. They remain valuable for traceability, audit, and milestone review, but they are not the primary operational documentation set.

**Archive Contents**:
- Release notes and release confirmation documents
- Refactoring completion reports
- Point-in-time fix reports
- Deep review snapshots
- One-off investigation summaries

When a historical document conflicts with a core active document, prefer the active document unless the historical artifact is being used for audit reconstruction.

**Note**: The root-level `CHANGELOG.md` is the authoritative version history. Historical milestone reports in `archive/` are preserved for reference but should not replace the main changelog.

See [ARCHIVE_REFERENCE.md](ARCHIVE_REFERENCE.md) for a complete inventory of archived documents.

## Document Classes

| Class | Description | Update Rule |
| --- | --- | --- |
| Active | Current source of truth used for delivery and operations | Must be reviewed when code or process changes |
| Reference | Stable supporting guidance | Review quarterly or on dependency change |
| Historical | Snapshot of a release, fix, or investigation | Do not rewrite materially after publication |
| Archived | Deprecated content preserved for record keeping | Keep read-only except metadata |

## Ownership Model

| Area | Owner |
| --- | --- |
| Product and repository overview | Engineering lead |
| Deployment and readiness | Platform or operations owner |
| Security-sensitive configuration | Backend lead or security owner |
| Documentation standards and workflow | Repository maintainers |
| Historical milestone reports | Original delivery owner |

## Review Triggers

Update the relevant documents when any of the following change:

- API routes or authentication behavior
- Query orchestration or retrieval strategy
- Environment variables or secret handling
- Build, deployment, or release process
- Frontend entry flow or admin capabilities
- Observability, resilience, or data retention policies

## Recommended Enterprise Baseline

For customer delivery, internal platform adoption, or handover to another team, make sure at minimum the following documents are current:

1. `README.md` (root)
2. `docs/README.md` (this file)
3. `docs/project/production_readiness_checklist.md`
4. `docs/ENTERPRISE_DOCUMENTATION_STANDARD.md`
5. `docs/DOCUMENTATION_STANDARD.md`
6. `docs/DOCUMENTATION_MAINTENANCE.md`
7. `CHANGELOG.md` (root)
8. `CLAUDE.md` (root)

## Notes On Document Organization

This repository now follows an enterprise-grade documentation structure:

- **Active Core Documents**: Located in `docs/` root - kept current and synchronized with code
- **Historical Records**: Located in `docs/archive/` - preserved for audit and traceability
- **Project Documentation**: Located in `docs/project/` - project-specific guidance
- **Design Specifications**: Located in `docs/design/` - feature and technical designs
- **Operations Guides**: Located in `docs/operations/` - deployment and operational guidance
- **Development Guides**: Located in `docs/development/` - development workflow and setup

For detailed information on the documentation organization standard, see [ENTERPRISE_DOCUMENTATION_STANDARD.md](ENTERPRISE_DOCUMENTATION_STANDARD.md).
