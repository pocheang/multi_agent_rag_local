#!/usr/bin/env node
/**
 * A ratchet over the shape and depth scales.
 *
 * The chat screen carried eight radii at once and eighteen distinct shadows.
 * That drift is cheap to prevent and expensive to undo, and it is the one
 * class of problem here that needs no framework at all -- just a rule that
 * says "not more than yesterday".
 *
 * Deliberately a ratchet rather than a hard ban: `src/**\/*.css` still holds
 * hundreds of off-scale radii and literal shadows, and rewriting them in one
 * pass would churn every file in the app to fix a cosmetic problem. Instead each
 * file's current count is frozen in `design-scale-baseline.json` -- which is the
 * only place the totals are stated, so this comment cannot drift out of date
 * with them; run the script to see today's numbers. A file may improve, never
 * regress, and a *new* file starts at zero. The same shape the Python suite
 * already uses for `KNOWN_OFFENDERS`.
 *
 * On the scale:  var(--shape-*) / var(--elev-*), or 8, 12, 16, 999px.
 * Off it:        any other literal.
 *
 * Run:  node scripts/check-design-scale.mjs        (check)
 *       node scripts/check-design-scale.mjs --write (re-freeze after a cleanup)
 */

import { readFileSync, writeFileSync, existsSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const BASELINE = join(here, "design-scale-baseline.json");

/** Values that are on the scale, or that carry no shape decision at all. */
const ALLOWED_RADIUS = new Set(["0px", "0", "8px", "12px", "16px", "999px", "9999px", "50%", "inherit", "initial", "unset"]);

function offScale(css) {
  let radii = 0;
  let shadows = 0;

  for (const match of css.matchAll(/border-radius:\s*([^;\n{}]+)/g)) {
    const value = match[1].trim();
    if (value.includes("var(")) continue; // a token is on the scale by definition
    if (value.split(/\s+/).every((part) => ALLOWED_RADIUS.has(part))) continue;
    radii += 1;
  }

  for (const match of css.matchAll(/box-shadow:\s*([^;\n{}]+)/g)) {
    const value = match[1].trim();
    if (value.includes("var(") || value === "none") continue;
    shadows += 1;
  }

  return { radii, shadows };
}

/** `fs.globSync` is still experimental and prints a warning on every CI run. */
function cssFiles(dir, acc = []) {
  for (const entry of readdirSync(join(root, dir), { withFileTypes: true })) {
    const next = dir + "/" + entry.name;
    if (entry.isDirectory()) cssFiles(next, acc);
    else if (entry.name.endsWith(".css")) acc.push(next);
  }
  return acc;
}

// Explicit comparator, not the default and not localeCompare: the baseline
// file's key order has to be identical on every machine, and localeCompare
// is locale-dependent.
const files = cssFiles("src").sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
const current = {};
for (const file of files) {
  const counts = offScale(readFileSync(join(root, file), "utf8"));
  if (counts.radii || counts.shadows) current[file.replaceAll("\\", "/")] = counts;
}

if (process.argv.includes("--write")) {
  writeFileSync(BASELINE, JSON.stringify(current, null, 2) + "\n");
  const totals = Object.values(current).reduce((a, c) => ({ radii: a.radii + c.radii, shadows: a.shadows + c.shadows }), { radii: 0, shadows: 0 });
  console.log(`frozen: ${Object.keys(current).length} files, ${totals.radii} off-scale radii, ${totals.shadows} literal shadows`);
  process.exit(0);
}

if (!existsSync(BASELINE)) {
  console.error("No baseline. Run: node scripts/check-design-scale.mjs --write");
  process.exit(1);
}

const baseline = JSON.parse(readFileSync(BASELINE, "utf8"));
const problems = [];

for (const [file, counts] of Object.entries(current)) {
  const was = baseline[file] ?? { radii: 0, shadows: 0 };
  if (counts.radii > was.radii) {
    problems.push(`${file}: ${counts.radii} off-scale border-radius (was ${was.radii})`);
  }
  if (counts.shadows > was.shadows) {
    problems.push(`${file}: ${counts.shadows} literal box-shadow (was ${was.shadows})`);
  }
}

if (problems.length) {
  console.error("Design scale regressed:\n");
  for (const p of problems) console.error("  " + p);
  console.error(`
Use the scale instead of a literal:

  border-radius: var(--shape-control);  /*  8px -- buttons, inputs, chips   */
  border-radius: var(--shape-card);     /* 12px -- cards, rows, panels      */
  border-radius: var(--shape-panel);    /* 16px -- large containers, modals */
  border-radius: var(--shape-pill);     /* badges, avatars                  */

  box-shadow: var(--elev-1);            /* resting surface                  */
  box-shadow: var(--elev-2);            /* hover, floating                  */
  box-shadow: var(--elev-3);            /* overlays                         */

Defined in src/styles/core/elevation.css. If a value genuinely does not belong
on the scale -- a chart bar, a scrollbar thumb -- re-freeze the baseline with
--write and say why in the commit.
`);
  process.exit(1);
}

const totals = Object.values(current).reduce((a, c) => ({ radii: a.radii + c.radii, shadows: a.shadows + c.shadows }), { radii: 0, shadows: 0 });
console.log(`design scale ok — ${totals.radii} off-scale radii, ${totals.shadows} literal shadows, none new`);
