import { useTranslation } from "react-i18next";
import { createApiErrorHandler } from "@/lib/api-error-handler";
import type { AdminActionsParams } from "./actions/types";
import { createUserActions } from "./actions/userActions";
import { createModelActions } from "./actions/modelActions";
import { createAuditActions } from "./actions/auditActions";
import { createSystemLogActions } from "./actions/systemLogActions";
import { createOpsActions } from "./actions/opsActions";

export function useAdminActions(params: AdminActionsParams) {
  const { t } = useTranslation();
  const { onLogout, setError } = params;

  const handleApiError = createApiErrorHandler({
    onLogout,
    onError: setError,
    sessionExpiredMessage: t("common.sessionExpired"),
  });

  const errorHandler = { handleApiError };

  const userActions = createUserActions(params, errorHandler);
  const modelActions = createModelActions(params, errorHandler);
  const auditActions = createAuditActions(params, errorHandler);
  const systemLogActions = createSystemLogActions(params, errorHandler);
  const opsActions = createOpsActions(params, errorHandler);

  return {
    ...userActions,
    ...modelActions,
    ...auditActions,
    ...systemLogActions,
    ...opsActions,
  };
}
