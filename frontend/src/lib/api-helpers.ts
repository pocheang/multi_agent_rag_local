import { authRequest, buildQueryString } from "./api-client";

export function encodePathParam(value: string): string {
  return encodeURIComponent(value);
}

type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export function buildRequest<T>(
  method: HttpMethod,
  path: string,
  body?: Record<string, unknown>,
  params?: Record<string, string | number | boolean | undefined>,
  timeoutMs?: number,
): Promise<T> {
  let fullPath = path;
  if (params) {
    const qs = buildQueryString(params);
    fullPath = qs ? `${path}?${qs}` : path;
  }

  const options: RequestInit = { method };
  if (body && method !== "GET") {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(body);
  }

  return authRequest<T>(fullPath, options, timeoutMs ? { timeoutMs } : {});
}

export function buildPatchRequest<T>(
  path: string,
  body: Record<string, unknown>,
): Promise<T> {
  return buildRequest<T>("PATCH", path, body);
}

export function buildPostRequest<T>(
  path: string,
  body: Record<string, unknown>,
  timeoutMs?: number,
): Promise<T> {
  return buildRequest<T>("POST", path, body, undefined, timeoutMs);
}

export function buildGetRequest<T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  return buildRequest<T>("GET", path, undefined, params);
}

export { buildQueryString };
