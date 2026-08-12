import { useState } from "react";
import { useTranslation } from "react-i18next";

import { confirmToolApproval } from "./toolApprovalApi";
import type { PendingApproval } from "./state";

type Props = { approval: PendingApproval | null; onResolved: () => void };

export function ToolApprovalPanel({ approval, onResolved }: Props) {
  const { t } = useTranslation();
  const [submitting, setSubmitting] = useState(false);
  const [resolvedToken, setResolvedToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!approval || resolvedToken === approval.token) return null;

  const confirm = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await confirmToolApproval(approval.token);
      setResolvedToken(approval.token);
      onResolved();
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : t("features.toolApproval.errorFallback"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="tool-approval-panel" aria-label={t("features.toolApproval.ariaLabel")}>
      <h2>{t("features.toolApproval.title")}</h2>
      <p>{approval.message}</p>
      {error ? <p className="runtime-panel-error" role="alert">{error}</p> : null}
      <button type="button" onClick={() => void confirm()} disabled={submitting}>
        {submitting ? t("features.toolApproval.confirming") : t("features.toolApproval.confirm")}
      </button>
    </section>
  );
}
