import i18n from "@/i18n/config";
import { appApi } from "@/lib/api";
import type { AdminUserSummary } from "@/types/api";
import type { AdminActionsParams, ErrorHandler } from "./types";

const t = i18n.t.bind(i18n);

export function createUserActions(params: AdminActionsParams, errorHandler: ErrorHandler) {
  const {
    isAdmin,
    adminUsername,
    adminPassword,
    adminPassword2,
    adminApprovalToken,
    newAdminApprovalToken,
    adminTicketId,
    adminReason,
    editingUser,
    editBu,
    editDept,
    editType,
    editScope,
    promptInput,
    setUsers,
    setError,
    setStatusText,
    setLoadingUsers,
    setCreatingAdmin,
    setSavingClass,
    setAdminUsername,
    setAdminPassword,
    setAdminPassword2,
    setAdminApprovalToken,
    setNewAdminApprovalToken,
    setAdminTicketId,
    setAdminReason,
    setEditingUser,
  } = params;

  const { handleApiError } = errorHandler;

  const loadUsers = async () => {
    if (!isAdmin) return;
    setLoadingUsers(true);
    setError("");
    try {
      setUsers(await appApi.adminUsers());
    } catch (e) {
      await handleApiError(e, t("admin.actions.loadUsersFailed"));
    } finally {
      setLoadingUsers(false);
    }
  };

  const createAdmin = async () => {
    const username = adminUsername.trim();
    if (!username) return setError(t("admin.actions.adminUsernameRequired"));
    if (!adminPassword || adminPassword.length < 12) return setError(t("admin.actions.passwordRequirements"));
    if (adminPassword !== adminPassword2) return setError(t("admin.actions.passwordMismatch"));
    if (!adminApprovalToken.trim()) return setError(t("admin.actions.approvalTokenRequired"));
    if (!newAdminApprovalToken.trim() || newAdminApprovalToken.trim().length < 12)
      return setError(t("admin.actions.newAdminTokenRequirements"));
    if (!adminTicketId.trim()) return setError(t("admin.actions.ticketIdRequired"));
    if (!adminReason.trim() || adminReason.trim().length < 5) return setError(t("admin.actions.reasonRequirements"));
    setCreatingAdmin(true);
    try {
      const created = await appApi.adminCreateAdmin({
        username,
        password: adminPassword,
        approvalToken: adminApprovalToken.trim(),
        ticketId: adminTicketId.trim(),
        reason: adminReason.trim(),
        newAdminApprovalToken: newAdminApprovalToken.trim(),
      });
      setUsers((prev) => [created, ...prev]);
      setAdminUsername("");
      setAdminPassword("");
      setAdminPassword2("");
      setAdminApprovalToken("");
      setNewAdminApprovalToken("");
      setAdminTicketId("");
      setAdminReason("");
      setStatusText(t("admin.actions.adminCreated", { username: created.username, userId: created.user_id }));
      setError("");
    } catch (e) {
      await handleApiError(e, t("admin.actions.createAdminFailed"));
    } finally {
      setCreatingAdmin(false);
    }
  };

  const updateRole = async (target: AdminUserSummary, role: string) => {
    if (target.role === role) return;
    try {
      const updated = await appApi.adminUpdateRole(target.user_id, role);
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
    } catch (e) {
      await handleApiError(e, t("admin.actions.updateRoleFailed"));
    }
  };

  const updateStatus = async (target: AdminUserSummary, statusValue: string) => {
    if (target.status === statusValue) return;
    try {
      const updated = await appApi.adminUpdateStatus(target.user_id, statusValue);
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
    } catch (e) {
      await handleApiError(e, t("admin.actions.updateStatusFailed"));
    }
  };

  const addUserCredits = async (target: AdminUserSummary) => {
    if ((target.role || "").toLowerCase() === "admin") return;
    const raw = await promptInput({
      title: t("admin.ui.addCredits"),
      message: t("admin.actions.creditsPrompt", { username: target.username }),
    });
    const rawAmount = (raw || "").trim();
    if (!rawAmount) return;
    if (!/^\d+$/.test(rawAmount)) return setError(t("admin.actions.creditsInvalidInteger"));
    const amount = Number(rawAmount);
    if (!Number.isSafeInteger(amount) || amount < 1 || amount > 1_000_000) {
      return setError(t("admin.actions.creditsRange"));
    }
    try {
      const updated = await appApi.adminAddCredits(target.user_id, amount);
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
      setStatusText(
        t("admin.actions.creditsAdded", { username: updated.username, amount, balance: updated.credit_balance }),
      );
      setError("");
    } catch (e) {
      await handleApiError(e, t("admin.actions.addCreditsFailed"));
    }
  };

  const saveClass = async () => {
    if (!editingUser) return;
    setSavingClass(true);
    try {
      const updated = await appApi.adminUpdateClassification(editingUser.user_id, {
        businessUnit: editBu.trim(),
        department: editDept.trim(),
        userType: editType.trim(),
        dataScope: editScope.trim(),
      });
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
      setEditingUser(null);
      setStatusText(t("admin.actions.classificationSaved"));
    } catch (e) {
      await handleApiError(e, t("admin.actions.updateClassificationFailed"));
    } finally {
      setSavingClass(false);
    }
  };

  const resetAdminApprovalToken = async (target: AdminUserSummary) => {
    if ((target.role || "").toLowerCase() !== "admin") return;
    const newTokenRaw = await promptInput({
      title: t("admin.ui.resetToken"),
      message: t("admin.actions.resetAdminTokenPrompt", { username: target.username }),
      inputType: "password",
    });
    const newToken = (newTokenRaw || "").trim();
    if (!newToken || newToken.length < 12) return setError(t("admin.actions.newAdminTokenRequirements"));
    const approvalTokenRaw = await promptInput({
      title: t("admin.ui.resetToken"),
      message: t("admin.actions.yourApprovalTokenPrompt"),
      inputType: "password",
    });
    const approvalToken = (approvalTokenRaw || "").trim();
    const ticketIdRaw = await promptInput({ title: t("admin.ui.resetToken"), message: t("admin.actions.ticketIdPrompt") });
    const ticketId = (ticketIdRaw || "").trim();
    const reasonRaw = await promptInput({ title: t("admin.ui.resetToken"), message: t("admin.actions.reasonPrompt") });
    const reason = (reasonRaw || "").trim();
    if (!approvalToken || !ticketId || reason.length < 5) return setError(t("admin.actions.incompleteApprovalFields"));
    try {
      const updated = await appApi.adminResetApprovalToken({
        userId: target.user_id,
        approvalToken,
        ticketId,
        reason,
        newAdminApprovalToken: newToken,
      });
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
      setStatusText(t("admin.actions.adminTokenReset", { username: updated.username }));
    } catch (e) {
      await handleApiError(e, t("admin.actions.resetAdminTokenFailed"));
    }
  };

  const resetUserPassword = async (target: AdminUserSummary) => {
    const newPasswordRaw = await promptInput({
      title: t("admin.ui.resetPassword"),
      message: t("admin.actions.resetPasswordPrompt", { username: target.username }),
      inputType: "password",
    });
    const newPassword = (newPasswordRaw || "").trim();
    if (!newPassword) return;
    const approvalTokenRaw = await promptInput({
      title: t("admin.ui.resetPassword"),
      message: t("admin.actions.yourApprovalTokenPrompt"),
      inputType: "password",
    });
    const approvalToken = (approvalTokenRaw || "").trim();
    const ticketIdRaw = await promptInput({ title: t("admin.ui.resetPassword"), message: t("admin.actions.ticketIdPrompt") });
    const ticketId = (ticketIdRaw || "").trim();
    const reasonRaw = await promptInput({ title: t("admin.ui.resetPassword"), message: t("admin.actions.resetReasonPrompt") });
    const reason = (reasonRaw || "").trim();
    if (!approvalToken || !ticketId || reason.length < 5) return setError(t("admin.actions.incompleteApprovalFields"));
    try {
      const updated = await appApi.adminResetPassword({
        userId: target.user_id,
        approvalToken,
        ticketId,
        reason,
        newPassword,
      });
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
      setStatusText(t("admin.actions.passwordReset", { username: updated.username }));
    } catch (e) {
      await handleApiError(e, t("admin.actions.resetPasswordFailed"));
    }
  };

  return {
    loadUsers,
    createAdmin,
    updateRole,
    updateStatus,
    addUserCredits,
    saveClass,
    resetAdminApprovalToken,
    resetUserPassword,
  };
}
