import { useEffect } from "react";

interface UseAutoRefreshOptions {
  refreshSessions: (showLoading?: boolean, silent?: boolean) => Promise<unknown>;
  refreshDocuments: (silent?: boolean) => Promise<void>;
  refreshPrompts: (silent?: boolean) => Promise<void>;
}

export function useAutoRefresh({
  refreshSessions,
  refreshDocuments,
  refreshPrompts,
}: UseAutoRefreshOptions) {
  useEffect(() => {
    const timer = window.setInterval(() => {
      void refreshSessions(false, true);
      void refreshDocuments(true);
      void refreshPrompts(true);
    }, 25000);

    return () => window.clearInterval(timer);
  }, [refreshSessions, refreshDocuments, refreshPrompts]);
}
