import { expect, test, type Page, type Request } from '@playwright/test';
import type { Game } from '../src/lib/types';
import { choose } from './forms';

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
  await choose(dialog.getByRole('combobox', { name: 'Source component', exact: true }), { label: from });
  await choose(dialog.getByRole('combobox', { name: 'Target component', exact: true }), { label: to });
  await dialog.getByRole('button', { name: 'Connect components' }).click();
  await expect(dialog).toBeHidden();
}

async function mapSettings(page: Page) {
  await page.getByRole('button', { name: 'Map settings', exact: true }).click();
  return page.getByRole('dialog', { name: 'Map settings' });
}

async function setMapView(page: Page, view: 'list' | 'canvas', touch = false) {
  const settings = await mapSettings(page);
  const toggle = settings.getByRole('button', { name: view === 'list' ? 'Show component list' : 'Show topology canvas' });
  if (touch) await toggle.tap();
  else await toggle.click();
  await expect(settings).toBeHidden();
}

async function openInspector(page: Page, label = 'Open component') {
  await page.getByRole('button', { name: label, exact: true }).click();
  const inspector = page.getByRole('dialog', { name: 'Component inspector' });
  await expect(inspector).toBeVisible();
  return inspector;
}

async function closeInspector(page: Page) {
  const inspector = page.getByRole('dialog', { name: 'Component inspector' });
  await inspector.getByRole('button', { name: 'Close dialog' }).click();
  await expect(inspector).toBeHidden();
}

async function addWaypoint(page: Page) {
  const inspector = await openInspector(page, 'Inspect selection');
  await inspector.getByRole('button', { name: 'Add waypoint', exact: true }).click();
  await closeInspector(page);
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

test('left click selects a component and right click or Shift+F10 opens its actions', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page, false, false);
  const initial = await state(page, id);
  const original = initial.production.nodes.find((node) => node.id === 'api')!;
  const node = page.locator('.svelte-flow__node[data-id="api"]');
  const actions = page.getByRole('group', { name: 'Component actions' });

  const database = page.locator('.svelte-flow__node[data-id="db"]');
  await database.click();
  await expect(database).toHaveClass(/selected/);
  await expect(actions).toHaveCount(0);
  await node.click();
  await expect(node).toHaveClass(/selected/);
  await expect(actions).toHaveCount(0);
  await node.click({ button: 'right' });
  await expect(actions.getByRole('button', { name: 'Add node' })).toHaveCount(0);
  await expect(actions.getByRole('button', { name: 'Component info' })).toBeFocused();
  await actions.getByRole('button', { name: 'Component info' }).click();
  await expect(page.getByRole('dialog', { name: 'Component inspector' }).getByRole('heading', { name: original.name })).toBeVisible();
  await closeInspector(page);

  await node.press('Enter');
  await expect(actions).toHaveCount(0);
  await node.press('Shift+F10');
  await actions.getByRole('button', { name: 'Copy component' }).click();
  const copy = page.locator('.svelte-flow__node[aria-label="Messenger API (copy)"]');
  await expect(copy).toHaveClass(/selected/);
  const copied = await state(page, id);
  const { id: copyId, position, ...settings } = copied.draft!.nodes.find((item) => item.name === 'Messenger API (copy)')!;
  expect(copyId).not.toBe(original.id);
  expect(position).not.toEqual(original.position);
  expect(settings).toEqual({ kind: original.kind, name: 'Messenger API (copy)', config: original.config });
  expect(copied.draft?.edges).toEqual(initial.production.edges);
  expect(copied.production).toEqual(initial.production);

  await copy.click({ button: 'right' });
  await actions.getByRole('button', { name: 'Edit configuration' }).click();
  const configuration = page.getByRole('dialog', { name: 'Component configuration' });
  await expect(configuration.getByLabel('Component name')).toHaveValue('Messenger API (copy)');
  await configuration.getByRole('button', { name: 'Close dialog' }).click();

  await page.getByRole('button', { name: 'Undo draft edit' }).click();
  await expect(copy).toHaveCount(0);
  await page.getByRole('button', { name: 'Redo draft edit' }).click();
  await expect(copy).toBeVisible();
  await page.reload();
  await expect(copy).toBeVisible();

  await page.locator('.svelte-flow__node[data-id="traffic"]').click({ button: 'right' });
  await expect(actions.getByRole('button', { name: 'Component info' })).toBeVisible();
  await expect(actions.getByRole('button', { name: 'Copy component' })).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(actions).toBeHidden();

  const pane = page.locator('.svelte-flow__pane');
  const canvasActions = page.getByRole('group', { name: 'Canvas actions' });
  await pane.click({ position: { x: 30, y: 95 } });
  await expect(page.locator('.svelte-flow__node.selected')).toHaveCount(0);
  await expect(canvasActions).toHaveCount(0);
  await pane.click({ button: 'right', position: { x: 30, y: 95 } });
  await expect(canvasActions.getByRole('button', { name: 'Add node' })).toBeVisible();
  await expect(canvasActions.getByRole('button', { name: 'Copy component' })).toHaveCount(0);
});

test('right-click menus create nested groups and edit membership without changing production', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page, false, false);
  const before = await state(page, id);
  const node = (id: string) => page.locator(`.svelte-flow__node-workbench[data-id="${id}"]`);
  const card = (name: string) => page.locator(`.svelte-flow__node-groupCard[aria-label="${name}"]`);
  const componentActions = page.getByRole('group', { name: 'Component actions' });
  const groupActions = page.getByRole('group', { name: 'Group actions' });
  const createGroup = page.getByRole('dialog', { name: 'Create group' });

  await node('db').click({ button: 'right' });
  await componentActions.getByRole('button', { name: 'Create group' }).click();
  await createGroup.getByLabel('Group name').fill('Data');
  await createGroup.getByRole('button', { name: 'Save group' }).click();
  await expect(card('Data')).toBeVisible();

  await page.locator('.svelte-flow__pane').click({ button: 'right', position: { x: 30, y: 95 } });
  await page.getByRole('group', { name: 'Canvas actions' }).getByRole('button', { name: 'Create group' }).click();
  await createGroup.getByLabel('Group name').fill('Compute');
  await createGroup.getByRole('checkbox', { name: 'Messenger API' }).check();
  await createGroup.getByRole('button', { name: 'Save group' }).click();
  await expect(card('Compute')).toBeVisible();

  await card('Data').locator('.group-header strong').click();
  await expect(card('Data')).toHaveClass(/selected/);
  await expect(groupActions).toHaveCount(0);
  await card('Data').locator('.group-header strong').click({ button: 'right' });
  await groupActions.getByRole('button', { name: 'Create parent group' }).click();
  await createGroup.getByLabel('Group name').fill('Backend');
  await expect(createGroup.getByRole('checkbox', { name: 'Data', exact: true })).toBeChecked();
  await createGroup.getByRole('checkbox', { name: 'Compute' }).check();
  await expect(createGroup.getByRole('checkbox', { name: 'Messenger API' })).toBeDisabled();
  await createGroup.getByRole('button', { name: 'Save group' }).click();
  await expect.poll(async () => {
    const groups = (await state(page, id)).diagram.groups;
    return groups.find((group) => group.name === 'Backend')?.members.map((id) => groups.find((group) => group.id === id)?.name);
  }).toEqual(['Data', 'Compute']);

  await node('edge').click({ button: 'right' });
  await componentActions.getByRole('button', { name: 'Add to group' }).click();
  const destination = page.getByRole('dialog', { name: 'Add to group' });
  await choose(destination.getByRole('combobox', { name: 'Destination group' }), { label: 'Compute' });
  await destination.getByRole('button', { name: 'Add to group' }).click();
  const computeMembers = async () => (await state(page, id)).diagram.groups.find((group) => group.name === 'Compute')?.members;
  await expect.poll(computeMembers).toEqual(['api', 'edge']);
  await node('edge').click({ button: 'right' });
  await componentActions.getByRole('button', { name: 'Remove from group' }).click();
  await expect.poll(computeMembers).toEqual(['api']);
  await expect(node('edge')).toBeVisible();

  await card('Compute').press('Shift+F10');
  await groupActions.getByRole('button', { name: 'Edit group' }).click();
  const edit = page.getByRole('dialog', { name: 'Edit group' });
  await expect(edit.getByRole('checkbox', { name: 'Backend' })).toHaveCount(0);
  await edit.getByRole('button', { name: 'Close dialog' }).click();

  await card('Backend').locator('.group-header strong').click({ button: 'right' });
  await groupActions.getByRole('button', { name: 'Ungroup' }).click();
  await expect.poll(async () => (await state(page, id)).diagram.groups.map((group) => group.name)).toEqual(['Data', 'Compute']);
  await page.reload();
  await expect(card('Data')).toBeVisible();
  await expect(card('Compute')).toBeVisible();
  await setMapView(page, 'list');
  const row = page.getByRole('button', { name: 'Compute Expanded' });
  await row.click();
  await expect(row).toHaveAttribute('aria-pressed', 'true');
  await expect(groupActions).toHaveCount(0);
  await row.click({ button: 'right' });
  await expect(groupActions.getByRole('button', { name: 'Edit group' })).toBeVisible();
  const after = await state(page, id);
  expect(after.production).toEqual(before.production);
  expect(after.draft).toBeNull();
  expect(after.revision).toBe(before.revision);
});

test('fast clock shortcuts suspend canvas rendering and allow an override on a narrow screen', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  const id = await create(page, false, false);
  const canvas = page.locator('.svelte-flow');
  const speeds = page.getByRole('group', { name: 'Game speed' });
  const speed = (value: number) => speeds.getByRole('button', { name: `Fast speed (${value}×)` });
  await expect(canvas).toBeVisible();
  await speed(10).click();
  await expect(speed(10)).toHaveAttribute('aria-pressed', 'true');
  await expect(canvas).toBeVisible();
  await page.keyboard.press('5');
  await expect(speed(20)).toHaveAttribute('aria-pressed', 'true');
  await expect(canvas).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Messenger API API server' })).toBeVisible();
  await speed(50).click();
  await expect(speed(50)).toHaveAttribute('aria-pressed', 'true');
  await expect(canvas).toHaveCount(0);
  await expect.poll(async () => (await state(page, id)).speed).toBe(50);
  expect((await state(page, id)).tick).toBeGreaterThan(0);
  expect(await speed(50).evaluate((button) => button.getBoundingClientRect().right)).toBeLessThan(320);

  await setMapView(page, 'canvas');
  await expect(canvas).toBeVisible();
  await page.reload();
  await expect(speed(50)).toHaveAttribute('aria-pressed', 'true');
  await expect(canvas).toBeVisible();
  const settings = await mapSettings(page);
  await settings.getByRole('switch', { name: 'Show component list at 20× and 50×' }).click();
  await expect(canvas).toHaveCount(0);
  await settings.getByRole('button', { name: 'Close dialog' }).click();
  await pause(page);
  await expect(canvas).toBeVisible();
});

test('the connection line and its rate label show the same request breakdown', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await create(page, false, false);
  const edge = page.locator('.svelte-flow__edge[data-id="traffic:edge"]');
  const path = edge.locator('.svelte-flow__edge-interaction');
  const pointOnLine = () => path.evaluate((element: SVGPathElement) => {
    const matrix = element.getScreenCTM()!;
    for (const fraction of [.15, .85, .07, .93, .25, .75]) {
      const { x, y } = element.getPointAtLength(element.getTotalLength() * fraction).matrixTransform(matrix);
      if (element.closest('.svelte-flow__edge')?.contains(document.elementFromPoint(x, y))) return { x, y };
    }
  });
  const edgePoint = (await pointOnLine())!;
  expect(edgePoint).toBeDefined();
  const rate = page.locator('.rate-layer[data-edge-id="traffic:edge"]').getByRole('button', { name: /Connection breakdown for/ });
  const tooltip = page.getByRole('tooltip');
  await rate.hover();
  await expect(tooltip).toContainText('Request types');
  const breakdown = (await tooltip.textContent())!;
  await page.mouse.move(5, 5);
  await expect(tooltip).toBeHidden();
  await page.mouse.move(edgePoint.x, edgePoint.y);
  await expect(tooltip).toHaveText(breakdown);
  await page.mouse.move(5, 5);
  await expect(tooltip).toBeHidden();
  await page.mouse.click(edgePoint.x, edgePoint.y);
  await expect(edge).toHaveClass(/selected/);

  const canvas = (await page.locator('.svelte-flow').boundingBox())!;
  await page.mouse.move(canvas.x + canvas.width / 2, canvas.y + canvas.height / 2);
  await page.keyboard.down('Control');
  await page.mouse.wheel(0, 900);
  await page.keyboard.up('Control');
  await expect(rate).toHaveCount(0);
  let zoomedPoint: Awaited<ReturnType<typeof pointOnLine>>;
  await expect.poll(async () => zoomedPoint = await pointOnLine()).toBeDefined();
  await page.mouse.move(zoomedPoint!.x, zoomedPoint!.y);
  await expect(tooltip).toHaveText(breakdown);
});

test('A and B · create, run, save, reopen, edit and scale production', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page);
  await expect(page.getByRole('img', { name: 'Minimap' })).toBeInViewport();
  const first = await state(page, id);
  expect(first.tick).toBe(0);
  expect(first.snapshot.metrics.rps).toBeGreaterThan(100);
  await expect((await openInspector(page)).getByRole('heading', { name: 'Messenger API' })).toBeVisible();
  await closeInspector(page);
  if (visualDir) await page.screenshot({ path: `${visualDir}/topology-1440.png` });

  await fast(page);
  await expect.poll(async () => (await state(page, id)).tick).toBeGreaterThan(2);
  const packet = page.locator('.svelte-flow__edge[data-id="traffic:edge"] circle.traffic').first();
  await expect(packet).toBeVisible();
  await pause(page);
  await expect(packet).toHaveCount(0);
  await page.getByRole('button', { name: 'Save game' }).click();
  await expect(page.getByRole('region', { name: 'Notifications' }).getByText('Game saved', { exact: true })).toBeVisible();
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
  await openInspector(page);
  await page.getByRole('button', { name: 'Edit configuration' }).click();
  await choose(page.getByRole('combobox', { name: 'Collection scope', exact: true }), 'Service history');
  await page.getByRole('button', { name: 'Save to draft' }).click();
  await closeInspector(page);
  await deploy(page);

  await navigate(page, 'Growth');
  await page.getByRole('heading', { name: 'Community campaign', exact: true }).locator('..').getByRole('button', { name: 'Plan campaign' }).click();
  await page.getByRole('button', { name: 'Start campaign' }).click();
  await fast(page);
  await expect.poll(async () => (await state(page, id)).audience, { timeout: 18_000 }).toBeGreaterThan(10_000);
  await pause(page);
  const before = await state(page, id);
  expect(before.snapshot.components.api.utilization.CPU).toBeGreaterThan(1);

  await navigate(page, 'Topology');
  await page.locator('.svelte-flow__node[aria-label="Messenger API"]').click();
  const inspector = await openInspector(page);
  await inspector.getByRole('button', { name: 'Metrics', exact: true }).click();
  await expect(inspector.getByRole('heading', { name: 'Resource utilization' })).toBeVisible();
  const cpu = inspector.getByRole('meter', { name: 'CPU' });
  await expect(cpu).toHaveAttribute('aria-valuetext', /^[1-9]\d{2,}%$/);
  if (visualDir) await page.screenshot({ path: `${visualDir}/overloaded-inspector.png` });
  await page.getByRole('button', { name: 'Edit configuration' }).click();
  await choose(page.getByRole('combobox', { name: 'Instance size', exact: true }), { label: 'Performance P4 · 4 vCPU / 8 GB' });
  await page.getByRole('button', { name: 'Save to draft' }).click();
  await closeInspector(page);
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
  await navigate(page, 'Telemetry');
  await expect(page.getByRole('heading', { name: 'System telemetry' })).toBeVisible();
  await expect(page.getByRole('figure', { name: /Request traffic/ })).toBeVisible();
  await expect(page.getByRole('figure', { name: /Peak resource load for Messenger API/ })).toBeVisible();
  await choose(page.getByRole('combobox', { name: 'Component', exact: true }), 'db');
  await expect(page.getByRole('figure', { name: /Peak resource load for Primary database/ })).toBeVisible();
  if (visualDir) await page.screenshot({ path: `${visualDir}/telemetry-1440.png` });
});

test('C and D · campaign and product release change workload and finances', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page, false, false);
  await navigate(page, 'Growth');
  if (visualDir) await page.screenshot({ path: `${visualDir}/growth-1440.png` });
  await page.getByRole('heading', { name: 'Community campaign', exact: true }).locator('..').getByRole('button', { name: 'Plan campaign' }).click();
  const plan = page.getByRole('dialog', { name: 'Campaign planning' });
  await expect(plan.getByRole('heading', { name: 'Capacity forecast' })).toBeVisible();
  await plan.getByRole('button', { name: 'Start campaign' }).click();
  await expect(plan).toBeHidden();
  expect((await state(page, id)).economy.marketing).toBe(420);

  await navigate(page, 'Product');
  const groups = page.getByRole('article').filter({ has: page.getByText('Group chats', { exact: true }) });
  await groups.getByRole('button', { name: /Group chats/ }).click();
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
  await groups.getByRole('button', { name: /Group chats/ }).click();
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
  await closeInspector(page);
  await page.getByRole('button', { name: 'Add node' }).click();
  await page.getByRole('dialog', { name: 'Component library' }).getByRole('button', { name: 'Monitoring', exact: true }).click();
  await connect(page, 'Primary database', 'Monitoring');
  await deploy(page);
  const constrained = await state(page, id);
  expect(constrained.snapshot.components.db.status).toBe('overloaded');
  expect(constrained.snapshot.components.api).toBeUndefined();

  await page.goto(`/game/${id}?view=monitor`);
  const diagnosis = page.getByRole('article', { name: 'Diagnostics' });
  await expect(diagnosis).toContainText('Overloaded');
  await expect(diagnosis.getByText('Database write capacity exceeded')).toHaveCount(0);
  await diagnosis.getByRole('link', { name: 'Primary database' }).click();
  const inspector = page.getByRole('dialog', { name: 'Component inspector' });
  await inspector.getByRole('button', { name: 'Metrics', exact: true }).click();
  await expect(inspector.getByText('Sustainable writes at current read load')).toBeVisible();
  await expect(inspector.getByText('Database write capacity exceeded')).toHaveCount(0);
  const diskHelp = inspector.getByRole('link', { name: 'Help with Disk I/O' });
  await diskHelp.click();
  await expect(page).toHaveURL(/article=database-io#io$/);
  await expect(page.getByRole('heading', { name: 'Disk I/O utilization' })).toBeVisible();
  config = await editDatabase();
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
  await expect(config.getByRole('heading', { name: 'Database upgrade forecast' })).toBeVisible();
  await expect(config.getByRole('row', { name: /Sustainable writes/ })).toBeVisible();
  await config.getByRole('button', { name: 'Save to draft' }).click();
  await expect(config).toBeHidden();
  await closeInspector(page);
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
  await choose(config.getByRole('combobox', { name: 'Storage type', exact: true }), 'NVMe');
  await config.getByRole('button', { name: 'Save to draft' }).click();
  await expect(config).toBeHidden();
  await closeInspector(page);
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
  await (await openInspector(page)).getByRole('button', { name: 'Add replica' }).click();
  await closeInspector(page);
  await deploy(page);
  expect((await state(page, id)).snapshot.metrics.availability).toBeGreaterThan(.98);
  await fast(page);
  await expect.poll(async () => (await state(page, id)).incidents.find((item) => item.title === 'Instance failure drill')?.active).toBe(false);
  await pause(page);
});

test.describe('Mobile workbench', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: process.env.TEST_BROWSER !== 'firefox' });

  test('tapping a block selects it and its inspector offers component actions', async ({ page }) => {
    await create(page, true, false);
    const node = page.locator('.svelte-flow__node[data-id="api"]');
    await node.tap();
    await expect(node).toHaveClass(/selected/);
    await expect(page.getByRole('group', { name: 'Component actions' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Open component', exact: true }).tap();
    const inspector = page.getByRole('dialog', { name: 'Component inspector' });
    await expect(inspector.getByRole('heading', { name: 'Messenger API' })).toBeVisible();
    await expect(inspector.getByRole('button', { name: 'Copy component' })).toBeVisible();
    await inspector.getByRole('button', { name: 'Create group' }).tap();
    const group = page.getByRole('dialog', { name: 'Create group' });
    await expect(group.getByRole('checkbox', { name: 'Messenger API' })).toBeChecked();
  });

  test('the minimap stays in the bottom-right corner on narrow screens', async ({ page }) => {
    await create(page, true, false);
    const graph = page.locator('.svelte-flow');
    const map = graph.getByRole('img', { name: 'Minimap' });
    await expect(map).toBeInViewport();
    const canvas = (await graph.boundingBox())!;
    const preview = (await map.boundingBox())!;
    const right = canvas.x + canvas.width - preview.x - preview.width;
    const bottom = canvas.y + canvas.height - preview.y - preview.height;
    expect(right).toBeGreaterThanOrEqual(0);
    expect(right).toBeLessThan(24);
    expect(bottom).toBeGreaterThanOrEqual(0);
    expect(bottom).toBeLessThan(24);
    await setMapView(page, 'list', true);
    await expect(map).toHaveCount(0);
    await setMapView(page, 'canvas', true);
    await expect(map).toBeVisible();
  });

  test('standard and premium cloud media limits persist on a narrow screen', async ({ page }) => {
    const created = await page.request.post('/api/games', {
      data: { id: crypto.randomUUID(), name: 'Cloud Messenger', seed: 7, settings: { show_tutorial: false } }
    });
    expect(created.ok()).toBeTruthy();
    const { id: initialId } = await created.json();
    const save = await (await page.request.get(`/api/games/${initialId}/export`)).json();
    save.game.released.push('images', 'premium');
    const imported = await page.request.post('/api/games/import', { data: save });
    expect(imported.ok(), await imported.text()).toBeTruthy();
    const { id } = await imported.json();
    await page.goto(`/game/${id}?view=product`);
    await page.getByRole('tab', { name: 'Product settings' }).tap();
    const standard = page.getByLabel('Limit cloud media storage', { exact: true });
    await standard.focus();
    await standard.press('Space');
    await page.getByRole('spinbutton', { name: 'Cloud media limit per user' }).fill('0.25');
    const premium = page.getByRole('combobox', { name: 'Premium cloud media storage' });
    await choose(premium, 'custom');
    await page.getByRole('spinbutton', { name: 'Cloud media limit per subscriber' }).fill('1.5');
    const submit = page.getByRole('button', { name: 'Save product settings' });
    await submit.tap();
    await expect.poll(async () => (await state(page, id)).product).toMatchObject({
      media_quota_gb: 0.25, premium_media_quota_gb: 1.5,
    });
    await choose(premium, 'unlimited');
    await submit.tap();
    await expect.poll(async () => (await state(page, id)).product.premium_media_quota_gb).toBe('unlimited');
    await standard.tap();
    await submit.tap();
    await expect.poll(async () => (await state(page, id)).product.media_quota_gb).toBeNull();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  });

  test('F · navigation, component list, mobile inspector and deployment', async ({ page, browserName }) => {
    const id = await create(page, true);
    const graph = page.locator('.svelte-flow');
    await expect(graph).toBeVisible();
    if (visualDir) await page.screenshot({ path: `${visualDir}/topology-390.png` });
    if (browserName === 'chromium') {
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
    }
    await setMapView(page, 'list', true);
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
    await expect(page.getByRole('region', { name: 'Notifications' }).getByText('Game saved', { exact: true })).toBeVisible();
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
    await library.getByRole('button', { name: 'Close dialog' }).tap();

    await setMapView(page, 'list', true);
    await page.getByRole('button', { name: 'Select multiple' }).tap();
    const api = page.getByRole('button', { name: 'Messenger API API server' });
    if (await api.getAttribute('aria-pressed') !== 'true') await api.tap();
    await page.getByRole('button', { name: 'Primary database Database' }).tap();
    await expect(page.getByRole('button', { name: 'Create group' })).toBeVisible();
    await page.getByRole('button', { name: 'Create group' }).tap();
    const group = page.getByRole('dialog', { name: 'Create group' });
    await group.getByLabel('Group name').fill('Data path');
    await group.getByRole('button', { name: 'Save group' }).tap();
    await openInspector(page, 'Inspect selection');
    await page.getByRole('button', { name: 'Collapse group', exact: true }).tap();
    await expect.poll(async () => (await state(page, id)).diagram.groups[0]?.collapsed).toBe(true);
    expect((await state(page, id)).draft).toBeNull();
    await page.getByRole('button', { name: 'Expand group', exact: true }).tap();
    await expect.poll(async () => (await state(page, id)).diagram.groups[0]?.collapsed).toBe(false);
    await closeInspector(page);
    await page.getByRole('button', { name: 'Data path Expanded' }).tap();
    await expect(page.getByRole('group', { name: 'Group actions' })).toHaveCount(0);
    const inspector = await openInspector(page, 'Inspect selection');
    await expect(inspector.getByRole('button', { name: 'Create parent group' })).toBeVisible();
    await closeInspector(page);

    await page.getByRole('button', { name: 'Add node' }).tap();
    await library.getByRole('button', { name: 'Monitoring', exact: true }).tap();
    await page.getByRole('button', { name: 'Connect', exact: true }).tap();
    const connection = page.getByRole('dialog', { name: 'Connect components' });
    await choose(connection.getByRole('combobox', { name: 'Source component', exact: true }), { label: 'Primary database' });
    await choose(connection.getByRole('combobox', { name: 'Target component', exact: true }), { label: 'Monitoring' });
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
  await setMapView(page, 'list');
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


test('alignment guides snap a component and speed changes keep the canvas and controls stable', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page, false, false);
  await pause(page);
  await page.getByRole('button', { name: 'Create draft' }).click();
  const before = await state(page, id);
  const settings = await mapSettings(page);
  await settings.getByRole('switch', { name: 'Alignment guides' }).check();
  await settings.getByRole('button', { name: 'Close dialog' }).click();
  await expect(settings).toHaveCount(0);

  const node = page.locator('.svelte-flow__node[data-id="api"]');
  const neighbor = page.locator('.svelte-flow__node[data-id="db"]');
  const from = (await node.boundingBox())!;
  const to = (await neighbor.boundingBox())!;
  const start = { x: from.x + from.width / 2, y: from.y + from.height / 2 };
  const horizontal = page.locator('.flow-shell .guide.horizontal');
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(start.x - 32, to.y + to.height / 2 + 5, { steps: 8 });
  await expect(horizontal).toBeVisible();
  await expect.poll(async () => Math.abs((await node.boundingBox())!.y - to.y)).toBeLessThan(1);
  await page.mouse.up();
  await expect(horizontal).toHaveCount(0);
  const dbY = before.draft!.nodes.find((item) => item.id === 'db')!.position.y;
  await expect.poll(async () => (await state(page, id)).diagram.positions.api?.y).toBe(dbY);

  const nodeElement = await node.elementHandle();
  const speed = page.getByRole('button', { name: 'Fast speed (3×)' });
  const save = page.getByRole('button', { name: 'Save game', exact: true });
  let releaseClock!: () => void;
  const pendingClock = new Promise<void>((resolve) => { releaseClock = resolve; });
  await page.route(`**/api/games/${id}/clock`, async (route) => {
    await pendingClock;
    await route.continue();
  });
  try {
    await speed.click();
    await expect(speed).toHaveAttribute('aria-disabled', 'true');
    await expect(speed).toHaveCSS('opacity', '1');
    await expect(save).toHaveCSS('opacity', '1');
    await expect(node.locator('.svelte-flow__handle.connectable')).toHaveCount(2);
  } finally {
    releaseClock();
  }
  await expect(speed).toHaveAttribute('aria-pressed', 'true');
  expect(await nodeElement?.evaluate((element) => element.isConnected)).toBe(true);
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

  await addWaypoint(page);
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
  const expanded = page.locator('.svelte-flow__node-groupCard');
  await expanded.locator('.group-header strong').click();
  await expect(expanded).toHaveClass(/selected/);
  await api.click();
  await expect(api).toHaveClass(/selected/);
  await expect(expanded).not.toHaveClass(/selected/);
  await db.click({ modifiers: ['Control'] });
  await expect(api).toHaveClass(/selected/);
  await expect(db).toHaveClass(/selected/);
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
  const movesApi = (request: Request) =>
    request.url().endsWith('/diagram') && request.method() === 'PATCH' && request.postDataJSON()?.positions?.api;
  page.on('request', (request) => {
    if (movesApi(request)) writes.push(request.method());
  });
  const box = (await api.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 30, box.y + box.height / 2 - 65, { steps: 12 });
  expect(writes).toEqual([]);
  const response = page.waitForResponse((candidate) => Boolean(movesApi(candidate.request())));
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
  await choose(page.getByRole('combobox', { name: 'Interface language', exact: true }), 'ru');
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.goto(`/game/${id}?view=monitor`);
    await expect(page.getByRole('heading', { name: 'Мониторинг системы' })).toBeVisible();
    await expect(page.getByRole('figure', { name: /пиковая загрузка/i })).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    if (visualDir) await page.screenshot({ path: `${visualDir}/russian-monitoring-${width}.png`, fullPage: true });
    await page.goto(`/game/${id}?view=product`);
    await page.getByRole('button', { name: /Голосовые сообщения/ }).click();
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
  await choose(page.getByRole('combobox', { name: 'Interface language', exact: true }), 'ru');
  await expect(page.getByRole('heading', { name: 'Настройки' })).toBeVisible();
  await page.goto('/?view=new');
  await page.getByLabel('Имя сервиса').fill('Мессенджер');
  await page.getByRole('button', { name: 'Создать игру' }).click();
  await expect(page.getByRole('heading', { name: 'Топология инфраструктуры' })).toBeVisible();
  await page.getByRole('button', { name: 'Пропустить обучение', exact: true }).click();
  const base = new URL(page.url()).pathname;
  for (const [view, title] of [['monitor', 'Мониторинг системы'], ['product', 'Функции продукта'], ['growth', 'Аудитория и кампании'],
      ['finance', 'Финансы'], ['events', 'События и инциденты'], ['guide', 'Справка'], ['settings', 'Настройки']]) {
    await page.goto(`${base}?view=${view}`);
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
  }
  await page.goto(`${base}?view=build`);
  await page.getByRole('button', { name: 'Настройки карты', exact: true }).click();
  const settings = page.getByRole('dialog', { name: 'Настройки карты' });
  await settings.getByText('Справочник соединений', { exact: true }).click();
  await expect(settings.getByText('Исходящие соединения', { exact: true })).toBeVisible();
  await settings.getByRole('button', { name: 'Закрыть окно' }).click();
  await expect(settings).toBeHidden();
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
  const monitorPorts = page.locator('.svelte-flow__edge[data-id$=":monitor"] line[data-port="target"]');
  await expect(monitorPorts).toHaveCount(5);
  expect(await monitorPorts.evaluateAll((ports) => new Set(ports.map((port) => port.getAttribute('y1'))).size)).toBe(5);
  const settings = await mapSettings(page);
  await settings.getByRole('switch', { name: 'Metrics collection', exact: true }).uncheck();
  await expect(monitorPorts).toHaveCount(0);
  await settings.getByText('Connection reference', { exact: true }).click();
  await expect(settings.getByText('Input connections', { exact: true })).toBeVisible();
  await settings.getByRole('button', { name: 'Close dialog' }).click();
  await page.reload();
  await expect(page.locator('.svelte-flow__edge')).toHaveCount(13);
  expect((await state(page, id)).production).toEqual(deployed.production);
  await mapSettings(page);
  await settings.getByRole('switch', { name: 'Metrics collection', exact: true }).check();
  await settings.getByRole('button', { name: 'Close dialog' }).click();
  await expect(monitorPorts).toHaveCount(5);
  await expect(settings).toHaveCount(0);
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
  const bundle = page.getByRole('button', { name: 'Connection breakdown for 3×', exact: true });
  await bundle.hover();
  await expect(page.getByRole('tooltip')).toContainText('Metrics collection');
  await page.mouse.move(5, 5);
  await expect(page.getByRole('tooltip')).toHaveCount(0);
  await bundle.focus();
  await expect(page.getByRole('tooltip')).toContainText('Metrics collection');
  await expect(page.getByRole('tooltip')).toContainText('3×');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('tooltip')).toHaveCount(0);
  expect((await state(page, id)).snapshot).toEqual(deployed.snapshot);
  await page.getByRole('button', { name: 'Run simulation at normal speed' }).click();
  await expect.poll(async () => (await state(page, id)).tick).toBeGreaterThan(deployed.tick);
  const trafficEdge = page.locator('.svelte-flow__edge[data-id="traffic:limit"]');
  const packet = trafficEdge.locator('circle.traffic').first();
  await expect(packet).toBeVisible();
  const measureMotion = () => trafficEdge.evaluate(async (edge) => {
    const samples = new Map<Element, { startX: number; startTime: number; x: number; time: number }>();
    let rewound = false;
    const intervals: number[] = [];
    let detached = false;
    let lastFrame: number | undefined;
    for (let frame = 0; frame < 40; frame++) {
      const time = await new Promise<number>(requestAnimationFrame);
      if (lastFrame !== undefined) intervals.push(time - lastFrame);
      lastFrame = time;
      if (!edge.isConnected) detached = true;
      for (const circle of edge.querySelectorAll('circle.traffic')) {
        const x = Number(circle.getAttribute('cx'));
        const sample = samples.get(circle);
        if (!sample) samples.set(circle, { startX: x, startTime: time, x, time });
        else {
          if (x < sample.x - .01) rewound = true;
          sample.x = x;
          sample.time = time;
        }
      }
    }

    let travel = 0;
    let elapsed = 0;
    for (const sample of samples.values()) {
      travel += sample.x - sample.startX;
      elapsed += sample.time - sample.startTime;
    }
    return { speed: travel / elapsed * 1000, rewound, detached, maxFrame: Math.max(...intervals) };
  });
  const normalMotion = await measureMotion();
  expect(normalMotion.detached).toBe(false);
  expect(normalMotion.rewound).toBe(false);
  expect(normalMotion.speed).toBeGreaterThan(30);
  await page.getByRole('button', { name: 'Fast speed (5×)' }).click();
  await expect(page.getByRole('button', { name: 'Fast speed (5×)' })).toHaveAttribute('aria-pressed', 'true');
  const tickBeforeMotion = (await state(page, id)).tick;
  const fastMotion = await measureMotion();
  expect(fastMotion.detached).toBe(false);
  expect(fastMotion.rewound).toBe(false);
  expect(fastMotion.speed / normalMotion.speed, JSON.stringify(fastMotion)).toBeGreaterThan(4.5);
  expect(fastMotion.speed / normalMotion.speed).toBeLessThan(5.5);
  expect((await state(page, id)).tick).toBeGreaterThan(tickBeforeMotion);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(packet).toBeHidden();
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await expect(page.locator('.svelte-flow__edge path[marker-end]')).toHaveCount(0);
  await subsystem.getByRole('button', { name: 'Expand group' }).click();
  await expect(page.locator('.svelte-flow__node-groupCard')).toHaveCount(3);
  const bentEdge = page.locator('.svelte-flow__edge[data-id="api:cache"]');
  await expect(bentEdge.locator('circle.traffic').first()).toBeVisible();
  const distanceFromRoute = await bentEdge.evaluate((edge) => {
    const path = edge.querySelector<SVGPathElement>('.svelte-flow__edge-path')!;
    const length = path.getTotalLength();
    const points = Array.from({ length: Math.ceil(length) + 1 }, (_, distance) => path.getPointAtLength(distance));
    return Math.max(...[...edge.querySelectorAll('circle.traffic')].map((circle) => {
      const x = Number(circle.getAttribute('cx'));
      const y = Number(circle.getAttribute('cy'));
      return Math.min(...points.map((point) => Math.hypot(x - point.x, y - point.y)));
    }));
  });
  expect(distanceFromRoute).toBeLessThan(1);
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
  const fieldHelp = config.getByRole('link', { name: 'Help with Connection pool limit' });
  await fieldHelp.focus();
  await expect(config.getByRole('tooltip').filter({ hasText: 'limits' })).toBeVisible();
  await expect(fieldHelp).toHaveAttribute('href', /article=read-write-throughput#connections$/);
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
  const drag = async (from: ReturnType<Page['locator']>, to: ReturnType<Page['locator']>, compatible: boolean) => {
    await expect.poll(() => from.evaluate((element) => {
      const box = element.getBoundingClientRect();
      return document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2) === element;
    })).toBe(true);
    const a = (await from.boundingBox())!;
    await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
    await page.mouse.down();
    await page.mouse.move(a.x + a.width / 2 + 12, a.y + a.height / 2);
    await expect(page.getByText('Highlighted ports accept this connection.')).toBeVisible();
    if (compatible) await expect(to).toHaveClass(/valid-port/);
    else await expect(to).not.toHaveClass(/valid-port/);
    const current = (await to.boundingBox())!;
    await page.mouse.move(current.x + current.width / 2, current.y + current.height / 2, { steps: 8 });
    const stable = (await to.boundingBox())!;
    await page.mouse.move(stable.x + stable.width / 2, stable.y + stable.height / 2);
    await page.mouse.up();
  };
  await drag(node('traffic').locator('.svelte-flow__handle.source'), node('db').locator('.target'), false);
  await expect(page.getByText('Traffic source cannot connect to Database.')).toBeVisible();
  expect((await state(page, id)).draft?.edges).toEqual(initial.production.edges);

  const from = (await node('traffic').boundingBox())!;
  const to = (await node('edge').boundingBox())!;
  await page.mouse.click((from.x + from.width + to.x) / 2, from.y + from.height / 2);
  const reconnect = page.locator('.svelte-flow__edgeupdater-target');
  await expect(reconnect).toBeVisible();
  await drag(reconnect, node('api').locator('.target'), true);
  await expect.poll(async () => (await state(page, id)).draft?.edges.some((edge) => edge.source === 'traffic' && edge.target === 'api')).toBe(true);
  expect((await state(page, id)).production).toEqual(initial.production);
  await setMapView(page, 'list');
  await page.getByRole('button', { name: 'Incoming traffic → Messenger API' }).click();
  await setMapView(page, 'canvas');
  await addWaypoint(page);
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

  await setMapView(page, 'list');
  await page.getByRole('button', { name: 'API server → Primary database', exact: true }).click();
  await setMapView(page, 'canvas');
  await addWaypoint(page);
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
  const inspector = await openInspector(page);
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
  const setSpeed = (speed: number) => page.request.put(`/api/games/${id}/clock`, { data: { request_id: crypto.randomUUID(), speed } });
  expect((await setSpeed(3)).ok()).toBeTruthy();
  await expect.poll(async () => (await state(page, id)).tick).toBeGreaterThan(tick + 2);
  expect((await setSpeed(0)).ok()).toBeTruthy();
  await expect(metrics).toHaveAttribute('aria-pressed', 'true');
  await config.click();
  await expect(config).toHaveAttribute('aria-pressed', 'true');
  await expect(inspector.getByText('2', { exact: true })).toBeVisible();
  await closeInspector(page);
  await setMapView(page, 'list');
  await page.getByRole('button', { name: 'Primary database Database' }).click();
  await openInspector(page);
  await expect(inspector.getByRole('heading', { name: 'Primary database' })).toBeVisible();
  await expect(config).toHaveAttribute('aria-pressed', 'true');
});

test('monetization controls, revenue history and server time render in both languages', async ({ page }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  const id = await create(page, false, false);
  await navigate(page, 'Product');
  const ads = page.getByRole('article').filter({ has: page.getByText('Advertising', { exact: true }) });
  const premium = page.getByRole('article').filter({ has: page.getByText('Premium subscriptions', { exact: true }) });
  const open = (item: typeof ads) => item.getByRole('button').click();
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
  const market = page.getByRole('article', { name: 'Market expansion', exact: true }).getByRole('listitem')
    .filter({ has: page.getByRole('heading', { name: 'North America', exact: true }) });
  await market.getByRole('button', { name: 'Start preparation' }).click();
  const update = await page.request.put(`/api/games/${id}/clock`, { data: { request_id: crypto.randomUUID(), speed: 5 } });
  expect(update.ok()).toBeTruthy();
  await market.getByRole('button', { name: 'Launch market' }).click({ timeout: 20_000 });
  await pause(page);
  await navigate(page, 'Product');
  await page.getByRole('tab', { name: 'Product settings' }).click();
  await choose(page.getByRole('combobox', { name: 'Ad intensity', exact: true }), 'high');
  await page.getByLabel('Price per game month (USD)', { exact: true }).fill('5.50');
  await page.getByLabel('Offer faster synchronization').uncheck();
  await page.getByRole('button', { name: 'Save product settings' }).click();
  await expect.poll(async () => (await state(page, id)).product).toMatchObject({
    ad_intensity: 'high', premium_price: 5.5, premium_fast_sync: false,
  });
  if (visualDir) await page.getByRole('tab', { name: 'Product settings' }).scrollIntoViewIfNeeded();
  if (visualDir) await page.screenshot({ path: `${visualDir}/monetization-1440.png` });

  await fast(page);
  await expect.poll(async () => (await state(page, id)).economy.revenue_sources.advertising).toBeGreaterThan(0);
  await pause(page);
  await page.getByRole('tab', { name: 'Feature catalog' }).click();
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
  await choose(page.getByRole('combobox', { name: 'Revenue history', exact: true }), 'advertising');
  await expect(page.getByRole('figure', { name: /Revenue per simulation step/ })).toBeVisible();
  const final = await state(page, id);
  expect(final.economy.revenue_sources.advertising).toBeCloseTo(final.economy.revenue);
  expect(final.economy.daily_total_expenses).toBeCloseTo(final.economy.daily_operating + 1420);
  if (visualDir) await page.screenshot({ path: `${visualDir}/monetized-finance-1440.png`, fullPage: true });
  await navigate(page, 'Telemetry');
  const clock = final.snapshot.demand_overview!;
  const time = [Math.floor(clock.utc_minute / 60), clock.utc_minute % 60].map((value) => String(value).padStart(2, '0')).join(':');
  await expect(page.getByTestId('game-utc-time')).toHaveText(`Day ${clock.day} / ${time} UTC`);
  expect(final.day).toBe(clock.day);
  await expect(page.getByRole('article', { name: 'Demand by region', exact: true }).locator('summary').filter({ hasText: 'North America' })).toBeVisible();

  await page.goto('/?view=settings');
  await choose(page.getByRole('combobox', { name: 'Interface language', exact: true }), 'ru');
  await page.setViewportSize({ width: 390, height: 844 });
  for (const [section, heading] of [['finance', 'Структура выручки'], ['product', 'Настройки продукта'], ['monitor', 'Трафик по регионам']]) {
    await page.goto(`/game/${id}?view=${section}`);
    if (section === 'product') {
      await page.getByRole('tab', { name: heading, exact: true }).click();
      await expect(page.getByRole('combobox', { name: 'Интенсивность рекламы' })).toBeVisible();
    } else {
      await expect(page.getByRole('heading', { name: heading })).toBeVisible();
    }
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    if (visualDir) await page.screenshot({ path: `${visualDir}/monetized-${section}-ru-390.png`, fullPage: true });
  }
});

test('migration progress stays in the editor and a retiring database can be upgraded', async ({ page }) => {
  const originalId = await create(page, false, false);
  const portable = await (await page.request.get(`/api/games/${originalId}/export`)).json();
  portable.game.balance = 100_000;
  portable.game.storage.db = 1800;
  portable.game.production.nodes.find((node: { id: string }) => node.id === 'db').config.storage = 3000;
  const response = await page.request.post('/api/games/import', { data: portable });
  expect(response.ok(), await response.text()).toBeTruthy();
  const { id } = await response.json();
  const mutate = async (path: string, method: string, data: object) => {
    const response = await page.request.fetch(`/api/games/${id}${path}`, {
      method, data: { request_id: crypto.randomUUID(), ...data }
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    return await response.json() as Game;
  };
  const opened = await mutate('/draft', 'POST', { revision: (await state(page, id)).revision });
  const topology = opened.draft!;
  const primary = topology.nodes.find((node) => node.id === 'db')!;
  primary.id = 'new-db';
  primary.name = 'Replacement database';
  topology.edges.find((edge) => edge.target === 'db')!.target = primary.id;
  const edited = await mutate('/draft', 'PUT', { revision: opened.revision, topology });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/game/${id}?view=build`);
  await page.getByRole('button', { name: 'Review deployment' }).click();
  const review = page.getByRole('dialog', { name: 'Deployment review' });
  await expect(review).toContainText('1,800 GB');
  await review.getByRole('button', { name: 'Start migration' }).click();
  const status = page.getByRole('button', { name: /Migration · 0%/ });
  await expect(status).toBeVisible();
  expect((await state(page, id)).revision).toBeGreaterThan(edited.revision);
  await status.click();

  const panel = page.getByRole('dialog', { name: 'Architecture migration' });
  await expect(panel.getByRole('meter')).toBeVisible();
  await panel.getByRole('button', { name: 'Pause migration' }).click();
  await expect(panel).toContainText('Migration paused');
  await choose(panel.getByRole('combobox', { name: 'Component' }), 'db');
  await expect(panel).toContainText('Removed after migration');
  await panel.getByRole('spinbutton', { name: 'New capacity' }).fill('4000');
  await panel.getByRole('button', { name: 'Check upgrade cost' }).click();
  await panel.getByRole('button', { name: /Buy upgrade for/ }).click();
  await expect.poll(async () => (await state(page, id)).production.nodes.find((node) => node.id === 'db')?.config.storage).toBe(4000);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.keyboard.press('Escape');
  await expect(panel).not.toBeVisible();
  await page.getByRole('button', { name: 'Create draft' }).click();
  await expect.poll(async () => (await state(page, id)).draft?.nodes.some((node) => node.id === 'new-db')).toBeTruthy();
  await page.getByRole('button', { name: 'Review deployment' }).click();
  await expect(page.getByRole('button', { name: 'Deploy after migration' })).toBeDisabled();
});
