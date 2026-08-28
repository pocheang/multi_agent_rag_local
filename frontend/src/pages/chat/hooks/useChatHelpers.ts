import { useCallback } from "react";
import type { IndexedFileSummary, PromptTemplate } from "@/types/api";
import type { AgentClassHint } from "@/pages/chat/constants";
import { isMobile } from "@/pages/chat/constants";
import { useChatStore } from "@/stores/useChatStore";

interface ChatActions {
  notify: (message: string, type: "success" | "info" | "warn" | "error") => void;
  deleteDocument: (item: IndexedFileSummary, removeFile: boolean) => Promise<void>;
  reindexDocument: (item: IndexedFileSummary) => Promise<void>;
  savePrompt: (title: string, content: string, editingId: string | null) => Promise<void>;
  checkPrompt: (title: string, content: string, useReasoning: boolean) => Promise<void>;
  deletePrompt: (item: PromptTemplate, editingId: string | null) => Promise<void>;
}

interface UseChatHelpersParams {
  canUploadAndManageDocs: boolean;
  pdfDocuments: IndexedFileSummary[];
  pdfTargetFile: string;
  setSidebarOpen: (open: boolean) => void;
  setAgentClassHint: (hint: AgentClassHint) => void;
  setQuestion: (question: string) => void;
  questionRef: React.RefObject<HTMLTextAreaElement>;
  actions: ChatActions;
}

export function useChatHelpers({
  canUploadAndManageDocs,
  pdfDocuments,
  pdfTargetFile,
  setSidebarOpen,
  setAgentClassHint,
  setQuestion,
  questionRef,
  actions,
}: UseChatHelpersParams) {
  const closeSidebar = useCallback(() => {
    if (isMobile()) setSidebarOpen(false);
  }, [setSidebarOpen]);

  const switchAgentMode = useCallback(
    (next: AgentClassHint) => {
      setAgentClassHint(next);
      actions.notify(`Mode switched to ${next || "auto"}`, "success");
    },
    [setAgentClassHint, actions]
  );

  const draftPdfQuestion = useCallback(() => {
    if (!pdfDocuments.length) {
      actions.notify("No PDF/image docs available. Upload first.", "warn");
      return;
    }
    const target = pdfTargetFile || pdfDocuments[0]?.filename || "";
    if (!target) return;
    setAgentClassHint("pdf_text");
    setQuestion(`Read "${target}" and provide key points, major risks, and supporting evidence.`);
    questionRef.current?.focus();
    actions.notify("Drafted a PDF-focused question.", "success");
  }, [pdfDocuments, pdfTargetFile, setAgentClassHint, setQuestion, questionRef, actions]);

  const deleteDocument = useCallback(
    async (item: IndexedFileSummary, removeFile: boolean) => {
      if (!canUploadAndManageDocs) {
        actions.notify("No document management permission", "warn");
        return;
      }
      await actions.deleteDocument(item, removeFile);
    },
    [canUploadAndManageDocs, actions]
  );

  const reindexDocument = useCallback(
    async (item: IndexedFileSummary) => {
      if (!canUploadAndManageDocs) {
        actions.notify("No document management permission", "warn");
        return;
      }
      await actions.reindexDocument(item);
    },
    [canUploadAndManageDocs, actions]
  );

  const savePrompt = useCallback(async () => {
    const { promptTitle, promptContent, editingPromptId } = useChatStore.getState();
    await actions.savePrompt(promptTitle, promptContent, editingPromptId);
  }, [actions]);

  const checkPrompt = useCallback(async () => {
    const { promptTitle, promptContent } = useChatStore.getState();
    await actions.checkPrompt(promptTitle, promptContent, true);
  }, [actions]);

  const deletePrompt = useCallback(
    async (item: PromptTemplate) => {
      const { editingPromptId } = useChatStore.getState();
      await actions.deletePrompt(item, editingPromptId);
    },
    [actions]
  );

  return {
    closeSidebar,
    switchAgentMode,
    draftPdfQuestion,
    deleteDocument,
    reindexDocument,
    savePrompt,
    checkPrompt,
    deletePrompt,
  };
}

