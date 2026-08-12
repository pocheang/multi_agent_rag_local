import { useEffect, useRef } from "react";
import { appApi } from "@/lib/api";
import type { SessionMessage, SessionSummary } from "@/types/api";
import type { PipelineProfile } from "@/types/api";
import { EMPTY_METADATA } from "@/pages/chat/constants";
import {
  isAbortError,
  parseStreamError,
  createInitialStreamMessages,
} from "./streamUtils";
import {
  createStreamEventHandlers,
  type StreamEventContext,
  type StreamMetadata,
} from "./streamEventHandlers";
import { createStreamMessageUpdater } from "./streamMessageUpdater";
import {
  consumeChatStream,
  createChatRunLifecycle,
  type ChatRunToken,
  type ExecutionEnvelopeEvent,
  type LegacyChatStreamEvent,
} from "./chatStreamAdapter";

type AgentClassHint = "" | "general" | "cybersecurity" | "artificial_intelligence" | "pdf_text";
type RetrievalStrategy = "baseline" | "advanced" | "safe";

function readStringField(event: LegacyChatStreamEvent, key: string): string {
  const value = event[key];
  return typeof value === "string" ? value : "";
}

function readExecutionMetadata(event: ExecutionEnvelopeEvent, key: string): string {
  return event.event.metadata.find((item) => item.key === key)?.value || "";
}

interface ChatActions {
  notify: (message: string, type: "success" | "info" | "warn" | "error") => void;
  handleApiError: (e: unknown, fallback: string) => Promise<void>;
  createSession: (signal?: AbortSignal) => Promise<string | null>;
  editMessage: (msg: SessionMessage, useWeb: boolean, useReasoning: boolean) => Promise<void>;
  removeMessage: (msg: SessionMessage) => Promise<void>;
  refreshSessions: (silent?: boolean, background?: boolean) => Promise<SessionSummary[]>;
}

interface UseMessageActionsParams {
  currentSessionId: string | null;
  actions: ChatActions;
  setRunStatus: (status: string) => void;
  setMessages: React.Dispatch<React.SetStateAction<SessionMessage[]>>;
  setIsSending: (sending: boolean) => void;
  setQuestion: (question: string) => void;
  onExecutionId?: (executionId: string | null) => void;
}

interface UseMessageActionsReturn {
  editMessage: (msg: SessionMessage, useWeb: boolean, useReasoning: boolean) => Promise<void>;
  removeMessage: (msg: SessionMessage) => Promise<void>;
  ensureSessionForAsk: () => Promise<string | null>;
  stopCurrentRun: (isSending: boolean) => void;
  ask: (params: {
    question: string;
    isSending: boolean;
    useWeb: boolean;
    useReasoning: boolean;
    agentClassHint: AgentClassHint;
    retrievalStrategy: RetrievalStrategy;
    pipelineProfile: PipelineProfile;
  }) => Promise<void>;
}

export function useMessageActions({
  currentSessionId,
  actions,
  setRunStatus,
  setMessages,
  setIsSending,
  setQuestion,
  onExecutionId,
}: UseMessageActionsParams): UseMessageActionsReturn {
  const streamAbortRef = useRef<AbortController | null>(null);
  const streamStoppedRef = useRef(false);
  const runLifecycleRef = useRef(createChatRunLifecycle());
  const activeRunRef = useRef<ChatRunToken | null>(null);

  useEffect(() => {
    const lifecycle = runLifecycleRef.current;
    lifecycle.mount();
    return () => {
      streamStoppedRef.current = true;
      lifecycle.dispose();
      streamAbortRef.current?.abort();
    };
  }, []);

  const editMessage = async (msg: SessionMessage, useWeb: boolean, useReasoning: boolean) => {
    if (!currentSessionId) return;
    if (msg.role === "user") setRunStatus("Re-running");
    await actions.editMessage(msg, useWeb, useReasoning);
    setRunStatus("");
  };

  const removeMessage = async (msg: SessionMessage) => {
    await actions.removeMessage(msg);
  };

  const ensureSessionForAsk = async (signal?: AbortSignal) => {
    if (currentSessionId) return currentSessionId;
    return actions.createSession(signal);
  };

  const stopCurrentRun = (isSending: boolean) => {
    if (!isSending) return;
    streamStoppedRef.current = true;
    setRunStatus("Stopping...");
    try {
      streamAbortRef.current?.abort();
    } catch {
      // ignore abort errors
    }
  };

  const ask = async ({
    question,
    isSending,
    useWeb,
    useReasoning,
    agentClassHint,
    retrievalStrategy,
    pipelineProfile,
  }: {
    question: string;
    isSending: boolean;
    useWeb: boolean;
    useReasoning: boolean;
    agentClassHint: AgentClassHint;
    retrievalStrategy: RetrievalStrategy;
    pipelineProfile: PipelineProfile;
  }) => {
    const q = question.trim();
    if (!q || isSending) return;
    const run = runLifecycleRef.current.begin();
    if (run === null) return;
    activeRunRef.current = run;
    const isRunActive = () => runLifecycleRef.current.isActive(run);
    const runAbort = new AbortController();
    streamAbortRef.current = runAbort;
    streamStoppedRef.current = false;
    if (!isRunActive()) return;
    onExecutionId?.(null);
    setIsSending(true);
    setQuestion("");
    setRunStatus("Processing");
    const sid = await ensureSessionForAsk(runAbort.signal);
    if (!sid || !isRunActive()) {
      const wasActive = isRunActive();
      if (wasActive) {
        setIsSending(false);
        setRunStatus("");
        runLifecycleRef.current.stop(run);
      }
      if (activeRunRef.current === run) activeRunRef.current = null;
      if (streamAbortRef.current === runAbort) streamAbortRef.current = null;
      return;
    }

    setMessages((prev) => [...prev, ...createInitialStreamMessages(q)]);
    const messageUpdater = createStreamMessageUpdater({ setMessages });

    if (pipelineProfile !== "standard") {
      try {
        const result = pipelineProfile === "strict_quality"
          ? await appApi.strictQuality({
              query: q,
              sessionId: sid,
              retrievalStrategy,
              agentClassHint: agentClassHint || undefined,
              enableContextTracking: true,
              signal: runAbort.signal,
            })
          : await appApi.advanced({
              query: q,
              retrievalStrategy,
              enableDecomposition: useReasoning,
              enableSelfRag: useReasoning,
              signal: runAbort.signal,
            });
        if (!isRunActive()) return;
        setMessages((prev) => prev.map((message) => (
          message.message_id === "local-assistant-stream"
            ? {
                ...message,
                content: result.answer,
                metadata: {
                  ...EMPTY_METADATA,
                  route: result.route || "",
                  retrieval_strategy: retrievalStrategy,
                  citations: result.citations,
                  quality_report: result.qualityReport,
                },
              }
            : message
        )));
      } catch (e) {
        if (!isRunActive()) return;
        if (isAbortError(e, streamStoppedRef.current)) {
          messageUpdater.replaceWithStoppedMessage("");
          actions.notify("Generation stopped", "info");
          return;
        }
        await actions.handleApiError(e, "Request failed. Please check backend/model status.");
        if (!isRunActive()) return;
        const message = e instanceof Error && e.message ? e.message : "Request failed";
        messageUpdater.replaceWithErrorMessage(message);
      } finally {
        if (isRunActive()) {
          setIsSending(false);
          setRunStatus("");
          runLifecycleRef.current.stop(run);
        }
        if (streamAbortRef.current === runAbort) streamAbortRef.current = null;
        if (activeRunRef.current === run) activeRunRef.current = null;
      }
      return;
    }

    const eventHandlers = createStreamEventHandlers();
    try {
      const runStartedAt = performance.now();
      const elapsedMs = () => Math.max(1, Math.round(performance.now() - runStartedAt));
      const res = await appApi.streamQuery({
        question: q,
        useWebFallback: useWeb,
        useReasoning,
        sessionId: sid,
        agentClassHint: agentClassHint || undefined,
        retrievalStrategy,
        signal: runAbort.signal,
      });

      if (!res.ok || !res.body) {
        const raw = await res.text();
        throw new Error(parseStreamError(raw));
      }

      let ctx: StreamEventContext = {
        answer: "",
        thoughts: [],
        meta: { ...EMPTY_METADATA } as StreamMetadata,
        executionSteps: [...(EMPTY_METADATA.execution_steps || [])],
        elapsedMs,
      };

      await consumeChatStream(res, {
        signal: runAbort.signal,
        onEvent: (event) => {
          if (!isRunActive()) return;

          if (event.type === "execution_event") {
            const executionId = readExecutionMetadata(event, "execution_id");
            if (executionId) onExecutionId?.(executionId);
            if (event.event.status === "failed") throw new Error(event.event.message || "stream error");

            const content = readExecutionMetadata(event, "content");
            const answerMode = readExecutionMetadata(event, "answer_mode");
            if (content) {
              const contentEvent = { type: "answer_chunk" as const, content };
              ctx = answerMode === "answer_reset"
                ? eventHandlers.handleAnswerResetEvent(contentEvent, ctx)
                : eventHandlers.handleAnswerChunkEvent(contentEvent, ctx);
            }

            const statusEvent: LegacyChatStreamEvent = {
              type: "status",
              message: event.event.message,
            };
            const { nextStatus, updatedCtx } = eventHandlers.handleStatusEvent(statusEvent, ctx);
            ctx = updatedCtx;
            setRunStatus(nextStatus || event.event.message);
            messageUpdater.patchStreamMessage(ctx.answer, ctx.meta);
            return;
          }

          if (event.type === "execution_started") {
            const executionId = readStringField(event, "execution_id");
            if (executionId) onExecutionId?.(executionId);
            return;
          }

          switch (event.type) {
            case "status": {
              const { nextStatus, updatedCtx } = eventHandlers.handleStatusEvent(event, ctx);
              ctx = updatedCtx;
              setRunStatus(nextStatus);
              messageUpdater.patchStreamMessage(ctx.answer, ctx.meta);
              break;
            }
            case "route":
              ctx = eventHandlers.handleRouteEvent(event, ctx);
              messageUpdater.patchStreamMessage(ctx.answer, ctx.meta);
              break;
            case "thought":
              ctx = eventHandlers.handleThoughtEvent(event, ctx);
              messageUpdater.patchStreamMessage(ctx.answer, ctx.meta);
              break;
            case "error": {
              const result = eventHandlers.handleErrorEvent(event, ctx);
              ctx = result.updatedCtx;
              messageUpdater.patchStreamMessage(ctx.answer, ctx.meta);
              throw result.error;
            }
            case "vector_result":
              ctx = eventHandlers.handleVectorResultEvent(event, ctx);
              messageUpdater.patchStreamMessage(ctx.answer, ctx.meta);
              break;
            case "graph_result":
              ctx = eventHandlers.handleGraphResultEvent(event, ctx);
              messageUpdater.patchStreamMessage(ctx.answer, ctx.meta);
              break;
            case "web_result":
              ctx = eventHandlers.handleWebResultEvent(event, ctx);
              messageUpdater.patchStreamMessage(ctx.answer, ctx.meta);
              break;
            case "answer_chunk":
              ctx = eventHandlers.handleAnswerChunkEvent(event, ctx);
              messageUpdater.patchStreamMessage(ctx.answer, ctx.meta);
              break;
            case "answer_reset":
              ctx = eventHandlers.handleAnswerResetEvent(event, ctx);
              messageUpdater.patchStreamMessage(ctx.answer, ctx.meta);
              break;
            case "done":
              ctx = eventHandlers.handleDoneEvent(event, ctx, retrievalStrategy);
              messageUpdater.patchStreamMessage(ctx.answer, ctx.meta);
              break;
            case "stream_end":
              break;
          }
        }
      });

      if (!isRunActive()) return;
      const detail = await appApi.sessionDetail(sid, runAbort.signal);
      if (!isRunActive()) return;
      messageUpdater.updateFinalMessage(detail.messages || [], ctx.meta);
    } catch (e) {
      if (!isRunActive()) return;
      if (isAbortError(e, streamStoppedRef.current)) {
        messageUpdater.replaceWithStoppedMessage("");
        actions.notify("Generation stopped", "info");
        return;
      }

      const fallback = "Request failed. Please check backend/model status.";
      await actions.handleApiError(e, fallback);
      if (!isRunActive()) return;
      const rawErrorText = e instanceof Error && e.message ? e.message : fallback;
      messageUpdater.replaceWithErrorMessage(rawErrorText);
    } finally {
      if (streamAbortRef.current === runAbort) streamAbortRef.current = null;
      streamStoppedRef.current = false;
      if (isRunActive()) {
        setIsSending(false);
        setRunStatus("");
        runLifecycleRef.current.stop(run);
      }
      if (activeRunRef.current === run) activeRunRef.current = null;
    }
  };

  return {
    editMessage,
    removeMessage,
    ensureSessionForAsk,
    stopCurrentRun,
    ask,
  };
}
