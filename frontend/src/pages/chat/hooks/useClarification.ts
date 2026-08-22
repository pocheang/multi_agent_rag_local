import { useState } from "react";
import type { ClarificationResponse } from "@/types/api";
import { clarificationApi } from "@/services/api/chat";
import { useTranslation } from "react-i18next";

interface UseClarificationOptions {
  currentSessionId: string | null;
  onClarificationComplete: (question: string) => Promise<void>;
  onNotify: (message: string, type: "success" | "error" | "info") => void;
}

export function useClarification({
  currentSessionId,
  onClarificationComplete,
  onNotify,
}: UseClarificationOptions) {
  const { t } = useTranslation();
  const [clarification, setClarification] = useState<ClarificationResponse | null>(null);
  const [isClarifying, setIsClarifying] = useState(false);
  const [originalQuestion, setOriginalQuestion] = useState<string>("");

  const handleClarificationAnswer = async (fieldName: string, answer: string) => {
    if (!clarification || !currentSessionId || !originalQuestion) return;

    setIsClarifying(true);

    try {
      const response = await clarificationApi.checkClarification({
        question: originalQuestion,
        session_id: currentSessionId,
        field_name: fieldName,
        answer: answer,
      });

      if (response.action === "NEED_CLARIFICATION") {
        // Continue clarification
        setClarification(response);
      } else {
        // Information is sufficient, execute query
        setClarification(null);
        setOriginalQuestion("");
        await onClarificationComplete(originalQuestion);
      }
    } catch (error) {
      console.error("Clarification answer failed:", error);
      onNotify(t("chat.clarificationError") || "Failed to submit clarification", "error");
    } finally {
      setIsClarifying(false);
    }
  };

  const handleClarificationSkip = async () => {
    if (!currentSessionId || !originalQuestion) return;

    try {
      await clarificationApi.resetClarification(currentSessionId);
      setClarification(null);
      setOriginalQuestion("");
      await onClarificationComplete(originalQuestion);
    } catch (error) {
      console.error("Skip clarification failed:", error);
      onNotify(t("chat.skipClarificationError") || "Failed to skip clarification", "error");
    }
  };

  const checkAndInitiateClarification = async (
    questionText: string,
    sessionId: string
  ): Promise<boolean> => {
    try {
      const response = await clarificationApi.checkClarification({
        question: questionText,
        session_id: sessionId,
      });

      if (response.action === "NEED_CLARIFICATION") {
        setClarification(response);
        setOriginalQuestion(questionText);
        return true; // Needs clarification
      }

      return false; // No clarification needed
    } catch (error: unknown) {
      // Check if it's an authentication or permission error
      const apiError = error as { response?: { status?: number }; status?: number };
      const status = apiError?.response?.status || apiError?.status;

      if (status === 403 || status === 401) {
        onNotify(
          t("chat.clarificationAuthError") || "Authentication required for advanced features",
          "error"
        );
        throw error; // Re-throw auth errors
      }

      // Other errors: fallback to direct query
      console.warn("Clarification service unavailable, falling back to direct query");
      return false; // Proceed without clarification
    }
  };

  return {
    clarification,
    isClarifying,
    originalQuestion,
    handleClarificationAnswer,
    handleClarificationSkip,
    checkAndInitiateClarification,
  };
}
