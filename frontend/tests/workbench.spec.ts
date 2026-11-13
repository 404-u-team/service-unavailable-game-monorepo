import { expect, test, type Page } from '@playwright/test';
import type { Game } from '../src/lib/types';

const visualDir = process.env.VISUAL_OUTPUT_DIR;
const serviceName = 'Workbench Messenger';

async function create(page: Page, mobile = false, capture = true) {
  await page.goto('/');
  await page.getByRole('link', { name: /New game/ }).click();
  await page.getByLabel('Service name').fill(serviceName);
  await page.getByLabel('Specify a simulation seed').check();
  await page.getByLabel('Simulation seed', { exact: true }).fill('7');
  if (visualDir && capture && !mobile && page.viewportSize()?.width === 1440) {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: `${visualDir}/new-game-1440.png` });
  }
  const submit = page.getByRole('button', { name: 'Create game' });
  if (mobile) await submit.tap();
  else await submit.click();
  await expect(page.getByRole('heading', { name: /topology/i })).toBeVisible();
  return new URL(page.url()).pathname.split('/').at(-1)!;
}

async function state(page: Page, id: string): Promise<Game> {
  const response = await page.request.get(`/api/games/${id}`);
  expect(response.ok()).toBeTruthy();
  return await response.json();
}

async function fast(page: Page) {
  await page.getByRole('button', { name: 'Game speed' }).click();
  await page.getByRole('button', { name: 'Fast speed (3×)' }).click();
}

async function pause(page: Page) {
  await page.getByRole('button', { name: 'Game speed' }).click();
  await page.getByRole('button', { name: 'Pause game' }).click();
}

async function navigate(page: Page, name: string, mobile = false) {
  await page.getByRole('navigation', { name: mobile ? 'Mobile navigation' : 'Workbench navigation' })
    .getByRole('link', { name, exact: true }).click();
}

async function connect(page: Page, from: string, to: string) {
  await page.getByRole('button', { name: 'Connect', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Connect components' });
  await dialog.getByLabel('Source component').selectOption({ label: from });
  await dialog.getByLabel('Target component').selectOption({ label: to });
  await dialog.getByRole('button', { name: 'Connect components' }).click();
  await expect(dialog).toBeHidden();
}

async function deploy(page: Page) {
  await page.getByRole('button', { name: 'Review deployment' }).click();
  const review = page.getByRole('dialog', { name: 'Deployment review' });
  await expect(review.getByRole('heading', { name: 'Capacity forecast' })).toBeVisible();
  await review.getByRole('button', { name: 'Deploy changes' }).click();
  await expect(review).toBeHidden();
}

test('A and B · create, run, save, reopen, edit and scale production', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page);
  const first = await state(page, id);
  expect(first.tick).toBe(0);
  expect(first.snapshot.metrics.rps).toBeGreaterThan(100);
  await expect(page.getByRole('complementary', { name: 'Component inspector' }).getByText('Messenger API')).toBeVisible();
  if (visualDir) await page.screenshot({ path: `${visualDir}/topology-1440.png` });

  await fast(page);
  await expect.poll(async () => (await state(page, id)).tick).toBeGreaterThan(2);
  await pause(page);
  await page.getByRole('button', { name: 'Save game' }).click();
  await expect(page.getByRole('status')).toHaveText('Game saved');
  const saved = await state(page, id);
  await page.getByRole('link', { name: 'Service Unavailable main menu' }).click();
  await page.getByRole('link', { name: /Saved games/ }).click();
  await page.getByRole('link', { name: new RegExp(serviceName) }).click();
  await expect(page.getByRole('heading', { name: 'Infrastructure topology' })).toBeVisible();
  expect((await state(page, id)).tick).toBe(saved.tick);

  await page.getByRole('button', { name: 'Add node' }).click();
  await page.getByRole('dialog', { name: 'Component library' }).getByRole('button', { name: 'Monitoring' }).click();
  await connect(page, 'Messenger API', 'Monitoring');
  await connect(page, 'Primary database', 'Monitoring');
  await page.locator('.svelte-flow__node[aria-label="Monitoring"]').click();
  await page.getByRole('button', { name: 'Edit configuration' }).click();
  await page.getByLabel('Collection scope').selectOption('Service history');
  await page.getByRole('button', { name: 'Save to draft' }).click();
  await deploy(page);

  await navigate(page, 'Growth');
  await page.getByRole('article').filter({ hasText: 'Community campaign' }).getByRole('button', { name: 'Plan campaign' }).click();
  await page.getByRole('button', { name: 'Start campaign' }).click();
  await fast(page);
  await expect.poll(async () => (await state(page, id)).audience, { timeout: 18_000 }).toBeGreaterThan(10_000);
  await pause(page);
  const before = await state(page, id);
  expect(before.snapshot.components.api.utilization.CPU).toBeGreaterThan(1);

  await navigate(page, 'Topology');
  await page.locator('.svelte-flow__node[aria-label="Messenger API"]').click();
  await expect.poll(async () => (await state(page, id)).tutorial).toBe(1);
  await page.getByRole('button', { name: 'Edit configuration' }).click();
  await page.getByLabel('Instance size').selectOption({ label: 'Performance P4 · 4 vCPU / 8 GB' });
  await page.getByRole('button', { name: 'Save to draft' }).click();
  await expect(page.getByRole('button', { name: 'Undo draft edit' })).toBeEnabled();
  await page.getByRole('button', { name: 'Undo draft edit' }).click();
  await expect(page.getByRole('button', { name: 'Redo draft edit' })).toBeEnabled();
  await page.getByRole('button', { name: 'Redo draft edit' }).click();
  expect((await state(page, id)).production.nodes.find((node) => node.id === 'api')!.config.cpu).toBeUndefined();
  await page.getByRole('button', { name: 'Review deployment' }).click();
  const review = page.getByRole('dialog', { name: 'Deployment review' });
  await expect(review.getByRole('heading', { name: 'Capacity forecast' })).toBeVisible();
  if (visualDir) await page.screenshot({ path: `${visualDir}/deployment-1440.png` });
  await review.getByRole('button', { name: 'Deploy changes' }).click();
  await expect(review).toBeHidden();

  const after = await state(page, id);
  expect(after.snapshot.components.api.utilization.CPU).toBeLessThan(before.snapshot.components.api.utilization.CPU);
  expect(after.draft).toBeNull();
  expect(after.deployments).toHaveLength(2);
  expect(after.tutorial).toBe(3);
  await navigate(page, 'Telemetry');
  await expect.poll(async () => (await state(page, id)).tutorial).toBe(4);
  await expect(page.getByRole('heading', { name: 'System telemetry' })).toBeVisible();
  await expect(page.getByRole('img', { name: /Request traffic/ })).toBeVisible();
  if (visualDir) await page.screenshot({ path: `${visualDir}/telemetry-1440.png` });
});

test('C and D · campaign and product release change workload and finances', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page, false, false);
  await navigate(page, 'Growth');
  if (visualDir) await page.screenshot({ path: `${visualDir}/growth-1440.png` });
  await page.getByRole('article').filter({ hasText: 'Community campaign' }).getByRole('button', { name: 'Plan campaign' }).click();
  const plan = page.getByRole('dialog', { name: 'Campaign planning' });
  await expect(plan.getByRole('heading', { name: 'Capacity forecast' })).toBeVisible();
  await plan.getByRole('button', { name: 'Start campaign' }).click();
  await expect(plan).toBeHidden();
  expect((await state(page, id)).economy.marketing).toBe(420);

  await navigate(page, 'Product');
  const groups = page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Group chats' }) });
  await groups.getByRole('button', { name: 'Feature details' }).click();
  await page.getByRole('button', { name: 'Start development' }).click();
  await fast(page);
  await expect(groups.getByText('Ready to release')).toBeVisible({ timeout: 16_000 });
  await pause(page);
  const before = await state(page, id);
  expect(before.audience).toBeGreaterThan(9_000);
  expect(before.economy.revenue).toBeGreaterThan(0);
  expect(before.economy.operating).toBeGreaterThan(0);
  expect(before.economy.development).toBe(650);
  if (visualDir) await page.screenshot({ path: `${visualDir}/product-1440.png` });
  await groups.getByRole('button', { name: 'Feature details' }).click();
  await page.getByRole('button', { name: 'Release feature' }).click();
  await expect(groups.getByText('Released', { exact: true })).toBeVisible();
  const released = await state(page, id);
  expect(released.snapshot.demand.groups).toBeGreaterThan(0);
  expect(released.snapshot.metrics.rps).toBeGreaterThan(before.snapshot.metrics.rps);
  await navigate(page, 'Finance');
  await expect(page.getByRole('heading', { name: 'Expense breakdown' })).toBeVisible();
  if (visualDir) await page.screenshot({ path: `${visualDir}/finance-1440.png` });
});

test('E · failed instance reduces availability and redundancy restores service', async ({ page }) => {
  const id = await create(page);
  await navigate(page, 'Events');
  await page.getByRole('button', { name: 'Run failure drill' }).click();
  await page.getByRole('button', { name: 'Start drill' }).click();
  const event = page.getByRole('button', { name: /Instance failure drill/ });
  await event.click();
  await expect(page.getByRole('dialog').getByText(/Component-level diagnostics require Monitoring/)).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Acknowledge' }).click();
  await expect(page.getByRole('dialog').getByText('Acknowledged', { exact: true })).toBeVisible();
  expect((await state(page, id)).snapshot.metrics.availability).toBe(0);
  await page.getByRole('button', { name: 'Close dialog' }).click();
  if (visualDir) await page.screenshot({ path: `${visualDir}/events-1440.png` });

  await navigate(page, 'Topology');
  await page.getByRole('button', { name: 'Add node' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Monitoring' }).click();
  await connect(page, 'Messenger API', 'Monitoring');
  await deploy(page);
  await navigate(page, 'Telemetry');
  await expect(page.getByRole('heading', { name: 'Node health' })).toBeVisible();
  await expect(page.getByText('Failed', { exact: true })).toBeVisible();

  await navigate(page, 'Topology');
  await page.getByRole('button', { name: 'Add replica' }).click();
  await deploy(page);
  expect((await state(page, id)).snapshot.metrics.availability).toBeGreaterThan(.98);
  await fast(page);
  await expect.poll(async () => (await state(page, id)).incidents.find((item) => item.title === 'Instance failure drill')?.active).toBe(false);
  await pause(page);
});

test.describe('Mobile workbench', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test('F · navigation, component list, mobile inspector and deployment', async ({ page }) => {
    const id = await create(page, true);
    const graph = page.locator('.svelte-flow');
    await expect(graph).toBeVisible();
    if (visualDir) await page.screenshot({ path: `${visualDir}/topology-390.png` });
    const cdp = await page.context().newCDPSession(page);
    const viewport = graph.locator('.svelte-flow__viewport');
    const transform = () => viewport.evaluate((element) => new DOMMatrix(getComputedStyle(element).transform).a);
    const bounds = (await graph.boundingBox())!;
    const x = bounds.x + bounds.width * .16;
    const y = bounds.y + bounds.height * .66;
    const pane = graph.locator('.svelte-flow__pane');
    await expect(pane).toHaveCSS('touch-action', 'none');
    const before = await transform();
    await cdp.send('Input.dispatchTouchEvent', {
      type: 'touchStart', touchPoints: [{ x, y: y - 20, id: 1 }, { x, y: y + 20, id: 2 }]
    });
    for (const distance of [30, 45, 60, 75]) {
      await cdp.send('Input.dispatchTouchEvent', {
        type: 'touchMove', touchPoints: [{ x, y: y - distance, id: 1 }, { x, y: y + distance, id: 2 }]
      });
    }
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await expect.poll(transform).toBeGreaterThan(before);
    await cdp.detach();
    await page.getByRole('button', { name: 'Show component list' }).tap();
    await page.getByRole('button', { name: 'Messenger API API server' }).tap();
    await page.getByRole('button', { name: 'Open component' }).tap();
    await page.getByRole('dialog', { name: 'Component inspector' }).getByRole('button', { name: 'Edit configuration' }).tap();
    await page.getByLabel('Instances', { exact: true }).fill('2');
    await page.getByRole('button', { name: 'Save to draft' }).tap();
    await page.getByRole('dialog', { name: 'Component inspector' }).getByRole('button', { name: 'Close dialog' }).tap();
    await page.getByRole('button', { name: 'Review deployment' }).tap();
    const review = page.getByRole('dialog', { name: 'Deployment review' });
    await expect(review.getByRole('heading', { name: 'Capacity forecast' })).toBeVisible();
    if (visualDir) await page.screenshot({ path: `${visualDir}/deployment-390.png` });
    await review.getByRole('button', { name: 'Deploy changes' }).tap();
    expect((await state(page, id)).production.nodes.find((node) => node.id === 'api')!.config.instances).toBe(2);
    await navigate(page, 'Home', true);
    await expect(page.getByRole('heading', { name: 'Service overview' })).toBeVisible();
    await navigate(page, 'More', true);
    await page.getByRole('link', { name: /Settings/ }).tap();
    await expect(page.getByRole('heading', { name: 'Game preferences' })).toBeVisible();
    await page.getByRole('button', { name: 'Save game' }).tap();
    await expect(page.getByRole('status')).toHaveText('Game saved');
  });
});

test('an older API catalog shows a recoverable error on the new game screen', async ({ page }) => {
  const pageErrors: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  await page.route('**/api/games/catalog', async (route) => {
    const response = await route.fetch();
    expect(response.ok()).toBeTruthy();
    const catalog = await response.json();
    delete catalog.difficulties;
    await route.fulfill({ response, json: catalog });
  });

  await page.goto('/?view=new');
  await expect(page.getByRole('alert')).toContainText('incompatible catalog');
  await expect(page.getByRole('button', { name: 'Create game' })).toBeDisabled();
  await page.unroute('**/api/games/catalog');
  await page.getByRole('button', { name: 'Retry connection' }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);

  await page.getByRole('radio', { name: 'Expert' }).check();
  await expect(page.getByText('$4,800 budget')).toBeVisible();
  await page.getByRole('button', { name: 'Create game' }).click();
  await expect(page.getByRole('heading', { name: 'Infrastructure topology' })).toBeVisible();
  const id = new URL(page.url()).pathname.split('/').at(-1)!;
  expect((await state(page, id)).difficulty).toBe('expert');
  expect(pageErrors).toEqual([]);
});

test('failed request can be retried and the responsive shell stays inside the viewport', async ({ page }) => {
  await page.route('**/api/games', (route) => route.fulfill({ status: 503, json: { detail: 'The game server is unavailable.' } }));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('unavailable');
  await page.unroute('**/api/games');
  await page.getByRole('button', { name: 'Retry connection' }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await create(page, false, false);
  for (const width of [390, 768, 1440, 1920]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await expect(page.locator('.svelte-flow')).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await expect.poll(() => page.locator('.svelte-flow').evaluate((canvas) => {
      const bounds = canvas.getBoundingClientRect();
      const nodes = [...canvas.querySelectorAll('.svelte-flow__node')].map((node) => node.getBoundingClientRect());
      if (!nodes.length) return Infinity;
      const left = Math.min(...nodes.map((node) => node.left));
      const right = Math.max(...nodes.map((node) => node.right));
      return Math.abs((left + right) / 2 - (bounds.left + bounds.right) / 2);
    })).toBeLessThan(30);
    if (visualDir && [768, 1920].includes(width)) await page.screenshot({ path: `${visualDir}/topology-${width}.png` });
  }
});

test('canvas drag, edge selection, and keyboard undo persist valid changes', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page, false, false);
  await page.getByRole('button', { name: 'Create draft' }).click();
  await expect(page.getByRole('button', { name: 'Review deployment' })).toBeVisible();
  const graphNode = page.locator('.svelte-flow__node[aria-label="Messenger API"]');
  const box = await graphNode.boundingBox();
  expect(box).not.toBeNull();
  const { x, y, width, height } = box!;
  await page.mouse.move(x + width / 2, y + height / 2);
  await page.mouse.down();
  await page.mouse.move(x + width / 2 + 35, y + height / 2 - 85, { steps: 8 });
  await page.mouse.up();
  await expect.poll(async () => (await state(page, id)).draft?.nodes.find((node) => node.id === 'api')?.position.y).toBeLessThan(145);
  await page.keyboard.press('Control+z');
  await expect.poll(async () => (await state(page, id)).draft?.nodes.find((node) => node.id === 'api')?.position.y).toBe(185);
  await page.getByRole('button', { name: 'Show component list' }).click();
  await page.getByRole('button', { name: 'Messenger API → Primary database' }).click();
  await page.keyboard.press('Delete');
  await expect.poll(async () => (await state(page, id)).draft?.edges.length).toBe(2);
  await page.getByRole('button', { name: 'Review deployment' }).click();
  const review = page.getByRole('dialog', { name: 'Deployment review' });
  await expect(review.getByRole('alert')).toContainText('Connect traffic to an API server');
  await expect(review.getByRole('button', { name: 'Deploy changes' })).toBeDisabled();
  await review.getByRole('button', { name: 'Back to draft' }).click();
  await page.getByRole('button', { name: 'Discard', exact: true }).click();
  await page.getByRole('button', { name: 'Discard draft', exact: true }).click();
  await expect.poll(async () => (await state(page, id)).draft).toBeNull();
  expect((await state(page, id)).production.edges).toHaveLength(3);
});
