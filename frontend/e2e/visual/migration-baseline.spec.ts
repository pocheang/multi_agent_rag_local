import { expect, test, type Page, type Route } from "@playwright/test";

type Language = "en" | "zh";

type BaselineCase = {
  name: string;
  path: string;
  ready: string;
  authenticated: boolean;
  language: Language;
  viewport: { width: number; height: number };
  settleMs?: number;
};

const FIXED_NOW = new Date("2026-08-23T08:00:00Z");

const mockUser = {
  user_id: "user_visual_admin",
  username: "visual-admin@example.test",
  display_name: "Visual Baseline Admin",
  role: "admin",
  status: "active",
  credit_balance: 500,
};

const mockSession = {
  session_id: "s_visual",
  title: "Tailwind migration visual baseline",
  updated_at: "2026-08-23T07:45:00Z",
  message_count: 2,
  pinned: true,
};

const mockSessionDetail = {
  ...mockSession,
  messages: [
    {
      message_id: "m_user_visual",
      role: "user",
      content: "Summarize the migration risks and preserve visual parity.",
      created_at: "2026-08-23T07:30:00Z",
      metadata: { citations: [] },
    },
    {
      message_id: "m_assistant_visual",
      role: "assistant",
      content:
        "The baseline captures routes, languages, and responsive boundaries before Tailwind utilities replace legacy CSS.",
      created_at: "2026-08-23T07:31:00Z",
      metadata: {
        route: "research",
        citations: [
          {
            source: "Migration design.md",
            document_id: "doc_visual",
            page: 1,
            content: "Visual snapshots are approval evidence, not disposable test output.",
          },
        ],
      },
    },
  ],
};

const mockDocuments = [
  {
    filename: "Migration design.md",
    source: "uploads/Migration design.md",
    chunks: 24,
    page_count: 1,
    document_id: "doc_visual",
    indexing_status: "ready",
    visibility: "private",
  },
];

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function preparePage(page: Page, options: Pick<BaselineCase, "authenticated" | "language">) {
  await page.addInitScript(({ authenticated, language }) => {
    localStorage.setItem("language", language);
    if (authenticated) localStorage.setItem("auth_token", "visual-baseline-token");
    else localStorage.removeItem("auth_token");

    // Baselines capture the initial route state. Disable background polling
    // so a refresh cannot restart chart animations during a screenshot.
    globalThis.setInterval = (() => 0) as typeof globalThis.setInterval;
  }, options);

  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new globalThis.URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (!["http:", "https:"].includes(url.protocol)) {
      return route.continue();
    }

    if (path === "/auth/me") {
      return options.authenticated ? json(route, mockUser) : json(route, { detail: "visual baseline guest" }, 401);
    }
    if (method === "GET" && path === "/sessions") {
      return json(route, [mockSession]);
    }
    if (method === "GET" && path === `/sessions/${mockSession.session_id}`) {
      return json(route, mockSessionDetail);
    }
    if (method === "GET" && path === "/documents") {
      return json(route, mockDocuments);
    }
    if (method === "GET" && path === "/prompts") {
      return json(route, []);
    }
    if (method === "GET" && path === "/user/api-settings") {
      return json(route, { has_openai_key: false, has_anthropic_key: false });
    }
    if (path === "/api/analytics/overview") {
      return json(route, {
        total_queries: 1248,
        success_rate: 98.7,
        avg_retrieval_time_ms: 386,
        avg_total_time_ms: 842,
        avg_retrieved_count: 7.4,
        agent_distribution: { research: 482, retrieval: 411, writer: 355 },
        route_distribution: { standard: 730, strict_quality: 311, advanced: 207 },
      });
    }
    if (path === "/api/analytics/agents") {
      return json(route, [
        {
          agent_class: "research",
          query_count: 482,
          success_rate: 99.1,
          avg_retrieval_time_ms: 760,
          avg_retrieved_count: 8.2,
        },
        {
          agent_class: "retrieval",
          query_count: 411,
          success_rate: 98.2,
          avg_retrieval_time_ms: 540,
          avg_retrieved_count: 6.7,
        },
        {
          agent_class: "writer",
          query_count: 355,
          success_rate: 98.8,
          avg_retrieval_time_ms: 910,
          avg_retrieved_count: 7.1,
        },
      ]);
    }
    if (path === "/api/analytics/documents") {
      return json(route, [
        { source: "Migration design.md", retrieval_count: 218, avg_score: 0.93 },
        { source: "Tailwind v4 upgrade notes.md", retrieval_count: 164, avg_score: 0.89 },
      ]);
    }
    if (path === "/admin/users") {
      return json(route, [{ ...mockUser, created_at: "2026-01-15T08:00:00Z", is_online: true }]);
    }
    if (path === "/admin/audit-logs") {
      return json(route, []);
    }
    if (path === "/admin/system-logs") {
      return json(route, { items: [], count: 0 });
    }
    if (path === "/admin/ops/overview") {
      return json(route, {
        status: "healthy",
        generated_at: "2026-08-23T08:00:00Z",
        window_hours: 24,
        kpi: {
          requests_total: 1248,
          requests_success: 1232,
          requests_error: 16,
          error_rate_percent: 1.3,
          active_users: 12,
          active_sessions: 18,
          queries: 86,
          uploads: 4,
          login_success: 22,
          login_failed: 1,
        },
        users: { total: 42, active: 39, disabled: 3, admin: 4 },
        top_actions: [
          { action: "query", count: 86 },
          { action: "upload", count: 4 },
        ],
        top_resource_types: [{ resource_type: "session", count: 104 }],
        top_error_reasons: [{ reason: "timeout", count: 3 }],
        slow_requests: [],
        hourly: [{ bucket: "2026-08-23T07:00:00Z", count: 61, errors: 1 }],
        services: {
          api: { ok: true, latency_ms: 18 },
          database: { ok: true, latency_ms: 7 },
          vector_store: { ok: true, latency_ms: 21 },
        },
      });
    }
    if (path === "/admin/ops/retrieval-profile") {
      return json(route, {
        active_profile: "advanced",
        config_default_profile: "advanced",
        follow_config_default: true,
        canary: { enabled: false, baseline_percent: 0, safe_percent: 0, seed: "visual" },
        updated_at: "2026-08-23T08:00:00Z",
        profiles: [{ id: "advanced", label: "Advanced", desc: "Balanced deterministic profile" }],
      });
    }
    if (path === "/admin/ops/benchmark/trends") {
      return json(route, { items: [], count: 0 });
    }
    if (path === "/admin/model-settings") {
      return json(route, {
        ok: true,
        settings: {
          enabled: false,
          provider: "local",
          api_key_masked: "",
          base_url: "",
          chat_model: "local-evidence",
          reasoning_model: "local-evidence",
          embedding_model: "local-hash-384",
          temperature: 0.7,
          max_tokens: 2048,
        },
      });
    }

    return route.continue();
  });
}

const desktop = { width: 1440, height: 1000 };

const cases: BaselineCase[] = [
  {
    name: "landing-en-light-desktop",
    path: "/",
    ready: ".landing-root",
    authenticated: false,
    language: "en",
    viewport: desktop,
  },
  {
    name: "login-en-light-desktop",
    path: "/app/login",
    ready: ".auth-root",
    authenticated: false,
    language: "en",
    viewport: desktop,
  },
  {
    name: "chat-en-light-desktop",
    path: "/app",
    ready: ".page-shell",
    authenticated: true,
    language: "en",
    viewport: desktop,
  },
  {
    name: "admin-en-light-desktop",
    path: "/app/admin",
    ready: ".admin-shell",
    authenticated: true,
    language: "en",
    viewport: desktop,
  },
  {
    name: "analytics-en-light-desktop",
    path: "/app/analytics",
    ready: ".analytics-page",
    authenticated: true,
    language: "en",
    viewport: desktop,
    settleMs: 2_500,
  },
  {
    name: "architecture-en-light-desktop",
    path: "/app/architecture",
    ready: ".architecture-shell",
    authenticated: true,
    language: "en",
    viewport: desktop,
    settleMs: 2_500,
  },
  {
    name: "profile-en-light-desktop",
    path: "/app/profile",
    ready: ".profile-page",
    authenticated: true,
    language: "en",
    viewport: desktop,
  },
  {
    name: "change-password-en-light-desktop",
    path: "/app/change-password",
    ready: ".change-password-card",
    authenticated: true,
    language: "en",
    viewport: desktop,
  },
  {
    name: "not-found-en-light-desktop",
    path: "/missing-visual-route",
    ready: ".not-found",
    authenticated: false,
    language: "en",
    viewport: desktop,
  },
  {
    name: "landing-zh-light-desktop",
    path: "/",
    ready: ".landing-root",
    authenticated: false,
    language: "zh",
    viewport: desktop,
  },
  {
    name: "login-zh-light-desktop",
    path: "/app/login",
    ready: ".auth-root",
    authenticated: false,
    language: "zh",
    viewport: desktop,
  },
  {
    name: "chat-zh-light-desktop",
    path: "/app",
    ready: ".page-shell",
    authenticated: true,
    language: "zh",
    viewport: desktop,
  },
  {
    name: "landing-en-light-mobile-375",
    path: "/",
    ready: ".landing-root",
    authenticated: false,
    language: "en",
    viewport: { width: 375, height: 812 },
  },
  {
    name: "chat-en-light-mobile-375",
    path: "/app",
    ready: ".page-shell",
    authenticated: true,
    language: "en",
    viewport: { width: 375, height: 812 },
  },
  {
    name: "chat-en-light-tablet-768",
    path: "/app",
    ready: ".page-shell",
    authenticated: true,
    language: "en",
    viewport: { width: 768, height: 1024 },
  },
  {
    name: "chat-en-light-sidebar-below-1079",
    path: "/app",
    ready: ".page-shell",
    authenticated: true,
    language: "en",
    viewport: { width: 1079, height: 900 },
  },
  {
    name: "chat-en-light-sidebar-above-1081",
    path: "/app",
    ready: ".page-shell",
    authenticated: true,
    language: "en",
    viewport: { width: 1081, height: 900 },
  },
];

for (const baseline of cases) {
  test(`migration baseline: ${baseline.name}`, async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.setViewportSize(baseline.viewport);
    await page.clock.setFixedTime(FIXED_NOW);
    await preparePage(page, baseline);
    await page.goto(baseline.path, { waitUntil: "networkidle" });

    await expect(page.locator(baseline.ready)).toBeVisible();
    if (baseline.settleMs) await page.waitForTimeout(baseline.settleMs);
    await expect(page).toHaveScreenshot(`${baseline.name}.png`, { fullPage: true });
    expect(pageErrors).toEqual([]);
  });
}
