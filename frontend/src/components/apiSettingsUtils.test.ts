import { describe, expect, it } from "vitest";

import { buildApiPayload, parseApiResponse } from "./apiSettingsUtils";

describe("user model temperature payloads", () => {
  it("normalizes stale temperatures in save and test payload construction", () => {
    const payload = buildApiPayload({
      provider: "local",
      apiKey: "",
      apiKeyMasked: "",
      baseUrl: "",
      model: "local-evidence",
      temperature: 1.4,
      maxTokens: 2048,
    });

    expect(payload.temperature).toBe(1);
  });

  it("normalizes a legacy response temperature", () => {
    const config = parseApiResponse({
      provider: "local",
      api_key_masked: "",
      base_url: "",
      model: "local-evidence",
      temperature: 1.4,
      max_tokens: 2048,
    });

    expect(config.temperature).toBe(1);
  });
});
