import { locale, t } from './i18n.svelte';

export const num = (value: number) => new Intl.NumberFormat(locale(), { maximumFractionDigits: 1 }).format(value);
export const money = (value: number) => new Intl.NumberFormat(locale() === 'en' ? 'en-US' : 'ru-RU', {
  style: 'currency', currency: 'USD', maximumFractionDigits: 0
}).format(value);
export const preciseMoney = (value: number) => new Intl.NumberFormat(locale() === 'en' ? 'en-US' : 'ru-RU', {
  style: 'currency', currency: 'USD'
}).format(value);
export const pct = (ratio: number, digits = 0) => new Intl.NumberFormat(locale(), {
  style: 'percent', minimumFractionDigits: digits, maximumFractionDigits: digits
}).format(ratio);
export const rps = (value: number) => t('{0} RPS', [num(value)]);
export const ms = (value: number) => t('{0} ms', [num(Math.round(value))]);
export const day = (tick: number) => Math.floor(tick / 144) + 1;
export const clock = (tick: number) => {
  const minutes = tick * 10 % 1440;
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
};
export const when = (tick: number) => t('Day {0} / {1}', [day(tick), clock(tick)]);
export const duration = (ticks: number) => {
  const minutes = ticks * 10;
  return [Math.floor(minutes / 60) ? t('{0}h', [Math.floor(minutes / 60)]) : '',
    minutes % 60 ? t('{0}m', [minutes % 60]) : ''].filter(Boolean).join(' ') || t('{0}m', [0]);
};
