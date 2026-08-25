const THEME_KEY = "theme_preference";

export function applyLightTheme() {
  document.documentElement.setAttribute("data-theme", "light");

  try {
    localStorage.removeItem(THEME_KEY);
  } catch {
    // Storage can be unavailable in privacy-restricted or sandboxed contexts.
  }
}

