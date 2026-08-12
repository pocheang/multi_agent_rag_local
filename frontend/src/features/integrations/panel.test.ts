import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("@/services/execution/execution-api", () => ({
  streamExecutionEvents: () => Promise.resolve(),
}));
vi.mock("@/services/http/client", () => ({
  authRequest: () => Promise.resolve(),
}));
vi.mock("@/features/execution-trace/ExecutionTracePanel", async () => (
  import("../execution-trace/ExecutionTracePanel")
));
vi.mock("@/features/execution-trace/useExecutionTrace", async () => (
  import("../execution-trace/useExecutionTrace")
));
vi.mock("@/features/tool-approval/ToolApprovalPanel", async () => (
  import("../tool-approval/ToolApprovalPanel")
));
vi.mock("@/features/integrations/IntegrationsPanel", async () => (
  import("./IntegrationsPanel")
));

import { ChatRuntimePanels } from "../../pages/chat/components/ChatRuntimePanels";
import { IntegrationsPanel } from "./IntegrationsPanel";

beforeAll(async () => {
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: { getItem: () => null },
  });
  Object.defineProperty(globalThis, "document", {
    configurable: true,
    value: { documentElement: { dataset: {}, lang: "" } },
  });
  await import("../../i18n/config");
});

describe("IntegrationsPanel", () => {
  it("renders connector creation and management controls without a credential display", () => {
    const html = renderToStaticMarkup(createElement(IntegrationsPanel, {}));

    expect(html).toContain("Connect integration");
    expect(html).toContain("Integration ID");
    expect(html).toContain("Base URL");
    expect(html).toContain("Allowed hosts");
    expect(html).toContain("Add connector");
    expect(html).not.toContain("credential_display");
  });
});

describe("integration panel placement", () => {
  it("renders no runtime panel before an execution starts", () => {
    const html = renderToStaticMarkup(createElement(ChatRuntimePanels, { executionId: null }));

    expect(html).toBe("");
  });

  it("keeps runtime traces in chat without rendering integrations", () => {
    const html = renderToStaticMarkup(createElement(ChatRuntimePanels, { executionId: "run-1" }));

    expect(html).toContain("execution-trace-panel");
    expect(html).not.toContain("integrations-panel");
  });
});
