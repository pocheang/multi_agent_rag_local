import i18n from "@/i18n/config";
import { appApi } from "@/lib/api";
import type { AdminActionsParams, ErrorHandler } from "./types";

const t = i18n.t.bind(i18n);

export function createSystemLogActions(params: AdminActionsParams, errorHandler: ErrorHandler) {
  const {
    systemLogLimit,
    systemLogLevel,
    systemLogLogger,
    systemLogKeyword,
    isAdmin,
    setSystemLogs,
    setError,
    setLoadingSystemLogs,
  } = params;

  const { handleApiError } = errorHandler;

  const loadSystemLogs = async () => {
    if (!isAdmin) return;
    setLoadingSystemLogs(true);
    try {
      const res = await appApi.adminSystemLogs({
        limit: systemLogLimit,
        level: systemLogLevel.trim() || undefined,
        logger: systemLogLogger.trim() || undefined,
        keyword: systemLogKeyword.trim() || undefined,
      });
      setSystemLogs(res.items || []);
      setError("");
    } catch (e) {
      await handleApiError(e, t("admin.actions.loadSystemLogsFailed"));
    } finally {
      setLoadingSystemLogs(false);
    }
  };

  return {
    loadSystemLogs,
  };
}
