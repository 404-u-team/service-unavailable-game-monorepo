import { expect, test, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import type { Game } from '../src/lib/types';

async function makeGame(page: Page) {
  const response = await page.request.post('/api/games', {
    data: { id: crypto.randomUUID(), name: 'Dashboard verification', seed: 7, settings: { show_tutorial: false } }
  });
  expect(response.status()).toBe(201);
  return (await response.json()).id as string;
}

for (const [view, heading, widget] of [
  ['monitor', 'System telemetry', 'Requests / sec'],
  ['growth', 'Audience & campaigns', 'Growth readiness'],
  ['finance', 'Finance', 'Cash flow']
] as const) {
  test(`${heading} saves dashboard changes per game and restores defaults`, async ({ page }) => {
    const id = await makeGame(page);
    const url = `/game/${id}?view=${view}`;
    await page.goto(url);
    const board = page.getByRole('region', { name: heading, exact: true });
    const tile = board.getByRole('article', { name: widget, exact: true });
    await expect(tile).toBeVisible();
    await board.getByRole('button', { name: 'Edit layout' }).click();
    const move = board.getByRole('button', { name: `Move ${widget}`, exact: true });
    const cell = tile.locator('..');
    const before = await cell.evaluate((element) => element.style.gridRow);
    await move.press('ArrowDown');
    await expect.poll(() => cell.evaluate((element) => element.style.gridRow)).not.toBe(before);
    await board.getByRole('button', { name: 'Widgets', exact: true }).click();
    const catalog = page.getByRole('dialog', { name: 'Widgets' });
    await catalog.getByRole('checkbox', { name: widget, exact: true }).uncheck();
    await catalog.getByRole('button', { name: 'Done', exact: true }).click();
    await expect(tile).toHaveCount(0);
    await page.reload();
    await expect(board).toBeVisible();
    await expect(tile).toHaveCount(0);

    const other = await makeGame(page);
    await page.goto(`/game/${other}?view=${view}`);
    await expect(tile).toBeVisible();
    await page.goto(url);
    await board.getByRole('button', { name: 'Edit layout' }).click();
    await board.getByRole('button', { name: 'Widgets', exact: true }).click();
    await catalog.getByRole('button', { name: 'Reset dashboard' }).click();
    await catalog.getByRole('button', { name: 'Done', exact: true }).click();
    await expect(tile).toBeVisible();
    await expect.poll(() => cell.evaluate((element) => element.style.gridRow)).toBe(before);
  });
}

test('incident pages retain filtering, older event deep links and acknowledgement', async ({ page }) => {
  const id = await makeGame(page);
  const initial: Game = await (await page.request.get(`/api/games/${id}`)).json();
  for (let index = 0; index < 24; index++) {
    const response = await page.request.put(`/api/games/${id}/product`, { data: {
      request_id: crypto.randomUUID(),
      product: { ...initial.product, sync_frequency: index % 2 ? 'standard' : 'frequent' }
    } });
    expect(response.ok(), await response.text()).toBeTruthy();
  }
  const drilled = await page.request.post(`/api/games/${id}/incidents/drill`, { data: { request_id: crypto.randomUUID() } });
  expect(drilled.ok(), await drilled.text()).toBeTruthy();
  const state: Game = await drilled.json();
  const older = state.incidents.at(-1)!;
  const url = `/game/${id}?view=events`;
  await page.goto(url);

  const events = page.getByRole('main').getByRole('button', { name: /Product settings updated|Instance failure drill/ });
  const pages = page.getByRole('navigation', { name: 'Incident pages' });
  await expect(events).toHaveCount(10);
  await expect(pages).toContainText('Page 1 of 3');
  await pages.getByRole('button', { name: 'Next page' }).click();
  await expect(pages).toContainText('Page 2 of 3');
  const filters = page.getByRole('group', { name: 'Filter events' });
  await filters.getByRole('button', { name: 'Active', exact: true }).click();
  await expect(events).toHaveCount(1);
  await expect(pages).toBeHidden();
  await filters.getByRole('button', { name: 'Closed', exact: true }).click();
  await expect(pages).toContainText('Page 1 of 3');

  await page.goto(url + '&event=' + encodeURIComponent(older.id));
  const incident = page.getByRole('dialog', { name: 'Incident details' });
  await expect(incident).toContainText(older.id);
  await expect(incident).toHaveAttribute('data-side', 'end');
  await incident.getByRole('button', { name: 'Acknowledge' }).click();
  await expect(incident.getByText('Acknowledged', { exact: true })).toBeVisible();
});

test('topology drawers preserve keyboard access and save feedback stays below navigation', async ({ page }) => {
  const id = await makeGame(page);
  await page.goto(`/game/${id}?view=build`);
  const open = page.getByRole('button', { name: 'Open component' });
  await open.press('Enter');
  const inspector = page.getByRole('dialog', { name: 'Component inspector' });
  await expect(inspector).toHaveAttribute('data-side', 'end');
  await page.keyboard.press('Escape');
  await expect(inspector).toBeHidden();
  await expect(open).toBeFocused();
  await page.getByRole('button', { name: 'Add node' }).click();
  const library = page.getByRole('dialog', { name: 'Component library' });
  await expect(library).toHaveAttribute('data-side', 'start');
  await library.getByRole('searchbox', { name: 'Search components' }).fill('Monitoring');
  await expect(library.getByRole('button', { name: 'Monitoring', exact: true })).toBeVisible();
  await page.keyboard.press('Escape');

  await page.getByRole('button', { name: 'Save game' }).click();
  const notifications = page.getByRole('region', { name: 'Notifications' });
  await expect(notifications.getByText('Game saved', { exact: true })).toBeVisible();
  const header = (await page.locator('.topbar').boundingBox())!;
  const toast = (await notifications.boundingBox())!;
  expect(toast.y).toBeGreaterThanOrEqual(header.y + header.height);
  expect(toast.x).toBeGreaterThan(header.width / 2);
});

test('topology opens node details on a double-click, with real motion in both directions', async ({ page }) => {
  const id = await makeGame(page);
  await page.goto(`/game/${id}?view=build`);
  await page.addStyleTag({ content: 'html:root { --sui-motion: 650ms; }' });
  const panel = page.locator('.sui-overlay');
  const translation = () => panel.evaluate((element) => new DOMMatrixReadOnly(getComputedStyle(element).transform === 'none'
    ? undefined : getComputedStyle(element).transform).m41);

  await page.getByRole('button', { name: 'Add node' }).click();
  await expect(panel).toHaveAttribute('data-side', 'start');
  await expect.poll(translation).toBeLessThan(-5);
  await panel.getByRole('button', { name: 'Close dialog' }).click();
  await expect(panel).toHaveAttribute('data-state', 'closed');
  await expect.poll(translation).toBeLessThan(-5);
  await expect(panel).toHaveCount(0);

  const node = page.locator('.svelte-flow__node[data-id="api"]').getByText('Messenger API', { exact: true });
  await node.click();
  await expect(panel).toHaveCount(0);
  await node.dblclick();
  await expect(panel).toHaveAttribute('data-side', 'end');
  await expect.poll(translation).toBeGreaterThan(5);
  await expect(panel.getByRole('heading', { name: 'Messenger API', exact: true })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(panel).toHaveAttribute('data-state', 'closed');
  await expect.poll(translation).toBeGreaterThan(5);
  await expect(panel).toHaveCount(0);

  await page.getByRole('button', { name: 'Map settings', exact: true }).click();
  await page.getByRole('dialog', { name: 'Map settings' }).getByRole('button', { name: 'Show component list' }).click();
  await page.getByRole('button', { name: 'Messenger API API server', exact: true }).dblclick();
  const inspector = page.getByRole('dialog', { name: 'Component inspector' });
  await expect(inspector).toBeVisible();
  await inspector.getByRole('link', { name: 'Component guide' }).click();
  await expect(panel).toHaveAttribute('data-state', 'closed');
  await expect(page).toHaveURL(/view=guide/);
});

test('Russian rail labels wrap between words and fit inside the rail', async ({ page }) => {
  const id = await makeGame(page);
  await page.addInitScript(() => localStorage.setItem('workbench-language', 'ru'));
  await page.setViewportSize({ width: 970, height: 610 });
  await page.goto(`/game/${id}?view=build`);
  const rail = page.getByRole('navigation', { name: 'Навигация рабочей области' });
  for (const text of ['Мониторинг', 'Сохранённые игры']) {
    const label = rail.getByRole('link', { name: text, exact: true }).getByText(text, { exact: true });
    await expect(label).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    expect(await label.evaluate((element) => {
      const link = element.closest('a')!.getBoundingClientRect();
      const text = element.firstChild!;
      const range = new Range();
      return [...(text.textContent ?? '').matchAll(/\S+/g)].every((word) => {
        range.setStart(text, word.index!);
        range.setEnd(text, word.index! + word[0].length);
        const rect = range.getBoundingClientRect();
        return range.getClientRects().length === 1 && rect.left >= link.left && rect.right <= link.right;
      });
    })).toBeTruthy();
  }
});

test('growth project rows pack independently and wheel scrolling continues on the dashboard', async ({ page }) => {
  const id = await makeGame(page);
  await page.goto(`/game/${id}?view=growth`);
  const market = page.getByRole('article', { name: 'Market expansion' });
  const languages = page.getByRole('article', { name: 'Messenger languages' });
  for (const widget of [market, languages]) {
    const first = widget.getByRole('listitem').first();
    const second = widget.getByRole('listitem').nth(1);
    await expect(second).toBeAttached();
    const a = (await first.boundingBox())!;
    const b = (await second.boundingBox())!;
    expect(b.x).toBe(a.x);
    expect(b.y - (a.y + a.height)).toBeLessThan(16);
  }
  const rows = market.getByRole('listitem');
  const firstDisclosure = rows.first().locator('summary');
  const before = (await rows.nth(1).boundingBox())!.y - (await rows.first().boundingBox())!.y;
  await firstDisclosure.click();
  await expect.poll(async () => (await rows.nth(1).boundingBox())!.y - (await rows.first().boundingBox())!.y).toBeGreaterThan(before);
  await firstDisclosure.click();

  const body = market.locator('.body').first();
  await body.scrollIntoViewIfNeeded();
  await expect.poll(() => body.evaluate((node) => node.scrollHeight - node.clientHeight)).toBeGreaterThan(80);
  const box = (await body.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, 80);
  await expect.poll(() => body.evaluate((node) => node.scrollTop)).toBeGreaterThan(0);
  await body.evaluate((node) => { node.scrollTop = node.scrollHeight; });
  const beforeWheel = await page.evaluate(() => scrollY);
  await expect.poll(async () => {
    await page.mouse.wheel(0, 280);
    return page.evaluate(() => scrollY);
  }, { intervals: [350, 450, 600] }).toBeGreaterThan(beforeWheel);
});

test('dashboard layouts can be saved, exported, set as default and imported into a different save', async ({ page, browser }) => {
  test.slow();
  const source = await makeGame(page);
  const target = await makeGame(page);
  const variants = [
    ['monitor', 'Requests / sec'],
    ['growth', 'Growth readiness'],
    ['finance', 'Cash flow']
  ] as const;
  const url = (id: string, view: string) => `/game/${id}?view=${view}`;
  const widget = (name: string) => page.getByRole('article', { name, exact: true });
  const notification = (text: string, tab = page) => tab.getByRole('region', { name: 'Notifications' }).getByText(text, { exact: true });

  for (const [view, name] of variants) {
    await page.goto(url(source, view));
    await expect(widget(name)).toBeVisible();
    await page.getByRole('button', { name: 'Edit layout' }).click();
    await page.getByRole('button', { name: 'Widgets', exact: true }).click();
    const drawer = page.getByRole('dialog', { name: 'Widgets' });
    await drawer.getByRole('checkbox', { name, exact: true }).uncheck();
    await drawer.getByRole('button', { name: 'Done', exact: true }).click();
    await expect(widget(name)).toHaveCount(0);
  }

  await page.goto(url(source, 'settings'));
  await page.getByRole('tab', { name: 'Dashboard layouts' }).click();
  await page.getByLabel('Layout name').fill('Operations desk');
  await page.getByRole('button', { name: 'Save layout', exact: true }).click();
  await expect(notification('Dashboard layout saved.')).toBeVisible();
  const current = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export current layout' }).click();
  const currentFile = JSON.parse(await readFile(await (await current).path(), 'utf8'));

  await page.goto('/?view=settings');
  await page.getByRole('button', { name: 'Set Operations desk as default for new games' }).click();
  await expect(page.getByText('Default for new games', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Actions for Operations desk' }).click();
  const exported = page.waitForEvent('download');
  await page.getByRole('menuitem', { name: 'Export layout' }).click();
  const file = await (await exported).path();
  const exportedFile = JSON.parse(await readFile(file, 'utf8'));
  expect(exportedFile.name).toBe('Operations desk');
  expect(exportedFile.layout).toEqual(currentFile.layout);
  expect(Object.keys(exportedFile.layout).sort()).toEqual(['finance', 'growth', 'monitor']);

  await page.goto(url(target, 'monitor'));
  await expect(widget('Requests / sec')).toBeVisible();
  await page.goto('/?view=new');
  await page.getByRole('button', { name: 'Create game', exact: true }).click();
  await expect(page).toHaveURL(/\/game\/[^/?]+\?view=build/);
  const fresh = new URL(page.url()).pathname.split('/').at(-1)!;
  for (const [view, name] of variants) {
    await page.goto(url(fresh, view));
    await expect(page.getByRole('button', { name: 'Edit layout' })).toBeVisible();
    await expect(widget(name)).toHaveCount(0);
  }

  await page.goto(url(target, 'settings'));
  await page.getByRole('tab', { name: 'Dashboard layouts' }).click();
  const input = page.getByLabel('Import layout into current game');
  await input.setInputFiles({ name: 'game.json', mimeType: 'application/json', buffer: Buffer.from('{"game":{}}') });
  await expect(notification('Choose a valid dashboard layout JSON file.')).toBeVisible();
  await input.setInputFiles(file);
  await expect(notification('Layout applied to this game.')).toBeVisible();
  for (const [view, name] of variants) {
    await page.goto(url(target, view));
    await expect(page.getByRole('button', { name: 'Edit layout' })).toBeVisible();
    await expect(widget(name)).toHaveCount(0);
  }

  await page.goto('/?view=settings');
  await page.getByRole('button', { name: 'Use built-in default' }).click();
  await expect(page.getByText('New games use the built-in layout.', { exact: true })).toBeVisible();
  const separate = await browser.newContext({ baseURL: new URL(page.url()).origin });
  try {
    const otherBrowser = await separate.newPage();
    await otherBrowser.goto('/?view=settings');
    const presetFile = otherBrowser.getByLabel('Import layout preset');
    await expect(presetFile).toBeEnabled();
    await presetFile.setInputFiles(file);
    await expect(notification('Dashboard layout imported.', otherBrowser)).toBeVisible();
    await expect(otherBrowser.getByRole('button', { name: 'Set Operations desk as default for new games' })).toBeVisible();
  } finally { await separate.close(); }
});
