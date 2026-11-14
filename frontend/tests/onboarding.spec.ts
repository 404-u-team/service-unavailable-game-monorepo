import { expect, test, type Locator, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { target } from '../src/lib/workbench/onboarding';
import type { Game } from '../src/lib/types';

const tutorial = (page: Page) => page.getByRole('complementary', { name: /Guided onboarding|Обучение/ });
const control = (page: Page, key: string) => {
  const selector = `[data-tutorial="${key}"]:visible`;
  return page.locator(`dialog[open] ${selector}, body:not(:has(dialog[open])) ${selector}`).first();
};
const highlight = (page: Page, key: string) => page.locator(`[data-tutorial-highlight="${key}"]`);
const button = (within: Page | Locator, name: string | RegExp) => within.getByRole('button', { name, exact: typeof name === 'string' });

async function start(page: Page, changes: Partial<Game> = {}) {
  await page.goto('/');
  const response = await page.request.post('/api/games', { data: { id: crypto.randomUUID(), name: 'Walkthrough', seed: 7 } });
  expect(response.ok(), await response.text()).toBeTruthy();
  const game: Game = await response.json();
  if (Object.keys(changes).length) {
    // Use the real server for every later mutation. Import the setup through its portable save endpoint.
    const exported = await page.request.get(`/api/games/${game.id}/export`);
    expect(exported.ok()).toBeTruthy();
    const data = await exported.json();
    Object.assign(data.game, changes);
    const imported = await page.request.post('/api/games/import', { data });
    expect(imported.ok(), await imported.text()).toBeTruthy();
    const copy: Game = await imported.json();
    await page.goto(`/game/${copy.id}`);
    await expect(tutorial(page)).toBeVisible();
    return copy;
  }
  await page.goto(`/game/${game.id}`);
  await expect(tutorial(page)).toBeVisible();
  return game;
}

async function clickTarget(page: Page, key: string) {
  await expect(highlight(page, key)).toBeVisible();
  await control(page, key).click();
}

async function step(page: Page, title: string | RegExp) {
  await expect(tutorial(page).getByRole('heading', { name: title, exact: typeof title === 'string' })).toBeVisible();
}

async function next(page: Page, name = 'Next') {
  await button(tutorial(page), name).click();
}

async function visibility(page: Page, key: string) {
  await expect(highlight(page, key)).toBeVisible();
  await expect.poll(async () => {
    const [popover, hole] = await Promise.all([tutorial(page).boundingBox(), highlight(page, key).boundingBox()]);
    if (!popover || !hole) return false;
    const { width, height } = page.viewportSize()!;
    const inside = popover.x >= 0 && popover.y >= 0 && popover.x + popover.width <= width + 1 && popover.y + popover.height <= height + 1;
    const overlap = popover.x < hole.x + hole.width && popover.x + popover.width > hole.x &&
      popover.y < hole.y + hole.height && popover.y + popover.height > hole.y;
    return inside && !overlap;
  }).toBeTruthy();
}

async function saveVisual(page: Page, label: string, browserName: string) {
  const dir = process.env.VISUAL_OUTPUT_DIR;
  if (!dir) return;
  await mkdir(dir, { recursive: true });
  await page.screenshot({ path: `${dir}/${browserName}-tutorial-${page.viewportSize()?.width}-${label}.png` });
}

for (const layout of ['desktop', 'compact']) {
  test(`walkthrough completes all chapters with real configuration, coverage and deployments on ${layout}`, async ({ page, browserName }) => {
    test.setTimeout(100_000);
    const compact = layout === 'compact';
    await page.setViewportSize(compact ? { width: 390, height: 700 } : { width: 1440, height: 900 });
    await start(page);
    await step(page, 'Game time');
    await visibility(page, target.clock);
    await saveVisual(page, 'clock', browserName);
    await next(page);
    await step(page, 'Cash and daily profit');
    await next(page);
    await step(page, 'Navigate the topology');
    await next(page);
    await step(page, 'From traffic to storage');
    await next(page, 'Continue chapter');
    await step(page, 'Select the API');
    await visibility(page, target.api);
    await saveVisual(page, 'node', browserName);
    await button(tutorial(page), 'Focus target').click();
    await expect(control(page, target.api)).toBeFocused();
    await page.keyboard.press('Enter');

    await step(page, 'Open Configuration');
    if (compact) await clickTarget(page, target.openInspector);
    await clickTarget(page, target.configuration);
    await step(page, 'Read the capacity settings');
    await visibility(page, target.capacity);
    await next(page);
    await step(page, 'Switch to Metrics');
    await clickTarget(page, target.metrics);
    await step(page, 'Check for component metrics');
    await visibility(page, target.missingMetrics);
    await next(page);
    await step(page, 'Return to Configuration');
    await clickTarget(page, target.configuration);

    await step(page, 'Set up monitoring coverage');
    if (compact) await clickTarget(page, target.close);
    await next(page, 'Continue chapter');
    await step(page, 'Add a Monitoring collector');
    await clickTarget(page, target.add);
    await expect(page.getByRole('dialog').locator('[data-spotlight-ui]')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await clickTarget(page, target.add);
    await visibility(page, target.collector);
    await saveVisual(page, 'catalog', browserName);
    await clickTarget(page, target.collector);

    await step(page, 'Link the API and database');
    for (const source of ['api', 'db']) {
      await clickTarget(page, target.connect);
      await expect(highlight(page, target.source)).toBeVisible();
      await control(page, target.source).selectOption(source);
      await expect(highlight(page, target.destination)).toBeVisible();
      await control(page, target.destination).selectOption({ label: 'Monitoring' });
      await clickTarget(page, target.saveLink);
      await expect(page.getByRole('dialog')).toHaveCount(0);
    }

    await step(page, 'Review monitoring changes');
    await clickTarget(page, target.review);
    await step(page, 'Check the monitoring costs');
    await visibility(page, target.forecast);
    await next(page);
    await step(page, 'Deploy monitoring coverage');
    await expect(page.getByRole('dialog').locator('[data-spotlight-ui]')).toBeVisible();
    await visibility(page, target.deploy);
    await saveVisual(page, 'review', browserName);
    await page.keyboard.press('Escape');
    await clickTarget(page, target.review);
    await clickTarget(page, target.deploy);
    await step(page, 'Open Telemetry');
    await clickTarget(page, target.done);
    await clickTarget(page, 'navigation.monitor');
    await step(page, 'Check who is reporting');
    await visibility(page, target.coverage);
    await next(page);
    await tutorial(page).getByRole('link', { name: 'Open Topology' }).click();
    if (compact) await clickTarget(page, target.openInspector);
    await clickTarget(page, target.metrics);
    await step(page, 'Read live API utilization');
    await visibility(page, target.cpu);
    const cpu = await control(page, target.cpu).boundingBox();
    const bar = await page.locator('.topbar').boundingBox();
    expect(cpu!.y).toBeGreaterThanOrEqual(bar!.height);
    await saveVisual(page, 'metric', browserName);
    await next(page);
    await step(page, 'Compare incoming and processed requests');
    await visibility(page, target.throughput);
    await next(page);
    await step(page, 'Plan an infrastructure change');
    if (compact) await clickTarget(page, target.close);
    await next(page, 'Continue chapter');
    await step(page, 'Create a draft');
    await clickTarget(page, target.createDraft);
    await step(page, 'Open the API settings');
    if (compact) await clickTarget(page, target.openInspector);
    await clickTarget(page, target.configuration);
    await expect.poll(() => control(page, target.edit).evaluate((node) => {
      const panel = node.closest('dialog, [data-tutorial-scroll]');
      return panel?.scrollTop ?? 0;
    })).toBeGreaterThan(0);
    await clickTarget(page, target.edit);
    await step(page, 'Change capacity in the draft');
    await expect(highlight(page, target.instance)).toBeVisible();
    await control(page, target.instance).selectOption('2');
    await clickTarget(page, target.save);
    await step(page, 'Open Deployment review');
    if (compact) await clickTarget(page, target.close);
    await clickTarget(page, target.review);
    await step(page, 'Read the deployment forecast');
    await visibility(page, target.capacityForecast);
    await next(page);
    await step(page, 'Check the deployment costs');
    await next(page);
    await step(page, 'Confirm the deployment');
    await clickTarget(page, target.deploy);
    await step(page, 'Compare before and after');
    await visibility(page, target.compare);
    await next(page);
    await step(page, 'Follow the money');
    await clickTarget(page, target.close);
    await next(page, 'Continue chapter');
    await step(page, 'Open Finance');
    await clickTarget(page, target.balance);
    await step(page, 'Read the revenue breakdown');
    await visibility(page, target.finance);
    await next(page);
    await step(page, 'Read the expense breakdown');
    await visibility(page, target.expenses);
    await next(page);
    await step(page, 'Open Product');
    if (compact) await clickTarget(page, 'navigation.more');
    await clickTarget(page, 'navigation.product');
    await step(page, 'Explore advertising');
    await next(page);
    await step(page, 'Explore premium subscriptions');
    await next(page);
    await step(page, 'Open Growth');
    await clickTarget(page, 'navigation.growth');
    await step(page, 'Check capacity before growing');
    await next(page, 'Finish');
    await step(page, 'Tutorial complete');
    await next(page, 'Done');
    await expect(tutorial(page)).toHaveCount(0);
  });
}

test('tutorial survives reload, navigation, skip and restart in Russian at 390px and 768px', async ({ page, browserName }) => {
  await page.addInitScript(() => localStorage.setItem('workbench-language', 'ru'));
  await page.setViewportSize({ width: 390, height: 844 });
  const game = await start(page);
  await step(page, 'Игровое время');
  await visibility(page, target.clock);
  await saveVisual(page, 'clock-ru', browserName);
  await next(page, 'Далее');
  await step(page, 'Баланс и дневная прибыль');
  await page.reload();
  await step(page, 'Баланс и дневная прибыль');
  await next(page, 'Далее');
  await step(page, 'Навигация по топологии');
  await visibility(page, target.canvas);
  await saveVisual(page, 'canvas-ru', browserName);
  await next(page, 'Далее');
  await next(page, 'Продолжить главу');
  await clickTarget(page, target.api);
  await step(page, 'Откройте конфигурацию');
  await clickTarget(page, target.openInspector);
  await visibility(page, target.configuration);
  await saveVisual(page, 'mobile-inspector-ru', browserName);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await clickTarget(page, target.openInspector);
  await clickTarget(page, target.configuration);
  await step(page, 'Параметры мощности');

  await page.setViewportSize({ width: 768, height: 900 });
  await visibility(page, target.capacity);
  await saveVisual(page, 'inspector-ru', browserName);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(768);
  await page.keyboard.press('Escape');
  await page.locator('nav [data-tutorial="navigation.growth"]:visible').first().click();
  await expect(tutorial(page).getByRole('link')).toBeVisible();
  await page.goBack();
  await step(page, 'Параметры мощности');
  await next(page, 'Пропустить обучение');
  await page.reload();
  await expect(tutorial(page)).toHaveCount(0);
  await page.goto(`/game/${game.id}?view=settings`);
  await button(page, 'Продолжить обучение').click();
  await step(page, 'Параметры мощности');
  await page.goto(`/game/${game.id}?view=guide`);
  await button(page, 'Начать обучение заново').click();
  await step(page, 'Игровое время');
});

test('a panned or unmounted API is revealed and resize keeps the modal control clickable', async ({ page, browserName }) => {
  await page.setViewportSize({ width: 1920, height: 980 });
  const state = {
    onboarding: { step: 2, furthest: 2, skipped: false, step_id: 'select-api', furthest_id: 'select-api' } as const,
    diagram: { positions: {}, routes: {}, groups: [{ id: 'hidden', name: 'Hidden API', members: ['api'], collapsed: true }],
      viewports: { wide: { x: -1200, y: -800, zoom: 1 } } }
  };
  await start(page, state);
  await step(page, 'Select the API');
  await visibility(page, target.api);
  await saveVisual(page, 'list-fallback', browserName);
  await clickTarget(page, target.api);
  await step(page, 'Open Configuration');
  await page.setViewportSize({ width: 390, height: 700 });
  await clickTarget(page, target.openInspector);
  await visibility(page, target.configuration);
  await clickTarget(page, target.configuration);
  await step(page, 'Read the capacity settings');
});

test('slow draft confirmation and a WebSocket reconnect preserve the interactive step', async ({ page }) => {
  let drop: (() => void) | undefined;
  let connections = 0;
  await page.routeWebSocket('**/api/games/*/live', (client) => {
    connections++;
    const server = client.connectToServer();
    drop = () => { client.close({ code: 1012 }); server.close({ code: 1012 }); };
  });
  const game = await start(page, {
    onboarding: { step: 6, furthest: 6, skipped: false, step_id: 'create-draft', furthest_id: 'create-draft' }
  });
  let release: () => void = () => {};
  await page.route(`**/api/games/${game.id}/draft`, async (route) => {
    await new Promise<void>((resolve) => release = resolve);
    await route.continue();
  });
  await clickTarget(page, target.createDraft);
  await expect(tutorial(page)).toContainText('Waiting for the server');
  await step(page, 'Create a draft');
  await expect.poll(() => connections).toBe(1);
  drop?.();
  await expect.poll(() => connections).toBeGreaterThan(1);
  await step(page, 'Create a draft');
  release();
  await step(page, 'Open the API settings');
  await page.reload();
  await step(page, 'Open the API settings');
});
