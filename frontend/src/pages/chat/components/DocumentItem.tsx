import type { IndexedFileSummary } from "@/types/api";
import { useTranslation } from "react-i18next";

type Props = {
  doc: IndexedFileSummary;
  canUploadAndManageDocs: boolean;
  isAdmin: boolean;
  currentUserId?: string;
  onReindexDocument: (doc: IndexedFileSummary) => Promise<void>;
  onDeleteDocument: (doc: IndexedFileSummary, removeFile: boolean) => Promise<void>;
};

export function DocumentItem({
  doc,
  canUploadAndManageDocs,
  isAdmin,
  currentUserId,
  onReindexDocument,
  onDeleteDocument,
}: Props) {
  const { t } = useTranslation();
  const canManage = canUploadAndManageDocs || isAdmin || !doc.owner_user_id || (!!currentUserId && doc.owner_user_id === currentUserId);
  const indexingStatus = doc.indexing_status || "ready";
  const statusLabel =
    indexingStatus === "pending"
      ? "Queued"
      : indexingStatus === "indexing"
        ? "Indexing"
        : indexingStatus === "failed"
          ? "Failed"
          : "Ready";

  return (
    <div className="doc-row">
      <div>
        <div className="doc-title-row">
          <span>{doc.filename}</span>
          <span className={`doc-status-pill doc-status-pill-${indexingStatus}`}>{statusLabel}</span>
        </div>
        <small className="muted">
          {t("components.workbench.docMeta", {
            chunks: doc.chunks,
            visibility: doc.visibility || "private",
            disk: doc.exists_on_disk ? t("components.workbench.yes") : t("components.workbench.no"),
            uploads: doc.in_uploads ? t("components.workbench.yes") : t("components.workbench.no"),
            agent: doc.agent_class || "general",
          })}
          {doc.parser_profile ? ` | parser=${doc.parser_profile}` : ""}
          {typeof doc.triplets_written === "number" ? ` | graph=${doc.triplets_written}` : ""}
          {doc.indexing_stage ? ` | stage=${doc.indexing_stage}` : ""}
        </small>
        {doc.indexing_error ? <small className="doc-error">{doc.indexing_error}</small> : null}
      </div>
      {canManage && (
        <div className="row-actions">
          <button type="button" className="secondary tiny-btn" onClick={() => void onReindexDocument(doc)} title="重新索引此文档">
            {t("components.workbench.reindex")}
          </button>
          <button type="button" className="danger tiny-btn" onClick={() => void onDeleteDocument(doc, false)} title="仅清除向量库索引">
            {t("components.workbench.deleteIndex")}
          </button>
          <button type="button" className="danger tiny-btn" onClick={() => void onDeleteDocument(doc, true)} title="删除源文件及索引">
            {t("components.workbench.deleteFile")}
          </button>
        </div>
      )}
    </div>
  );
}
