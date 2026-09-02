import { useTranslation } from "react-i18next";
import type React from "react";
import type { IndexedFileSummary } from "@/types/api";
import type { UserIdentity } from "@/types/auth";
import { DocumentItem } from "./DocumentItem";

const PDF_FILE_RE = /\.(pdf|png|jpe?g|bmp|tiff?|webp)$/i;

type Props = {
  documents: IndexedFileSummary[];
  docsLoading: boolean;
  uploading: boolean;
  uploadInfo: string;
  uploadProgress: number;
  uploadProgressText: string;
  uploadVisibility: "private" | "public";
  docDropActive: boolean;
  canUploadAndManageDocs: boolean;
  isAdmin: boolean;
  user: UserIdentity | null;
  fileInputRef: React.RefObject<HTMLInputElement>;
  onRefreshDocuments: () => Promise<void>;
  onUploadVisibilityChange: (visibility: "private" | "public") => void;
  onMainUploadChange: (evt: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  onDocsDrop: (evt: React.DragEvent<HTMLDivElement>) => Promise<void>;
  onDocDropActiveChange: (active: boolean) => void;
  onReindexDocument: (doc: IndexedFileSummary) => Promise<void>;
  onDeleteDocument: (doc: IndexedFileSummary, removeFile: boolean) => Promise<void>;
};

export function DocumentsPanel({
  documents,
  docsLoading,
  uploading,
  uploadInfo,
  uploadProgress,
  uploadProgressText,
  uploadVisibility,
  docDropActive,
  canUploadAndManageDocs,
  isAdmin,
  user,
  fileInputRef,
  onRefreshDocuments,
  onUploadVisibilityChange,
  onMainUploadChange,
  onDocsDrop,
  onDocDropActiveChange,
  onReindexDocument,
  onDeleteDocument,
}: Props) {
  const { t } = useTranslation();
  const pdfDocuments = documents.filter((doc) => PDF_FILE_RE.test(doc.filename || ""));
  const nonPdfDocuments = documents.filter((doc) => !PDF_FILE_RE.test(doc.filename || ""));

  return (
    <section className="panel">
      <div className="section-head">
        <strong>{t("components.workbench.documents")}</strong>
        <button type="button" className="secondary tiny-btn" onClick={() => void onRefreshDocuments()}>
          {t("components.workbench.refresh")}
        </button>
      </div>

      {canUploadAndManageDocs && (
        <div className="upload-box">
          {isAdmin && (
            <select
              value={uploadVisibility}
              onChange={(event) => onUploadVisibilityChange((event.target.value as "private" | "public") || "private")}
            >
              <option value="private">{t("components.workbench.private")}</option>
              <option value="public">{t("components.workbench.public")}</option>
            </select>
          )}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={(event) => void onMainUploadChange(event)}
            accept=".md,.txt,.pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp"
          />
          <div className="muted">
            {uploading ? t("components.workbench.uploading") : t("components.workbench.uploadSupport")}
          </div>
          {uploadInfo && <div className="hint">{uploadInfo}</div>}
          {(uploading || uploadProgress > 0) && (
            <div className="progress-wrap">
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${Math.round(uploadProgress)}%` }} />
              </div>
              <div className="progress-text">
                {uploadProgressText || t("components.workbench.uploadProgress", { progress: Math.round(uploadProgress) })}
              </div>
            </div>
          )}
        </div>
      )}

      {canUploadAndManageDocs && (
        <div
          className={`dropzone ${docDropActive ? "dragover" : ""}`}
          onDragEnter={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onDocDropActiveChange(true);
          }}
          onDragOver={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onDocDropActiveChange(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onDocDropActiveChange(false);
          }}
          onDrop={(event) => void onDocsDrop(event)}
        >
          {t("components.workbench.dropDocs")}
        </div>
      )}

      {docsLoading && <div className="skeleton-list" />}
      {!docsLoading && documents.length === 0 && <div className="muted">{t("components.workbench.noIndexedDocuments")}</div>}
      {!docsLoading && pdfDocuments.length > 0 && (
        <div className="doc-subtitle">{t("components.workbench.pdfImageDocs", { count: pdfDocuments.length })}</div>
      )}
      {!docsLoading &&
        pdfDocuments.map((doc) => (
          <DocumentItem
            key={`${doc.filename}-${doc.source}`}
            doc={doc}
            canUploadAndManageDocs={canUploadAndManageDocs}
            isAdmin={isAdmin}
            currentUserId={user?.user_id}
            onReindexDocument={onReindexDocument}
            onDeleteDocument={onDeleteDocument}
          />
        ))}
      {!docsLoading && nonPdfDocuments.length > 0 && (
        <div className="doc-subtitle">{t("components.workbench.otherDocs", { count: nonPdfDocuments.length })}</div>
      )}
      {!docsLoading &&
        nonPdfDocuments.map((doc) => (
          <DocumentItem
            key={`${doc.filename}-${doc.source}`}
            doc={doc}
            canUploadAndManageDocs={canUploadAndManageDocs}
            isAdmin={isAdmin}
            currentUserId={user?.user_id}
            onReindexDocument={onReindexDocument}
            onDeleteDocument={onDeleteDocument}
          />
        ))}
    </section>
  );
}
