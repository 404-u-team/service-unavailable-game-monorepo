<script lang="ts">
  import type { HTMLInputAttributes } from 'svelte/elements';
  let { value = $bindable(''), ...attributes }: Omit<HTMLInputAttributes, 'value'> & { value?: string } = $props();
</script>

<input {...attributes} bind:value />
