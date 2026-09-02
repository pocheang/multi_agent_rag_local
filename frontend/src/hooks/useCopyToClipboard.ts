import { useState } from "react";

export function useCopyToClipboard(duration: number = 2000) {
  const [copied, setCopied] = useState(false);

  const copy = async (text: string): Promise<boolean> => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), duration);
      return true;
    } catch (err) {
      console.error("Failed to copy to clipboard:", err);
      setCopied(false);
      return false;
    }
  };

  return { copied, copy };
}
