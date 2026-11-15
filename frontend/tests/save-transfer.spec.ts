import { readFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import type { Game } from '../src/lib/types';

for (const locale of ['en', 'ru'] as const) {
  for (const width of [1440, 390]) {
    test(`save file transfer in ${locale} at ${width}px`, async ({ browser, baseURL }) => {
      const options = { baseURL, viewport: { width, height: 900 }, acceptDownloads: true, hasTouch: width < 500 };
      const source = await browser.newContext(options);
      const destination = await browser.newContext(options);
      try {
        for (const context of [source, destination]) {
          await context.addInitScript((language) => localStorage.setItem('workbench-language', language), locale);
        }
        const name = 'Transfer Messenger';
        const requestId = () => ({ request_id: crypto.randomUUID() });
        const id = crypto.randomUUID();
        const created = await source.request.post('/api/games', {
          data: { id, name, seed: 29, settings: { show_tutorial: false } }
        });
        expect(created.status()).toBe(201);
        const layout = {
          positions: { db: { x: 940, y: 260 } },
          routes: { 'api:db': [{ x: 825, y: 256 }] },
          groups: [{ id: 'data', name: 'Data layer', members: ['db'], collapsed: true }]
        };
        expect((await source.request.put(`/api/games/${id}/diagram`, { data: { ...requestId(), diagram: layout } })).ok()).toBeTruthy();
        const draftResponse = await source.request.post(`/api/games/${id}/draft`, {
          data: { ...requestId(), revision: 0 }
        });
        expect(draftResponse.ok()).toBeTruthy();
        const original: Game = await draftResponse.json();

        const savedGames = await source.newPage();
        await savedGames.goto('/?view=saves');
        const downloading = savedGames.waitForEvent('download');
        await savedGames.getByRole('button', { name: locale === 'en' ? `Export ${name}` : `Экспортировать «${name}»` }).click();
        const download = await downloading;
        expect(download.suggestedFilename()).toMatch(/^service-unavailable-transfer-messenger-\d{4}-\d{2}-\d{2}\.json$/);
        const file = await readFile((await download.path())!);

        const receiving = await destination.newPage();
        await receiving.goto('/?view=saves');
        const upload = receiving.getByLabel(locale === 'en' ? 'Select a save file' : 'Выбрать файл сохранения');
        await expect(upload).toBeEnabled();
        const uploadBytes = (bytes: Buffer) => upload.setInputFiles({ name: download.suggestedFilename(), mimeType: 'application/json', buffer: bytes });
        await uploadBytes(Buffer.from(JSON.stringify({ ...JSON.parse(file.toString()), version: 99 })));
        await expect(receiving.getByRole('alert')).toHaveText(locale === 'en'
          ? 'This save file version is unsupported.' : 'Эта версия файла сохранения не поддерживается.');
        await uploadBytes(file);
        const preview = receiving.getByRole('dialog', { name: locale === 'en' ? 'Import preview' : 'Просмотр сохранения перед импортом' });
        await expect(preview.getByText(name)).toBeVisible();
        await expect(preview.getByText(locale === 'en' ? 'Save version' : 'Версия сохранения')).toBeVisible();
        await expect(preview.getByText(locale === 'en' ? 'Export date' : 'Дата экспорта')).toBeVisible();
        await preview.getByRole('button', { name: locale === 'en' ? 'Import as new save' : 'Импортировать как новое сохранение' }).click();
        await expect(receiving.getByRole('region', { name: locale === 'en' ? 'Notifications' : 'Уведомления' })).toContainText(locale === 'en' ? 'Save imported successfully.' : 'Сохранение успешно импортировано.');
        const imported = receiving.getByRole('link', { name: locale === 'en' ? 'Open imported save' : 'Открыть импортированное сохранение' });
        const copyId = (await imported.getAttribute('href'))!.split('/')[2].split('?')[0];
        expect(copyId).not.toBe(id);
        expect((await destination.request.get(`/api/games/${id}/export`)).status()).toBe(404);
        await imported.click();
        await expect(receiving.getByRole('heading', { level: 1, name: locale === 'en'
          ? (width < 500 ? 'Topology' : 'Infrastructure topology')
          : (width < 500 ? 'Архитектура' : 'Топология инфраструктуры'), exact: true })).toBeVisible();
        const copy: Game = await (await destination.request.get(`/api/games/${copyId}`)).json();
        for (const field of ['name', 'tick', 'balance', 'audience', 'production', 'draft', 'diagram'] as const) {
          expect(copy[field]).toEqual(original[field]);
        }
        await expect(receiving.getByText('Data layer', { exact: true }).first()).toBeVisible();
      } finally {
        await Promise.all([source.close(), destination.close()]);
      }
    });
  }
}
