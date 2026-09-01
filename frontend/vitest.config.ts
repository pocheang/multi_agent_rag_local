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
  },
});
