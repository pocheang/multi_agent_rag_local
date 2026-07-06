# Dependencies and Contracts

For dependencies, record reason, old/new versions, transitive/runtime impact, license, advisories, platform support, lockfile/image digest, tests, SBOM/provenance, and rollback. Model/provider SDKs also require schema, streaming, retry/rate-limit, token, timeout, and fallback checks.

For consumer contracts, inventory consumers and classify changes as additive, behavioral, deprecating, or breaking. Prefer expand-and-contract: add compatible path, update/observe consumers, announce deprecation, remove after the approved window.

Keep FastAPI/Pydantic schemas, frontend types, clients, events, config, tool/prompt schemas, docs, and tests synchronized. Never silently repurpose a field or assume repository search finds every external consumer.
