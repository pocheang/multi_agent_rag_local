# Chat submit and runtime panel repair

## Goal

Restore chat submission under the existing React 18 development runtime and remove the misplaced integrations panel from the chat layout. Preserve the current backend contracts, profile semantics, authentication, and SSE implementation.

## Confirmed causes

1. `useMessageActions` creates one lifecycle object during render and permanently disposes it in effect cleanup. React `StrictMode` runs an effect setup/cleanup/setup cycle in development, so the surviving component retains a disposed lifecycle. `ask()` then exits when `begin()` returns `null`, before clearing the question or sending a request.
2. `ChatRuntimePanels` renders after `</main>` as a direct child of the two-column `.page-shell` grid. Its always-present integrations panel becomes an unintended extra grid item and creates the large empty block shown by the user.

## Design

### Submission lifecycle

- Create a fresh chat-run lifecycle during every `useEffect` setup and assign it to the ref.
- Cleanup must dispose only the lifecycle created by that setup and abort only the active request belonging to the unmounted component.
- Preserve duplicate-submit rejection, explicit cancellation, stale-event suppression, and unmount cleanup.
- Do not remove `React.StrictMode` as a workaround.

### Runtime panels

- Keep execution trace and tool approval in `ChatRuntimePanels`.
- Render `ChatRuntimePanels` inside `<main>`, between the message window and composer, so it participates in the chat content column.
- Do not render an empty execution trace panel before an execution exists. Tool approval remains visible whenever approval is pending.

### Integrations

- Remove `IntegrationsPanel` from `ChatRuntimePanels`.
- Render it inside the existing API/settings dialog content as a separate settings section.
- Keep connector API calls, credentials handling, translations, and backend contracts unchanged.

## Error and state behavior

- A valid click must immediately enter sending state and clear the input before session creation/query execution.
- Session creation, authentication, query, SSE, model, and cancellation errors continue through the existing user-visible toast/message paths.
- Remounting in `StrictMode` must not disable future submissions.

## Tests

1. Add a regression test that mounts a minimal `useMessageActions` harness inside `React.StrictMode`, clicks submit, and proves the session/query path starts after the StrictMode effect cycle. Confirm the test fails before the production change.
2. Extend component tests to prove integrations are absent from `ChatRuntimePanels`, present in settings, and empty runtime panels do not render in an idle chat.
3. Re-run focused chat lifecycle, stream adapter, integrations, settings, and profile tests.
4. Run the full frontend test suite and `npm run build`.
5. With the live Vite/FastAPI services, verify the page still serves and authenticated/manual UI behavior is clearly separated from automated checks when browser session access is unavailable.

## Scope constraints

- Frontend-only repair; no backend contract changes.
- No removal of concurrency, cancellation, SSE, or profile behavior.
- No unrelated visual redesign or refactor.
- Preserve all unrelated dirty-worktree changes.
