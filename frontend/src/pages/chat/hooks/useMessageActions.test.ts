// @vitest-environment jsdom

import { StrictMode, createElement } from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import type { SessionMessage, SessionSummary } from "@/types/api";

const appApi = vi.hoisted(() => ({
  sessionDetail: vi.fn(),
  streamQuery: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ appApi }));

import { useMessageActions } from "./useMessageActions";

beforeAll(() => {
  const reactTestGlobal = globalThis as typeof globalThis & {
    IS_REACT_ACT_ENVIRONMENT?: boolean;
  };
  reactTestGlobal.IS_REACT_ACT_ENVIRONMENT = true;
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((fulfill) => {
    resolve = fulfill;
  });
  return { promise, resolve };
}

function completedStreamResponse(): Response {
  const event = {
    version: "1",
    stage: "complete",
    status: "completed",
    duration_ms: 3,
    message: "done",
    metadata: [{ key: "content", value: "late answer" }],
    occurred_at: "2026-08-11T00:00:00Z",
  };
  return new Response(`data: ${JSON.stringify(event)}\n\n`);
}

afterEach(() => {
  vi.clearAllMocks();
  document.body.replaceChildren();
});

describe("useMessageActions lifecycle", () => {
  it("starts after StrictMode effect replay and ignores a late stream after unmount", async () => {
    const stream = deferred<Response>();
    appApi.streamQuery.mockReturnValue(stream.promise);
    appApi.sessionDetail.mockResolvedValue({ messages: [] });

    let createSessionCalls = 0;
    let createSessionSignal: AbortSignal | null = null;
    const actions = {
      notify: () => undefined,
      handleApiError: async () => undefined,
      createSession: async (signal?: AbortSignal) => {
        createSessionCalls += 1;
        createSessionSignal = signal ?? null;
        return "session-1";
      },
      editMessage: async () => undefined,
      removeMessage: async () => undefined,
      refreshSessions: async (): Promise<SessionSummary[]> => [],
    };
    let messages: SessionMessage[] = [];
    let messageUpdates = 0;
    let statusUpdates = 0;
    let sendingUpdates = 0;
    let hook: ReturnType<typeof useMessageActions> | null = null;

    function Harness() {
      hook = useMessageActions({
        currentSessionId: null,
        actions,
        setRunStatus: () => {
          statusUpdates += 1;
        },
        setMessages: (update) => {
          messages = typeof update === "function" ? update(messages) : update;
          messageUpdates += 1;
        },
        setIsSending: () => {
          sendingUpdates += 1;
        },
        setQuestion: () => undefined,
      });
      return null;
    }

    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);
    await act(async () => {
      root.render(createElement(StrictMode, null, createElement(Harness)));
    });

    let askPromise: Promise<void> | null = null;
    await act(async () => {
      askPromise = hook!.ask({
        question: "StrictMode question",
        isSending: false,
        useWeb: false,
        useReasoning: false,
        agentClassHint: "",
        retrievalStrategy: "advanced",
        pipelineProfile: "standard",
      });
      await Promise.resolve();
    });

    expect(createSessionCalls).toBe(1);
    expect(createSessionSignal).not.toBeNull();
    expect(appApi.streamQuery).toHaveBeenCalledOnce();
    const queryInput: unknown = appApi.streamQuery.mock.calls[0]?.[0];
    expect(queryInput).toMatchObject({ signal: expect.any(AbortSignal) });
    const querySignal = (queryInput as { signal: AbortSignal }).signal;
    expect(querySignal).toBe(createSessionSignal);

    await act(async () => {
      root.unmount();
    });
    expect(querySignal.aborted).toBe(true);
    const updatesAtUnmount = { messageUpdates, statusUpdates, sendingUpdates };

    stream.resolve(completedStreamResponse());
    await act(async () => {
      await askPromise;
    });

    expect({ messageUpdates, statusUpdates, sendingUpdates }).toEqual(updatesAtUnmount);
    expect(messages.some((message) => message.content === "late answer")).toBe(false);
    expect(appApi.sessionDetail).not.toHaveBeenCalled();
  });
});
