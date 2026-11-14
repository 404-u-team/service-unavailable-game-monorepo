<script lang="ts">
  let { label, value, min, max, step, onchange }: {
    label: string; value: number; min: number; max: number; step: number; onchange: (value: number) => void;
  } = $props();

  function update(raw: number) {
    const next = min + Math.round((raw - min) / step) * step;
    onchange(Math.min(max, Math.max(min, Number(next.toFixed(4)))));
  }

  function keys(event: KeyboardEvent) {
    if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      onchange(event.key === 'Home' ? min : max);
    } else if (['ArrowUp', 'ArrowRight', 'ArrowDown', 'ArrowLeft'].includes(event.key)) {
      event.preventDefault();
      update(value + (event.key === 'ArrowUp' || event.key === 'ArrowRight' ? step : -step));
    }
  }
</script>
<input type="range" aria-label={label} {min} {max} step="any" {value}
  onkeydown={keys} oninput={(event) => update(event.currentTarget.valueAsNumber)} />

<style>
  input { display: block; width: 100%; min-height: 22px; margin: 0; padding: 0; accent-color: var(--primary); cursor: pointer; }
</style>
