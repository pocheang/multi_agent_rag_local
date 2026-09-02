import type { KeyboardEvent } from "react";

/**
 * Keyboard activation for a control that had to be built out of a div.
 *
 * `typescript:S1082` found five of these. Two were not controls at all -- modal
 * backdrops -- and got `role="presentation"` instead; the rest are genuine
 * controls whose markup is a div because the styling needs one, and those need
 * to answer Enter and Space the way a button does.
 *
 * Space is prevented from scrolling the page, which is the half of this that is
 * easy to leave out and immediately obvious to anyone using it.
 *
 * Reach for a real `<button>` first. This is for the cases where wrapping the
 * content in one would change the layout, and it always comes with
 * `role="button"` and `tabIndex={0}` on the same element -- keyboard handling
 * without focusability is a listener nothing can reach.
 */
export function activateOnKey(activate: () => void) {
  return (event: KeyboardEvent) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      activate();
    }
  };
}
