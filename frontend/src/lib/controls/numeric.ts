export function parseNumber(text: string, language: 'en' | 'ru'): number | undefined {
  const normalized = text.trim().replace(/[−–]/g, '-');
  const pattern = language === 'ru'
    ? /^[+-]?(?:\d+|\d{1,3}(?:[ \u00a0\u202f]\d{3})+)?(?:[.,]\d+)?$/
    : /^[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)?(?:\.\d+)?$/;
  if (!pattern.test(normalized) || !/\d/.test(normalized)) return undefined;
  const number = Number(language === 'ru' ? normalized.replace(/\s/g, '').replace(',', '.') : normalized.replaceAll(',', ''));
  return Number.isFinite(number) ? number : undefined;
}
