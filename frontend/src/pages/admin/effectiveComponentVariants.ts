import { cva, type VariantProps } from "class-variance-authority";

/**
 * The status table for the "effective configuration" rows.
 *
 * Written as a variant table rather than `admin-effective-${status}` for the
 * reason `animatedButtonVariants.ts` records: a template literal produces class
 * names nothing can check against the stylesheet, and this project has already
 * shipped a rule that never matched anything.
 *
 * It very nearly happened again here. The first draft interpolated the status,
 * and the backend can emit four of them -- active, degraded, disabled,
 * unavailable -- while the CSS defined row styling for two. `disabled` and
 * `unavailable` would have rendered with the neutral default border, which is
 * exactly what "no rule matched" looks like, so nothing would have appeared
 * wrong. With the table, `VariantProps` makes the four a type and every one of
 * them has a class here that a stylesheet can be checked against.
 */
export const effectiveRow = cva("admin-effective-row", {
  variants: {
    status: {
      active: "admin-effective-active",
      degraded: "admin-effective-degraded",
      disabled: "admin-effective-disabled",
      unavailable: "admin-effective-unavailable",
    },
  },
  defaultVariants: { status: "active" },
});

export const effectiveStatusPill = cva("admin-effective-status", {
  variants: {
    status: {
      active: "admin-effective-status-active",
      degraded: "admin-effective-status-degraded",
      disabled: "admin-effective-status-disabled",
      unavailable: "admin-effective-status-unavailable",
    },
  },
  defaultVariants: { status: "active" },
});

export type EffectiveStatus = NonNullable<VariantProps<typeof effectiveRow>["status"]>;
