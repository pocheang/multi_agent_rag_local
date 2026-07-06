# Small, Extensible Modules

## Choose the change mode

### Bug fix

- Reproduce with a regression test first.
- Make the smallest local correction; do not mix unrelated cleanup.
- Preserve public behavior except the confirmed defect.
- Refactor only when the existing structure prevents a safe fix.

### Code generation

- Generate one vertical slice at a time, not a giant scaffold.
- Follow existing repository patterns before introducing a framework or base class.
- Separate transport/UI, application policy, domain logic, and infrastructure.
- Generate tests and public contracts with the implementation.

### Refactor

- Characterize behavior before moving code.
- Split in behavior-preserving steps with green tests after each step.
- Keep compatibility adapters during migration; remove them only after consumers move.
- Do not combine broad renaming, dependency upgrades, and behavior changes in one refactor.

## File and function size heuristics

Size is a review signal, not a correctness rule:

- Prefer production modules around **100–300 logical lines**.
- Review cohesion and split opportunities above **400 lines**.
- Above **600 lines** requires explicit justification or a tracked split plan.
- Prefer functions around **10–40 lines**; review functions above **60 lines** or with deep nesting/many branches.
- Keep React pages/components focused; extract hooks, data access, state transitions, and repeated UI when they change independently.

Generated files, schemas, migrations, tables, and tightly cohesive algorithms may exceed these ranges. Do not split them into meaningless fragments merely to satisfy line counts.

## Split by reason to change

Prefer feature/domain boundaries over generic `utils`, `helpers`, or layer-wide dumping grounds. A module should have:

- one clear responsibility and owner;
- a small public surface;
- dependencies passed at volatile boundaries;
- domain logic independent from HTTP, UI, storage, and model-provider details;
- tests through public behavior rather than private implementation.

Extract when code has multiple unrelated responsibilities, repeated policy, independent change cadence, excessive branching, circular dependencies, or difficult test setup.

## Extensibility

- Prefer composition over inheritance.
- Introduce protocols/interfaces only at real volatile boundaries.
- Use strategy/registry/plugin patterns only when at least two meaningful variants exist or an approved near-term variant is known.
- Keep configuration declarative; avoid scattered provider/type conditionals.
- Make the default path simple and the extension point narrow.

Do not add factories, abstract base classes, event buses, or plugin systems for hypothetical reuse. The best extension point is often a small function or injected callable.

## Handoff

Report files created/split, responsibility of each, public interfaces, dependency direction, compatibility adapters, tests, remaining oversized hotspots, and intentional exceptions to size guidance.
