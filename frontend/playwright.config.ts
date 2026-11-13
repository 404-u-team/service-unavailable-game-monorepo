import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    ...devices['Desktop Chrome'],
    baseURL: process.env.TEST_BASE_URL || 'http://127.0.0.1:5173',
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : undefined,
    trace: 'retain-on-failure'
  }
});
