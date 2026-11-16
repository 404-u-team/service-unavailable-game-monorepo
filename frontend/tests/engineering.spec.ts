import { expect, test, type Page } from '@playwright/test';
import russian from '../src/lib/ru.json';
import { choose } from './forms';

async function preparedGame(page: Page, completed: boolean) {
  const response = await page.request.post('/api/games', {
    data: { id: crypto.randomUUID(), name: 'Engineering Messenger', seed: 7, settings: { show_tutorial: false } }
  });
  expect(response.status()).toBe(201);
  const game = await response.json();
  if (!completed) return game;
  const save = await (await page.request.get(`/api/games/${game.id}/export`)).json();
  save.game.engineering = { decomposition: 0, domains: 0, queries: 0, sharding: 0, autoscaling: 0 };
  const imported = await page.request.post('/api/games/import', { data: save });
  expect(imported.ok(), await imported.text()).toBeTruthy();
  const summary = await imported.json();
  return (await page.request.get(`/api/games/${summary.id}`)).json();
}

for (const width of [390, 768, 1440, 1920]) for (const language of ['en', 'ru'] as const) {
  test(`Engineering research, configuration and Guide at ${width}px ${language}`, async ({ page }, info) => {
    const tr = (value: string) => language === 'ru' ? (russian as Record<string, string>)[value] ?? value : value;
    await page.addInitScript((value) => localStorage.setItem('workbench-language', value), language);
    await page.setViewportSize({ width, height: 1000 });
    const game = await preparedGame(page, true);
    await page.goto(`/game/${game.id}?view=product`);
    await page.getByRole('tab', { name: tr('Engineering'), exact: true }).click();
    const engineering = page.getByRole('region', { name: tr('Engineering'), exact: true });
    await expect(engineering.getByRole('heading', { name: tr('Service Decomposition'), exact: true })).toBeVisible();
    await expect(engineering.getByText(tr('Completed'), { exact: true })).toHaveCount(5);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    if (process.env.VISUAL_OUTPUT_DIR) await page.screenshot({ path: `${process.env.VISUAL_OUTPUT_DIR}/engineering-${width}-${language}-${info.project.name || 'browser'}.png`, fullPage: true });

    const draft = await page.request.post(`/api/games/${game.id}/draft`, { data: { request_id: crypto.randomUUID(), revision: game.revision } });
    expect(draft.ok()).toBeTruthy();
    await page.goto(`/game/${game.id}?view=build&component=api&configure=1`);
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('combobox', { name: tr('API service role'), exact: true })).toBeVisible();
    await choose(dialog.getByRole('combobox', { name: tr('API service role'), exact: true }), 'Messages');
    await expect(dialog.getByText(tr('Connect this service to an Accounts API for identity checks and to its data domain.'), { exact: true })).toBeVisible();
    await dialog.getByRole('button', { name: tr('Preview cost and capacity'), exact: true }).click();
    await expect(dialog.getByText(tr('Connect each specialized service to an Accounts API for identity checks.'), { exact: true })).toBeVisible();
    expect(await dialog.evaluate((node) => node.scrollWidth <= node.clientWidth + 1)).toBeTruthy();
    if (process.env.VISUAL_OUTPUT_DIR) await page.screenshot({ path: `${process.env.VISUAL_OUTPUT_DIR}/engineering-config-${width}-${language}-${info.project.name || 'browser'}.png` });
    await dialog.getByRole('button', { name: tr('Cancel'), exact: true }).click();
    await page.goto(`/game/${game.id}?view=guide&article=database-sharding`);
    await expect(page.getByRole('heading', { name: tr('Database Sharding'), exact: true })).toBeVisible();
    await expect(page.locator('#example')).toContainText(tr('Messenger example'));
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  });
}

test('Engineering starts research, shows prerequisites, locks settings and resumes its walkthrough', async ({ page }) => {
  const game = await preparedGame(page, false);
  await page.goto(`/game/${game.id}?view=product`);
  await page.getByRole('tab', { name: 'Engineering', exact: true }).click();
  const research = page.getByRole('region', { name: 'Engineering', exact: true });
  const decomposition = research.getByRole('listitem').filter({ has: page.getByRole('heading', { name: 'Service Decomposition', exact: true }) });
  await decomposition.getByRole('button', { name: 'Start research' }).click();
  await expect(decomposition.getByText('In development', { exact: true })).toBeVisible();
  await expect(research.getByText('Unavailable', { exact: true })).toHaveCount(3);
  await research.getByRole('button', { name: 'Engineering walkthrough' }).click();
  const lesson = page.getByRole('complementary', { name: 'Guided onboarding' });
  await expect(lesson.getByRole('heading', { name: 'Research Service Decomposition', exact: true })).toBeVisible();
  await lesson.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(lesson.getByRole('heading', { name: 'Create a specialized service', exact: true })).toBeVisible();
  await page.reload();
  await expect(lesson.getByRole('heading', { name: 'Create a specialized service', exact: true })).toBeVisible();
  await lesson.getByRole('button', { name: 'Skip tutorial', exact: true }).click();
  await page.goto(`/game/${game.id}?view=build&component=api&configure=1`);
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByText('Unlock this setting through Engineering in Product.').first()).toBeVisible();
  await expect(dialog.getByRole('combobox', { name: 'API service role', exact: true })).toHaveCount(0);
});

test('domain, partition, query and autoscaling settings preview and persist independently of production', async ({ page }) => {
  const game = await preparedGame(page, true);
  await page.request.post(`/api/games/${game.id}/draft`, { data: { request_id: crypto.randomUUID(), revision: game.revision } });
  await page.goto(`/game/${game.id}?view=build&component=db&configure=1`);
  const dialog = page.getByRole('dialog');
  await choose(dialog.getByRole('combobox', { name: 'Data domain', exact: true }), 'Messages');
  await choose(dialog.getByRole('combobox', { name: 'Dataset membership', exact: true }), 'Partition');
  await choose(dialog.getByRole('combobox', { name: 'Query plan', exact: true }), 'History indexes');
  await choose(dialog.getByRole('combobox', { name: 'Storage type', exact: true }), 'HDD');
  await expect(dialog.getByText('126 modeled IOPS · 80% of base cost')).toBeVisible();
  await dialog.getByRole('button', { name: 'Save to draft', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  const updated = await (await page.request.get(`/api/games/${game.id}`)).json();
  const changed = updated.draft.nodes.find((n: { id: string }) => n.id === 'db');
  expect(changed.config).toMatchObject({ domain: 'Messages', partition: 'Partition', query_plan: 'History indexes', disk: 'HDD' });
  expect(updated.production).toEqual(game.production);
  await page.goto(`/game/${game.id}?view=build&component=api&configure=1`);
  await expect(dialog.getByText('Eligible demand before routing', { exact: true })).toBeVisible();
  await choose(dialog.getByRole('combobox', { name: 'Autoscaling', exact: true }), 'Enabled');
  await expect(dialog.getByRole('spinbutton', { name: 'Minimum instances', exact: true })).toBeVisible();
  await expect(dialog.getByRole('spinbutton', { name: 'Maximum instances', exact: true })).toBeVisible();
});

test('covered services expose operation, domain and cost telemetry', async ({ page }) => {
  const game = await preparedGame(page, true);
  const save = await (await page.request.get(`/api/games/${game.id}/export`)).json();
  save.game.production.nodes.push({ id: 'telemetry', kind: 'monitor', name: 'Service collector', position: { x: 0, y: 400 }, config: { slots: 16, detail: 'Service history' } });
  for (const source of ['api', 'db']) save.game.production.edges.push({ source, target: 'telemetry' });
  const imported = await page.request.post('/api/games/import', { data: save });
  expect(imported.ok(), await imported.text()).toBeTruthy();
  const summary = await imported.json();
  await page.goto(`/game/${summary.id}?view=monitor`);
  await expect(page.getByRole('heading', { name: 'Service responsibilities', exact: true })).toBeVisible();
  const telemetry = page.getByRole('article', { name: 'Service responsibilities', exact: true });
  await expect(telemetry).toContainText('Chat history');
  await expect(telemetry).toContainText('Shared');
  await expect(telemetry).toContainText('per day');
});

test('manual sharding accepts a cache link and switches production after copying', async ({ page }) => {
  const game = await preparedGame(page, true);
  const opened = await page.request.post(`/api/games/${game.id}/draft`, { data: { request_id: crypto.randomUUID(), revision: game.revision } });
  expect(opened.ok()).toBeTruthy();
  const draft = await opened.json();
  const topology = draft.draft;
  topology.nodes.find((node: { id: string }) => node.id === 'db').config = { domain: 'Messages', partition: 'Partition' };
  topology.nodes.push(
    { id: 'shard-2', kind: 'database', name: 'Second shard', config: { domain: 'Messages', partition: 'Partition' }, position: { x: 1100, y: 180 } },
    { id: 'accounts', kind: 'database', name: 'Accounts database', config: { domain: 'Accounts' }, position: { x: 900, y: 320 } },
    { id: 'router', kind: 'shard_router', name: 'Shard router', config: { domain: 'Messages' }, position: { x: 650, y: 160 } },
    { id: 'cache', kind: 'cache', name: 'Cache', config: {}, position: { x: 500, y: 320 } }
  );
  topology.edges = topology.edges.filter((edge: { source: string; target: string }) => edge.source !== 'api' || edge.target !== 'db');
  for (const [source, target] of [['api', 'accounts'], ['api', 'router'], ['api', 'cache'], ['router', 'db'], ['router', 'shard-2']]) {
    topology.edges.push({ source, target });
  }
  const edited = await page.request.put(`/api/games/${game.id}/draft`, { data: { request_id: crypto.randomUUID(), revision: draft.revision, topology } });
  expect(edited.ok(), await edited.text()).toBeTruthy();
  await page.goto(`/game/${game.id}?view=build&component=db`);
  const inspector = page.getByRole('dialog', { name: 'Component inspector' });
  await expect(inspector.getByRole('button', { name: 'Edit configuration' })).toBeVisible();
  await expect(inspector.getByRole('button', { name: 'Prepare sharding' })).toHaveCount(0);
  await inspector.getByRole('button', { name: 'Close dialog' }).click();
  await page.getByRole('button', { name: 'Connect', exact: true }).click();
  const connection = page.getByRole('dialog', { name: 'Connect components' });
  await choose(connection.getByRole('combobox', { name: 'Source component' }), { label: 'Cache' });
  await choose(connection.getByRole('combobox', { name: 'Target component' }), { label: 'Shard router' });
  await connection.getByRole('button', { name: 'Connect components' }).click();
  await expect(connection).toBeHidden();
  await page.getByRole('button', { name: 'Review deployment' }).click();
  const review = page.getByRole('dialog', { name: 'Deployment review' });
  await expect(review.getByText(/Migration preparation:/)).toBeVisible();
  await expect(review.getByText(/Shard router/).first()).toBeVisible();
  await expect(review.getByText(/Second shard/).first()).toBeVisible();
  const start = review.getByRole('button', { name: 'Start migration' });
  await expect(start).toBeEnabled();
  const current = async () => (await page.request.get(`/api/games/${game.id}`)).json();
  expect((await current()).production).toEqual(game.production);
  await start.click();
  await expect(review).toBeHidden();
  await expect(page.getByText('Production serves traffic while data is copied.', { exact: false })).toBeVisible();
  expect((await current()).production).toEqual(game.production);
  await page.getByRole('button', { name: 'Run migration' }).click();
  await expect.poll(async () => (await current()).migration, { timeout: 15_000 }).toBeNull();
  const deployed = await current();
  expect(deployed.production.nodes.filter((node: { kind: string }) => node.kind === 'shard_router')).toHaveLength(1);
  expect(deployed.production.nodes.filter((node: { config: { partition?: string } }) => node.config.partition === 'Partition')).toHaveLength(2);
  expect(deployed.production.edges).toContainEqual({ source: 'cache', target: 'router' });
});
