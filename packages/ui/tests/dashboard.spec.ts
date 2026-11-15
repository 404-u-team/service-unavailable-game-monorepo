import { expect, test, type Page } from '@playwright/test';
import { parseDashboardState, resolveDashboard, type DashboardState, type DashboardWidgetDefinition } from '../src/dashboard';

const url = '/iframe.html?id=patterns-dashboard--editable-dashboard&viewMode=story';
const storageKey = 'sui-storybook-infrastructure-dashboard';

async function saved(page: Page) {
  return parseDashboardState(await page.evaluate((key) => localStorage.getItem(key), storageKey));
}

function widget(state: DashboardState | null, id: string) {
  return state?.widgets.find((item) => item.id === id);
}

function expectNoOverlap(state: DashboardState) {
  const visible = state.widgets.filter((item) => item.visible);
  visible.forEach(({ placement: a }, index) => {
    for (const { placement: b } of visible.slice(index + 1)) {
      expect(a.x + a.width <= b.x || b.x + b.width <= a.x
        || a.y + a.height <= b.y || b.y + b.height <= a.y).toBe(true);
    }
  });
}

test('snapshot decoder validates schemas and restores known widgets ahead of new defaults', () => {
  expect(parseDashboardState('{"version":2,"widgets":[]}')).toBeNull();
  expect(parseDashboardState('{"version":1,"widgets":[{},{}]}')).toBeNull();
  const content = (() => {}) as unknown as DashboardWidgetDefinition['content'];
  const definitions: DashboardWidgetDefinition[] = [
    { id: 'new', title: 'New', placement: { x: 0, y: 0 }, content },
    { id: 'kept', title: 'Kept', minWidth: 3, defaultSettings: { showHistory: true }, content }
  ];
  const incoming = {
    version: 1 as const,
    mobileOrder: ['removed', 'kept'],
    widgets: [
      { id: 'kept', visible: true, placement: { x: 1, y: 0, width: 1, height: 2 }, settings: { threshold: 15 } },
      { id: 'removed', visible: false, placement: { x: 0, y: 0, width: 2, height: 2 }, settings: {} }
    ]
  };
  expect(parseDashboardState({ ...incoming, widgets: [...incoming.widgets, incoming.widgets[0]] })).toBeNull();
  const restored = resolveDashboard(definitions, 12, parseDashboardState(JSON.stringify(incoming)));
  expect(widget(restored, 'kept')).toMatchObject({
    placement: { x: 1, y: 0, width: 3, height: 2 }, settings: { showHistory: true, threshold: 15 }
  });
  expect(widget(restored, 'new')?.placement.y).toBe(2);
  expect(widget(restored, 'removed')).toBeUndefined();
  expect(restored.mobileOrder).toEqual(['kept', 'new']);
  expectNoOverlap(restored);
});

test('drag previews without saving, drops once, and pushes colliding widgets down', async ({ page }) => {
  await page.addInitScript((key) => {
    let writes = 0;
    const save = Storage.prototype.setItem;
    Storage.prototype.setItem = function (name, value) {
      if (this === localStorage && name === key) writes++;
      save.call(this, name, value);
    };
    Object.defineProperty(window, 'dashboardWrites', { get: () => writes });
  }, storageKey);
  await page.goto(url);
  await page.getByRole('button', { name: 'Edit layout' }).click();
  const traffic = page.locator('[data-widget=traffic]');
  const handle = traffic.getByRole('button', { name: 'Move Incoming traffic' });
  const start = (await handle.boundingBox())!;
  const neighbor = (await page.locator('[data-widget=availability]').boundingBox())!;
  const source = (await traffic.boundingBox())!;
  const x = start.x + start.width / 2;
  const y = start.y + start.height / 2;
  const distance = neighbor.x - source.x;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + distance, y, { steps: 5 });
  await expect(traffic).toHaveCSS('grid-column-start', '5');
  expect(await saved(page)).toBeNull();
  await page.keyboard.press('Escape');
  await page.mouse.up();
  await expect(traffic).toHaveCSS('grid-column-start', '1');
  expect(await saved(page)).toBeNull();

  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + distance, y, { steps: 5 });
  await page.mouse.up();
  await expect.poll(async () => widget(await saved(page), 'traffic')?.placement.x).toBe(4);
  expect(await page.evaluate(() => Reflect.get(window, 'dashboardWrites'))).toBe(1);
  const snapshot = (await saved(page))!;
  expect(widget(snapshot, 'availability')?.placement.y).toBeGreaterThan(0);
  expectNoOverlap(snapshot);

  await page.reload();
  await expect(traffic).toHaveCSS('grid-column-start', '5');
  await expect(page.getByRole('button', { name: 'Edit layout' })).toBeVisible();
});

test('a drag near the viewport edge scrolls the board and can be canceled', async ({ page }) => {
  await page.setViewportSize({ width: 1000, height: 460 });
  await page.goto(url);
  await page.getByRole('button', { name: 'Edit layout' }).click();
  const handle = page.getByRole('button', { name: 'Move Incoming traffic' });
  await expect(handle).toBeVisible();
  const start = (await handle.boundingBox())!;
  const x = start.x + start.width / 2;
  await page.mouse.move(x, start.y + start.height / 2);
  await page.mouse.down();
  await page.mouse.move(x, 450, { steps: 6 });
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(20);
  await page.keyboard.press('Escape');
  await page.mouse.up();
  expect(await saved(page)).toBeNull();
});

test('resize handles and widget settings write a single dashboard snapshot', async ({ page }) => {
  await page.goto(url);
  await page.getByRole('button', { name: 'Edit layout' }).click();
  const traffic = page.locator('[data-widget=traffic]');
  const handle = traffic.getByRole('button', { name: 'Resize Incoming traffic' });
  const start = (await handle.boundingBox())!;
  const oneRow = 68;
  await page.mouse.move(start.x + start.width / 2, start.y + start.height / 2);
  await page.mouse.down();
  await page.mouse.move(start.x + start.width / 2, start.y + start.height / 2 + oneRow, { steps: 4 });
  await expect(traffic).toHaveCSS('grid-row-end', 'span 3');
  expect(await saved(page)).toBeNull();
  await page.mouse.up();
  await expect.poll(async () => widget(await saved(page), 'traffic')?.placement.height).toBe(3);
  await handle.press('ArrowRight');
  await expect.poll(async () => widget(await saved(page), 'traffic')?.placement.width).toBe(5);

  await page.getByRole('button', { name: 'Configure Request history' }).click();
  const settings = page.getByRole('dialog', { name: 'Configure Request history' });
  await settings.getByRole('switch', { name: 'Compare with provisioned capacity' }).click();
  expect(widget(await saved(page), 'history')?.settings).toEqual({ compareCapacity: true });
  await settings.getByRole('spinbutton', { name: 'Width in columns' }).fill('9');
  await settings.getByRole('button', { name: 'Save settings' }).click();
  await expect(settings).toBeHidden();
  const snapshot = (await saved(page))!;
  expect(widget(snapshot, 'history')?.placement.width).toBe(9);
  expect(widget(snapshot, 'history')?.settings).toEqual({ compareCapacity: false });
  expectNoOverlap(snapshot);
  await expect(page.locator('[data-widget=history]').getByText('Capacity', { exact: true })).toBeHidden();
});

test('visibility, export, and hot import operate on the whole dashboard', async ({ page }) => {
  await page.goto(url);
  await page.getByRole('button', { name: 'Edit layout' }).click();
  await page.getByRole('button', { name: 'Widgets', exact: true }).click();
  const catalog = page.getByRole('dialog', { name: 'Widgets' });
  await catalog.getByRole('checkbox', { name: 'Availability' }).uncheck();
  await catalog.getByRole('checkbox', { name: 'Daily cash flow' }).check();
  await catalog.getByRole('button', { name: 'Done', exact: true }).click();
  await expect(page.getByRole('article', { name: 'Availability' })).toBeHidden();
  await expect(page.getByRole('article', { name: 'Daily cash flow' })).toBeVisible();

  await page.getByText('Dashboard snapshot', { exact: true }).click();
  await page.getByRole('button', { name: 'Export JSON' }).click();
  const json = page.getByRole('textbox', { name: 'Dashboard JSON' });
  const exported = parseDashboardState(await json.inputValue())!;
  expect(widget(exported, 'availability')?.visible).toBe(false);
  expect(widget(exported, 'cash')?.visible).toBe(true);

  await json.fill('{"version":3,"widgets":[]}');
  await page.getByRole('button', { name: 'Import JSON' }).click();
  await expect(page.getByRole('alert')).toContainText('unsupported version');
  await expect(page.getByRole('article', { name: 'Daily cash flow' })).toBeVisible();
  widget(exported, 'availability')!.visible = true;
  widget(exported, 'cash')!.visible = false;
  await json.fill(JSON.stringify(exported));
  await page.getByRole('button', { name: 'Import JSON' }).click();
  await expect(page.getByRole('article', { name: 'Availability' })).toBeVisible();
  await expect(page.getByRole('article', { name: 'Daily cash flow' })).toBeHidden();

  await page.getByRole('button', { name: 'Widgets', exact: true }).click();
  await catalog.getByRole('checkbox', { name: 'Availability' }).uncheck();
  await catalog.getByRole('button', { name: 'Reset dashboard' }).click();
  await expect(catalog.getByRole('checkbox', { name: 'Availability' })).toBeChecked();
  expect(widget(await saved(page), 'availability')?.visible).toBe(true);
});

test('the narrow list reorders using the keyboard and keeps desktop placement', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto(url);
  await page.getByRole('button', { name: 'Edit layout' }).click();
  const move = page.getByRole('button', { name: 'Move Incoming traffic' });
  await move.press('ArrowDown');
  await expect(move).toBeFocused();
  await expect.poll(async () => (await saved(page))?.mobileOrder?.slice(0, 2)).toEqual(['availability', 'traffic']);
  expect(widget(await saved(page), 'traffic')?.placement.x).toBe(0);
  await expect(page.locator('[data-widget=traffic]')).toHaveCSS('grid-row-start', '2');
  await expect(page.getByRole('button', { name: 'Resize Incoming traffic' })).toBeHidden();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(360);
});

test('touch can drag a widget in the narrow list', async ({ browser, browserName, baseURL }) => {
  test.skip(browserName !== 'chromium', 'Uses Chromium touch events.');
  const context = await browser.newContext({ baseURL, viewport: { width: 360, height: 780 }, hasTouch: true, isMobile: true });
  try {
    const page = await context.newPage();
    await page.goto(url);
    await page.getByRole('button', { name: 'Edit layout' }).tap();
    const handle = page.getByRole('button', { name: 'Move Incoming traffic' });
    await expect(handle).toBeVisible();
    const box = (await handle.boundingBox())!;
    const next = (await page.locator('[data-widget=availability]').boundingBox())!;
    const client = await context.newCDPSession(page);
    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;
    await client.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    await client.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: next.y + next.height - 3 }] });
    await client.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await expect.poll(async () => (await saved(page))?.mobileOrder?.slice(0, 2)).toEqual(['availability', 'traffic']);
  } finally {
    await context.close();
  }
});
