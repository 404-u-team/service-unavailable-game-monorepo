import adapter from '@sveltejs/adapter-bun';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, loadEnv } from 'vite';
import { MAX_SAVE_BYTES } from './src/lib/save-limit.ts';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const api = new URL(process.env.CORE_API_URL || env.CORE_API_URL || 'http://127.0.0.1:8000');
  api.protocol = api.protocol === 'https:' ? 'wss:' : 'ws:';
  const proxy = { '^/api/games/[^/]+/live$': { target: api.origin, ws: true } };
  return { plugins: [sveltekit({ adapter: adapter({ serverOptions: { maxRequestBodySize: MAX_SAVE_BYTES + 1024 * 1024 } }) })], server: { proxy }, preview: { proxy } };
});
