import { useTranslation } from "react-i18next";
import type { ExecutionTraceState } from "../tool-approval/state";

type Props = { trace: ExecutionTraceState };

export function ExecutionTracePanel({ trace }: Props) {
  const { t } = useTranslation();

  return (
    <section className="execution-trace-panel" aria-label={t("features.executionTrace.ariaLabel")}>
      <h2>{t("features.executionTrace.title")}</h2>
      {trace.events.length === 0 ? (
        <p className="runtime-panel-empty">{t("features.executionTrace.empty")}</p>
      ) : (
        <ol>
          {trace.events.map((event, index) => (
            <li key={`${event.occurred_at}-${index}`}>
              {t("features.executionTrace.event", {
                stage: event.stage,
                message: event.message || event.status,
                duration: event.duration_ms,
              })}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
