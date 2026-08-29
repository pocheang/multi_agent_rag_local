import i18n from "@/i18n/config";
import { appApi } from "@/lib/api";
import type { AdminActionsParams, ErrorHandler } from "./types";
import { resolveUserIdFromInput } from "../utils";
import { downloadFile, generateTimestampedFilename } from "@/lib/file-utils";

const t = i18n.t.bind(i18n);

export function createOpsActions(params: AdminActionsParams, errorHandler: ErrorHandler) {
  const {
    users,
    opsHours,
    opsActorUserId,
    opsActionKeyword,
    isAdmin,
    setOps,
    setBenchmarkTrends,
    setError,
    setStatusText,
    setLoadingOps,
    setBenchmarkRunning,
  } = params;

  const { handleApiError } = errorHandler;

  const loadOps = async () => {
    if (!isAdmin) return;
    setLoadingOps(true);
    try {
      setOps(await appApi.adminOpsOverview({
        hours: opsHours,
        actorUserId: resolveUserIdFromInput(opsActorUserId, users, { allowRawId: false }),
        actionKeyword: opsActionKeyword.trim() || undefined,
      }));
      setError("");
    } catch (e) {
      await handleApiError(e, t("admin.actions.loadOpsFailed"));
    } finally {
      setLoadingOps(false);
    }
  };

  const loadRagOps = async () => {
    if (!isAdmin) return;
    try {
      const trends = await appApi.adminBenchmarkTrends({ limit: 30 });
      setBenchmarkTrends(trends.items || []);
      setError("");
    } catch (e) {
      await handleApiError(e, t("admin.actions.loadRagOpsFailed"));
    }
  };

  const exportOpsCsv = async () => {
    try {
      const csv = await appApi.adminOpsExportCsv({
        hours: opsHours,
        actorUserId: resolveUserIdFromInput(opsActorUserId, users, { allowRawId: false }),
        actionKeyword: opsActionKeyword.trim() || undefined,
      });
      downloadFile(csv, generateTimestampedFilename("ops_report", "csv"), "text/csv");
      setStatusText(t("admin.actions.opsExported"));
    } catch (e) {
      await handleApiError(e, t("admin.actions.exportFailed"));
    }
  };

  const runBenchmark = async () => {
    setBenchmarkRunning(true);
    try {
      // The backend answers 202 and runs the benchmark in its background queue,
      // so the trends below are the *previous* results; refresh again later to
      // see this run.
      await appApi.adminRunBenchmark({ maxQueries: 20 });
      const trends = await appApi.adminBenchmarkTrends({ limit: 30 });
      setBenchmarkTrends(trends.items || []);
      setStatusText(t("admin.actions.benchmarkQueued"));
    } catch (e) {
      await handleApiError(e, t("admin.actions.runBenchmarkFailed"));
    } finally {
      setBenchmarkRunning(false);
    }
  };

  const reloadConfig = async () => {
    try {
      await appApi.adminReloadConfig();
      await loadRagOps();
      setStatusText(t("admin.actions.configReloaded"));
    } catch (e) {
      await handleApiError(e, t("admin.actions.reloadConfigFailed"));
    }
  };

  const exportAuditReportMd = async () => {
    try {
      const text = await appApi.adminOpsExportAuditReportMd({ hours: opsHours });
      downloadFile(text, generateTimestampedFilename("ops_audit_report", "md"), "text/markdown");
      setStatusText(t("admin.actions.auditReportExported"));
    } catch (e) {
      await handleApiError(e, t("admin.actions.exportAuditReportFailed"));
    }
  };

  return {
    loadOps,
    loadRagOps,
    exportOpsCsv,
    runBenchmark,
    reloadConfig,
    exportAuditReportMd,
  };
}
