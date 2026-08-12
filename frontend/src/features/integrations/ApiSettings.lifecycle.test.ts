// @vitest-environment jsdom

import { StrictMode, act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import "../../i18n/config";

const apiMocks = vi.hoisted(() => ({
  authRequest: vi.fn(),
  getUserApiSettings: vi.fn(),
  modelCatalog: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  appApi: {
    getUserApiSettings: apiMocks.getUserApiSettings,
    modelCatalog: apiMocks.modelCatalog,
  },
}));
vi.mock("../../lib/api-client", () => ({ authRequest: apiMocks.authRequest }));

import { ApiSettings } from "../../components/ApiSettings";

type ConnectorList = {
  connectors: Array<{
    connector_id: string;
    name: string;
    base_url: string;
    allowed_hosts: string[];
    status: "enabled";
    test_status: "not_tested";
  }>;
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((fulfill) => {
    resolve = fulfill;
  });
  return { promise, resolve };
}

function connectorList(id: string, name: string): ConnectorList {
  return {
    connectors: [{
      connector_id: id,
      name,
      base_url: "https://api.example.com",
      allowed_hosts: ["api.example.com"],
      status: "enabled",
      test_status: "not_tested",
    }],
  };
}

const mountedRoots: Root[] = [];

function mountSettings(isOpen: boolean) {
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  mountedRoots.push(root);
  const render = async (open: boolean) => {
    await act(async () => {
      root.render(createElement(
        StrictMode,
        null,
        createElement(ApiSettings, { isOpen: open, onClose() {} }),
      ));
      await Promise.resolve();
    });
  };
  return { container, render, initialRender: render(isOpen) };
}

async function flushEffects() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

beforeAll(() => {
  const reactTestGlobal = globalThis as typeof globalThis & {
    IS_REACT_ACT_ENVIRONMENT?: boolean;
  };
  reactTestGlobal.IS_REACT_ACT_ENVIRONMENT = true;
});

beforeEach(() => {
  apiMocks.authRequest.mockReset();
  apiMocks.getUserApiSettings.mockReset();
  apiMocks.modelCatalog.mockReset();
  apiMocks.getUserApiSettings.mockResolvedValue({ ok: false });
  apiMocks.modelCatalog.mockResolvedValue({ providers: {} });
});

afterEach(async () => {
  while (mountedRoots.length) {
    const root = mountedRoots.pop();
    if (root) {
      await act(async () => root.unmount());
    }
  }
  document.body.replaceChildren();
});

describe("ApiSettings integration lifecycle", () => {
  it("does not load connectors while closed or before settings finish loading", async () => {
    const settings = deferred<{ ok: false }>();
    apiMocks.getUserApiSettings.mockReturnValue(settings.promise);
    apiMocks.authRequest.mockResolvedValue({ connectors: [] });
    const view = mountSettings(false);
    await view.initialRender;

    expect(apiMocks.authRequest).not.toHaveBeenCalled();
    await view.render(true);
    expect(view.container.innerHTML).not.toContain("integrations-panel");
    expect(apiMocks.authRequest).not.toHaveBeenCalled();

    settings.resolve({ ok: false });
    await flushEffects();

    expect(view.container.innerHTML).toContain("integrations-panel");
    expect(apiMocks.authRequest).toHaveBeenCalledOnce();
  });

  it("passes an AbortSignal to the single connector load and aborts it on close", async () => {
    const connectorRequest = deferred<ConnectorList>();
    apiMocks.authRequest.mockReturnValue(connectorRequest.promise);
    const view = mountSettings(true);
    await view.initialRender;
    await flushEffects();

    expect(apiMocks.authRequest).toHaveBeenCalledOnce();
    const options: unknown = apiMocks.authRequest.mock.calls[0]?.[1];
    expect(options).toMatchObject({ signal: expect.any(AbortSignal) });
    const signal = (options as { signal: AbortSignal }).signal;
    expect(signal.aborted).toBe(false);

    await view.render(false);

    expect(signal.aborted).toBe(true);
  });

  it("does not let an aborted connector response replace data from a reopened dialog", async () => {
    const first = deferred<ConnectorList>();
    const second = deferred<ConnectorList>();
    apiMocks.authRequest
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    const view = mountSettings(true);
    await view.initialRender;
    await flushEffects();

    await view.render(false);
    await view.render(true);
    await flushEffects();
    second.resolve(connectorList("fresh", "Fresh connector"));
    await flushEffects();
    expect(view.container.innerHTML).toContain("Fresh connector");

    first.resolve(connectorList("stale", "Stale connector"));
    await flushEffects();

    expect(view.container.innerHTML).toContain("Fresh connector");
    expect(view.container.innerHTML).not.toContain("Stale connector");
  });
});
