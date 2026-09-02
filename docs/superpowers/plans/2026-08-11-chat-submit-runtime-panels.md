# Chat Submit and Runtime Panels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make chat submission work under React 18 `StrictMode`, keep runtime feedback in the chat column, and move connector management into settings.

**Architecture:** Re-activate the existing run lifecycle during each effect setup so the StrictMode setup/cleanup/setup cycle cannot leave it disposed. Keep execution trace and tool approval as chat runtime concerns, while rendering integrations in the existing settings dialog.

**Tech Stack:** React 18, TypeScript, Vitest, Vite, React server rendering for node-environment component tests.

## Global Constraints

- Frontend-only repair; no backend contract changes.
- No removal of concurrency, cancellation, SSE, or profile behavior.
- No unrelated visual redesign or refactor.
- Preserve all unrelated dirty-worktree changes.
- Do not disable `React.StrictMode`.
- Do not commit changes.

---

### Task 1: Repair StrictMode lifecycle and runtime panel placement

**Files:**
- Modify: `frontend/src/pages/chat/hooks/chatStreamAdapter.ts`
- Modify: `frontend/src/pages/chat/hooks/chatStreamAdapter.test.ts`
- Modify: `frontend/src/pages/chat/hooks/useMessageActions.ts`
- Modify: `frontend/src/pages/chat/components/ChatRuntimePanels.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`
- Modify: `frontend/src/components/ApiSettings.tsx`
- Modify or create focused component test files under `frontend/src/features/integrations/` or `frontend/src/pages/chat/components/` using the existing `*.test.ts` convention
- Modify only if required for the relocated settings section: `frontend/src/styles/features/runtime-panels.css`

**Interfaces:**
- `createChatRunLifecycle()` keeps `begin()`, `isActive()`, `stop()`, and `dispose()` and adds `mount(): void` to reactivate the same lifecycle for an effect setup.
- `ChatRuntimePanels({ executionId: string | null })` retains execution trace and tool approval behavior but contains no integrations UI.
- `ApiSettings({ isOpen, onClose })` remains the single settings dialog and includes `IntegrationsPanel` within `.settings-content`.

- [ ] **Step 1: Add the failing StrictMode lifecycle regression**

Extend `chatStreamAdapter.test.ts` with a test equivalent to:

```ts
it("accepts a run after the StrictMode setup-cleanup-setup cycle", () => {
  const lifecycle = createChatRunLifecycle();
  lifecycle.mount();
  lifecycle.dispose();
  lifecycle.mount();

  expect(lifecycle.begin()).toBe(1);
});
```

Run:

```powershell
cd frontend
npm.cmd test -- --run src/pages/chat/hooks/chatStreamAdapter.test.ts
```

Expected RED: the lifecycle has no `mount()` method.

- [ ] **Step 2: Add failing component-placement regressions**

Using `createElement` and `renderToStaticMarkup`, with `@/i18n/config` initialized where needed, assert:

```ts
expect(renderToStaticMarkup(createElement(ChatRuntimePanels, { executionId: null }))).toBe("");
```

and for open settings:

```ts
const html = renderToStaticMarkup(createElement(ApiSettings, { isOpen: true, onClose() {} }));
expect(html).toContain("integrations-panel");
```

Also make the test fail if `ChatRuntimePanels` output contains `integrations-panel`.

Run the new/modified focused tests and confirm RED because the idle trace and integrations placement still match the broken implementation.

- [ ] **Step 3: Implement lifecycle reactivation**

In `createChatRunLifecycle`, add:

```ts
mount(): void {
  mounted = true;
},
```

In `useMessageActions`, change the effect to activate the lifecycle during setup and dispose that lifecycle during cleanup:

```ts
useEffect(() => {
  const lifecycle = runLifecycleRef.current;
  lifecycle.mount();
  return () => {
    streamStoppedRef.current = true;
    lifecycle.dispose();
    streamAbortRef.current?.abort();
  };
}, []);
```

Do not change the request, profile, SSE, error, or cancellation branches.

- [ ] **Step 4: Implement panel relocation**

- Remove `IntegrationsPanel` from `ChatRuntimePanels`.
- Return `null` from `ChatRuntimePanels` while `executionId` is absent and there is no pending approval; after execution begins, retain trace and approval rendering.
- Move `<ChatRuntimePanels executionId={executionId} />` inside `<main>`, immediately after `ChatMessages` and before `ChatComposer`.
- Import and render `<IntegrationsPanel />` inside the non-loading `.settings-content` portion of `ApiSettings` as a separate settings section.
- Add only the minimal scoped CSS needed for the panel to fit the settings dialog; do not redesign the dialog.

- [ ] **Step 5: Verify focused tests GREEN**

Run all modified/new tests plus:

```powershell
cd frontend
npm.cmd test -- --run src/pages/chat/hooks/chatStreamAdapter.test.ts src/features/integrations/panel.test.ts src/pages/chat/components/profileCapabilities.test.ts
```

Expected: every selected test passes with zero failures.

- [ ] **Step 6: Verify the frontend**

Run:

```powershell
cd frontend
npm.cmd test -- --run
npm.cmd run build
```

Record exact pass/fail counts. Do not describe the known integrations i18n test as passing unless it is actually fixed by the test initialization.

- [ ] **Step 7: Inspect scope and live service**

Run:

```powershell
git diff --check -- frontend
git diff -- frontend/src/pages/chat/hooks/chatStreamAdapter.ts frontend/src/pages/chat/hooks/chatStreamAdapter.test.ts frontend/src/pages/chat/hooks/useMessageActions.ts frontend/src/pages/chat/components/ChatRuntimePanels.tsx frontend/src/pages/ChatPage.tsx frontend/src/components/ApiSettings.tsx frontend/src/styles/features/runtime-panels.css
```

Confirm `http://127.0.0.1:5173/` returns HTTP 200. If no authenticated browser is available, report manual click-through as unverified rather than passing.
