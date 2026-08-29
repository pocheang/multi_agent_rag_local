import type { Dispatch, SetStateAction } from "react";
import { useTranslation } from "react-i18next";
import { appApi } from "@/lib/api";
import type { IndexedFileSummary } from "@/types/api";

type AgentClassHint = "" | "general" | "cybersecurity" | "artificial_intelligence" | "pdf_text";

interface UseDocumentActionsParams {
  setDocuments: Dispatch<SetStateAction<IndexedFileSummary[]>>;
  setDocsLoading: Dispatch<SetStateAction<boolean>>;
  setUploading: Dispatch<SetStateAction<boolean>>;
  setUploadInfo: Dispatch<SetStateAction<string>>;
  setUploadProgress: Dispatch<SetStateAction<number>>;
  setUploadProgressText: Dispatch<SetStateAction<string>>;
  setAgentClassHint: Dispatch<SetStateAction<AgentClassHint>>;
  setError: Dispatch<SetStateAction<string>>;
  uploadVisibility: "private" | "public";
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  chatUploadInputRef: React.RefObject<HTMLInputElement | null>;
  notify: (text: string, kind?: "info" | "success" | "warn" | "error", ttl?: number) => void;
  handleApiError: (e: unknown, fallback: string) => Promise<void>;
  confirm: (opts: { message: string; title?: string; isDanger?: boolean }) => Promise<boolean>;
}

export function useDocumentActions(params: UseDocumentActionsParams) {
  const { t } = useTranslation();
  const {
    setDocuments,
    setDocsLoading,
    setUploading,
    setUploadInfo,
    setUploadProgress,
    setUploadProgressText,
    setAgentClassHint,
    setError,
    uploadVisibility,
    fileInputRef,
    chatUploadInputRef,
    notify,
    handleApiError,
    confirm,
  } = params;

  const refreshDocuments = async (silent = false) => {
    if (!silent) setDocsLoading(true);
    try {
      const rows = await appApi.documents();
      setDocuments(rows);
      setError("");
    } catch (e) {
      await handleApiError(e, t("components.workbench.loadDocumentsFailed"));
    } finally {
      if (!silent) setDocsLoading(false);
    }
  };

  const uploadFiles = async (files: File[]) => {
    if (!files.length) return;
    try {
      setUploading(true);
      setUploadProgress(0);
      setUploadProgressText(t("components.workbench.preparingUpload"));
      setUploadInfo(t("components.workbench.uploading"));
      const data = await appApi.upload(
        files,
        (percent) => {
          setUploadProgress(percent);
          setUploadProgressText(t("components.workbench.uploadProgress", { progress: Math.round(percent) }));
        },
        uploadVisibility,
      );
      setUploadProgress(100);
      setUploadProgressText(t("components.workbench.uploadComplete"));

      const uploadSummary = [];
      if (data.indexing_status === "queued") {
        uploadSummary.push(t("components.workbench.queuedForIndexing"));
      }
      if (data.duplicate_files && data.duplicate_files.length > 0) {
        uploadSummary.push(t("components.workbench.reusedFiles", { files: data.duplicate_files.join(", ") }));
      }
      uploadSummary.push(t("components.workbench.uploadedCount", { count: data.loaded_documents }));
      if (data.chunks_indexed > 0) {
        uploadSummary.push(t("components.workbench.indexedChunksCount", { count: data.chunks_indexed }));
      }
      if (data.pages_by_source && Object.keys(data.pages_by_source).length > 0) {
        const totalPages = Object.values(data.pages_by_source).reduce((a, b) => a + b, 0);
        uploadSummary.push(t("components.workbench.totalPagesCount", { count: totalPages }));
      }
      if (data.triplets_written > 0) {
        uploadSummary.push(t("components.workbench.extractedTripletsCount", { count: data.triplets_written }));
      }
      if (data.skipped_files && data.skipped_files.length > 0) {
        uploadSummary.push(t("components.workbench.skippedFiles", { files: data.skipped_files.join(", ") }));
      }

      setUploadInfo(uploadSummary.join(" | "));
      const classes = Object.values(data.assigned_agent_classes || {}).filter(Boolean);
      if (classes.length > 0) {
        const unique = Array.from(new Set(classes));
        if (unique.length === 1) setAgentClassHint((unique[0] as AgentClassHint) || "");
      }
      notify(uploadSummary.join(" | "), "success", 4000);
      await refreshDocuments();
    } catch (e) {
      setUploadInfo(
        t("components.workbench.uploadFailedReason", {
          reason: e instanceof Error ? e.message : t("components.workbench.unknownError"),
        }),
      );
      await handleApiError(e, t("components.workbench.uploadFailed"));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (chatUploadInputRef.current) chatUploadInputRef.current.value = "";
      window.setTimeout(() => {
        setUploadProgress(0);
        setUploadProgressText("");
      }, 900);
    }
  };

  const deleteDocument = async (item: IndexedFileSummary, removeFile: boolean) => {
    const verb = removeFile
      ? t("components.workbench.deleteFileAndIndexVerb")
      : t("components.workbench.deleteIndexVerb");
    const confirmed = await confirm({
      message: t("components.workbench.deleteDocConfirm", { verb, filename: item.filename }),
      isDanger: true,
    });
    if (!confirmed) return;
    try {
      const res = await appApi.documentDelete(item.filename, item.source, removeFile);
      setUploadInfo(
        `${item.filename}: chunks_removed=${res.chunks_removed}, triplets_removed=${res.triplets_removed}, file_removed=${res.file_removed}`,
      );
      notify(t("components.workbench.fileDeleted", { filename: item.filename }), "success");
      await refreshDocuments();
    } catch (e) {
      await handleApiError(e, t("components.workbench.deleteDocumentFailed"));
    }
  };

  const reindexDocument = async (item: IndexedFileSummary) => {
    try {
      const res = await appApi.documentReindex(item.filename, item.source);
      if (res.skipped) {
        const skippedSummary = t("components.workbench.reindexSkipped", {
          filename: item.filename,
          reason: res.reason || t("components.workbench.unchangedReason"),
        });
        setUploadInfo(skippedSummary);
        notify(skippedSummary, "info", 3000);
        await refreshDocuments();
        return;
      }

      const reindexSummary = [t("components.workbench.reindexComplete", { filename: item.filename })];
      if (res.chunks_indexed && res.chunks_indexed > 0) {
        reindexSummary.push(t("components.workbench.indexedChunksCount", { count: res.chunks_indexed }));
      }
      if (res.pages_by_source && Object.keys(res.pages_by_source).length > 0) {
        const totalPages = Object.values(res.pages_by_source).reduce((a, b) => a + b, 0);
        reindexSummary.push(t("components.workbench.totalPagesCount", { count: totalPages }));
      }
      if (res.triplets_written && res.triplets_written > 0) {
        reindexSummary.push(t("components.workbench.extractedTripletsCount", { count: res.triplets_written }));
      }

      setUploadInfo(reindexSummary.join(" - "));
      notify(reindexSummary.join(" - "), "success", 3000);
      await refreshDocuments();
    } catch (e) {
      await handleApiError(e, t("components.workbench.reindexDocumentFailed"));
    }
  };

  return {
    refreshDocuments,
    uploadFiles,
    deleteDocument,
    reindexDocument,
  };
}
