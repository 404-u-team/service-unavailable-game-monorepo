import { defineConfig, devices } from '@playwright/test';

const firefox = process.env.TEST_BROWSER === 'firefox';
const port = 6007;
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: './tests',
  use: {
    ...devices[firefox ? 'Desktop Firefox' : 'Desktop Chrome'],
    baseURL,
    trace: 'retain-on-failure'
  },
  webServer: {
    command: `bun run build-storybook && bun run vite preview --outDir storybook-static --host 127.0.0.1 --port ${port} --strictPort`,
    url: `${baseURL}/index.json`,
    timeout: 90_000
  }
});
