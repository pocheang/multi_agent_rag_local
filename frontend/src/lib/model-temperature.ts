const DEFAULT_MODEL_TEMPERATURE = 0.7;

function clampModelTemperature(value: number): number {
  return Math.min(1, Math.max(0, value));
}

export function normalizeModelTemperature(
  value: number,
  fallback: number = DEFAULT_MODEL_TEMPERATURE,
): number {
  const safeFallback = Number.isFinite(fallback)
    ? clampModelTemperature(fallback)
    : DEFAULT_MODEL_TEMPERATURE;
  return Number.isFinite(value) ? clampModelTemperature(value) : safeFallback;
}
