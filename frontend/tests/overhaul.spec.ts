import { expect, test, type Page } from '@playwright/test';
import russian from '../src/lib/ru.json';
import type { Game } from '../src/lib/types';
import { choose } from './forms';

const visualDir = process.env.VISUAL_OUTPUT_DIR;
const regions = [
  'north_america', 'south_america', 'east_asia', 'south_southeast_asia',
  'mena', 'sub_saharan_africa', 'oceania'
];

async function setup(page: Page, markets = regions) {
  const created = await page.request.post('/api/games', {
    data: { id: crypto.randomUUID(), name: 'Regional Messenger', seed: 7, settings: { show_tutorial: false } }
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const game: Game = await created.json();
  const exported = await page.request.get(`/api/games/${game.id}/export`);
  const save = await exported.json();
  save.game.launched_markets = markets;
  save.game.market_audience = Object.fromEntries(markets.filter((region) => region !== 'north_america').map((region, i) => [region, 4400 - 450 * i]));
  save.game.north_america_audience = markets.includes('north_america') ? 5900 : 0;
  save.game.audience = 41000;
  save.game.history[0].audience = 41000;
  const imported = await page.request.post('/api/games/import', { data: save });
  expect(imported.ok(), await imported.text()).toBeTruthy();
  return (await imported.json() as Game).id;
}

for (const [width, language] of [[390, 'ru'], [768, 'en'], [1440, 'ru'], [1920, 'en']] as const) {
  test(`Growth shows all eight markets at ${width}px in ${language}`, async ({ page, browserName }) => {
    const id = await setup(page);
    const tr = (value: keyof typeof russian) => language === 'ru' ? russian[value] : value;
    await page.addInitScript((value) => localStorage.setItem('workbench-language', value), language);
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    await page.goto(`/game/${id}?view=growth`);
    await expect(page.getByRole('heading', { name: tr('Regional traffic') })).toBeVisible();
    await expect(page.locator('.regions summary')).toHaveCount(8);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    const choice = page.getByRole('combobox', { name: tr('Sort regions') });
    await choose(choice, 'name');
    await page.locator('.regions summary').first().click();
    await expect(page.locator('.regions details[open]').getByText(tr('Local time'), { exact: true })).toBeVisible();
    const chart = page.getByRole('button', { name: new RegExp(tr('Expected daily demand')) });
    await chart.focus();
    await chart.press('Home');
    await expect(page.locator('.regional-demand').getByRole('tooltip')).toContainText('00:00');
    await chart.press('ArrowRight');
    await expect(page.locator('.regional-demand').getByRole('tooltip')).toContainText('01:00');
    await chart.press('Escape');
    if (browserName === 'chromium' && visualDir) {
      await page.evaluate(() => scrollTo(0, 0));
      await page.screenshot({ path: `${visualDir}/overhaul-growth-${width}-${language}.png`, fullPage: width === 1920 });
    }
  });
}

test('campaign planner searches eligible regions and spends one total budget', async ({ page, browserName }) => {
  await page.setViewportSize({ width: 1440, height: 1050 });
  const id = await setup(page, ['north_america', 'south_america']);
  await page.goto(`/game/${id}?view=growth`);
  await page.getByRole('button', { name: 'Plan campaign' }).last().click();
  const dialog = page.getByRole('dialog', { name: 'Campaign planning' });
  const choice = dialog.getByRole('combobox', { name: 'Target markets' });
  await choice.press('ArrowDown');
  const search = dialog.getByRole('searchbox');
  await search.fill('Oceania');
  await expect(dialog.getByRole('option', { name: /Oceania/ })).toBeDisabled();
  await search.fill('North America');
  await search.press('ArrowDown');
  await page.keyboard.press('Enter');
  await page.keyboard.press('Escape');
  await expect(choice).toContainText('2 selected');
  await dialog.getByRole('spinbutton', { name: 'Campaign budget', exact: true }).fill('1,500.02');
  await dialog.getByRole('spinbutton', { name: 'Duration (game hours)', exact: true }).fill('3');
  await expect(dialog.getByText('$750.01', { exact: false })).toHaveCount(2);
  await expect(dialog.getByText(/Expected peak traffic/)).toBeVisible();
  if (browserName === 'chromium' && visualDir) {
    await page.screenshot({ path: `${visualDir}/overhaul-campaign.png` });
  }
  const before: Game = await (await page.request.get(`/api/games/${id}`)).json();
  await dialog.getByRole('button', { name: 'Start campaign' }).click();
  await expect(dialog).toBeHidden();
  const after: Game = await (await page.request.get(`/api/games/${id}`)).json();
  expect(before.balance - after.balance).toBeCloseTo(1500.02);
  expect(before.economy.daily_profit).toBe(after.economy.daily_profit);
  expect(after.campaigns[0].regions).toEqual(['europe', 'north_america']);
  await page.goto(`/game/${id}?view=finance`);
  await page.getByText('Recent purchases', { exact: true }).click();
  await expect(page.getByText('Operating profit / day', { exact: true })).toBeVisible();
  if (browserName === 'chromium' && visualDir) {
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({ path: `${visualDir}/overhaul-finance.png`, fullPage: true });
  }
});

test('Russian configuration and deployment use localized controls, actual costs and synchronized sliders', async ({ page, browserName }) => {
  const id = await setup(page, []);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.addInitScript(() => localStorage.setItem('workbench-language', 'ru'));
  await page.goto(`/game/${id}?view=build&component=api`);
  await page.getByRole('button', { name: russian['Edit configuration'] }).click();
  const modal = page.getByRole('dialog', { name: russian['Component configuration'] });
  const cpu = modal.locator('#config-cpu');
  await cpu.fill('3,5');
  const slider = modal.getByRole('slider', { name: russian['Adjust {0}'].replace('{0}', russian['vCPU per instance']) });
  await expect(slider).toHaveValue('3.5');
  await slider.focus();
  await slider.press('ArrowUp');
  await expect(cpu).toHaveValue('5');
  await modal.getByRole('button', { name: russian['Preview cost and capacity'] }).click();
  await expect(modal.getByRole('heading', { name: russian['Capacity forecast'] })).toBeVisible();
  if (browserName === 'chromium' && visualDir) {
    await page.screenshot({ path: `${visualDir}/overhaul-configuration-ru.png` });
  }
  await modal.getByRole('button', { name: russian['Save to draft'] }).click();
  await page.getByRole('dialog', { name: russian['Component inspector'] }).getByRole('button', { name: russian['Close dialog'] }).click();
  await page.getByRole('button', { name: russian['Review deployment'] }).click();
  const review = page.getByRole('dialog', { name: russian['Deployment review'] });
  await review.getByRole('button', { name: russian['Deploy changes'] }).click();
  const results = page.getByRole('dialog', { name: russian['Deployment complete'] });
  for (const label of ['Successful requests', 'Average latency', 'Error rate', 'Daily infrastructure'] as const) {
    await expect(results.getByRole('rowheader', { name: russian[label], exact: true })).toBeVisible();
  }
  await expect(results).not.toContainText('Successful requests');
  if (browserName === 'chromium' && visualDir) {
    await page.screenshot({ path: `${visualDir}/overhaul-deployment-ru.png` });
  }
});

test.describe('compact campaign planning', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });

  test('touch selection opens a usable market list inside the planner', async ({ page }) => {
    const id = await setup(page, ['north_america']);
    await page.goto(`/game/${id}?view=growth`);
    await page.getByRole('button', { name: 'Plan campaign' }).last().tap();
    const dialog = page.getByRole('dialog', { name: 'Campaign planning' });
    const choice = dialog.getByRole('combobox', { name: 'Target markets' });
    await choice.tap();
    await page.getByRole('option', { name: 'North America', exact: true }).tap();
    await expect(choice).toContainText('2 selected');
    await dialog.getByRole('button', { name: 'Clear selection' }).tap();
    await expect(choice).toContainText('Select…');
    await dialog.getByRole('searchbox').press('Escape');
    await expect(dialog.getByText('Select at least one active market.')).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Start campaign' })).toBeDisabled();
  });
});
