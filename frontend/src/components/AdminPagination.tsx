import { useTranslation } from "react-i18next";

type AdminPaginationProps = {
  totalItems: number;
  currentPage: number;
  pageSize: number;
  pageSizeOptions: number[];
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
};

const MAX_VISIBLE_PAGES = 7;

export function AdminPagination({
  totalItems,
  currentPage,
  pageSize,
  pageSizeOptions,
  onPageChange,
  onPageSizeChange,
}: AdminPaginationProps) {
  const { t } = useTranslation();

  // Guard against invalid props
  const safePageSize = pageSize > 0 ? pageSize : pageSizeOptions[0] || 10;
  const safeTotalPages = Math.max(1, Math.ceil(totalItems / safePageSize) || 1);
  const safeCurrentPage = Math.max(1, Math.min(currentPage, safeTotalPages));

  return (
    <nav aria-label={t("admin.ui.pagination", "Pagination")} className="admin-pagination">
      <div className="admin-pagination-info">
        {t("admin.ui.totalItems", { count: totalItems })}
      </div>
      <div className="admin-pagination-controls">
        <div className="admin-pagination-select-wrap">
          <span>{t("admin.ui.showPerPage")}</span>
          <select
            value={safePageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value) || pageSizeOptions[0])}
            aria-label={t("admin.ui.itemsPerPage", "Items per page")}
          >
            {pageSizeOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <span>{t("admin.ui.items")}</span>
        </div>
        <div className="admin-pagination-pages">
          <button
            type="button"
            className="admin-pagination-btn"
            disabled={safeCurrentPage === 1}
            aria-disabled={safeCurrentPage === 1}
            aria-label={t("common.previous") || "Previous page"}
            onClick={() => onPageChange(Math.max(1, safeCurrentPage - 1))}
          >
            {t("common.previous")}
          </button>
          {Array.from({ length: safeTotalPages }).map((_, idx) => {
            const pageNum = idx + 1;
            if (safeTotalPages > MAX_VISIBLE_PAGES) {
              const isNearCurrent = Math.abs(pageNum - safeCurrentPage) <= 1;
              const isFirstOrLast = pageNum === 1 || pageNum === safeTotalPages;
              if (!isNearCurrent && !isFirstOrLast) {
                if (pageNum === 2 || pageNum === safeTotalPages - 1) {
                  return (
                    <span key={pageNum} style={{ padding: "0 4px", opacity: 0.5 }} aria-hidden="true">
                      ...
                    </span>
                  );
                }
                return null;
              }
            }
            return (
              <button
                key={pageNum}
                type="button"
                className={`admin-pagination-btn ${safeCurrentPage === pageNum ? "active" : ""}`}
                onClick={() => onPageChange(pageNum)}
                aria-label={t("admin.ui.goToPage", { page: pageNum }) || `Go to page ${pageNum}`}
                aria-current={safeCurrentPage === pageNum ? "page" : undefined}
              >
                {pageNum}
              </button>
            );
          })}
          <button
            type="button"
            className="admin-pagination-btn"
            disabled={safeCurrentPage === safeTotalPages}
            aria-disabled={safeCurrentPage === safeTotalPages}
            aria-label={t("common.next") || "Next page"}
            onClick={() => onPageChange(Math.min(safeTotalPages, safeCurrentPage + 1))}
          >
            {t("common.next")}
          </button>
        </div>
      </div>
    </nav>
  );
}
