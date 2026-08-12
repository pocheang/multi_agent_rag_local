import type { FileIndexActionResponse, IndexedFileSummary, IndexHealthResponse, UploadResponse } from "@/types/api";
import { authFetch, parseOrThrow, toUrl, getToken, safeParsePayload, ApiError } from "./api-client";
import { authApi } from "./auth-api";
import { encodePathParam } from "./api-helpers";

export const documentApi = {
  upload(
    files: File[],
    onProgress?: (percent: number) => void,
    visibility: "private" | "public" = "private",
  ): Promise<UploadResponse> {
    if (!onProgress) {
      return (async () => {
        const form = new FormData();
        for (const file of files) form.append("files", file);
        form.append("visibility", visibility);
        const res = await authFetch("/upload", { method: "POST", body: form });
        return parseOrThrow<UploadResponse>(res);
      })();
    }

    return new Promise<UploadResponse>((resolve, reject) => {
      const form = new FormData();
      for (const file of files) form.append("files", file);
      form.append("visibility", visibility);

      const xhr = new XMLHttpRequest();
      xhr.open("POST", toUrl("/upload"));
      xhr.withCredentials = true;
      getToken();

      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable && evt.total > 0) {
          const percent = (evt.loaded / evt.total) * 100;
          onProgress(Math.min(100, Math.max(0, percent)));
          return;
        }
        onProgress(35);
      };

      xhr.onerror = () => {
        reject(new Error("network error"));
      };

      xhr.onload = () => {
        const text = xhr.responseText || "";
        const payload = safeParsePayload(text);

        if (xhr.status === 401) {
          authApi.setToken("");
          reject(new ApiError(401, "unauthorized"));
          return;
        }
        if (xhr.status < 200 || xhr.status >= 300) {
          const detail = payload && typeof payload === "object" && !Array.isArray(payload)
            ? (payload as Record<string, unknown>).detail
            : undefined;
          reject(new ApiError(xhr.status, typeof detail === "string" ? detail : "request failed"));
          return;
        }
        resolve(payload as UploadResponse);
      };

      xhr.send(form);
    });
  },
  documents() {
    return authFetch("/documents").then(parseOrThrow<IndexedFileSummary[]>);
  },
  indexHealth() {
    return authFetch("/documents/index-health").then(parseOrThrow<IndexHealthResponse>);
  },
  async documentDelete(filename: string, source: string, removeFile: boolean) {
    const qs = new URLSearchParams({
      remove_file: removeFile ? "true" : "false",
      source,
    });
    const res = await authFetch(`/documents/${encodePathParam(filename)}?${qs.toString()}`, {
      method: "DELETE",
    });
    return parseOrThrow<FileIndexActionResponse>(res);
  },
  async documentReindex(filename: string, source: string) {
    const qs = new URLSearchParams({ source });
    const res = await authFetch(
      `/documents/${encodePathParam(filename)}/reindex?${qs.toString()}`,
      { method: "POST" },
    );
    return parseOrThrow<FileIndexActionResponse>(res);
  },
};
