import type { ConfirmDialogOptions } from "@/hooks/useConfirmDialog";
import { useTranslation } from "react-i18next";

interface ConfirmDialogProps {
  isOpen: boolean;
  options: ConfirmDialogOptions | null;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ isOpen, options, onConfirm, onCancel }: ConfirmDialogProps) {
  const { t } = useTranslation();
  if (!isOpen || !options) return null;

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        {options.title && <h3>{options.title}</h3>}
        <p>{options.message}</p>
        <div className="modal-actions">
          <button onClick={onCancel} className="btn-secondary">
            {options.cancelText || t("common.cancel")}
          </button>
          <button onClick={onConfirm} className="btn-danger">
            {options.confirmText || t("common.confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}
