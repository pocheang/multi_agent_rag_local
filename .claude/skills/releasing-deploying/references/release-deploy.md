# Release and Deployment Gates

Release evidence: version, commit, artifact digest, validation, approvals, notes, compatibility, configuration/migrations, security fixes, known issues, dependencies, provenance/SBOM, deployment prerequisites, rollback.

Keep `VERSION`, `pyproject.toml`, and `frontend/package.json` synchronized when version changes.

Deployment preflight: target/artifact, approver, capacity, dependencies, config/secrets, backups, migration order, compatibility, health/readiness/smoke/RAG/security/business signals, observation window, rollback thresholds.

Roll out in stages and record timestamps, traffic/exposure, metrics, deviations, incidents, final state, and operational handoff. Never improvise thresholds after failure begins.
