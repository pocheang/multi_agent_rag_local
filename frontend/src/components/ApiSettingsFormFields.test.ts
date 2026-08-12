import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

import { ApiSettingsFormFields } from "./ApiSettingsFormFields";

describe("ApiSettingsFormFields", () => {
  it("renders a temperature range bounded from zero to one", () => {
    const html = renderToStaticMarkup(createElement(ApiSettingsFormFields, {
      config: {
        provider: "local",
        apiKey: "",
        apiKeyMasked: "",
        baseUrl: "",
        model: "local-evidence",
        temperature: 0.7,
        maxTokens: 2048,
      },
      selectedModels: ["local-evidence"],
      requiresApiKey: false,
      requiresBaseUrl: false,
      showApiKey: false,
      onShowApiKeyToggle() {},
      onConfigChange() {},
    }));

    expect(html).toContain('id="temperature-input" type="range"');
    expect(html).toContain('min="0" max="1" step="0.1"');
  });
});
