import type { SessionMessage } from "../../../types/api";
import { EMPTY_METADATA } from "../constants";

/**
 * 解析流式请求错误响应
 */
export function parseStreamError(raw: string): string {
  if (!raw) return "Stream request failed";
  try {
    const parsed: unknown = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      const detail = (parsed as Record<string, unknown>).detail;
      if (typeof detail === "string" && detail.trim()) return detail.trim();
      if (Array.isArray(detail)) {
        const first = detail.find((item): item is Record<string, unknown> => (
          !!item && typeof item === "object" && !Array.isArray(item)
        ));
        if (first && typeof first.msg === "string" && first.msg.trim()) {
          return `Invalid request: ${first.msg.trim()}`;
        }
        return "Invalid request";
      }
    }
    return "Stream request failed";
  } catch {
    return raw;
  }
}

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
 * 判断是否为网络错误
 */
export function isNetworkError(errorText: string): boolean {
  const lowered = String(errorText).toLowerCase();
  return (
    lowered.includes("networkerror") ||
    lowered.includes("failed to fetch") ||
    lowered.includes("network error")
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
