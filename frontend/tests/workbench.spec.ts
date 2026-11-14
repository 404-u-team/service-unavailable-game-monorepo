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
  const skip = page.getByRole('button', { name: 'Skip tutorial' });
  if (await skip.isVisible()) {
    await skip.click();
    await expect(skip).toHaveCount(0);
  }
  return new URL(page.url()).pathname.split('/').at(-1)!;
}

async function state(page: Page, id: string): Promise<Game> {
  const response = await page.request.get(`/api/games/${id}`);
  expect(response.ok()).toBeTruthy();
  return await response.json();
}

async function fast(page: Page) {
  await page.getByRole('button', { name: 'Fast speed (3×)' }).click();
}

async function pause(page: Page) {
  await page.getByRole('button', { name: 'Pause simulation' }).click();
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
  const results = page.getByRole('dialog', { name: 'Deployment complete' });
  await expect(results.getByRole('table')).toBeVisible();
  await results.getByRole('button', { name: 'Done' }).click();
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
  await expect(page.getByRole('status').filter({ hasText: 'Game saved' })).toBeVisible();
  const saved = await state(page, id);
  await page.getByRole('link', { name: 'Service Unavailable main menu' }).click();
  await page.getByRole('link', { name: /Saved games/ }).click();
  await page.getByRole('link', { name: new RegExp(serviceName) }).click();
  await expect(page.getByRole('heading', { name: 'Infrastructure topology' })).toBeVisible();
  expect((await state(page, id)).tick).toBe(saved.tick);

  await page.getByRole('button', { name: 'Add node' }).click();
  await page.getByRole('dialog', { name: 'Component library' }).getByRole('button', { name: 'Monitoring', exact: true }).click();
  await connect(page, 'Messenger API', 'Monitoring');
  await connect(page, 'Primary database', 'Monitoring');
  await page.locator('.svelte-flow__node[aria-label="Monitoring"]').click();
  await page.getByRole('button', { name: 'Edit configuration' }).click();
  await page.getByLabel('Collection scope', { exact: true }).selectOption('Service history');
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
  await page.getByRole('button', { name: 'Done' }).click();

  const after = await state(page, id);
  expect(after.snapshot.components.api.utilization.CPU).toBeLessThan(before.snapshot.components.api.utilization.CPU);
  expect(after.draft).toBeNull();
  expect(after.deployments).toHaveLength(2);
  expect(after.tutorial).toBe(3);
  await navigate(page, 'Telemetry');
  await expect.poll(async () => (await state(page, id)).tutorial).toBe(4);
  await expect(page.getByRole('heading', { name: 'System telemetry' })).toBeVisible();
  await expect(page.getByRole('img', { name: /Request traffic/ })).toBeVisible();
  await expect(page.getByRole('img', { name: /Peak resource load for Messenger API/ })).toBeVisible();
  await page.getByRole('combobox', { name: 'Component', exact: true }).selectOption('db');
  await expect(page.getByRole('img', { name: /Peak resource load for Primary database/ })).toBeVisible();
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
  expect(before.economy.revenue).toBe(0);
  expect(before.economy.operating).toBeGreaterThan(0);
  expect(before.economy.development).toBe(650);
  if (visualDir) await page.screenshot({ path: `${visualDir}/product-1440.png` });
  await groups.getByRole('button', { name: 'Feature details' }).click();
  await page.getByRole('button', { name: 'Release feature' }).click();
  await expect(groups.getByText('Released and enabled', { exact: true })).toBeVisible();
  const released = await state(page, id);
  expect(released.snapshot.demand.groups).toBeGreaterThan(0);
  expect(released.snapshot.metrics.rps).toBeGreaterThan(before.snapshot.metrics.rps);
  await navigate(page, 'Finance');
  await expect(page.getByRole('heading', { name: 'Expense breakdown' })).toBeVisible();
  if (visualDir) await page.screenshot({ path: `${visualDir}/finance-1440.png` });
});

test('database pool and hardware upgrades have distinct effects on a live save', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page, false, false);
  const editDatabase = async () => {
    await page.goto(`/game/${id}?view=build&component=db`);
    await page.getByRole('button', { name: 'Edit configuration' }).click();
    return page.getByRole('dialog', { name: 'Component configuration' });
  };

  let config = await editDatabase();
  await config.getByLabel('Database vCPU', { exact: true }).fill('1');
  await config.getByRole('button', { name: 'Save to draft' }).click();
  await expect(config).toBeHidden();
  await page.getByRole('button', { name: 'Add node' }).click();
  await page.getByRole('dialog', { name: 'Component library' }).getByRole('button', { name: 'Monitoring', exact: true }).click();
  await connect(page, 'Primary database', 'Monitoring');
  await deploy(page);
  const constrained = await state(page, id);
  expect(constrained.snapshot.components.db.status).toBe('overloaded');
  expect(constrained.snapshot.components.api).toBeUndefined();

  await page.goto(`/game/${id}?view=monitor`);
  const diagnosis = page.locator('[data-guide="diagnostics"]');
  await expect(diagnosis.getByText('Database write capacity exceeded')).toBeVisible();
  await expect(diagnosis.getByText('Sustainable writes at current read load')).toBeVisible();
  await expect(diagnosis.getByText('Increase vCPU to raise read and write processing capacity.')).toBeVisible();
  await diagnosis.getByRole('link', { name: 'Database Guide' }).click();
  await expect(page.getByRole('heading', { name: 'Cache versus read replica' })).toBeVisible();
  await page.goto(`/game/${id}?view=monitor`);
  await diagnosis.getByRole('link', { name: 'Edit configuration' }).click();
  config = page.getByRole('dialog', { name: 'Component configuration' });
  await expect(config).toBeVisible();
  await config.getByLabel('Connection pool limit', { exact: true }).fill('700');
  let releaseForecast!: () => void;
  let forecastStarted!: () => void;
  const heldForecast = new Promise<void>((resolve) => releaseForecast = resolve);
  const intercepted = new Promise<void>((resolve) => forecastStarted = resolve);
  await page.route('**/draft/review', async (route) => {
    forecastStarted();
    await heldForecast;
    await route.continue();
  }, { times: 1 });
  await config.getByRole('button', { name: 'Preview cost and capacity' }).click();
  await intercepted;
  await config.getByLabel('Connection pool limit', { exact: true }).fill('800');
  const stale = page.waitForResponse((response) => response.url().endsWith('/draft/review'));
  releaseForecast();
  await stale;
  await expect(config.getByRole('heading', { name: 'Capacity forecast' })).toBeHidden();
  await config.getByLabel('Connection pool limit', { exact: true }).fill('700');
  await config.getByRole('button', { name: 'Preview cost and capacity' }).click();
  await expect(config.getByRole('heading', { name: 'Capacity forecast' })).toBeVisible();
  await config.getByRole('button', { name: 'Save to draft' }).click();
  await expect(config).toBeHidden();
  await page.getByRole('button', { name: 'Review deployment' }).click();
  await page.getByRole('button', { name: 'Deploy changes' }).click();
  const results = page.getByRole('dialog', { name: 'Deployment complete' });
  await expect(results.getByText(/Successful throughput barely changed\. Primary database/)).toBeVisible();
  await results.getByRole('button', { name: 'Done' }).click();
  const pool = await state(page, id);
  expect(pool.snapshot.metrics).toEqual(constrained.snapshot.metrics);
  expect(pool.economy.daily_infrastructure).toBe(constrained.economy.daily_infrastructure);

  config = await editDatabase();
  await config.getByLabel('Database vCPU', { exact: true }).fill('8');
  await config.getByLabel('RAM (GB)', { exact: true }).fill('32');
  await config.getByLabel('Storage type', { exact: true }).selectOption('NVMe');
  await config.getByRole('button', { name: 'Save to draft' }).click();
  await expect(config).toBeHidden();
  await deploy(page);
  const upgraded = await state(page, id);
  expect(upgraded.snapshot.metrics.throughput).toBeGreaterThan(pool.snapshot.metrics.throughput);
  expect(upgraded.economy.daily_infrastructure).toBeGreaterThan(pool.economy.daily_infrastructure);
  expect(upgraded.deployments[0].comparison?.before).toEqual(pool.snapshot.metrics);
  expect(upgraded.deployments[0].comparison?.after).toEqual(upgraded.snapshot.metrics);
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
  await page.getByRole('dialog').getByRole('button', { name: 'Monitoring', exact: true }).click();
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
    const inspector = page.getByRole('dialog', { name: 'Component inspector' });
    const configuration = inspector.getByRole('button', { name: 'Configuration', exact: true });
    const metrics = inspector.getByRole('button', { name: 'Metrics', exact: true });
    await metrics.tap();
    await expect(metrics).toHaveAttribute('aria-pressed', 'true');
    await expect(inspector.getByRole('heading', { name: 'Messenger API' })).toBeVisible();
    await configuration.tap();
    await expect(configuration).toHaveAttribute('aria-pressed', 'true');
    await inspector.getByRole('button', { name: 'Edit configuration' }).tap();
    await page.getByLabel('Instances', { exact: true }).fill('2');
    await page.getByRole('button', { name: 'Save to draft' }).tap();
    await page.getByRole('dialog', { name: 'Component inspector' }).getByRole('button', { name: 'Close dialog' }).tap();
    await page.getByRole('button', { name: 'Review deployment' }).tap();
    const review = page.getByRole('dialog', { name: 'Deployment review' });
    await expect(review.getByRole('heading', { name: 'Capacity forecast' })).toBeVisible();
    if (visualDir) await page.screenshot({ path: `${visualDir}/deployment-390.png` });
    await review.getByRole('button', { name: 'Deploy changes' }).tap();
    await page.getByRole('button', { name: 'Done' }).tap();
    expect((await state(page, id)).production.nodes.find((node) => node.id === 'api')!.config.instances).toBe(2);
    await navigate(page, 'Home', true);
    await expect(page.getByRole('heading', { name: 'Service overview' })).toBeVisible();
    await navigate(page, 'More', true);
    await page.getByRole('link', { name: /Settings/ }).tap();
    await expect(page.getByRole('heading', { name: 'Game preferences' })).toBeVisible();
    await page.getByRole('main').getByRole('button', { name: 'Save game' }).tap();
    await expect(page.getByRole('status').filter({ hasText: 'Game saved' })).toBeVisible();
  });

  test('touch players can use component help, group cards, and typed connections', async ({ page }) => {
    const id = await create(page, true, false);
    await page.getByRole('button', { name: 'Add node' }).tap();
    const library = page.getByRole('dialog', { name: 'Component library' });
    await library.getByRole('button', { name: 'About Monitoring' }).tap();
    const reference = page.getByRole('dialog', { name: 'Connection reference' });
    await expect(reference.getByText('Input connections')).toBeVisible();
    await expect(reference.getByText(/Worker · Metrics collection/)).toBeVisible();
    await reference.getByRole('button', { name: 'Close dialog' }).tap();

    await page.getByRole('button', { name: 'Show component list' }).tap();
    await page.getByRole('button', { name: 'Select multiple' }).tap();
    const api = page.getByRole('button', { name: 'Messenger API API server' });
    if (await api.getAttribute('aria-pressed') !== 'true') await api.tap();
    await page.getByRole('button', { name: 'Primary database Database' }).tap();
    await expect(page.getByRole('button', { name: 'Create group' })).toBeVisible();
    await page.getByRole('button', { name: 'Create group' }).tap();
    const group = page.getByRole('dialog', { name: 'Create group' });
    await group.getByLabel('Group name').fill('Data path');
    await group.getByRole('button', { name: 'Save group' }).tap();
    await page.getByRole('button', { name: 'Collapse group', exact: true }).tap();
    await expect.poll(async () => (await state(page, id)).diagram.groups[0]?.collapsed).toBe(true);
    expect((await state(page, id)).draft).toBeNull();
    await page.getByRole('button', { name: 'Expand group', exact: true }).tap();
    await expect.poll(async () => (await state(page, id)).diagram.groups[0]?.collapsed).toBe(false);

    await page.getByRole('button', { name: 'Add node' }).tap();
    await library.getByRole('button', { name: 'Monitoring', exact: true }).tap();
    await page.getByRole('button', { name: 'Connect', exact: true }).tap();
    const connection = page.getByRole('dialog', { name: 'Connect components' });
    await connection.getByLabel('Source component').selectOption({ label: 'Primary database' });
    await connection.getByLabel('Target component').selectOption({ label: 'Monitoring' });
    await expect(connection.getByText('Metrics collection')).toBeVisible();
    await connection.getByRole('button', { name: 'Connect components' }).tap();
    await expect(connection).toBeHidden();
    await deploy(page);
    await navigate(page, 'Monitor', true);
    await expect(page.getByText('Collecting metrics', { exact: true })).toBeVisible();
    expect((await state(page, id)).snapshot.components.api).toBeUndefined();
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
    await page.getByRole('button', { name: 'Fit view' }).click();
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
  await expect.poll(async () => (await state(page, id)).diagram.positions.api?.y).toBeLessThan(145);
  await page.keyboard.press('Control+z');
  await expect.poll(async () => (await state(page, id)).diagram.positions.api).toBeUndefined();
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


test('layout edits persist without Draft and preserve production', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page, false, false);
  const initial = await state(page, id);
  const api = page.locator('.svelte-flow__node-workbench[aria-label="Messenger API"]');
  const db = page.locator('.svelte-flow__node-workbench[aria-label="Primary database"]');
  const apiBox = (await api.boundingBox())!;
  const dbBox = (await db.boundingBox())!;
  await page.mouse.click((apiBox.x + apiBox.width + dbBox.x) / 2, apiBox.y + apiBox.height / 2);

  await page.getByRole('button', { name: 'Add waypoint' }).click();
  const handle = page.getByRole('button', { name: 'Waypoint 1' });
  await expect(handle).toBeVisible();
  await expect.poll(async () => (await state(page, id)).diagram.routes['api:db']?.length).toBe(1);
  await expect.poll(() => handle.evaluate((element) => {
    const box = element.getBoundingClientRect();
    return document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2) === element;
  })).toBe(true);
  const point = (await handle.boundingBox())!;
  await page.mouse.move(point.x + point.width / 2, point.y + point.height / 2);
  await page.mouse.down();
  await page.mouse.move(point.x + point.width / 2, point.y - 50, { steps: 7 });
  await page.mouse.up();
  await expect.poll(async () => (await state(page, id)).diagram.routes['api:db']?.[0]?.y).toBeLessThan(220);
  if (visualDir) await page.screenshot({ path: `${visualDir}/manual-routing.png` });

  await api.click();
  await db.click({ modifiers: ['Control'] });
  await page.getByRole('button', { name: 'Create group' }).click();
  const group = page.getByRole('dialog', { name: 'Create group' });
  await group.getByLabel('Group name').fill('Data path');
  await group.getByRole('button', { name: 'Save group' }).click();
  await expect(page.locator('.svelte-flow__node-groupCard')).toHaveCount(1);
  if (visualDir) await page.screenshot({ path: `${visualDir}/expanded-group.png` });
  await page.locator('.svelte-flow__node-groupCard').getByRole('button', { name: 'Collapse group' }).click();
  await expect(api).toHaveCount(0);
  await expect.poll(async () => (await state(page, id)).diagram.groups[0]?.collapsed).toBe(true);
  if (visualDir) await page.screenshot({ path: `${visualDir}/collapsed-group.png` });
  await page.reload();
  await expect(page.locator('.svelte-flow__node-groupCard')).toContainText('Data path');
  await expect(api).toHaveCount(0);
  await page.locator('.svelte-flow__node-groupCard').getByRole('button', { name: 'Expand group' }).click();
  await expect(api).toBeVisible();
  const after = await state(page, id);
  expect(after.production).toEqual(initial.production);
  expect(after.revision).toBe(initial.revision);
  expect(after.snapshot.metrics).toEqual(initial.snapshot.metrics);
  expect(after.draft).toBeNull();
  expect(after.diagram.routes['api:db']).toHaveLength(1);
});

test('production node dragging sends one layout write and survives Draft and reload', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page, false, false);
  const initial = await state(page, id);
  const api = page.locator('.svelte-flow__node-workbench[data-id="api"]');
  const writes: string[] = [];
  page.on('request', (request) => {
    if (request.url().endsWith('/diagram')) writes.push(request.method());
  });
  const box = (await api.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 30, box.y + box.height / 2 - 65, { steps: 12 });
  expect(writes).toEqual([]);
  const response = page.waitForResponse((candidate) => candidate.url().endsWith('/diagram'));
  await page.mouse.up();
  const saved = await response;
  expect(saved.status()).toBe(200);
  expect(writes).toEqual(['PATCH']);
  const updated: Game = await saved.json();
  expect(updated.diagram.positions.api.y).toBeLessThan(initial.production.nodes.find((node) => node.id === 'api')!.position.y);
  expect(updated.production).toEqual(initial.production);
  expect(updated.revision).toBe(initial.revision);
  await page.reload();
  await expect(api).toBeVisible();
  await page.getByRole('button', { name: 'Create draft' }).click();
  await expect(page.getByRole('button', { name: 'Review deployment' })).toBeVisible();
  expect((await state(page, id)).diagram.positions.api).toEqual(updated.diagram.positions.api);
  await page.getByRole('button', { name: 'View production' }).click();
  await expect(api).toBeVisible();
  await expect(page.getByRole('button', { name: 'Review deployment' })).toBeHidden();
  await page.getByRole('button', { name: 'Return to draft' }).click();
  await page.getByRole('button', { name: 'Discard', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Discard draft' }).click();
  await expect.poll(async () => (await state(page, id)).draft).toBeNull();
  expect((await state(page, id)).diagram.positions.api).toEqual(updated.diagram.positions.api);
});

test('Russian Monitoring and feature requirements render on desktop and mobile', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page, false, false);
  const pageErrors: string[] = [];
  const failedResponses: number[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('response', (response) => { if (response.status() >= 500) failedResponses.push(response.status()); });
  const mutate = async (path: string, method: string, data: object) => {
    const response = await page.request.fetch(`/api/games/${id}${path}`, {
      method, data: { request_id: crypto.randomUUID(), ...data }
    });
    expect(response.ok(), await response.text()).toBe(true);
    return await response.json() as Game;
  };
  const first = await state(page, id);
  const opened = await mutate('/draft', 'POST', { revision: first.revision });
  const topology = opened.draft!;
  topology.nodes.push({ id: 'monitor', name: 'Monitoring', kind: 'monitor', position: { x: 740, y: 360 }, config: { detail: 'Service history' } });
  topology.edges.push({ source: 'api', target: 'monitor' }, { source: 'db', target: 'monitor' });
  const edited = await mutate('/draft', 'PUT', { revision: opened.revision, topology });
  await mutate('/deployments', 'POST', { revision: edited.revision });
  await mutate('/clock', 'PUT', { speed: 3 });
  await expect.poll(async () => (await state(page, id)).history.length).toBeGreaterThan(2);
  await mutate('/clock', 'PUT', { speed: 0 });
  await page.goto('/?view=settings');
  await page.getByLabel('Interface language').selectOption('ru');
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.goto(`/game/${id}?view=monitor`);
    await expect(page.getByRole('heading', { name: 'Мониторинг системы' })).toBeVisible();
    await expect(page.getByRole('img', { name: /пиковая загрузка/i })).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    if (visualDir) await page.screenshot({ path: `${visualDir}/russian-monitoring-${width}.png`, fullPage: true });
    await page.goto(`/game/${id}?view=product`);
    const voice = page.locator('.feature-row').filter({ has: page.getByRole('heading', { name: 'Голосовые сообщения' }) });
    await voice.getByRole('button', { name: 'Сведения о функции' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toContainText('Рабочая инфраструктура');
    await expect(dialog).toContainText('хотя бы один воркер');
    if (visualDir) await page.screenshot({ path: `${visualDir}/russian-product-${width}.png` });
  }
  expect(pageErrors).toEqual([]);
  expect(failedResponses).toEqual([]);
});

test('Russian is persisted across menus, editor, settings, and game screens', async ({ page }) => {
  await page.goto('/?view=settings');
  await page.getByLabel('Interface language').selectOption('ru');
  await expect(page.getByRole('heading', { name: 'Настройки' })).toBeVisible();
  await page.goto('/?view=new');
  await page.getByLabel('Имя сервиса').fill('Мессенджер');
  await page.getByRole('button', { name: 'Создать игру' }).click();
  await expect(page.getByRole('heading', { name: 'Топология инфраструктуры' })).toBeVisible();
  const base = new URL(page.url()).pathname;
  for (const [view, title] of [['monitor', 'Мониторинг системы'], ['product', 'Функции продукта'], ['growth', 'Аудитория и кампании'],
      ['finance', 'Финансы'], ['events', 'События и инциденты'], ['guide', 'Справка'], ['settings', 'Настройки']]) {
    await page.goto(`${base}?view=${view}`);
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
  }
  await page.goto(`${base}?view=build`);
  await page.getByRole('button', { name: 'Справочник соединений' }).click();
  await expect(page.getByRole('dialog')).toContainText('Исходящие соединения');
  await page.getByRole('button', { name: 'Закрыть окно' }).click();
  await page.getByRole('button', { name: 'Создать черновик' }).click();
  await expect(page.getByRole('button', { name: 'Проверить развёртывание' })).toBeVisible();
  const sourcePort = page.locator('.svelte-flow__node[data-id="traffic"] .svelte-flow__handle.source');
  await page.getByRole('button', { name: 'Вписать в экран' }).click();
  const databasePort = page.locator('.svelte-flow__node[data-id="db"]');
  await expect(databasePort).toBeInViewport();
  const sourceBox = (await sourcePort.boundingBox())!;
  await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(sourceBox.x + sourceBox.width / 2 + 12, sourceBox.y + sourceBox.height / 2);
  await expect(page.getByText('Подсвеченные порты принимают соединение.')).toBeVisible();
  const targetBox = (await databasePort.boundingBox())!;
  await page.mouse.move(targetBox.x + targetBox.width / 2, targetBox.y + targetBox.height / 2, { steps: 12 });
  await page.mouse.up();
  await expect(page.getByText('Нельзя соединить «Источник трафика» и «База данных».')).toBeVisible();
  const id = base.split('/').at(-1)!;
  const draft = await state(page, id);
  const rejected = await page.request.put(`/api/games/${id}/draft`, {
    data: {
      request_id: crypto.randomUUID(),
      revision: draft.revision,
      topology: { ...draft.draft!, edges: [...draft.draft!.edges, { source: 'traffic', target: 'db' }] }
    }
  });
  expect(rejected.status()).toBe(422);
  expect(rejected.headers()['x-game-error-code']).toBe('incompatible_connection');
  expect((await state(page, id)).draft).toEqual(draft.draft);
  await page.getByRole('button', { name: 'Проверить развёртывание' }).click();
  const review = page.getByRole('dialog', { name: 'Проверка развёртывания' });
  await expect(review.getByRole('heading', { name: 'Прогноз нагрузки и производительности' })).toBeVisible();
  await review.getByRole('button', { name: 'К черновику' }).click();
  await page.getByRole('button', { name: 'Отменить', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Удалить черновик' }).click();
  await expect(page.getByRole('button', { name: 'Создать черновик' })).toBeVisible();
  for (const width of [1920, 1440, 768, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.getByRole('button', { name: 'Вписать в экран' }).click();
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await expect.poll(() => page.locator('.svelte-flow').evaluate((canvas) => {
      const bounds = canvas.getBoundingClientRect();
      const nodes = [...canvas.querySelectorAll('.svelte-flow__node-workbench')].map((node) => node.getBoundingClientRect());
      return nodes.length === 4 && nodes.every((node) => node.left >= bounds.left - 1 && node.right <= bounds.right + 1 &&
        node.top >= bounds.top - 1 && node.bottom <= bounds.bottom + 1);
    })).toBe(true);
    if (visualDir) await page.screenshot({ path: `${visualDir}/russian-${width}.png` });
  }
});

test('complex topology supports nested groups, telemetry capacity and configuration previews', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const id = await create(page, false, false);
  const initial = await state(page, id);
  const request = async (path: string, method: 'POST' | 'PUT', body: object) => {
    const response = await page.request.fetch(`/api/games/${id}${path}`, {
      method, data: { request_id: crypto.randomUUID(), ...body }
    });
    expect(response.ok(), await response.text()).toBe(true);
    return await response.json() as Game;
  };
  const draft = await request('/draft', 'POST', { revision: initial.revision });
  const topology = draft.draft!;
  topology.nodes.push(
    { id: 'limit', kind: 'limiter', name: 'Burst protection', position: { x: 268, y: 245 }, config: { limit: 210 } },
    { id: 'api2', kind: 'api', name: 'Messenger API communications standby for long regional names', position: { x: 715, y: 360 }, config: { cpu: 4, memory: 8 } },
    { id: 'replica', kind: 'replica', name: 'Read replica', position: { x: 945, y: 120 }, config: {} },
    { id: 'cache', kind: 'cache', name: 'Redis cache', position: { x: 945, y: 24 }, config: {} },
    { id: 'queue', kind: 'queue', name: 'Media jobs', position: { x: 945, y: 520 }, config: {} },
    { id: 'worker', kind: 'worker', name: 'Media worker', position: { x: 1175, y: 520 }, config: {} },
    { id: 'monitor', kind: 'monitor', name: 'Metrics collector', position: { x: 1175, y: 270 }, config: { slots: 4, detail: 'Service history' } }
  );
  const positions = {
    traffic: { x: 40, y: 245 }, edge: { x: 490, y: 245 }, api: { x: 715, y: 150 }, db: { x: 1175, y: 110 },
    replica: { x: 945, y: 172 }
  };
  topology.edges = [
    ['traffic', 'limit'], ['limit', 'edge'], ['edge', 'api'], ['edge', 'api2'], ['api', 'db'], ['api2', 'db'],
    ['api', 'cache'], ['api2', 'replica'], ['cache', 'replica'], ['replica', 'db'], ['api', 'queue'],
    ['api2', 'queue'], ['queue', 'worker'], ['api', 'monitor'], ['api2', 'monitor'], ['cache', 'monitor'],
    ['db', 'monitor'], ['worker', 'monitor']
  ].map(([source, target]) => ({ source, target }));
  const edited = await request('/draft', 'PUT', { revision: draft.revision, topology });
  const groups = [
    { id: 'compute-display', name: 'API cluster', members: ['api', 'api2'], collapsed: false },
    { id: 'background-display', name: 'Background processing', members: ['queue', 'worker'], collapsed: false },
    { id: 'application-display', name: 'Messaging subsystem', members: ['compute-display', 'background-display'], collapsed: false }
  ];
  await request('/diagram', 'PUT', { diagram: { positions, groups, routes: {} } });
  const deployed = await request('/deployments', 'POST', { revision: edited.revision });
  expect(deployed.snapshot.monitors.monitor.covered).toEqual(['api', 'api2']);
  expect(deployed.snapshot.monitors.monitor.dropped).toEqual(['cache', 'db', 'worker']);
  await page.reload();
  await expect(page.locator('.svelte-flow__node-workbench')).toHaveCount(11);
  await expect(page.locator('.svelte-flow__node-groupCard')).toHaveCount(3);
  await expect(page.locator('.svelte-flow__edge')).toHaveCount(18);
  await page.getByRole('button', { name: 'Fit view' }).click();
  const clipped = await page.locator('.svelte-flow__node-workbench').evaluateAll((nodes) => nodes.some((node) => {
    const content = node.querySelector('.node-status');
    const heading = node.querySelector('strong');
    const meter = node.querySelector('.meter');
    const box = node.getBoundingClientRect();
    return !content || !heading || !heading.title || content.getBoundingClientRect().bottom > box.bottom + 1 ||
      heading.getBoundingClientRect().right > box.right + 1 || (meter && meter.getBoundingClientRect().right > box.right + 1);
  }));
  expect(clipped).toBe(false);
  if (visualDir) await page.screenshot({ path: `${visualDir}/complex-topology.png` });

  const subsystem = page.locator('.svelte-flow__node-groupCard[aria-label="Messaging subsystem"]');
  await subsystem.getByRole('button', { name: 'Collapse group' }).click();
  await expect(page.locator('.svelte-flow__node-groupCard')).toHaveCount(1);
  await expect(page.locator('.svelte-flow__node-workbench')).toHaveCount(7);
  await expect.poll(async () => (await state(page, id)).diagram.groups.find((group) => group.id === 'application-display')?.collapsed).toBe(true);
  expect((await state(page, id)).snapshot).toEqual(deployed.snapshot);
  await page.getByRole('button', { name: 'Run simulation at normal speed' }).click();
  await expect.poll(async () => (await state(page, id)).tick).toBeGreaterThan(deployed.tick);
  await subsystem.getByRole('button', { name: 'Expand group' }).click();
  await expect(page.locator('.svelte-flow__node-groupCard')).toHaveCount(3);
  const running = await state(page, id);
  expect(running.production).toEqual(deployed.production);
  expect(running.revision).toBe(deployed.revision);
  expect(running.snapshot.metrics.throughput).toBeGreaterThan(0);
  await pause(page);

  await navigate(page, 'Telemetry');
  await expect(page.getByText('Collection capacity exceeded.', { exact: false })).toBeVisible();
  const coverage = page.getByRole('heading', { name: 'Monitoring coverage' });
  await expect(coverage).toBeVisible();
  if (visualDir) {
    await coverage.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${visualDir}/monitoring-coverage.png` });
  }

  await page.goto(`/game/${id}?view=build&component=db`);
  await page.getByRole('button', { name: 'Edit configuration' }).click();
  const config = page.getByRole('dialog', { name: 'Component configuration' });
  await config.getByRole('button', { name: 'Help with Connection pool limit' }).click();
  await expect(config.getByRole('tooltip').filter({ hasText: 'limits' })).toBeVisible();
  if (visualDir) await page.screenshot({ path: `${visualDir}/configuration-help.png` });
  await config.getByLabel('Database vCPU', { exact: true }).fill('8');
  await config.getByRole('button', { name: 'Preview cost and capacity' }).click();
  await expect(config.getByRole('heading', { name: 'Capacity forecast' })).toBeVisible();
  await expect(config.getByText('Daily infrastructure ·', { exact: false })).toBeVisible();
});

test('port guidance rejects incompatible links and reconnects endpoints in Draft', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page, false, false);
  const initial = await state(page, id);
  await page.getByRole('button', { name: 'Create draft' }).click();
  await expect(page.getByRole('button', { name: 'Review deployment' })).toBeVisible();
  const node = (id: string) => page.locator(`.svelte-flow__node[data-id="${id}"]`);
  const drag = async (from: ReturnType<Page['locator']>, to: ReturnType<Page['locator']>) => {
    await expect.poll(() => from.evaluate((element) => {
      const box = element.getBoundingClientRect();
      return document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2) === element;
    })).toBe(true);
    const a = (await from.boundingBox())!;
    await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
    await page.mouse.down();
    await page.mouse.move(a.x + a.width / 2 + 12, a.y + a.height / 2);
    await expect(page.getByText('Highlighted ports accept this connection.')).toBeVisible();
    const current = (await to.boundingBox())!;
    await page.mouse.move(current.x + current.width / 2, current.y + current.height / 2, { steps: 8 });
    const stable = (await to.boundingBox())!;
    await page.mouse.move(stable.x + stable.width / 2, stable.y + stable.height / 2);
    await page.mouse.up();
  };
  await drag(node('traffic').locator('.svelte-flow__handle.source'), node('db').locator('.target'));
  await expect(page.getByText('Traffic source cannot connect to Database.')).toBeVisible();
  expect((await state(page, id)).draft?.edges).toEqual(initial.production.edges);

  const from = (await node('traffic').boundingBox())!;
  const to = (await node('edge').boundingBox())!;
  await page.mouse.click((from.x + from.width + to.x) / 2, from.y + from.height / 2);
  const reconnect = page.locator('.svelte-flow__edgeupdater-target');
  await expect(reconnect).toBeVisible();
  await drag(reconnect, node('api').locator('.target'));
  await expect.poll(async () => (await state(page, id)).draft?.edges.some((edge) => edge.source === 'traffic' && edge.target === 'api')).toBe(true);
  expect((await state(page, id)).production).toEqual(initial.production);
  await page.getByRole('button', { name: 'Show component list' }).click();
  await page.getByRole('button', { name: 'Incoming traffic → Messenger API' }).click();
  await page.getByRole('button', { name: 'Show topology canvas' }).click();
  await page.getByRole('button', { name: 'Add waypoint' }).click();
  await expect.poll(async () => (await state(page, id)).diagram.routes['traffic:api']?.length).toBe(1);
  const routeBeforeDeploy = (await state(page, id)).diagram.routes['traffic:api'];
  await deploy(page);
  await page.reload();
  await expect(page.locator('.svelte-flow__edge[data-id="traffic:api"]')).toBeAttached();
  const final = await state(page, id);
  expect(final.production.edges.some((edge) => edge.source === 'traffic' && edge.target === 'api')).toBe(true);
  expect(final.diagram.routes['traffic:api']).toEqual(routeBeforeDeploy);
});

test('a new API server in a reopened save keeps its links and route through deployment', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page, false, false);
  const original = await state(page, id);
  await page.getByRole('link', { name: 'Service Unavailable main menu' }).click();
  await page.getByRole('link', { name: /Saved games/ }).click();
  await page.getByRole('link', { name: new RegExp(serviceName) }).click();
  await page.getByRole('button', { name: 'Add node' }).click();
  await page.getByRole('dialog', { name: 'Component library' }).getByRole('button', { name: 'API server', exact: true }).click();
  await connect(page, 'Edge balancer', 'API server');
  await connect(page, 'API server', 'Primary database');
  const drafted = await state(page, id);
  const added = drafted.draft!.nodes.find((node) => node.kind === 'api' && node.id !== 'api')!;
  expect(drafted.production).toEqual(original.production);

  await page.getByRole('button', { name: 'Show component list' }).click();
  await page.getByRole('button', { name: 'API server → Primary database', exact: true }).click();
  await page.getByRole('button', { name: 'Show topology canvas' }).click();
  await page.getByRole('button', { name: 'Add waypoint' }).click();
  const routeKey = `${added.id}:db`;
  await expect.poll(async () => (await state(page, id)).diagram.routes[routeKey]?.length).toBe(1);
  const waypoint = page.getByRole('button', { name: 'Waypoint 1' });
  await page.getByRole('button', { name: 'Fit view' }).click();
  await waypoint.focus();
  await page.keyboard.press('ArrowDown');
  await expect.poll(async () => (await state(page, id)).diagram.routes[routeKey]?.[0].y).toBeGreaterThan(
    (added.position.y + original.production.nodes.find((node) => node.id === 'db')!.position.y) / 2 + 50.5
  );
  const route = (await state(page, id)).diagram.routes[routeKey];
  await deploy(page);
  await page.reload();
  await expect(page.locator(`.svelte-flow__edge[data-id="${routeKey}"]`)).toBeAttached();
  const restored = await state(page, id);
  expect(restored.production).toEqual(drafted.draft);
  expect(restored.diagram.routes[routeKey]).toEqual(route);
});

test('inspector keeps both tabs through live updates and preserves draft values', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 720 });
  const id = await create(page, false, false);
  const inspector = page.getByRole('complementary', { name: 'Component inspector' });
  const config = inspector.getByRole('button', { name: 'Configuration', exact: true });
  const metrics = inspector.getByRole('button', { name: 'Metrics', exact: true });
  await inspector.getByRole('button', { name: 'Add replica' }).click();
  await expect.poll(async () => (await state(page, id)).draft?.nodes.find(({ id }) => id === 'api')?.config.instances).toBe(2);
  await metrics.click();
  await expect(metrics).toHaveAttribute('aria-pressed', 'true');
  await expect(inspector.getByRole('heading', { name: 'Messenger API' })).toBeVisible();
  await expect(inspector.getByText('Component metrics require a linked Monitoring collector.')).toBeVisible();
  await expect(inspector.getByRole('button', { name: 'Add replica' })).toHaveCount(0);
  const tick = (await state(page, id)).tick;
  await fast(page);
  await expect.poll(async () => (await state(page, id)).tick).toBeGreaterThan(tick + 2);
  await pause(page);
  await expect(metrics).toHaveAttribute('aria-pressed', 'true');
  await config.click();
  await expect(config).toHaveAttribute('aria-pressed', 'true');
  await expect(inspector.getByText('2', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Show component list' }).click();
  await page.getByRole('button', { name: 'Primary database Database' }).click();
  await expect(inspector.getByRole('heading', { name: 'Primary database' })).toBeVisible();
  await expect(config).toHaveAttribute('aria-pressed', 'true');
});

test('monetization controls, revenue history and server time render in both languages', async ({ page }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page, false, false);
  await navigate(page, 'Product');
  const ads = page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Advertising', exact: true }) });
  const premium = page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Premium subscriptions', exact: true }) });
  const open = (item: typeof ads) => item.getByRole('button', { name: 'Feature details' }).click();
  for (const item of [ads, premium]) {
    await open(item);
    await page.getByRole('button', { name: 'Start development' }).click();
  }
  await fast(page);
  await expect(premium.getByText('Ready to release')).toBeVisible({ timeout: 20_000 });
  await pause(page);
  for (const item of [ads, premium]) {
    await open(item);
    await page.getByRole('button', { name: 'Release feature' }).click();
    await expect(item.getByText('Released and enabled')).toBeVisible();
  }
  await navigate(page, 'Growth');
  await page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'North America', exact: true }) })
    .getByRole('button', { name: 'Start preparation' }).click();
  const update = await page.request.put(`/api/games/${id}/clock`, { data: { request_id: crypto.randomUUID(), speed: 5 } });
  expect(update.ok()).toBeTruthy();
  await page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'North America', exact: true }) })
    .getByRole('button', { name: 'Launch market' }).click({ timeout: 20_000 });
  await pause(page);
  await navigate(page, 'Product');
  await page.getByLabel('Ad intensity').selectOption('high');
  await page.getByLabel('Price per game month (USD)').fill('5.50');
  await page.getByLabel('Offer faster synchronization').uncheck();
  await page.getByRole('button', { name: 'Save product settings' }).click();
  await expect.poll(async () => (await state(page, id)).product).toMatchObject({
    ad_intensity: 'high', premium_price: 5.5, premium_fast_sync: false,
  });
  if (visualDir) await page.getByRole('heading', { name: 'Product settings' }).scrollIntoViewIfNeeded();
  if (visualDir) await page.screenshot({ path: `${visualDir}/monetization-1440.png` });

  await fast(page);
  await expect.poll(async () => (await state(page, id)).economy.revenue_sources.advertising).toBeGreaterThan(0);
  await pause(page);
  await open(ads);
  await page.getByRole('button', { name: 'Disable feature', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm disable' }).click();
  await expect(ads.getByText('Released but disabled')).toBeVisible();
  expect((await state(page, id)).snapshot.demand.ad).toBeUndefined();
  await open(ads);
  await page.getByRole('button', { name: 'Enable feature' }).click();
  await expect(ads.getByText('Released and enabled')).toBeVisible();

  await navigate(page, 'Finance');
  await expect(page.getByRole('heading', { name: 'Revenue breakdown' })).toBeVisible();
  await page.getByLabel('Revenue history').selectOption('advertising');
  await expect(page.getByRole('img', { name: /Revenue per simulation step/ })).toBeVisible();
  const final = await state(page, id);
  expect(final.economy.revenue_sources.advertising).toBeCloseTo(final.economy.revenue);
  expect(final.economy.daily_total_expenses).toBeCloseTo(final.economy.daily_operating + 1420);
  await page.getByRole('button', { name: 'Dismiss notification' }).click();
  if (visualDir) await page.screenshot({ path: `${visualDir}/monetized-finance-1440.png`, fullPage: true });
  await navigate(page, 'Telemetry');
  const clock = final.snapshot.demand_overview!;
  const time = [Math.floor(clock.utc_minute / 60), clock.utc_minute % 60].map((value) => String(value).padStart(2, '0')).join(':');
  await expect(page.getByTestId('game-utc-time')).toHaveText(`Day ${clock.day} / ${time} UTC`);
  expect(final.day).toBe(clock.day);
  await expect(page.getByRole('heading', { name: 'North America' })).toBeVisible();

  await page.goto('/?view=settings');
  await page.getByLabel('Interface language').selectOption('ru');
  await page.setViewportSize({ width: 390, height: 844 });
  for (const [section, heading] of [['finance', 'Структура выручки'], ['product', 'Настройки продукта'], ['monitor', 'Трафик по регионам']]) {
    await page.goto(`/game/${id}?view=${section}`);
    await expect(page.getByRole('heading', { name: heading })).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    if (visualDir) await page.screenshot({ path: `${visualDir}/monetized-${section}-ru-390.png`, fullPage: true });
  }
});
