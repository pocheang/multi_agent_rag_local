import { useEffect } from "react";

interface WebVitalsMetric {
  name: string;
  value: number;
  id: string;
  navigationType: string;
}

/**
 * Performance monitoring hook using Web Vitals
 * Tracks: LCP, FID, CLS, FCP, TTFB
 */
export function usePerformanceMonitoring(enabled: boolean = true) {
  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;

    const observers: PerformanceObserver[] = [];

    // Report metrics to console (can be sent to analytics service)
    const reportMetric = (metric: WebVitalsMetric) => {
      console.log(`[Performance] ${metric.name}:`, metric.value.toFixed(2), "ms");

      // TODO: Send to analytics service
      // analytics.track('web-vitals', {
      //   metric: metric.name,
      //   value: metric.value,
      //   id: metric.id
      // });
    };

    // Measure Largest Contentful Paint (LCP)
    const observeLCP = () => {
      if (!("PerformanceObserver" in window)) return;

      try {
        const observer = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          const lastEntry = entries[entries.length - 1] as PerformanceEntry;
          if (lastEntry) {
            reportMetric({
              name: "LCP",
              value: lastEntry.startTime,
              id: String(lastEntry.entryType),
              navigationType: "navigate",
            });
          }
        });
        observer.observe({ entryTypes: ["largest-contentful-paint"] });
        observers.push(observer);
      } catch (e) {
        console.warn("LCP observation failed:", e);
      }
    };

    // Measure First Input Delay (FID)
    const observeFID = () => {
      if (!("PerformanceObserver" in window)) return;

      try {
        const observer = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          entries.forEach((entry) => {
            const fidEntry = entry as PerformanceEventTiming;
            reportMetric({
              name: "FID",
              value: fidEntry.processingStart - fidEntry.startTime,
              id: String(entry.entryType),
              navigationType: "navigate",
            });
          });
        });
        observer.observe({ entryTypes: ["first-input"] });
        observers.push(observer);
      } catch (e) {
        console.warn("FID observation failed:", e);
      }
    };

    // Measure Cumulative Layout Shift (CLS)
    const observeCLS = () => {
      if (!("PerformanceObserver" in window)) return;

      let clsValue = 0;
      try {
        const observer = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (!(entry as LayoutShift).hadRecentInput) {
              clsValue += (entry as LayoutShift).value;
            }
          }
          reportMetric({
            name: "CLS",
            value: clsValue,
            id: "cls",
            navigationType: "navigate",
          });
        });
        observer.observe({ entryTypes: ["layout-shift"] });
        observers.push(observer);
      } catch (e) {
        console.warn("CLS observation failed:", e);
      }
    };

    observeLCP();
    observeFID();
    observeCLS();

    // Measure page load time
    const reportPageLoad = () => {
      if (window.performance && window.performance.timing) {
        const timing = window.performance.timing;
        const loadTime = timing.loadEventEnd - timing.navigationStart;
        console.log(`[Performance] Page Load Time: ${loadTime}ms`);
      }
    };
    window.addEventListener("load", reportPageLoad);

    return () => {
      observers.forEach((observer) => observer.disconnect());
      window.removeEventListener("load", reportPageLoad);
    };
  }, [enabled]);
}

// Type definitions for PerformanceObserver entries
interface PerformanceEventTiming extends PerformanceEntry {
  processingStart: number;
}

interface LayoutShift extends PerformanceEntry {
  value: number;
  hadRecentInput: boolean;
}
