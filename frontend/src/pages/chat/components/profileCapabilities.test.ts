import { describe, expect, it } from "vitest";

import {
  profileCapabilities,
  profileModeHint,
} from "./profileCapabilities";

describe("profileCapabilities", () => {
  it.each([
    [
      "standard",
      { web: true, reasoning: true, agent: true, retrieval: true },
    ],
    [
      "strict_quality",
      { web: false, reasoning: false, agent: true, retrieval: true },
    ],
    [
      "advanced",
      { web: false, reasoning: true, agent: false, retrieval: true },
    ],
  ] as const)("exposes only controls supported by %s", (profile, expected) => {
    expect(profileCapabilities(profile)).toEqual(expected);
  });
});

describe("profileModeHint", () => {
  it("uses only switches that the selected profile supports", () => {
    expect(profileModeHint("standard", { useWeb: true, useReasoning: true })).toBe(
      "web",
    );
    expect(
      profileModeHint("strict_quality", { useWeb: true, useReasoning: true }),
    ).toBe("strictQuality");
    expect(
      profileModeHint("advanced", { useWeb: true, useReasoning: true }),
    ).toBe("advancedReasoning");
    expect(
      profileModeHint("advanced", { useWeb: true, useReasoning: false }),
    ).toBe("advanced");
  });
});
