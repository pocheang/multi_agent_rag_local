import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (_key: string, fallback?: string) => fallback ?? _key }),
}));
vi.mock("@/lib/api", () => ({
  appApi: { modelCatalog: () => Promise.resolve({ version: "test", providers: {} }) },
}));

import { AdminModelSettings } from "./AdminModelSettings";

describe("AdminModelSettings", () => {
  it("renders a temperature range bounded from zero to one", () => {
    const html = renderToStaticMarkup(createElement(AdminModelSettings, {
      modelSettings: {
        enabled: false,
        provider: "local",
        api_key_masked: "",
        base_url: "",
        chat_model: "local-evidence",
        reasoning_model: "local-evidence",
        embedding_model: "local-hash-384",
        temperature: 0.7,
        max_tokens: 2048,
      },
      modelLoading: false,
      modelSaving: false,
      modelTesting: false,
      modelTestResult: null,
      onRefresh() {},
      onSave() {},
      onTest() {},
      onPatch() {},
      modelApiKey: "",
      onApiKeyChange() {},
    }));

    expect(html).toContain('type="range" min="0" max="1" step="0.1"');
  });
});
