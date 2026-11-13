import { locale, t } from './i18n.svelte';

export const num = (value: number) => new Intl.NumberFormat(locale(), { maximumFractionDigits: 1 }).format(value);
export const money = (value: number) => new Intl.NumberFormat(locale() === 'en' ? 'en-US' : 'ru-RU', {
  style: 'currency', currency: 'USD', maximumFractionDigits: 0
}).format(value);
export const preciseMoney = (value: number, digits = 2) => new Intl.NumberFormat(locale() === 'en' ? 'en-US' : 'ru-RU', {
  style: 'currency', currency: 'USD', minimumFractionDigits: digits, maximumFractionDigits: digits
}).format(value);
export const pct = (ratio: number, digits = 0) => new Intl.NumberFormat(locale(), {
  style: 'percent', minimumFractionDigits: digits, maximumFractionDigits: digits
}).format(ratio);
export const rps = (value: number) => t('{0} RPS', [num(value)]);
export const ms = (value: number) => t('{0} ms', [num(Math.round(value))]);
export const minuteClock = (minutes: number) =>
  `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
export const clock = (tick: number, start = 0, step = 10) => minuteClock((start + tick * step) % 1440);
export const when = (tick: number, start = 0, step = 10) => t('Day {0} / {1}', [Math.floor((start + tick * step) / 1440) + 1, clock(tick, start, step)]);
export const duration = (ticks: number) => {
  const minutes = ticks * 10;
  return [Math.floor(minutes / 60) ? t('{0}h', [Math.floor(minutes / 60)]) : '',
    minutes % 60 ? t('{0}m', [minutes % 60]) : ''].filter(Boolean).join(' ') || t('{0}m', [0]);
};
