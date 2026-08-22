# Tailwind CSS Full-Project Migration Design

**Date:** 2026-08-22

**Status:** Approved design

**Baseline commit:** `eea13d468fe17fb857568e5345582cd2a6ae37c8`

**Scope:** `frontend/`

## Summary

Migrate every project-authored frontend style to Tailwind CSS while preserving the current appearance and behavior. The migration will use Tailwind CSS v4 with the official Vite plugin and proceed in independently verifiable batches. Project-authored legacy CSS will be removed completely; official CSS shipped by third-party packages is the only allowed exception.

The current frontend is React 18, TypeScript, and Vite. The inventory contains 88 CSS files totaling 428,410 bytes, 99 TSX files, route-specific CSS splitting, light and dark themes, responsive layouts, animations, critical-CSS extraction, PurgeCSS, React Flow, and Recharts.

## Goals

- Preserve the current visual appearance and interaction behavior by default.
- Migrate all project-authored selectors and style rules to Tailwind utilities.
- Delete all project-authored legacy CSS after its consumers are migrated.
- Keep the existing `data-theme="light|dark"` and `localStorage` theme behavior.
- Keep official third-party package CSS only where the package depends on it.
- Maintain a buildable, testable, and independently reversible state after every batch.
- Add automated visual, interaction, accessibility, and anti-regression checks.
- Permit objective UI defects to be corrected in separate, documented `fix(ui)` changes.

## Non-Goals

- A general visual redesign.
- Replacing React Flow, Recharts, Framer Motion, or another working third-party package.
- Introducing a new component framework or a large variant-management dependency.
- Refactoring application state, API contracts, routing, or business behavior unrelated to styling.
- Supporting browsers older than Safari 16.4, Chrome 111, or Firefox 128.

## Decisions

### Tailwind version and integration

- Use Tailwind CSS v4.
- Use the official `@tailwindcss/vite` plugin.
- Add one project entry file: `frontend/src/styles/tailwind.css`.
- During migration, import Tailwind theme and utilities without Preflight.
- Enable official Tailwind Preflight only after all application components have migrated.

### Authored CSS boundary

The final project may contain one Tailwind entry file, but it must contain only Tailwind configuration directives:

- Tailwind imports.
- `@theme` design tokens.
- The custom dark variant for `[data-theme=dark]`.
- Tailwind-managed animation definitions associated with `--animate-*` tokens.

The entry file must not contain project selectors, legacy semantic classes, `@apply`, or compatibility rules.

Official third-party package CSS is allowed through an explicit whitelist. The initial whitelist contains:

- `reactflow/dist/style.css`

Any additional exception requires a package-level reason and must originate from `node_modules`, not from the project.

### Migration strategy

Use a hybrid progressive migration:

1. Establish visual baselines and Tailwind infrastructure.
2. Migrate design tokens and genuinely shared UI units.
3. Migrate simple routes.
4. Migrate analytics and architecture routes.
5. Migrate the admin route.
6. Migrate the chat shell and navigation.
7. Migrate complex chat content and runtime features.
8. Migrate remaining independent components.
9. Enable Preflight, remove the legacy toolchain, and enforce the final boundary.

Legacy CSS may coexist with Tailwind only while it still has unmigrated consumers. A migrated component may not retain a dependency on a legacy semantic style class.

## Architecture

### Styling data flow

The styling flow will be:

```text
component props/state
  -> static variant map
  -> cn()
  -> complete Tailwind utility tokens
  -> Tailwind/Vite generated CSS
```

Add `frontend/src/lib/cn.ts` as a small wrapper around the existing `clsx` dependency. Do not add a separate class-variance dependency. Variant maps must contain complete statically detectable utility strings.

Allowed:

```ts
const toneClasses = {
  success: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200",
  warning: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-200",
  danger: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-200",
} as const;
```

Disallowed:

```ts
const className = `bg-${color}-500`;
```

### Design tokens

Translate the current, actually used values into Tailwind v4 theme variables:

- Brand, surface, panel, text, border, success, warning, and danger colors.
- Spacing values that are not represented accurately by Tailwind defaults.
- Border radii, shadows, font families, font sizes, and custom breakpoints.
- Animation durations, easing functions, and keyframes.

Light and dark values remain explicit. Components use normal utilities for the light appearance and `dark:` variants for the dark appearance. The existing `applyTheme()` function continues to set `data-theme` on the document root.

Do not mechanically preserve every legacy variable. A token is retained only if a migrated component consumes it or it is required to reproduce the approved baseline.

### Preflight isolation

Tailwind Preflight resets margins, borders, headings, lists, and media elements globally. Enabling it at the start would change unmigrated routes. The coexistence phase therefore imports only Tailwind theme and utilities. After every application component has explicit Tailwind styling, enable Preflight and run the complete visual and interaction matrix before removing the legacy reset.

### Shared UI boundaries

Normalize only patterns that already repeat in the application:

- Controls: buttons, auth inputs, admin form fields, selects, and toggles.
- Containers: cards, panels, modals, and dropdowns.
- Status UI: badges, status panels, spinners, skeletons, and toasts.
- Feedback: confirmation dialogs, error boundaries, and loading states.
- Tables: pagination, headers, row states, and empty states.

Page-specific layout remains with its page or feature component. Migration is not a reason to create a generic component for every repeated utility string.

### Third-party components

Keep official package CSS when the package owns internal markup and behavioral styles. Apply project-specific layout, color, size, and state adjustments through Tailwind classes on supported wrappers and component props. Do not copy third-party CSS into the repository.

## Migration Batches

### Batch 0: Baseline and infrastructure

- Record the CSS inventory and current production CSS size.
- Add deterministic Playwright fixtures and visual snapshots.
- Add Tailwind v4 and the Vite plugin.
- Add `tailwind.css` without Preflight.
- Add `cn()` and static class-map conventions.
- Add style-boundary checks in non-blocking migration mode.

### Batch 1: Shared controls and feedback

- Buttons and button groups.
- Auth and admin form fields.
- Language and theme controls.
- Badges and status states.
- Spinner, skeleton, toast, and animated button components.
- Confirm dialog, error boundaries, modal, and dropdown shells.

Delete a shared CSS file only after every consumer of its selectors has migrated.

### Batch 2: Authentication and profile routes

- Login.
- Forgot password.
- Change password.
- Profile.
- Not found and route fallback states.

Remove the auth and profile CSS entry imports after all shared auth consumers pass visual and interaction tests.

### Batch 3: Public and reporting routes

- Landing.
- Architecture.
- Analytics.
- Data-flow visualization wrappers.

Keep React Flow's official stylesheet. Migrate only project-authored React Flow overrides and surrounding layout.

### Batch 4: Admin route

- Admin shell and section navigation.
- Operations overview and diagnostics.
- System monitor and log views.
- RAG and model settings.
- User and administrator management.
- Audit log and web-activity dashboards.
- Admin tables, charts, forms, actions, empty states, and responsive layouts.

### Batch 5: Chat shell and navigation

- Chat page shell.
- Top bar and menus.
- Sidebar, responsive rail, backdrop, and modules.
- Session list and session states.
- Workbench container and document navigation.

### Batch 6: Chat content and composer

- Welcome state and quick actions.
- Messages and Markdown presentation.
- Thinking, streaming, and clarification states.
- Composer, selects, toggles, drag-and-drop, and file upload states.
- Citations, process steps, graph panels, and runtime panels.
- Chat-specific light and dark appearances.

### Batch 7: Remaining components

- Session export, import, search, metadata, and tags.
- API settings and integration panels.
- Multimodal image and table views.
- Execution trace and tool approval panels.
- Any source component not reached through the primary page batches.

### Batch 8: Final cutover

- Verify that dead backup sources such as `ChatPage.old.tsx` have no consumers, then delete them instead of migrating them.
- Enable Tailwind Preflight.
- Correct Preflight differences with utilities in the owning elements.
- Remove the legacy reset, theme, token, page, feature, component, and component-local CSS files.
- Remove legacy CSS imports and route entry files.
- Remove PurgeCSS dependencies and configuration.
- Remove critical-CSS extraction scripts and the inline-critical Vite plugin.
- Remove CSS-specific manual chunk rules that no longer apply.
- Switch the style-boundary check to strict final mode.

## Visual Parity

### Snapshot matrix

Create deterministic Playwright snapshots from baseline commit `eea13d468fe17fb857568e5345582cd2a6ae37c8`.

Viewports:

- Mobile: 390 x 844.
- Tablet: 768 x 1024.
- Desktop: 1440 x 900.

Themes:

- Light.
- Dark.

Routes:

- Landing.
- Login and authentication flows.
- Profile.
- Architecture.
- Analytics.
- Admin.
- Chat.

Representative states:

- Empty, loading, populated, and error.
- Menus and dialogs open.
- Sidebar expanded, collapsed, and mobile-open.
- Streaming and clarification UI.
- File drag-over and document lists.
- Tables, charts, graphs, and runtime panels.

Use fixed API mocks, fixed timestamps, stable fonts, disabled nondeterministic motion, a fixed Chromium build, and the same execution environment for baseline and comparison runs.

### Parity gate

Every migration batch must preserve:

- Geometry, spacing, typography, colors, borders, radii, and shadows.
- Responsive behavior across the three approved viewports.
- Light and dark appearance.
- Hover, focus, active, disabled, loading, and error states.
- Keyboard focus order and visible focus treatment.
- Scrolling, dragging, dropping, resizing, menus, and dialogs.
- Existing ARIA semantics and labels.

Screenshot differences must stay within an antialiasing tolerance and every changed region must be reviewed. A batch does not pass solely because its numerical pixel threshold passes.

## UI Defect and Redesign Policy

Migration commits are visual-equivalence changes. When migration reveals an objective defect such as overflow, insufficient contrast, an undersized touch target, inaccessible focus, or incorrect stacking:

1. Finish or preserve the equivalent migration state.
2. Capture the old screenshot and describe the defect.
3. Implement the correction in a separate `fix(ui)` commit.
4. Capture and approve the new screenshot.
5. Record the route, state, reason, and result in the Tailwind migration decision log.

Subjective restyling or layout restructuring requires separate approval. If a proposed redesign is not approved, the current appearance remains the target.

## Failure Handling and Rollback

- Do not delete legacy CSS when visual, interaction, type, lint, or build checks fail.
- Migrate each component atomically; do not leave it dependent on both a semantic legacy class and Tailwind indefinitely.
- Prefer precise arbitrary values and arbitrary variants to an unapproved visual change.
- Keep each batch in an independent commit or small commit series that can be reverted without reverting completed earlier batches.
- A failing batch remains incomplete until its failing evidence is resolved and rerun.
- If a third-party internal selector changes after a dependency upgrade, restore supported package usage rather than copying its CSS into the project.

## Testing Strategy

### Static checks

Retain and run:

- TypeScript type checking.
- ESLint.
- Prettier check.
- Production build.

Add `npm run check:styles` to detect:

- Project-authored CSS files outside the Tailwind entry.
- Project-authored CSS imports.
- `@apply`.
- Dynamic Tailwind utility construction.
- Remaining legacy semantic class names.
- Non-whitelisted third-party stylesheet imports.

At Batch 0, extract legacy selectors into a machine-readable migration inventory. The final check requires zero remaining application usages, excluding documented third-party selectors.

### Unit and component tests

The current Vitest configuration includes only `src/**/*.test.ts` under a Node environment, so existing `.test.tsx` files are not part of the test command. Keep Node tests unchanged and add a separate jsdom UI configuration for:

- `cn()` and variant maps.
- Theme switching.
- Shared controls and feedback components.
- Active, disabled, loading, and error states.
- Dialog, toast, and animation lifecycle behavior.

### Playwright tests

Promote the existing mocked `frontend/scripts/webapp-smoke.mjs` approach into a formal Playwright configuration and fixtures. Add:

- Route and critical interaction tests.
- Visual comparisons using `toHaveScreenshot()`.
- Production-preview smoke tests.
- Accessibility checks with `@axe-core/playwright` for WCAG A/AA automatically detectable issues.
- Manual keyboard and interaction checklists for behavior that automated accessibility scanning cannot prove.

### Verification commands

The final frontend verification surface will provide commands equivalent to:

```text
npm run test
npm run test:ui
npm run test:e2e
npm run test:visual
npm run type-check
npm run lint
npm run format:check
npm run build
npm run smoke:production
npm run check:styles
```

Add a frontend verification workflow that executes the deterministic checks in a fixed environment. Visual baselines may only be updated intentionally and their image diffs must be reviewed.

## Performance

- Record the current production CSS raw and gzip sizes before Tailwind is introduced.
- Record the final generated CSS raw and gzip sizes.
- Final CSS gzip size must not exceed the recorded baseline without a documented reason.
- Verify that theme initialization does not introduce a flash of the wrong theme.
- Verify that migrated pages do not introduce visible layout shift.
- Run smoke tests against `vite preview`, not only the development server.

## Completion Criteria

The migration is complete only when all of the following are true:

- All 88 inventoried project-authored CSS files have been migrated and removed or replaced by the single Tailwind configuration entry.
- All 99 inventoried TSX files and every actual runtime route have been inspected.
- There are no project-authored legacy CSS imports.
- There are no remaining application usages of inventoried legacy semantic style classes.
- There are no dynamically constructed Tailwind utilities.
- There is no `@apply`.
- Only explicitly whitelisted official third-party CSS is imported.
- Light and dark themes pass the approved route, state, and viewport matrix.
- Responsive, animation, keyboard, drag-and-drop, modal, streaming, bilingual, and accessibility behavior remains correct.
- Unit, UI, interaction, visual, accessibility, lint, format, type, build, style-boundary, and production smoke checks pass.
- All accepted UI changes are documented with before and after evidence.
- Legacy PurgeCSS, critical-CSS, and manual CSS-splitting machinery has been removed.
- Production CSS size has been measured and satisfies the approved budget.
- The Git worktree is clean and the migration remains split into reversible commits.

## Risks and Mitigations

### Tailwind utilities are missed in production

Risk: dynamic class construction is not detected by Tailwind's source scanner.

Mitigation: complete static variant maps, unit tests, production preview tests, and the style-boundary scanner.

### Legacy routes change before migration

Risk: Tailwind Preflight applies global resets.

Mitigation: disable Preflight during coexistence and enable it only at final cutover.

### CSS specificity changes the baseline

Risk: legacy rules and utilities overlap during a batch.

Mitigation: migrate components atomically, remove their old dependency in the same batch, and gate deletion on screenshots.

### Dark theme drifts from the current design

Risk: dark values become approximated by generic Tailwind colors.

Mitigation: encode the exact used colors as theme variables and require light/dark snapshots.

### Visual tests become flaky

Risk: fonts, animation, backend data, timestamps, or platform rendering change pixels.

Mitigation: deterministic mocks, fixed environment, stable fonts, frozen dynamic values, and reviewed antialiasing tolerance.

### Migration becomes a redesign

Risk: subjective improvements expand scope and make parity impossible to review.

Mitigation: visual-equivalence commits first; separate approved `fix(ui)` commits with evidence.

## References

- [Tailwind CSS: Vite installation](https://tailwindcss.com/docs/installation/using-vite)
- [Tailwind CSS: upgrade guide and browser requirements](https://tailwindcss.com/docs/upgrade-guide)
- [Tailwind CSS: dark mode with a data attribute](https://tailwindcss.com/docs/dark-mode)
- [Tailwind CSS: source detection and dynamic classes](https://tailwindcss.com/docs/detecting-classes-in-source-files)
- [Tailwind CSS: Preflight and disabling Preflight](https://tailwindcss.com/docs/preflight)
- [Tailwind CSS: theme variables](https://tailwindcss.com/docs/theme)
- [Playwright: visual comparisons](https://playwright.dev/docs/next/test-snapshots)
- [Playwright: accessibility testing](https://playwright.dev/docs/accessibility-testing)
