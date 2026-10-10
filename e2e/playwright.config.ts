import { defineConfig } from "@playwright/test";
import path from "node:path";
import os from "node:os";

// Browser end-to-end smoke tests (spec 13.2.4 / 13.3.7).
// They run against an ISOLATED stack started here: the API through scripts/dev_isolated_server.py (throw-away SQLite file, every external service blanked,
// refuses to start if anything points outside this machine) and the Next.js dev server. Nothing here can reach production data.
// The browser is the Chrome installed on the machine (channel "chrome"), so no browser download is needed.
const API_PORT = 8765;
const WEB_PORT = 3001;
const repoRoot = path.resolve(__dirname, "..");
const dbPath = path.join(os.tmpdir(), `rag-e2e-${Date.now()}.db`);
const python = process.env.PYTHON ?? (process.platform === "win32" ? path.join(repoRoot, ".venv", "Scripts", "python.exe") : "python3");

export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${WEB_PORT}`, channel: "chrome", headless: true, trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: [
    {
      command: `"${python}" scripts/dev_isolated_server.py`,
      cwd: repoRoot,
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      env: { PREVIEW_DB_PATH: dbPath, PREVIEW_PORT: String(API_PORT), RATE_LIMIT_ENABLED: "false" },
    },
    {
      command: `npx next dev -p ${WEB_PORT} --webpack`,
      cwd: path.join(repoRoot, "frontend"),
      url: `http://localhost:${WEB_PORT}/login`,
      reuseExistingServer: !process.env.CI,
      timeout: 600_000,
      env: { NEXT_PUBLIC_API_URL: `http://localhost:${API_PORT}` },
    },
  ],
});
