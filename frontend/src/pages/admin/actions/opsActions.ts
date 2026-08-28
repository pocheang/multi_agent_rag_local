import { appApi } from "@/lib/api";
import type { AdminActionsParams, ErrorHandler } from "./types";
import { resolveUserIdFromInput } from "../utils";
import { downloadFile, generateTimestampedFilename } from "@/lib/file-utils";

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
      await handleApiError(e, "加载运维指标失败");
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
      await handleApiError(e, "加载 RAG 运维配置失败");
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
      setStatusText("运维报表导出成功");
    } catch (e) {
      await handleApiError(e, "导出失败");
    }
  };

  const runBenchmark = async () => {
    setBenchmarkRunning(true);
    try {
      await appApi.adminRunBenchmark({ maxQueries: 20 });
      const trends = await appApi.adminBenchmarkTrends({ limit: 30 });
      setBenchmarkTrends(trends.items || []);
      setStatusText("基准任务完成，趋势已更新");
    } catch (e) {
      await handleApiError(e, "运行基准失败");
    } finally {
      setBenchmarkRunning(false);
    }
  };

  const reloadConfig = async () => {
    try {
      await appApi.adminReloadConfig();
      await loadRagOps();
      setStatusText("配置热加载成功");
    } catch (e) {
      await handleApiError(e, "配置热加载失败");
    }
  };

  const exportAuditReportMd = async () => {
    try {
      const text = await appApi.adminOpsExportAuditReportMd({ hours: opsHours });
      downloadFile(text, generateTimestampedFilename("ops_audit_report", "md"), "text/markdown");
      setStatusText("审计 Markdown 报告导出成功");
    } catch (e) {
      await handleApiError(e, "导出审计报告失败");
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
