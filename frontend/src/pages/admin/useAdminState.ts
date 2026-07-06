import { useState } from "react";
import type {
  AdminUserSummary,
  AdminModelSettingsView,
  AuditLogEntry,
  BenchmarkTrendItem,
  OpsOverview,
  RetrievalProfileState,
  SystemLogEntry,
} from "@/types/api";

type Section =
  | "ops"
  | "monitor"
  | "rag"
  | "models"
  | "admins"
  | "users"
  | "audit"
  | "syslog"
  | "webactivity"
  | "agentquality";

export function useAdminState() {
  const [section, setSection] = useState<Section>("ops");
  const [users, setUsers] = useState<AdminUserSummary[]>([]);
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [systemLogs, setSystemLogs] = useState<SystemLogEntry[]>([]);
  const [ops, setOps] = useState<OpsOverview | null>(null);
  const [profileState, setProfileState] = useState<RetrievalProfileState | null>(null);
  const [benchmarkTrends, setBenchmarkTrends] = useState<BenchmarkTrendItem[]>([]);
  const [modelSettings, setModelSettings] = useState<AdminModelSettingsView | null>(null);

  const [statusText, setStatusText] = useState("");
  const [error, setError] = useState("");

  const [loadingUsers, setLoadingUsers] = useState(false);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [loadingSystemLogs, setLoadingSystemLogs] = useState(false);
  const [loadingOps, setLoadingOps] = useState(false);
  const [creatingAdmin, setCreatingAdmin] = useState(false);
  const [savingClass, setSavingClass] = useState(false);
  const [benchmarkRunning, setBenchmarkRunning] = useState(false);
  const [modelLoading, setModelLoading] = useState(false);
  const [modelSaving, setModelSaving] = useState(false);
  const [modelTesting, setModelTesting] = useState(false);

  const [kw, setKw] = useState("");
  const [fRole, setFRole] = useState("");
  const [fStatus, setFStatus] = useState("");
  const [fOnline, setFOnline] = useState("");

  const [auditLimit, setAuditLimit] = useState(200);
  const [auditActorUserId, setAuditActorUserId] = useState("");
  const [auditActionKeyword, setAuditActionKeyword] = useState("");
  const [auditEventCategory, setAuditEventCategory] = useState("");
  const [auditSeverity, setAuditSeverity] = useState("");
  const [auditResult, setAuditResult] = useState("");

  const [systemLogLimit, setSystemLogLimit] = useState(200);
  const [systemLogLevel, setSystemLogLevel] = useState("");
  const [systemLogLogger, setSystemLogLogger] = useState("");
  const [systemLogKeyword, setSystemLogKeyword] = useState("");

  const [opsHours, setOpsHours] = useState(24);
  const [opsActorUserId, setOpsActorUserId] = useState("");
  const [opsActionKeyword, setOpsActionKeyword] = useState("");
  const [opsAutoRefresh, setOpsAutoRefresh] = useState(true);

  const [canaryEnabled, setCanaryEnabled] = useState(false);
  const [canaryBaseline, setCanaryBaseline] = useState(0);
  const [canarySafe, setCanarySafe] = useState(0);
  const [canarySeed, setCanarySeed] = useState("default");

  const [modelApiKey, setModelApiKey] = useState("");
  const [modelTestResult, setModelTestResult] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const [adminUsername, setAdminUsername] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [adminPassword2, setAdminPassword2] = useState("");
  const [adminApprovalToken, setAdminApprovalToken] = useState("");
  const [newAdminApprovalToken, setNewAdminApprovalToken] = useState("");
  const [adminTicketId, setAdminTicketId] = useState("");
  const [adminReason, setAdminReason] = useState("");

  const [editingUser, setEditingUser] = useState<AdminUserSummary | null>(null);
  const [editBu, setEditBu] = useState("");
  const [editDept, setEditDept] = useState("");
  const [editType, setEditType] = useState("");
  const [editScope, setEditScope] = useState("");

  return {
    section,
    setSection,
    users,
    setUsers,
    logs,
    setLogs,
    systemLogs,
    setSystemLogs,
    ops,
    setOps,
    profileState,
    setProfileState,
    benchmarkTrends,
    setBenchmarkTrends,
    modelSettings,
    setModelSettings,
    statusText,
    setStatusText,
    error,
    setError,
    loadingUsers,
    setLoadingUsers,
    loadingLogs,
    setLoadingLogs,
    loadingSystemLogs,
    setLoadingSystemLogs,
    loadingOps,
    setLoadingOps,
    creatingAdmin,
    setCreatingAdmin,
    savingClass,
    setSavingClass,
    benchmarkRunning,
    setBenchmarkRunning,
    modelLoading,
    setModelLoading,
    modelSaving,
    setModelSaving,
    modelTesting,
    setModelTesting,
    kw,
    setKw,
    fRole,
    setFRole,
    fStatus,
    setFStatus,
    fOnline,
    setFOnline,
    auditLimit,
    setAuditLimit,
    auditActorUserId,
    setAuditActorUserId,
    auditActionKeyword,
    setAuditActionKeyword,
    auditEventCategory,
    setAuditEventCategory,
    auditSeverity,
    setAuditSeverity,
    auditResult,
    setAuditResult,
    systemLogLimit,
    setSystemLogLimit,
    systemLogLevel,
    setSystemLogLevel,
    systemLogLogger,
    setSystemLogLogger,
    systemLogKeyword,
    setSystemLogKeyword,
    opsHours,
    setOpsHours,
    opsActorUserId,
    setOpsActorUserId,
    opsActionKeyword,
    setOpsActionKeyword,
    opsAutoRefresh,
    setOpsAutoRefresh,
    canaryEnabled,
    setCanaryEnabled,
    canaryBaseline,
    setCanaryBaseline,
    canarySafe,
    setCanarySafe,
    canarySeed,
    setCanarySeed,
    modelApiKey,
    setModelApiKey,
    modelTestResult,
    setModelTestResult,
    adminUsername,
    setAdminUsername,
    adminPassword,
    setAdminPassword,
    adminPassword2,
    setAdminPassword2,
    adminApprovalToken,
    setAdminApprovalToken,
    newAdminApprovalToken,
    setNewAdminApprovalToken,
    adminTicketId,
    setAdminTicketId,
    adminReason,
    setAdminReason,
    editingUser,
    setEditingUser,
    editBu,
    setEditBu,
    editDept,
    setEditDept,
    editType,
    setEditType,
    editScope,
    setEditScope,
  };
}
