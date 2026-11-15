import { expect, test, type Page } from '@playwright/test';
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
