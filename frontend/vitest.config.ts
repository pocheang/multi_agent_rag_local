import { defineConfig } from "vitest/config";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    // The default for everything that does not need a DOM. A component test
    // opts in per file with `// @vitest-environment jsdom` rather than paying
    // jsdom setup for the pure-logic suites, which are most of them.
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    coverage: {
      provider: "v8",
      // lcov is what Sonar reads; text-summary is the one line CI prints so
      // the number is visible on a run where the scan is skipped.
      reporter: ["text-summary", "lcov"],
      reportsDirectory: "coverage",
      include: ["src/**/*.{ts,tsx}"],
      // Declarations and the bootstrap have nothing to cover, and counting
      // them makes the number say less than it looks like it says.
      exclude: ["src/**/*.d.ts", "src/main.tsx"],
    },
  },
});
