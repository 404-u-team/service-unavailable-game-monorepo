import { expect, test, type Page } from '@playwright/test';
import type { Game } from '../src/lib/types';

async function start(page: Page, tutorial = false) {
  await page.goto('/');
  const response = await page.request.post('/api/games', {
    data: { id: crypto.randomUUID(), name: 'Live workbench', seed: 7, settings: { show_tutorial: tutorial } }
  });
  expect(response.ok()).toBeTruthy();
  const game: Game = await response.json();
  await page.goto(`/game/${game.id}`);
  await expect(page.getByRole('group', { name: 'Game speed' })).toBeVisible();
  return game;
}

test('live socket reconnects across tabs without polling and shortcuts respect editable fields', async ({ page, context }) => {
  let reads = 0;
  let dropLive: (() => void) | undefined;
  await page.routeWebSocket('**/api/games/*/live', (client) => {
    const server = client.connectToServer();
    dropLive = () => { client.close({ code: 1012 }); server.close({ code: 1012 }); };
  });
  const sockets: string[] = [];
  page.on('websocket', (socket) => { if (socket.url().endsWith('/live')) sockets.push(socket.url()); });
  const initial = await start(page);
  await expect.poll(() => sockets.length).toBe(1);
  await page.route(`**/api/games/${initial.id}`, (route) => {
    reads++;
    return route.abort();
  });
  await page.locator('body').click({ position: { x: 2, y: 2 } });
  await page.keyboard.press('3');
  const speed = page.getByRole('button', { name: 'Fast speed (5×)' });
  await expect(speed).toHaveAttribute('aria-pressed', 'true');
  const other = await context.newPage();
  await other.goto(`/game/${initial.id}`);
  await expect(other.getByRole('button', { name: 'Fast speed (5×)' })).toHaveAttribute('aria-pressed', 'true');
  const currentTime = await page.locator('.time').textContent();
  await expect(page.locator('.time')).not.toHaveText(currentTime!);
  const search = page.getByRole('searchbox', { name: 'Search components' });
  await search.focus();
  await page.keyboard.press('1');
  await expect(search).toHaveValue('1');
  await expect(speed).toHaveAttribute('aria-pressed', 'true');
  expect(dropLive).toBeDefined();
  dropLive?.();
  await expect(page.getByText('Live connection lost. Reconnecting…')).toBeVisible();
  await expect(page.getByText('Live connection lost. Reconnecting…')).toHaveCount(0);
  await expect.poll(() => sockets.length).toBeGreaterThan(1);
  await other.getByRole('button', { name: 'Pause simulation' }).click();
  await expect(page.getByRole('button', { name: 'Pause simulation' })).toHaveAttribute('aria-pressed', 'true');
  expect(reads).toBe(0);
});

test('wheel and middle drag navigate the canvas, and newly added nodes stay in view', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const initial = await start(page);
  const canvas = page.locator('.svelte-flow');
  const transform = () => page.locator('.svelte-flow__viewport').evaluate((element) => {
    const matrix = new DOMMatrix(getComputedStyle(element).transform);
    return { x: matrix.e, y: matrix.f, zoom: matrix.a };
  });
  const bounds = (await canvas.boundingBox())!;
  await page.mouse.move(bounds.x + bounds.width * .55, bounds.y + bounds.height * .38);
  const initialView = await transform();
  await page.mouse.wheel(0, 180);
  await expect.poll(async () => (await transform()).y).toBeLessThan(initialView.y - 10);
  const scrolled = await transform();
  await page.keyboard.down('Shift');
  await page.mouse.wheel(0, 160);
  await page.keyboard.up('Shift');
  await expect.poll(async () => (await transform()).x).toBeLessThan(scrolled.x - 10);
  await page.keyboard.down('Control');
  await page.mouse.wheel(0, -200);
  await page.keyboard.up('Control');
  await expect.poll(async () => (await transform()).zoom).toBeGreaterThan(scrolled.zoom);
  const zoomed = await transform();
  await page.mouse.down({ button: 'middle' });
  await page.mouse.move(bounds.x + bounds.width * .55 + 90, bounds.y + bounds.height * .38 + 50, { steps: 5 });
  await page.mouse.up({ button: 'middle' });
  await expect.poll(async () => (await transform()).x).toBeGreaterThan(zoomed.x + 25);

  await page.getByRole('button', { name: 'Add node' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Cache', exact: true }).click();
  const node = canvas.locator('.svelte-flow__node[aria-label="Cache"]');
  await expect(node).toBeVisible();
  const box = (await node.boundingBox())!;
  expect(box.x).toBeGreaterThanOrEqual(bounds.x - 1);
  expect(box.y).toBeGreaterThanOrEqual(bounds.y - 1);
  expect(box.x + box.width).toBeLessThanOrEqual(bounds.x + bounds.width + 1);
  expect(box.y + box.height).toBeLessThanOrEqual(bounds.y + bounds.height + 1);
  await page.keyboard.press('Control+s');
  await expect(page.getByText('Game saved', { exact: true })).toBeVisible();
  const data: Game = await (await page.request.get(`/api/games/${initial.id}`)).json();
  expect(data.diagram.viewports?.wide?.zoom).toBeGreaterThan(initialView.zoom);
  expect(data.production).toEqual(initial.production);
  await page.reload();
  await expect(node).toBeVisible();
  await expect.poll(async () => (await transform()).zoom).toBeCloseTo(data.diagram.viewports!.wide!.zoom);
});

test('spotlight progress resumes after reload and advances from a real inspector selection', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await start(page, true);
  const guide = page.getByRole('complementary', { name: 'Guided onboarding' });
  await expect(guide).toContainText('Step 1 of 9');
  await expect(page.locator('.spotlight')).toBeVisible();
  await guide.getByRole('button', { name: 'Next' }).click();
  await expect(guide).toContainText('Step 2 of 9');
  await page.reload();
  await expect(guide).toContainText('Step 2 of 9');
  await guide.getByRole('button', { name: 'Next' }).click();
  await expect(guide).toContainText('Step 3 of 9');
  await page.locator('.svelte-flow__node[data-id="api"]').click();
  await expect(guide).toContainText('Step 4 of 9');
  await guide.getByRole('button', { name: 'Skip tutorial' }).click();
  await expect(guide).toHaveCount(0);
  await page.reload();
  await expect(guide).toHaveCount(0);
  await page.goto(page.url() + '?view=settings');
  await page.getByRole('button', { name: 'Resume tutorial' }).click();
  await expect(guide).toContainText('Step 4 of 9');
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('raw utilization values render equal meter fills in English and Russian', async ({ page }) => {
  const game = await start(page);
  const values = [0, .125, .35, .78, .99, 1];
  const sample = JSON.parse(JSON.stringify(game)) as Game;
  sample.snapshot.components.api = {
    status: 'healthy', rps: 1, throughput: 1, latency: 1,
    utilization: Object.fromEntries(values.map((value, index) => [`Resource ${index}`, value])),
    active_instances: 1, cache_hit: null, backlog: null, storage_used: null, replication_lag: null,
    queue_wait_minutes: null, jobs_dropped: null, jobs_expired: null
  };
  await page.route(`**/api/games/${game.id}`, (route) => route.fulfill({ json: sample }));
  await page.routeWebSocket(`**/api/games/${game.id}/live`, (socket) => {
    socket.send(JSON.stringify({ type: 'snapshot', seq: 1, state: sample }));
  });

  for (const [locale, label] of [['en', 'Metrics'], ['ru', 'Метрики']]) {
    await page.evaluate((value) => localStorage.setItem('workbench-language', value), locale);
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('lang', locale);
    await page.getByRole('button', { name: label, exact: true }).click();
    for (const [index, value] of values.entries()) {
      const meter = page.getByRole('meter', { name: `Resource ${index}` });
      await expect(meter).toHaveAttribute('aria-valuenow', String(value * 100));
      const width = await meter.evaluate((bar) => {
        const fill = bar.firstElementChild!.getBoundingClientRect().width;
        return fill / bar.getBoundingClientRect().width;
      });
      expect(width).toBeCloseTo(value, 2);
    }
  }
});
