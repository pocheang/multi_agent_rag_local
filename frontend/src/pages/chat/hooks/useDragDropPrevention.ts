import { useEffect } from "react";

/**
 * Prevents default drag and drop behavior on the window
 */
export function useDragDropPrevention() {
  useEffect(() => {
    const preventDefault = (evt: DragEvent) => evt.preventDefault();
    window.addEventListener("dragover", preventDefault);
    window.addEventListener("drop", preventDefault);

    return () => {
      window.removeEventListener("dragover", preventDefault);
      window.removeEventListener("drop", preventDefault);
    };
  }, []);
}
