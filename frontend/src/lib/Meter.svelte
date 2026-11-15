<script lang="ts">
  import { Meter, type Tone } from '@service-unavailable/ui';
  import { pct } from './format';
  let { value, label, show = true, tone }: { value: number; label: string; show?: boolean; tone?: 'bad' | 'warn' | 'good' } = $props();
  const colors: Record<'bad' | 'warn' | 'good', Tone> = { bad: 'danger', warn: 'warning', good: 'success' };
</script>

<Meter {label} value={Number.isFinite(value) ? value * 100 : 0} valueText={pct(value)} showLabel={show}
  tone={colors[tone ?? (value >= 1 ? 'bad' : value >= 0.78 ? 'warn' : 'good')]} />
