import { create } from "zustand";
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

export interface AdminState {
  section: Section;
  users: AdminUserSummary[];
  logs: AuditLogEntry[];
  systemLogs: SystemLogEntry[];
  ops: OpsOverview | null;
  profileState: RetrievalProfileState | null;
  benchmarkTrends: BenchmarkTrendItem[];
  modelSettings: AdminModelSettingsView | null;

  statusText: string;
  error: string;

  loadingUsers: boolean;
  loadingLogs: boolean;
  loadingSystemLogs: boolean;
  loadingOps: boolean;
  creatingAdmin: boolean;
  savingClass: boolean;
  benchmarkRunning: boolean;
  modelLoading: boolean;
  modelSaving: boolean;
  modelTesting: boolean;

  kw: string;
  fRole: string;
  fStatus: string;
  fOnline: string;

  auditLimit: number;
  auditActorUserId: string;
  auditActionKeyword: string;
  auditEventCategory: string;
  auditSeverity: string;
  auditResult: string;

  systemLogLimit: number;
  systemLogLevel: string;
  systemLogLogger: string;
  systemLogKeyword: string;

  opsHours: number;
  opsActorUserId: string;
  opsActionKeyword: string;
  opsAutoRefresh: boolean;

  canaryEnabled: boolean;
  canaryBaseline: number;
  canarySafe: number;
  canarySeed: string;

  modelApiKey: string;
  modelTestResult: { type: "success" | "error"; message: string } | null;

  adminUsername: string;
  adminPassword: string;
  adminPassword2: string;
  adminApprovalToken: string;
  newAdminApprovalToken: string;
  adminTicketId: string;
  adminReason: string;

  editingUser: AdminUserSummary | null;
  editBu: string;
  editDept: string;
  editType: string;
  editScope: string;

  // Actions
  setSection: (val: Section | ((prev: Section) => Section)) => void;
  setUsers: (val: AdminUserSummary[] | ((prev: AdminUserSummary[]) => AdminUserSummary[])) => void;
  setLogs: (val: AuditLogEntry[] | ((prev: AuditLogEntry[]) => AuditLogEntry[])) => void;
  setSystemLogs: (val: SystemLogEntry[] | ((prev: SystemLogEntry[]) => SystemLogEntry[])) => void;
  setOps: (val: OpsOverview | null | ((prev: OpsOverview | null) => OpsOverview | null)) => void;
  setProfileState: (val: RetrievalProfileState | null | ((prev: RetrievalProfileState | null) => RetrievalProfileState | null)) => void;
  setBenchmarkTrends: (val: BenchmarkTrendItem[] | ((prev: BenchmarkTrendItem[]) => BenchmarkTrendItem[])) => void;
  setModelSettings: (val: AdminModelSettingsView | null | ((prev: AdminModelSettingsView | null) => AdminModelSettingsView | null)) => void;

  setStatusText: (val: string | ((prev: string) => string)) => void;
  setError: (val: string | ((prev: string) => string)) => void;

  setLoadingUsers: (val: boolean | ((prev: boolean) => boolean)) => void;
  setLoadingLogs: (val: boolean | ((prev: boolean) => boolean)) => void;
  setLoadingSystemLogs: (val: boolean | ((prev: boolean) => boolean)) => void;
  setLoadingOps: (val: boolean | ((prev: boolean) => boolean)) => void;
  setCreatingAdmin: (val: boolean | ((prev: boolean) => boolean)) => void;
  setSavingClass: (val: boolean | ((prev: boolean) => boolean)) => void;
  setBenchmarkRunning: (val: boolean | ((prev: boolean) => boolean)) => void;
  setModelLoading: (val: boolean | ((prev: boolean) => boolean)) => void;
  setModelSaving: (val: boolean | ((prev: boolean) => boolean)) => void;
  setModelTesting: (val: boolean | ((prev: boolean) => boolean)) => void;

  setKw: (val: string | ((prev: string) => string)) => void;
  setFRole: (val: string | ((prev: string) => string)) => void;
  setFStatus: (val: string | ((prev: string) => string)) => void;
  setFOnline: (val: string | ((prev: string) => string)) => void;

  setAuditLimit: (val: number | ((prev: number) => number)) => void;
  setAuditActorUserId: (val: string | ((prev: string) => string)) => void;
  setAuditActionKeyword: (val: string | ((prev: string) => string)) => void;
  setAuditEventCategory: (val: string | ((prev: string) => string)) => void;
  setAuditSeverity: (val: string | ((prev: string) => string)) => void;
  setAuditResult: (val: string | ((prev: string) => string)) => void;

  setSystemLogLimit: (val: number | ((prev: number) => number)) => void;
  setSystemLogLevel: (val: string | ((prev: string) => string)) => void;
  setSystemLogLogger: (val: string | ((prev: string) => string)) => void;
  setSystemLogKeyword: (val: string | ((prev: string) => string)) => void;

  setOpsHours: (val: number | ((prev: number) => number)) => void;
  setOpsActorUserId: (val: string | ((prev: string) => string)) => void;
  setOpsActionKeyword: (val: string | ((prev: string) => string)) => void;
  setOpsAutoRefresh: (val: boolean | ((prev: boolean) => boolean)) => void;

  setCanaryEnabled: (val: boolean | ((prev: boolean) => boolean)) => void;
  setCanaryBaseline: (val: number | ((prev: number) => number)) => void;
  setCanarySafe: (val: number | ((prev: number) => number)) => void;
  setCanarySeed: (val: string | ((prev: string) => string)) => void;

  setModelApiKey: (val: string | ((prev: string) => string)) => void;
  setModelTestResult: (val: { type: "success" | "error"; message: string } | null | ((prev: { type: "success" | "error"; message: string } | null) => { type: "success" | "error"; message: string } | null)) => void;

  setAdminUsername: (val: string | ((prev: string) => string)) => void;
  setAdminPassword: (val: string | ((prev: string) => string)) => void;
  setAdminPassword2: (val: string | ((prev: string) => string)) => void;
  setAdminApprovalToken: (val: string | ((prev: string) => string)) => void;
  setNewAdminApprovalToken: (val: string | ((prev: string) => string)) => void;
  setAdminTicketId: (val: string | ((prev: string) => string)) => void;
  setAdminReason: (val: string | ((prev: string) => string)) => void;

  setEditingUser: (val: AdminUserSummary | null | ((prev: AdminUserSummary | null) => AdminUserSummary | null)) => void;
  setEditBu: (val: string | ((prev: string) => string)) => void;
  setEditDept: (val: string | ((prev: string) => string)) => void;
  setEditType: (val: string | ((prev: string) => string)) => void;
  setEditScope: (val: string | ((prev: string) => string)) => void;
}

function updateValue<T>(val: T | ((prev: T) => T), prev: T): T {
  return typeof val === "function" ? (val as (prev: T) => T)(prev) : val;
}

export const useAdminStore = create<AdminState>((set) => ({
  section: "ops",
  users: [],
  logs: [],
  systemLogs: [],
  ops: null,
  profileState: null,
  benchmarkTrends: [],
  modelSettings: null,

  statusText: "",
  error: "",

  loadingUsers: false,
  loadingLogs: false,
  loadingSystemLogs: false,
  loadingOps: false,
  creatingAdmin: false,
  savingClass: false,
  benchmarkRunning: false,
  modelLoading: false,
  modelSaving: false,
  modelTesting: false,

  kw: "",
  fRole: "",
  fStatus: "",
  fOnline: "",

  auditLimit: 200,
  auditActorUserId: "",
  auditActionKeyword: "",
  auditEventCategory: "",
  auditSeverity: "",
  auditResult: "",

  systemLogLimit: 200,
  systemLogLevel: "",
  systemLogLogger: "",
  systemLogKeyword: "",

  opsHours: 24,
  opsActorUserId: "",
  opsActionKeyword: "",
  opsAutoRefresh: true,

  canaryEnabled: false,
  canaryBaseline: 0,
  canarySafe: 0,
  canarySeed: "default",

  modelApiKey: "",
  modelTestResult: null,

  adminUsername: "",
  adminPassword: "",
  adminPassword2: "",
  adminApprovalToken: "",
  newAdminApprovalToken: "",
  adminTicketId: "",
  adminReason: "",

  editingUser: null,
  editBu: "",
  editDept: "",
  editType: "",
  editScope: "",

  setSection: (val) => set((s) => ({ section: updateValue(val, s.section) })),
  setUsers: (val) => set((s) => ({ users: updateValue(val, s.users) })),
  setLogs: (val) => set((s) => ({ logs: updateValue(val, s.logs) })),
  setSystemLogs: (val) => set((s) => ({ systemLogs: updateValue(val, s.systemLogs) })),
  setOps: (val) => set((s) => ({ ops: updateValue(val, s.ops) })),
  setProfileState: (val) => set((s) => ({ profileState: updateValue(val, s.profileState) })),
  setBenchmarkTrends: (val) => set((s) => ({ benchmarkTrends: updateValue(val, s.benchmarkTrends) })),
  setModelSettings: (val) => set((s) => ({ modelSettings: updateValue(val, s.modelSettings) })),

  setStatusText: (val) => set((s) => ({ statusText: updateValue(val, s.statusText) })),
  setError: (val) => set((s) => ({ error: updateValue(val, s.error) })),

  setLoadingUsers: (val) => set((s) => ({ loadingUsers: updateValue(val, s.loadingUsers) })),
  setLoadingLogs: (val) => set((s) => ({ loadingLogs: updateValue(val, s.loadingLogs) })),
  setLoadingSystemLogs: (val) => set((s) => ({ loadingSystemLogs: updateValue(val, s.loadingSystemLogs) })),
  setLoadingOps: (val) => set((s) => ({ loadingOps: updateValue(val, s.loadingOps) })),
  setCreatingAdmin: (val) => set((s) => ({ creatingAdmin: updateValue(val, s.creatingAdmin) })),
  setSavingClass: (val) => set((s) => ({ savingClass: updateValue(val, s.savingClass) })),
  setBenchmarkRunning: (val) => set((s) => ({ benchmarkRunning: updateValue(val, s.benchmarkRunning) })),
  setModelLoading: (val) => set((s) => ({ modelLoading: updateValue(val, s.modelLoading) })),
  setModelSaving: (val) => set((s) => ({ modelSaving: updateValue(val, s.modelSaving) })),
  setModelTesting: (val) => set((s) => ({ modelTesting: updateValue(val, s.modelTesting) })),

  setKw: (val) => set((s) => ({ kw: updateValue(val, s.kw) })),
  setFRole: (val) => set((s) => ({ fRole: updateValue(val, s.fRole) })),
  setFStatus: (val) => set((s) => ({ fStatus: updateValue(val, s.fStatus) })),
  setFOnline: (val) => set((s) => ({ fOnline: updateValue(val, s.fOnline) })),

  setAuditLimit: (val) => set((s) => ({ auditLimit: updateValue(val, s.auditLimit) })),
  setAuditActorUserId: (val) => set((s) => ({ auditActorUserId: updateValue(val, s.auditActorUserId) })),
  setAuditActionKeyword: (val) => set((s) => ({ auditActionKeyword: updateValue(val, s.auditActionKeyword) })),
  setAuditEventCategory: (val) => set((s) => ({ auditEventCategory: updateValue(val, s.auditEventCategory) })),
  setAuditSeverity: (val) => set((s) => ({ auditSeverity: updateValue(val, s.auditSeverity) })),
  setAuditResult: (val) => set((s) => ({ auditResult: updateValue(val, s.auditResult) })),

  setSystemLogLimit: (val) => set((s) => ({ systemLogLimit: updateValue(val, s.systemLogLimit) })),
  setSystemLogLevel: (val) => set((s) => ({ systemLogLevel: updateValue(val, s.systemLogLevel) })),
  setSystemLogLogger: (val) => set((s) => ({ systemLogLogger: updateValue(val, s.systemLogLogger) })),
  setSystemLogKeyword: (val) => set((s) => ({ systemLogKeyword: updateValue(val, s.systemLogKeyword) })),

  setOpsHours: (val) => set((s) => ({ opsHours: updateValue(val, s.opsHours) })),
  setOpsActorUserId: (val) => set((s) => ({ opsActorUserId: updateValue(val, s.opsActorUserId) })),
  setOpsActionKeyword: (val) => set((s) => ({ opsActionKeyword: updateValue(val, s.opsActionKeyword) })),
  setOpsAutoRefresh: (val) => set((s) => ({ opsAutoRefresh: updateValue(val, s.opsAutoRefresh) })),

  setCanaryEnabled: (val) => set((s) => ({ canaryEnabled: updateValue(val, s.canaryEnabled) })),
  setCanaryBaseline: (val) => set((s) => ({ canaryBaseline: updateValue(val, s.canaryBaseline) })),
  setCanarySafe: (val) => set((s) => ({ canarySafe: updateValue(val, s.canarySafe) })),
  setCanarySeed: (val) => set((s) => ({ canarySeed: updateValue(val, s.canarySeed) })),

  setModelApiKey: (val) => set((s) => ({ modelApiKey: updateValue(val, s.modelApiKey) })),
  setModelTestResult: (val) => set((s) => ({ modelTestResult: updateValue(val, s.modelTestResult) })),

  setAdminUsername: (val) => set((s) => ({ adminUsername: updateValue(val, s.adminUsername) })),
  setAdminPassword: (val) => set((s) => ({ adminPassword: updateValue(val, s.adminPassword) })),
  setAdminPassword2: (val) => set((s) => ({ adminPassword2: updateValue(val, s.adminPassword2) })),
  setAdminApprovalToken: (val) => set((s) => ({ adminApprovalToken: updateValue(val, s.adminApprovalToken) })),
  setNewAdminApprovalToken: (val) => set((s) => ({ newAdminApprovalToken: updateValue(val, s.newAdminApprovalToken) })),
  setAdminTicketId: (val) => set((s) => ({ adminTicketId: updateValue(val, s.adminTicketId) })),
  setAdminReason: (val) => set((s) => ({ adminReason: updateValue(val, s.adminReason) })),

  setEditingUser: (val) => set((s) => ({ editingUser: updateValue(val, s.editingUser) })),
  setEditBu: (val) => set((s) => ({ editBu: updateValue(val, s.editBu) })),
  setEditDept: (val) => set((s) => ({ editDept: updateValue(val, s.editDept) })),
  setEditType: (val) => set((s) => ({ editType: updateValue(val, s.editType) })),
  setEditScope: (val) => set((s) => ({ editScope: updateValue(val, s.editScope) })),
}));
