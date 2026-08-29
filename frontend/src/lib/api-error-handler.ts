import { ApiError } from "@/lib/api";

/**
 * Shared 401-aware API error handler. Chat and admin previously each
 * implemented their own version with diverging behavior (chat notified the
 * user before logging out; admin logged out silently with no feedback at
 * all). This factory keeps the shared "401 -> notify, then log out" policy
 * while letting each caller supply its own display mechanism (toast vs
 * inline status text).
 */
export function createApiErrorHandler(options: {
  onLogout: () => Promise<void> | void;
  onError: (message: string) => void;
  sessionExpiredMessage: string;
}) {
  const { onLogout, onError, sessionExpiredMessage } = options;
  return async (e: unknown, fallback: string) => {
    if (e instanceof ApiError && e.status === 401) {
      onError(sessionExpiredMessage);
      await onLogout();
      return;
    }
    const msg = e instanceof Error ? e.message : fallback;
    onError(msg);
  };
}
