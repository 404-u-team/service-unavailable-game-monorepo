import { type Locator } from '@playwright/test';

export async function choose(control: Locator, option: string | { label: string }) {
  await control.click();
  const list = control.page().getByRole('listbox');
  const item = typeof option === 'string'
    ? list.locator(`[data-value=${JSON.stringify(option)}]`)
    : list.getByRole('option', { name: option.label, exact: true });
  await item.click();
}
