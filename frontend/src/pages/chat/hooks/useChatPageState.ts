import { useRef } from "react";
import { useChatStore } from "@/stores/useChatStore";

export function useChatPageState() {
  const store = useChatStore();

  // DOM Refs preserved locally
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatUploadInputRef = useRef<HTMLInputElement | null>(null);
  const questionRef = useRef<HTMLTextAreaElement | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);

  return {
    ...store,
    fileInputRef,
    chatUploadInputRef,
    questionRef,
    chatScrollRef,
  };
}
