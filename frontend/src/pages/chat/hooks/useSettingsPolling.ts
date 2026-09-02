import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { appApi } from "@/lib/api";

interface UseSettingsPollingOptions {
  onNotify: (message: string, type: "success" | "error" | "info", duration?: number) => void;
}

export function useSettingsPolling({ onNotify }: UseSettingsPollingOptions) {
  const { t } = useTranslation();
  const lastOverrideStateRef = useRef<{
    enabled: boolean;
    provider: string;
    model: string;
  } | null>(null);

  useEffect(() => {
    // Initial fetch
    void (async () => {
      try {
        const res = await appApi.getUserApiSettings();
        if (res.ok && res.settings) {
          lastOverrideStateRef.current = {
            enabled: !!res.settings.global_override_enabled,
            provider: res.settings.global_provider || "",
            model: res.settings.global_model || "",
          };
        }
      } catch (e) {
        // Silent catch - initial fetch failure is not critical
      }
    })();

    // Polling
    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const res = await appApi.getUserApiSettings();
          if (res.ok && res.settings) {
            const enabled = !!res.settings.global_override_enabled;
            const provider = res.settings.global_provider || "";
            const model = res.settings.global_model || "";

            if (lastOverrideStateRef.current !== null) {
              const prev = lastOverrideStateRef.current;
              if (prev.enabled !== enabled || prev.provider !== provider || prev.model !== model) {
                if (enabled) {
                  const desc = t("components.apiSettings.globalOverrideDesc", { provider, model });
                  onNotify(`${t("components.apiSettings.globalOverrideNotice")}: ${desc}`, "info", 4000);
                } else if (prev.enabled) {
                  onNotify(t("components.apiSettings.globalOverrideDisabledNotice"), "info", 4000);
                }
              }
            }
            lastOverrideStateRef.current = { enabled, provider, model };
          }
        } catch (e) {
          // Silent catch - polling failure is not critical
        }
      })();
    }, 25000);

    return () => window.clearInterval(timer);
  }, [onNotify, t]);
}
