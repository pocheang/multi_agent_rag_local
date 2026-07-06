# Threat Model and Test Strategy

For security-sensitive work, map assets, actors, entry points, data/control flows, trust boundaries, and abuse cases. Consider spoofing, tampering, repudiation, disclosure, denial of service, privilege escalation, supply chain, prompt injection, data poisoning, and tenant leakage. Map preventive, detective, and recovery controls to owners and tests.

For testing, map each requirement/risk to the cheapest reliable layer:

- unit: deterministic domain behavior;
- component/contract: module and consumer/provider boundaries;
- integration: real dependency interaction;
- E2E: critical user journeys;
- specialized: security, migration, resilience, performance, and RAG evaluation.

Define fixtures, tenant isolation, positive/negative/boundary/timeout/concurrency/recovery cases, environment, thresholds, artifacts, and cadence. Critical unmitigated threats block release unless explicitly accepted.
