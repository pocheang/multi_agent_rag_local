// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";
import { activateOnKey } from "@/lib/a11y";

/**
 * `typescript:S1082` flagged both divs in this dialog: the backdrop, which had
 * an onClick, and the panel inside it, whose onClick existed only to stop the
 * backdrop's from firing. Neither is a control, so the fix was not to give them
 * keyboard handlers -- a fake onKeyDown on a non-interactive div silences the
 * rule and invents a control for a screen reader to announce, which is worse
 * than leaving it alone.
 *
 * The backdrop says `role="presentation"` and decides for itself whether the
 * click landed on it, which deleted the inner handler outright. In passing, the
 * panel got the semantics it never had: a screen reader had no way to know this
 * was a modal, or what it was about.
 *
 * jsdom has no layout, so none of this could be checked by looking. It can read
 * the accessibility tree, which is the entire point of these assertions.
 */

afterEach(cleanup); // vitest runs without globals here, so it is not automatic

function open(onCancel = vi.fn(), onConfirm = vi.fn()) {
  render(
    <ConfirmDialog
      isOpen
      title="Delete session"
      message="This cannot be undone."
      onConfirm={onConfirm}
      onCancel={onCancel}
    />,
  );
  return { onCancel, onConfirm };
}

describe("the dialog announces itself as one", () => {
  it("is a modal dialog, not an anonymous div", () => {
    open();
    const dialog = screen.getByRole("dialog");

    expect(dialog.getAttribute("aria-modal")).toBe("true");
  });

  it("is labelled by its own title", () => {
    open();
    const dialog = screen.getByRole("dialog");
    const labelledBy = dialog.getAttribute("aria-labelledby");

    expect(labelledBy).toBeTruthy();
    expect(document.getElementById(labelledBy as string)?.textContent).toBe("Delete session");
  });

  it("does not present the backdrop as something to interact with", () => {
    const { container } = render(
      <ConfirmDialog isOpen title="t" message="m" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    const backdrop = container.querySelector(".confirm-dialog-overlay");

    expect(backdrop?.getAttribute("role")).toBe("presentation");
    expect(backdrop?.getAttribute("tabindex")).toBeNull();
  });
});

describe("dismissing it", () => {
  it("closes on a click that lands on the backdrop", () => {
    const { onCancel } = open();
    const backdrop = document.querySelector(".confirm-dialog-overlay") as HTMLElement;

    fireEvent.click(backdrop);

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("does not close on a click inside the panel", () => {
    /** The behaviour the deleted stopPropagation handler was there for. */
    const { onCancel } = open();

    fireEvent.click(screen.getByRole("dialog"));
    fireEvent.click(screen.getByText("This cannot be undone."));

    expect(onCancel).not.toHaveBeenCalled();
  });

  it("closes on Escape, which is the keyboard route", () => {
    const { onCancel } = open();

    fireEvent.keyDown(document, { key: "Escape" });

    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});

describe("activateOnKey", () => {
  /** For the two findings that *were* controls: a drop zone and a result card. */
  const press = (key: string) => {
    const activate = vi.fn();
    activateOnKey(activate)({ key, preventDefault: vi.fn() } as never);
    return activate;
  };

  it("activates on Enter and on Space", () => {
    expect(press("Enter")).toHaveBeenCalledTimes(1);
    expect(press(" ")).toHaveBeenCalledTimes(1);
  });

  it("ignores everything else", () => {
    for (const key of ["a", "Tab", "Escape", "ArrowDown", "Shift"]) {
      expect(press(key)).not.toHaveBeenCalled();
    }
  });

  it("stops Space from scrolling the page", () => {
    const preventDefault = vi.fn();
    activateOnKey(vi.fn())({ key: " ", preventDefault } as never);

    expect(preventDefault).toHaveBeenCalledTimes(1);
  });
});
