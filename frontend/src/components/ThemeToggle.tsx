import "@/styles/components/theme-toggle.css";
import { getThemeIcon } from "@/lib/theme";

interface ThemeToggleProps {
  themeLabel: string;
  onThemeToggle: () => void;
  className?: string;
}

export function ThemeToggle({ themeLabel, onThemeToggle, className = "theme-toggle" }: ThemeToggleProps) {
  const themeIcon = getThemeIcon(themeLabel);

  return (
    <button
      type="button"
      className={className}
      onClick={onThemeToggle}
      aria-label={themeLabel}
      title={themeLabel}
    >
      {themeIcon} {themeLabel}
    </button>
  );
}
