# Chat Runtime Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 稳定 Chat 的设置轮询、自动刷新、流式自动滚动和拖拽副作用所有权，避免 rerender 重建计时器或重复全局监听。

**Architecture:** 稳定性封装在各副作用 hook 内，通过 refs 使用最新回调，不重构整个 `useChatActions`。`ChatMessages` 成为自动滚动唯一所有者，`useDragDropPrevention` 成为 window 拖拽防默认行为的唯一所有者。

**Tech Stack:** React 18 hooks、TypeScript 5.9、Vitest 3 fake timers、Testing Library `renderHook`、jsdom 26

**Spec:** `docs/superpowers/specs/2026-08-24-frontend-low-risk-repairs-design.md`

## Global Constraints

- 轮询间隔保持 25,000 ms。
- 轮询失败继续静默降级，且不覆盖上一次成功状态。
- 不大规模 memo 化 `useChatActions` 或改变任何 API 请求。
- 不改变页面视觉结构、路由、权限或后端接口。
- 自动滚动不使用浏览器专有 API，接近底部阈值固定为 80 px。
- `useDragHandlers` 只处理 composer 局部事件；`useDragDropPrevention` 独占 window `dragover/drop`。
- 仓库已有未提交改动；每次只暂存任务明确列出的文件。

---

## File Structure

- `frontend/src/pages/chat/hooks/useSettingsPolling.ts`：稳定设置轮询、语言受控重启、最新通知回调和单次 in-flight 请求。
- `frontend/src/pages/chat/hooks/useSettingsPolling.test.tsx`：fake timer + rerender + 慢请求测试。
- `frontend/src/pages/chat/hooks/useAutoRefresh.ts`：单一 interval、最新三个刷新回调和整批 in-flight 锁。
- `frontend/src/pages/chat/hooks/useAutoRefresh.test.tsx`：验证 rerender 不重建 interval、tick 调用最新回调、慢批次不重叠。
- `frontend/src/pages/chat/hooks/useAutoScroll.ts`：使用前一次 scrollHeight 判断内容增长及用户更新前是否接近底部。
- `frontend/src/pages/chat/hooks/useAutoScroll.test.tsx`：覆盖同一消息增长、用户向上阅读、流结束更新。
- `frontend/src/pages/chat/components/ChatMessages.tsx`：自动滚动唯一组件所有者。
- `frontend/src/pages/ChatPage.tsx`：删除重复 hook import/call。
- `frontend/src/pages/chat/hooks/useDragHandlers.ts`：只返回局部 React drag handlers。
- `frontend/src/pages/chat/hooks/useDragHandlers.test.tsx`：证明不注册 window listener，并验证局部事件行为。
- `frontend/src/pages/chat/hooks/useDragDropPrevention.test.tsx`：证明唯一全局 listener 成对安装/清理。

### Task 1: Stabilize Settings Polling across Ordinary Rerenders

**Files:**
- Create: `frontend/src/pages/chat/hooks/useSettingsPolling.test.tsx`
- Modify: `frontend/src/pages/chat/hooks/useSettingsPolling.ts`

**Interfaces:**
- Consumes: `appApi.getUserApiSettings()` and `onNotify(message, type, duration)`.
- Produces: one initial request per mount/language cycle, one 25-second interval, latest notification callback, and no overlapping settings request.

- [ ] **Step 1: Write rerender and in-flight regression tests**

Create `frontend/src/pages/chat/hooks/useSettingsPolling.test.tsx`:

```tsx
// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appApi } from "@/lib/api";
import { useSettingsPolling } from "./useSettingsPolling";

vi.mock("@/lib/api", () => ({
  appApi: { getUserApiSettings: vi.fn() },
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, values?: Record<string, string>) => values ? `${key}:${values.provider}:${values.model}` : key,
    i18n: { resolvedLanguage: "en" },
  }),
}));

const settings = (enabled: boolean, provider = "", model = "") => ({
  ok: true,
  settings: {
    global_override_enabled: enabled,
    global_provider: provider,
    global_model: model,
  },
});

describe("useSettingsPolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(appApi.getUserApiSettings).mockReset();
  });
  afterEach(() => vi.useRealTimers());

  it("does not refetch on rerender and notifies through the latest callback", async () => {
    vi.mocked(appApi.getUserApiSettings)
      .mockResolvedValueOnce(settings(false))
      .mockResolvedValueOnce(settings(true, "openai", "gpt"));
    const firstNotify = vi.fn();
    const secondNotify = vi.fn();
    const { rerender } = renderHook(
      ({ onNotify }) => useSettingsPolling({ onNotify }),
      { initialProps: { onNotify: firstNotify } },
    );
    await act(async () => Promise.resolve());
    expect(appApi.getUserApiSettings).toHaveBeenCalledTimes(1);

    rerender({ onNotify: secondNotify });
    await act(async () => Promise.resolve());
    expect(appApi.getUserApiSettings).toHaveBeenCalledTimes(1);

    await act(async () => vi.advanceTimersByTimeAsync(25000));
    expect(firstNotify).not.toHaveBeenCalled();
    expect(secondNotify).toHaveBeenCalledWith(expect.stringContaining("globalOverrideNotice"), "info", 4000);
  });

  it("skips a tick while the prior request is unresolved", async () => {
    let resolveRequest: ((value: ReturnType<typeof settings>) => void) | undefined;
    vi.mocked(appApi.getUserApiSettings).mockImplementation(() => new Promise((resolve) => {
      resolveRequest = resolve;
    }));
    const { unmount } = renderHook(() => useSettingsPolling({ onNotify: vi.fn() }));

    await act(async () => vi.advanceTimersByTimeAsync(25000));
    expect(appApi.getUserApiSettings).toHaveBeenCalledTimes(1);

    await act(async () => resolveRequest?.(settings(false)));
    unmount();
  });
});
```

- [ ] **Step 2: Run the tests and observe old behavior**

Run: `cd frontend && npm run test -- --run src/pages/chat/hooks/useSettingsPolling.test.tsx`

Expected: FAIL because rerender triggers another initial request and the old implementation has no in-flight guard.

- [ ] **Step 3: Implement latest refs, language-cycle effect, and in-flight guard**

Replace the hook body with:

```ts
export function useSettingsPolling({ onNotify }: UseSettingsPollingOptions) {
  const { t, i18n } = useTranslation();
  const notifyRef = useRef(onNotify);
  const translateRef = useRef(t);
  const lastOverrideStateRef = useRef<{
    enabled: boolean;
    provider: string;
    model: string;
  } | null>(null);

  notifyRef.current = onNotify;
  translateRef.current = t;

  useEffect(() => {
    let disposed = false;
    let inFlight = false;

    const poll = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const res = await appApi.getUserApiSettings();
        if (disposed || !res.ok || !res.settings) return;
        const next = {
          enabled: Boolean(res.settings.global_override_enabled),
          provider: res.settings.global_provider || "",
          model: res.settings.global_model || "",
        };
        const previous = lastOverrideStateRef.current;
        if (previous && (
          previous.enabled !== next.enabled ||
          previous.provider !== next.provider ||
          previous.model !== next.model
        )) {
          if (next.enabled) {
            const desc = translateRef.current("components.apiSettings.globalOverrideDesc", {
              provider: next.provider,
              model: next.model,
            });
            notifyRef.current(
              `${translateRef.current("components.apiSettings.globalOverrideNotice")}: ${desc}`,
              "info",
              4000,
            );
          } else if (previous.enabled) {
            notifyRef.current(
              translateRef.current("components.apiSettings.globalOverrideDisabledNotice"),
              "info",
              4000,
            );
          }
        }
        lastOverrideStateRef.current = next;
      } catch {
        // Settings polling is best-effort.
      } finally {
        inFlight = false;
      }
    };

    void poll();
    const timer = window.setInterval(() => void poll(), 25000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [i18n.resolvedLanguage]);
}
```

- [ ] **Step 4: Run focused tests and lint**

Run: `cd frontend && npm run test -- --run src/pages/chat/hooks/useSettingsPolling.test.tsx && npm run lint -- src/pages/chat/hooks/useSettingsPolling.ts src/pages/chat/hooks/useSettingsPolling.test.tsx`

Expected: tests PASS; no hook dependency or unused-catch warning.

- [ ] **Step 5: Commit the settings polling fix**

```bash
git add frontend/src/pages/chat/hooks/useSettingsPolling.ts frontend/src/pages/chat/hooks/useSettingsPolling.test.tsx
git commit -m "fix: stabilize chat settings polling"
```

### Task 2: Keep One Auto-Refresh Interval and Use the Latest Callbacks

**Files:**
- Create: `frontend/src/pages/chat/hooks/useAutoRefresh.test.tsx`
- Modify: `frontend/src/pages/chat/hooks/useAutoRefresh.ts`

**Interfaces:**
- Consumes: existing refresh function signatures.
- Produces: one mount-scoped interval and one in-flight batch containing session/document/prompt refreshes.

- [ ] **Step 1: Write interval identity and latest-callback tests**

Create `frontend/src/pages/chat/hooks/useAutoRefresh.test.tsx`:

```tsx
// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAutoRefresh } from "./useAutoRefresh";

const callbacks = () => ({
  refreshSessions: vi.fn().mockResolvedValue([]),
  refreshDocuments: vi.fn().mockResolvedValue(undefined),
  refreshPrompts: vi.fn().mockResolvedValue(undefined),
});

describe("useAutoRefresh", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("keeps one interval and calls the latest callbacks", async () => {
    const first = callbacks();
    const second = callbacks();
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    const { rerender, unmount } = renderHook((props) => useAutoRefresh(props), {
      initialProps: first,
    });

    rerender(second);
    expect(setIntervalSpy).toHaveBeenCalledTimes(1);
    await act(async () => vi.advanceTimersByTimeAsync(25000));

    expect(first.refreshSessions).not.toHaveBeenCalled();
    expect(second.refreshSessions).toHaveBeenCalledWith(false, true);
    expect(second.refreshDocuments).toHaveBeenCalledWith(true);
    expect(second.refreshPrompts).toHaveBeenCalledWith(true);
    unmount();
  });

  it("does not overlap slow refresh batches", async () => {
    let resolveSessions: (() => void) | undefined;
    const slow = callbacks();
    slow.refreshSessions.mockImplementation(() => new Promise((resolve) => {
      resolveSessions = () => resolve([]);
    }));
    renderHook(() => useAutoRefresh(slow));

    await act(async () => vi.advanceTimersByTimeAsync(50000));
    expect(slow.refreshSessions).toHaveBeenCalledTimes(1);
    await act(async () => resolveSessions?.());
  });
});
```

- [ ] **Step 2: Run the tests and confirm interval reset/overlap**

Run: `cd frontend && npm run test -- --run src/pages/chat/hooks/useAutoRefresh.test.tsx`

Expected: FAIL because rerender installs a second interval and a 50-second advance starts overlapping batches.

- [ ] **Step 3: Implement callback refs and batch locking**

Replace the implementation with:

```ts
import { useEffect, useRef } from "react";

export function useAutoRefresh(options: UseAutoRefreshOptions) {
  const callbacksRef = useRef(options);
  callbacksRef.current = options;

  useEffect(() => {
    let inFlight = false;
    const refresh = async () => {
      if (inFlight) return;
      inFlight = true;
      const current = callbacksRef.current;
      try {
        await Promise.allSettled([
          current.refreshSessions(false, true),
          current.refreshDocuments(true),
          current.refreshPrompts(true),
        ]);
      } finally {
        inFlight = false;
      }
    };

    const timer = window.setInterval(() => void refresh(), 25000);
    return () => window.clearInterval(timer);
  }, []);
}
```

- [ ] **Step 4: Run the focused test and type-check**

Run: `cd frontend && npm run test -- --run src/pages/chat/hooks/useAutoRefresh.test.tsx && npm run type-check`

Expected: PASS.

- [ ] **Step 5: Commit the auto-refresh fix**

```bash
git add frontend/src/pages/chat/hooks/useAutoRefresh.ts frontend/src/pages/chat/hooks/useAutoRefresh.test.tsx
git commit -m "fix: stabilize chat auto refresh"
```

### Task 3: Give ChatMessages Sole Ownership of Growth-Aware Auto-Scroll

**Files:**
- Create: `frontend/src/pages/chat/hooks/useAutoScroll.test.tsx`
- Modify: `frontend/src/pages/chat/hooks/useAutoScroll.ts`
- Modify: `frontend/src/pages/chat/components/ChatMessages.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`

**Interfaces:**
- Produces: `useAutoScroll({ ref, messages })` with an 80 px near-bottom threshold.
- Consumers: only `ChatMessages`; `ChatPage` no longer imports or calls this hook.

- [ ] **Step 1: Write growth and user-position tests**

Create `frontend/src/pages/chat/hooks/useAutoScroll.test.tsx`:

```tsx
// @vitest-environment jsdom
import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SessionMessage } from "@/types/api";
import { useAutoScroll } from "./useAutoScroll";

const message = (content: string): SessionMessage => ({
  message_id: "local-assistant-stream",
  role: "assistant",
  content,
});

function scrollBox() {
  const element = document.createElement("div");
  Object.defineProperties(element, {
    scrollHeight: { configurable: true, writable: true, value: 1000 },
    clientHeight: { configurable: true, writable: true, value: 400 },
  });
  element.scrollTop = 550;
  return element;
}

describe("useAutoScroll", () => {
  it("follows same-message content growth when the user was near the bottom", () => {
    const element = scrollBox();
    const ref = { current: element };
    const { rerender } = renderHook(({ messages }) => useAutoScroll({ ref, messages }), {
      initialProps: { messages: [message("a")] },
    });
    element.scrollTop = 550;
    Object.defineProperty(element, "scrollHeight", { configurable: true, writable: true, value: 1200 });

    rerender({ messages: [message("ab")] });

    expect(element.scrollTop).toBe(1200);
  });

  it("preserves position when the user was more than 80px from the bottom", () => {
    const element = scrollBox();
    const ref = { current: element };
    const { rerender } = renderHook(({ messages }) => useAutoScroll({ ref, messages }), {
      initialProps: { messages: [message("a")] },
    });
    element.scrollTop = 200;
    Object.defineProperty(element, "scrollHeight", { configurable: true, writable: true, value: 1200 });

    rerender({ messages: [message("ab")] });

    expect(element.scrollTop).toBe(200);
  });

  it("handles the final replacement after the streaming marker disappears", () => {
    const element = scrollBox();
    const ref = { current: element };
    const { rerender } = renderHook(({ messages }) => useAutoScroll({ ref, messages }), {
      initialProps: { messages: [message("partial")] },
    });
    element.scrollTop = 550;
    Object.defineProperty(element, "scrollHeight", { configurable: true, writable: true, value: 1100 });

    rerender({ messages: [{ ...message("complete"), message_id: "server-message-1" }] });

    expect(element.scrollTop).toBe(1100);
  });
});
```

- [ ] **Step 2: Run the tests and reproduce same-length failure**

Run: `cd frontend && npm run test -- --run src/pages/chat/hooks/useAutoScroll.test.tsx`

Expected: FAIL because the current hook only reacts when `messages.length` increases.

- [ ] **Step 3: Implement previous-height and near-bottom logic**

Replace `useAutoScroll.ts` with:

```ts
import { useLayoutEffect, useRef } from "react";
import type { RefObject } from "react";
import type { SessionMessage } from "@/types/api";

const NEAR_BOTTOM_PX = 80;

interface UseAutoScrollOptions {
  ref: RefObject<HTMLDivElement>;
  messages: SessionMessage[];
}

export function useAutoScroll({ ref, messages }: UseAutoScrollOptions) {
  const previousHeightRef = useRef<number | null>(null);

  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;

    const previousHeight = previousHeightRef.current;
    const grew = previousHeight === null || element.scrollHeight > previousHeight;
    const wasNearBottom = previousHeight === null ||
      previousHeight - element.clientHeight - element.scrollTop <= NEAR_BOTTOM_PX;

    if (grew && wasNearBottom) {
      element.scrollTop = element.scrollHeight;
    }
    previousHeightRef.current = element.scrollHeight;
  }, [messages, ref]);

  return ref;
}
```

- [ ] **Step 4: Remove duplicate ownership**

In `ChatMessages.tsx`, remove the `isStreaming` calculation and call:

```tsx
useAutoScroll({ ref: containerRef, messages });
```

In `ChatPage.tsx`, delete:

```tsx
import { useAutoScroll } from "@/pages/chat/hooks/useAutoScroll";
```

and delete:

```tsx
useAutoScroll({ ref: chatScrollRef, messages });
```

- [ ] **Step 5: Run focused tests and Chat type-check**

Run: `cd frontend && npm run test -- --run src/pages/chat/hooks/useAutoScroll.test.tsx && npm run type-check`

Expected: all three cases PASS and there is exactly one source call to `useAutoScroll` under `src/pages`.

Run: `cd frontend && rg "useAutoScroll" src/pages`

Expected: import/call in `ChatMessages.tsx` only.

- [ ] **Step 6: Commit auto-scroll ownership**

```bash
git add frontend/src/pages/chat/hooks/useAutoScroll.ts frontend/src/pages/chat/hooks/useAutoScroll.test.tsx frontend/src/pages/chat/components/ChatMessages.tsx frontend/src/pages/ChatPage.tsx
git commit -m "fix: follow chat stream growth safely"
```

### Task 4: Make Global Drag Prevention Single-Owner

**Files:**
- Create: `frontend/src/pages/chat/hooks/useDragHandlers.test.tsx`
- Create: `frontend/src/pages/chat/hooks/useDragDropPrevention.test.tsx`
- Modify: `frontend/src/pages/chat/hooks/useDragHandlers.ts`

**Interfaces:**
- Produces: local composer handlers from `useDragHandlers`; global listener lifecycle only from `useDragDropPrevention`.

- [ ] **Step 1: Write ownership tests**

Create `frontend/src/pages/chat/hooks/useDragHandlers.test.tsx`:

```tsx
// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useDragHandlers } from "./useDragHandlers";

describe("useDragHandlers", () => {
  it("only handles composer events and registers no window listener", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    const setActive = vi.fn();
    const { result } = renderHook(() => useDragHandlers(setActive));
    const event = { preventDefault: vi.fn(), stopPropagation: vi.fn() };

    act(() => result.current.onComposerDragEnter(event as never));

    expect(event.preventDefault).toHaveBeenCalledOnce();
    expect(event.stopPropagation).toHaveBeenCalledOnce();
    expect(setActive).toHaveBeenCalledWith(true);
    expect(addSpy).not.toHaveBeenCalledWith("dragover", expect.any(Function));
    expect(addSpy).not.toHaveBeenCalledWith("drop", expect.any(Function));
  });
});
```

Create `frontend/src/pages/chat/hooks/useDragDropPrevention.test.tsx`:

```tsx
// @vitest-environment jsdom
import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useDragDropPrevention } from "./useDragDropPrevention";

describe("useDragDropPrevention", () => {
  it("installs and removes the sole global drag handlers", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const { unmount } = renderHook(() => useDragDropPrevention());
    const dragover = addSpy.mock.calls.find(([type]) => type === "dragover")?.[1];
    const drop = addSpy.mock.calls.find(([type]) => type === "drop")?.[1];

    expect(dragover).toEqual(expect.any(Function));
    expect(drop).toEqual(expect.any(Function));
    unmount();
    expect(removeSpy).toHaveBeenCalledWith("dragover", dragover);
    expect(removeSpy).toHaveBeenCalledWith("drop", drop);
  });
});
```

- [ ] **Step 2: Run tests and reproduce duplicate ownership**

Run: `cd frontend && npm run test -- --run src/pages/chat/hooks/useDragHandlers.test.tsx src/pages/chat/hooks/useDragDropPrevention.test.tsx`

Expected: `useDragHandlers` ownership test FAIL because it registers window listeners.

- [ ] **Step 3: Remove the global effect from local handlers**

Replace `useDragHandlers.ts` with:

```ts
type DragHandlers = {
  onComposerDragEnter: (evt: React.DragEvent<HTMLElement>) => void;
  onComposerDragOver: (evt: React.DragEvent<HTMLElement>) => void;
  onComposerDragLeave: (evt: React.DragEvent<HTMLElement>) => void;
};

export function useDragHandlers(setComposerDropActive: (active: boolean) => void): DragHandlers {
  return {
    onComposerDragEnter: (evt) => {
      evt.preventDefault();
      evt.stopPropagation();
      setComposerDropActive(true);
    },
    onComposerDragOver: (evt) => {
      evt.preventDefault();
      evt.stopPropagation();
      setComposerDropActive(true);
    },
    onComposerDragLeave: (evt) => {
      evt.preventDefault();
      evt.stopPropagation();
      setComposerDropActive(false);
    },
  };
}
```

- [ ] **Step 4: Run drag tests and verify source ownership**

Run: `cd frontend && npm run test -- --run src/pages/chat/hooks/useDragHandlers.test.tsx src/pages/chat/hooks/useDragDropPrevention.test.tsx`

Expected: both tests PASS.

Run: `cd frontend && rg 'addEventListener\("(dragover|drop)"' src/pages/chat`

Expected: matches only `useDragDropPrevention.ts` and its test.

- [ ] **Step 5: Commit drag ownership**

```bash
git add frontend/src/pages/chat/hooks/useDragHandlers.ts frontend/src/pages/chat/hooks/useDragHandlers.test.tsx frontend/src/pages/chat/hooks/useDragDropPrevention.test.tsx
git commit -m "fix: centralize chat drag prevention"
```

### Task 5: Verify Runtime Stability and Visual Compatibility

**Files:**
- Verify only; do not update visual snapshots unless a product-visible change was separately approved.

**Interfaces:**
- Consumes: Tasks 1–4 plus the quality-baseline plan, because `.test.tsx` discovery must be active.
- Produces: evidence that runtime fixes preserve build output and all 17 approved visual snapshots.

- [ ] **Step 1: Run the complete Chat hook group**

Run: `cd frontend && npm run test -- --run src/pages/chat/hooks`

Expected: all hook tests PASS, including fake-timer and jsdom cases.

- [ ] **Step 2: Run static and unit gates**

Run:

```bash
cd frontend
npm run type-check
npm run lint
npm run test -- --run
npm run build
```

Expected: all commands PASS.

- [ ] **Step 3: Run the approved visual suite**

Run: `cd frontend && npm run test:visual`

Expected: 17/17 PASS. Do not run the snapshot update command.

- [ ] **Step 4: Check duplicate ownership and patch hygiene**

Run:

```bash
cd frontend
rg "useAutoScroll" src/pages
rg 'addEventListener\("(dragover|drop)"' src/pages/chat
cd ..
git diff --check
git status --short
```

Expected: auto-scroll is owned only by `ChatMessages`; global drag listeners are owned only by `useDragDropPrevention`; no unrelated file is staged.

- [ ] **Step 5: Report verification without an empty commit**

Attach exact command results, unit count, build status, and visual result to the implementation handoff. If any gate fails, keep its task open and diagnose before claiming completion.
