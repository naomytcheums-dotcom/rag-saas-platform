import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
    // Page tests drive real user events through jsdom; on a loaded CI runner or dev machine the 5s default made them time out
    // intermittently (they pass in isolation). A longer limit, not a weaker assertion.
    testTimeout: 20000,
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
    },
  },
});
