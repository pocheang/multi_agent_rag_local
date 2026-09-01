import { useState } from "react";
import { useTranslation } from "react-i18next";

import { confirmToolApproval } from "./toolApprovalApi";
import type { PendingApproval } from "@/types/api";

type Props = {
  approval: PendingApproval | null;
  /** Re-run the request carrying the approved token. Confirming alone does not
   *  perform the action: it marks the token approved, and the run that replays
   *  it is what reaches the executor. This panel used to stop after confirming,
   *  so the action the user approved never actually happened. */
  onApproved: (token: string) => Promise<void> | void;
  onDismiss: () => void;
};

export function ToolApprovalPanel({ approval, onApproved, onDismiss }: Props) {
  const { t } = useTranslation();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!approval) return null;

  const confirm = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await confirmToolApproval(approval.token);
      await onApproved(approval.token);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : t("features.toolApproval.errorFallback"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="tool-approval-panel" aria-label={t("features.toolApproval.ariaLabel")}>
      <h2>{t("features.toolApproval.title")}</h2>
      <p>{approval.summary || approval.tool_id}</p>
      {error ? <p className="runtime-panel-error" role="alert">{error}</p> : null}
      <button type="button" onClick={() => void confirm()} disabled={submitting}>
        {submitting ? t("features.toolApproval.confirming") : t("features.toolApproval.confirm")}
      </button>
      <button type="button" onClick={onDismiss} disabled={submitting}>
        {t("features.toolApproval.dismiss", "Not now")}
      </button>
    </section>
  );
}
