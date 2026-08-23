import { getThemeIcon } from "@/lib/theme";

interface ThemeToggleProps {
  themeLabel: string;
  onThemeToggle: () => void;
  className?: string;
}

export function ThemeToggle({ themeLabel, onThemeToggle, className = "" }: ThemeToggleProps) {
  const themeIcon = getThemeIcon(themeLabel);

  return (
    <button
      type="button"
      className={`tw:inline-flex tw:items-center tw:gap-2 tw:whitespace-nowrap tw:cursor-pointer tw:px-4 tw:py-2 tw:rounded-lg tw:border tw:border-[rgba(220,228,242,0.9)] tw:bg-[rgba(255,255,255,0.94)] tw:text-[#2d3748] tw:text-sm tw:font-medium tw:transition-all tw:duration-200 tw:z-[var(--z-fixed)] hover:tw:bg-[#f7fafc] hover:tw:border-[#3b66e0] hover:tw:-translate-y-px hover:tw:shadow-[0_2px_8px_rgba(0,0,0,0.1)] active:tw:translate-y-0 tw:dark:bg-[rgba(25,30,40,0.94)] tw:dark:border-[rgba(60,70,85,0.5)] tw:dark:text-[#e2e8f0] tw:dark:hover:bg-[rgba(35,40,50,0.94)] tw:dark:hover:border-[#5a8ff5] max-[768px]:tw:px-3 max-[768px]:tw:py-1.5 max-[768px]:tw:text-[0.8125rem] ${className}`}
      onClick={onThemeToggle}
      aria-label={themeLabel}
      title={themeLabel}
    >
      {themeIcon} {themeLabel}
    </button>
  );
}
