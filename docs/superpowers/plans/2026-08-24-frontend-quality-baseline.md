# Frontend Quality Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 恢复前端测试收集、会话重命名契约、Storage 降级和 ESLint 门禁的可信基线。

**Architecture:** 纯逻辑测试继续使用 Vitest 的 node 环境，DOM 测试按文件切换 jsdom；Storage 访问集中到一个无状态 adapter。ESLint 只修正 TypeScript 环境误配，并逐条消除真实 warning，不降低 `--max-warnings 0`。

**Tech Stack:** React 18、TypeScript 5.9、Vite 6、Vitest 3、Testing Library 16、ESLint 9 flat config、jsdom 26

**Spec:** `docs/superpowers/specs/2026-08-24-frontend-low-risk-repairs-design.md`

## Global Constraints

- 不迁移 localStorage bearer 到纯 HttpOnly Cookie。
- 不运行全仓库 Prettier 写入，不处理 238 个格式差异。
- 不重构超大 CSS、设计 token 或 bundle 分包。
- 不批量删除旧动画体系、专用 ErrorBoundary 和全部零引用文件。
- 不改变页面视觉设计、路由、权限或后端接口。
- 不降低 ESLint 的 `--max-warnings 0`。
- 语言默认 `en`，Chat 布局默认显示，现有 Storage key 不改名。
- 仓库已有未提交改动；每次只暂存任务明确列出的文件。

---

## File Structure

- `frontend/vitest.config.ts`：同时收集 `.test.ts` 和 `.test.tsx`，默认保持 node。
- `frontend/src/components/animations/*.test.tsx`：文件级 jsdom；旧组件保留有效断言，当前 Lite 组件增加最小行为断言。
- `frontend/src/lib/session-api.test.ts`：验证真实 PATCH 请求契约和统一错误类型。
- `frontend/src/lib/safe-storage.ts`：唯一负责安全读取、写入和删除浏览器 Storage。
- `frontend/src/lib/safe-storage.test.ts`：覆盖 Storage 缺失、读写异常和正常路径。
- `frontend/src/i18n/config.test.ts`：证明语言初始化在 Storage getter 抛错时仍可加载。
- `frontend/src/hooks/useSectionToggle.test.tsx`：证明布局 hooks 在 Storage 读写失败时仍可渲染和切换。
- `frontend/eslint.config.js`：声明 browser/node 环境，TS 文件关闭核心 `no-undef`，仅对明确的混合导出文件缩窄 Fast Refresh 规则。
- 其余列出的 TS/TSX 文件：逐条清理 37 个真实 warning，不承担结构重写。

### Task 1: Make DOM Tests Discoverable and Deterministic

**Files:**
- Modify: `frontend/vitest.config.ts`
- Modify: `frontend/src/components/animations/AnimatedButton.test.tsx`
- Modify: `frontend/src/components/animations/AnimationComponents.test.tsx`
- Create: `frontend/src/components/animations/AnimatedButtonLite.test.tsx`
- Create: `frontend/src/components/animations/AnimatedToastLite.test.tsx`

**Interfaces:**
- Consumes: Vitest file-level environment directive `// @vitest-environment jsdom`.
- Produces: test discovery pattern `src/**/*.test.{ts,tsx}`; deterministic behavior coverage for both retained and currently used animation components.

- [ ] **Step 1: Prove TSX tests are currently excluded**

Run: `cd frontend && npm run test -- --run src/components/animations/AnimatedButton.test.tsx`

Expected: FAIL with `No test files found` because `vitest.config.ts` only includes `.test.ts`.

- [ ] **Step 2: Expand collection without changing the default environment**

Replace the `test` block in `frontend/vitest.config.ts` with:

```ts
test: {
  environment: "node",
  include: ["src/**/*.test.{ts,tsx}"],
},
```

Add this as the first line of every animation `.test.tsx` file touched by this task:

```ts
// @vitest-environment jsdom
```

- [ ] **Step 3: Remove timing-based assertions and test console output from retained tests**

In `AnimatedButton.test.tsx` and `AnimationComponents.test.tsx`, delete only the cases that compare elapsed render time or call `console.log`. Keep role, label, click, loading, close, spinner, skeleton, and toast assertions intact. Timing thresholds are machine-dependent and are not product behavior.

- [ ] **Step 4: Add deterministic Lite button coverage**

Create `frontend/src/components/animations/AnimatedButtonLite.test.tsx`:

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AnimatedButtonLite } from "./AnimatedButtonLite";

describe("AnimatedButtonLite", () => {
  it("does not invoke onClick while disabled", () => {
    const onClick = vi.fn();
    render(<AnimatedButtonLite disabled onClick={onClick}>Save</AnimatedButtonLite>);

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onClick).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("renders externally controlled loading state", () => {
    render(<AnimatedButtonLite state="loading">Save</AnimatedButtonLite>);

    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });
});
```

- [ ] **Step 5: Add deterministic Lite toast coverage**

Create `frontend/src/components/animations/AnimatedToastLite.test.tsx`:

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AnimatedToastLite } from "./AnimatedToastLite";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe("AnimatedToastLite", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("closes after its duration and exit animation", () => {
    const onClose = vi.fn();
    render(
      <AnimatedToastLite
        toast={{ id: "toast-1", message: "Saved", type: "success", duration: 1000 }}
        index={0}
        onClose={onClose}
      />,
    );

    act(() => vi.advanceTimersByTime(1299));
    expect(onClose).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(onClose).toHaveBeenCalledWith("toast-1");
  });

  it("starts the exit path when clicked", () => {
    const onClose = vi.fn();
    render(
      <AnimatedToastLite
        toast={{ id: "toast-2", message: "Notice", type: "info" }}
        index={0}
        onClose={onClose}
      />,
    );

    fireEvent.click(screen.getByRole("alert"));
    act(() => vi.advanceTimersByTime(300));
    expect(onClose).toHaveBeenCalledWith("toast-2");
  });
});
```

- [ ] **Step 6: Run the animation group**

Run: `cd frontend && npm run test -- --run src/components/animations`

Expected: all four TSX test files are collected and PASS; output contains no timing logs.

- [ ] **Step 7: Commit only this test-discovery batch**

```bash
git add frontend/vitest.config.ts frontend/src/components/animations/AnimatedButton.test.tsx frontend/src/components/animations/AnimationComponents.test.tsx frontend/src/components/animations/AnimatedButtonLite.test.tsx frontend/src/components/animations/AnimatedToastLite.test.tsx
git commit -m "test: collect frontend DOM component tests"
```

### Task 2: Replace the Stale Session Rename Assertion with a Request Contract

**Files:**
- Modify: `frontend/src/lib/session-api.test.ts`

**Interfaces:**
- Consumes: `sessionApi.sessionRename(sessionId: string, title: string): Promise<SessionDetail>` and `ApiError`.
- Produces: request-level coverage for encoded path, PATCH body, credentials, and non-success response behavior.

- [ ] **Step 1: Write the request-level tests**

Replace `frontend/src/lib/session-api.test.ts` with:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/services/http/client";
import { sessionApi } from "./session-api";

describe("session API contract", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renames a session with an encoded PATCH request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ session_id: "folder/name" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    await sessionApi.sessionRename("folder/name", "New title");

    expect(fetchMock).toHaveBeenCalledWith(
      "/sessions/folder%2Fname",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ title: "New title" }),
        credentials: "include",
      }),
    );
  });

  it("uses ApiError for a rejected rename", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "rename rejected" }), {
      status: 409,
      headers: { "Content-Type": "application/json" },
    })));

    await expect(sessionApi.sessionRename("session-1", "Conflict")).rejects.toEqual(
      expect.objectContaining<ApiError>({ name: "ApiError", status: 409, message: "rename rejected" }),
    );
  });
});
```

- [ ] **Step 2: Run the contract test**

Run: `cd frontend && npm run test -- --run src/lib/session-api.test.ts`

Expected: both cases PASS. If the first request URL includes a configured base prefix, assert the exact value produced by the test environment rather than weakening the path check.

- [ ] **Step 3: Commit the test-only correction**

```bash
git add frontend/src/lib/session-api.test.ts
git commit -m "test: align session rename contract"
```

### Task 3: Add Safe Storage and Migrate Language/Layout Preferences

**Files:**
- Create: `frontend/src/lib/safe-storage.ts`
- Create: `frontend/src/lib/safe-storage.test.ts`
- Create: `frontend/src/i18n/config.test.ts`
- Create: `frontend/src/hooks/useSectionToggle.test.tsx`
- Modify: `frontend/src/i18n/config.ts`
- Modify: `frontend/src/hooks/useSectionToggle.tsx`

**Interfaces:**
- Produces: `safeStorage.get(key: string, fallback: string): string`, `safeStorage.set(key: string, value: string): boolean`, `safeStorage.remove(key: string): boolean`.
- Consumers: language key `language`; layout keys `chatSectionsHidden` and `chatTopbarHidden`.

- [ ] **Step 1: Write adapter failure-path tests**

Create `frontend/src/lib/safe-storage.test.ts`:

```ts
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { safeStorage } from "./safe-storage";

describe("safeStorage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("returns the fallback when reading throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });

    expect(safeStorage.get("language", "en")).toBe("en");
  });

  it("reports failed writes and removals without throwing", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("full", "QuotaExceededError");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });

    expect(safeStorage.set("language", "zh")).toBe(false);
    expect(safeStorage.remove("language")).toBe(false);
  });
});
```

- [ ] **Step 2: Run the new adapter test and confirm the missing module failure**

Run: `cd frontend && npm run test -- --run src/lib/safe-storage.test.ts`

Expected: FAIL because `./safe-storage` does not exist.

- [ ] **Step 3: Implement the adapter**

Create `frontend/src/lib/safe-storage.ts`:

```ts
function browserStorage(): Storage | undefined {
  try {
    return typeof localStorage === "undefined" ? undefined : localStorage;
  } catch {
    return undefined;
  }
}

export const safeStorage = {
  get(key: string, fallback: string): string {
    try {
      return browserStorage()?.getItem(key) ?? fallback;
    } catch {
      return fallback;
    }
  },

  set(key: string, value: string): boolean {
    try {
      const storage = browserStorage();
      if (!storage) return false;
      storage.setItem(key, value);
      return true;
    } catch {
      return false;
    }
  },

  remove(key: string): boolean {
    try {
      const storage = browserStorage();
      if (!storage) return false;
      storage.removeItem(key);
      return true;
    } catch {
      return false;
    }
  },
};
```

- [ ] **Step 4: Write initialization and hook regression tests**

Create `frontend/src/i18n/config.test.ts`:

```ts
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

describe("i18n storage fallback", () => {
  afterEach(() => vi.restoreAllMocks());

  it("loads with English fallback when Storage reading throws", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    vi.resetModules();

    const { default: i18n } = await import("./config");

    expect(i18n.language).toBe("en");
    expect(document.documentElement.lang).toBe("en");
  });
});
```

Create `frontend/src/hooks/useSectionToggle.test.tsx`:

```tsx
// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useSectionToggle, useTopbarToggle } from "./useSectionToggle";

describe("layout preference storage fallback", () => {
  afterEach(() => vi.restoreAllMocks());

  it("renders visible defaults and still toggles when Storage fails", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new DOMException("blocked", "SecurityError"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("full", "QuotaExceededError"); });

    const sections = renderHook(() => useSectionToggle());
    const topbar = renderHook(() => useTopbarToggle());
    expect(sections.result.current.sectionsHidden).toBe(false);
    expect(topbar.result.current.topbarHidden).toBe(false);

    act(() => sections.result.current.toggleSections());
    act(() => topbar.result.current.toggleTopbar());
    expect(sections.result.current.sectionsHidden).toBe(true);
    expect(topbar.result.current.topbarHidden).toBe(true);
  });
});
```

- [ ] **Step 5: Migrate the three consumers**

In `frontend/src/i18n/config.ts`, import the adapter and replace the top-level read:

```ts
import { safeStorage } from "@/lib/safe-storage";

const savedLanguage = safeStorage.get("language", "en");
```

In `frontend/src/hooks/useSectionToggle.tsx`, import the adapter, replace both `localStorage.getItem` initializer blocks with these expressions, and replace the two `localStorage.setItem` statements with the shown adapter calls. Leave the existing DOM class loops below each call unchanged.

```tsx
const [sectionsHidden, setSectionsHidden] = useState(
  () => safeStorage.get("chatSectionsHidden", "false") === "true",
);

safeStorage.set("chatSectionsHidden", String(sectionsHidden));

const [topbarHidden, setTopbarHidden] = useState(
  () => safeStorage.get("chatTopbarHidden", "false") === "true",
);

safeStorage.set("chatTopbarHidden", String(topbarHidden));
```

- [ ] **Step 6: Run the Storage group**

Run: `cd frontend && npm run test -- --run src/lib/safe-storage.test.ts src/i18n/config.test.ts src/hooks/useSectionToggle.test.tsx`

Expected: all tests PASS and no `SecurityError`/`QuotaExceededError` escapes.

- [ ] **Step 7: Commit the isolated Storage migration**

```bash
git add frontend/src/lib/safe-storage.ts frontend/src/lib/safe-storage.test.ts frontend/src/i18n/config.ts frontend/src/i18n/config.test.ts frontend/src/hooks/useSectionToggle.tsx frontend/src/hooks/useSectionToggle.test.tsx
git commit -m "fix: safely persist frontend preferences"
```

### Task 4: Correct ESLint Environments without Weakening the Gate

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/eslint.config.js`

**Interfaces:**
- Consumes: `globals@^14.0.0` already present transitively in the installed dependency tree.
- Produces: browser globals for source, node globals for tests, TypeScript-owned undefined-name checking, and explicit Fast Refresh exceptions for six mixed-export modules.

- [ ] **Step 1: Capture the failing gate**

Run: `cd frontend && npm run lint -- --quiet`

Expected: FAIL with about 201 core `no-undef` errors in TS/TSX files.

- [ ] **Step 2: Make `globals` a direct development dependency**

Run: `cd frontend && npm install --save-dev globals@^14.0.0 --package-lock-only --offline`

Expected: `package.json` and `package-lock.json` list `globals`; no application runtime dependency changes.

- [ ] **Step 3: Layer environments and disable only the core TS rule**

Add this import to `frontend/eslint.config.js`:

```js
import globals from 'globals';
```

Replace the hand-written `globals` object in the TS/TSX block and add the core rule:

```js
languageOptions: {
  parser: tsparser,
  parserOptions: {
    ecmaVersion: 2020,
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  globals: globals.browser,
},
rules: {
  'no-undef': 'off',
},
```

Insert `'no-undef': 'off'` alongside the existing rules; do not delete or change the existing TypeScript, React, hook, console, or general rules.

Add a test override after the TS/TSX block:

```js
{
  files: ['src/**/*.test.{ts,tsx}'],
  languageOptions: {
    globals: {
      ...globals.browser,
      ...globals.node,
    },
  },
},
```

- [ ] **Step 4: Add the narrow Fast Refresh exception**

Add this final override. These files intentionally export HOCs/hooks/utilities alongside components; the rule remains active everywhere else.

```js
{
  files: [
    'src/components/AdminErrorBoundary.tsx',
    'src/components/ChatErrorBoundary.tsx',
    'src/components/animations/AnimatedToast.tsx',
    'src/components/animations/AnimatedToastLite.tsx',
    'src/hooks/usePermissions.tsx',
    'src/utils/exportUtils.tsx',
  ],
  rules: {
    'react-refresh/only-export-components': 'off',
  },
},
```

- [ ] **Step 5: Verify that only the 26 non-Fast-Refresh warnings remain**

Run: `cd frontend && npm run lint`

Expected: FAIL because `--max-warnings 0` still sees the remaining real warnings; there are no `no-undef` errors and no warning from `react-refresh/only-export-components` in the six named files.

- [ ] **Step 6: Commit the configuration correction**

```bash
git add frontend/package.json frontend/package-lock.json frontend/eslint.config.js
git commit -m "fix: configure eslint for frontend environments"
```

### Task 5: Remove Mechanical TypeScript and Console Warnings

**Files:**
- Modify: `frontend/src/components/animations/AnimatedButton.tsx`
- Modify: `frontend/src/components/animations/AnimatedButtonLite.tsx`
- Modify: `frontend/src/components/SessionManagement/SessionSearch.tsx`
- Modify: `frontend/src/hooks/usePerformanceMonitoring.ts`
- Modify: `frontend/src/lib/async-utils.ts`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/pages/chat/components/SessionList.tsx`
- Modify: `frontend/src/pages/chat/hooks/chatStreamAdapter.test.ts`
- Modify: `frontend/src/pages/chat/hooks/useChatInitialization.ts`
- Modify: `frontend/src/pages/chat/hooks/useMessageActions.test.ts`
- Modify: `frontend/src/pages/chat/hooks/useSettingsPolling.ts`

**Interfaces:**
- Produces: identical runtime behavior with explicit types, guarded DOM root access, and no unused bindings/non-null assertions.
- Consumes: existing component and test APIs; no exported signature changes except `TArgs extends unknown[]` in `createAsyncAction`.

- [ ] **Step 1: Apply the unused-binding and explicit-type replacements**

Use parameterless catches in both animated button files, both silent catches in `useSettingsPolling.ts`, and the pin/delete catches in `SessionList.tsx`:

```ts
} catch {
  // Keep each existing fallback/state transition body unchanged.
}
```

In `SessionSearch.tsx`, declare and use exact select types:

```tsx
type SortBy = 'updated_at' | 'created_at' | 'query_count';
type SortOrder = 'asc' | 'desc';

const [sortBy, setSortBy] = useState<SortBy>('updated_at');
const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

onChange={(event) => setSortBy(event.target.value as SortBy)}
onChange={(event) => setSortOrder(event.target.value as SortOrder)}
```

In `async-utils.ts`, replace the variadic constraint:

```ts
export function createAsyncAction<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
```

- [ ] **Step 2: Guard the React root instead of asserting it exists**

Replace the root creation in `frontend/src/main.tsx`:

```tsx
const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Application root element was not found");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
```

- [ ] **Step 3: Replace test non-null assertions with explicit narrowing**

In `chatStreamAdapter.test.ts`, narrow both run identifiers before use:

```ts
expect(first).not.toBeNull();
if (first === null) throw new Error("first run was not created");
expect(lifecycle.isActive(first)).toBe(true);
lifecycle.stop(first);
expect(lifecycle.isActive(first)).toBe(false);

const second = lifecycle.begin();
expect(second).not.toBeNull();
if (second === null) throw new Error("second run was not created");
lifecycle.dispose();
expect(lifecycle.isActive(second)).toBe(false);
```

In `useMessageActions.test.ts`, narrow the captured hook before calling `ask`:

```ts
if (!hook) throw new Error("hook was not initialized");
askPromise = hook.ask({
  question: "StrictMode question",
  isSending: false,
  useWeb: false,
  useReasoning: false,
  agentClassHint: "",
  retrievalStrategy: "advanced",
  pipelineProfile: "standard",
});
```

- [ ] **Step 4: Preserve intentional performance diagnostics with line-scoped justification**

Immediately before the two intentional `console.log` calls in `usePerformanceMonitoring.ts`, add:

```ts
// eslint-disable-next-line no-console -- Development performance telemetry is intentionally visible in DevTools.
```

Do not change the global `no-console` rule. The three timing logs in animation tests were removed in Task 1 rather than suppressed.

- [ ] **Step 5: Make the existing smart-prompt dependency real without changing its empty result**

Replace `useSmartPrompts` with:

```ts
export function useSmartPrompts({ messages }: SmartPromptsOptions) {
  return useMemo<string[]>(() => {
    void messages;
    return [];
  }, [messages]);
}
```

- [ ] **Step 6: Run focused type-check and lint**

Run: `cd frontend && npm run type-check && npm run lint`

Expected: type-check PASS; lint still fails only on hook dependency warnings assigned to Task 6.

- [ ] **Step 7: Commit the mechanical cleanup**

```bash
git add frontend/src/components/animations/AnimatedButton.tsx frontend/src/components/animations/AnimatedButtonLite.tsx frontend/src/components/SessionManagement/SessionSearch.tsx frontend/src/hooks/usePerformanceMonitoring.ts frontend/src/lib/async-utils.ts frontend/src/main.tsx frontend/src/pages/chat/components/SessionList.tsx frontend/src/pages/chat/hooks/chatStreamAdapter.test.ts frontend/src/pages/chat/hooks/useChatInitialization.ts frontend/src/pages/chat/hooks/useMessageActions.test.ts frontend/src/pages/chat/hooks/useSettingsPolling.ts
git commit -m "fix: clear mechanical frontend lint warnings"
```

### Task 6: Resolve Hook Dependency Warnings at Their Effect Boundaries

**Files:**
- Modify: `frontend/src/components/SessionManagement/SessionMetadataEditor.tsx`
- Modify: `frontend/src/components/SessionManagement/SessionSearch.tsx`
- Modify: `frontend/src/features/integrations/IntegrationsPanel.tsx`
- Modify: `frontend/src/pages/admin/AdminAgentQualityDashboard.tsx`
- Modify: `frontend/src/pages/admin/AdminWebActivityDashboard.tsx`

**Interfaces:**
- Produces: stable admin refresh functions, latest-callback search scheduling, and dependency-complete effects.
- Consumes: existing APIs and UI state; no request path or payload changes.

- [ ] **Step 1: Stabilize metadata loading**

Import `useCallback`, move `loadMetadata` above its effect, and wrap it as follows:

```tsx
const loadMetadata = useCallback(async () => {
  setLoading(true);
  setError(null);
  try {
    const metadata = await sessionManagementApi.getMetadata(sessionId);
    setTags(metadata.tags);
    setCategory(metadata.category);
    setDescription(metadata.description || '');
    setAutoTags(metadata.auto_tags);
  } catch (err: unknown) {
    if (!(err instanceof ApiError && err.status === 404)) {
      console.error('Failed to load metadata:', err);
      setError(t('sessionManagement.errorLoadingMetadata'));
    }
  } finally {
    setLoading(false);
  }
}, [sessionId, t]);

useEffect(() => {
  void loadMetadata();
}, [loadMetadata]);
```

Keep `handleCancel` calling the same stable `loadMetadata` function.

- [ ] **Step 2: Preserve SessionSearch click semantics with a latest callback ref**

Import `useRef`, place `handleSearch` before the scheduling effect, then add:

```tsx
const handleSearchRef = useRef(handleSearch);
handleSearchRef.current = handleSearch;

useEffect(() => {
  void handleSearchRef.current();
}, [page, sortBy, sortOrder]);
```

This keeps text/tag/category changes manual until the search button is used, while pagination and sorting still trigger a request.

- [ ] **Step 3: Complete the integration translation dependency**

In `IntegrationsPanel.tsx`, use:

```tsx
}, [t]);
```

for the connector-loading effect so a language change can refresh its translated failure message.

- [ ] **Step 4: Stabilize both admin refresh functions**

Import `useCallback` in both dashboard files and replace each request function/effect pair with the exact matching block below.

```tsx
const fetchStats = useCallback(async () => {
  try {
    setError(null);
    const data = await authRequest<AgentQualityStats>("/api/v1/admin/agent-quality/stats");
    setStats(data);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      setError(t("admin.agentQuality.authRequired", "Authentication required. Please sign in again."));
    } else {
      setError(t("admin.agentQuality.loadingError", "Failed to fetch agent quality data."));
    }
    console.error("Failed to fetch agent quality stats:", err);
  } finally {
    setLoading(false);
  }
}, [t]);

useEffect(() => {
  void fetchStats();
  if (!autoRefresh) return;
  const interval = window.setInterval(() => void fetchStats(), 30000);
  return () => window.clearInterval(interval);
}, [autoRefresh, fetchStats]);
```

For `AdminWebActivityDashboard.tsx`, use:

```tsx
const fetchData = useCallback(async () => {
  try {
    setError(null);
    const [statsData, alertsData] = await Promise.all([
      authRequest<WebActivityStats>("/api/v1/admin/web-activity/stats"),
      authRequest<AlertsResponse>("/api/v1/admin/web-activity/alerts?hours=24"),
    ]);
    setStats(statsData);
    setAlerts(alertsData.alerts || []);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      setError(t("admin.webActivity.authRequired", "Authentication required. Please sign in again."));
    } else {
      setError(t("admin.webActivity.loadingError", "Failed to fetch web activity data."));
    }
  } finally {
    setLoading(false);
  }
}, [t]);

useEffect(() => {
  void fetchData();
  if (!autoRefresh) return;
  const interval = window.setInterval(() => void fetchData(), 30000);
  return () => window.clearInterval(interval);
}, [autoRefresh, fetchData]);
```

- [ ] **Step 5: Run the strict lint gate**

Run: `cd frontend && npm run lint`

Expected: PASS with 0 errors and 0 warnings.

- [ ] **Step 6: Run affected component tests and type-check**

Run: `cd frontend && npm run test -- --run src/components src/pages/admin src/features/integrations && npm run type-check`

Expected: all collected tests PASS; type-check PASS.

- [ ] **Step 7: Commit dependency fixes**

```bash
git add frontend/src/components/SessionManagement/SessionMetadataEditor.tsx frontend/src/components/SessionManagement/SessionSearch.tsx frontend/src/features/integrations/IntegrationsPanel.tsx frontend/src/pages/admin/AdminAgentQualityDashboard.tsx frontend/src/pages/admin/AdminWebActivityDashboard.tsx
git commit -m "fix: stabilize frontend effect dependencies"
```

### Task 7: Verify the Quality Baseline as an Independent Deliverable

**Files:**
- Verify only; do not edit unrelated files while interpreting failures.

**Interfaces:**
- Consumes: Tasks 1–6.
- Produces: a green unit/type/lint/build baseline, with the known 238-file formatting baseline explicitly recorded rather than rewritten.

- [ ] **Step 1: Run all non-visual gates**

Run:

```bash
cd frontend
npm run type-check
npm run lint
npm run test -- --run
npm run build
```

Expected: all four commands PASS; the unit count is greater than the previous 63 because TSX tests are now collected.

- [ ] **Step 2: Confirm the formatting baseline without writing files**

Run: `cd frontend && npm run format:check`

Expected: non-zero status with the pre-existing broad formatting set (previous audit: 238 files). Do not run `npm run format` in this project.

- [ ] **Step 3: Inspect the exact staged scope**

Run: `git status --short && git diff --check`

Expected: no whitespace errors; no authentication, backend, CSS, route, permission, or unrelated user file is staged by these tasks.

- [ ] **Step 4: Record verification without an empty commit**

If Tasks 1–6 already produced clean commits, attach the command results to the implementation report. Do not create an empty verification commit.
