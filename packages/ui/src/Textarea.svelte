<script lang="ts">
  import type { HTMLTextareaAttributes } from 'svelte/elements';

  let { value = $bindable(''), rows = 4, class: className, ...attrs }: Omit<HTMLTextareaAttributes, 'value'> & {
    value?: string;
  } = $props();
</script>

<textarea {...attrs} {rows} bind:value class={['sui-control', className]}></textarea>

<style>
  textarea { display: block; resize: vertical; }
</style>
