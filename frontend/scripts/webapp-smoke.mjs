import { chromium } from "@playwright/test";

const baseURL = process.env.APP_BASE_URL || "http://127.0.0.1:4173";

const mockUser = {
  user_id: "u_demo",
  username: "demo_admin",
  role: "admin",
  status: "active",
};

const mockDocuments = [
  {
    filename: "incident-report.pdf",
    source: "/uploads/u_demo/incident-report.pdf",
    chunks: 12,
    agent_class: "pdf_text",
    owner_user_id: "u_demo",
    visibility: "private",
    exists_on_disk: true,
    in_uploads: true,
  },
  {
    filename: "network-hardening.md",
    source: "/uploads/u_demo/network-hardening.md",
    chunks: 6,
    agent_class: "cybersecurity",
    owner_user_id: "u_demo",
    visibility: "private",
    exists_on_disk: true,
    in_uploads: true,
  },
];

function jsonResponse(body, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  };
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  await context.route("**/*", async (route) => {
    const req = route.request();
    const url = req.url();
    const method = req.method();

    if (url.endsWith("/auth/me") && method === "GET") {
      await route.fulfill(jsonResponse(mockUser));
      return;
    }
    if (url.endsWith("/auth/logout") && method === "POST") {
      await route.fulfill(jsonResponse({ ok: true }));
      return;
    }
    if (url.endsWith("/sessions") && method === "GET") {
      await route.fulfill(jsonResponse([]));
      return;
    }
    if (url.endsWith("/sessions") && method === "POST") {
      await route.fulfill(
        jsonResponse({
          session_id: "s_demo",
          title: "New Session",
          messages: [],
        }),
      );
      return;
    }
    if (url.includes("/sessions/") && method === "GET") {
      await route.fulfill(
        jsonResponse({
          session_id: "s_demo",
          title: "New Session",
          messages: [],
        }),
      );
      return;
    }
    if (url.endsWith("/documents") && method === "GET") {
      await route.fulfill(jsonResponse(mockDocuments));
      return;
    }
    if (url.endsWith("/prompts") && method === "GET") {
      await route.fulfill(jsonResponse([]));
      return;
    }

    await route.continue();
  });

  await page.addInitScript(() => {
    localStorage.setItem("auth_token", "e2e-token");
  });

  await page.goto(`${baseURL}/`, { waitUntil: "networkidle" });

  await page.getByText("Agent Workbench").waitFor();
  await page.getByText("PDF Workbench").waitFor();
  await page.getByText("PDF/Image (1)").waitFor();

  await page.getByRole("button", { name: "Force pdf_text" }).click();
  await page.getByRole("button", { name: "Draft Question" }).click();
  const composer = page.locator(".composer-panel textarea");
  await composer.waitFor();
  const draft = await composer.inputValue();
  if (!draft.includes("incident-report.pdf")) {
    throw new Error("PDF draft question was not populated as expected.");
  }

  await composer.fill("<img src=x onerror=alert(1) />");
  const scriptCount = await page.locator("script").count();
  if (scriptCount < 1) {
    throw new Error("Unexpected DOM state: script tags missing.");
  }
  const xssMarker = await page.locator("script[data-test-xss]").count();
  if (xssMarker !== 0) {
    throw new Error("Unexpected script injection marker found.");
  }

  console.log("webapp smoke test passed");
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
