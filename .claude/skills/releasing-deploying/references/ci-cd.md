# CI/CD

Define trusted triggers, protected branches/tags, environments, owners, and approvals. Separate validate, build, release, and deploy.

Run fast deterministic checks first; parallelize independent work and retain artifacts. Build once from an approved revision. Record digest, SBOM/dependencies, provenance/signing when supported. Promote the same artifact with environment-scoped config/secrets.

Use short-lived credentials, least privilege, pinned actions/images, isolated untrusted contributions, concurrency/cancellation, timeouts, bounded retries, cache integrity, and cleanup.

This repository currently has no committed `.github/workflows`; do not claim enforcement until workflows and platform rules are verified.
