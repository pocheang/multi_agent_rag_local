import { useCallback, useRef, useState } from "react";

export interface PromptDialogOptions {
  title?: string;
  message: string;
  defaultValue?: string;
  placeholder?: string;
  confirmText?: string;
  cancelText?: string;
  multiline?: boolean;
  inputType?: "text" | "password";
}

export function usePromptDialog() {
  const [isOpen, setIsOpen] = useState(false);
  const [options, setOptions] = useState<PromptDialogOptions | null>(null);
  const resolverRef = useRef<((value: string | null) => void) | null>(null);

  const promptInput = useCallback((opts: PromptDialogOptions): Promise<string | null> => {
    setOptions(opts);
    setIsOpen(true);
    return new Promise<string | null>((resolve) => {
      resolverRef.current = resolve;
    });
  }, []);

  const handleConfirm = useCallback((value: string) => {
    setIsOpen(false);
    resolverRef.current?.(value);
    resolverRef.current = null;
  }, []);

  const handleCancel = useCallback(() => {
    setIsOpen(false);
    resolverRef.current?.(null);
    resolverRef.current = null;
  }, []);

  return {
    isOpen,
    options,
    promptInput,
    handleConfirm,
    handleCancel,
  };
}
