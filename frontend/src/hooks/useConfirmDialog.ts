import { useState, useCallback } from "react";

export interface ConfirmDialogOptions {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  onConfirm: () => void | Promise<void>;
  onCancel?: () => void;
}

export function useConfirmDialog() {
  const [isOpen, setIsOpen] = useState(false);
  const [options, setOptions] = useState<ConfirmDialogOptions | null>(null);

  const confirm = useCallback((opts: ConfirmDialogOptions) => {
    setOptions(opts);
    setIsOpen(true);
  }, []);

  const handleConfirm = useCallback(async () => {
    if (options?.onConfirm) {
      await options.onConfirm();
    }
    setIsOpen(false);
    setOptions(null);
  }, [options]);

  const handleCancel = useCallback(() => {
    options?.onCancel?.();
    setIsOpen(false);
    setOptions(null);
  }, [options]);

  return {
    isOpen,
    options,
    confirm,
    handleConfirm,
    handleCancel,
  };
}
