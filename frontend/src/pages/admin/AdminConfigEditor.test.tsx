// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminConfigEditor } from "@/pages/admin/AdminConfigEditor";
import type { ConfigField } from "@/types/api";

/**
 * The page is generated from the server's schema, so what is worth testing is
 * the two things the generation has to get right:
 *
 * 1. a value pinned in the process environment is not editable here -- it
 *    outranks the configuration centre, so an enabled input would invite a
 *    change that silently does nothing;
 * 2. only the fields actually edited are sent, because the server merges them
 *    into the document it already holds. Sending everything would turn a page
 *    load into a write of every value, and stale reads into overwrites.
 */

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string, options?: { count?: number }) => (options ? `${key}:${options.count}` : key) }),
}));

const schema = vi.fn();
const save = vi.fn();
vi.mock("@/services/api/admin", () => ({
  adminConfigApi: {
    configSchema: () => schema(),
    saveConfig: (values: Record<string, string>, dataId?: string) => save(values, dataId),
  },
}));

function field(overrides: Partial<ConfigField> = {}): ConfigField {
  return {
    alias: "TOP_K",
    group: "retrieval",
    summary: "Results per source before reranking.",
    type: "int",
    value: 4,
    default: 4,
    layer: "default",
    editable_here: true,
    requires_restart: false,
    ...overrides,
  };
}

afterEach(() => {
  // Auto-cleanup only registers when vitest runs with globals; this project
  // imports its test helpers explicitly, so an uncleaned render leaks into the
  // next test and every query finds two of everything.
  cleanup();
  vi.clearAllMocks();
});

describe("AdminConfigEditor", () => {
  it("disables a field pinned in the process environment", async () => {
    schema.mockResolvedValue({
      config_centre_enabled: true,
      fields: [
        field(),
        field({ alias: "RERANKER_TOP_N", value: 9, layer: "environment", editable_here: false }),
      ],
    });

    render(<AdminConfigEditor />);

    await waitFor(() => expect(screen.getByRole("textbox", { name: "TOP_K" })).toBeEnabled());
    expect(screen.getByRole("textbox", { name: "RERANKER_TOP_N" })).toBeDisabled();
    expect(screen.getByText("environment")).toBeInTheDocument();
  });

  it("is read-only when no configuration centre is configured", async () => {
    schema.mockResolvedValue({ config_centre_enabled: false, fields: [field()] });

    render(<AdminConfigEditor />);

    await waitFor(() => expect(screen.getByRole("textbox", { name: "TOP_K" })).toBeDisabled());
    expect(screen.getByText("admin.config.noCentre")).toBeInTheDocument();
  });

  it("sends only the fields that were edited", async () => {
    schema.mockResolvedValue({
      config_centre_enabled: true,
      fields: [field(), field({ alias: "BM25_TOP_K", value: 6 })],
    });
    save.mockResolvedValue({ ok: true, data_id: "querymind", changed: ["TOP_K"], fields: [field({ value: 9 })] });

    render(<AdminConfigEditor />);
    await waitFor(() => expect(screen.getByRole("textbox", { name: "TOP_K" })).toBeEnabled());

    const input = screen.getByRole("textbox", { name: "TOP_K" });
    await userEvent.clear(input);
    await userEvent.type(input, "9");
    await userEvent.click(screen.getByText(/admin\.config\.save/));

    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(save).toHaveBeenCalledWith({ TOP_K: "9" }, undefined);
  });

  it("surfaces a refusal from the server instead of reporting a save", async () => {
    schema.mockResolvedValue({ config_centre_enabled: true, fields: [field()] });
    save.mockRejectedValue(new Error("pinned in the process environment"));

    render(<AdminConfigEditor />);
    await waitFor(() => expect(screen.getByRole("textbox", { name: "TOP_K" })).toBeEnabled());

    const input = screen.getByRole("textbox", { name: "TOP_K" });
    await userEvent.clear(input);
    await userEvent.type(input, "9");
    await userEvent.click(screen.getByText(/admin\.config\.save/));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("pinned in the process environment"));
  });
});
