import { appApi } from "@/lib/api";
import type { AdminUserSummary } from "@/types/api";
import type { AdminActionsParams, ErrorHandler } from "./types";

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
      await handleApiError(e, "加载用户失败");
    } finally {
      setLoadingUsers(false);
    }
  };

  const createAdmin = async () => {
    const username = adminUsername.trim();
    if (!username) return setError("管理员用户名不能为空");
    if (!adminPassword || adminPassword.length < 12) return setError("密码长度至少 12 位，需含大小写、数字和特殊字符");
    if (adminPassword !== adminPassword2) return setError("两次密码不一致");
    if (!adminApprovalToken.trim()) return setError("审批令牌不能为空");
    if (!newAdminApprovalToken.trim() || newAdminApprovalToken.trim().length < 12) return setError("新管理员令牌至少 12 位");
    if (!adminTicketId.trim()) return setError("工单号不能为空");
    if (!adminReason.trim() || adminReason.trim().length < 5) return setError("原因至少 5 个字符");
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
      setStatusText(`管理员已创建：${created.username}（ID: ${created.user_id}）`);
      setError("");
    } catch (e) {
      await handleApiError(e, "创建管理员失败");
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
      await handleApiError(e, "角色更新失败");
    }
  };

  const updateStatus = async (target: AdminUserSummary, statusValue: string) => {
    if (target.status === statusValue) return;
    try {
      const updated = await appApi.adminUpdateStatus(target.user_id, statusValue);
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
    } catch (e) {
      await handleApiError(e, "状态更新失败");
    }
  };

  const addUserCredits = async (target: AdminUserSummary) => {
    if ((target.role || "").toLowerCase() === "admin") return;
    const rawAmount = (window.prompt(`请输入要为 ${target.username} 增加的额度（正整数）`) || "").trim();
    if (!rawAmount) return;
    if (!/^\d+$/.test(rawAmount)) return setError("额度必须是正整数");
    const amount = Number(rawAmount);
    if (!Number.isSafeInteger(amount) || amount < 1 || amount > 1_000_000) {
      return setError("单次增加额度必须在 1 到 1000000 之间");
    }
    try {
      const updated = await appApi.adminAddCredits(target.user_id, amount);
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
      setStatusText(`已为 ${updated.username} 增加 ${amount} 点，当前余额 ${updated.credit_balance} 点`);
      setError("");
    } catch (e) {
      await handleApiError(e, "增加额度失败");
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
      setStatusText("用户分类已保存");
    } catch (e) {
      await handleApiError(e, "分类更新失败");
    } finally {
      setSavingClass(false);
    }
  };

  const resetAdminApprovalToken = async (target: AdminUserSummary) => {
    if ((target.role || "").toLowerCase() !== "admin") return;
    const newToken = (window.prompt(`请输入 ${target.username} 的新管理员令牌（至少12位）`) || "").trim();
    if (!newToken || newToken.length < 12) return setError("新管理员令牌至少 12 位");
    const approvalToken = (window.prompt("请输入你的审批令牌") || "").trim();
    const ticketId = (window.prompt("请输入工单号") || "").trim();
    const reason = (window.prompt("请输入原因（至少5个字符）") || "").trim();
    if (!approvalToken || !ticketId || reason.length < 5) return setError("审批令牌/工单号/原因不完整");
    try {
      const updated = await appApi.adminResetApprovalToken({
        userId: target.user_id,
        approvalToken,
        ticketId,
        reason,
        newAdminApprovalToken: newToken,
      });
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
      setStatusText(`管理员令牌已重置：${updated.username}`);
    } catch (e) {
      await handleApiError(e, "重置管理员令牌失败");
    }
  };

  const resetUserPassword = async (target: AdminUserSummary) => {
    const newPassword = (window.prompt(`请输入 ${target.username} 的新密码（至少12位，含大小写、数字和特殊字符）`) || "").trim();
    if (!newPassword) return;
    const approvalToken = (window.prompt("请输入你的审批令牌") || "").trim();
    const ticketId = (window.prompt("请输入工单号") || "").trim();
    const reason = (window.prompt("请输入重置原因（至少5个字符）") || "").trim();
    if (!approvalToken || !ticketId || reason.length < 5) return setError("审批令牌/工单号/原因不完整");
    try {
      const updated = await appApi.adminResetPassword({
        userId: target.user_id,
        approvalToken,
        ticketId,
        reason,
        newPassword,
      });
      setUsers((prev) => prev.map((x) => (x.user_id === updated.user_id ? updated : x)));
      setStatusText(`用户密码已重置：${updated.username}`);
    } catch (e) {
      await handleApiError(e, "重置密码失败");
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
