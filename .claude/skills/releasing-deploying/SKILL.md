---
name: releasing-deploying
description: Use when creating CI/CD, producing a release, publishing an artifact, deploying to an environment, promoting traffic, or rolling back.
disable-model-invocation: true
---

# Releasing and Deploying

Promote one verified, immutable artifact with explicit authorization.

1. Identify source revision, artifact/digest, target, owner, approver, risk, window, and rollback target.
2. Require validation evidence, synchronized version/notes, dependency record, configuration and migration plan.
3. Use least-privileged CI/CD, protected environments, provenance/SBOM when supported, and no production secrets for untrusted code.
4. Roll out development to staging to canary/partial to full; observe predefined health, quality, security, and business signals.
5. Stop or roll back when a trigger fires; record approval, timestamps, observations, deviations, and handoff.

Read [ci-cd.md](references/ci-cd.md) for pipeline work. Read [release-deploy.md](references/release-deploy.md) for release/deployment gates.

Tagging, pushing, publishing, deploying, migrating, traffic changes, and rollback require explicit authorization.
