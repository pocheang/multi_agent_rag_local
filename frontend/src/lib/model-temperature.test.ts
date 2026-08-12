import { describe, expect, it } from "vitest";

import { normalizeModelTemperature } from "./model-temperature";

describe("normalizeModelTemperature", () => {
  it.each([
    [-0.2, undefined, 0],
    [0.7, undefined, 0.7],
    [1.4, undefined, 1],
    [Number.NaN, 0.7, 0.7],
  ] as const)("normalizes %s with fallback %s", (value, fallback, expected) => {
    expect(normalizeModelTemperature(value, fallback)).toBe(expected);
  });
});
