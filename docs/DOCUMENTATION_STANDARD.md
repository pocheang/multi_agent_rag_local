# Documentation Standard

**Policy Status**: Published  
**Version**: 2.0  
**Last Updated**: 2026-04-27  
**Applies To**: All repository documentation in the project root and `docs/`

This standard defines how project documentation is written, reviewed, published, and maintained for enterprise delivery scenarios. The goal is to keep documentation accurate, auditable, and useful across engineering, operations, product, and security stakeholders.

## 1. Principles

- Documentation must reflect the current repository behavior, not aspiration.
- Every active document must have a clear owner and update trigger.
- Core documents should optimize for handoff, onboarding, and operational clarity.
- Historical documents should preserve context without being mistaken for current policy.
- Security, deployment, and access-control claims must be traceable to code or configuration.

## 2. Document Classes

| Class | Purpose | Editing Rule |
| --- | --- | --- |
| Active | Current source of truth for engineering or operations | Update when relevant code or process changes |
| Reference | Stable supporting guidance | Review on dependency or process change |
| Historical | Snapshot of a milestone, release, or incident | Keep content stable after publication |
| Archived | Retained for compliance or traceability | Do not materially change except metadata |

## 3. Required Metadata

Every active or reference document must begin with a metadata block similar to the following:

```md
# Document Title

**Document Status**: Published
**Version**: 1.0
**Last Updated**: YYYY-MM-DD
**Audience**: Engineering, Operations
**Owner**: Team or role
**Scope**: One-sentence scope statement
```

Historical documents may use lighter metadata, but they must include the publication date and milestone or release context.

## 4. Naming Conventions

| Type | Convention | Example |
| --- | --- | --- |
| Root entry document | `README.md` | `README.md` |
| Documentation index | `README.md` under folder | `docs/README.md` |
| Standards and policy | uppercase descriptive name | `DOCUMENTATION_STANDARD.md` |
| Guides | descriptive snake or uppercase title | `API_SETTINGS_GUIDE.md` |
| Checklists | descriptive lowercase title | `production_readiness_checklist.md` |
| Historical release docs | include version or date | `RELEASE_SUMMARY_v0.2.5.md` |
| Historical fix docs | include date | `FIXES_ROUND4_2026-04-27.md` |

## 5. Active Document Structure

Active documents should follow this structure whenever it fits the content:

1. Purpose or executive summary
2. Audience and scope
3. Current-state guidance
4. Roles, responsibilities, or workflow
5. Validation or acceptance criteria
6. Links to related documents

Avoid long diary-style narratives in active documents.

## 6. Language And Style

- Write in direct, operational language.
- Prefer precise claims over promotional language.
- Use tables where comparison or ownership matters.
- Use numbered steps for procedures.
- Avoid screenshots unless they materially improve execution.
- Avoid undocumented version claims that conflict with repository metadata.
- If a statement is inferred rather than directly validated, label it clearly.

## 7. Source Of Truth Rules

When multiple documents touch the same topic:

- `README.md` is the top-level business and technical overview.
- `docs/README.md` is the navigation layer for documentation consumers.
- Checklists define release or operational gates.
- Historical reports provide evidence, not current operating policy.
- Code and configuration are authoritative when documentation is stale.

## 8. Review Requirements

### Mandatory Review Triggers

- New API endpoint or route change
- Auth, session, or RBAC behavior change
- New environment variable or secret requirement
- New retrieval or orchestration behavior
- Changes to deployment, monitoring, or rollback flow
- Major refactoring that changes file ownership or module boundaries

### Minimum Review Cadence

| Document Type | Cadence |
| --- | --- |
| Root overview and docs hub | Monthly |
| Production and security guidance | Before every release |
| Architecture and workflow guidance | On material code change |
| Historical reports | No scheduled review after publication |

## 9. Quality Gate For Documentation

An active document is ready for publication only if:

- The title and purpose are clear
- Metadata is present
- Links resolve correctly
- Commands and paths match the repository
- Ownership is identifiable
- Security-sensitive instructions do not expose secrets
- Version or release statements do not contradict known repository facts

## 10. Historical Content Handling

Historical files should not be rewritten into current-state docs. Instead:

1. Preserve the original context
2. Add a short note if the document is superseded
3. Point readers to the active replacement document
4. Avoid deleting milestone evidence unless explicitly requested

## 11. Recommended Minimal Enterprise Set

Every maintained branch intended for internal or external delivery should keep these documents current:

- `README.md`
- `docs/README.md`
- `docs/production_readiness_checklist.md`
- `docs/DOCUMENTATION_STANDARD.md`
- `docs/DOCUMENTATION_MAINTENANCE.md`
- `CHANGELOG.md`

## 12. Definition Of Done

A documentation update is complete when:

1. The affected active document is updated.
2. Any entry-point index is updated if navigation changed.
3. Version-sensitive language is consistent.
4. Related operational or security notes are reviewed.
5. The change can be understood by someone outside the original implementation context.
