import { expect, test } from '@playwright/test';

function story(id: string) {
  return '/iframe.html?id=' + id + '&viewMode=story';
}

test('manual slider entry synchronizes only when valid and submits one value', async ({ page }) => {
  await page.goto(story('patterns-workbench--capacity-overview'));
  await page.getByRole('button', { name: 'Service settings' }).click();
  const dialog = page.getByRole('dialog', { name: 'Service settings' });
  const slider = dialog.getByRole('slider', { name: 'Traffic allocation' });
  const number = dialog.getByRole('spinbutton', { name: 'Exact traffic allocation' });
  await expect(number).toHaveValue('65');

  await number.fill('73');
  await expect(slider).toHaveValue('65');
  await dialog.getByRole('button', { name: 'Save settings' }).click();
  await expect(dialog).toBeVisible();
  await number.fill('75');
  await expect(slider).toHaveValue('75');
  await slider.press('ArrowRight');
  await expect(number).toHaveValue('80');

  await dialog.getByRole('button', { name: 'Increase Traffic allocation' }).click();
  await expect(slider).toHaveValue('85');
  expect(await dialog.locator('form').evaluate((form: HTMLFormElement) => new FormData(form).getAll('traffic'))).toEqual(['85']);
  await dialog.getByRole('button', { name: 'Save settings' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole('region', { name: 'Notifications' })).toContainText('Settings saved');
});

test('form associates hints, validates email, and submits named controls', async ({ page }) => {
  await page.goto(story('inputs-controls--form-submission'));
  const email = page.getByRole('textbox', { name: 'Email' });
  await expect(email).toHaveAccessibleDescription('We use this address for service alerts.');
  await email.fill('bogus');
  await page.getByRole('button', { name: 'Save settings' }).click();
  await expect(page.getByRole('status')).toBeEmpty();
  await email.fill('ops@example.test');
  await page.getByRole('checkbox', { name: 'Send weekly reports' }).press('Space');
  await expect(page.getByRole('checkbox')).toBeChecked();
  await page.getByRole('button', { name: 'Save settings' }).click();
  await expect(page.getByRole('status')).toHaveText('Settings saved for ops@example.test.');
});

test('number buttons preserve decimal steps and bounds', async ({ page }) => {
  await page.goto(story('inputs-controls--number-input'));
  const price = page.getByRole('spinbutton', { name: 'Premium price' });
  await expect(price).toHaveAccessibleDescription('USD');
  await page.getByRole('button', { name: 'Increase Premium price' }).click();
  await expect(price).toHaveValue('5');
  await page.getByRole('button', { name: 'Decrease Premium price' }).click();
  await expect(price).toHaveValue('4.99');
  await price.fill('0');
  await expect(page.getByRole('button', { name: 'Decrease Premium price' })).toBeDisabled();
});

test('custom select validates, skips disabled options, and submits the selected value', async ({ page }) => {
  await page.goto(story('inputs-controls--select'));
  const trigger = page.getByRole('combobox', { name: 'Region' });
  const submit = page.getByRole('button', { name: 'Save settings' });
  await expect(trigger).toHaveText('Choose a region');
  await submit.click();
  await expect(page.getByRole('status')).toBeEmpty();
  await expect(trigger).toBeFocused();
  await trigger.press('ArrowDown');
  const list = page.getByRole('listbox');
  await expect(list).toBeVisible();
  await expect(list.getByRole('option', { name: 'Asia Pacific' })).toHaveAttribute('data-disabled', '');
  await trigger.press('End');
  await trigger.press('Enter');
  await expect(list).toBeHidden();
  await expect(trigger).toHaveText('North America');
  expect(await page.locator('form').evaluate((form: HTMLFormElement) => new FormData(form).get('region'))).toBe('na');
  await submit.click();
  await expect(page.getByRole('status')).toHaveText('Settings saved');
});

test('custom checkbox renders mixed, checked, and disabled states', async ({ page }) => {
  await page.goto(story('inputs-controls--checkbox-and-switch'));
  const checkbox = page.getByRole('checkbox', { name: 'Select all regions' });
  await expect(checkbox).toHaveJSProperty('indeterminate', true);
  await checkbox.press('Space');
  await expect(checkbox).toHaveJSProperty('indeterminate', false);
  await expect(checkbox).toBeChecked();
  await page.getByText('Select all regions', { exact: true }).click();
  await expect(checkbox).not.toBeChecked();
  await expect(page.getByRole('checkbox', { name: 'Include migration history' })).toBeDisabled();
});

test('tabs and actions support keyboard navigation and skip disabled entries', async ({ page }) => {
  await page.goto(story('navigation-navigation--tabs'));
  const overview = page.getByRole('tab', { name: 'Overview' });
  const telemetry = page.getByRole('tab', { name: 'Telemetry' });
  await overview.focus();
  await overview.press('ArrowRight');
  await expect(telemetry).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('tabpanel')).toHaveText('Recent measurements from monitored servers.');
  await telemetry.press('ArrowRight');
  await expect(overview).toBeFocused();

  await page.goto(story('navigation-navigation--action-dropdown'));
  const trigger = page.getByRole('button', { name: 'Server actions' });
  await trigger.press('ArrowDown');
  await expect(page.getByRole('menuitem', { name: 'Compare' })).toBeFocused();
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('menuitem', { name: 'Remove server' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('status')).toHaveText('Removal requested.');
  await expect(trigger).toBeFocused();
});

test('overlays constrain focus and restore it on close', async ({ page }) => {
  await page.goto(story('overlays-feedback-and-overlays--slideover'));
  const trigger = page.getByRole('button', { name: 'Open server settings' });
  await trigger.press('Enter');
  const dialog = page.getByRole('dialog');
  const close = dialog.getByRole('button', { name: 'Close dialog' });
  await expect(close).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(dialog.getByRole('button', { name: 'Save settings' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();

  await page.goto(story('overlays-feedback-and-overlays--modal'));
  const review = page.getByRole('button', { name: 'Open deployment review' });
  await review.press('Enter');
  await expect(page.getByRole('dialog', { name: 'Review deployment' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(review).toBeFocused();
});

test('slideover slides in and out and resizes by keyboard and drag', async ({ page }) => {
  await page.goto(story('overlays-feedback-and-overlays--slideover'));
  await page.addStyleTag({ content: ':root { --sui-motion: 650ms; }' });
  const opener = page.getByRole('button', { name: 'Open server settings' });
  await opener.click();
  const panel = page.getByRole('dialog');
  await expect.poll(() => panel.evaluate((element) => element.getBoundingClientRect().right - innerWidth)).toBeGreaterThan(5);
  const handle = panel.getByRole('separator', { name: 'Resize side panel' });
  await expect(handle).toHaveAttribute('aria-valuenow', '448');
  await handle.press('ArrowLeft');
  await expect(handle).toHaveAttribute('aria-valuenow', '464');
  await handle.press('Home');
  await expect(handle).toHaveAttribute('aria-valuenow', '320');
  await panel.evaluate((node) => Promise.all(node.getAnimations().map((animation) => animation.finished)));
  const box = (await handle.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 - 75, box.y + box.height / 2, { steps: 5 });
  await page.mouse.up();
  await expect(handle).toHaveAttribute('aria-valuenow', '395');
  await expect(panel).toHaveCSS('width', '395px');
  await page.keyboard.press('Escape');
  const ending = page.locator('.sui-overlay[data-ending-style]');
  await expect(ending).toBeAttached();
  await expect(ending).not.toBeAttached();
  await expect(opener).toBeFocused();
  await opener.press('Enter');
  await expect(handle).toHaveAttribute('aria-valuenow', '395');
});

test('tooltip works with keyboard and hover', async ({ page }) => {
  await page.goto(story('overlays-feedback-and-overlays--tooltip'));
  const help = page.getByRole('button', { name: 'About capacity targets' });
  await expect(help).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(help).toBeFocused();
  await expect(page.getByRole('tooltip')).toBeVisible();
  await expect(help).toHaveAccessibleDescription(/requests that the current topology can serve/);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('tooltip')).toBeHidden();
  await help.hover();
  await expect(page.getByRole('tooltip')).toBeVisible();
});

test('toasts announce outcomes and retain focus as items are dismissed', async ({ page }) => {
  await page.goto(story('overlays-feedback-and-overlays--toasts'));
  await page.getByRole('button', { name: 'Show success' }).click();
  await page.getByRole('button', { name: 'Show error' }).click();
  await expect(page.locator('[aria-live=polite]')).toContainText('Settings saved');
  await expect(page.locator('[aria-live=assertive]')).toContainText('Deployment failed');
  await page.getByRole('button', { name: 'Dismiss Settings saved' }).press('Enter');
  await expect(page.getByRole('button', { name: 'Dismiss Deployment failed' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('region', { name: 'Notifications' })).toBeHidden();
});

test('toast countdown pauses on focus and dismisses automatically after resuming', async ({ page }) => {
  await page.goto(story('overlays-feedback-and-overlays--toasts'));
  const trigger = page.getByRole('button', { name: 'Show success' });
  await trigger.click();
  const toast = page.getByRole('region', { name: 'Notifications' });
  const timer = toast.locator('.timer');
  await expect(timer).toHaveCSS('height', '2px');
  const close = toast.getByRole('button', { name: 'Dismiss Settings saved' });
  await close.focus();
  await expect(timer).toHaveCSS('animation-play-state', 'paused');
  await trigger.focus();
  await expect(timer).toHaveCSS('animation-play-state', 'running');
  await expect(toast).toBeHidden({ timeout: 9000 });
});

test('chart exposes actual values and preserves a missing measurement', async ({ page }) => {
  await page.goto(story('data-visualization--line-chart'));
  const inspect = page.getByRole('button', { name: 'Inspect samples' });
  await inspect.press('Home');
  const tooltip = page.getByRole('tooltip');
  await expect(tooltip).toContainText('08:00');
  await inspect.press('ArrowRight');
  await expect(tooltip).toContainText('09:00');
  await inspect.press('ArrowRight');
  await inspect.press('ArrowRight');
  await expect(tooltip).toContainText('11:00');
  await expect(tooltip).toContainText('No sample recorded');
  await inspect.press('End');
  await expect(tooltip).toContainText('246');
  await inspect.press('Escape');
  await expect(tooltip).toBeHidden();
  await expect(page.getByText('View chart data', { exact: true })).toHaveCount(0);
});

test('workbench columns fit a narrow viewport and the chart can be inspected by touch', async ({ browser, browserName, baseURL }) => {
  test.skip(browserName === 'firefox', 'Firefox Playwright does not emulate touch.');
  const context = await browser.newContext({ baseURL, viewport: { width: 320, height: 780 }, hasTouch: true, isMobile: true });
  try {
    const page = await context.newPage();
    await page.goto(story('patterns-workbench--capacity-overview') + '&globals=locale:ru');
    await expect(page.getByRole('heading', { name: 'Обзор сервиса' })).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
    await page.getByRole('button', { name: 'Просмотреть замеры' }).tap();
    const sample = page.getByRole('tooltip');
    await expect(sample).toContainText('11:00');
    const box = (await sample.boundingBox())!;
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(320);
    await page.getByRole('button', { name: 'Настройки сервиса' }).tap();
    const panel = page.getByRole('dialog');
    await expect(panel).toHaveCSS('width', '320px');
    await expect(panel.getByRole('separator')).toBeHidden();
    await page.goto(story('overlays-feedback-and-overlays--tooltip'));
    await page.getByRole('button', { name: 'About capacity targets' }).tap();
    await expect(page.getByRole('tooltip')).toBeVisible();
  } finally {
    await context.close();
  }
});
