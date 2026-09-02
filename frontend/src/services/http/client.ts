import { requiresCsrfProtection, addCsrfHeader } from "@/lib/csrf";

type Json = Record<string, unknown> | Array<unknown>;

export type RequestOptions = {
  timeoutMs?: number;
};

export type AuthFetchOptions = RequestOptions & {
  networkRetry?: number;
  retryDelayMs?: number;
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function resolveApiBase() {
  const raw = String(import.meta.env.VITE_API_BASE_URL || "").trim();
  if (!raw) return "";
  const cleaned = raw.replace(/\/+$/, "");

  if (typeof window === "undefined") return cleaned;
  try {
    const parsed = new URL(cleaned);
    const pageHost = window.location.hostname;
    const apiHost = parsed.hostname;
    const isLoopbackPair =
      (apiHost === "localhost" || apiHost === "127.0.0.1") &&
      (pageHost === "localhost" || pageHost === "127.0.0.1");
    if (!isLoopbackPair || apiHost === pageHost) return cleaned;
    parsed.hostname = pageHost;
    return parsed.toString().replace(/\/+$/, "");
  } catch {
    return cleaned.startsWith("/") ? cleaned : `/${cleaned}`;
  }
}

function resolveAppBasePrefix() {
  const raw = String(import.meta.env.BASE_URL || "/").trim();
  if (!raw || raw === "/") return "";
  const normalized = raw.replace(/\/+$/, "");
  if (!normalized || normalized === "/") return "";
  return normalized.startsWith("/") ? normalized : `/${normalized}`;
}

const API_BASE = resolveApiBase();
const APP_BASE_PREFIX = resolveAppBasePrefix();
const TOKEN_KEY = "auth_token";

export function getToken() {
  if (typeof localStorage === "undefined") return "";
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token: string) {
  if (typeof localStorage === "undefined") return;
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function toUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (API_BASE) {
    let basePath = API_BASE.startsWith("/") ? API_BASE : "";
    let absoluteOrigin = "";
    try {
      const parsed = new URL(API_BASE);
      basePath = parsed.pathname.replace(/\/+$/, "");
      absoluteOrigin = parsed.origin;
    } catch {
      // Relative API prefixes are handled directly.
    }
    if (basePath && (normalizedPath === basePath || normalizedPath.startsWith(`${basePath}/`))) {
      return absoluteOrigin ? `${absoluteOrigin}${normalizedPath}` : normalizedPath;
    }
    return `${API_BASE}${normalizedPath}`;
  }
  if (APP_BASE_PREFIX && (normalizedPath === APP_BASE_PREFIX || normalizedPath.startsWith(`${APP_BASE_PREFIX}/`))) {
    return normalizedPath;
  }
  return `${APP_BASE_PREFIX}${normalizedPath}`;
}

function sleep(ms: number) {
  return new Promise((resolve) => globalThis.setTimeout(resolve, ms));
}

function isTransientNetworkError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const msg = String(err.message || "").toLowerCase();
  return (
    err.name === "TypeError" ||
    msg.includes("failed to fetch") ||
    msg.includes("networkerror") ||
    msg.includes("network error")
  );
}

export function safeParsePayload(text: string): unknown {
  if (!text) return {};
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { detail: text };
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function errorMessage(payload: unknown): string {
  if (isRecord(payload) && typeof payload.detail === "string" && payload.detail.trim()) {
    return payload.detail.trim();
  }
  if (isRecord(payload) && Array.isArray(payload.detail)) {
    const first = payload.detail.find(isRecord);
    if (first && typeof first.msg === "string" && first.msg.trim()) {
      return `Invalid request: ${first.msg.trim()}`;
    }
    return "Invalid request";
  }
  return "Request failed";
}

function createRequestSignal(signal: AbortSignal | null | undefined, timeoutMs: number | undefined) {
  const controller = new AbortController();
  let timedOut = false;
  const onAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", onAbort, { once: true });
  }
  const timeoutId = timeoutMs && timeoutMs > 0
    ? globalThis.setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs)
    : undefined;
  return {
    signal: controller.signal,
    wasTimedOut: () => timedOut,
    dispose: () => {
      if (timeoutId !== undefined) globalThis.clearTimeout(timeoutId);
      signal?.removeEventListener("abort", onAbort);
    },
  };
}

async function fetchWithTimeout(path: string, init: RequestInit, options: RequestOptions): Promise<Response> {
  const composed = createRequestSignal(init.signal, options.timeoutMs ?? 30_000);
  try {
    const headers = new Headers(init.headers || {});
    const token = getToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    // Add CSRF protection for state-changing requests
    if (requiresCsrfProtection(init.method || 'GET')) {
      addCsrfHeader(headers);
    }

    return await fetch(toUrl(path), { ...init, headers, signal: composed.signal, credentials: "include" });
  } catch (error) {
    if (composed.wasTimedOut()) throw new ApiError(408, "Request timed out");
    throw error;
  } finally {
    composed.dispose();
  }
}

export async function request<T = Json>(path: string, init: RequestInit = {}, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(init.headers || {});
  const res = await fetchWithTimeout(path, { ...init, headers }, options);

  const text = await res.text();
  const payload = safeParsePayload(text);
  if (!res.ok) {
    throw new ApiError(res.status, errorMessage(payload));
  }
  return payload as T;
}

export async function authFetch(
  path: string,
  init: RequestInit = {},
  opts: AuthFetchOptions = {},
) {
  const retries = Math.max(0, Number(opts.networkRetry || 0));
  const delayMs = Math.max(50, Number(opts.retryDelayMs || 300));
  let attempt = 0;
  while (true) {
    try {
      const headers = new Headers(init.headers || {});
      const res = await fetchWithTimeout(path, { ...init, headers }, opts);
      if (res.status === 401) {
        throw new ApiError(401, "unauthorized");
      }
      return res;
    } catch (e) {
      if (attempt >= retries || !isTransientNetworkError(e)) {
        throw e;
      }
      attempt += 1;
      await sleep(delayMs * attempt);
    }
  }
}

export async function parseOrThrow<T>(res: Response): Promise<T> {
  const text = await res.text();
  const payload = safeParsePayload(text);
  if (!res.ok) {
    throw new ApiError(res.status, errorMessage(payload));
  }
  return payload as T;
}

export async function authRequest<T>(
  path: string,
  init: RequestInit = {},
  opts: AuthFetchOptions = {},
): Promise<T> {
  const res = await authFetch(path, init, opts);
  return parseOrThrow<T>(res);
}

export function buildQueryString(params: Record<string, string | number | boolean | undefined>): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      qs.set(key, String(value));
    }
  }
  return qs.toString();
}

export const TOKEN_KEY_EXPORT = TOKEN_KEY;
