/**
 * 管理后台常量定义
 */

/** 用户角色选项 */
export const ROLE_OPTIONS = ["viewer", "analyst"];

/** 用户状态选项 */
export const STATUS_OPTIONS = ["active", "disabled"];

/** 审计日志操作关键词选项 —— 必须与后端 app/services/security/audit_actions.py 的 AuditAction 一致；
 *  tests/security/test_audit_action_vocabulary.py 会核对这份清单里的每一项确实存在。 */
export const ACTION_KEYWORD_OPTIONS = [
  "auth.login",
  "auth.logout",
  "session.create",
  "session.delete",
  "query.load_guard",
  "query.credit_reserve",
  "query.source_scope",
  "document.upload",
  "document.delete",
  "prompt.create",
  "prompt.update",
  "prompt.delete",
  "admin.user.create_admin",
  "admin.user.role_update",
  "admin.user.status_update",
  "admin.user.classification_update",
  "admin.user.reset_password",
  "admin.user.reset_approval_token",
];
