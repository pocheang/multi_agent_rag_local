import type { SessionMessage } from "../../../types/api";
import { EMPTY_METADATA } from "../constants";

/**
 * 判断是否为中止错误
 */
export function isAbortError(e: unknown, streamStopped: boolean): boolean {
  const rawError = e instanceof Error && e.message ? e.message : "request aborted";
  return (
    streamStopped ||
    (e instanceof DOMException && e.name === "AbortError") ||
    String(rawError).toLowerCase().includes("abort")
  );
}

/**
 * 创建初始流式消息（用户消息 + 空的助手消息）
 */
export function createInitialStreamMessages(question: string): SessionMessage[] {
  return [
    { message_id: `local-user-${Date.now()}`, role: "user", content: question },
    {
      message_id: "local-assistant-stream",
      role: "assistant",
      content: "",
      metadata: { ...EMPTY_METADATA }
    },
  ];
}
