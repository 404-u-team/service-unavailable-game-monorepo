import translations from '../../../frontend/src/lib/ru.json';

const dictionary: Record<string, string> = translations;
let language = $state<'en' | 'ru'>('en');

export function setLocale(locale: unknown) {
  language = locale === 'ru' ? 'ru' : 'en';
  document.documentElement.lang = language;
}

export function t(message: string, args: readonly unknown[] = []) {
  const text = language === 'ru' ? dictionary[message] ?? message : message;
  return text.replace(/\{(\d+)\}/g, (match, index) => String(args[Number(index)] ?? match));
}

export function formatNumber(value: number) {
  return new Intl.NumberFormat(language, { maximumFractionDigits: 1 }).format(value);
}

export function stepLabels(label: string) {
  return { decrease: t('Decrease {0}', [label]), increase: t('Increase {0}', [label]) };
}
