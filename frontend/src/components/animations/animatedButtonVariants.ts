import { cva, type VariantProps } from "class-variance-authority";

/**
 * The button's variant table, owned by the component.
 *
 * This exists because of a bug that shipped: `groups.css` styled
 * `.tiny-btn.danger` and `.tiny-btn.secondary`, class names nothing has ever
 * produced -- the component emits `animated-btn-lite--danger`. The colour rule
 * therefore never matched while an unconditional white background two rules
 * above it did, and every Delete button rendered white-on-white: contrast 1.0,
 * a blank rectangle beside every message. Nothing failed; a stylesheet was
 * simply describing a component that had moved.
 *
 * Template-literal class names cannot be checked by anything. A variant table
 * can: `VariantProps` makes the accepted values a type, `cva` makes the
 * emitted classes a value, and a stylesheet that wants to target one has a
 * single place to read it from.
 *
 * The classes below are still the existing hand-written ones, on purpose. The
 * appearance was tuned against real screenshots and is not what needed fixing;
 * moving them to Tailwind utilities is a separate step that can now happen one
 * variant at a time, inside this file, without touching a single call site.
 */
export const animatedButton = cva("animated-btn-lite", {
  variants: {
    variant: {
      primary: "animated-btn-lite--primary",
      secondary: "animated-btn-lite--secondary",
      ghost: "animated-btn-lite--ghost",
      danger: "animated-btn-lite--danger",
    },
    size: {
      small: "animated-btn-lite--small",
      medium: "animated-btn-lite--medium",
      large: "animated-btn-lite--large",
    },
    state: {
      idle: "animated-btn-lite--idle",
      loading: "animated-btn-lite--loading",
      success: "animated-btn-lite--success",
      error: "animated-btn-lite--error",
    },
  },
  defaultVariants: {
    variant: "primary",
    size: "medium",
    state: "idle",
  },
});

export type AnimatedButtonVariants = VariantProps<typeof animatedButton>;
