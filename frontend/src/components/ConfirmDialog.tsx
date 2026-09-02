import { useEffect, useId } from "react";
import { useTranslation } from "react-i18next";

type Props = {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isDanger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmText,
  cancelText,
  isDanger = false,
  onConfirm,
  onCancel,
}: Props) {
  const { t } = useTranslation();
  const titleId = useId();

  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onCancel();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  return (
    // The backdrop is scenery, not a control: role="presentation" says so, and
    // dismissing on a click that landed on the backdrop itself replaces the
    // inner stopPropagation handler that used to exist only to undo this one.
    // Escape is wired above and is the keyboard route.
    <div
      className="confirm-dialog-overlay"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="confirm-dialog-header">
          <h3 className="confirm-dialog-title" id={titleId}>{title}</h3>
        </div>
        <div className="confirm-dialog-body">
          <p className="confirm-dialog-message">{message}</p>
        </div>
        <div className="confirm-dialog-footer">
          <button
            type="button"
            className="confirm-dialog-btn confirm-dialog-btn-cancel"
            onClick={onCancel}
          >
            {cancelText || t("common.cancel")}
          </button>
          <button
            type="button"
            className={`confirm-dialog-btn confirm-dialog-btn-confirm ${isDanger ? "danger" : ""}`}
            onClick={onConfirm}
            autoFocus
          >
            {confirmText || t("common.confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}
