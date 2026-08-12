import { authRequest } from "@/services/http/client";

export function confirmToolApproval(token: string): Promise<void> {
  return authRequest<void>(`/api/v1/connectors/approvals/${encodeURIComponent(token)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmed: true }),
  });
}
