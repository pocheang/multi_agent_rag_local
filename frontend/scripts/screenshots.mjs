#!/usr/bin/env node
/**
 * Capture the app's main states to PNG.
 *
 * This exists because the defects that cost the most in the 2026-08-31 pass
 * were invisible to the test suite and obvious on screen: a Delete button
 * rendering white on white, expanded panels clipped to a third of their height,
 * floating buttons sitting on the message text, an input area taking 68% of a
 * phone viewport. Every suite was green through all of it. A screenshot run is
 * the only artefact that would have shown any of them.
 *
 * Deliberately a local tool, not a CI gate. Gating on pixels needs a seeded
 * corpus and a pinned font stack, and without those it fails on the day
 * somebody upgrades Chromium rather than the day the UI breaks. Run it before
 * and after a change and look at the pair.
 *
 * Needs both servers up:
 *   uvicorn app.api.main:app --port 8000
 *   npm run dev
 *
 * Then:  npm run screenshots
 *
 * On a machine that has never run this, install the browser first:
 *   npx playwright install chromium
 * `npm ci --ignore-scripts` is what CI and the frontend image use now, and
 * Playwright downloads its browser from a postinstall hook -- so the package
 * arrives without one. The download is cached per user, not per checkout, so
 * this is a once-per-machine step, not a once-per-clone one.
 *
 * Credentials come from the environment so nothing usable is committed:
 *   SHOT_USER, SHOT_PASSWORD   (default: the local walkthrough account)
 *   SHOT_BASE                  (default: http://localhost:5173)
 *   SHOT_OUT                   (default: docs/.../screenshots next to the log)
 */

import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "../..");

const BASE = process.env.SHOT_BASE ?? "http://localhost:5173";
const USER = process.env.SHOT_USER ?? "walkthrough_alice";
const PASSWORD = process.env.SHOT_PASSWORD ?? "";
const OUT = process.env.SHOT_OUT ?? join(repo, "docs/development/daily-logs/2026-08-31/screenshots");

const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 375, height: 812 };

/** Give the shell a moment to settle: fonts, the SSE subscription, layout. */
async function settle(page, ms = 900) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(ms);
}

async function shot(page, name) {
  const file = join(OUT, `${name}.png`);
  await page.screenshot({ path: file });
  console.log("  " + name + ".png");
}

async function signIn(page) {
  await page.goto(`${BASE}/app`, { waitUntil: "domcontentloaded" });
  await settle(page);

  // Already authenticated from a previous run's storage state.
  if (await page.locator(".page-shell").count()) return;

  const username = page.getByPlaceholder("Username");
  await username.waitFor({ timeout: 15000 });
  await username.fill(USER);
  await page.getByPlaceholder("Password").fill(PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.locator(".page-shell").waitFor({ timeout: 20000 });
  await settle(page);
}

/**
 * The sidebar is a persistent column above 1080px and an off-canvas drawer
 * below it, and one button drives both -- so "open it" means "toggle unless it
 * is already open", not "click once".
 *
 * The open test has to be the `.open` class, which is what the responsive CSS
 * keys on. A visibility check does not work: a drawer pushed off-screen with
 * `translateX(-104%)` still reports as visible, so the first version of this
 * silently skipped the click and captured the chat view twice.
 */
async function openSidebar(page) {
  const sidebar = page.locator(".sidebar");
  const wide = (page.viewportSize()?.width ?? 0) > 1080;
  const isOpen = wide
    ? !(await page.locator(".page-shell.sidebar-collapsed").count())
    : await sidebar.evaluate((el) => el.classList.contains("open"));

  if (!isOpen) {
    await page.getByRole("button", { name: /sessions and tools/i }).click();
    await page.waitForTimeout(600);
  }

  const opened = wide
    ? !(await page.locator(".page-shell.sidebar-collapsed").count())
    : await sidebar.evaluate((el) => el.classList.contains("open"));
  if (!opened) throw new Error("sidebar did not open — the capture would repeat the previous shot");
}

async function main() {
  if (!PASSWORD) {
    console.error("Set SHOT_PASSWORD (and SHOT_USER if not walkthrough_alice).");
    process.exit(1);
  }
  mkdirSync(OUT, { recursive: true });
  console.log(`capturing ${BASE} -> ${OUT}\n`);

  const browser = await chromium.launch();

  // --- desktop -------------------------------------------------------------
  const desktop = await browser.newContext({ viewport: DESKTOP, deviceScaleFactor: 2 });
  const page = await desktop.newPage();
  await signIn(page);

  await shot(page, "01-desktop-chat");

  await openSidebar(page);
  await shot(page, "02-desktop-sidebar");

  const collapseAll = page.getByRole("button", { name: /collapse all/i });
  if (await collapseAll.count()) {
    await collapseAll.click();
    await page.waitForTimeout(400);
    await shot(page, "03-desktop-workbench-collapsed");

    await page.getByRole("button", { name: /expand all/i }).click();
    await page.waitForTimeout(500);
    await shot(page, "04-desktop-workbench-expanded");
  }

  // The auth screen, which is what a first-time visitor actually sees.
  const anon = await browser.newContext({ viewport: DESKTOP, deviceScaleFactor: 2 });
  const anonPage = await anon.newPage();
  await anonPage.goto(`${BASE}/app/login?mode=login`, { waitUntil: "domcontentloaded" });
  await settle(anonPage);
  await shot(anonPage, "05-desktop-login");
  await anon.close();

  // --- mobile --------------------------------------------------------------
  const phone = await browser.newContext({ viewport: MOBILE, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const small = await phone.newPage();
  await signIn(small);
  await shot(small, "06-mobile-chat");

  await openSidebar(small);
  await shot(small, "07-mobile-sidebar");

  const anonPhone = await browser.newContext({ viewport: MOBILE, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const anonSmall = await anonPhone.newPage();
  await anonSmall.goto(`${BASE}/app/login?mode=login`, { waitUntil: "domcontentloaded" });
  await settle(anonSmall);
  await shot(anonSmall, "08-mobile-login");

  await browser.close();
  console.log("\ndone");
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
