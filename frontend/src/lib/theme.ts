const THEME_KEY = "theme_preference";
export type ThemeMode = "auto" | "light" | "dark";

export function getSavedTheme(): ThemeMode {
  const raw = localStorage.getItem(THEME_KEY);
  if (raw === "light" || raw === "dark" || raw === "auto") return raw;
  return "auto";
}

export function saveTheme(mode: ThemeMode) {
  localStorage.setItem(THEME_KEY, mode);
}

export function applyTheme(mode: ThemeMode) {
  if (mode === "auto") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.setAttribute("data-theme", mode);
  }
}

export function nextTheme(mode: ThemeMode): ThemeMode {
  if (mode === "auto") return "dark";
  if (mode === "dark") return "light";
  return "auto";
}
