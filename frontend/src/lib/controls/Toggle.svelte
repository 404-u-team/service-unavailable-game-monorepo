<script lang="ts">
  import type { HTMLInputAttributes } from 'svelte/elements';
  let { checked = $bindable(false), switchStyle = false, onchange, ...attributes }: Omit<HTMLInputAttributes, 'checked' | 'onchange'> & {
    checked?: boolean; switchStyle?: boolean; onchange?: (value: boolean) => void;
  } = $props();
</script>

<input {...attributes} type="checkbox" role={switchStyle ? 'switch' : undefined} bind:checked
  onchange={(event) => onchange?.(event.currentTarget.checked)} />
