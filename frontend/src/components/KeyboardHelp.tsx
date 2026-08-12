import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import "@/styles/components/keyboard-help.css";

interface Shortcut {
  keys: string[];
  description: string;
  category: string;
}

export function KeyboardHelp() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const shortcuts = useMemo<Shortcut[]>(
    () => [
      { keys: ["Ctrl", "Enter"], description: t("components.keyboard.shortcuts.send"), category: t("components.keyboard.categories.message") },
      { keys: ["Shift", "Enter"], description: t("components.keyboard.shortcuts.newline"), category: t("components.keyboard.categories.message") },
      { keys: ["Esc"], description: t("components.keyboard.shortcuts.clear"), category: t("components.keyboard.categories.message") },
      { keys: ["Ctrl", "K"], description: t("components.keyboard.shortcuts.focusSearch"), category: t("components.keyboard.categories.navigation") },
      { keys: ["Ctrl", "N"], description: t("components.keyboard.shortcuts.newSession"), category: t("components.keyboard.categories.navigation") },
      { keys: ["Ctrl", "B"], description: t("components.keyboard.shortcuts.toggleSidebar"), category: t("components.keyboard.categories.navigation") },
      { keys: ["Ctrl", "W"], description: t("components.keyboard.shortcuts.toggleWeb"), category: t("components.keyboard.categories.options") },
      { keys: ["Ctrl", "R"], description: t("components.keyboard.shortcuts.toggleReasoning"), category: t("components.keyboard.categories.options") },
      { keys: ["?"], description: t("components.keyboard.shortcuts.showHelp"), category: t("components.keyboard.categories.other") },
      { keys: ["Ctrl", "/"], description: t("components.keyboard.shortcuts.showHelp"), category: t("components.keyboard.categories.other") },
    ],
    [t],
  );

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "?" && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
        const target = event.target as HTMLElement;
        if (target.tagName !== "INPUT" && target.tagName !== "TEXTAREA") {
          event.preventDefault();
          setIsOpen(true);
        }
      } else if ((event.ctrlKey || event.metaKey) && event.key === "/") {
        event.preventDefault();
        setIsOpen(true);
      }

      if (event.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  const groupedShortcuts = useMemo(() => {
    return shortcuts.reduce((acc, shortcut) => {
      if (!acc[shortcut.category]) acc[shortcut.category] = [];
      acc[shortcut.category].push(shortcut);
      return acc;
    }, {} as Record<string, Shortcut[]>);
  }, [shortcuts]);

  if (!isOpen) return null;

  return (
    <>
      <div className="keyboard-help-backdrop" onClick={() => setIsOpen(false)} aria-hidden="true" />
      <div className="keyboard-help-modal" role="dialog" aria-modal="true" aria-labelledby="keyboard-help-title">
        <div className="keyboard-help-header">
          <h2 id="keyboard-help-title">{t("components.keyboard.title")}</h2>
          <button
            type="button"
            className="keyboard-help-close"
            onClick={() => setIsOpen(false)}
            aria-label={t("components.keyboard.close")}
          >
            ×
          </button>
        </div>

        <div className="keyboard-help-content">
          {Object.entries(groupedShortcuts).map(([category, items]) => (
            <div key={category} className="keyboard-help-section">
              <h3 className="keyboard-help-category">{category}</h3>
              <div className="keyboard-help-list">
                {items.map((shortcut) => (
                  <div key={`${category}-${shortcut.keys.join("-")}`} className="keyboard-help-item">
                    <div className="keyboard-help-keys">
                      {shortcut.keys.map((key, index) => (
                        <span key={key}>
                          <kbd className="keyboard-key">{key}</kbd>
                          {index < shortcut.keys.length - 1 && <span className="keyboard-plus">+</span>}
                        </span>
                      ))}
                    </div>
                    <span className="keyboard-help-description">{shortcut.description}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="keyboard-help-footer">
          <p className="keyboard-help-hint">{t("components.keyboard.footer")}</p>
        </div>
      </div>
    </>
  );
}
