<script lang="ts">
  import Choice, { type Option } from './Choice.svelte';
  import type { HTMLButtonAttributes } from 'svelte/elements';
  let { options, value = $bindable(''), label, onchange, searchable = false, ...attributes }: Omit<HTMLButtonAttributes, 'value' | 'onchange'> & {
    options: Option[]; value?: string; label: string; onchange?: (value: string) => void; searchable?: boolean;
  } = $props();
</script>

<Choice {...attributes} {options} {label} {searchable} selected={[value]}
  choose={([next]) => { value = next; onchange?.(next); }} />
