import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createConnector,
  listConnectors,
  setConnectorEnabled,
  testConnector,
} from "./api";

describe("connector management REST client", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      removeItem: () => undefined,
    });
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockReset();
    fetchMock.mockImplementation(() => Promise.resolve(
      new Response(JSON.stringify({ connectors: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ));
  });

  afterEach(() => vi.unstubAllGlobals());

  it("uses only bounded FastAPI connector endpoints", async () => {
    await listConnectors();
    await createConnector({
      connector_id: "crm",
      name: "CRM",
      base_url: "https://api.example.com/v1",
      allowed_hosts: ["api.example.com"],
      secret: "server-only",
    });
    await setConnectorEnabled("crm", false);
    await setConnectorEnabled("crm", true);
    await testConnector("crm");

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/connectors",
      "/api/v1/connectors",
      "/api/v1/connectors/crm/disable",
      "/api/v1/connectors/crm/enable",
      "/api/v1/connectors/crm/test",
    ]);
    expect(fetchMock.mock.calls.map(([, init]) => init.method ?? "GET")).toEqual([
      "GET",
      "POST",
      "POST",
      "POST",
      "POST",
    ]);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      connector_id: "crm",
      name: "CRM",
      base_url: "https://api.example.com/v1",
      allowed_hosts: ["api.example.com"],
      secret: "server-only",
    });
    expect(fetchMock.mock.calls.flat().join(" ")).not.toContain("jsonrpc");
  });
});
