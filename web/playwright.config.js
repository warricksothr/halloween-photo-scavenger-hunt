import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.js',
  timeout: 45_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  // One worker: the specs share one served build, and the service-worker
  // spec rewrites dist/index.html to stand in for a deploy. Parallel
  // files would race that rewrite against the other spec.
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: [['list']],
  outputDir: '.playwright-results',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: {
    command:
      'PYTHONPATH=../server ../server/.venv/bin/python e2e/test-server.py --port 4173',
    url: 'http://127.0.0.1:4173/api/health',
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
