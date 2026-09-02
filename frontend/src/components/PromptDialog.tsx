import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import type React from "react";
import { useTranslation } from "react-i18next";

type Props = {
  isOpen: boolean;
  title: string;
  message: string;
  defaultValue?: string;
  placeholder?: string;
  confirmText?: string;
  cancelText?: string;
  multiline?: boolean;
  inputType?: "text" | "password";
  onConfirm: (value: string) => void;
  onCancel: () => void;
};

export function PromptDialog({
  isOpen,
  title,
  message,
  defaultValue = "",
  placeholder,
  confirmText,
  cancelText,
  multiline = false,
  inputType = "text",
  onConfirm,
  onCancel,
}: Props) {
  const { t } = useTranslation();
  const titleId = useId();
  const [value, setValue] = useState(defaultValue);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);

  useLayoutEffect(() => {
    setValue(isOpen ? defaultValue : "");
  }, [isOpen, defaultValue]);

  useEffect(() => {
    if (!isOpen) return;
    window.setTimeout(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    }, 0);
  }, [isOpen]);

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
      <div className="confirm-dialog prompt-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="confirm-dialog-header">
          <h3 className="confirm-dialog-title" id={titleId}>{title}</h3>
        </div>
        <div className="confirm-dialog-body">
          <p className="confirm-dialog-message">{message}</p>
          {multiline ? (
            <textarea
              ref={inputRef as React.RefObject<HTMLTextAreaElement>}
              className="prompt-dialog-input prompt-dialog-textarea"
              value={value}
              placeholder={placeholder}
              rows={5}
              onChange={(event) => setValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                  event.preventDefault();
                  onConfirm(value);
                }
              }}
            />
          ) : (
            <input
              ref={inputRef as React.RefObject<HTMLInputElement>}
              type={inputType}
              className="prompt-dialog-input"
              value={value}
              placeholder={placeholder}
              onChange={(event) => setValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  onConfirm(value);
                }
              }}
            />
          )}
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
            className="confirm-dialog-btn confirm-dialog-btn-confirm"
            onClick={() => onConfirm(value)}
          >
            {confirmText || t("common.confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}
