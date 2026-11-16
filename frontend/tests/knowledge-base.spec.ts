import { expect, test, type Page } from '@playwright/test';
import type { Catalog, Game } from '../src/lib/types';

const screenshots = process.env.VISUAL_OUTPUT_DIR;

async function makeGame(page: Page) {
  const response = await page.request.post('/api/games', {
    data: { id: crypto.randomUUID(), name: 'Inspector Messenger', seed: 7, settings: { show_tutorial: false } }
  });
  expect(response.status()).toBe(201);
  return (await response.json()) as Game;
}

test('knowledge base covers the catalog, searches content and resolves stable article links', async ({ page }) => {
  const response = await page.request.get('/api/games/catalog');
  expect(response.ok()).toBeTruthy();
  const { components } = (await response.json()) as Catalog;
  await page.goto('/?view=guide');
  const directory = page.getByRole('heading', { name: 'Browse articles' }).locator('..');
  await expect(directory.getByRole('heading', { level: 3 })).toHaveCount(5);
  for (const kind of Object.keys(components)) {
    await expect(directory.locator(`a[href$="&article=${kind}"]`)).toHaveCount(1);
  }
  for (const article of ['deployment', 'monitoring-charts', 'product-features', 'campaigns', 'availability', 'finances', 'save-files']) {
    await expect(directory.locator(`a[href$="&article=${article}"]`)).toHaveCount(1);
  }

  const query = page.getByRole('searchbox', { name: 'Search the Guide' });
  await query.fill('LFU');
  const results = page.getByRole('region', { name: 'Search articles' });
  await expect(results.getByRole('link', { name: 'Cache Infrastructure components' })).toBeVisible();
  await query.fill('xyz-no-results');
  await expect(results.getByRole('status')).toHaveText('No matching articles.');
  await query.fill('disk i/o');
  await results.getByRole('link', { name: 'Database disk I/O System architecture' }).click();
  await expect(page.getByRole('heading', { name: 'Database disk I/O', exact: true })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Guide breadcrumbs' })).toContainText('System architecture');
  await page.getByRole('navigation', { name: 'On this page' }).getByRole('link', { name: 'Storage types and space' }).click();
  await expect(page).toHaveURL(/article=database-io#space$/);
  await page.reload();
  await expect(page.locator('#space')).toBeInViewport();
  await expect(page.getByRole('link', { name: 'Database scaling', exact: true }).last()).toBeVisible();
});

test('desktop inspector resizes without moving draft nodes and restores the local preference', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const game = await makeGame(page);
  const url = `/game/${game.id}?view=build`;
  await page.goto(url);
  await page.getByRole('button', { name: 'Create draft' }).click();
  await expect(page.getByRole('button', { name: 'Review deployment' })).toBeVisible();
  const open = page.getByRole('button', { name: 'Open component' });
  await open.click();
  const inspector = page.getByRole('dialog', { name: 'Component inspector' });
  const handle = page.getByRole('separator', { name: 'Resize component inspector' });
  const canvas = page.locator('[data-tutorial="topology.canvas"]');
  const width = () => inspector.evaluate((node) => node.getBoundingClientRect().width);
  const canvasWidth = () => canvas.evaluate((node) => node.getBoundingClientRect().width);
  const node = page.locator('.svelte-flow__node[data-id="api"]');
  await expect(node).toBeVisible();
  const position = await node.evaluate((item) => (item as HTMLElement).style.transform);
  const before = await width();
  const originalCanvas = await canvasWidth();
  await inspector.getByRole('button', { name: 'Metrics', exact: true }).click();
  const divider = (await handle.boundingBox())!;
  const x = divider.x + divider.width / 2;
  const y = divider.y + divider.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x - 115, y, { steps: 7 });
  await expect.poll(width).toBe(before + 115);
  await page.mouse.up();
  expect(await canvasWidth()).toBe(originalCanvas);
  expect(await node.evaluate((item) => (item as HTMLElement).style.transform)).toBe(position);
  await expect(inspector.getByRole('button', { name: 'Metrics', exact: true })).toHaveAttribute('aria-pressed', 'true');

  await page.reload();
  await open.click();
  await expect.poll(width).toBe(before + 115);
  await handle.focus();
  await handle.press('End');
  await expect.poll(width).toBe(Number(await handle.getAttribute('aria-valuemax')));
  await handle.press('Home');
  await expect.poll(width).toBe(Number(await handle.getAttribute('aria-valuemin')));
  await handle.press('ArrowLeft');
  await expect.poll(width).toBe(Number(await handle.getAttribute('aria-valuemin')) + 16);
  await inspector.getByRole('button', { name: 'Reset width' }).click();
  await expect.poll(width).toBe(before);
  await inspector.getByRole('button', { name: 'Configuration', exact: true }).click();
  await inspector.getByRole('button', { name: 'Edit configuration' }).click();
  const config = page.getByRole('dialog', { name: 'Component configuration' });
  await config.getByLabel('Component name').fill('Unsaved Messenger API');
  const help = config.getByRole('link', { name: 'Help with vCPU per instance' });
  const popupEvent = page.waitForEvent('popup');
  await help.click();
  const popup = await popupEvent;
  await expect(popup).toHaveURL(/article=api#configuration$/);
  await expect(config.getByLabel('Component name')).toHaveValue('Unsaved Messenger API');
  await popup.close();
  await config.getByRole('button', { name: 'Cancel' }).click();
  const current = (await (await page.request.get(`/api/games/${game.id}`)).json()) as Game;
  expect(current.production).toEqual(game.production);
  expect(current.deployments).toEqual(game.deployments);
  expect(current.diagram.positions).toEqual(game.diagram.positions);
  await inspector.getByRole('link', { name: 'Component guide' }).click();
  await expect(page).toHaveURL(/article=api$/);
});

for (const language of ['en', 'ru'] as const) {
  for (const mobile of [false, true]) {
    const ru = language === 'ru';
    test(`guide and inspector layout in ${language} at ${mobile ? 'mobile' : 'desktop'} width`, async ({ page, browserName }) => {
      await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 });
      const game = await makeGame(page);
      await page.addInitScript((value) => localStorage.setItem('workbench-language', value), language);
      const base = `/game/${game.id}`;
      await page.goto(`${base}?view=guide&article=replication`);
      const article = page.getByRole('heading', { name: ru ? 'Репликация' : 'Replication', exact: true });
      await expect(article).toBeInViewport();
      if (mobile) {
        const categories = page.getByRole('button', { name: ru ? 'Разделы' : 'Categories' });
        const navigation = page.getByRole('navigation', { name: ru ? 'Навигация по справке' : 'Guide navigation' });
        await expect(navigation).toBeHidden();
        await categories.click();
        await expect(navigation).toBeVisible();
        await page.getByRole('dialog').getByRole('button', { name: ru ? 'Закрыть окно' : 'Close dialog' }).click();
      }
      const fit = () => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
      expect(await fit()).toBe(true);
      if (screenshots) await page.screenshot({ path: `${screenshots}/${browserName}-guide-${language}-${mobile ? 'mobile' : 'desktop'}.png` });
      const query = page.getByRole('searchbox', { name: ru ? 'Поиск по справке' : 'Search the Guide' });
      await query.fill(ru ? 'Поисковый индекс' : 'search index');
      const results = page.getByRole('region', { name: ru ? 'Поиск статей' : 'Search articles' });
      await expect(results.locator('a[href$="article=database"]')).toBeVisible();
      await page.goto(`${base}?view=build&component=db`);
      const inspectorName = ru ? 'Сведения о компоненте' : 'Component inspector';
      const inspector = page.getByRole('dialog', { name: inspectorName });
      await expect(inspector).toBeVisible();
      if (mobile) {
        await expect(inspector.getByRole('separator')).toBeHidden();
        await expect(inspector).toHaveCSS('width', '390px');
      }
      await expect(inspector.getByRole('link', { name: ru ? 'Справка о компоненте' : 'Component guide' })).toBeVisible();
      await inspector.getByRole('button', { name: ru ? 'Метрики' : 'Metrics', exact: true }).click();
      expect(await fit()).toBe(true);
      if (screenshots) await page.screenshot({ path: `${screenshots}/${browserName}-inspector-${language}-${mobile ? 'mobile' : 'desktop'}.png` });
    });
  }
}
