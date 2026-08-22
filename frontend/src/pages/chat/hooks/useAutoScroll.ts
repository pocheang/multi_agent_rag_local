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

  useEffect(() => {
    if (!enabled || !ref.current) return;

    // Only scroll if new messages were added
    if (messages.length > prevLengthRef.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }

    prevLengthRef.current = messages.length;
  }, [messages, ref, enabled]);

  return ref;
}
