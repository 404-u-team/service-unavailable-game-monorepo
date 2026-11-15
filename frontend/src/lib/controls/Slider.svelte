<script lang="ts">
  import { Slider } from '@service-unavailable/ui';

  let { label, value, min, max, step, onchange }: {
    label: string; value: number; min: number; max: number; step: number; onchange: (value: number) => void;
  } = $props();
</script>

<Slider aria-label={label} {min} {max} {step} allowOffStep bind:value={() => value, onchange} />
