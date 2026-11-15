<script lang="ts">
  import type { HTMLInputAttributes } from 'svelte/elements';

  let { type = 'text', value = $bindable(''), class: className, ...attrs }: Omit<HTMLInputAttributes, 'type' | 'value'> & {
    type?: 'text' | 'email' | 'password' | 'url' | 'search' | 'tel' | 'date' | 'time';
    value?: string;
  } = $props();
</script>

<input {...attrs} {type} bind:value class={['sui-control', className]} />
