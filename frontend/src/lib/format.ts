const numberFormat = new Intl.NumberFormat('en', { maximumFractionDigits: 1 });
const moneyFormat = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const preciseMoneyFormat = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

export const num = (value: number) => numberFormat.format(value);
export const money = (value: number) => moneyFormat.format(value);
export const preciseMoney = (value: number) => preciseMoneyFormat.format(value);
export const pct = (ratio: number, digits = 0) => `${(ratio * 100).toFixed(digits)}%`;
export const rps = (value: number) => `${num(value)} RPS`;
export const ms = (value: number) => `${Math.round(value)} ms`;
export const day = (tick: number) => Math.floor(tick / 144) + 1;
export const clock = (tick: number) => {
  const minutes = tick * 10 % 1440;
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
};
export const when = (tick: number) => `Day ${day(tick)} / ${clock(tick)}`;
export const duration = (ticks: number) => {
  const minutes = ticks * 10;
  return [Math.floor(minutes / 60) ? `${Math.floor(minutes / 60)}h` : '', minutes % 60 ? `${minutes % 60}m` : ''].filter(Boolean).join(' ') || '0m';
};
