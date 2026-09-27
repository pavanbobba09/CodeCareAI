import { defineConfig, devices } from "@playwright/test";

// Local-only end-to-end run (owner decision Q): the fake LLM, the real backend on the local
// dev database (FY2027 tables loaded), and the Next.js app, on ports that do not clash with
// a normal dev setup. The backend reaches the fake LLM only through LLM_* env vars.
const API = "http://localhost:8010";
const WEB = "http://localhost:3010";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: WEB, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "../backend/.venv/bin/python ../scripts/fake_llm.py --port 8765",
      port: 8765,
      reuseExistingServer: false,
    },
    {
      command: "../backend/.venv/bin/uvicorn app.main:app --port 8010",
      cwd: "../backend",
      url: `${API}/api/v1/health`,
      reuseExistingServer: false,
      env: {
        LLM_BASE_URL: "http://127.0.0.1:8765/v1",
        LLM_API_KEY: "fake",
        LLM_MODEL: "fake-replay",
        FRONTEND_ORIGIN: WEB,
      },
    },
    {
      // A production build: no on-demand route compiling during the test.
      // NEXT_PUBLIC_API_BASE_URL is inlined at build time, so it is set for the build too.
      command: "npx next build && npx next start --port 3010",
      url: WEB,
      timeout: 240_000,
      reuseExistingServer: false,
      env: { NEXT_PUBLIC_API_BASE_URL: API },
    },
  ],
});
