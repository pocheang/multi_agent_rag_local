import { useMemo } from "react";
import type { IndexedFileSummary, SessionSummary } from "@/types/api";
import type { SessionMessage } from "@/types/api";

interface UseChatInitializationOptions {
  documents: IndexedFileSummary[];
  refreshSessions: (showLoading?: boolean, silent?: boolean) => Promise<SessionSummary[]>;
  refreshDocuments: (silent?: boolean) => Promise<void>;
  refreshPrompts: (silent?: boolean) => Promise<void>;
  loadSession: (sessionId: string) => Promise<void>;
}

export function useChatInitialization({
  documents,
  refreshSessions,
  refreshDocuments,
  refreshPrompts,
  loadSession,
}: UseChatInitializationOptions) {
  // Auto-select first PDF document
  const pdfDocuments = useMemo(
    () => documents.filter((doc) => /\.(pdf|png|jpe?g|bmp|tiff?|webp)$/i.test(doc.filename)),
    [documents]
  );

  // Initialize on mount
  const initialize = async () => {
    const rows = await refreshSessions();
    await refreshDocuments();
    await refreshPrompts();
    if (rows.length > 0) {
      await loadSession(rows[0].session_id);
    }
  };

  return {
    pdfDocuments,
    initialize,
  };
}

interface SmartPromptsOptions {
  messages: SessionMessage[];
}

export function useSmartPrompts({ messages }: SmartPromptsOptions) {
  return useMemo(() => {
    // This would typically import from smartPrompts util
    // For now, return empty array as placeholder
    return [];
  }, [messages]);
}
