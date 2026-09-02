import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import type { SessionMessage } from "@/types/api";

interface UseAutoScrollOptions {
  ref: RefObject<HTMLDivElement>;
  messages: SessionMessage[];
  enabled?: boolean;
}

export function useAutoScroll({ ref, messages, enabled = true }: UseAutoScrollOptions) {
  const prevLengthRef = useRef(messages.length);
  const prevLastContentRef = useRef(messages[messages.length - 1]?.content ?? "");

  useEffect(() => {
    if (!enabled || !ref.current) return;

    const lastMessage = messages[messages.length - 1];
    const lastContent = lastMessage?.content ?? "";
    // Scroll on new messages, and also when the last message's content changes
    // in place -- e.g. the streaming placeholder being replaced by the final
    // answer, which doesn't change messages.length.
    if (messages.length > prevLengthRef.current || lastContent !== prevLastContentRef.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }

    prevLengthRef.current = messages.length;
    prevLastContentRef.current = lastContent;
  }, [messages, ref, enabled]);

  return ref;
}
