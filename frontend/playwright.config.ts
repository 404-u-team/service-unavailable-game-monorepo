import { defineConfig, devices } from '@playwright/test';

const firefox = process.env.TEST_BROWSER === 'firefox';
const executablePath = firefox ? process.env.FIREFOX_PATH : process.env.CHROMIUM_PATH;

export default defineConfig({
  testDir: './tests',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    ...devices[firefox ? 'Desktop Firefox' : 'Desktop Chrome'],
    baseURL: process.env.TEST_BASE_URL || 'http://127.0.0.1:5173',
    launchOptions: executablePath ? { executablePath } : undefined,
    trace: 'retain-on-failure'
  }
});
