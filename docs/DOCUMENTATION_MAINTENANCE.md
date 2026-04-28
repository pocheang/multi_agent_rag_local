# Documentation Maintenance Guide

**Document Status**: Published  
**Version**: 2.0  
**Last Updated**: 2026-04-27  
**Owner**: Repository maintainers  
**Scope**: Ongoing maintenance of active and historical documentation

This guide defines how the team keeps documentation aligned with the codebase over time. It focuses on ownership, update triggers, review workflow, and historical preservation.

## 1. Maintenance Objectives

- Keep active documents aligned with the current implementation
- Reduce drift between code, configuration, and written guidance
- Make handoff and onboarding reliable
- Preserve milestone records without mixing them into current operating guidance

## 2. Documentation Operating Model

### Active Layer

These documents are expected to stay current:

- `README.md`
- `docs/README.md`
- `docs/production_readiness_checklist.md`
- `docs/DOCUMENTATION_STANDARD.md`
- `docs/DOCUMENTATION_MAINTENANCE.md`
- `CHANGELOG.md`

### Historical Layer

These documents are retained for traceability:

- Release summaries
- Refactoring reports
- Fix round reports
- Deep reviews
- One-time investigation notes

Historical documents should remain readable and discoverable, but they should not be treated as the default source of truth.

## 3. Ownership Matrix

| Topic | Primary Owner | Backup Owner |
| --- | --- | --- |
| Repository overview and onboarding | Engineering lead | Maintainer |
| Production readiness and deployment validation | Operations owner | Backend lead |
| Security, auth, and admin controls | Backend lead | Security reviewer |
| Runtime configuration and model settings | Backend lead | Platform owner |
| Documentation policy and structure | Maintainer | Engineering lead |
| Historical release and fix reports | Original author | Maintainer |

## 4. Update Triggers

Update active documents when any of the following occur:

- API route changes
- Authentication, session, or RBAC changes
- Query orchestration changes
- Retrieval profile or ranking behavior changes
- New environment variables or secret requirements
- Build or deployment changes
- Monitoring, alerting, or readiness behavior changes
- New admin features or operational controls

## 5. Maintenance Workflow

1. Identify the affected document set.
2. Update the primary active document first.
3. Update navigation documents if the document landscape changed.
4. Check whether a historical document should receive a superseded note.
5. Validate links, commands, and key claims.
6. Publish the documentation update with the related code change whenever possible.

## 6. Review Checklist

Before considering a documentation update complete, confirm:

- Scope is clear
- Commands are executable for this repository
- Paths match current structure
- Environment variables match `.env.example` or code
- API descriptions match current routes
- Security guidance does not expose secrets
- Historical versus active status is obvious

## 7. Handling Version Drift

This repository contains historical artifacts from multiple milestones. When version identifiers differ across files:

1. Treat `README.md`, `docs/README.md`, and `CHANGELOG.md` as the first places to normalize.
2. Do not silently rewrite historical release evidence to look current.
3. Add clarifying language in active documents when mixed-version history exists.
4. If package metadata and release docs disagree, record the discrepancy and resolve it in the relevant code or release workflow.

## 8. Archiving Rules

Archive or de-emphasize a document when:

- A newer active document replaces its role
- The document describes a one-time event
- The feature or process is no longer active
- The document is useful for audit but not for daily operations

### Archive Practice

- Keep the file in place if links already depend on it
- Mark it as historical or superseded near the top when appropriate
- Point to the active replacement document

## 9. Release-Time Documentation Gate

Before a production release or internal handoff:

1. Review `README.md`
2. Review `docs/README.md`
3. Review `docs/production_readiness_checklist.md`
4. Review `CHANGELOG.md`
5. Verify that any new admin, security, or ingestion behavior is documented

## 10. Recommended Review Cadence

| Area | Cadence |
| --- | --- |
| Root overview and docs hub | Monthly |
| Readiness and operational guidance | Every release |
| Configuration and security guidance | Every release |
| Historical artifacts | As needed only |

## 11. Definition Of Maintained

A document is considered maintained when:

- It has an identifiable owner
- It has a valid last-updated date
- Its commands and paths still work
- Its role in the documentation hierarchy is clear
- It does not materially contradict the repository state
