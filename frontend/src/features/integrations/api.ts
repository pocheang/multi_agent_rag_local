import { authRequest } from "../../lib/api-client";

export type ConnectorStatus = "enabled" | "disabled";
export type ConnectorTestStatus = "not_tested" | "passed" | "failed";

export type ConnectorView = {
  connector_id: string;
  name: string;
  base_url: string;
  allowed_hosts: readonly string[];
  status: ConnectorStatus;
  test_status: ConnectorTestStatus;
};

export type ConnectorCreate = {
  connector_id: string;
  name: string;
  base_url: string;
  allowed_hosts: readonly string[];
  secret: string;
};

export type ConnectorProbeResult = {
  status: "passed" | "failed";
  message: string;
};

export async function listConnectors(signal?: AbortSignal): Promise<readonly ConnectorView[]> {
  const response = await authRequest<{ connectors: ConnectorView[] }>(
    "/api/v1/connectors",
    { signal },
  );
  return response.connectors;
}

export function createConnector(input: ConnectorCreate): Promise<ConnectorView> {
  return authRequest<ConnectorView>("/api/v1/connectors", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function setConnectorEnabled(connectorId: string, enabled: boolean): Promise<ConnectorView> {
  const action = enabled ? "enable" : "disable";
  return authRequest<ConnectorView>(
    `/api/v1/connectors/${encodeURIComponent(connectorId)}/${action}`,
    { method: "POST" },
  );
}

export function testConnector(connectorId: string): Promise<ConnectorProbeResult> {
  return authRequest<ConnectorProbeResult>(
    `/api/v1/connectors/${encodeURIComponent(connectorId)}/test`,
    { method: "POST" },
  );
}
