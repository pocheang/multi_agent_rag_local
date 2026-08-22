import { useState, useEffect } from "react";

export function useSectionToggle() {
  const [sectionsHidden, setSectionsHidden] = useState(() => {
    const stored = localStorage.getItem("chatSectionsHidden");
    return stored === "true";
  });

  useEffect(() => {
    localStorage.setItem("chatSectionsHidden", String(sectionsHidden));

    // Toggle classes on the panels (not topbar)
    const executionPanels = document.querySelectorAll(".execution-trace-panel, .tool-approval-panel");
    const composerPanels = document.querySelectorAll(".composer-panel");

    executionPanels.forEach((panel) => {
      if (sectionsHidden) {
        panel.classList.add("hidden");
      } else {
        panel.classList.remove("hidden");
      }
    });

    composerPanels.forEach((panel) => {
      if (sectionsHidden) {
        panel.classList.add("hidden");
      } else {
        panel.classList.remove("hidden");
      }
    });
  }, [sectionsHidden]);

  const toggleSections = () => {
    setSectionsHidden((prev) => !prev);
  };

  return { sectionsHidden, toggleSections };
}

export function useTopbarToggle() {
  const [topbarHidden, setTopbarHidden] = useState(() => {
    const stored = localStorage.getItem("chatTopbarHidden");
    return stored === "true";
  });

  useEffect(() => {
    localStorage.setItem("chatTopbarHidden", String(topbarHidden));

    // Toggle classes on the topbar
    const topbars = document.querySelectorAll(".topbar");

    topbars.forEach((topbar) => {
      if (topbarHidden) {
        topbar.classList.add("hidden");
      } else {
        topbar.classList.remove("hidden");
      }
    });
  }, [topbarHidden]);

  const toggleTopbar = () => {
    setTopbarHidden((prev) => !prev);
  };

  return { topbarHidden, toggleTopbar };
}
