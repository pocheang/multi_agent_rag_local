import { useEffect } from "react";
import type { RefObject } from "react";

interface UseTextareaAutoResizeOptions {
  ref: RefObject<HTMLTextAreaElement>;
  value: string;
  maxHeight?: number;
}

export function useTextareaAutoResize({
  ref,
  value,
  maxHeight = 180,
}: UseTextareaAutoResizeOptions) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    el.style.height = "auto";
    el.style.height = `${Math.min(maxHeight, el.scrollHeight)}px`;
  }, [value, ref, maxHeight]);
}
