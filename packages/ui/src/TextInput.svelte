<script lang="ts">
  import type { HTMLInputAttributes } from 'svelte/elements';

  let { type = 'text', value = $bindable(''), element = $bindable<HTMLInputElement>(), class: className, ...attrs }: Omit<HTMLInputAttributes, 'type' | 'value'> & {
    type?: 'text' | 'email' | 'password' | 'url' | 'search' | 'tel' | 'date' | 'time';
    value?: string;
    element?: HTMLInputElement;
  } = $props();
</script>

<input {...attrs} {type} bind:value bind:this={element} class={['sui-control', className]} />
